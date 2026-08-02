# Opportunity Model — Canonical, Source-Independent

**Version:** 1.0.0
**Status:** Frozen (ADR-008)

---

## 1. Purpose

Every source — manual queue, LinkedIn URL, Wellfound URL, careers page, Greenhouse, Lever, Ashby, Workday, Rippling, recruiter email/message, job URL, PDF, plain text, screenshot, HTML, and future providers — normalizes into **one** `CopilotOpportunity`. The Browser Assistant and Brief engine operate only on this model. ATS specifics live in adapters, never in the model.

## 2. `CopilotOpportunity` — Frozen Contract

```python
@dataclass(frozen=True)
class CopilotOpportunity:
    # identity
    opportunity_id: str            # uuid4
    provider_id: str               # originating provider id, "" if n/a
    provider_job_id: str           # provider-specific job id, "" if n/a
    source: str                    # enum: manual_queue|generic_url|linkedin_url|wellfound_url|
                                   #       careers_url|pasted_text|pdf|greenhouse|lever|ashby|
                                   #       workday|rippling|recruiter_email|recruiter_message|
                                   #       screenshot|html|future
    source_url: str | None
    canonical_url: str | None      # dedup canonical form

    # role
    title: str
    seniority: str | None          # junior|mid|senior|lead|manager|executive|unknown
    employment_type: str | None    # full_time|part_time|contract|internship|unknown
    work_mode: str | None          # remote|hybrid|on_site|unknown
    experience_required: str | None
    role_family: str | None        # derived: applied_ai|forward_deployed|fullstack|other

    # company
    company: str
    company_domain: str | None
    company_size: str | None
    industry: str | None
    ats_type: str | None           # greenhouse|lever|ashby|workday|rippling|generic|none
    careers_url: str | None

    # compensation
    comp_min: float | None
    comp_max: float | None
    currency: str | None
    comp_notes: str | None
    equity: str | None
    bonus: str | None
    market_benchmark: dict | None  # {low, median, high} from knowledge store

    # skills
    required_skills: list[str]
    preferred_skills: list[str]
    tools: list[str]
    domain_knowledge: list[str]

    # location
    city: str | None
    region: str | None
    country: str | None
    remote: bool | None
    relocation_required: bool | None

    # application
    apply_url: str | None
    application_strategy: str       # auto|ats|manual|unsupported  (ADR-004 mapping)
    attachments: list[Attachment]   # [{name, kind: pdf|doc|link, ref}]
    resume_recommendation: ResumeRec | None  # {resume_type, reason, scores, path}

    # content
    description_html: str | None
    description_text: str | None
    raw_ref: str | None             # pointer to original pdf/html/screenshot

    # metadata
    acquired_at: datetime
    fingerprint: str                # sha256 over source-independent identity
    provenance: dict[str, list[str]] # field -> ["parser", "llm", "human", "provider"]
    confidence: dict[str, float]    # field -> 0..1

    # intelligence (brief-derived, denormalized for UI)
    score: float | None
    fit_class: str | None           # strong|consider|weak
    missing_skills: list[str]
    interview_probability: float | None
    effort_estimate: EffortEstimate | None  # {fields, pages, ats_type, auto_fillable_frac, minutes}

    # status
    status_view: str                # reconciled read view (ADR-012)
```

## 3. Field Provenance

Every field carries provenance so trust is explicit:
- `parser` — deterministic extraction (regex, DOM, JSON-LD, PDF).
- `provider` — supplied by the provider/native API.
- `llm` — generated; only used when deterministic failed and confidence ≥ gate.
- `human` — entered/edited by the user (highest trust).
- Derived fields (`role_family`, `fit_class`) are always recomputed, never stored as source facts.

Rule: a Brief never presents an `llm`-provenance fact as `provider` truth. Provenance renders as confidence in the UI (`07_UI.md`).

## 4. Fingerprinting & Dedup

- `fingerprint = sha256(normalize(title) | normalize(company) | normalize(location_city) | req_exp_bucket)[:16]`.
- `oppstore.upsert` dedups on fingerprint; keeps the richer record, merges source refs.
- Cross-source dedup (e.g., same role on LinkedIn and Greenhouse) is resolved at upsert; the richer record wins; duplicate marked `superseded`.

## 5. Source → Adapter → Model Mapping

| Source | Adapter (`ingestion/adapters/`) | Primary extraction |
|---|---|---|
| manual_queue | `manual_queue.py` | Existing `WorkflowQueue`/`ManualActionQueue` rows |
| generic_url | `generic_url.py` | HTTP fetch → JSON-LD/meta/OG → description |
| linkedin_url | `linkedin_url.py` | Fetch → parse (paywall → partial + guidance) |
| wellfound_url | `wellfound_url.py` | Fetch → parse |
| careers_url | `careers_url.py` | Reuse generic_url + careers heuristics |
| pasted_text | `pasted_text.py` | Raw text → structured via rules + optional LLM |
| pdf | `pdf.py` | PDF text extraction → rules + optional LLM |
| screenshot | `screenshot.py` | OCR → text (future) |
| html | `html.py` | HTML → text + meta |
| greenhouse/lever/ashby | ATS adapters (optimization) | Structured feed/page + form model (`04_BROWSER_ASSISTANT.md`) |
| workday/rippling | assist-only wrapper | Guidance mode only (v1) |
| recruiter_email/message | future | Email adapter (backlog, `12_BACKLOG.md`) |

## 6. Rejection Rules

An opportunity is rejected at ingest if: empty title+company; unparseable content after both deterministic and LLM paths; or explicitly user-dismissed (kept in a dismissed registry to prevent re-appearance).

## 7. Status Read View (ADR-012)

`status_view` reconciles the five existing state machines into one display status:
`NEW | REVIEW | APPLYING | SUBMITTED | TRACKING | CLOSED` derived from:
- `JobLifecycleStore.current_state` (canonical),
- `WorkflowQueue` status (when queued),
- `ApplicationLedger.lifecycle_stage` (post-submit funnel).
Rule: canonical lifecycle wins; WorkflowQueue status fills pre-submit; ledger stage fills post-submit. Mapping table lives in `oppstore/status_view.py`.
