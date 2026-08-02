"""Careers URL adapter (CP-1-07).

Company careers pages normalize like any generic job page, plus careers
heuristics: ATS detection (Greenhouse/Lever/Ashby markers in URL + HTML) and
apply-link resolution (``directApply`` JSON-LD → apply_url). Subclasses the
generic adapter; excludes sources with dedicated adapters.
"""

from typing import Any

from src.copilot.constants import ApplicationStrategy, AtsType, OpportunitySource
from src.copilot.ingestion.adapters.generic_url import (
    GenericUrlAdapter,
    _find_job_posting,
    _resolve_url,
)
from src.copilot.ingestion.models import ParsedOpportunity, RawSourceContent

_ATS_MARKERS: dict[str, tuple[str, ...]] = {
    AtsType.GREENHOUSE.value: ("greenhouse.io", "grnh.se", "boards.greenhouse"),
    AtsType.LEVER.value: ("lever.co", "jobs.lever"),
    AtsType.ASHBY.value: ("ashbyhq.com", "jobs.ashby"),
}

_EXCLUDED_HOSTS = ("linkedin.com", "wellfound.com")


class CareersUrlAdapter(GenericUrlAdapter):
    """Careers/job-board URL → opportunity with ATS + apply-link heuristics."""

    source_id = OpportunitySource.CAREERS_URL.value

    def supports(self, payload: Any) -> bool:
        url = _resolve_url(payload)
        if not (super().supports(payload) and url is not None):
            return False
        return not any(host in url for host in _EXCLUDED_HOSTS)

    def parse(self, content: RawSourceContent) -> ParsedOpportunity:
        parsed = super().parse(content)
        data = dict(parsed.data)
        provenance = {
            field: list(sources) for field, sources in parsed.provenance.items()
        }

        ats_type = self._detect_ats(content)
        if ats_type is not None:
            data["ats_type"] = ats_type
            data["application_strategy"] = ApplicationStrategy.ATS.value
        if self._direct_apply(content):
            data["apply_url"] = data.get("canonical_url") or data.get("source_url")
        for field in ("ats_type", "apply_url"):
            if field in data and data[field] is not None:
                provenance[field] = ["parser"]

        return ParsedOpportunity(
            source=self.source_id,
            data=data,
            provenance=provenance,
            meta=parsed.meta,
        )

    def _detect_ats(self, content: RawSourceContent) -> str | None:
        haystack = f"{content.url or ''} {content.raw_html or ''}"[:20000]
        for ats, markers in _ATS_MARKERS.items():
            if any(marker in haystack for marker in markers):
                return ats
        return None

    def _direct_apply(self, content: RawSourceContent) -> bool:
        job = _find_job_posting(content.meta.get("jsonld") or [])
        return bool(job and job.get("directApply") is True)
