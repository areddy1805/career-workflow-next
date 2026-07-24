from dataclasses import dataclass, field
from typing import List, Optional
from src.core.job_intelligence.provenance import ExtractedField

@dataclass
class JobMetadata:
    """
    Structured job metadata containing provenance, rule versions, and confidence scores for every field.
    """
    company: ExtractedField = field(default_factory=lambda: ExtractedField("Unknown", 0, "default", "none"))
    provider: ExtractedField = field(default_factory=lambda: ExtractedField("Unknown", 0, "default", "none"))
    seniority: ExtractedField = field(default_factory=lambda: ExtractedField("Unknown", 0, "default", "none"))
    employment_type: ExtractedField = field(default_factory=lambda: ExtractedField("Unknown", 0, "default", "none"))
    work_mode: ExtractedField = field(default_factory=lambda: ExtractedField("Unknown", 0, "default", "none"))
    location: ExtractedField = field(default_factory=lambda: ExtractedField([], 0, "default", "none"))
    salary_min: ExtractedField = field(default_factory=lambda: ExtractedField(None, 0, "default", "none"))
    salary_max: ExtractedField = field(default_factory=lambda: ExtractedField(None, 0, "default", "none"))
    posting_age_days: ExtractedField = field(default_factory=lambda: ExtractedField(None, 0, "default", "none"))
    
    technologies: ExtractedField = field(default_factory=lambda: ExtractedField([], 0, "default", "none"))
    frameworks: ExtractedField = field(default_factory=lambda: ExtractedField([], 0, "default", "none"))
    databases: ExtractedField = field(default_factory=lambda: ExtractedField([], 0, "default", "none"))
    cloud: ExtractedField = field(default_factory=lambda: ExtractedField([], 0, "default", "none"))
    ai_keywords: ExtractedField = field(default_factory=lambda: ExtractedField([], 0, "default", "none"))
    
    rule_version: str = "1.0.0"
    rule_checksum: str = ""
