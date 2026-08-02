"""Generic URL adapter (CP-1-04).

Fetches any job-page URL and normalizes it deterministically: JSON-LD
``JobPosting`` → meta/OpenGraph → visible text, in that precedence order, with
every field carrying ``parser`` provenance (03 §3).

Rejection rule (03 §6): if title and company are both missing after all
deterministic paths, the content is unresolvable → :class:`UnresolvableError`.

LLM structing is only a fallback on deterministic fail and is confidence-gated;
it is wired via ``llm_struct_fn`` (disabled by default — the gated LLM
infrastructure arrives with CP-1-08/CP-2-06).
"""

from typing import Any, Callable

from src.copilot.constants import ApplicationStrategy, OpportunitySource
from src.copilot.ingestion.base import IngestionAdapter
from src.copilot.ingestion.extract.html import (
    canonical_url,
    extract_meta,
    html_to_text,
    page_title,
)
from src.copilot.ingestion.extract.jsonld import extract_jsonld
from src.copilot.ingestion.extract.text import normalize_text
from src.copilot.ingestion.fetcher import FetchResult, fetch_url
from src.copilot.ingestion.models import (
    IngestionPayload,
    ParsedOpportunity,
    RawSourceContent,
    UnresolvableError,
)

_EMPLOYMENT_MAP = {
    "FULL_TIME": "full_time",
    "FULL-TIME": "full_time",
    "PART_TIME": "part_time",
    "PART-TIME": "part_time",
    "CONTRACTOR": "contract",
    "CONTRACT": "contract",
    "INTERNSHIP": "internship",
    "INTERN": "internship",
}


def _resolve_url(payload: Any) -> str | None:
    data = getattr(payload, "data", None)
    if isinstance(data, str):
        return data if data.startswith(("http://", "https://")) else None
    if isinstance(data, dict):
        url = data.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            return url
    return None


