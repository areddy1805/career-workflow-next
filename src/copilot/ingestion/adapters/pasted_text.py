"""Pasted text adapter (CP-1-08).

Deterministic rule-based structuring of a raw job description into a
normalized :class:`ParsedOpportunity`. The rules live in :func:`structure_text`
and are shared with the PDF adapter (CP-1-09) so both sources normalize
identically, every field carrying ``parser`` provenance (03 §3).

Rejection rule (03 §6): if title and company are both missing after
deterministic structuring, the content is unresolvable →
:class:`UnresolvableError`. LLM structing is a confidence-gated fallback wired
via ``llm_struct_fn`` (disabled by default), identical to the generic URL
adapter (gate 0.7).
"""

import re
from typing import Any, Callable

from src.copilot.constants import ApplicationStrategy, OpportunitySource
from src.copilot.ingestion.adapters.generic_url import _first
from src.copilot.ingestion.base import IngestionAdapter
from src.copilot.ingestion.extract.text import normalize_text
from src.copilot.ingestion.models import (
    IngestionPayload,
    ParsedOpportunity,
    RawSourceContent,
    UnresolvableError,
)

_COUNTRIES = {
    "us", "usa", "u.s.", "u.s.a.", "united states", "canada", "uk", "u.k.",
    "united kingdom", "germany", "france", "india", "australia",
    "netherlands", "singapore", "ireland", "spain", "sweden", "brazil",
    "mexico", "japan",
}

# employment keywords: (search key, canonical value) in priority order
_EMPLOYMENT_KEYS: tuple[tuple[str, str], ...] = (
    ("full time", "full_time"),
    ("part time", "part_time"),
    ("contract", "contract"),
    ("internship", "internship"),
)

# keyword catalog: lowercase search key -> (canonical label, skill|tool)
_KEYWORD_CATALOG: dict[str, tuple[str, str]] = {
    "python": ("Python", "skill"),
    "typescript": ("TypeScript", "skill"),
    "javascript": ("JavaScript", "skill"),
    "golang": ("Go", "skill"),
    "java": ("Java", "skill"),
    "c++": ("C++", "skill"),
    "rust": ("Rust", "skill"),
    "ruby": ("Ruby", "skill"),
    "sql": ("SQL", "skill"),
    "postgresql": ("PostgreSQL", "skill"),
    "postgres": ("PostgreSQL", "skill"),
    "mysql": ("MySQL", "skill"),
    "mongodb": ("MongoDB", "skill"),
    "redis": ("Redis", "skill"),
    "kafka": ("Kafka", "skill"),
    "graphql": ("GraphQL", "skill"),
    "react": ("React", "skill"),
    "vue": ("Vue", "skill"),
    "angular": ("Angular", "skill"),
    "node.js": ("Node.js", "skill"),
    "nodejs": ("Node.js", "skill"),
    "django": ("Django", "skill"),
    "flask": ("Flask", "skill"),
    "fastapi": ("FastAPI", "skill"),
    "rails": ("Rails", "skill"),
    "docker": ("Docker", "skill"),
    "kubernetes": ("Kubernetes", "skill"),
    "k8s": ("Kubernetes", "skill"),
    "aws": ("AWS", "skill"),
    "gcp": ("GCP", "skill"),
    "azure": ("Azure", "skill"),
    "terraform": ("Terraform", "skill"),
    "git": ("Git", "skill"),
    "machine learning": ("Machine Learning", "skill"),
    "pytorch": ("PyTorch", "skill"),
    "tensorflow": ("TensorFlow", "skill"),
    "llm": ("LLM", "skill"),
    "nlp": ("NLP", "skill"),
    "spark": ("Spark", "skill"),
    "airflow": ("Airflow", "skill"),
    "snowflake": ("Snowflake", "skill"),
    "databricks": ("Databricks", "skill"),
    "etl": ("ETL", "skill"),
    "microservices": ("Microservices", "skill"),
    "rest apis": ("REST APIs", "skill"),
    "rest api": ("REST APIs", "skill"),
    "ci/cd": ("CI/CD", "skill"),
    "agile": ("Agile", "skill"),
    "jira": ("Jira", "tool"),
    "confluence": ("Confluence", "tool"),
    "slack": ("Slack", "tool"),
    "figma": ("Figma", "tool"),
    "notion": ("Notion", "tool"),
    "github": ("GitHub", "tool"),
    "gitlab": ("GitLab", "tool"),
    "jenkins": ("Jenkins", "tool"),
    "datadog": ("Datadog", "tool"),
    "grafana": ("Grafana", "tool"),
    "sentry": ("Sentry", "tool"),
    "salesforce": ("Salesforce", "tool"),
    "hubspot": ("HubSpot", "tool"),
    "tableau": ("Tableau", "tool"),
    "looker": ("Looker", "tool"),
}

