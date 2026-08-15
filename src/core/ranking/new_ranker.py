"""Deterministic multi-objective job ranker (Phases C+D).

Replaces LLM-ai_score as the production ordering key with an explainable
deterministic score. Zero LLM calls. Every score decomposes into
role_family, ai_depth, fde_band + evidence, technical_fit, trajectory,
location fit, and penalties — all reproducible from the job text alone.

Contract used by tools/evaluation/eval_harness.py:
    from src.core.ranking.new_ranker import score
    ranked = sorted(jobs, key=lambda j: -score(j))   # higher = better

Production seam: pipeline sets ``opp.score = new_score(job)``; PriorityEngine
then orders the pool by this score exactly as before (unchanged sort).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Signal tables (deterministic; curated once)
# ---------------------------------------------------------------------------

# Depth 4: deep AI engineering — you build/train/operate the model layer.
DEEP_AI = {
    "fine-tun", "finetun", "pretrain", "pre-train", "model training",
    "train models", "training llm", "training llms", "transformers",
    "model serving", "inference optimization", "inference pipeline",
    "llm inference", "serving layer", "ai infrastructure", "ai infra",
    "mlops", "llmops", "evaluation framework", "ragas", "llm evaluation",
    "evals", "embedding model", "embeddings pipeline", "vector database",
    "vector db", "vector search", "multimodal", "mcp", "model context protocol",
    "agentic", "agents", "multi-agent", "langgraph", "crewai", "autogen",
    "rag pipeline", "production rag", "model deployment", "deploy models",
}

# Depth 3: hands-on GenAI/LLM engineering — you build apps ON the model.
STRONG_AI = {
    "generative ai", "genai", "gen ai", "large language model", "large language models",
    "llm", "llms", "rag", "retrieval augmented generation", "langchain",
    "llamaindex", "semantic kernel", "azure openai", "openai api", "openai",
    "anthropic", "gemini", "claude", "gpt", "prompt engineering", "prompt engineer",
    "ai agent", "ai agents", "ai application", "ai applications", "ai platform",
    "ai copilot", "copilot", "conversational ai", "chatbot", "nlp", "natural language",
    "computer vision", "embeddings", "embedding", "vector search", "hugging face",
    "huggingface", "deep learning", "model integration", "ai api", "ai apis",
    "ai solutions", "ai developer", "ai engineer", "genai developer",
}

# Depth 2: AI-adjacent/ML-adjacent work — ML/data/AI integration, not core GenAI.
MODERATE_AI = {
    "machine learning", "ml engineer", "ai/ml", "aiml", "artificial intelligence",
    "data science", "data scientist", "ml model", "model development",
    "ai integration", "ai-powered", "ai enabled", "ai-enabled", "ai powered",
    "recommendation", "predictive", "forecasting", "regression model",
    "classification model", "feature engineering", "model evaluation",
    "ai product", "ai workflow", "ai features", "ai capabilities",
}

# Depth 1: incidental AI mention — no concrete AI work.
LIGHT_AI = {"ai ", " ai", "artificial intelligence"}

# Non-target role families (never ranked for AI/FDE).
NON_TARGET_TITLE = {
    "team lead", "team leader", "sales", "marketing", "business development",
    "recruitment", "recruiter", "hr ", "human resource", "tax", "accountant",
    "video editor", "content writer", "operations", "realty", "insurance field",
    "field sales", "bpo", "support executive", "telecaller", "customer service",
    "accounts", "finance manager", "chef", "delivery driver", "data entry",
}

NON_TARGET_DESC = {
    "team lead", "team leader", "bp0", "bpo", "telecaller", "outbound call",
    "sales target", "commission", "recruitment process", "payroll processing",
    "tax preparation", "video editing", "content writing", "customer support",
    "call center", "door to door", "field sales", "insurance agent",
}

# Strong FDE evidence (title side).
FDE_TITLE_STRONG = {
    "forward deployed", "forward-deployed", "forward deployment",
    "implementation engineer", "deployment engineer", "customer engineer",
    "technical solutions engineer", "solutions engineer", "ai solutions engineer",
    "solutions consultant", "field engineer", "implementation consultant",
}

# FDE evidence (description side) — customer-facing deployment engineering.
FDE_DESC_STRONG = {
    "deploy solutions to customer", "deploy to customer", "customer site",
    "client site", "on-site deployment", "on site deployment", "production adoption",
    "customer-facing engineering", "customer facing engineering",
    "rapid prototyping", "poc to production", "proof of concept to production",
    "technical discovery", "implementation at customer", "implement at customer",
    "integrate with customer", "go-live", "post-sales engineering", "post sales",
    "work with customers", "working with customers", "work directly with customers",
    "customer onboarding", "deploy at customer", "deployment at customer",
    "customer deployment", "client deployment", "production deployment",
    "build solutions for customers", "solve customer problems", "customer problem",
}

FDE_DESC_MEDIUM = {
    "stakeholder", "integration", "end-to-end implementation", "implementation",
    "prototype", "prototypes", "solution architecture", "consulting",
    "customer success engineering", "technical account", "proof of concept",
    "poc", "discovery phase", "requirements gathering", "product adoption",
}

# Anti-signals: title/desc indicates support/sales, NOT FDE.
FDE_ANTI = {
    "support engineer", "technical support", "customer support", "help desk",
    "field service", "presales", "pre-sales", "sales engineer", "account manager",
    "business development", "customer success manager", "recruiter",
    "service desk", "it support", "desktop support",
}

# Candidate technical fit (from config/candidate_profile.py).
CANDIDATE_TECH = {
    "python": 3.0, "fastapi": 2.0, "azure": 3.0, "openai": 3.0,
    "langchain": 2.0, "langgraph": 2.0, "rag": 3.0, "vector": 3.0,
    "llm": 3.0, "agent": 3.0, "angular": 5.0, "typescript": 5.0,
    "node": 3.0, "sql": 1.0, "docker": 2.0, "api": 3.0, "genai": 3.0,
    "azure openai": 3.0, "mcp": 1.0, "fastapi": 2.0, "nlp": 3.0,
    "ml": 3.0, "aiml": 3.0,
}

# Generic-SWE stack tokens: high saturation means the role is fundamentally
# a traditional stack (Java/.NET/React/Node/PHP...) even when the JD contains
# AI keywords. Caps AI depth (anti superficial-AI-by-keyword-count).
GENERIC_STACK = {
    "java", ".net", "c#", "asp.net", "spring boot", "spring", "hibernate",
    "react", "reactjs", "angularjs", "redux", "javascript", "jquery",
    "sql server", "mysql", "postgres", "oracle db", "mongodb", "express",
    "nodejs", "php", "laravel", "wordpress", "django", "flask", "ruby",
    "golang", "kotlin", "swift", "vue", "nextjs", "microservices",
    "rest api", "grpc", "kafka", "rabbitmq", "jenkins", "terraform",
    "docker", "kubernetes", "aws", "gcp", "azure", "git", "ci/cd",
}

# Roles that are QA/testing/RPA/automation first — never AI_ENGINEERING no
# matter how many AI keywords the JD contains (fires on title alone).
NON_AI_ENG_TITLE = {"qa", "test automation", "automation test", "testing", "tester", "rpa",
                     "automation engineer", "quality assurance", "sdet",
                     "test engineer", "software test", "qa engineer",
                     "iics", "etl developer", "erpnext", "odoo", "sap",
                     "support engineer", "technical support", "packaged",
                     "saas application", "field service", "customer support"}

# Staffing/agency-style titles with no concrete engineering role.
VAGUE_AI_TITLE = {"ai/ml model development expert", "ai/ml expert", "ai expert",
                  "ai specialist", "model development expert", "data specialist"}

# Generic full-stack/backend/frontend titles: the ROLE is traditional SWE even
# if the JD mentions AI. Caps AI depth unless the title itself is an AI role.
GENERIC_TITLE = {
    "full stack developer", "fullstack developer", "full-stack developer",
    "java developer", "java full stack", "java fullstack", ".net fullstack",
    ".net full stack", "net developer", "react developer", "reactjs developer",
    "node developer", "nodejs developer", "backend developer", "back end developer",
    "backend java", "java backend", "php developer", "laravel developer",
    "software developer", "senior software developer", "full stack engineer",
    "fullstack engineer", "full-stack engineer", "frontend developer",
    "front end developer", "angular developer", "senior software engineer",
    "senior software developer", "software engineer", "application developer",
    "developer", "sde", "swe",
}

# Location fit: candidate preferred Pune/Remote/Hybrid + Bengaluru/Hyderabad/
# Mumbai/Chennai acceptable.
GOOD_LOCATIONS = {
    "pune", "remote", "hybrid", "bengaluru", "bangalore", "hyderabad",
    "mumbai", "chennai", "pan india", "india",
}

FAMILY_BASE = {
    "AI_FDE": 75.0,
    "AI_ENGINEERING": 70.0,
    "FDE": 66.0,
    "AI_ADJACENT": 52.0,
    "GENERIC_ENGINEERING": 38.0,
    "NON_TARGET": 8.0,
}

FDE_BAND_BONUS = {"NONE": 0.0, "LOW": 2.0, "MEDIUM": 5.0, "HIGH": 8.0, "EXCELLENT": 10.0}


def _text(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def _count(text: str, table: set[str]) -> List[str]:
    found = []
    tl = text.lower()
    for kw in table:
        # Word-boundary match: "rag" must not match inside "storage".
        if re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", tl):
            found.append(kw)
    return found


def _parse_experience(exp: str | None) -> tuple[float | None, float | None]:
    """Extract (min_years, max_years) from a free-text experience field."""
    if not exp:
        return None, None
    import re

    m = re.search(r"(\d+)[\s-]*to[\s-]*(\d+)", exp.lower()) or re.search(
        r"(\d+)\s*-\s*(\d+)", exp.lower()
    )
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"(\d+)\+?\s*(?:yrs?|years?)", exp.lower())
    if m:
        return float(m.group(1)), None
    return None, None


def detect_ai_depth(title: str, tags: List[str], description: str) -> tuple[int, List[str]]:
    """Return (depth 0-4, evidence keywords).

    Generic-stack saturation (Java/.NET/React/Node...) caps the depth:
    a "Java Full Stack" JD with a few LLM mentions is depth 1-2, not 4.
    """
    title_l = title.lower()
    tags_l = _text(*tags)
    desc_l = description.lower() if description else ""
    text = f"{title_l} {tags_l} {desc_l}"

    deep = _count(text, DEEP_AI)
    strong = _count(text, STRONG_AI)
    moderate = _count(text, MODERATE_AI)
    generic = _count(text, GENERIC_STACK)

    title_has_ai = any(k in title_l for k in
                       ("llm", "genai", "generative ai", "ai engineer", "ai developer",
                        "ml engineer", "machine learning", "ai/ml", "rag", "agent",
                        "applied ai", "data scientist", "nlp", "ai-"))

    # Anti: QA/test/RPA/SAP/support/packaged titles cap depth regardless of
    # keyword count — "GenAI Tester" is still a tester, "SAP Agentic AI
    # Consultant" is still SAP consulting.
    for kw in NON_AI_ENG_TITLE:
        if kw in title_l:
            return 1, [f"role is {kw}"]
    if any(k in title_l for k in VAGUE_AI_TITLE):
        return 2, ["vague AI-title (staffing/consultancy style)"]

    # Generic-SWE title: role is traditional software even if the JD is AI-heavy.
    is_generic_title = any(k in title_l for k in GENERIC_TITLE) and not title_has_ai

    # Depth 4: title signals model-layer work, OR deep evidence in desc
    if deep and (strong or title_has_ai) and not is_generic_title:
        return 4, deep + strong[:6]
    if len(deep) >= 2 and title_has_ai:
        return 4, deep
    if strong and (title_has_ai or len(strong) >= 2) and not is_generic_title:
        return 3, strong[:8]
    if strong and not is_generic_title:
        return 3, strong[:6]
    if moderate and (title_has_ai or len(moderate) >= 2):
        return 2, moderate[:6]
    if moderate:
        return 2, moderate[:4]

    # Generic-stack dilution: an AI-heavy JD about Java/React is AI-adjacent,
    # not deep AI — unless the title itself is an AI role.
    if (generic and len(generic) >= 3) or is_generic_title:
        if strong or deep:
            return 2, (strong or deep)[:4] + ["generic-stack dilution"]

    if "ai" in title_l or "ai " in text or " ai" in text:
        return 1, ["incidental AI mention"]
    return 0, []


def detect_fde(title: str, description: str) -> tuple[str, List[str], List[str]]:
    """Return (fde_band, strong_evidence, medium_evidence).

    band: NONE | LOW | MEDIUM | HIGH | EXCELLENT
    """
    title_l = title.lower()
    desc_l = description.lower() if description else ""
    text = f"{title_l} {desc_l}"

    title_strong = _count(title_l, FDE_TITLE_STRONG)
    desc_strong = _count(desc_l, FDE_DESC_STRONG)
    desc_medium = _count(desc_l, FDE_DESC_MEDIUM)
    anti = _count(text, FDE_ANTI)

    # Anti-signals cap the band (support/sales roles are never FDE) — check
    # title AND description (e.g. "Customer Engineer" doing hardware field
    # service with schematics).
    anti_text = f"{title_l} {desc_l}"
    if any(k in anti_text for k in FDE_ANTI) or (
        "customer engineer" in title_l and ("schemat" in desc_l or "field service" in desc_l)
    ):
        return "NONE", [], []

    # Hardware/chip-design roles with "implementation" in the title are
    # ASIC/board implementation, not customer-deployment engineering.
    # Also fire on the description: "Associate Engineer" @ Western Digital
    # is NAND/FPGA hardware despite a generic title (Phase F6 finding).
    if any(hw in text for hw in ("asic", "vlsi", "chip", "fpga", "soc", "rtl", "verilog", "hardware", "nand flash")):
        return "NONE", [], []

    evidence = desc_strong + title_strong
    medium = [k for k in desc_medium if k not in evidence]

    # Title alone is a strong FDE signal when the role IS forward-deployed /
    # implementation engineering — description may be missing entirely
    # (routed jobs have no JD text in the cache).
    strong_title_only = any(k in title_l for k in
        ("forward deployed", "forward-deployed", "forward deployment engineer",
         "implementation engineer", "deployment engineer", "customer engineer",
         "solutions engineer", "technical solutions engineer",
         "ai solutions engineer", "implementation consultant"))

    if strong_title_only:
        if len(desc_strong) >= 1 or len(desc_medium) >= 2:
            band = "EXCELLENT"
        else:
            band = "HIGH"
    elif title_strong and len(desc_strong) >= 2:
        band = "EXCELLENT"
    elif title_strong and (len(desc_strong) >= 1 or len(desc_medium) >= 2):
        band = "HIGH"
    elif len(desc_strong) >= 3:
        band = "EXCELLENT"
    elif len(desc_strong) >= 2:
        band = "HIGH"
    elif title_strong or len(desc_strong) >= 1 or len(desc_medium) >= 3:
        band = "MEDIUM"
    elif desc_medium:
        band = "LOW"
    else:
        band = "NONE"
    return band, evidence[:8], medium[:6]


def detect_family(ai_depth: int, fde_band: str, title: str, description: str) -> str:
    """Role family: AI_FDE | AI_ENGINEERING | FDE | AI_ADJACENT | GENERIC_ENGINEERING | NON_TARGET.

    FDE is first-class: a Forward Deployed / Implementation Engineer is FDE
    even with zero AI mention (they deploy software to customers). AI depth
    only upgrades FDE to AI_FDE.
    """
    title_l = title.lower()
    desc_l = (description or "").lower()

    # NON_TARGET first (hardest signal, e.g. team lead / sales / video editor)
    if any(k in title_l for k in NON_TARGET_TITLE) or any(
        k in desc_l for k in NON_TARGET_DESC
    ):
        # Guard: tech-stack presence overrides generic "team lead" in title
        if any(t in title_l for t in ("developer", "engineer", "full stack", "backend", "frontend")):
            pass  # fall through to engineering logic
        else:
            return "NON_TARGET"

    if ai_depth >= 3 and fde_band in ("HIGH", "EXCELLENT"):
        return "AI_FDE"
    if fde_band in ("HIGH", "EXCELLENT"):
        return "FDE"
    if ai_depth >= 3:
        return "AI_ENGINEERING"
    if ai_depth >= 1 or fde_band in ("LOW", "MEDIUM"):
        return "AI_ADJACENT"
    return "GENERIC_ENGINEERING"


def technical_fit(title: str, tags: List[str], description: str) -> tuple[float, List[str]]:
    """Score 0..8 for candidate tech overlap, with matched evidence."""
    text = _text(title, *tags, description)
    matches = [t for t in CANDIDATE_TECH if t in text]
    score = min(8.0, sum(min(2.0, CANDIDATE_TECH[t]) for t in matches) * 1.2)
    return round(score, 1), matches[:10]


def location_fit(location: str | None) -> tuple[float, str]:
    loc = (location or "").lower()
    if not loc:
        return 1.5, "location unknown"
    if any(g in loc for g in GOOD_LOCATIONS):
        return 3.0, f"good location: {loc}"
    return 0.0, f"less preferred location: {loc}"


def experience_fit(title: str, exp_field: str | None) -> tuple[float, str]:
    """0..4; candidate has ~5yrs, seeks 2-8yr roles. Seniority mismatch penalty."""
    exp_min, exp_max = _parse_experience(exp_field)
    title_l = title.lower()
    senior = any(k in title_l for k in ("vp", "head of", "director", "principal", "cto", "fellow", "distinguished"))
    junior = any(k in title_l for k in ("intern", "internship", "fresher", "graduate trainee"))

    if junior:
        return 0.0, "junior role (intern/fresher)"
    if senior and (exp_min or 20) >= 15:
        return 0.5, "too-senior role for candidate"
    if exp_min is not None and exp_min > 10:
        return 1.0, f"requires {exp_min:.0f}+ yrs (candidate 5)"
    if exp_min is not None and exp_min >= 2:
        return 4.0, f"experience fit {exp_min:.0f}-{exp_max or ''} yrs"
    if exp_min is not None:
        return 2.0, f"entry-level-ish ({exp_min:.0f} yrs min)"
    return 3.0, "experience not specified"


def trajectory(family: str, ai_depth: int, fde_band: str) -> tuple[float, str]:
    """0..5: how well the role advances the candidate's AI/FDE trajectory."""
    if family in ("AI_FDE",):
        return 5.0, "direct AI+FDE career target"
    if family == "AI_ENGINEERING" and ai_depth >= 3:
        return 5.0, "direct AI engineering target"
    if family == "FDE":
        return 4.0, "direct FDE target"
    if ai_depth >= 2:
        return 3.0, "advances AI trajectory"
    if ai_depth == 1:
        return 1.5, "incidental AI exposure"
    return 0.0, "does not advance AI/FDE trajectory"