def _first(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _text_of(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, dict):
        text = value.get("description") or value.get("name")
        return normalize_text(str(text)) if text else None
    return normalize_text(str(value))


def _find_job_posting(objects: list[dict[str, Any]]) -> dict[str, Any] | None:
    for obj in objects:
        type_value = obj.get("@type")
        types = type_value if isinstance(type_value, list) else [type_value]
        if "JobPosting" in types:
            return obj
    return None


def _salary(job: dict[str, Any]) -> tuple[float | None, float | None, str | None]:
    base = job.get("baseSalary")
    value = base.get("value") if isinstance(base, dict) else None
    currency = base.get("currency") if isinstance(base, dict) else None
    if isinstance(value, dict):
        currency = value.get("currency") or currency
        low, high = value.get("minValue"), value.get("maxValue")
        if isinstance(low, (int, float)) and isinstance(high, (int, float)):
            return float(low), float(high), currency
        if isinstance(value.get("value"), (int, float)):
            return float(value["value"]), None, currency
    elif isinstance(value, (int, float)):
        return float(value), None, currency
    return None, None, None


class GenericUrlAdapter(IngestionAdapter):
    """Fetch + deterministic normalization for any job-page URL."""

    source_id = OpportunitySource.GENERIC_URL.value

    def __init__(
        self,
        fetcher: Callable[..., FetchResult] = fetch_url,
        llm_struct_fn: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._llm_struct_fn = llm_struct_fn

    def supports(self, payload: Any) -> bool:
        return (
            isinstance(payload, IngestionPayload)
            and payload.kind == self.source_id
            and _resolve_url(payload) is not None
        )

    def fetch(self, payload: Any) -> RawSourceContent:
        url = _resolve_url(payload)
        result = self._fetcher(url)
        if result.status >= 400:
            raise UnresolvableError(f"HTTP {result.status} for {url}")
        meta = extract_meta(result.text)
        return RawSourceContent(
            source=self.source_id,
            raw_text=html_to_text(result.text),
            raw_html=result.text,
            url=result.url,
            meta={
                "meta": meta,
                "page_title": page_title(result.text),
                "canonical": canonical_url(result.text, result.url),
                "jsonld": extract_jsonld(result.text),
                "status": result.status,
                "content_type": result.content_type,
            },
        )

    def parse(self, content: RawSourceContent) -> ParsedOpportunity:
        meta: dict[str, Any] = content.meta
        page_meta: dict[str, str] = meta.get("meta") or {}
        job = _find_job_posting(meta.get("jsonld") or [])

        title = _first(
            job.get("title") if job else None,
            page_meta.get("og:title"),
            page_meta.get("twitter:title"),
            meta.get("page_title"),
        )
        description = _first(
            job.get("description") if job else None,
            page_meta.get("og:description"),
            page_meta.get("twitter:description"),
            page_meta.get("description"),
        )
        company = _first(
            (job.get("hiringOrganization") or {}).get("name") if job else None,
            page_meta.get("og:site_name"),
        )
        canonical = _first(meta.get("canonical"), content.url)
        job_url = job.get("url") if job else None

        data: dict[str, Any] = {
            "source": self.source_id,
            "title": normalize_text(str(title)) if title else "",
            "company": normalize_text(str(company)) if company else "",
            "source_url": canonical,
            "canonical_url": canonical,
            "apply_url": job_url if job_url and job_url != canonical else None,
            "application_strategy": ApplicationStrategy.MANUAL.value,
            "description_text": html_to_text(description) if description else None,
        }
        if job is not None:
            self._apply_jobposting(job, data)

        if not data["title"] and not data["company"]:
            llm_struct = self._llm_struct_fn
            if llm_struct is not None:
                return self._llm_parse(content, data, llm_struct)
            raise UnresolvableError(
                "no title or company after deterministic extraction "
                f"(url={content.url!r})"
            )

        provenance = {field: ["parser"] for field in data}
        return ParsedOpportunity(
            source=self.source_id, data=data, provenance=provenance
        )

    def _apply_jobposting(self, job: dict[str, Any], data: dict[str, Any]) -> None:
        if not data["company"]:
            org = job.get("hiringOrganization") or {}
            company_name = _first(org.get("name"), data["company"])
            data["company"] = normalize_text(str(company_name))
        address = ((job.get("jobLocation") or {}).get("address") or {})
        data["city"] = _text_of(address.get("addressLocality"))
        data["region"] = _text_of(address.get("addressRegion"))
        data["country"] = _text_of(address.get("addressCountry"))
        if str(job.get("jobLocationType") or "").upper() == "TELECOMMUTE":
            data["remote"] = True
        employment = str(job.get("employmentType") or "").upper()
        mapped = _EMPLOYMENT_MAP.get(employment)
        if mapped:
            data["employment_type"] = mapped
        low, high, currency = _salary(job)
        data["comp_min"] = low
        data["comp_max"] = high
        data["currency"] = currency
        skills = job.get("skills")
        if isinstance(skills, str) and skills.strip():
            data["required_skills"] = [
                normalize_text(skill) for skill in skills.split(",") if skill.strip()
            ]
        if not data["description_text"]:
            data["description_text"] = html_to_text(job.get("description"))

    def _llm_parse(
        self,
        content: RawSourceContent,
        data: dict[str, Any],
        llm_struct: Callable[..., dict[str, Any]],
    ) -> ParsedOpportunity:
        structured = llm_struct(raw_text=content.raw_text, hint=data)
        confidence = structured.get("confidence", {})
        gate = 0.7  # confidence gate: only accept confident fields
        for field, value in structured.get("data", {}).items():
            if value not in (None, "") and confidence.get(field, 0) >= gate:
                data[field] = value
        if not data["title"] and not data["company"]:
            raise UnresolvableError(
                "unresolvable after deterministic and LLM paths "
                f"(url={content.url!r})"
            )
        provenance = {field: ["parser"] for field in data}
        for field in structured.get("data", {}):
            if confidence.get(field, 0) >= gate:
                provenance.setdefault(field, []).append("llm")
        return ParsedOpportunity(
            source=self.source_id, data=data, provenance=provenance
        )
