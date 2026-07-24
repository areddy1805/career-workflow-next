from dataclasses import dataclass, field
from typing import List
from src.core.job_intelligence.metadata import JobMetadata
from src.core.candidate.profile import CandidateProfile

@dataclass(frozen=True)
class ResumeDelta:
    """
    Release 3.1.5 Phase F: Resume Delta Engine Artifact.
    Provides detailed skill gap analysis, learning effort estimation, and personalized recommendations.
    """
    job_id: str
    strong_matches: List[str] = field(default_factory=list)
    transferable_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    learning_cost: str = "LOW"  # LOW, MEDIUM, HIGH
    career_benefit: str = ""
    recommendation: str = ""

class ResumeDeltaEngine:
    @staticmethod
    def generate_delta(job_id: str, meta: JobMetadata, profile: CandidateProfile) -> ResumeDelta:
        job_techs = set([t.lower() for t in meta.technologies.value + meta.frameworks.value])
        primary_set = set(profile.primary_skills)
        secondary_set = set(profile.secondary_skills)
        emerging_set = set(profile.emerging_skills)
        all_candidate_skills = primary_set | secondary_set | emerging_set

        strong = list(job_techs & primary_set)
        transferable = list(job_techs & (secondary_set | emerging_set))
        missing = list(job_techs - all_candidate_skills)

        if not missing:
            learning_cost = "LOW"
            rec = "Highly Recommended: Immediate fit with zero missing skills."
        elif len(missing) <= 2:
            learning_cost = "MEDIUM"
            rec = f"Recommended: Strong core fit. Learn {missing} on the job."
        else:
            learning_cost = "HIGH"
            rec = f"Caution: Substantial skill gap. Requires learning {missing}."

        has_ai = any(kw in ["llm", "rag", "generative ai", "agent"] for kw in meta.ai_keywords.value)
        career_benefit = "High AI Career Advancement: Accelerates transition into GenAI/LLM Engineering." if has_ai else "Solid Engineering Continuity."

        return ResumeDelta(
            job_id=job_id,
            strong_matches=strong,
            transferable_skills=transferable,
            missing_skills=missing,
            learning_cost=learning_cost,
            career_benefit=career_benefit,
            recommendation=rec
        )
