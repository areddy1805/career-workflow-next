"""Wellfound URL adapter (CP-1-06).

Wellfound job pages expose the same OpenGraph/JSON-LD shape as any generic
job page, so this adapter is the generic URL normalization with a Wellfound
``source_id`` and host gating.
"""

from typing import Any

from src.copilot.constants import OpportunitySource
from src.copilot.ingestion.adapters.generic_url import GenericUrlAdapter, _resolve_url


class WellfoundUrlAdapter(GenericUrlAdapter):
    """Wellfound job URL → opportunity (JSON-LD/OG/description + provenance)."""

    source_id = OpportunitySource.WELLFOUND_URL.value

    def supports(self, payload: Any) -> bool:
        url = _resolve_url(payload)
        return super().supports(payload) and url is not None and "wellfound.com" in url
