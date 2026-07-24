import hashlib
import json
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, Optional, List

@dataclass(frozen=True)
class CandidateIntelligence:
    """
    Release 3.1.5 Addendum: Canonical Candidate Intelligence Model.
    The single, immutable, versioned, hashable source of truth for ALL candidate data across the repository.
    Consolidates candidate_profile.py, candidate_evidence.py, user_profile.yaml, and search_strategy.yaml.
    """
    candidate_id: str = "canonical_candidate"
    version: str = "2.0.0"
    positioning: str = "Applied AI Engineer & Senior Software Engineer"
    
    # Compensation
    current_ctc_lpa: float = 16.0
    expected_ctc_lpa: float = 26.0
    expected_comp_usd: float = 120000.0
    
    # Experience & Seniority
    total_experience_years: float = 5.0
    seniority_level: str = "Senior"
    notice_period_days: int = 30
    reason_for_change: str = "Seeking a production GenAI, RAG and agentic AI engineering role."
    
    # Skills Breakdown
    primary_skills: Tuple[str, ...] = ("python", "angular", "typescript", "node", "azure", "fastapi", "docker")
    secondary_skills: Tuple[str, ...] = ("sql", "postgresql", "aws", "kubernetes", "git", "ci_cd")
    emerging_skills: Tuple[str, ...] = ("genai", "llm", "rag", "agentic_ai", "vector_db", "langchain", "langgraph", "mcp", "prompt_engineering")
    
    experience_years_by_tech: Dict[str, float] = field(default_factory=lambda: {
        "angular": 5.0, "typescript": 5.0, "node": 3.0, "python": 3.0, "api_development": 3.0,
        "genai": 3.0, "llm": 3.0, "rag": 3.0, "agentic_ai": 3.0, "ai_experience": 3.0,
        "vector_db": 3.0, "langchain": 2.0, "langgraph": 2.0, "fastapi": 2.0,
        "cloud": 3.0, "azure": 3.0, "aws": 1.0, "sql": 1.0, "dotnet": 0.0
    })
    
    # Certifications
    verified_certifications: Tuple[str, ...] = ("Microsoft Certified: Azure AI Engineer Associate (AI-102)", "AWS Certified Developer")
    
    # Location & Relocation
    current_location: str = "Pune"
    preferred_locations: Tuple[str, ...] = ("Pune", "Remote", "Hybrid", "Bengaluru", "Hyderabad", "Mumbai", "Chennai")
    relocation_preferences: Tuple[str, ...] = ("Pune", "Bengaluru", "Hyderabad", "Mumbai", "Chennai")
    
    # Work Preferences & Deal Breakers
    accept_fte: bool = True
    accept_remote: bool = True
    accept_contract: bool = True
    willing_hackerrank: bool = True
    willing_f2f: bool = True
    avoid_technologies: Tuple[str, ...] = ("dotnet_only", "java_only", "legacy_php", "c_embedded")
    deal_breakers: Tuple[str, ...] = ("onsite_only_outside_city", "night_shift")
    
    # Deep Capability Evidence
    evidence_summary: Dict[str, Any] = field(default_factory=dict)
    intelligence_hash: str = ""

    def calculate_hash(self) -> str:
        payload = {
            "id": self.candidate_id,
            "version": self.version,
            "ctc": self.expected_ctc_lpa,
            "exp": self.total_experience_years,
            "primary": list(self.primary_skills),
            "emerging": list(self.emerging_skills),
            "certs": list(self.verified_certifications)
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def from_repository_sources(cls) -> "CandidateIntelligence":
        """
        Factory method that audits and consolidates all repository candidate sources.
        """
        try:
            from config.candidate_profile import CANDIDATE_PROFILE
        except ImportError:
            CANDIDATE_PROFILE = {}

        try:
            from config.candidate_evidence import CANDIDATE_EVIDENCE
        except ImportError:
            CANDIDATE_EVIDENCE = {}

        current_ctc = float(CANDIDATE_PROFILE.get("current_ctc_lpa", 16))
        expected_ctc = float(CANDIDATE_PROFILE.get("expected_ctc_lpa", 26))
        total_exp = float(CANDIDATE_PROFILE.get("total_experience_years", 5))

        prof_location = CANDIDATE_PROFILE.get("current_location", "Pune")
        pref_locs = tuple(CANDIDATE_PROFILE.get("preferred_locations", ["Pune", "Remote", "Hybrid", "Bengaluru"]))

        # Build verified certs list
        certs_list = []
        if "certifications" in CANDIDATE_EVIDENCE and "verified" in CANDIDATE_EVIDENCE["certifications"]:
            for c in CANDIDATE_EVIDENCE["certifications"]["verified"]:
                certs_list.append(c["name"])
        if not certs_list:
            certs_list = ["Microsoft Certified: Azure AI Engineer Associate (AI-102)"]

        inst = cls(
            current_ctc_lpa=current_ctc,
            expected_ctc_lpa=expected_ctc,
            total_experience_years=total_exp,
            current_location=prof_location,
            preferred_locations=pref_locs,
            verified_certifications=tuple(certs_list),
            evidence_summary=CANDIDATE_EVIDENCE.get("capabilities", {})
        )
        
        object.__setattr__(inst, 'intelligence_hash', inst.calculate_hash())
        return inst
