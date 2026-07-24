import hashlib
import json
from dataclasses import dataclass
from typing import Dict, Any

class EntityIdentityLayer:
    """
    Release 3.2 Phase 7: Entity Identity Layer.
    Generates deterministic Canonical IDs for Job, Company, Skill, and Question entities
    to allow deduplication prior to vector embedding generation.
    """
    @staticmethod
    def generate_job_canonical_id(title: str, company: str, location: str, employment_type: str = "full_time") -> str:
        raw = f"{title.lower().strip()}_{company.lower().strip()}_{location.lower().strip()}_{employment_type.lower().strip()}"
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"job_canon_{h}"

    @staticmethod
    def generate_company_canonical_id(company_name: str) -> str:
        raw = company_name.lower().strip()
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"company_canon_{h}"

    @staticmethod
    def generate_skill_canonical_id(skill_name: str) -> str:
        raw = skill_name.lower().strip()
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"skill_canon_{h}"

    @staticmethod
    def generate_question_canonical_id(question_text: str) -> str:
        raw = question_text.lower().strip()
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"question_canon_{h}"
