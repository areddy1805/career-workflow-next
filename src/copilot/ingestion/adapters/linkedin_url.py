"""LinkedIn URL adapter (CP-1-05).

Fetches a LinkedIn job URL and normalizes it. LinkedIn serves a scraper wall
(HTTP 999 / authwall) to non-browser clients; that path still yields a
*partial* opportunity (title/company from the OpenGraph meta that ships with
the walled page) flagged ``needs_manual_verify`` — guidance, never auto-submit
(ADR-004).
"""

from typing import Any

from src.copilot.constants import ApplicationStrategy, OpportunitySource
from src.copilot.ingestion.adapters.generic_url import (
    GenericUrlAdapter,
    _find_job_posting,
    _resolve_url,
)
from src.copilot.ingestion.extract.html import (
    canonical_url,
    extract_meta,
    html_to_text,
)
from src.copilot.ingestion.extract.jsonld import extract_jsonld
from src.copilot.ingestion.extract.text import normalize_text
from src.copilot.ingestion.models import (
    ParsedOpportunity,
    RawSourceContent,
    UnresolvableError,
)


def _linkedin_title_company(og_title: str | None) -> tuple[str | None, str | None]:
    """Split ``"Engineer at Acme | LinkedIn"`` into (title, company)."""
    if not og_title:
        return None, None
    text = og_title.removesuffix("| LinkedIn").strip()
    if " at " in text:
        title, company = text.rsplit(" at ", 1)
        return title.strip() or None, company.strip() or None
    return text or None, None


class LinkedInUrlAdapter(GenericUrlAdapter):
    """LinkedIn job URL → opportunity; paywalled pages yield partial + flag."""

    source_id = OpportunitySource.LINKEDIN_URL.value

    def supports(self, payload: Any) -> bool:
        return super().supports(payload) and _is_linkedin(payload)

    def fetch(self, payload: Any) -> RawSourceContent:
        url = _resolve_url(payload)
        result = self._fetcher(url)
        paywalled = result.status == 999 or "authwall" in result.text.lower()
        if not paywalled and result.status >= 400:
            raise UnresolvableError(f"HTTP {result.status} for {url}")
        page_meta = extract_meta(result.text)
        return RawSourceContent(
            source=self.source_id,
            raw_text=html_to_text(result.text),
            raw_html=result.text,
            url=result.url,
            meta={
                "meta": page_meta,
                "canonical": canonical_url(result.text, result.url),
                "jsonld": extract_jsonld(result.text),
                "status": result.status,
                "needs_manual_verify": paywalled,
            },
        )

    def parse(self, content: RawSourceContent) -> ParsedOpportunity:
        meta: dict[str, Any] = content.meta
        page_meta: dict[str, str] = meta.get("meta") or {}
        og_title = page_meta.get("og:title")
        title, company = _linkedin_title_company(og_title)
        description = (
            page_meta.get("og:description") or page_meta.get("description")
        )
        canonical = meta.get("canonical") or content.url

        data: dict[str, Any] = {
            "source": self.source_id,
            "title": normalize_text(title) if title else "",
            "company": normalize_text(company) if company else "",
            "source_url": canonical,
            "canonical_url": canonical,
            "application_strategy": ApplicationStrategy.MANUAL.value,
            "description_text": html_to_text(description) if description else None,
        }
        job = _find_job_posting(meta.get("jsonld") or [])
        if job is not None:
            self._apply_jobposting(job, data)

        needs_verify = bool(meta.get("needs_manual_verify"))
        if not data["title"] and not data["company"] and not needs_verify:
            raise UnresolvableError(
                "no title or company after deterministic extraction "
                f"(url={content.url!r})"
            )
        if not data["company"]:
            company_name = page_meta.get("og:site_name")
            if company_name and company_name != "LinkedIn":
                data["company"] = normalize_text(company_name)

        provenance = {field: ["parser"] for field in data}
        return ParsedOpportunity(
            source=self.source_id,
            data=data,
            provenance=provenance,
            meta={"needs_manual_verify": needs_verify},
        )


def _is_linkedin(payload: Any) -> bool:
    url = _resolve_url(payload)
    return url is not None and "linkedin.com" in url