# Penalty tables (subtracted)
NOISE_TITLE = {
    "rpa": 12.0, "test automation": 10.0, "qa ": 8.0, "quality assurance": 8.0,
    "erpnext": 8.0, "odoo": 8.0, "sap": 6.0, "etl": 5.0, "iics": 6.0,
    "support": 6.0, "helpdesk": 6.0, "packaged": 6.0, "saas application": 6.0,
    "presales": 6.0, "sales": 6.0, "customer support": 6.0, "data entry": 8.0,
}


def role_noise_penalty(title: str, description: str) -> tuple[float, List[str]]:
    title_l = title.lower()
    desc_l = (description or "").lower()
    hits = [k for k in NOISE_TITLE if k in title_l or k in desc_l]
    return min(18.0, sum(NOISE_TITLE[k] for k in hits)), hits[:6]


def analyze(job: Dict[str, Any]) -> Dict[str, Any]:
    """Full deterministic analysis of one job record (dict with title/company/
    description[_evidence]/tags/experience/location keys)."""
    title = str(job.get("title", "") or "")
    company = str(job.get("company", "") or "")
    description = str(job.get("description") or job.get("description_evidence") or "")
    tags = job.get("tags") or []
    experience = str(job.get("experience") or "") or None
    location = str(job.get("location") or "")

    ai_depth, ai_evidence = detect_ai_depth(title, tags, description)
    fde_band, fde_evidence, fde_medium = detect_fde(title, description)
    family = detect_family(ai_depth, fde_band, title, description)
    tech, tech_matches = technical_fit(title, tags, description)
    loc, loc_reason = location_fit(location)
    exp, exp_reason = experience_fit(title, experience)
    traj, traj_reason = trajectory(family, ai_depth, fde_band)
    noise, noise_hits = role_noise_penalty(title, description)

    base = FAMILY_BASE[family]
    score = (
        base
        + ai_depth * 4.0
        + FDE_BAND_BONUS[fde_band]
        + tech
        + loc
        + exp
        + traj
        - noise
    )
    score = round(max(0.0, min(100.0, score)), 1)

    return {
        "final_score": score,
        "role_family": family,
        "ai_depth": ai_depth,
        "ai_evidence": ai_evidence,
        "fde_band": fde_band,
        "fde_evidence": fde_evidence,
        "fde_medium_evidence": fde_medium,
        "technical_fit": tech,
        "technical_matches": tech_matches,
        "location_fit": loc,
        "location_reason": loc_reason,
        "experience_fit": exp,
        "experience_reason": exp_reason,
        "trajectory": traj,
        "trajectory_reason": traj_reason,
        "noise_penalty": round(noise, 1),
        "noise_evidence": noise_hits,
        "base": base,
        "components": {
            "base": base,
            "ai_depth": ai_depth * 4.0,
            "fde_band": FDE_BAND_BONUS[fde_band],
            "technical_fit": tech,
            "location_fit": loc,
            "experience_fit": exp,
            "trajectory": traj,
            "noise_penalty": -noise,
        },
        "explanation": (
            f"{family} depth={ai_depth} fde={fde_band} tech={tech}/8 loc={loc:.1f}/3 "
            f"exp={exp:.0f}/4 traj={traj:.0f}/5 noise={noise:.0f} -> {score}"
        ),
        "company": company,
        "title": title,
    }


def score(job: Dict[str, Any]) -> float:
    """Harness contract: higher = better. Deterministic, no LLM."""
    return float(analyze(job)["final_score"])
