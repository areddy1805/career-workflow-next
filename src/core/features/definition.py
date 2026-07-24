from dataclasses import dataclass, field
from typing import List, Optional, Callable, Any

VALID_FAMILIES = {
    "Eligibility", "Compatibility", "Preference", "Market", "Risk", "Quality"
}

VALID_CATEGORIES = {
    "Skills", "Experience", "Location", "Compensation",
    "Company", "Technology", "AI", "Resume", "Market", "Quality"
}

@dataclass(frozen=True)
class FeatureDefinition:
    """
    Catalog schema defining a feature's metadata, family grouping, execution cost, dependencies, and execution bounds.
    """
    id: str
    name: str
    family: str  # Eligibility, Compatibility, Preference, Market, Risk, Quality
    category: str
    version: str
    dependencies: List[str] = field(default_factory=list)
    weight: float = 1.0
    enabled: bool = True
    validator: Optional[Callable[[Any], bool]] = None
    extractor_name: str = ""
    
    # Execution attributes
    estimated_cost: str = "LOW"  # LOW, MEDIUM, HIGH
    execution_time_class: str = "FAST"  # FAST, MEDIUM, SLOW
    cacheable: bool = True
    parallelizable: bool = True

    def __post_init__(self):
        if self.family not in VALID_FAMILIES:
            raise ValueError(f"Invalid family '{self.family}'. Must be one of {VALID_FAMILIES}")
        if self.category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category '{self.category}'. Must be one of {VALID_CATEGORIES}")
