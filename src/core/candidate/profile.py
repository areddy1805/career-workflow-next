import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, Optional

@dataclass(frozen=True)
class CandidateProfile:
    """
    Immutable, versioned, hashed CandidateProfile representing the candidate's complete state,
    career transition goals, skills, deal-breakers, and target tech stack.
    """
    candidate_id: str
    version: str = "1.0.0"
    seniority_level: str = "senior"
    primary_skills: Tuple[str, ...] = ("python", "react", "azure", "docker", "fastapi")
    secondary_skills: Tuple[str, ...] = ("node", "typescript", "postgresql", "kubernetes")
    emerging_skills: Tuple[str, ...] = ("rag", "llm", "langchain", "openai", "agentic_ai")
    experience_years_by_tech: Dict[str, float] = field(default_factory=lambda: {
        "python": 6.0, "react": 4.0, "azure": 3.0, "docker": 4.0, "node": 3.0
    })
    certifications: Tuple[str, ...] = ("Azure AI Engineer Associate", "AWS Certified Developer")
    expected_comp_usd: Optional[float] = 120000.0
    preferred_locations: Tuple[str, ...] = ("bangalore", "remote", "delhi")
    work_mode_preference: Tuple[str, ...] = ("remote", "hybrid")
    target_role_families: Tuple[str, ...] = ("AI Engineer", "Senior Software Engineer", "Full Stack Engineer")
    grow_into_technologies: Tuple[str, ...] = ("rag", "langgraph", "vector_databases", "fine_tuning")
    avoid_technologies: Tuple[str, ...] = ("java_only", "legacy_php", "c_embedded")
    deal_breakers: Tuple[str, ...] = ("onsite_only_outside_city", "night_shift")
    profile_hash: str = ""

    def get_hash(self) -> str:
        payload = {
            "id": self.candidate_id,
            "version": self.version,
            "primary": list(self.primary_skills),
            "emerging": list(self.emerging_skills),
            "exp": self.experience_years_by_tech,
            "targets": list(self.target_role_families)
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def create_default(cls, candidate_id: str = "default_candidate") -> "CandidateProfile":
        inst = cls(candidate_id=candidate_id)
        object.__setattr__(inst, 'profile_hash', inst.get_hash())
        return inst
