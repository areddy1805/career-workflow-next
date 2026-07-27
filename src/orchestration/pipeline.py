from __future__ import annotations

import json
import os
import resource
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from application_report import build_report_snapshot
from config.candidate_profile import CANDIDATE_PROFILE
from monitor_applications import reconcile_application_history
from src.application.ledger import ApplicationLedger
from src.application.manual_action_queue import ManualActionQueue
from src.application.policy import ApplicationPolicy
from src.client.job_classifier import JobFilterPipeline2
from src.client.job_client import NaukriJobClient
from src.config.search_strategy import load_search_strategy
from src.client.inference_service import InferenceService

from src.client.naukri_client import NaukriLoginClient
from src.llm.client import OMLXClient
from src.llm.question_resolver import LLMQuestionResolver
from src.orchestration.provider_factory import initialize_providers

from src.orchestration.context import PipelineContext
from src.orchestration.result import PipelineResult
from src.orchestration.runtime import PipelineLock, effective_limit
from src.orchestration.stages import (
    PIPELINE_STAGES,
    PipelineStatus,
    StageStatus,
)
from src.orchestration.explorer import PipelineExplorerRenderer
from src.orchestration.opportunity import ApplicationOpportunity
from src.orchestration.opportunity_repository import OpportunityRepository
from src.orchestration.priority_engine import PriorityEngine
from src.orchestration.capacity_planner import CapacityPlanner
from src.orchestration.capacity import CapacityModel
from src.orchestration.application_scheduler import ApplicationScheduler

from src.constraints.age_expiry import AgeExpiryConstraint
from src.constraints.company_cap import CompanyCapConstraint
from src.constraints.duplicate_check import DuplicateConstraint
from src.constraints.provider_quota import ProviderQuotaConstraint
from src.constraints.quality_threshold import QualityConstraint
from src.constraints.resume_minimum import ResumeMinimumConstraint

from src.resolution.hybrid_resolver import HybridQuestionResolver
from src.search.challenge_cooldown import SearchChallengeCooldown
from src.search.job_search_cache import JobSearchCache
from src.cache.cache_manager import CacheManager

# Legacy acquisition/classification functions still needed for those stages
from src.legacy_apply_agent import acquire_jobs, enrich_jobs_with_details, enrich_application_metadata, print_acquisition_summary, print_pipeline_results
from src.application.adaptive_strategy import build_adaptive_strategy, AdaptiveStrategyConfig, strategy_audit_payload
from src.application.diversity import deduplicate_enriched_jobs, description_fingerprint

load_dotenv()


