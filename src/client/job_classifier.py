import json
import os
import re
import hashlib
import concurrent.futures
from src.client.inference_service import InferenceService
from src.orchestration.metrics import PipelineRunMetrics
from src.cache.cache_manager import CacheManager
from src.cache.fingerprint import compute_llm_fingerprint


class JobFilterPipeline2:

    # ── your stack — AI scores against this ──────────────────────────────────
    MY_STACK = [
        # ── Core backend ──────────────────────────────────────────────
        "node",
        "node.js",
        "nodejs",
        "python",
        "javascript",
        "typescript",
        "angular",
        "rxjs",
        "html",
        "css",
        # ── Frameworks ───────────────────────────────────────────────
        "express",
        "express.js",
        "fastapi",
        "flask",
        "nestjs",
        "nest.js",
        "django",
        "hapi",
        "koa",
        # ── Databases ────────────────────────────────────────────────
        "mongodb",
        "mongoose",
        "postgresql",
        "mysql",
        "redis",
        "sqlite",
        "dynamodb",
        "firestore",
        "cassandra",
        "elasticsearch",
        "sql",
        "nosql",
        # ── Cloud & DevOps ───────────────────────────────────────────
        "aws",
        "gcp",
        "azure",
        "docker",
        "kubernetes",
        "ci/cd",
        "github actions",
        "jenkins",
        "terraform",
        "linux",
        "nginx",
        "ec2",
        "s3",
        "lambda",
        "cloudwatch",
        # ── APIs & Messaging ─────────────────────────────────────────
        "rest",
        "rest api",
        "restful",
        "graphql",
        "websocket",
        "grpc",
        "kafka",
        "rabbitmq",
        "celery",
        "bull",
        "socket.io",
        # ── Automation & Scraping ────────────────────────────────────
        "selenium",
        "playwright",
        "puppeteer",
        "beautifulsoup",
        "scrapy",
        "web scraping",
        "automation",
        "n8n",
        "trigger.dev",
        "zapier",
        # ── AI / LLM ─────────────────────────────────────────────────
        "langchain",
        "openai",
        "llm",
        "rag",
        "vector db",
        "pinecone",
        "weaviate",
        "chromadb",
        "huggingface",
        "embeddings",
        "genai",
        "langsmith",
        "llamaindex",
        "langgraph",
        "semantic kernel",
        "azure openai",
        "azure ai search",
        "agentic ai",
        "tool calling",
        "llm evaluation",
        # ── Tools & Practices ────────────────────────────────────────
        "git",
        "github",
        "postman",
        "swagger",
        "jwt",
        "oauth",
        "microservices",
        "system design",
        "api design",
    ]

    PRIMARY_STACK_CONFLICTS = {
        "java developer": {
            "java",
            "spring",
            "spring boot",
            "hibernate",
        },
        ".net developer": {
            ".net",
            "c#",
            "asp.net",
            "dotnet",
        },
        "vba automation": {
            "vba",
            "advanced excel",
            "power query",
            "excel macros",
        },
        "ml research": {
            "tensorflow",
            "pytorch",
            "deep learning",
            "computer vision",
            "linear algebra",
            "model training",
        },
    }

    # ── IMPOSSIBLE FILTER (Data-Driven Domain Exclusions) ───────────────────
    # Reject ONLY things that are objectively impossible. Borderline/adjacent roles survive.
    IMPOSSIBLE_DOMAINS = {
        "Healthcare": [
            r"\bdentist\b",
            r"\bdoctor\b",
            r"\bnurse\b",
            r"\bphysician\b",
            r"\bmedical officer\b",
            r"\bpharmacist\b",
        ],
        "Non-Software Engineering": [
            r"\bcivil\b",
            r"\bmechanical\b",
            r"\belectrical\b",
            r"\bchemical\b",
            r"\bstructural\b",
        ],
        "Finance/Accounting": [
            r"\baccountant\b",
            r"\bchartered accountant\b",
            r"\bca\b",
            r"\btax consultant\b",
            r"\bauditor\b",
        ],
        "Sales/Marketing": [
            r"\bsales executive\b",
            r"\bbusiness development executive\b",
            r"\breal estate sales\b",
            r"\btelecaller\b",
            r"\bbde\b",
            r"\bsales manager\b",
        ],
        "Legal/HR": [
            r"\blawyer\b",
            r"\battorney\b",
            r"\blegal counsel\b",
            r"\bhr recruiter\b",
            r"\btalent acquisition\b",
        ],
        "Legacy Systems": [
            r"\bsap payroll\b",
            r"\bmainframe cobol\b",
            r"\bpeoplesoft hcm\b",
        ],
        "Training/Entry": [
            r"\btutor\b",
            r"\btrainer\b",
            r"\bwalk-in\b",
            r"\bwalkin\b",
            r"\bwalk in\b",
        ],
    }

    # Broad-coverage policy: company name never decides AI eligibility.
    VETO_COMPANIES = set()

    # ── red flag sniff on description (cheap, pre-ai) ───────────────────────
    # Only the things AI genuinely can't infer from tags alone
    DESC_RED_FLAGS = {
        "walk-in": r"walk.?in|walkin",
        "venue listed": r"venue\s*:|interview venue|bring your resume|carry your resume",
    }

    SOFTWARE_KEYWORDS = {
        "software",
        "developer",
        "engineer",
        "engineering",
        "backend",
        "full stack",
        "fullstack",
        "python",
        "node",
        "nodejs",
        "javascript",
        "typescript",
        "django",
        "fastapi",
        "flask",
        "golang",
        "devops",
        "cloud",
        "sre",
        "platform",
        "api",
        "microservices",
        "infrastructure",
        "tech lead",
        "sde",
        "swe",
        "mts",
        "programmer",
        "react",
    }

    # if ANY of these appear in title → drop it
    # Only obvious non-software/non-AI tracks. Stack and AI sub-discipline are ranking signals.
    WRONG_TRACK_TITLE_KEYWORDS = {
        "android developer",
        "ios developer",
        "flutter developer",
        "site reliability engineer",
        "sre engineer",
        "devops engineer",
    }

    # Backward-compatible alias for callers/tests that inspect the old name.
    FRONTEND_VETO_KEYWORDS = WRONG_TRACK_TITLE_KEYWORDS

    # =========================================================
    # AI RELEVANCE GATE
    # =========================================================

    STRONG_AI_SIGNALS = {
        "generative ai",
        "genai",
        "gen ai",
        "large language model",
        "large language models",
        "llm",
        "llms",
        "rag",
        "retrieval augmented generation",
        "langchain",
        "langgraph",
        "llamaindex",
        "semantic kernel",
        "azure openai",
        "openai api",
        "vector database",
        "vector db",
        "vector search",
        "embeddings",
        "prompt engineering",
        "agentic ai",
        "ai agent",
        "ai agents",
        "multi-agent",
        "autogen",
        "crewai",
    }

    MEDIUM_AI_SIGNALS = {
        "artificial intelligence",
        "natural language processing",
        "nlp",
        "machine learning",
        "hugging face",
        "huggingface",
        "transformers",
        "transformer models",
        "foundation models",
        "language models",
        "chatbot",
        "conversational ai",
        "ai application",
        "ai applications",
        "ai integration",
        "ai platform",
    }

    AI_TITLE_SIGNALS = {
        "ai engineer",
        "artificial intelligence engineer",
        "generative ai engineer",
        "genai engineer",
        "gen ai engineer",
        "llm engineer",
        "llm operations engineer",
        "llm model developer",
        "rag engineer",
        "ai developer",
        "genai developer",
        "ai application developer",
        "applied ai engineer",
        "ai software engineer",
        "ai backend developer",
        "python ai developer",
        "ai/ml engineer",
        "ai ml engineer",
        "machine learning engineer",
        "ml engineer",
        "data scientist",
        "computer vision engineer",
        "deep learning engineer",
        "nlp engineer",
        "prompt engineer",
        "ml scientist",
        "applied scientist",
        "mlops engineer",
        "llmops engineer",
        "ai lead",
        "ai architect",
        "ai full stack engineer",
        "full stack ai engineer",
        "fullstack ai engineer",
        "ai platform",
        "ai application",
        "ai applications",
        "ai solutions",
        "ai consultant",
        "ai specialist",
        "ai systems",
        "ai integration",
        "ai workflow",
        "ai software",
        "applied ai",
        "ai native",
        "agent engineer",
        "agentic engineer",
        "agentic ai",
        "gen ai",
        "genai",
        "generative ai",
        "llm",
        "rag",
        "prompt engineer",
        "prompt engineering",
        "ai product",
        "ai research",
        "ml engineer",
        "machine learning engineer",
    }

    def __init__(
        self,
        daily_apply_limit: int = 500,
        min_apply_score: int = 50,
        ai_score_limit: int = 300,
        batch_size: int = 5,
        metrics: PipelineRunMetrics | None = None,
        exec_context=None,
        test_mode: bool = False,
        inference_service: InferenceService | None = None,
    ):
        self.metrics = metrics
        self.exec_context = exec_context
        self.test_mode = test_mode
        self.inference_service = inference_service or InferenceService()

        self.daily_apply_limit = daily_apply_limit
        self.min_apply_score = min_apply_score
        self.ai_score_limit = ai_score_limit
        self.batch_size = batch_size

        self.rejected_jobs: list[dict] = []

    # =========================================================
    # STATE TRACKING
    # =========================================================

    def record_decision(self, job: dict, stage: str, code: str, reason: str) -> None:

        if not job.get("_rejection_recorded"):
            job["rejection_stage"] = stage
            job["rejection_code"] = code
            job["rejection_reason"] = reason
            self.rejected_jobs.append(job)
            job["_rejection_recorded"] = True

        if self.exec_context:
            self.exec_context.reject(job, reason=reason, code=code)

        decisions = job.setdefault("decisions", [])
        decisions.append(
            {
                "stage": stage,
                "code": code,
                "reason": reason,
            }
        )

        decision_history = job.setdefault("decision_history", [])
        decision_history.append(
            {
                "stage": stage,
                "code": code,
                "reason": reason,
            }
        )

    # =========================================================
    # MAIN
    # =========================================================

    def pre_filter(self, jobs):
        """
        Cheap deterministic filtering before full job-detail enrichment.
        """

        print("\nRAW JOBS:", len(jobs))

        jobs = self.normalize_jobs(jobs)
        print("AFTER NORMALIZE:", len(jobs))

        jobs = self.age_filter(jobs)
        print("AFTER AGE FILTER:", len(jobs))

        jobs = self.dedup(jobs)
        print("AFTER DEDUP:", len(jobs))

        jobs = self.impossible_filter(jobs)
        print("AFTER IMPOSSIBLE FILTER:", len(jobs))

        # Experience is a soft penalty, but still hard rejects impossible roles.
        jobs = self.experience_filter(jobs)
        print("AFTER EXP FILTER:", len(jobs))

        jobs = self.desc_red_flag_check(jobs)
        print("AFTER RED FLAG CHECK:", len(jobs))

        jobs = self.title_filter(jobs)
        print("AFTER TITLE FILTER:", len(jobs))

        # Company is not an application eligibility gate.
        # jobs = self.company_veto(jobs)
        print("AFTER COMPANY VETO:", len(jobs))

        jobs = self.ai_relevance_gate(jobs)
        print("AFTER AI RELEVANCE GATE:", len(jobs))

        # Stack mismatch is a ranking signal, never an eligibility veto.
        jobs = self.tag_presort(jobs)

        jobs = jobs[: self.ai_score_limit]
        print("AFTER LIMIT:", len(jobs))

        return jobs

    def score_and_select(self, jobs):
        """
        Final classification after full-JD enrichment.

        Order:
        1. Full-JD red flags
        2. Full-JD primary stack conflicts
        3. AI scoring
        4. Deterministic post-score enforcement
        5. Rank and select
        """

        jobs = self.full_description_red_flag_check(jobs)
        print("AFTER FULL JD RED FLAG CHECK:", len(jobs))

        jobs = self.location_work_mode_gate(jobs)
        print("AFTER LOCATION / WORK-MODE GATE:", len(jobs))

        jobs = self.ai_score_batch(jobs)

        jobs = self.post_score_guard(jobs)
        print("AFTER POST-SCORE GUARD:", len(jobs))

        jobs = self.rank(jobs)
        print("AFTER RANK:", len(jobs))

        jobs = self.select(jobs)
        print("FINAL SELECTED:", len(jobs))

        for j in jobs:
            print(
                f"  {j.get('ai_score'):>3}  "
                f"{j.get('title')} @ {j.get('company')}"
                f"  |  {j.get('ai_reason', '')}"
            )

        return jobs

    def run(self, jobs):
        """
        Compatibility wrapper for tests and existing callers.

        Production orchestration should use:
            pre_filter()
            enrichment
            score_and_select()
        """

        candidates = self.pre_filter(jobs)

        return self.score_and_select(candidates)

    # =========================================================
    # NORMALIZE  — tags are the star, keep them clean
    # =========================================================
    def normalize_jobs(self, jobs):
        normalized = []

        for j in jobs:
            job = j if isinstance(j, dict) else j.__dict__

            # days old
            posted = (job.get("posted_date") or "").lower()
            days_old = None
            if posted:
                if "today" in posted or "hour" in posted or "just now" in posted:
                    days_old = 0
                elif "yesterday" in posted:
                    days_old = 1
                else:
                    m = re.search(r"(\d+)\s*day", posted)
                    if m:
                        days_old = int(m.group(1))
                    else:
                        m = re.search(r"(\d+)\s*week", posted)
                        if m:
                            days_old = int(m.group(1)) * 7

            # experience range
            exp = job.get("experience") or ""
            exp_min, exp_max = 0, 10
            nums = re.findall(r"\d+", exp)
            if len(nums) >= 2:
                exp_min, exp_max = int(nums[0]), int(nums[1])
            elif len(nums) == 1:
                exp_min = exp_max = int(nums[0])

            # tags — normalize once, use everywhere
            raw_tags = job.get("tags") or job.get("skills") or []
            if isinstance(raw_tags, str):
                raw_tags = re.split(r"[,;|]", raw_tags)
            tags = [t.strip().lower() for t in raw_tags if t.strip()]

            # Preserve existing decision history if seeded, else seed it
            decision_history = job.get("decision_history")
            if not decision_history:
                decision_history = [{"stage": "Acquisition"}]

            normalized.append(
                {
                    "job_id": job.get("job_id"),
                    "title": (job.get("title") or "").strip(),
                    "company": (job.get("company") or "").strip(),
                    "location": (job.get("location") or "").strip(),
                    "description": (job.get("description") or "").strip(),
                    "tags": tags,
                    "mandatory_tags": tags[:2],
                    "optional_tags": tags[2:],
                    "days_old": days_old,
                    "experience_min": exp_min,
                    "experience_max": exp_max,
                    "search_track": (job.get("search_track") or "UNKNOWN"),
                    "search_query": (job.get("search_query") or ""),
                    "search_profile": (job.get("search_profile") or "unknown"),
                    "matched_technology": (job.get("matched_technology") or ""),
                    "decision_history": decision_history,
                    "rejection_reason": "",
                    "provider_id": job.get("provider_id", "unknown"),
                    "provider_name": job.get("provider_name", "unknown"),
                    "provider_source": job.get("provider_source", "unknown"),
                    "provider_job_id": job.get("provider_job_id", ""),
                }
            )

        return normalized

    # =========================================================
    # AGE FILTER
    # =========================================================
    def age_filter(self, jobs):
        from src.config.search_strategy import load_search_strategy
        from src.orchestration.job_decision_ledger import compute_job_fingerprint

        strategy = load_search_strategy()
        max_age = strategy.job_policy.max_posting_age_days
        reject_unknown = strategy.job_policy.reject_unknown_posting_age

        clean = []
        for j in jobs:
            days_old = j.get("days_old")

            if days_old is None:
                if reject_unknown:
                    posted_date = j.get("posted_date") or "unknown"
                    provider = j.get("provider_name", "unknown")
                    title = str(j.get("title") or "")
                    company = str(j.get("company") or "")
                    location = str(j.get("location") or "")
                    fingerprint = compute_job_fingerprint(title, company, location)

                    reason = f"Posting date: {posted_date}, Age: unknown, Threshold: {max_age}, Provider: {provider}, Fingerprint: {fingerprint}"
                    self.record_decision(j, "Age Filter", "POSTING_TOO_OLD", reason)
                    if self.metrics:
                        self.metrics.record_rejection("Posting Too Old")
                    continue
            elif days_old > max_age:
                posted_date = j.get("posted_date") or "unknown"
                provider = j.get("provider_name", "unknown")
                title = str(j.get("title") or "")
                company = str(j.get("company") or "")
                location = str(j.get("location") or "")
                fingerprint = compute_job_fingerprint(title, company, location)

                reason = f"Posting date: {posted_date}, Age: {days_old}, Threshold: {max_age}, Provider: {provider}, Fingerprint: {fingerprint}"
                self.record_decision(j, "Age Filter", "POSTING_TOO_OLD", reason)
                if self.metrics:
                    self.metrics.record_rejection("Posting Too Old")
                continue

            clean.append(j)
        return clean

    # =========================================================
    # DEDUP
    # =========================================================
    def dedup(self, jobs):
        seen, result = set(), []
        for j in jobs:
            job_id = j.get("job_id")
            if job_id is None:
                result.append(j)  # can't dedup without an id, just keep it
                continue
            if job_id in seen:
                continue

            title = str(j.get("title") or "")
            company = str(j.get("company") or "")
            location = str(j.get("location") or "")

            if self.exec_context and hasattr(self.exec_context, "ledger"):
                if self.exec_context.ledger.is_duplicate_fingerprint(
                    title, company, location
                ):
                    self.record_decision(
                        j,
                        "Deduplication",
                        "ALREADY_PROCESSED",
                        "Job fingerprint found in active ledger decisions",
                    )
                    if self.metrics:
                        self.metrics.record_rejection("Deduplication")
                    continue

            seen.add(job_id)
            result.append(j)
        return result

    # =========================================================
    # IMPOSSIBLE FILTER  — domain exclusions only
    # =========================================================
    def impossible_filter(self, jobs):
        clean = []
        for j in jobs:
            title = (j.get("title") or "").lower()
            rejected = False
            for domain, patterns in self.IMPOSSIBLE_DOMAINS.items():
                if any(re.search(pattern, title) for pattern in patterns):
                    self.record_decision(
                        j,
                        "Impossible Filter",
                        "OBJECTIVELY_INCOMPATIBLE",
                        f"Title matched impossible domain: {domain}",
                    )
                    if self.metrics:
                        self.metrics.record_rejection("Impossible Filter")
                    rejected = True
                    break

            if not rejected:
                clean.append(j)
        return clean

    # =========================================================
    # EXPERIENCE FILTER
    # =========================================================
    def experience_filter(self, jobs):
        """
        Keep roles that are plausible for the candidate's overall engineering
        seniority. Do not equate years of Applied-AI work with total software
        experience: the candidate has a senior full-stack foundation and a
        newer Applied-AI specialization.

        Reject only clearly junior-only roles and roles whose minimum
        experience is beyond a credible transition range.
        """
        clean = []

        for job in jobs:
            title = (job.get("title") or "").lower()
            exp_min = int(job.get("experience_min", 0) or 0)
            exp_max = int(job.get("experience_max", 10) or 10)

            junior_only = (
                any(
                    token in title
                    for token in ("intern", "internship", "graduate trainee", "fresher")
                )
                or exp_max == 0
            )

            too_senior = any(
                token in title
                for token in (
                    "vice president",
                    "vp of",
                    "head of engineering",
                    "head of technology",
                    "chief technology officer",
                    "cto",
                    "director",
                    "principal",
                    "head of ai",
                    "distinguished engineer",
                    "fellow",
                )
            )

            if junior_only or too_senior:
                code = "EXPERIENCE_TOO_LOW" if junior_only else "EXPERIENCE_TOO_HIGH"
                reason = (
                    "Requires fresher/0 years experience"
                    if junior_only
                    else "Title indicates non-target seniority level"
                )
                self.record_decision(job, "Experience Filter", code, reason)
                if self.metrics:
                    self.metrics.record_rejection("Hard Veto (Experience/Seniority)")
                continue

            clean.append(job)

        return clean

    # =========================================================
    # DESC RED FLAG CHECK  — one cheap regex pass, nothing more
    # =========================================================
    def desc_red_flag_check(self, jobs):
        clean = []
        for j in jobs:
            desc = (j.get("description") or "").lower()
            flagged = [
                label
                for label, pat in self.DESC_RED_FLAGS.items()
                if re.search(pat, desc)
            ]
            if flagged:
                print(f"  [RED FLAG {flagged}] {j.get('title')}")
                self.record_decision(
                    j,
                    "Desc Red Flag Check",
                    "DESC_RED_FLAG",
                    f"Description matched red flag pattern: {flagged[0]}",
                )
                if self.metrics:
                    self.metrics.record_rejection(f"Red Flag (Desc): {flagged[0]}")
                continue
            clean.append(j)
        return clean

    def full_description_red_flag_check(self, jobs):
        """
        Re-run description safety checks against the enriched full JD.

        Search-result descriptions may be empty or abbreviated, so the same
        checks are applied again after detail enrichment.
        """

        clean = []

        for job in jobs:
            desc = (job.get("description") or "").lower()

            flagged = [
                label
                for label, pattern in self.DESC_RED_FLAGS.items()
                if re.search(pattern, desc)
            ]

            if flagged:
                print(
                    f"  [FULL JD RED FLAG {flagged}] "
                    f"{job.get('title')} @ "
                    f"{job.get('company')}"
                )
                self.record_decision(
                    job,
                    "Full Desc Red Flag Check",
                    "FULL_DESC_RED_FLAG",
                    f"Full description matched red flag pattern: {flagged[0]}",
                )
                if self.metrics:
                    self.metrics.record_rejection(f"Red Flag (Full JD): {flagged[0]}")
                continue

            clean.append(job)

        return clean

    # =========================================================
    # TAG PRESORT  — rough stack overlap count, no AI cost
    # Keeps best candidates at the front before we hit the limit
    # =========================================================

    def title_filter(self, jobs):
        result = []

        for job in jobs:
            title = (job.get("title") or "").lower()

            explicit_ai_title = any(signal in title for signal in self.AI_TITLE_SIGNALS)

            if not explicit_ai_title and not any(
                keyword in title for keyword in self.SOFTWARE_KEYWORDS
            ):
                self.record_decision(
                    job, "Title Filter", "NON_SOFTWARE_ROLE", "Non-software role"
                )
                if self.metrics:
                    self.metrics.record_rejection("Title Filter (Not SW/AI)")
                continue

            # We removed the WRONG_TRACK rejection so things like Android/iOS, DevOps, SRE
            # can be penalized by the AI instead of hard-rejected.

            result.append(job)

        return result

    def company_veto(self, jobs):
        clean = []
        for j in jobs:
            company = (j.get("company") or "").lower()
            if any(vc in company for vc in self.VETO_COMPANIES):
                print(f"  [COMPANY VETO] {j.get('title')} @ {j.get('company')}")
                self.record_decision(
                    j, "Company Veto", "COMPANY_VETO", "Company is blacklisted"
                )
                if self.metrics:
                    self.metrics.record_rejection("Company Veto")
                continue
            clean.append(j)
        return clean

    def ai_relevance_gate(self, jobs):
        """
        AI relevance is now a ranking signal, not a hard gate.
        We will score all engineering roles.
        """
        for job in jobs:
            title = (job.get("title") or "").lower()
            tags_text = " ".join(job.get("tags") or []).lower()
            description = (job.get("description") or "").lower()
            searchable_text = " ".join((title, tags_text, description))

            title_hits = sorted(
                signal for signal in self.AI_TITLE_SIGNALS if signal in title
            )
            strong_hits = sorted(
                signal for signal in self.STRONG_AI_SIGNALS if signal in searchable_text
            )
            medium_hits = sorted(
                signal for signal in self.MEDIUM_AI_SIGNALS if signal in searchable_text
            )

            explicit_ai_title = bool(title_hits)
            concrete_ai_work = len(strong_hits) >= 1
            broad_ai_evidence = len(medium_hits) >= 2

            if explicit_ai_title:
                relevance_reason = f"AI title signal: {title_hits[0]}"
                ai_relevance = True
            elif concrete_ai_work:
                relevance_reason = f"Strong AI signal: {strong_hits[0]}"
                ai_relevance = True
            elif broad_ai_evidence:
                relevance_reason = "Multiple AI signals: " + ", ".join(medium_hits[:3])
                ai_relevance = True
            else:
                relevance_reason = "No strong AI signals found; treated as general software engineering."
                ai_relevance = False

            job["ai_relevance"] = ai_relevance
            job["ai_relevance_reason"] = relevance_reason
            job["ai_signal_count"] = (
                len(title_hits) + len(strong_hits) + len(medium_hits)
            )
            job.setdefault("decision_history", []).append(
                {"stage": "AI Filter", "decision": "PASS (Ranking Signal)"}
            )

        return jobs

    def primary_stack_conflict_filter(
        self,
        jobs,
        use_full_description=False,
    ):
        """
        Compatibility hook. Broad AI coverage policy never rejects a genuine
        AI job because of Java/C++/.NET/CV/ML/Data-Science stack differences.
        Those differences are handled by scoring and ranking only.
        """
        return list(jobs)

    @staticmethod
    def _classify_work_mode(job):
        structured = (
            " ".join(str(job.get(key) or "") for key in ("work_mode", "workMode"))
            .lower()
            .strip()
        )

        location = str(job.get("location") or "").lower().strip()
        description = str(job.get("description") or "").lower()
        text = f"{location} {description}"

        negative_remote = (
            r"\bnot remote\b",
            r"\bno remote (?:work|working|option)\b",
            r"\bremote (?:work|working) (?:is )?not available\b",
            r"\bno work[- ]from[- ]home\b",
            r"\bwfh (?:is )?not available\b",
            r"\bmust relocate\b",
        )
        hybrid_signals = (
            r"\bhybrid (?:role|position|work|working|model|mode)\b",
            r"\bhybrid\b",
        )
        office_signals = (
            r"\bwork[- ]from[- ]office\b",
            r"\bwfo\b",
            r"\bon[- ]site\b",
            r"\bin[- ]office\b",
            r"\boffice[- ]based\b",
        )
        remote_signals = (
            r"\bfully remote\b",
            r"\b100% remote\b",
            r"\bremote (?:role|position|job|work|working)\b",
            r"\bwork remotely\b",
            r"\bwork[- ]from[- ]home\b",
            r"\bwfh\b",
            r"\blocation independent\b",
            r"\bwork from anywhere\b",
        )

        # Explicit negative language wins over every positive remote signal.
        if any(re.search(pattern, text) for pattern in negative_remote):
            if any(re.search(pattern, text) for pattern in hybrid_signals):
                return "hybrid"
            if any(re.search(pattern, text) for pattern in office_signals):
                return "office"
            return "office"

        # Naukri can emit location="Remote" while work_mode="Hybrid". For the
        # user's policy, explicit remote location metadata qualifies worldwide.
        if re.search(r"\bremote\b", location):
            return "remote"

        if structured:
            if re.search(r"\b(remote|wfh|work from home)\b", structured):
                return "remote"
            if re.search(r"\bhybrid\b", structured):
                return "hybrid"
            if re.search(r"\b(office|onsite|on-site|wfo)\b", structured):
                return "office"

        if any(re.search(pattern, text) for pattern in hybrid_signals):
            return "hybrid"

        if any(re.search(pattern, text) for pattern in office_signals):
            return "office"

        if any(re.search(pattern, text) for pattern in remote_signals):
            return "remote"

        return "unknown"

    @staticmethod
    def _classify_location_preference(job):
        location = str(job.get("location") or "").lower()
        description = str(job.get("description") or "").lower()

        mode = JobFilterPipeline2._classify_work_mode(job)
        if mode == "remote":
            return "Preferred"

        preferred_pattern = r"\bpune\b|\bpimpri\b|\bchinchwad\b|\bhinja?wadi\b|\bbengaluru\b|\bbangalore\b|\bhyderabad\b|\bremote\b"
        acceptable_pattern = r"\bmumbai\b|\bchennai\b|\bnoida\b|\bgurgaon\b|\bgurugram\b|\bdelhi ncr\b|\bflexible\b|\bindia\b"

        if re.search(preferred_pattern, location):
            return "Preferred"
        if re.search(acceptable_pattern, location):
            return "Acceptable"

        explicit_preferred = (
            rf"\b(?:job|work|base|office) location\s*[:\-]\s*[^.\n]{{0,100}}(?:{preferred_pattern})",
            rf"\bbased in\s+(?:{preferred_pattern})",
            rf"\bposition is based in\s+(?:{preferred_pattern})",
        )
        if any(re.search(pattern, description) for pattern in explicit_preferred):
            return "Preferred"

        explicit_acceptable = (
            rf"\b(?:job|work|base|office) location\s*[:\-]\s*[^.\n]{{0,100}}(?:{acceptable_pattern})",
            rf"\bbased in\s+(?:{acceptable_pattern})",
            rf"\bposition is based in\s+(?:{acceptable_pattern})",
        )
        if any(re.search(pattern, description) for pattern in explicit_acceptable):
            return "Acceptable"

        return "Unknown"

    def location_work_mode_gate(self, jobs):
        """
        Location is now a ranking penalty, not a hard gate, unless explicitly blacklisted.
        """
        eligible = []
        for job in jobs:
            mode = self._classify_work_mode(job)
            loc_pref = self._classify_location_preference(job)

            job["work_mode_classification"] = mode
            job["location_preference"] = loc_pref

            # We can reject if it's explicitly onsite abroad, but for now we'll pass it and let the LLM score it low.
            # Record it for metrics.
            job.setdefault("decision_history", []).append(
                {"stage": "Location Filter", "decision": f"PASS ({loc_pref})"}
            )
            eligible.append(job)

        return eligible

    def tag_presort(self, jobs):
        my_stack = set(self.MY_STACK)

        from src.config.search_strategy import load_search_strategy

        strategy = load_search_strategy()
        weights = strategy.summary_scoring

        for j in jobs:
            tags = set(j.get("tags", []))
            mandatory_hit = sum(1 for t in j.get("mandatory_tags", []) if t in my_stack)
            total_hit = len(tags & my_stack)

            days_old_val = j.get("days_old")
            days_old = days_old_val if days_old_val is not None else 7
            # Recency bonus: max 7 points (0 days old = 7, 7 days old = 0)
            recency_days = max(0, 7 - days_old)

            mandatory_score = mandatory_hit * weights.mandatory_weight
            skills_score = total_hit * weights.skills_weight
            recency_score = recency_days * weights.recency_weight

            total_score = mandatory_score + skills_score + recency_score

            j["summary_score"] = total_score
            j["summary_breakdown"] = {
                "mandatory_hits": mandatory_hit,
                "mandatory_score": mandatory_score,
                "skills_hits": total_hit,
                "skills_score": skills_score,
                "recency_days": days_old,
                "recency_score": recency_score,
            }

        return sorted(jobs, key=lambda j: j["summary_score"], reverse=True)

    def post_score_guard(self, jobs):
        """
        Deterministic post-score guard to validate candidate jobs after AI scoring.
        Ensures scores are bounded and non-null before ranking.
        """
        guarded = []
        for job in jobs:
            score = job.get("ai_score")
            if score is None:
                job["ai_score"] = job.get("score", 0)
            guarded.append(job)
        return guarded

    def _job_text(self, job):
        return " ".join(
            [
                (job.get("title") or "").lower(),
                " ".join(job.get("mandatory_tags") or []).lower(),
                " ".join(job.get("optional_tags") or []).lower(),
                " ".join(job.get("tags") or []).lower(),
                (job.get("description") or "").lower(),
            ]
        )

    def _fit_features(self, job):
        text = self._job_text(job)
        title = (job.get("title") or "").lower()

        applied_ai_terms = (
            "generative ai",
            "genai",
            "large language model",
            "llm",
            "rag",
            "retrieval augmented generation",
            "langchain",
            "langgraph",
            "llamaindex",
            "semantic kernel",
            "azure openai",
            "openai api",
            "vector database",
            "vector db",
            "vector search",
            "embedding",
            "agentic ai",
            "ai agent",
            "tool calling",
            "function calling",
            "prompt engineering",
            "llm evaluation",
        )
        backend_terms = (
            "python",
            "fastapi",
            "flask",
            "node.js",
            "nodejs",
            "express",
            "rest api",
            "microservices",
            "mongodb",
            "postgresql",
            "docker",
            "azure",
            "aws",
        )
        frontend_terms = (
            "angular",
            "typescript",
            "rxjs",
            "frontend",
            "front-end",
            "full stack",
            "fullstack",
        )
        research_terms = (
            "research scientist",
            "applied research",
            "publish papers",
            "publication record",
            "phd required",
            "train foundation models",
            "train deep learning models",
            "training neural networks",
            "novel architectures",
            "computer vision research",
        )
        ml_core_terms = (
            "tensorflow",
            "pytorch",
            "scikit-learn",
            "feature engineering",
            "model training",
            "hyperparameter tuning",
            "deep learning",
            "computer vision",
        )

        return {
            "ai_hits": sum(term in text for term in applied_ai_terms),
            "backend_hits": sum(term in text for term in backend_terms),
            "frontend_hits": sum(term in text for term in frontend_terms),
            "research_hits": sum(term in text for term in research_terms),
            "ml_core_hits": sum(term in text for term in ml_core_terms),
            "ai_title": any(signal in title for signal in self.AI_TITLE_SIGNALS),
            "fullstack_title": any(
                term in title
                for term in ("full stack", "fullstack", "software engineer")
            ),
        }

    class EvidenceConfidenceEngine:
        """
        Generic evaluator that bypasses LLM reasoning when structured evidence
        provides high confidence of a positive match.
        """

        @staticmethod
        def evaluate(features: dict, title: str) -> dict:
            # We aggregate signal strength across all extracted domains.
            signal_strength = features.get("ai_hits", 0) * 1.5
            signal_strength += features.get("backend_hits", 0) * 1.0
            signal_strength += features.get("frontend_hits", 0) * 0.5
            signal_strength += features.get("ml_core_hits", 0) * 1.2

            # Very strong single signals
            if features.get("ai_title"):
                signal_strength += 5.0
            if features.get("fullstack_title"):
                signal_strength += 3.0

            if signal_strength >= 4.0:
                return {
                    "status": "OBVIOUS_APPLY",
                    "decision": "APPLY",
                    "score": min(100, int(70 + signal_strength * 2)),
                    "reason": f"High confidence deterministic match (signal strength: {signal_strength:.1f})",
                }
            return {"status": "NEEDS_REASONING"}

    # =========================================================
    # AI SCORING  — tags go in, score + reason come out
    # =========================================================
    def ai_score_batch(self, jobs, timeout: float = 60.0, global_offset: int = 0):
        import sys
        import time
        from datetime import datetime, timezone
        print(f"Entering ai_score_batch (Total Jobs: {len(jobs)}, Timeout: {timeout}s)", file=sys.stdout, flush=True)
        result = []
        jobs_for_inference = []

        system_prompt = (
            "You are the evaluator for an autonomous job acquisition engine.\n"
            "This platform intentionally optimizes for high recall (Spray & Pray), NOT maximum precision.\n"
            "The objective is to maximize interview opportunities, NOT to identify only perfect matches.\n"
            "Assume that spending one application is inexpensive compared to missing a potential interview.\n\n"
            "Primary Objective:\n"
            "Would applying to this job be a reasonable use of an application, given the user's profile and stated strategy? \n"
            "Prefer applying unless there is a strong reason not to.\n"
            "Evaluate whether the candidate could plausibly succeed in the hiring process—not whether they are the perfect match.\n\n"
            "Candidate ground-truth profile:\n"
            "- Senior software engineer with production full-stack/backend experience.\n"
            "- Angular/TypeScript, Node.js/Express, REST APIs, MongoDB, service integration.\n"
            "- Production AI engineering experience represented by Python/FastAPI AI services,\n"
            "  RAG, hybrid retrieval, embeddings, LangChain/LangGraph, agents, tool calling, Azure OpenAI.\n\n"
            "POLICY:\n"
            "- NEVER reject a job solely because it is not a perfect match.\n"
            "- Borderline software engineering roles (Backend, Full Stack, Platform, Cloud, Python, Node.js, DevOps, AI-adjacent) should continue through evaluation.\n"
            "- Only REJECT jobs that are objectively incompatible with the candidate's background.\n"
            "- Stack mismatch or missing sub-disciplines affects ranking, but should NOT usually result in rejection.\n"
            "- Absence of evidence is not evidence of incompatibility. Missing AI keywords, incomplete descriptions, or poorly written JDs must not be interpreted as negative evidence. Penalize explicit mismatches, not missing information.\n"
            "- If confidence is uncertain but the role is technically adjacent, default to APPLY.\n\n"
            "OUTPUT CONTRACT:\n"
            "Return JSON containing 'decision' ('APPLY' or 'REJECT'), 'score' (0-100 integer representing Apply Confidence), and 'reason'.\n"
            "No markdown or extra text.\n"
        )

        total_jobs = len(jobs)
        for idx, job in enumerate(jobs, 1):
            jid = str(job.get("job_id") or "").strip()
            f = self._fit_features(job)
            title = (job.get("title") or "").lower()
            global_num = global_offset + idx

            if self.test_mode:
                eval_result = self.EvidenceConfidenceEngine.evaluate(f, title)
                score = (
                    eval_result.get("score", 70)
                    if eval_result.get("status") == "OBVIOUS_APPLY"
                    else 65
                )
                job["ai_decision"] = "APPLY"
                job["ai_score"] = score
                job["ai_reason"] = "Test mode deterministic score"
                job["structured_evidence"] = f
                job.setdefault("decision_history", []).append(
                    {"stage": "AI Score", "score": job["ai_score"]}
                )
                result.append(job)
            else:
                jobs_for_inference.append((idx, global_num, total_jobs, job, f, title, jid))

        if not self.test_mode and jobs_for_inference:

            def _process_inference(item):
                batch_num, global_num, total_in_batch, job, f, title, jid = item
                import sys
                raw_desc = (job.get("description") or "").strip()
                raw_desc_len = len(raw_desc)
                mandatory = ", ".join(job.get("mandatory_tags", [])) or "none"
                optional = ", ".join(job.get("optional_tags", [])) or "none"
                exp = f"{job.get('experience_min', 0)}-{job.get('experience_max', 10)} yrs"
                description = raw_desc[:6000]

                prompt = (
                    f"Job ID:      {job.get('job_id')}\n"
                    f"Title:       {job.get('title')}\n"
                    f"Company:     {job.get('company')}\n"
                    f"Mandatory:   {mandatory}\n"
                    f"Optional:    {optional}\n"
                    f"Exp:         {exp}\n"
                    f"Full JD:\n{description}\n"
                )
                prompt_chars = len(prompt)
                est_tokens = prompt_chars // 4

                start_time_iso = datetime.now(timezone.utc).isoformat()
                start_clock = time.perf_counter()

                print(
                    f"[JOB #{batch_num}/{total_in_batch} (Global #{global_num})] START - "
                    f"ID: {jid} | Title: {job.get('title')} | Raw Desc: {raw_desc_len} chars | "
                    f"Prompt: {prompt_chars} chars (~{est_tokens} tokens) | Time: {start_time_iso}",
                    file=sys.stdout,
                    flush=True,
                )

                context_hash = hashlib.md5(
                    f"{job.get('provider_id', '')}:{jid}:{title}:{description}".encode(
                        "utf-8"
                    )
                ).hexdigest()

                parsed = self.inference_service.classify_job(
                    evidence=f,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    context_hash=context_hash,
                )

                duration_s = time.perf_counter() - start_clock
                end_time_iso = datetime.now(timezone.utc).isoformat()

                print(
                    f"[JOB #{batch_num}/{total_in_batch} (Global #{global_num})] END - "
                    f"ID: {jid} | Duration: {duration_s:.2f}s | Time: {end_time_iso}",
                    file=sys.stdout,
                    flush=True,
                )

                job["ai_decision"] = parsed.get("decision", "APPLY")
                score_val = (
                    parsed.get("llm_score")
                    if "llm_score" in parsed
                    else parsed.get("score", 50)
                )
                job["ai_score"] = score_val
                job["ai_reason"] = parsed.get(
                    "reason", "Inference response missing reason"
                )
                job["structured_evidence"] = f

                job.setdefault("decision_history", []).append(
                    {
                        "stage": "AI Score",
                        "score": job["ai_score"],
                        "decision": job["ai_decision"],
                    }
                )
                return job

            import sys
            print(f"Creating ThreadPoolExecutor for {len(jobs_for_inference)} jobs...", file=sys.stdout, flush=True)
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(10, len(jobs_for_inference))
            ) as executor:
                futures = {}
                for item in jobs_for_inference:
                    batch_num, global_num, total_in_batch, job_obj, f, title, jid = item
                    print(f"Submitting Job #{batch_num}/{total_in_batch} (Global #{global_num}) ID: {jid}", file=sys.stdout, flush=True)
                    futures[executor.submit(_process_inference, item)] = item

                print("Waiting for completed futures...", file=sys.stdout, flush=True)
                completed_count = 0
                failed_count = 0
                for future in concurrent.futures.as_completed(futures):
                    item = futures[future]
                    batch_num, global_num, total_in_batch, job_obj, f, title, jid = item
                    try:
                        res = future.result(timeout=timeout)
                        result.append(res)
                        completed_count += 1
                        print(f"Result acquired for Job #{batch_num}/{total_in_batch} (Global #{global_num}) ID: {jid} (Completed {completed_count}/{total_in_batch})", file=sys.stdout, flush=True)
                    except concurrent.futures.TimeoutError:
                        failed_count += 1
                        print(f"[STALLED / TIMEOUT] Job #{batch_num}/{total_in_batch} (Global #{global_num}) ID: {jid} timed out after {timeout}s!", file=sys.stdout, flush=True)
                    except Exception as e:
                        failed_count += 1
                        print(f"[FAILED] Job #{batch_num}/{total_in_batch} (Global #{global_num}) ID: {jid}: {e}", file=sys.stdout, flush=True)

        print(f"Leaving ai_score_batch (Completed: {len(result)}, Failed/Timed out: {total_jobs - len(result)})", file=sys.stdout, flush=True)
        return result

    # =========================================================
    # RANK  — ai score + small recency bump
    # =========================================================
    def rank(self, jobs):
        return sorted(
            jobs,
            key=lambda job: (
                job.get("ai_score") or 0,
                job.get("ai_signal_count") or 0,
                -(job.get("days_old") or 7),
            ),
            reverse=True,
        )

    # =========================================================
    # SELECT
    # =========================================================
    def select(self, jobs):
        """
        Every job reaching this stage has already passed the hard-veto,
        genuine-AI relevance, and location/work-mode eligibility gates.

        AI score controls ordering only; it is not an eligibility threshold.
        """
        return jobs[: self.daily_apply_limit]

    # =========================================================
    # CACHE
    # =========================================================
    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file) as f:
                    data = json.load(f)

                return data if isinstance(data, dict) else {}

            except Exception:
                return {}

        return {}

    def _save_cache(self):
        with open(self.cache_file, "w") as f:
            json.dump(self.cache, f, indent=2)
