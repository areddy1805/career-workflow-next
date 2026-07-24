from dataclasses import dataclass, field
from typing import Dict, List, Tuple

@dataclass(frozen=True)
class TargetProfileOverlay:
    """
    Release 3.1.7 Phase 2: Target Profile Overlay Architecture.
    Interprets the single canonical CandidateIntelligence model through role-specific lenses.
    Does NOT duplicate candidate data; only specifies feature weight multipliers and scoring priorities.
    """
    target_role_id: str  # "applied_ai", "fde", "fullstack"
    display_name: str
    family_weight_modifiers: Dict[str, float] = field(default_factory=dict)
    priority_technologies: Tuple[str, ...] = field(default_factory=tuple)
    priority_keywords: Tuple[str, ...] = field(default_factory=tuple)
    consulting_weight_boost: float = 1.0

class TargetOverlayManager:
    @staticmethod
    def get_applied_ai_overlay() -> TargetProfileOverlay:
        return TargetProfileOverlay(
            target_role_id="applied_ai",
            display_name="Applied AI Engineer",
            family_weight_modifiers={
                "Eligibility": 0.35,
                "Compatibility": 0.30,
                "Preference": 0.25,
                "Market": 0.05,
                "Risk": 0.05
            },
            priority_technologies=("python", "fastapi", "azure", "openai", "rag", "langchain", "langgraph", "vector_db"),
            priority_keywords=("llm", "rag", "generative ai", "agent", "prompt engineering", "ai evaluation", "vector search"),
            consulting_weight_boost=1.0
        )

    @staticmethod
    def get_forward_deployed_overlay() -> TargetProfileOverlay:
        return TargetProfileOverlay(
            target_role_id="fde",
            display_name="Forward Deployed Engineer (FDE)",
            family_weight_modifiers={
                "Eligibility": 0.30,
                "Compatibility": 0.25,
                "Preference": 0.25,
                "Market": 0.15,
                "Risk": 0.05
            },
            priority_technologies=("python", "angular", "typescript", "fastapi", "node", "azure", "docker", "apis"),
            priority_keywords=("customer", "client", "consulting", "solution architecture", "discovery", "prototype", "integration", "stakeholder", "end-to-end"),
            consulting_weight_boost=1.5
        )

    @staticmethod
    def get_fullstack_overlay() -> TargetProfileOverlay:
        return TargetProfileOverlay(
            target_role_id="fullstack",
            display_name="Full Stack Engineer",
            family_weight_modifiers={
                "Eligibility": 0.40,
                "Compatibility": 0.35,
                "Preference": 0.10,
                "Market": 0.10,
                "Risk": 0.05
            },
            priority_technologies=("angular", "typescript", "node", "python", "sql", "postgresql", "docker", "rest_api"),
            priority_keywords=("frontend", "backend", "fullstack", "architecture", "scalability", "ci/cd", "performance"),
            consulting_weight_boost=1.0
        )

    @classmethod
    def get_overlay_by_id(cls, role_id: str) -> TargetProfileOverlay:
        role_id = role_id.lower().strip()
        if role_id in ("fde", "forward_deployed", "forward_deployed_engineer"):
            return cls.get_forward_deployed_overlay()
        elif role_id in ("fullstack", "full_stack", "full_stack_engineer"):
            return cls.get_fullstack_overlay()
        else:
            return cls.get_applied_ai_overlay()
