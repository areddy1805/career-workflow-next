import csv
import re
from pathlib import Path

INPUT_FILE = Path("data/raw_jobs.csv")
OUTPUT_FILE = Path("data/scored_jobs.csv")


# ------------------------------------------------------------------
# Strong AI signals
#
# At least one strong signal is normally required for eligibility.
# These indicate that the role is genuinely related to modern AI
# engineering rather than merely mentioning Python or Azure.
# ------------------------------------------------------------------

STRONG_AI_SIGNALS = [
    "generative ai",
    "gen ai",
    "genai",
    "large language model",
    "large language models",
    "llm",
    "llms",
    "retrieval augmented generation",
    "retrieval-augmented generation",
    "rag",
    "agentic ai",
    "ai agent",
    "ai agents",
    "agentic workflow",
    "langchain",
    "langgraph",
    "semantic kernel",
    "azure openai",
    "openai api",
    "prompt engineering",
    "vector database",
    "vector db",
    "vector search",
    "embedding",
    "embeddings",
    "reranking",
    "re-ranking",
]


# ------------------------------------------------------------------
# AI role-title signals
#
# These are checked primarily against the title.
# ------------------------------------------------------------------

AI_TITLE_SIGNALS = [
    "ai engineer",
    "artificial intelligence engineer",
    "gen ai engineer",
    "genai engineer",
    "generative ai engineer",
    "llm engineer",
    "rag engineer",
    "agentic ai engineer",
    "applied ai engineer",
    "ai developer",
    "ai application developer",
    "ai software engineer",
    "ai backend engineer",
    "ai platform engineer",
    "ai solutions engineer",
    "ai solution engineer",
    "prompt engineer",
    "copilot engineer",
    "machine learning engineer",
    "ml engineer",
    "mlops engineer",
    "llmops",
]


# ------------------------------------------------------------------
# Hard exclusions
#
# These should reject roles that are clearly outside our target.
# Keep this list conservative.
# ------------------------------------------------------------------

HARD_EXCLUDE_TITLE_TERMS = [
    "data scientist",
    "data analyst",
    "business analyst",
    "research scientist",
    "research intern",
    "ai intern",
    "machine learning intern",
    "computer vision engineer",
    "computer vision scientist",
    "nlp scientist",
    "ai qa",
    "ai tester",
    "test engineer",
    "qa engineer",
    "sales engineer",
    "pre sales",
    "presales",
    "business development",
    "product manager",
    "project manager",
    "program manager",
]


# ------------------------------------------------------------------
# Research-heavy signals
#
# Do not reject on one occurrence alone.
# Multiple signals indicate a model-training/research-heavy role.
# ------------------------------------------------------------------

RESEARCH_HEAVY_SIGNALS = [
    "phd",
    "publish research",
    "research papers",
    "novel algorithms",
    "model pretraining",
    "pre-training models",
    "train foundation models",
    "training foundation models",
    "reinforcement learning from human feedback",
    "rlhf",
    "cuda kernel",
    "distributed model training",
]


# ------------------------------------------------------------------
# Traditional ML-heavy signals
#
# Used as a warning, not automatic rejection.
# ------------------------------------------------------------------

ML_HEAVY_SIGNALS = [
    "tensorflow",
    "pytorch",
    "scikit-learn",
    "xgboost",
    "feature engineering",
    "model training",
    "statistical modeling",
    "deep learning",
    "neural networks",
]


# ------------------------------------------------------------------
# Application engineering overlap
# ------------------------------------------------------------------

APPLICATION_ENGINEERING_SIGNALS = [
    "python",
    "fastapi",
    "flask",
    "api development",
    "rest api",
    "restful api",
    "backend development",
    "backend engineer",
    "application development",
    "software engineering",
    "microservices",
    "docker",
    "kubernetes",
    "azure",
    "aws",
]


# ------------------------------------------------------------------
# Priority weights
#
# These do NOT decide eligibility.
# They only rank eligible AI jobs.
# ------------------------------------------------------------------