_KEYWORD_RE = re.compile(
    r"\b(" + "|".join(
        re.escape(key)
        for key in sorted(_KEYWORD_CATALOG, key=len, reverse=True)
    ) + r")\b"
)

_FIELD_RE = re.compile(
    r"^(?P<key>job\s*title|company\s*name|employment\s*type|years\s*of\s*"
    r"experience|required\s*skills|preferred\s*skills|nice\s*to\s*have|"
    r"title|position|role|company|location|salary|compensation|job\s*type|"
    r"work\s*mode|experience|tool|tools)\s*[:：]\s*(?P<value>.+)$",
    re.IGNORECASE,
)

_FIELD_BUCKETS = {
    "required skills": "required",
    "preferred skills": "preferred",
    "nice to have": "preferred",
    "tool": "tools",
    "tools": "tools",
}

_TITLE_AT_COMPANY = re.compile(
    r"^(?P<title>.+?)\s+at\s+(?P<company>.+)$"
)
_HIRING = re.compile(
    r"^(?P<company>.+?)\s+(?:is|are)\s+hiring\s+(?:a|an|the)?\s*"
    r"(?P<title>.+?)(?=\s+(?:to|who|that)\b|[.!]?$)",
    re.IGNORECASE,
)

_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP"}

_AMOUNT = r"(?P<cur>[€£$])?\s*(?P<num>\d{2,3}(?:,\d{3})*)\s*(?P<k>[kK])?"
_SALARY_RANGE = re.compile(
    _AMOUNT
    + r"\s*(?:-|–|—|to)\s*"
    + _AMOUNT.replace("cur>", "cur2>").replace("num>", "num2>").replace(
        "k>", "k2>"
    )
)
_SALARY_SINGLE = re.compile(_AMOUNT)

_EXP_RANGE = re.compile(
    r"(\d+)\s*[-–—to]+\s*(\d+)\s*\+?\s*(?:years?|yrs?)(?:\s*of)?"
    r"(?:\s+experience)?\b",
    re.IGNORECASE,
)
_EXP_SINGLE = re.compile(
    r"(?P<num>\d+)\s*(?P<plus>\+)?\s*(?:years?|yrs?)(?:\s*of)?"
    r"(?:\s+experience)?\b",
    re.IGNORECASE,
)

_SECTION_HEADER = re.compile(r"^(?:required|preferred|nice\s+to\s+have)\b", re.I)


def _resolve_text(payload: Any) -> str | None:
    data = getattr(payload, "data", None)
    if isinstance(data, str):
        return data if data.strip() else None
    if isinstance(data, dict):
        text = data.get("text")
        if isinstance(text, str) and text.strip():
            return text
    return None


def _split_items(value: str) -> list[str]:
    """Split a list-ish value into clean canonical items."""
    items: list[str] = []
    for part in re.split(r"\s*(?:,|;|\||·|&|\band\b)\s*", value):
        item = re.sub(r"^[\s\-•*·]+", "", part).strip().strip(".")
        if not item or "." in item:
            continue
        canonical = _canon(item)
        if len(canonical) <= 24:
            items.append(canonical)
    return items


def _canon(item: str) -> str:
    label, _bucket = _KEYWORD_CATALOG.get(item.lower(), ("", ""))
    return label or item


