from dataclasses import dataclass, field
from typing import List, Optional

@dataclass(frozen=True)
class NormalizedJob:
    """
    Immutable, compiler-grade normalized job representation.
    Produced by JobNormalizer prior to metadata extraction.
    """
    raw_job_id: str
    title: str
    company: str
    location: str
    salary_raw: str
    salary_normalized: str
    description: str
    tags: List[str] = field(default_factory=list)
    provider_name: str = "Unknown"
    posted_date: str = ""