PRIORITY_WEIGHTS = {
    "rag": 10,
    "retrieval augmented generation": 10,
    "retrieval-augmented generation": 10,
    "agentic ai": 10,
    "ai agent": 8,
    "ai agents": 8,
    "langgraph": 8,
    "llm": 8,
    "llms": 8,
    "large language model": 8,
    "generative ai": 8,
    "gen ai": 8,
    "genai": 8,
    "azure openai": 10,
    "azure ai": 8,
    "semantic kernel": 8,
    "langchain": 6,
    "vector search": 6,
    "vector database": 5,
    "vector db": 5,
    "reranking": 5,
    "re-ranking": 5,
    "embedding": 4,
    "embeddings": 4,
    "python": 5,
    "fastapi": 6,
    "api development": 4,
    "rest api": 3,
    "backend development": 4,
    "docker": 3,
    "kubernetes": 2,
    "azure": 3,
}


def normalize(value):
    return re.sub(
        r"\s+",
        " ",
        (value or "").lower(),
    ).strip()


def get_text(row):
    title = normalize(row.get("title", ""))

    full_text = normalize(
        " ".join(
            [
                row.get("title", ""),
                row.get("tags", ""),
                row.get("description", ""),
            ]
        )
    )

    return title, full_text


def find_matches(text, terms):
    return [term for term in terms if term in text]


def weighted_score(text):
    score = 0
    matches = []

    for term, weight in PRIORITY_WEIGHTS.items():
        if term in text:
            score += weight
            matches.append(term)

    return score, matches


# def classify_subtrack(title, text):
#     if any(
#         term in text
#         for term in [
#             "agentic ai",
#             "ai agent",
#             "ai agents",
#             "langgraph",
#             "agentic workflow",
#         ]
#     ):
#         return "AGENTIC"

#     if any(
#         term in text
#         for term in [
#             "retrieval augmented generation",
#             "retrieval-augmented generation",
#             "rag",
#             "vector search",
#             "reranking",
#         ]
#     ):
#         return "RAG"

#     if any(
#         term in text
#         for term in [
#             "llmops",
#             "mlops",
#             "model deployment",
#             "model monitoring",
#             "ai platform",
#         ]
#     ):
#         return "AI_PLATFORM"

#     if any(
#         term in title
#         for term in [
#             "backend",
#             "application developer",
#             "software engineer",
#             "full stack",
#             "fullstack",
#         ]
#     ):
#         return "AI_APPLICATION"

#     if any(
#         term in text
#         for term in [
#             "generative ai",
#             "gen ai",
#             "genai",
#             "llm",
#             "large language model",
#         ]
#     ):
#         return "GENAI_APP"

#     return "OTHER_AI"