def _dedup(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


def _catalog_hits(
    lines: list[str], preferred_lines: set[int]
) -> tuple[list[str], list[str], list[str]]:
    """Whole-text keyword scan → (required, preferred, tools) canonical labels."""
    required: list[str] = []
    preferred: list[str] = []
    tools: list[str] = []
    seen: set[str] = set()
    for idx, line in enumerate(lines):
        for match in _KEYWORD_RE.finditer(line.lower()):
            key = match.group(1)
            if key in seen:
                continue
            seen.add(key)
            label, bucket = _KEYWORD_CATALOG[key]
            if bucket == "tool":
                tools.append(label)
            elif idx in preferred_lines:
                preferred.append(label)
            else:
                required.append(label)
    return required, preferred, tools


def _parse_location(value: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    low = value.lower()
    if re.search(r"\bremote\b", low):
        data["work_mode"] = "remote"
    paren = re.search(r"\(([^)]+)\)", value)
    if paren and paren.group(1).lower() in _COUNTRIES:
        data["country"] = paren.group(1).strip()
    clean = re.sub(r"\([^)]*\)", "", value)
    parts = [p.strip().strip(".") for p in clean.split(",") if p.strip()]
    if parts and parts[-1].lower() in _COUNTRIES:
        data["country"] = parts.pop()
    if (
        parts
        and data.get("work_mode") == "remote"
        and len(parts) == 1
        and re.search(r"\bremote\b", parts[0].lower())
    ):
        parts = []  # "Remote" alone is not a city
    if len(parts) >= 2:
        data["region"] = parts.pop()
        data["city"] = parts.pop(0)
    elif len(parts) == 1:
        data["city"] = parts[0]
    return data


def _salary_amount(
    match: re.Match[str], prefix: str
) -> tuple[float, str | None]:
    currency = match.group(f"cur{prefix}")
    number = match.group(f"num{prefix}").replace(",", "")
    value = float(number)
    if match.group(f"k{prefix}"):
        value *= 1000
    return value, currency


def _parse_salary(
    text: str, strict: bool = False
) -> tuple[float | None, float | None, str | None]:
    """First salary range/value in ``text`` → (min, max, currency)."""
    range_match = _SALARY_RANGE.search(text)
    if range_match:
        cur1 = range_match.group("cur")
        k1 = range_match.group("k")
        cur2 = range_match.group("cur2")
        k2 = range_match.group("k2")
        if (
            not strict
            or cur1
            or k1
            or "," in range_match.group("num")
            or cur2
            or k2
            or "," in range_match.group("num2")
        ):
            low, currency = _salary_amount(range_match, "")
            high, currency2 = _salary_amount(range_match, "2")
            return low, high, _CURRENCY.get(currency or currency2 or "", "USD")
    if strict:
        # whole-text scan: skip non-currency numbers (e.g. "100+ employees")
        for single_match in _SALARY_SINGLE.finditer(text):
            if single_match.group("cur") or single_match.group("k"):
                value, currency = _salary_amount(single_match, "")
                return value, None, _CURRENCY.get(currency or "", "USD")
    else:
        single_search = _SALARY_SINGLE.search(text)
        if single_search:
            value, currency = _salary_amount(single_search, "")
            return value, None, _CURRENCY.get(currency or "", "USD")
    return None, None, None


def _parse_employment(text: str) -> str | None:
    low = re.sub(r"[\s_-]+", " ", text.lower())
    for key, value in _EMPLOYMENT_KEYS:
        if key in low:
            return value
    return None


def _work_mode_of(text: str) -> str | None:
    low = text.lower()
    if "hybrid" in low:
        return "hybrid"
    if re.search(r"\bremote\b", low):
        return "remote"
    if "on-site" in low or "onsite" in low or "on site" in low:
        return "on_site"
    return None


def _parse_work_mode(labeled: str | None, text: str) -> str | None:
    if labeled:
        return _work_mode_of(labeled)
    return _work_mode_of(text)


def _parse_experience(text: str) -> str | None:
    range_match = _EXP_RANGE.search(text)
    if range_match:
        return f"{range_match.group(1)}-{range_match.group(2)} years"
    single = _EXP_SINGLE.search(text)
    if single:
        plus = "+" if single.group("plus") else ""
        return f"{single.group('num')}{plus} years"
    return None


def structure_text(
    raw_text: str,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Deterministic rule-based structuring shared with the PDF adapter.

    Operates on newline-preserving text (``normalize_text`` collapses
    newlines, so callers — pasted text and PDF text — keep line breaks).
    Returns ``(data, provenance)`` where ``data`` holds the normalized
    opportunity fields and ``provenance`` maps each to ``["parser"]``.
    """
    lines = [" ".join(line.split()) for line in raw_text.splitlines()]

    scalar: dict[str, str] = {}
    section_items: dict[str, list[str]] = {
        "required": [], "preferred": [], "tools": [],
    }
    preferred_lines: set[int] = set()
    active: str | None = None

    for idx, line in enumerate(lines):
        if not line:
            active = None
            continue
        field = _FIELD_RE.match(line)
        if field:
            key = field.group("key").lower().replace("_", " ")
            value = field.group("value").strip()
            bucket = _FIELD_BUCKETS.get(key)
            if bucket:
                active = bucket
                section_items[bucket] += _split_items(value)
                if bucket == "preferred":
                    preferred_lines.add(idx)
            else:
                active = None
                scalar[key] = value
        elif active:
            section_items[active] += _split_items(line)
            if active == "preferred":
                preferred_lines.add(idx)

    title = _first(
        scalar.get("job title"), scalar.get("title"), scalar.get("position")
    )
    company = scalar.get("company")
    first = lines[0] if lines else ""
    if first:
        at = _TITLE_AT_COMPANY.match(first)
        hiring = _HIRING.match(first)
        if at:
            if not title:
                title = at.group("title").strip()
            if not company:
                company = at.group("company").strip()
        elif hiring:
            if not title:
                title = hiring.group("title").strip()
            if not company:
                company = hiring.group("company").strip()
        elif not title and len(first) <= 60 and not re.search(r"[.!?]$", first):
            title = first

    data: dict[str, Any] = {
        "title": normalize_text(title) if title else "",
        "company": normalize_text(company) if company else "",
    }

    if scalar.get("location"):
        data.update(_parse_location(scalar["location"]))

    salary_text = _first(scalar.get("salary"), scalar.get("compensation"))
    if salary_text:
        low, high, currency = _parse_salary(salary_text)
    else:
        low, high, currency = _parse_salary(raw_text, strict=True)
    if low is not None:
        data["comp_min"] = low
        data["comp_max"] = high
        data["currency"] = currency

    employment = _first(
        scalar.get("employment type"), scalar.get("job type")
    )
    parsed_employment = _parse_employment(
        employment if employment else raw_text
    )
    if parsed_employment:
        data["employment_type"] = parsed_employment

    work_mode = _parse_work_mode(
        scalar.get("work mode"), data.get("work_mode") or raw_text
    )
    if work_mode:
        data["work_mode"] = work_mode

    experience = _first(
        scalar.get("experience"), scalar.get("years of experience")
    )
    parsed_experience = _parse_experience(
        experience if experience else raw_text
    )
    if parsed_experience:
        data["experience_required"] = parsed_experience

    required_hits, preferred_hits, tool_hits = _catalog_hits(
        lines, preferred_lines
    )
    required = _dedup(section_items["required"] + required_hits)
    preferred = _dedup(section_items["preferred"] + preferred_hits)
    tools = _dedup(section_items["tools"] + tool_hits)
    if required:
        data["required_skills"] = required
    if preferred:
        data["preferred_skills"] = preferred
    if tools:
        data["tools"] = tools

    data["description_text"] = normalize_text(raw_text)

    provenance = {field: ["parser"] for field in data}
    return data, provenance


class PastedTextAdapter(IngestionAdapter):
    """Raw pasted job description → normalized opportunity (source=pasted_text)."""

    source_id = OpportunitySource.PASTED_TEXT.value

    def __init__(
        self,
        llm_struct_fn: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self._llm_struct_fn = llm_struct_fn

    def supports(self, payload: Any) -> bool:
        return (
            isinstance(payload, IngestionPayload)
            and payload.kind == self.source_id
            and _resolve_text(payload) is not None
        )

    def fetch(self, payload: Any) -> RawSourceContent:
        text = _resolve_text(payload)
        if text is None:
            raise UnresolvableError("pasted text payload has no text")
        # keep line structure (structure_text is line-based); collapse
        # whitespace within each line
        raw_text = "\n".join(
            " ".join(line.split()) for line in text.splitlines()
        )
        return RawSourceContent(source=self.source_id, raw_text=raw_text)

    def parse(self, content: RawSourceContent) -> ParsedOpportunity:
        data, _provenance = structure_text(content.raw_text)
        data = {
            "source": self.source_id,
            "application_strategy": ApplicationStrategy.MANUAL.value,
            **data,
        }
        if not data["title"] and not data["company"]:
            llm_struct = self._llm_struct_fn
            if llm_struct is not None:
                return self._llm_parse(content, data, llm_struct)
            raise UnresolvableError(
                "no title or company after deterministic text structuring"
            )
        provenance = {field: ["parser"] for field in data}
        return ParsedOpportunity(
            source=self.source_id, data=data, provenance=provenance
        )

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
                "unresolvable after deterministic and LLM paths"
            )
        provenance = {field: ["parser"] for field in data}
        for field in structured.get("data", {}):
            if confidence.get(field, 0) >= gate:
                provenance.setdefault(field, []).append("llm")
        return ParsedOpportunity(
            source=self.source_id, data=data, provenance=provenance
        )
