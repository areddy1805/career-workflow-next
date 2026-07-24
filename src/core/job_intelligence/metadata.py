from dataclasses import dataclass, field
from typing import List, Optional
from src.core.job_intelligence.provenance import ExtractedField

def _def_field(val: any):
    return field(default_factory=lambda: ExtractedField(value=val, normalized_value=val, rule_id="default", rule_version="1.2.0", source_span=(0, 0), confidence=0))

@dataclass
class JobMetadata:
    """
    Structured job metadata containing provenance, rule versions, and confidence scores for every field.
    """
    company: ExtractedField = _def_field("Unknown")
    provider: ExtractedField = _def_field("Unknown")
    seniority: ExtractedField = _def_field("Unknown")
    employment_type: ExtractedField = _def_field("Unknown")
    work_mode: ExtractedField = _def_field("Unknown")
    location: ExtractedField = _def_field([])
    salary_min: ExtractedField = _def_field(None)
    salary_max: ExtractedField = _def_field(None)
    posting_age_days: ExtractedField = _def_field(None)
    
    technologies: ExtractedField = _def_field([])
    frameworks: ExtractedField = _def_field([])
    databases: ExtractedField = _def_field([])
    cloud: ExtractedField = _def_field([])
    ai_keywords: ExtractedField = _def_field([])
    
    rule_version: str = "1.2.0"
    rule_checksum: str = ""