def classify_subtrack(title, text):
    """
    Classify the job into one primary AI subtrack.

    Strategy:
    1. Strong title evidence wins.
    2. Otherwise score evidence across the full job text.
    3. Return the highest-scoring subtrack.
    """

    # --------------------------------------------------------------
    # Title-first classification
    # --------------------------------------------------------------

    title_rules = {
        "AGENTIC": [
            "agentic ai",
            "ai agent engineer",
            "agent engineer",
        ],
        "RAG": [
            "rag engineer",
            "retrieval engineer",
            "retrieval augmented generation engineer",
        ],
        "AI_PLATFORM": [
            "ai platform engineer",
            "mlops engineer",
            "llmops engineer",
            "ai infrastructure engineer",
        ],
        "AI_APPLICATION": [
            "ai application developer",
            "ai application engineer",
            "ai software engineer",
            "ai backend engineer",
            "llm full stack engineer",
            "genai full stack",
            "gen ai full stack",
            "backend engineer",
        ],
        "GENAI_APP": [
            "generative ai engineer",
            "gen ai engineer",
            "genai engineer",
            "llm engineer",
            "ai engineer",
            "ai developer",
            "applied ai engineer",
        ],
    }

    for subtrack, terms in title_rules.items():
        if any(term in title for term in terms):
            return subtrack

    # --------------------------------------------------------------
    # Full-text evidence scoring
    # --------------------------------------------------------------

    evidence = {
        "AGENTIC": {
            "agentic ai": 5,
            "ai agents": 4,
            "ai agent": 4,
            "langgraph": 5,
            "agent orchestration": 5,
            "multi-agent": 5,
            "tool calling": 3,
            "agentic workflow": 4,
        },
        "RAG": {
            "retrieval augmented generation": 5,
            "retrieval-augmented generation": 5,
            "rag": 5,
            "vector search": 4,
            "reranking": 4,
            "re-ranking": 4,
            "hybrid search": 4,
            "azure ai search": 4,
        },
        "AI_PLATFORM": {
            "llmops": 6,
            "mlops": 5,
            "model monitoring": 4,
            "model deployment": 3,
            "ai platform": 5,
            "model serving": 4,
            "inference optimization": 4,
        },
        "AI_APPLICATION": {
            "fastapi": 4,
            "api development": 3,
            "backend development": 3,
            "microservices": 3,
            "rest api": 2,
            "application development": 3,
            "full stack": 3,
            "fullstack": 3,
        },
        "GENAI_APP": {
            "generative ai": 4,
            "gen ai": 4,
            "genai": 4,
            "llm": 4,
            "large language model": 4,
            "prompt engineering": 3,
            "langchain": 3,
            "semantic kernel": 3,
            "azure openai": 4,
        },
    }

    scores = {}

    for subtrack, terms in evidence.items():
        score = 0

        for term, weight in terms.items():
            if term in text:
                score += weight

        scores[subtrack] = score

    best_subtrack = max(
        scores,
        key=scores.get,  # type: ignore
    )  # type: ignore

    if scores[best_subtrack] == 0:
        return "OTHER_AI"

    return best_subtrack


def classify_location(location):
    location = normalize(location)

    if "pune" in location:
        return "PUNE"

    if "remote" in location:
        return "REMOTE"

    if location == "india":
        return "INDIA"

    return "OTHER"


