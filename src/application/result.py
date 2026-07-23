from dataclasses import dataclass
from typing import Optional

from src.application.models import RoutingStrategy, ATSType


@dataclass(frozen=True)
class RoutingResult:
    """The result of the routing decision."""

    strategy: RoutingStrategy
    reasoning: str
    ats_type: Optional[ATSType] = None
    url: Optional[str] = None
