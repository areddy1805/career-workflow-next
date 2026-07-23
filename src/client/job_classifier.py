import json
import os
import re
import requests
import time
import psutil

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

    # ── hard veto BEFORE ai — title only, zero ambiguity ────────────────────
    # Hard veto only unmistakably non-target employment formats / non-engineering roles.
    # AI/ML/Data Science/CV/model-training titles are deliberately NOT vetoed.
    VETO_TITLES = [
        "walk-in",
        "walkin",
        "walk in",
        "tutor",
        "trainer",
        "sales executive",
        "business development executive",
        "recruiter",
        "talent acquisition",
    ]

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
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        cache_file: str = "data/score_cache.json",
        daily_apply_limit: int = 500,
        min_apply_score: int = 50,
        ai_score_limit: int = 300,
        batch_size: int = 5,
        metrics: PipelineRunMetrics | None = None,
        exec_context=None,
        cache_manager: CacheManager | None = None,
    ):
        self.metrics = metrics
        self.exec_context = exec_context
        self.cache_manager = cache_manager
        self.api_key = api_key or os.getenv("OMLX_API_KEY")
        
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=100)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        if not self.api_key:
            raise ValueError("OMLX_API_KEY is not configured")

        self.base_url = (
            base_url or os.getenv("OMLX_BASE_URL") or "http://127.0.0.1:8000/v1"
        ).rstrip("/")

        self.model = model or os.getenv("OMLX_MODEL") or "qwen3.5-4b"

        self.url = f"{self.base_url}/chat/completions"

        self.cache_file = cache_file
        self.daily_apply_limit = daily_apply_limit
        self.min_apply_score = min_apply_score
        self.ai_score_limit = ai_score_limit
        self.batch_size = batch_size
        self.cache = self._load_cache()
        self.rejected_jobs: list[dict] = []

    # =========================================================
    # STATE TRACKING
    # =========================================================

    def record_decision(self, job: dict, stage: str, code: str, reason: str) -> None:

        job_copy = job.copy()
        job_copy["rejection_stage"] = stage
        job_copy["rejection_code"] = code
        job_copy["rejection_reason"] = reason

        if self.exec_context:
            self.exec_context.reject(job, reason=reason, code=code)

        self.rejected_jobs.append(job_copy)

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

        if not job.get("_rejection_recorded"):
            self.rejected_jobs.append(job)
            job["_rejection_recorded"] = True

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

        jobs = self.dedup(jobs)
        print("AFTER DEDUP:", len(jobs))

        jobs = self.hard_veto(jobs)
        print("AFTER HARD VETO:", len(jobs))

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
            days_old = 7
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
            seen.add(job_id)
            result.append(j)
        return result

    # =========================================================
    # HARD VETO  — title only, no ambiguity allowed
    # =========================================================
    def hard_veto(self, jobs):
        clean = []
        for j in jobs:
            title = (j.get("title") or "").lower()
            if any(kw in title for kw in self.VETO_TITLES):
                self.record_decision(
                    j, "Hard Veto", "WALK_IN_RECRUITMENT", f"Title matched veto pattern"
                )
                if self.metrics:
                    self.metrics.record_rejection("Hard Veto (Title)")
                continue
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

            days_old = j.get("days_old", 7)
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

    def _calibrate_score(self, job, raw_score):
        """
        Bound model variance with deterministic evidence bands.

        The LLM judges semantic fit inside a band; deterministic evidence
        prevents generic AI mentions from outranking direct Applied-AI roles.
        """
        score = max(0, min(100, int(raw_score)))
        f = self._fit_features(job)

        if f["research_hits"] >= 2 and f["ai_hits"] == 0:
            return min(score, 25)

        if f["ml_core_hits"] >= 3 and f["ai_hits"] <= 1:
            return min(score, 39)

        if f["ai_hits"] >= 4 and (f["backend_hits"] >= 2 or f["ai_title"]):
            return max(score, 78)

        if f["ai_hits"] >= 2 and f["backend_hits"] >= 2:
            return max(score, 72)

        if f["ai_hits"] >= 2 and (f["backend_hits"] >= 1 or f["frontend_hits"] >= 1):
            return max(score, 65)

        if f["ai_hits"] == 1 and not f["ai_title"]:
            return min(score, 59)

        return score

    # =========================================================
    # AI SCORING  — tags go in, score + reason come out
    # =========================================================
    def ai_score_batch(self, jobs):
        result = []

        # Adaptive concurrency
        try:
            cpu_usage = psutil.cpu_percent(interval=0.1)
            if cpu_usage > 85.0:
                self.batch_size = max(1, self.batch_size // 2)
            elif cpu_usage < 40.0:
                self.batch_size = min(10, self.batch_size + 1)
        except Exception:
            pass

        for i in range(
            0,
            len(jobs),
            self.batch_size,
        ):
            batch = jobs[i : i + self.batch_size]

            uncached_jobs = []

            for job in batch:
                jid = str(job.get("job_id") or "").strip()

                cached_data = None
                
                # Check CacheManager
                if self.cache_manager and jid:
                    provider = job.get("provider_id", "naukri")
                    title = job.get("title", "")
                    company = job.get("company", "")
                    desc = job.get("description", "")
                    
                    fingerprint = compute_llm_fingerprint(
                        provider=provider,
                        job_id=jid,
                        title=title,
                        company=company,
                        normalized_description=desc,
                        model_name=self.model,
                        prompt_version="1",
                        classifier_version="1",
                        pipeline_version="1",
                        search_strategy_version="1",
                        ranking_version="1"
                    )
                    job["_llm_fingerprint"] = fingerprint
                    
                    start_lookup = time.perf_counter()
                    llm_record = self.cache_manager.llm.get(fingerprint)
                    self.cache_manager.track_lookup((time.perf_counter() - start_lookup) * 1000)
                    
                    if llm_record:
                        self.cache_manager.metrics["llm_hits"] += 1
                        self.cache_manager.metrics["llm_tokens_saved"] += llm_record.get("tokens", 0)
                        self.cache_manager.metrics["llm_time_saved_ms"] += llm_record.get("latency_ms", 0)
                        
                        try:
                            parsed = json.loads(llm_record["parsed_response"])
                            if isinstance(parsed, dict) and "score" in parsed:
                                cached_data = parsed
                        except Exception:
                            pass
                    else:
                        self.cache_manager.metrics["llm_misses"] += 1

                if not cached_data and jid and jid in self.cache:
                    cached_data = self.cache[jid]

                if cached_data:
                    job["ai_score"] = cached_data.get("score", 0)
                    job["ai_reason"] = cached_data.get("reason", "cached")
                    result.append(job)
                else:
                    uncached_jobs.append(job)

            if not uncached_jobs:
                continue

            scores = self._call_ai(uncached_jobs)
            
            raw_response = ""
            duration_ms = 0
            tokens = 0
            if isinstance(scores, tuple) and len(scores) == 4:
                scores, raw_response, duration_ms, tokens = scores

            submitted_ids = {
                str(job.get("job_id") or "").strip()
                for job in uncached_jobs
                if str(job.get("job_id") or "").strip()
            }

            valid_scores = {}

            if isinstance(scores, list):
                for item in scores:
                    if not isinstance(item, dict):
                        continue

                    jid = str(item.get("job_id") or "").strip()

                    score = item.get("score")

                    if (
                        jid in submitted_ids
                        and jid not in valid_scores
                        and isinstance(score, int)
                    ):
                        valid_scores[jid] = item

            missing_jobs = []

            for job in uncached_jobs:
                jid = str(job.get("job_id") or "").strip()

                data = valid_scores.get(jid)

                if data is None:
                    missing_jobs.append(job)
                    continue

                normalized_data = {
                    "score": self._calibrate_score(
                        job,
                        data["score"],
                    ),
                    "reason": str(data.get("reason") or "").strip(),
                }

                job["ai_score"] = normalized_data["score"]
                job["ai_reason"] = normalized_data["reason"]

                if jid:
                    self.cache[jid] = normalized_data
                    if self.cache_manager and "_llm_fingerprint" in job:
                        start_save = time.perf_counter()
                        self.cache_manager.llm.set(
                            fingerprint=job["_llm_fingerprint"],
                            provider=job.get("provider_id", "naukri"),
                            job_id=jid,
                            raw_response=raw_response,
                            parsed_response=json.dumps(normalized_data),
                            model=self.model,
                            latency_ms=duration_ms,
                            tokens=tokens
                        )
                        self.cache_manager.track_save((time.perf_counter() - start_save) * 1000)

                result.append(job)

            # Retry malformed or missing jobs individually.
            for job in missing_jobs:
                jid = str(job.get("job_id") or "").strip()

                print(
                    f"  [AI RETRY SINGLE] "
                    f"{job.get('title')} @ "
                    f"{job.get('company')}"
                )

                retry_data = self._call_ai([job])

                matched = None

                if isinstance(retry_data, list):
                    for item in retry_data:
                        if not isinstance(item, dict):
                            continue

                        if str(item.get("job_id") or "").strip() == jid and isinstance(
                            item.get("score"), int
                        ):
                            matched = item
                            break

                if matched is None:
                    print(
                        f"AI score unavailable after retry "
                        f"for job_id={jid or '<unknown>'}"
                    )

                    job["ai_score"] = 0
                    job["ai_reason"] = "AI scoring unavailable after retry"

                    result.append(job)
                    continue

                normalized_data = {
                    "score": self._calibrate_score(
                        job,
                        matched["score"],
                    ),
                    "reason": str(matched.get("reason") or "").strip(),
                }

                job["ai_score"] = normalized_data["score"]
                job["ai_reason"] = normalized_data["reason"]

                if jid:
                    self.cache[jid] = normalized_data

                result.append(job)

            self._save_cache()

        for job in result:
            job.setdefault("decision_history", []).append(
                {"stage": "AI Score", "score": job.get("ai_score")}
            )

        return result

    def _call_ai(self, jobs):
        job_block = ""
        for j in jobs:
            mandatory = ", ".join(j.get("mandatory_tags", [])) or "none"
            optional = ", ".join(j.get("optional_tags", [])) or "none"
            exp = f"{j.get('experience_min', 0)}-{j.get('experience_max', 10)} yrs"
            description = (j.get("description") or "").strip()

            description = description[:6000]

            job_block += (
                f"Job ID:      {j.get('job_id')}\n"
                f"  Title:       {j.get('title')}\n"
                f"  Company:     {j.get('company')}\n"
                f"  Mandatory:   {mandatory}\n"
                f"  Optional:    {optional}\n"
                f"  Exp:         {exp}\n"
                f"  Days old:    {j.get('days_old', 7)}\n"
                f"  Search track:{j.get('search_track', 'UNKNOWN')}\n"
                f"  AI evidence: {j.get('ai_relevance_reason', '')}\n"
                f"  Full JD:\n{description}\n"
                f"---\n"
            )

        prompt2 = f"""
You rank genuine AI jobs for this candidate. Eligibility is broad; ranking is preference.

Candidate ground-truth profile for matching:
- Senior software engineer with production full-stack/backend experience.
- Angular/TypeScript, Node.js/Express, REST APIs, MongoDB, service integration.
- Production AI engineering experience represented by Python/FastAPI AI services,
  RAG, hybrid retrieval, reranking, embeddings, vector search, LangChain/LangGraph,
  agents, tool calling, LLM evaluation, local model serving, Azure OpenAI,
  Azure AI Foundry, and Azure AI Search.

POLICY:
- Any genuinely AI-related engineering role is eligible.
- Do NOT reject or heavily punish a role merely because its primary stack is
  Java, C++, .NET, TensorFlow, PyTorch, computer vision, NLP, traditional ML,
  data science, model training, MLOps, or another AI sub-discipline.
- Stack and sub-discipline mismatch affect ranking only.
- Generic software jobs with only incidental AI wording should score below 50.
- Explicit AI roles should normally score at least 50.
- Prefer GenAI/LLM/RAG/Agentic roles, then Applied AI/NLP/Prompt/AI Full Stack,
  then ML/CV/DL/Data Science + AI, then ambiguous AI-adjacent roles.
- Evaluate against the stated candidate profile; do not describe the candidate
  as transitioning into AI or lacking production AI experience.

SCORING:
90-100: direct GenAI/LLM/RAG/agentic fit with strong stack overlap.
80-89: strong applied-AI fit.
70-79: genuine AI role with good transferable overlap.
60-69: genuine AI role with meaningful stack/sub-discipline gaps.
50-59: genuine AI role with substantial gaps but still worth applying.
0-49: not genuinely AI work, or AI is merely incidental.

OUTPUT CONTRACT:
Return exactly one result for every supplied Job ID. Copy IDs exactly.
No markdown or extra text. Integer score 0-100.

Return ONLY:
{{
  "results": [
    {{
      "job_id": "exact supplied id",
      "score": 82,
      "reason": "Specific evidence-based fit explanation."
    }}
  ]
}}

Jobs:
{job_block}
"""

        try:
            start_time = time.perf_counter()
            res = self.session.post(
                self.url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt2,
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2000,
                    "response_format": {
                        "type": "json_object",
                    },
                    "chat_template_kwargs": {
                        "enable_thinking": False,
                    },
                },
                timeout=300,
            )
            duration = time.perf_counter() - start_time
            if self.metrics:
                self.metrics.add_llm_time(duration)

            if res.status_code != 200:
                print("AI HTTP ERROR:", res.status_code, res.text[:200])
                return []

            response_json = res.json()

            message = response_json["choices"][0]["message"]

            content = message.get("content") or ""

            content = re.sub(
                r"```json|```",
                "",
                content,
            ).strip()

            match = re.search(
                r"\{.*\}",
                content,
                re.S,
            )

            if not match:
                print(
                    "AI PARSE ERROR — no JSON object found\n"
                    f"finish_reason={response_json['choices'][0].get('finish_reason')}\n"
                    f"content={content[:1000]}"
                )

                return []

            json_text = match.group(0)

            try:
                data = json.loads(json_text)

            except json.JSONDecodeError as exc:
                print(
                    "AI JSON ERROR\n"
                    f"error={exc}\n"
                    f"finish_reason={response_json['choices'][0].get('finish_reason')}\n"
                    f"content={content[:1500]}"
                )

                return []

            if not isinstance(data, dict):
                return []

            results = data.get("results")

            if not isinstance(results, list):
                print("AI CONTRACT ERROR — " "'results' must be a list")
                return ([], "", 0, 0)

            tokens = response_json.get("usage", {}).get("total_tokens", 0)
            return (results, content, duration * 1000, tokens)

        except Exception as e:
            print("AI call error:", e)
            return ([], "", 0, 0)

    def post_score_guard(self, jobs):
        """
        Enforce deterministic consistency between job evidence and score.

        The model may refine ordering inside evidence bands, but it cannot:
        - promote incidental-AI generic software above direct AI work;
        - keep obvious VBA/content roles because the title contains AI;
        - leave concrete LLM/RAG/agentic backend roles below their evidence floor.
        """
        clean = []

        for job in jobs:
            features = self._fit_features(job)
            text = self._job_text(job)
            title = (job.get("title") or "").lower()
            score = int(job.get("ai_score", 0) or 0)

            vba_automation_hits = sum(
                term in text
                for term in (
                    "vba",
                    "excel macros",
                    "advanced excel",
                    "power query",
                    "macro automation",
                )
            )
            content_role_hits = sum(
                term in text
                for term in (
                    "copywriter",
                    "copywriting",
                    "brand copy",
                    "marketing copy",
                    "content writer",
                    "social media content",
                )
            )
            engineering_hits = features["backend_hits"] + features["ai_hits"]

            # Misleading AI titles: the actual work is office automation or content.
            if vba_automation_hits >= 2 and features["ai_hits"] <= 1:
                print(
                    f"  [POST-SCORE REJECT - INCIDENTAL AUTOMATION] "
                    f"{job.get('title')} @ {job.get('company')}"
                )
                self.record_decision(
                    job,
                    "Post Score Guard",
                    "NON_SOFTWARE_ROLE",
                    "Role is incidental automation (VBA/macros) rather than engineering",
                )
                continue

            if content_role_hits >= 2 and engineering_hits <= 2:
                print(
                    f"  [POST-SCORE REJECT - NON-ENGINEERING AI] "
                    f"{job.get('title')} @ {job.get('company')}"
                )
                self.record_decision(
                    job,
                    "Post Score Guard",
                    "NON_SOFTWARE_ROLE",
                    "Role is content creation rather than software engineering",
                )
                continue

            # Generic software with one weak AI mention stays below application floor.
            if features["ai_hits"] <= 1 and not features["ai_title"]:
                score = min(score, 49)

            # Concrete applied-AI backend work gets deterministic floors even when
            # the title is generic (for example an agentic manufacturing platform).
            if features["ai_hits"] >= 4 and (
                features["backend_hits"] >= 2 or features["ai_title"]
            ):
                score = max(score, 78)
            elif features["ai_hits"] >= 2 and features["backend_hits"] >= 2:
                score = max(score, 72)
            elif features["ai_hits"] >= 2 and (
                features["backend_hits"] >= 1 or features["frontend_hits"] >= 1
            ):
                score = max(score, 65)

            # Explicit AI engineering titles remain eligible, but only after the
            # misleading-title rejection rules above have run.
            if features["ai_title"]:
                score = max(score, self.min_apply_score)

            job["ai_score"] = max(0, min(100, score))
            clean.append(job)

        return clean

    # =========================================================
    # RANK  — ai score + small recency bump
    # =========================================================
    def rank(self, jobs):
        return sorted(
            jobs,
            key=lambda job: (
                job.get("ai_score", 0),
                job.get("ai_signal_count", 0),
                -job.get("days_old", 7),
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