def classify_job(row):
    title, text = get_text(row)

    # --------------------------------------------------------------
    # 1. Explicit title exclusions
    # --------------------------------------------------------------

    hard_exclusions = find_matches(
        title,
        HARD_EXCLUDE_TITLE_TERMS,
    )

    if hard_exclusions:
        return {
            "eligible": "NO",
            "priority": "BLOCKED",
            "subtrack": "NONE",
            "score": 0,
            "location_group": classify_location(row.get("location", "")),
            "ai_signals": "",
            "app_signals": "",
            "reason": ("excluded title: " + ", ".join(hard_exclusions)),
        }

    # --------------------------------------------------------------
    # 2. Detect AI evidence
    # --------------------------------------------------------------

    title_ai_matches = find_matches(
        title,
        AI_TITLE_SIGNALS,
    )

    strong_ai_matches = find_matches(
        text,
        STRONG_AI_SIGNALS,
    )

    # A job is considered AI-related if:
    #
    # A) title itself is clearly AI-related
    # OR
    # B) description contains at least one strong modern AI signal
    #
    # This is intentionally permissive.
    # --------------------------------------------------------------

    is_ai_role = bool(title_ai_matches or strong_ai_matches)

    if not is_ai_role:
        return {
            "eligible": "NO",
            "priority": "BLOCKED",
            "subtrack": "NONE",
            "score": 0,
            "location_group": classify_location(row.get("location", "")),
            "ai_signals": "",
            "app_signals": "",
            "reason": "no meaningful AI role signal",
        }

    # --------------------------------------------------------------
    # 3. Research-heavy exclusion
    #
    # Require at least two research-heavy signals.
    # One incidental mention should not block the job.
    # --------------------------------------------------------------

    research_matches = find_matches(
        text,
        RESEARCH_HEAVY_SIGNALS,
    )

    if len(research_matches) >= 2:
        return {
            "eligible": "NO",
            "priority": "BLOCKED",
            "subtrack": "NONE",
            "score": 0,
            "location_group": classify_location(row.get("location", "")),
            "ai_signals": ", ".join(strong_ai_matches),
            "app_signals": "",
            "reason": ("research-heavy role: " + ", ".join(research_matches)),
        }

    # --------------------------------------------------------------
    # 4. Application engineering overlap
    # --------------------------------------------------------------

    app_matches = find_matches(
        text,
        APPLICATION_ENGINEERING_SIGNALS,
    )

    ml_matches = find_matches(
        text,
        ML_HEAVY_SIGNALS,
    )

    # --------------------------------------------------------------
    # 5. Priority score
    # --------------------------------------------------------------

    score, score_matches = weighted_score(text)

    # Title-level AI signal gets a small boost.
    if title_ai_matches:
        score += 10

    # Application engineering overlap gets a boost.
    score += min(len(app_matches) * 2, 10)

    # ML-heavy content is not automatically bad.
    # Penalize only when ML-heavy evidence dominates and application
    # engineering evidence is weak.
    if len(ml_matches) >= 4 and len(app_matches) <= 1:
        score -= 10

    # --------------------------------------------------------------
    # 6. Priority assignment
    #
    # Every job reaching this point remains eligible.
    # --------------------------------------------------------------

    if score >= 55:
        priority = "P1"

    elif score >= 30:
        priority = "P2"

    else:
        priority = "P3"

    return {
        "eligible": "YES",
        "priority": priority,
        "subtrack": classify_subtrack(
            title,
            text,
        ),
        "score": score,
        "location_group": classify_location(row.get("location", "")),
        "ai_signals": ", ".join(strong_ai_matches),
        "app_signals": ", ".join(app_matches),
        "reason": "",
    }


def main():
    with INPUT_FILE.open(
        encoding="utf-8",
        newline="",
    ) as file:
        jobs = list(csv.DictReader(file))

    results = []

    for job in jobs:
        classification = classify_job(job)

        results.append(
            {
                **job,
                **classification,
            }
        )

    results.sort(
        key=lambda row: (
            row["eligible"] == "YES",
            int(row["score"]),
        ),
        reverse=True,
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = list(results[0].keys())

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(results)

    print("=" * 90)
    print("AI JOB ELIGIBILITY SUMMARY")
    print("=" * 90)

    eligible = [row for row in results if row["eligible"] == "YES"]

    blocked = [row for row in results if row["eligible"] == "NO"]

    print(f"\nTotal jobs:    {len(results)}")
    print(f"Eligible AI:   {len(eligible)}")
    print(f"Blocked:       {len(blocked)}")

    priority_counts = {}

    for row in eligible:
        priority = row["priority"]

        priority_counts[priority] = priority_counts.get(priority, 0) + 1

    print("\nPRIORITIES")
    print("-" * 90)

    for priority in ["P1", "P2", "P3"]:
        print(f"{priority}: " f"{priority_counts.get(priority, 0)}")

    subtrack_counts = {}

    for row in eligible:
        subtrack = row["subtrack"]

        subtrack_counts[subtrack] = subtrack_counts.get(subtrack, 0) + 1

    print("\nSUBTRACKS")
    print("-" * 90)

    for subtrack, count in sorted(
        subtrack_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"{subtrack:<20} {count:>4}")

    print("\nTOP 30 ELIGIBLE JOBS")
    print("=" * 90)

    for row in eligible[:30]:
        print(
            f'{row["priority"]:<3} | '
            f'{int(row["score"]):>3} | '
            f'{row["subtrack"]:<15} | '
            f'{row["location_group"]:<6} | '
            f'{row["title"]} | '
            f'{row["company"]}'
        )


if __name__ == "__main__":
    main()