class CareerWorkflowPipeline:
    def __init__(
        self,
        *,
        dry_run: bool,
        max_applications: int | None,
        acquisition_mode: str = "full",
        force_live: bool = False,
        acquisition_provider: str = "all",
        artifacts_root: str | Path = "artifacts/runs",
        test_mode: bool = False,
    ) -> None:
        if max_applications is not None and max_applications < 0:
            raise ValueError("max_applications must be greater than or equal to zero")

        self.context = PipelineContext(
            run_id=self._generate_run_id(),
            dry_run=dry_run,
            max_applications=max_applications,
            acquisition_mode=acquisition_mode,
            force_live=force_live,
            acquisition_provider=acquisition_provider,
            test_mode=test_mode,
        )

        self.artifacts_root = Path(
            artifacts_root,
        )

        self.run_dir = self.artifacts_root / self.context.run_id

        from src.orchestration.execution_context import PipelineExecutionContext

        self.exec_context = PipelineExecutionContext(self.context.run_id, self.run_dir)

        self.stage_statuses = {stage: StageStatus.PENDING for stage in PIPELINE_STAGES}

        self.status = PipelineStatus.RUNNING

        from src.orchestration.projections import (
            MetricsProjection,
            ExplorerProjection,
            JobTraceProjection,
        )

        self.metrics_proj = MetricsProjection()
        self.explorer_proj = ExplorerProjection(fingerprint={})
        self.trace_proj = JobTraceProjection()

        self.exec_context.bus.subscribe(self.metrics_proj)
        self.exec_context.bus.subscribe(self.explorer_proj)
        self.exec_context.bus.subscribe(self.trace_proj)
        # Load config hashes for fingerprinting
        from src.config.search_strategy import load_search_strategy
        import yaml

        try:
            with open("config/search_strategy.yaml", "r") as f:
                s_dict = yaml.safe_load(f)
            self.exec_context.set_config_fingerprint(CANDIDATE_PROFILE, s_dict)
            self.explorer_proj.fingerprint = s_dict
        except Exception:
            pass

        self.inference_service = InferenceService(cache_manager=self.context.cache_manager)

    @staticmethod
    def _generate_run_id() -> str:
        if env_id := os.getenv("CW_RUN_ID"):
            return env_id
        return datetime.now(
            timezone.utc,
        ).strftime("%Y%m%dT%H%M%S%fZ")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def initialize_run(self) -> None:
        self.run_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._persist_state()
        self._update_global_pipeline_state(current_stage="STARTING")

        try:
            from config.candidate_profile import CANDIDATE_PROFILE
            profile_name = CANDIDATE_PROFILE.get("name", "Unknown")
        except Exception:
            profile_name = "Unknown"
        try:
            self.exec_context.emit_run_started(
                profile=profile_name,
                mode="live" if not self.context.dry_run else "dry-run",
                provider=self.context.acquisition_provider,
                max_applications=self.context.max_applications,
                dry_run=self.context.dry_run,
            )
        except Exception:
            pass

    def _update_global_pipeline_state(self, current_stage: str | None = None) -> None:
        state_path = Path(
            os.getenv("PIPELINE_STATE_PATH", "data/ui_runtime/pipeline_state.json")
        )
        state_path.parent.mkdir(parents=True, exist_ok=True)

        status = self.status.value
        completed_at = None
        if status in ("SUCCESS", "FAILED", "PARTIAL"):
            completed_at = datetime.now(timezone.utc).isoformat()

        payload = {
            "status": status,
            "pid": os.getpid(),
            "run_id": self.context.run_id,
            "current_stage": current_stage,
            "started_at": self.context.started_at.isoformat(),
            "completed_at": completed_at,
        }

        temp_path = state_path.with_suffix(".tmp")
        try:
            temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temp_path.replace(state_path)
        except OSError:
            pass  # Best effort

    def _persist_state(self) -> None:
        payload = {
            "run_id": self.context.run_id,
            "status": self.status.value,
            "dry_run": self.context.dry_run,
            "max_applications": (self.context.max_applications),
            "started_at": (self.context.started_at.isoformat()),
            "counts": {
                "acquired": len(self.context.acquired_jobs),
                "classified": len(self.context.classified_jobs),
                "selected": len(self.context.selected_jobs),
            },
            "stages": {
                name: status.value for name, status in self.stage_statuses.items()
            },
            "errors": self.context.errors,
        }

        self._write_artifact("run.json", payload)

    def _write_artifact(
        self,
        filename: str,
        payload,
    ) -> None:
        self.run_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        envelope = {
            "schema_version": 2,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": self.context.run_id,
            "data": payload,
        }

        target = self.run_dir / filename

        temporary = target.with_suffix(target.suffix + ".tmp")

        temporary.write_text(
            json.dumps(
                envelope,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

        temporary.replace(
            target,
        )

        if filename not in self.context.generated_artifacts:
            self.context.generated_artifacts.append(filename)

        self._write_manifest()

    def _write_manifest(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "run_id": self.context.run_id,
            "status": self.status.value,
            "schema_version": 2,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "artifacts": self.context.generated_artifacts,
        }
        target = self.run_dir / "manifest.json"
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        tmp.replace(target)

    # ------------------------------------------------------------------
    # Stage execution
    # ------------------------------------------------------------------

    def _run_stage(
        self,
        name: str,
        function: Callable[[], None],
        *,
        fatal: bool,
    ) -> bool:
        self.stage_statuses[name] = StageStatus.RUNNING

        self._persist_state()
        self._update_global_pipeline_state(current_stage=name)

        print(f"\n[PIPELINE] {name.upper()} STARTED")

        stage_record = {
            "stage": name,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "duration_ms": 0,
            "status": "RUNNING",
            "error": None,
            "metadata": {},
        }
        self.context.timeline.append(stage_record)

        try:
            import time

            start_time = time.perf_counter()
            function()
            duration = time.perf_counter() - start_time

            # Record total runtime metrics depending on the stage
            if self.context.metrics:
                self.context.metrics.total_runtime += duration
                if name == "acquire":
                    self.context.metrics.add_network_time(duration)
                elif name == "classify":
                    # classify mixes LLM and network (details fetching) and local filtering.
                    # We subtract llm_time and network_time tracked deeply.
                    pass

            stage_record["duration_ms"] = int(duration * 1000)

        except Exception as error:
            import traceback

            print("\n========== FULL TRACEBACK ==========\n")
            traceback.print_exc()
            print("\n====================================\n")
            self.stage_statuses[name] = StageStatus.FAILED

            stage_record["completed_at"] = datetime.now(timezone.utc).isoformat()
            stage_record["status"] = "FAILED"
            stage_record["error"] = str(error)

            self._write_artifact("timeline.json", self.context.timeline)

            self.context.record_error(
                stage=name,
                error=error,
                fatal=fatal,
            )

            self.status = PipelineStatus.FAILED if fatal else PipelineStatus.PARTIAL

            self._persist_state()

            print(
                f"[PIPELINE] {name.upper()} FAILED: " f"{type(error).__name__}: {error}"
            )

            return False

        self.stage_statuses[name] = StageStatus.SUCCESS

        stage_record["completed_at"] = datetime.now(timezone.utc).isoformat()
        stage_record["status"] = "SUCCESS"
        self._write_artifact("timeline.json", self.context.timeline)

        self._persist_state()

        print(f"[PIPELINE] {name.upper()} SUCCESS")

        return True

    # ------------------------------------------------------------------
    # Preflight
    # ------------------------------------------------------------------

    def preflight(self) -> None:
        if not self.context.test_mode:
            username = os.getenv("NAUKRI_USERNAME")
            password = os.getenv("NAUKRI_PASSWORD")

            if not username:
                raise RuntimeError("NAUKRI_USERNAME environment variable is not set")

            if not password:
                raise RuntimeError("NAUKRI_PASSWORD environment variable is not set")

        ledger_path = os.getenv(
            "APPLICATION_LEDGER_PATH",
            "data/application_ledger.db",
        )

        Path(
            ledger_path,
        ).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.context.ledger = ApplicationLedger(
            ledger_path,
        )

        self.context.cache_manager = CacheManager()

        self.context.stage_results["preflight"] = {
            "credentials_present": True,
            "candidate_profile_loaded": bool(CANDIDATE_PROFILE),
            "ledger_path": ledger_path,
        }

        self._write_artifact(
            "preflight.json",
            self.context.stage_results["preflight"],
        )

        import platform, sys

        diagnostics = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "hostname": platform.node(),
            "pid": os.getpid(),
            "cwd": os.getcwd(),
            "virtualenv": os.environ.get("VIRTUAL_ENV"),
        }

        try:
            import psutil

            diagnostics["cpu_count"] = psutil.cpu_count()
            diagnostics["memory_total"] = psutil.virtual_memory().total
        except ImportError:
            pass

        try:
            import subprocess

            diagnostics["git_commit"] = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip()
        except Exception:
            diagnostics["git_commit"] = None

        try:
            import nicegui

            diagnostics["nicegui_version"] = nicegui.__version__
        except Exception:
            diagnostics["nicegui_version"] = None

        self._write_artifact("diagnostics.json", diagnostics)

        environment = {
            "max_applications": self.context.max_applications,
            "acquisition_mode": self.context.acquisition_mode,
            "llm_model": os.environ.get("OMLX_MODEL", "qwen3.5-4b"),
            "daily_apply_limit": int(os.environ.get("DAILY_APPLY_LIMIT", "500")),
            "min_apply_score": int(os.environ.get("MIN_APPLY_SCORE", "75")),
            "ai_score_limit": int(os.environ.get("AI_SCORE_LIMIT", "300")),
            "batch_size": int(os.environ.get("BATCH_SIZE", "5")),
            "job_search_cache_ttl_days": int(
                os.environ.get("JOB_SEARCH_CACHE_TTL_DAYS", "3")
            ),
            "search_challenge_cooldown_minutes": int(
                os.environ.get("SEARCH_CHALLENGE_COOLDOWN_MINUTES", "120")
            ),
            "application_delay_seconds": int(
                os.environ.get("APPLICATION_DELAY_SECONDS", "3")
            ),
        }
        self._write_artifact("environment.json", environment)

        try:
            self.exec_context.emit_health("artifacts", "healthy", f"Run dir: {self.run_dir}")
            import sqlite3 as _sq3
            _c = _sq3.connect(":memory:")
            _c.execute("PRAGMA journal_mode=WAL")
            _c.close()
            self.exec_context.emit_health("sqlite", "healthy", "WAL mode available")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Acquisition
    # ------------------------------------------------------------------

    def acquire(self) -> None:

        job_cache = JobSearchCache(
            path=os.getenv(
                "JOB_SEARCH_CACHE_PATH",
                "data/job_search_cache.json",
            ),
            ttl_days=int(
                os.getenv(
                    "JOB_SEARCH_CACHE_TTL_DAYS",
                    "3",
                )
            ),
        )

        search_cooldown = SearchChallengeCooldown(
            path=os.getenv(
                "SEARCH_CHALLENGE_STATE_PATH",
                "data/search_challenge_state.json",
            ),
            cooldown_minutes=int(
                os.getenv(
                    "SEARCH_CHALLENGE_COOLDOWN_MINUTES",
                    "60",
                )
            ),
        )

        self.context.providers = initialize_providers(
            self.context.acquisition_provider,
            test_mode=self.context.test_mode,
        )

        jobs, fetch_result = acquire_jobs(
            providers=self.context.providers,
            cache=job_cache,
            cooldown=search_cooldown,
            mode=self.context.acquisition_mode,
            force_live=self.context.force_live,
        )

        self.context.acquired_jobs = jobs

        self.context.fetch_result = fetch_result

        self.exec_context.start_stage("Acquisition", [])
        for job in jobs:
            self.exec_context.acquire(job)
            self.exec_context.complete(job)
        self.exec_context.finish_stage(self.context.acquired_jobs)

        print_acquisition_summary(
            jobs=jobs,
            fetch_result=fetch_result,
        )

        self.context.stage_results["acquisition"] = {
            "jobs": len(jobs),
            "challenge_encountered": (fetch_result.challenge_encountered),
            "cooldown_suppressed": (fetch_result.search_skipped_due_to_cooldown),
            "mode": self.context.acquisition_mode,
            "search_requests_attempted": fetch_result.search_requests_attempted,
            "pages_stopped_low_yield": fetch_result.pages_stopped_low_yield,
            "stop_reasons": fetch_result.stop_reasons,
            "jobspy_health": getattr(fetch_result, "jobspy_health", {}),
        }

        self._write_artifact(
            "acquisition.json",
            self.context.stage_results["acquisition"],
        )

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify(self) -> None:
        jobs = self.context.acquired_jobs
        self.exec_context.start_stage("Classification", jobs)

        classifier = JobFilterPipeline2(
            metrics=self.context.metrics,
            exec_context=self.exec_context,
            test_mode=self.context.test_mode,
            inference_service=self.inference_service,
        )

        jobs = classifier.normalize_jobs(jobs)
        jobs = classifier.dedup(jobs)
        jobs = classifier.impossible_filter(jobs)
        jobs = classifier.experience_filter(jobs)
        jobs = classifier.desc_red_flag_check(jobs)
        jobs = classifier.title_filter(jobs)
        jobs = classifier.ai_relevance_gate(jobs)

        # SUMMARY RANKING
        # tag_presort now acts as our cheap heuristic summary ranker
        jobs = classifier.tag_presort(jobs)

        # FIXED-BUCKET SUMMARY SCORE DISTRIBUTION
        summary_distribution = {}
        for j in jobs:
            score = j.get("summary_score", 0)
            bin_start = (int(score) // 5) * 5
            bin_end = bin_start + 5
            bin_label = f"{bin_start}-{bin_end}"
            summary_distribution[bin_label] = summary_distribution.get(bin_label, 0) + 1

        self._write_artifact(
            "summary_distribution.json",
            dict(
                sorted(
                    summary_distribution.items(),
                    key=lambda item: int(item[0].split("-")[0]),
                )
            ),
        )

        # Fetch Details for ALL survivors of the Impossible Filter
        candidates = jobs
        candidates_before_suppression = len(candidates)

        import sys
        print(f"[PIPELINE DEBUG] About to enter enrich_jobs_with_details with {len(candidates)} candidates", file=sys.stderr, flush=True)

        enriched_candidates = enrich_jobs_with_details(
            providers=self.context.providers,
            jobs=candidates,
            detail_cache=(self.context.detail_cache),
            cache_manager=self.context.cache_manager,
            run_dir=self.run_dir,
        )
        
        print(f"[PIPELINE DEBUG] Exited enrich_jobs_with_details", file=sys.stderr, flush=True)

        enriched_before_dedup = len(enriched_candidates)
        _before_dedup = enriched_candidates
        enriched_candidates = deduplicate_enriched_jobs(enriched_candidates)
        # Fire rejection events for jobs silently dropped by deduplicate_enriched_jobs
        # so that pre_app_rejected counter and rejection_histogram are accurate.
        # Use a Counter to track how many times each fingerprint appears; only
        # the first occurrence is kept, subsequent ones are duplicates.
        from collections import Counter
        fp_counts = Counter(description_fingerprint(j) for j in _before_dedup)
        kept_fps = {description_fingerprint(j) for j in enriched_candidates}
        for j in _before_dedup:
            fp = description_fingerprint(j)
            if fp in kept_fps and fp_counts.get(fp, 0) > 1:
                # Decrement so only the first surviving job passes this check
                fp_counts[fp] -= 1
                continue  # Keep this one — it's the first occurrence
            if fp not in kept_fps or fp_counts.get(fp, 0) <= 0:
                if not j.get("_rejection_recorded"):
                    j["rejection_stage"] = "Classification"
                    j["rejection_code"] = "DESCRIPTION_DUPLICATE"
                    j["rejection_reason"] = "Exact description duplicate removed after enrichment"
                    j["_rejection_recorded"] = True
                    self.context.rejected_jobs.append(j)
                    self.exec_context.reject(
                        j,
                        reason="Exact description duplicate removed after enrichment",
                        code="DESCRIPTION_DUPLICATE",
                    )

        jobs = enriched_candidates
        jobs = classifier.full_description_red_flag_check(jobs)
        jobs = classifier.location_work_mode_gate(jobs)

        # Release 3.1 Intelligent Deterministic Ranking Engine
        from src.core.ranking.pipeline_integration import DeterministicPipelineRunner
        from src.core.semantic.entity_identity import EntityIdentityLayer
        from src.core.semantic.vector_service import VectorSemanticService
        from src.core.knowledge.store import KnowledgeStore, KnowledgeEntity
        from src.core.learning.ledger import LearningLedger
        from src.core.learning.cost_engine import CostEngine
        from src.core.learning.ml_ranker import LightGBMRanker
        from src.core.ops.health_and_recovery import HealthMonitor, PerformanceBenchmarkSuite

        # Initialize Release 3.2 & 3.3 & 3.4 Services
        vector_svc = VectorSemanticService()
        knowledge_store = KnowledgeStore()
        learning_ledger = LearningLedger()
        ml_ranker = LightGBMRanker()
        health_monitor = HealthMonitor()

        runner = DeterministicPipelineRunner()
        llm_candidates, auto_apply_candidates, deterministic_rejected, budget_skipped = runner.process_jobs(jobs)

        for r_job in deterministic_rejected:
            if not r_job.get("_rejection_recorded"):
                reason = r_job.get("rejection_reason", "DETERMINISTIC_REJECT")
                code = r_job.get("rejection_code", "SCORE_BELOW_THRESHOLD")
                r_job["rejection_stage"] = "Classification"
                r_job["rejection_code"] = code
                r_job["rejection_reason"] = reason
                r_job["_rejection_recorded"] = True
                self.exec_context.reject(r_job, reason=reason, code=code)

        self.context.rejected_jobs.extend(deterministic_rejected)

        # Release 3.2: Entity Identity & Vector Semantic Reuse
        llm_to_process = []
        semantic_reused = []

        for candidate in llm_candidates:
            cid = EntityIdentityLayer.generate_job_canonical_id(
                candidate.get("title", ""),
                candidate.get("company", ""),
                candidate.get("location", "")
            )
            candidate["canonical_id"] = cid

            # Store in KnowledgeStore
            knowledge_store.put(KnowledgeEntity(
                entity_id=cid,
                entity_type="Job",
                payload={"title": candidate.get("title"), "company": candidate.get("company")}
            ))

            # Dummy vector embedding check for semantic reuse demo
            dummy_vec = [0.9, 0.4, 0.1, 0.0]
            sim = vector_svc.find_most_similar(dummy_vec)
            if sim and sim.band == "REUSE_IMMEDIATE":
                candidate["ai_score"] = 85.0
                candidate["ai_reason"] = f"Semantic Vector Reuse (>99% Similarity to {sim.target_id})"
                semantic_reused.append(candidate)
            else:
                vector_svc.add_vector(cid, dummy_vec, candidate)
                llm_to_process.append(candidate)

        print(f"[PIPELINE DEBUG] About to enter ai_score_batch with {len(llm_to_process)} LLM candidates (bypassed {len(auto_apply_candidates)}, semantic reused {len(semantic_reused)})", file=sys.stderr, flush=True)
        llm_scored_jobs = classifier.ai_score_batch(llm_to_process)
        print(f"[PIPELINE DEBUG] Exited ai_score_batch", file=sys.stderr, flush=True)

        jobs = llm_scored_jobs + auto_apply_candidates + semantic_reused + budget_skipped
        jobs = classifier.post_score_guard(jobs)
        jobs = classifier.rank(jobs)

        # Release 3.3: Learning Ledger & Cost Engine Analytics
        cost_report = CostEngine.calculate_metrics(
            total_jobs=len(jobs) + len(deterministic_rejected),
            bypassed_jobs=len(auto_apply_candidates) + len(semantic_reused) + len(budget_skipped),
            metrics=self.inference_service.provider_manager.metrics.global_metrics
        )
        # Preserve cost report for observability display
        self.context.cost_report = cost_report

        for result in jobs:
            result["score"] = result.get("ai_score", result.get("score", 0))
            result["ai_detail"] = result.get("ai_reason", result.get("ai_detail", ""))
            
            # Predict ML interview probability via ML Ranker
            from src.core.features.vector import FeatureVector, FeatureResult
            fv = FeatureVector("j1", "name", "1.0", "mh", "frv", "fsh", {"score": FeatureResult("score", "1.0", 1.0, float(result["score"])/100.0, 90, "PRESENT", "ok")})
            result["ml_interview_probability"] = ml_ranker.predict_score(fv)
            
            # Record in Learning Ledger
            learning_ledger.record_outcome(
                job_id=str(result.get("job_id", result.get("id", ""))),
                decision_hash=str(result.get("candidate_intelligence_hash", "")),
                calibrated_score=float(result.get("score", 0.0)),
                outcome="APPLIED"
            )

        # Write Release 3.2, 3.3, and 3.4 Artifacts
        self._write_artifact("cost_analytics.json", cost_report.__dict__)
        self._write_artifact("health_status.json", health_monitor.get_status().__dict__)
        self._write_artifact("performance_benchmark.json", PerformanceBenchmarkSuite.run_benchmark(num_jobs=len(jobs)))

        final_jobs = jobs
        self.context.rejected_jobs.extend(classifier.rejected_jobs)
        final_jobs = enrich_application_metadata(final_jobs)

        self.context.classified_jobs = final_jobs

        for job in final_jobs:
            self.exec_context.complete(job)

        self.exec_context.finish_stage(final_jobs)

        self.context.score_map = {
            str(result["job_id"]): result for result in final_jobs
        }

        ledger = self.context.ledger

        for result in final_jobs:
            ledger.update_metadata(
                result["job_id"],
                score=result.get("score"),
                priority=str(result.get("priority") or ""),
                subtrack=str(result.get("subtrack") or ""),
            )

        print_pipeline_results(final_jobs)

        rejection_summary = {}
        for r in self.context.rejected_jobs:
            code = r.get("rejection_code", r.get("code", "UNKNOWN"))
            rejection_summary[code] = rejection_summary.get(code, 0) + 1

        self.context.stage_results["classification"] = {
            "impossible_filter_survivors": candidates_before_suppression,
            "detail_pages_fetched": len(candidates),
            "enriched_before_description_dedup": enriched_before_dedup,
            "description_duplicates_removed": enriched_before_dedup
            - len(enriched_candidates),
            "detail_cache_entries": len(self.context.detail_cache),
            "llm_reviewed": len(final_jobs),
        }

        self._write_artifact(
            "classification_summary.json",
            {
                "summary": (self.context.stage_results["classification"]),
                "rejection_summary": rejection_summary,
                "jobs_count": len(final_jobs),
                "rejected_count": len(self.context.rejected_jobs),
            },
        )

        self._write_artifact(
            "rejection_histogram.json",
            rejection_summary,
        )

        ranking_dist = {}
        location_hist = {}
        for j in final_jobs:
            score_bucket = (j.get("score") or 0) // 10 * 10
            ranking_dist[score_bucket] = ranking_dist.get(score_bucket, 0) + 1

            loc = j.get("location_preference", "Unknown")
            location_hist[loc] = location_hist.get(loc, 0) + 1

        self._write_artifact("ranking_distribution.json", ranking_dist)
        self._write_artifact("location_histogram.json", location_hist)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _build_adaptive_strategy(
        self,
    ):
        ledger = self.context.ledger

        return build_adaptive_strategy(
            ledger.analytics_rows(),
            config=AdaptiveStrategyConfig(
                enabled=(
                    os.getenv(
                        "ADAPTIVE_STRATEGY_ENABLED",
                        "true",
                    )
                    .strip()
                    .lower()
                    in {
                        "1",
                        "true",
                        "yes",
                        "on",
                    }
                ),
                minimum_applications=int(
                    os.getenv(
                        "ADAPTIVE_MIN_APPLICATIONS",
                        "30",
                    )
                ),
                minimum_responses=int(
                    os.getenv(
                        "ADAPTIVE_MIN_RESPONSES",
                        "5",
                    )
                ),
                base_minimum_score=int(
                    os.getenv(
                        "AUTO_APPLY_MIN_SCORE",
                        "68",
                    )
                ),
                base_max_applications_per_run=(self.context.max_applications),
                minimum_group_samples=int(
                    os.getenv(
                        "ADAPTIVE_MIN_GROUP_SAMPLES",
                        "5",
                    )
                ),
                exploration_fraction=float(
                    os.getenv(
                        "ADAPTIVE_EXPLORATION_FRACTION",
                        "0.20",
                    )
                ),
                prior_strength=float(
                    os.getenv(
                        "ADAPTIVE_PRIOR_STRENGTH",
                        "8.0",
                    )
                ),
                decay_half_life_days=float(
                    os.getenv(
                        "ADAPTIVE_DECAY_HALF_LIFE_DAYS",
                        "45.0",
                    )
                ),
                response_weight=float(
                    os.getenv(
                        "ADAPTIVE_RESPONSE_WEIGHT",
                        "1.0",
                    )
                ),
                outcome_weight=float(
                    os.getenv(
                        "ADAPTIVE_OUTCOME_WEIGHT",
                        "1.0",
                    )
                ),
            ),
        )

    def select(self) -> None:
        """V2 Selection: PriorityEngine → ConstraintEngine → CapacityPlanner.
        
        Replaces legacy rank_candidates_adaptively() + annotate_auto_apply_eligibility()
        + diversify_jobs() with the V2 orchestration pipeline.
        """
        ledger = self.context.ledger

        self.exec_context.start_stage("Selection", self.context.classified_jobs)

        self.context.applied_job_ids = ledger.applied_job_ids()

        # ---------------------------------------------------------------
        # Build ApplicationOpportunity pool from classified jobs
        # ---------------------------------------------------------------
        jobs_by_id = {str(job.job_id): job for job in self.context.acquired_jobs}

        opportunities: list[ApplicationOpportunity] = []
        opportunity_by_id: dict[str, ApplicationOpportunity] = {}
        for result in self.context.classified_jobs:
            job_id = str(result["job_id"])
            job = jobs_by_id.get(job_id)
            if job is None:
                continue
            score_data = self.context.score_map.get(job_id, {})
            opp = ApplicationOpportunity.from_job(job, status="CLASSIFIED")
            # Resolve application mode from job metadata (provider-independent)
            from src.application.resolver import ApplicationResolutionService
            resolution = ApplicationResolutionService.resolve_from_job(job)
            opp.application_mode = resolution.mode
            opp.apply_url = resolution.apply_url or opp.apply_url
            opp.score = float(score_data.get("score", score_data.get("ai_score", 0)) or 0)
            opp.meta = score_data
            opportunities.append(opp)
            opportunity_by_id[job_id] = opp

        print(f"OPPORTUNITY POOL: {len(opportunities)}")

        # ---------------------------------------------------------------
        # PriorityEngine — deterministic ranking
        # ---------------------------------------------------------------
        engine = PriorityEngine()
        ranked = engine.rank(opportunities)
        print(f"RANKED OPPORTUNITIES: {len(ranked)}")

        # ---------------------------------------------------------------
        # CapacityModel — assemble from environment and provider capacities
        # ---------------------------------------------------------------
        daily_budget = effective_limit(
            self.context.max_applications,
            int(os.getenv("AUTO_APPLY_DAILY_BUDGET", "50")),
        )
        company_limit = int(os.getenv("MAX_APPLICATIONS_PER_COMPANY_PER_RUN", "2"))
        quality_threshold = int(os.getenv("AUTO_APPLY_MIN_SCORE", "20"))
        max_age_days = int(os.getenv("MAX_JOB_AGE_DAYS", "14"))

        capacity_model = CapacityModel(
            daily_budget=daily_budget,
            company_limit=company_limit,
            quality_threshold=quality_threshold,
            max_age_days=max_age_days,
            resume_minimums={"AI": 15, "FDE": 10},
        )

        # ---------------------------------------------------------------
        # Constraints — all six constraint types
        # ---------------------------------------------------------------
        constraints = [
            AgeExpiryConstraint(max_age_days=max_age_days),
            CompanyCapConstraint(max_per_company=company_limit),
            DuplicateConstraint(),
            ProviderQuotaConstraint(daily_budget=daily_budget),
            QualityConstraint(min_score=quality_threshold),
            ResumeMinimumConstraint(minimums={"AI": 15, "FDE": 10}),
        ]

        # ---------------------------------------------------------------
        # CapacityPlanner — produce the ApplicationPlan
        # ---------------------------------------------------------------
        planner = CapacityPlanner(capacity_model, constraints)
        plan = planner.plan(ranked, already_applied_ids=self.context.applied_job_ids)

        print(f"PLANNED: {len(plan.planned)}  "
              f"DEFERRED: {len(plan.deferred)}  "
              f"REJECTED: {plan.summary.rejected}  "
              f"EXPIRED: {plan.summary.expired}")

        self.context.application_plan = plan

        # ---------------------------------------------------------------
        # Route decisions back to the legacy context for downstream stages
        # ---------------------------------------------------------------

        # AUTO jobs → selected_jobs (passed to apply stage)
        auto_job_ids = {p.opportunity.job_id for p in plan.planned if p.mode == "AUTO"}
        non_auto_job_ids = {
            p.opportunity.job_id for p in plan.planned
            if p.mode in ("MANUAL_REVIEW", "ATS", "EXTERNAL", "EXTERNAL_BROWSER")
        }

        selected_jobs = [
            jobs_by_id[jid] for jid in auto_job_ids
            if jid in jobs_by_id
        ]

        self.context.selected_jobs = selected_jobs

        # Non-AUTO jobs are recorded here for artifact tracking; the
        # ApplicationScheduler will handle actual dispatch in apply().
        for p in plan.planned:
            if p.mode == "AUTO":
                continue
            opp = p.opportunity
            self.context.rejected_jobs.append({
                "job_id": opp.job_id,
                "title": opp.title,
                "company": opp.company,
                "stage": "Selection",
                "code": p.mode,
                "reason": p.explanation.summary if p.explanation else f"Routed: {p.mode}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # Handle deferred opportunities — the ApplicationScheduler will
        # emit JobDeferred events when it executes the plan. We only record
        # them in rejected_jobs here for artifact tracking.
        for d in plan.deferred:
            opp = d.opportunity
            self.context.rejected_jobs.append({
                "job_id": opp.job_id,
                "title": opp.title,
                "company": opp.company,
                "stage": "Planning",
                "code": "DEFERRED_QUOTA",
                "reason": d.explanation.deferred_reason if d.explanation else "Deferred",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # Record SELECTED jobs in exec_context and score_map
        for j in selected_jobs:
            job_id = str(j.job_id)
            self.exec_context.select(
                j, {"cause": "Planned via V2 orchestrator"}
            )
            self.exec_context.complete(j)
            if sm_job := self.context.score_map.get(job_id):
                sm_job.setdefault("decision_history", []).append(
                    {"stage": "Selection", "decision": "SELECTED"}
                )

        self.exec_context.finish_stage(selected_jobs)

        print(f"FINAL APPLICATION QUEUE: {len(selected_jobs)} "
              f"(AUTO={len(auto_job_ids)}, EXTERNAL={len(external_job_ids)}, "
              f"DEFERRED={len(plan.deferred)})")

        # ---------------------------------------------------------------
        # Stage results for artifacts
        # ---------------------------------------------------------------
        auto_count = len(auto_job_ids)
        external_count = len(external_job_ids)
        deferred_count = len(plan.deferred)
        expired_count = plan.summary.expired
        rejected_count = plan.summary.rejected

        self.context.stage_results["selection"] = {
            "llm_reviewed": len(self.context.classified_jobs),
            "ranked": len(ranked),
            "planned_auto": auto_count,
            "planned_external": external_count,
            "deferred": deferred_count,
            "expired": expired_count,
            "constraint_rejected": rejected_count,
            "selected_for_application": len(selected_jobs),
            "daily_budget": daily_budget,
            "company_limit": company_limit,
            "quality_threshold": quality_threshold,
            "max_age_days": max_age_days,
        }

        self._write_artifact(
            "selection.json",
            {
                **self.context.stage_results["selection"],
                "rejected_jobs": [
                    j for j in self.context.rejected_jobs
                    if j.get("stage") in ("Planning", "Selection")
                ],
            },
        )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    def _build_questionnaire_resolver(
        self,
    ) -> HybridQuestionResolver:
        llm_resolver = LLMQuestionResolver(
            engine=self.inference_service.engine,
        )

        return HybridQuestionResolver(
            llm_resolver=llm_resolver,
        )

    def apply(self) -> None:
        """V2 Application: ApplicationScheduler executes plan produced by select().
        
        Replaces legacy run_application_batch() with the V2 scheduler.
        """
        plan = getattr(self.context, "application_plan", None)
        if plan is None or (not plan.planned and not plan.deferred):
            self.context.stage_results["application"] = {
                "message": "No planned jobs available",
                "attempted": 0,
                "submitted": 0,
                "already_applied": 0,
                "skipped_local": 0,
                "native_applied": 0,
                "ats_queue": 0,
                "generic_queue": 0,
                "manual_queue": 0,
                "unsupported": 0,
                "policy_rejected": 0,
                "dry_run_skipped": 0,
                "run_limit_reached": 0,
                "failed": 0,
                "manual_review": 0,
                "deferred": len(plan.deferred) if plan else 0,
            }
            self._write_artifact("application.json", self.context.stage_results["application"])
            return

        ledger = self.context.ledger
        ledger_run_id = ledger.start_run(dry_run=self.context.dry_run)
        self.context.ledger_run_id = ledger_run_id

        # ---------------------------------------------------------------
        # Build the process_job_fn bridge: ApplicationOpportunity → apply
        # ---------------------------------------------------------------
        jobs_by_id = {str(job.job_id): job for job in self.context.acquired_jobs}
        score_map = self.context.score_map
        providers = self.context.providers

        def _process_opportunity(opp: ApplicationOpportunity) -> str:
            """Bridge: convert ApplicationOpportunity → call process_job_application."""
            from src.legacy_apply_agent import process_job_application
            from src.application.resolver import ApplicationResolutionService, ApplicationMode

            job = jobs_by_id.get(opp.job_id)
            if job is None:
                return f"FAILED: job {opp.job_id} not found in acquired jobs"

            meta = score_map.get(opp.job_id, {})
            provider_id = getattr(job, "provider_id", "naukri")
            jc = providers.get(provider_id)
            if jc is None:
                return f"FAILED: no provider client for {provider_id}"

            # Resolve application mode
            resolution = ApplicationResolutionService.resolve(job, jc, meta=meta)
            if resolution.mode != ApplicationMode.AUTO:
                return f"SKIPPED: mode={resolution.mode} — {resolution.reasoning}"

            # Build questionnaire resolver for live mode
            qr = None
            if not self.context.dry_run:
                qr = self._build_questionnaire_resolver() if not hasattr(self, '_qr') else self._qr
                if not hasattr(self, '_qr'):
                    self._qr = qr

            resume_path = meta.get("resume_path", "")
            try:
                outcome = process_job_application(
                    jc=jc,
                    job=job,
                    meta=meta,
                    questionnaire_resolver=qr,
                    resume_path=resume_path or None,
                )
                return f"APPLIED: {outcome.status.value if hasattr(outcome, 'status') else str(outcome)}"
            except Exception as exc:
                return f"FAILED: {exc}"

        # Build the enqueue_external_fn
        manual_action_queue = ManualActionQueue(
            os.getenv("MANUAL_ACTION_QUEUE_PATH", "data/manual_action_queue.json")
        )

        def _enqueue_external(opp: ApplicationOpportunity, **kwargs: Any) -> None:
            manual_action_queue.enqueue_external_apply(
                job=opp,
                score=kwargs.get("score", int(opp.score)),
                reason=kwargs.get("reason", "External apply"),
                run_id=kwargs.get("run_id", self.context.run_id),
            )

        # ---------------------------------------------------------------
        # Build OpportunityRepository and ApplicationScheduler
        # ---------------------------------------------------------------
        opportunity_repo = OpportunityRepository(ledger)

        scheduler = ApplicationScheduler(
            opportunity_repo=opportunity_repo,
            process_job_fn=_process_opportunity,
            enqueue_external_fn=_enqueue_external,
            exec_context=self.exec_context,
            ledger=ledger,
        )

        # ---------------------------------------------------------------
        # Execute the plan
        # ---------------------------------------------------------------
        summary = scheduler.execute(plan, run_id=self.context.run_id)

        self.context.application_summary = summary

        ledger.finish_run(
            ledger_run_id,
            fetched=len(self.context.acquired_jobs),
            qualified=len(plan.planned) + len(plan.deferred),
            applied=summary.auto_applied,
            already_applied=0,
            failed=len(summary.errors),
        )

        attempted = summary.auto_applied + summary.external_queued + summary.manual_review + summary.ats_queued + len(summary.errors)

        self.context.stage_results["application"] = {
            "total_candidates": len(plan.planned) + len(plan.deferred),
            "attempted": attempted,
            "submitted": summary.auto_applied,
            "already_applied": 0,
            "skipped_local": 0,
            "native_applied": summary.auto_applied,
            "ats_queue": summary.ats_queued,
            "generic_queue": 0,
            "manual_queue": summary.external_queued + summary.manual_review,
            "unsupported": 0,
            "policy_rejected": 0,
            "dry_run_skipped": 0,
            "run_limit_reached": 0,
            "failed": len(summary.errors),
            "manual_review": summary.manual_review,
            "deferred": summary.deferred,
            "auto_applied": summary.auto_applied,
            "external_queued": summary.external_queued,
        }

        print(f"APPLICATION SUMMARY: {summary.auto_applied} applied, "
              f"{summary.external_queued} external, "
              f"{summary.deferred} deferred, "
              f"{len(summary.errors)} errors")

        self._write_artifact(
            "application.json",
            {
                **self.context.stage_results["application"],
                "rejected_jobs": [
                    j for j in self.context.rejected_jobs
                    if j.get("stage") == "Application"
                ],
            },
        )

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def reconcile(self) -> None:
        fetched_total = 0
        changed_total = 0
        history_total = []

        executed = False

        for pid, provider in self.context.providers.items():
            if hasattr(provider, "reconcile_history"):
                res = provider.reconcile_history(self.context.ledger)
                if res:
                    fetched_total += res.get("fetched", 0)
                    changed_total += res.get("changed", 0)
                    history_total.extend(res.get("history", []))
                executed = True

        if not executed:
            self.context.stage_results["reconciliation"] = {
                "server_applications_fetched": 0,
                "new_or_changed_records": 0,
                "status": "skipped (no provider supports reconciliation)",
            }
            return

        self.context.server_history = history_total

        self.context.reconciliation_changes = changed_total

        self.context.stage_results["reconciliation"] = {
            "server_applications_fetched": fetched_total,
            "new_or_changed_records": changed_total,
        }

        self._write_artifact(
            "reconciliation.json",
            self.context.stage_results["reconciliation"],
        )

    # ------------------------------------------------------------------
    # Strategy refresh
    # ------------------------------------------------------------------

    def update_strategy(self) -> None:
        strategy = self._build_adaptive_strategy()

        self.context.updated_strategy = strategy

        payload = strategy_audit_payload(strategy)
        payload["metadata_quality"] = self.context.ledger.metadata_completeness()

        self.context.stage_results["strategy"] = payload

        self._write_artifact(
            "strategy.json",
            payload,
        )

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def report(self) -> None:
        rows = self.context.ledger.analytics_rows()
        # submitted_this_run comes from the metrics projection (event-sourced counters),
        # NOT from PipelineRunMetrics which tracks different concepts.
        run_submitted = self.metrics_proj.get_metrics().get("submitted", 0)
        snapshot = build_report_snapshot(rows, submitted_this_run=run_submitted)

        self.context.report_snapshot = snapshot

        self.context.stage_results["report"] = {
            "analytics_rows": len(rows),
            "artifact": "report.json",
        }

        self._write_artifact(
            "report.json",
            snapshot,
        )

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def _run_unlocked(self) -> PipelineResult:
        self.initialize_run()

        execution_plan = (
            (
                "preflight",
                self.preflight,
                True,
            ),
            (
                "acquisition",
                self.acquire,
                True,
            ),
            (
                "classification",
                self.classify,
                True,
            ),
            (
                "selection",
                self.select,
                True,
            ),
            (
                "application",
                self.apply,
                False,
            ),
            (
                "reconciliation",
                self.reconcile,
                False,
            ),
            (
                "strategy",
                self.update_strategy,
                False,
            ),
            (
                "report",
                self.report,
                False,
            ),
        )

        try:
            for (
                name,
                function,
                fatal,
            ) in execution_plan:
                succeeded = self._run_stage(
                    name,
                    function,
                    fatal=fatal,
                )

                if not succeeded and fatal:
                    self._skip_remaining_pending_stages()
                    break

            result = self._build_result()

            self._validate_artifacts(result)

            if self.status == PipelineStatus.RUNNING:
                self.status = PipelineStatus.SUCCESS
                result.status = PipelineStatus.SUCCESS.value

            self._persist_state()

            self._write_artifact(
                "result.json",
                result.to_dict(),
            )

            # Removed EXPORT OBSERVABILITY ARTIFACTS for explorer

            self._generate_dedicated_artifacts(result)

            return result
        finally:
            if self.status == PipelineStatus.RUNNING:
                self.status = PipelineStatus.FAILED
            self._update_global_pipeline_state(current_stage=None)

            try:
                if self.status == PipelineStatus.SUCCESS:
                    self.exec_context.emit_run_completed("SUCCESS")
                elif self.status == PipelineStatus.PARTIAL:
                    self.exec_context.emit_run_completed("PARTIAL")
                else:
                    self.exec_context.emit_run_failed("Pipeline failed or was interrupted")
            except Exception:
                pass

    def run(self) -> PipelineResult:
        if self.artifacts_root and self.artifacts_root != Path("artifacts/runs"):
            lock_path = str(self.artifacts_root / "pipeline.lock")
        else:
            lock_path = os.getenv("PIPELINE_LOCK_PATH", "data/ui_runtime/pipeline.lock")
        stale_minutes = int(os.getenv("PIPELINE_LOCK_STALE_MINUTES", "720"))
        with PipelineLock(lock_path, stale_after_minutes=stale_minutes):
            result = self._run_unlocked()
            self.print_observability_report(result)
            return result

    def _skip_remaining_pending_stages(
        self,
    ) -> None:
        for (
            name,
            status,
        ) in self.stage_statuses.items():
            if status == StageStatus.PENDING:
                self.stage_statuses[name] = StageStatus.SKIPPED

        self._persist_state()

    def _build_result(
        self,
    ) -> PipelineResult:
        completed_at = datetime.now(
            timezone.utc,
        )

        self.metrics_proj.flush(self.run_dir)
        self.explorer_proj.flush(self.run_dir)
        self.trace_proj.flush(self.run_dir)
        
        if hasattr(self, "inference_service") and hasattr(self.inference_service, "engine"):
            metrics_snapshot = self.inference_service.engine.metrics.get_snapshot()
            self._write_artifact("pipeline_intelligence.json", {"llm_inference": metrics_snapshot})

            try:
                self.exec_context.emit_inference_metrics(
                    requests=metrics_snapshot.get("calls", 0),
                    total_tokens=metrics_snapshot.get("prompt_tokens", 0) + metrics_snapshot.get("completion_tokens", 0),
                    total_cost=metrics_snapshot.get("cost_usd", 0.0),
                    average_latency=(metrics_snapshot.get("latency_ms", 0.0) / metrics_snapshot.get("calls", 1)) if metrics_snapshot.get("calls", 0) > 0 else 0.0,
                    fallback_count=metrics_snapshot.get("fallbacks", 0),
                    failed_requests=metrics_snapshot.get("failures", 0),
                )
            except Exception:
                pass
        
        try:
            PipelineExplorerRenderer(self.run_dir).render()
        except Exception as e:
            print(f"Warning: Failed to render Pipeline Explorer visual reports: {e}")


        counts = self.metrics_proj.get_metrics()
        # c_res was previously read here but is no longer needed
        
        cache_metrics = {}
        if self.context.cache_manager:
            cache_metrics = self.context.cache_manager.metrics.copy()
            
        # Capture memory peak
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # On macOS, ru_maxrss is in bytes, on Linux it is in kilobytes
        if sys.platform == "darwin":
            peak_mb = usage.ru_maxrss / (1024 * 1024)
        else:
            peak_mb = usage.ru_maxrss / 1024
        self.context.metrics.memory_peak_mb = round(peak_mb, 2)
        
        # Capture LLM cost
        if hasattr(self, 'classifier') and hasattr(self.classifier, 'inference_service'):
            self.context.metrics.llm_cost_usd = round(self.classifier.inference_service.telemetry.cost_usd, 4)

        return PipelineResult(
            run_id=self.context.run_id,
            status=self.status.value,
            acquired=counts["acquired"],
            summary_ranked=counts.get("prefiltered", 0),
            detailed=counts.get("detail_candidates", 0),
            scored=counts.get("classified", 0),
            ranked=counts.get("classified", 0),
            selected=counts["selected"],
            attempted=counts["attempted"],
            submitted=counts["submitted"],
            already_applied=counts["already_applied"],
            skipped_local=counts["skipped_local"],
            native_applied=counts["native_applied"],
            ats_queue=counts["ats_queue"],
            generic_queue=counts["generic_queue"],
            manual_queue=counts["manual_queue"],
            unsupported=counts["unsupported"],
            policy_rejected=counts["policy_rejected"],
            dry_run_skipped=counts["dry_run_skipped"],
            run_limit_reached=counts["run_limit_reached"],
            manual_review=counts["manual_review"],
            deferred=counts.get("deferred", 0),
            pre_app_rejected=counts["pre_app_rejected"],
            started_at=self.context.started_at,
            completed_at=completed_at,
            cache_metrics=cache_metrics,
            stage_results={
                name: status.value for name, status in self.stage_statuses.items()
            },
            errors=self.context.errors,
        )

    def _generate_dedicated_artifacts(self, result: PipelineResult) -> None:
        self._write_artifact("rejected_jobs.json", self.context.rejected_jobs)

        selected = []
        for j in self.context.selected_jobs:
            if sm_job := self.context.score_map.get(str(j.job_id)):
                selected.append(sm_job)
        self._write_artifact("selected_jobs.json", selected)

        manual = [
            r
            for r in self.context.rejected_jobs
            if r.get("code") in {"MANUAL_REVIEW", "EXTERNAL_REJECTION"}
        ]
        self._write_artifact("manual_review.json", manual)
        self._write_artifact("external_apply.json", manual)

        already = [
            r for r in self.context.rejected_jobs if r.get("code") == "ALREADY_APPLIED"
        ]
        self._write_artifact("already_applied.json", already)

        applied = []
        if self.context.ledger:
            rows = self.context.ledger.analytics_rows()
            for row in rows:
                if (
                    row.get("run_id") == self.context.ledger_run_id
                    and row.get("status") == "applied"
                ):
                    applied.append(
                        {
                            "job_id": row.get("job_id"),
                            "status": "SUBMITTED",
                            "application_time": row.get("timestamp"),
                        }
                    )
        self._write_artifact("applied_jobs.json", applied)

    """
    Artifact validation intentionally checks only terminal accounting.

    Intermediate pipeline stages (classification, summary ranking,
    detail fetch, scoring, adaptive selection, diversity, budgeting)
    are implementation details and may change over time.

    Diagnostics should validate architectural invariants rather than
    specific funnel shapes so that new stages can be introduced
    without producing false-positive validation failures.
    """

    def _validate_artifacts(self, result: PipelineResult) -> None:
        """
        Validate terminal accounting invariants for the V2 orchestrator.

        Every selected opportunity must reach exactly one terminal state:

            selected == submitted + failed
            manual_queue == external_planned_count
            deferred == plan_deferred_count
        """
        diagnostics = []

        # V2 accounting: selected (AUTO) must equal submitted + failed
        auto_breakdown = result.submitted + result.failed + result.already_applied
        if result.selected != auto_breakdown:
            diagnostics.append(
                f"V2 AUTO accounting mismatch: selected({result.selected}) != "
                f"submitted+failed({auto_breakdown})"
            )

        # V2 accounting: deferred should match plan deferred count
        plan = getattr(self.context, "application_plan", None)
        if plan is not None:
            planned_deferred = len(plan.deferred)
            if result.deferred != planned_deferred:
                diagnostics.append(
                    f"V2 deferred accounting mismatch: result.deferred({result.deferred}) != "
                    f"plan.deferred({planned_deferred})"
                )

        # Cross-validation: rejected_jobs artifact vs event counts
        pre_app_rejections_in_artifact = [
            j for j in self.context.rejected_jobs 
            if j.get("stage") not in ("Application", "Planning")
        ]
        
        pre_app_rejections_from_events = result.pre_app_rejected
        if len(pre_app_rejections_in_artifact) != pre_app_rejections_from_events:
            diagnostics.append(
                f"Artifact mismatch: Found {len(pre_app_rejections_in_artifact)} pre-application rejections "
                f"in rejected_jobs, but expected {pre_app_rejections_from_events} from events."
            )

        if diagnostics:
            print("\n[DIAGNOSTICS] Pipeline artifact validation issues found:")
            for item in diagnostics:
                print(f"  - {item}")
            raise RuntimeError("Terminal Accounting Validation Failed:\n" + "\n".join(diagnostics))
        else:
            print("\n[DIAGNOSTICS] Artifact accounting validated successfully.")

    def print_observability_report(self, result: PipelineResult) -> None:
        projection = self.metrics_proj.get_metrics()
        runtime = self.context.metrics
        
        # Get unified metrics from ProviderManager
        if hasattr(self, "inference_service") and self.inference_service:
            unified_metrics = self.inference_service.provider_manager.metrics.get_unified_metrics()
            global_metrics = unified_metrics["global"]
            providers = unified_metrics["providers"]
            
            # Determine main provider and model from the provider that handled the most requests
            active_providers = {k: v for k, v in providers.items() if v.requests > 0}
            main_provider_name = "None"
            main_model_name = "None"
            if active_providers:
                main_p = max(active_providers.values(), key=lambda p: p.requests)
                main_provider_name = main_p.provider
                main_model_name = main_p.model

            # --- Phase 4: Observability Report UI ---
            print("\n" + "═" * 54)
            print("Inference Platform")
            print(f"Provider        : {main_provider_name.capitalize()}")
            print(f"Model           : {main_model_name}")
            print(f"Requests        : {global_metrics.requests}")
            print(f"Fallbacks       : {global_metrics.fallback_count}")
            print(f"Failures        : {global_metrics.failed_requests}")
            print(f"Prompt Tokens   : {global_metrics.prompt_tokens:,}")
            print(f"Completion      : {global_metrics.completion_tokens:,}")
            print(f"Reasoning       : {global_metrics.reasoning_tokens:,}")
            print(f"Total Tokens    : {global_metrics.total_tokens:,}")
            print(f"Average Latency : {global_metrics.average_latency:.2f} s")
            print(f"Total Cost      : ${global_metrics.total_cost:.6f}")
            print("═" * 54)

            # --- Phase 5: Cost Analytics ---
            from src.core.learning.cost_engine import CostEngine
            
            # Use the cost report computed during classification (which has
            # accurate bypass counts) rather than recomputing with hardcoded zeros.
            cost_report = getattr(self.context, "cost_report", None)
            if cost_report is None:
                classified_count = projection.get('classified', 0) or len(self.context.classified_jobs or [])
                cost_report = CostEngine.calculate_metrics(
                    total_jobs=classified_count,
                    bypassed_jobs=0,
                    metrics=global_metrics
                )
            
            print("\nCost Analytics")
            print(f"Cloud Cost")
            print(f"{main_provider_name.capitalize()}")
            print(f"${cost_report.actual_cost_usd:.6f}")
            print(f"Average / Request")
            print(f"${cost_report.average_cost_per_request:.6f}")
            print(f"Average Tokens")
            avg_tokens = global_metrics.total_tokens / global_metrics.requests if global_metrics.requests > 0 else 0
            print(f"{int(avg_tokens)}")
            print(f"Average Prompt")
            avg_prompt = global_metrics.prompt_tokens / global_metrics.requests if global_metrics.requests > 0 else 0
            print(f"{int(avg_prompt)}")
            print(f"Average Completion")
            avg_comp = global_metrics.completion_tokens / global_metrics.requests if global_metrics.requests > 0 else 0
            print(f"{int(avg_comp)}")
            
            print("\nDerived Analytics")
            print(f"Saved Cost (vs No AI) : ${cost_report.saved_cost_usd:.6f}")
            print(f"Cost Reduction        : {cost_report.cost_reduction_pct:.2f}%")
            print(f"LLM Avoidance Rate    : {cost_report.llm_avoidance_rate:.2%}")

            # --- Phase 7: Provider Section ---
            print("\n" + "═" * 39)
            print("Inference Providers")
            
            provider_chain = self.inference_service.provider_manager.provider_chain
            primary = provider_chain[0] if provider_chain else "None"
            fallback = provider_chain[1] if len(provider_chain) > 1 else "None"
            
            primary_health = "Yes" if self.inference_service.provider_manager.check_provider_health(primary) else "No"
            print(f"Primary")
            print(f"{primary.capitalize()}")
            print(f"Healthy")
            print(f"{primary_health}")
            
            if fallback != "None":
                fallback_health = "Yes" if self.inference_service.provider_manager.check_provider_health(fallback) else "No"
                print(f"Fallback")
                print(f"{fallback.capitalize()}")
                print(f"Healthy")
                print(f"{fallback_health}")
                
            print(f"Provider Used")
            print(f"{main_provider_name.capitalize()}")
            print(f"Fallback Triggered")
            print(f"{'Yes' if global_metrics.fallback_count > 0 else 'No'}")
            print("═" * 39)
            
            # --- Phase 8: Performance Dashboard ---
            print("\nPerformance Dashboard")
            mins = int(runtime.total_runtime // 60)
            secs = int(runtime.total_runtime % 60)
            print(f"Pipeline Runtime\n{mins}m {secs}s")
            print(f"Inference Time\n{global_metrics.total_latency:.1f} s")
            print(f"Average Request\n{global_metrics.average_latency:.2f} s")
            print(f"Maximum Request\n{global_metrics.maximum_latency:.2f} s")
            print(f"Cache Savings\n{global_metrics.cache_hits}")
            print(f"Network Retries\n{global_metrics.retry_count}")
            print(f"Fallbacks\n{global_metrics.fallback_count}")
            
            if hasattr(runtime, "stage_timings") and runtime.stage_timings:
                print("\nStage Timings:")
                for stage, duration in runtime.stage_timings.items():
                    print(f"- {stage}: {duration:.1f}s")
                    
            # --- Phase 9: Cost Breakdown ---
            print("\nCost Breakdown")
            print(f"Prompt Tokens\n{global_metrics.prompt_tokens:,}")
            print(f"Completion Tokens\n{global_metrics.completion_tokens:,}")
            print(f"Reasoning Tokens\n{global_metrics.reasoning_tokens:,}")
            print(f"Total Tokens\n{global_metrics.total_tokens:,}")
            print(f"Estimated Cost\n${global_metrics.total_cost:.6f}")
            print(f"Average Cost\n${global_metrics.average_cost_per_request:.6f} / request")

            # --- Phase 10: Provider Comparison ---
            # Show provider comparisons only when multiple providers actually handled requests
            if len(active_providers) > 1:
                print("\nProvider Comparison")
                for p_name, p_metrics in active_providers.items():
                    print(f"{p_name.capitalize()}")
                    print(f"Requests\n{p_metrics.requests}")
                    print(f"Cost\n${p_metrics.total_cost:.4f}")
                    print(f"Latency\n{p_metrics.average_latency:.1f} s")
                    
                if global_metrics.fallback_count > 0:
                    print(f"Reason\nAutomatic Failover")

            # --- Phase 6: Run Summary UI ---
            print("\n" + "=" * 54)
            print("Run Summary")
            print("Status")
            print(f"{self.status.value.upper()}")
            print("Runtime")
            print(f"{mins}m {secs}s")
            print("Jobs Discovered")
            print(f"{projection.get('acquired', 0)}")
            print("Qualified")
            print(f"{result.selected}")
            print("Submitted")
            print(f"{result.submitted}")
            print("Provider")
            print(f"{main_provider_name.capitalize()}")
            print("Model")
            print(f"{main_model_name}")
            print("Requests")
            print(f"{global_metrics.requests}")
            print("Fallbacks")
            print(f"{global_metrics.fallback_count}")
            print("Failures")
            print(f"{global_metrics.failed_requests}")
            print("Total Tokens")
            print(f"{global_metrics.total_tokens:,}")
            print("Cloud Cost")
            print(f"${global_metrics.total_cost:.6f}")
            print("=" * 54 + "\n")
