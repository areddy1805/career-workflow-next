# Progress

**Last Updated:** 2026-08-02
**Phase:** PH1 complete (certified) — see PH1 Certification below.

| Phase | Status | % | Last task | Notes |
|---|---|---|---|---|
| PH0 | ✅ Complete (certified) | 100 | CP-0-05 DONE | See PH0 Certification below |
| PH1 | ✅ Complete (certified) | 100 | CP-1-09 DONE | 13/13; see PH1 Certification below |
| PH2 | Pending | 0 | — | Blocked on PH1 |
| PH3 | Ready (parallel) | 0 | — | First task: CP-3-01 |
| PH4 | Pending | 0 | — | Blocked on PH2/PH3 |
| PH5 | Pending | 0 | — | Blocked on PH3 |
| PH6 | Pending | 0 | — | Blocked on PH1–PH5 |
| PH7 | Pending | 0 | — | Blocked on PH4 |
| PH8 | Pending | 0 | — | Blocked on PH1/PH4/PH7 |
| PH9 | Pending | 0 | — | Blocked on all |

Session convention: every session updates this file + `09_TASK_BOARD.md`. Task statuses: TODO/IN PROGRESS/DONE/BLOCKED/CANCELLED.

## Session Log

### 2026-08-02 — CP-1-09 (PDF adapter) — DONE
- Files: `src/copilot/ingestion/adapters/pdf.py`, `tests/copilot/test_pdf_adapter.py`, `api/routers/copilot.py` (registry); `extract/pdf.py` + `extract/text.py` touched additively.
- `PdfAdapter` (source_id `pdf`): payload `{kind: pdf, data: {path} | {ref}}`; `fetch` → `pdf_to_text` (unreadable/missing → ParseError), carries ref in `RawSourceContent.meta`; `parse` reuses the shared `structure_text` rules (CP-1-08) so PDFs normalize identically to pasted text, plus `raw_ref` = path/ref; provenance `parser`. Scanned/image-only PDF (empty text) → partial opportunity + `meta={needs_manual_verify: True, guidance: "scanned_pdf"}` (mirrors LinkedIn paywall pattern, D-009); text present but no title+company → UnresolvableError (03 §6). No LLM seam on PDF (ponytail: rules + guidance cover the spec; add with the gated LLM infra if needed).
- `pdf_to_text` now preserves line structure via new `extract/text.py` `normalize_lines` (per-line whitespace collapse, keeps `\n`) — the shared rules are line-based and `normalize_text` collapses newlines; `pasted_text.fetch` uses the same helper. Additive; existing pdf extraction tests unchanged.
- Validation: 6 new integration tests (supports incl. ref payload, text-PDF structures like pasted text, ref→raw_ref, scanned→guidance partial, missing file→ParseError, no-identity text→UnresolvableError); full regression 1049 passed; ruff + mypy clean.

### 2026-08-02 — CP-1-08 (Pasted text adapter) — DONE
- Files: `src/copilot/ingestion/adapters/pasted_text.py`, `tests/copilot/{test_pasted_text_adapter.py,fixtures/pasted_structured.txt,fixtures/pasted_prose.txt}`; registered in `api/routers/copilot.py` `get_ingestion_registry()`.
- `PastedTextAdapter` (source_id `pasted_text`): payload `{kind: pasted_text, data: {text} | "text"}`; `fetch` preserves line structure (the rule engine is line-based — `normalize_text` collapses newlines). Shared deterministic engine `structure_text(raw_text) -> (data, provenance)` (every field provenance `parser`): labeled fields (`Job Title:/Title:/Company:/Location:/Salary:/Employment Type:/Work Mode:/Experience:/Required|Preferred Skills:/Tools:` with `:` or `：`), first-line heuristics ("X at Y", "X is hiring a Y", short bare first line), salary ranges ($80k–$120k, $90,000–$120,000, €/£; comp_min/max + currency, USD default), location → city/region/country (+ remote), employment_type (full_time/part_time/contract/internship), work_mode (hybrid > remote > on_site), experience_required ("5+ years"), required/preferred skills + tools via labeled sections plus a whole-text word-boundary keyword catalog (~60 skills/tools) with preferred-section routing, description_text = normalized full text.
- Rejection (03 §6): title+company both missing → UnresolvableError; optional confidence-gated `llm_struct_fn` seam (gate 0.7, disabled default, provenance `llm` appended) identical to generic_url. `structure_text` is the shared rules home for the CP-1-09 PDF adapter.
- Validation: 9 new integration/unit tests (supports incl. string-data payload, structured-header fixture, plain-prose fixture, rejection, LLM seam accepted/not-invoked/low-confidence paths, shared-rules unit); full regression 1043 passed; ruff + mypy clean.
- Also landed (follow-up commit fbd3f8f): `ParsedOpportunity.meta` model change from the D-009 decision (linkedin/careers adapters already constructed/read it; left uncommitted in the working tree).

### 2026-08-02 — CP-1-07 (Careers URL adapter) — DONE
- Files: `src/copilot/ingestion/adapters/careers_url.py`, `tests/copilot/{test_careers_url_adapter.py,fixtures/careers_greenhouse.html}`; registered in `api/routers/copilot.py` `get_ingestion_registry()`.
- Subclasses GenericUrlAdapter (source_id `careers_url`): excludes linkedin.com/wellfound.com hosts; ATS detection (greenhouse/lever/ashby markers in URL + first 20k of HTML) → `ats_type` + `application_strategy=ats`; `directApply` JSON-LD → `apply_url` = canonical; provenance `parser`.
- Validation: 3 new tests (host gating, ATS + apply-link detection, no-marker fallback to manual); full regression 1034 passed; ruff + mypy clean.

### 2026-08-02 — CP-1-13 (Ingest + list + detail API) — DONE
- Files: `api/routers/copilot.py`, `api/schemas.py` (IngestRequest), `tests/copilot/test_ingest_api.py`.
- POST `/api/copilot/ingest` (source + data → IngestionPayload → run_ingestion → CopilotOpportunity(**data, provenance=parsed.provenance) → store.upsert dedup); typed errors as `{ok:false, error:{message, type}}` (UnsupportedSourceError etc.); `guidance` key surfaces parsed.meta flags (e.g. LinkedIn needs_manual_verify). GET `/api/copilot/opportunities` (source/status/q filters + limit/offset pagination via store); GET `/opportunities/{id}` detail, 404 via envelope JSONResponse.
- Tier-1 registry built by `get_ingestion_registry()` (generic_url/linkedin_url/wellfound_url/manual_queue) as a FastAPI dependency — tests override it, so no pipeline files are touched in the test suite.
- Validation: 7 new integration tests (ingest normalize, typed errors, list/detail, dedup, filters + pagination, 404 envelope); full regression 1031 passed; ruff + mypy clean (src/copilot + api/routers/copilot.py).
- Pipeline untouched; additive surface.

### 2026-08-02 — CP-1-05 (LinkedIn URL adapter) — DONE
- Files: `src/copilot/ingestion/adapters/linkedin_url.py`, `tests/copilot/{test_linkedin_url_adapter.py,fixtures/linkedin_paywall.html}`.
- Subclasses GenericUrlAdapter; paywall detection (HTTP 999 or "authwall" in body) → partial opportunity + `ParsedOpportunity.meta["needs_manual_verify"]` guidance flag (never auto-submit, ADR-004); og:title split heuristic ("Engineer at Acme | LinkedIn" → title/company, rsplit on " at "); JSON-LD JobPosting path reused; non-paywall HTTP ≥400 → UnresolvableError; application_strategy manual.
- `ParsedOpportunity` gained optional `meta: dict` (additive; guidance flags home) — recorded in 11_DECISIONS (D-009).
- Validation: 6 new tests (host gating, paywall partial+flag, authwall-on-200, 404 raise, title/company heuristic); full regression 1024 passed; ruff + mypy clean.

### 2026-08-02 — CP-1-06 (Wellfound URL adapter) — DONE
- Files: `src/copilot/ingestion/adapters/wellfound_url.py`, `tests/copilot/{test_wellfound_url_adapter.py,fixtures/wellfound_job.html}`.
- Thin subclass of GenericUrlAdapter: `source_id=wellfound_url` + host gating (`wellfound.com`); reuses JSON-LD/OG deterministic normalization + provenance.
- Validation: 3 new tests (host gating, fixture normalize incl. salary/employment/city, provenance all parser); full regression 1024 passed; ruff + mypy clean.

### 2026-08-02 — CP-1-12 (Status read view) — DONE
- Files: `src/copilot/oppstore/status_view.py`, `tests/copilot/test_status_view.py`.
- Frozen mapping tables (ADR-012, 03 §7) in `reconcile(lifecycle_state, workflow_status, ledger_stage) -> OpportunityStatusView` — pure, no pipeline imports: ledger funnel (post-submit: SUBMITTED/VIEWED/SHORTLISTED/INTERVIEW/OFFER/REJECTED) > canonical JobState (15 values incl. ROUTED_*/QUEUED→REVIEW, PRE_APPLICATION_REJECTED/APPLICATION_FAILED/DEFERRED→CLOSED, ALREADY_APPLIED→TRACKING) > WorkflowStatus (9 values) > NEW. Keys are exact pipeline string values; pipeline stays decoupled (ADR-007).
- `StatusViewResolver` lazily wires real read-only sources (JobLifecycleStore.current_state, WorkflowQueue.get, OpportunityRepository.get_status via ApplicationLedger) via importlib; sources injectable for tests.
- Validation: 42 new tests (full lifecycle/workflow/funnel matrices, precedence, unknown→NEW, resolver with fakes + real JobLifecycleStore(:memory:) + real WorkflowQueue(tmp)); full regression 1016 passed; ruff + mypy clean.
- Additive; resolver not yet called by the store/API (wired at CP-1-13).

### 2026-08-02 — CP-1-04 (Generic URL adapter) — DONE
- Files: `src/copilot/ingestion/adapters/generic_url.py`, `tests/copilot/{test_generic_url_adapter.py,fixtures/generic_job_rich.html,fixtures/generic_job_og_only.html}`.
- `GenericUrlAdapter`: supports `{kind: generic_url, data: {url} | url}` (http(s) only); `fetch` via injectable fetcher (default `fetch_url`), HTTP ≥400 → UnresolvableError; carries meta/title/canonical/jsonld/status in RawSourceContent.meta. `parse` deterministic precedence JSON-LD JobPosting → OG/meta → `<title>`; maps title/company/description (html_to_text-stripped)/canonical/apply_url/salary (minValue/maxValue)/currency/employment_type (FULL_TIME→full_time…)/remote (TELECOMMUTE)/city/region/country/required_skills (comma-split); every field provenance `parser`. Rejection (03 §6): title+company both empty → UnresolvableError; optional confidence-gated `llm_struct_fn` seam (gate 0.7, provenance `llm` appended) — disabled by default, gated LLM infra arrives CP-1-08/CP-2-06.
- Validation: 7 new integration tests (rich JSON-LD fixture, OG-only fallback, HTTP error, empty rejection, LLM seam accepted/low-confidence-rejected paths); full regression 974 passed; ruff + mypy clean.
- Additive; not registered in the default registry yet (CP-1-13 wires adapters).

### 2026-08-02 — CP-1-03 (Manual queue adapter) — DONE
- Files: `src/copilot/ingestion/adapters/{__init__,manual_queue}.py`, `tests/copilot/test_manual_queue_adapter.py`.
- `ManualQueueAdapter` (source_id `manual_queue`): payload `{kind: manual_queue, data: {job_id} | "job_id"}`; resolves rows read-only via `WorkflowQueue.get` (ADR-007; WorkflowQueue lazy-loaded via importlib — keeps pipeline package optional and mypy scoped clean); missing item → UnresolvableError. `parse` maps row → ParsedOpportunity (title/company/source_url/provider_id/provider_job_id/application_strategy=manual/description_text) with every field provenance `provider` (03 §3); output feeds `CopilotOpportunity(**data)` directly (verified by test).
- Not auto-registered (import side-effect free); API layer (CP-1-13) wires it into the registry — rollback: don't register.
- Validation: 6 new integration tests vs seeded queue DB (tmp_path maq.json + wq.db); full regression 967 passed; ruff + mypy clean.
- Read-only on pipeline state; no behavior change.

### 2026-08-02 — CP-1-11 (Opportunity store + dedup + mapping) — DONE
- Files: `src/copilot/oppstore/store.py`, `tests/copilot/test_oppstore_store.py`.
- CRUD on frozen `copilot_opportunities` (§7.8): `upsert` (fingerprint dedup), `get`, `find_by_fingerprint`, `list_opportunities` (source/status/query filters via JSON1 json_extract on title/company, limit/offset), `delete`; mapping: `set_pipeline_job_id`, `find_by_pipeline_job_id` (ADR-012/007 — Copilot-owned writes only).
- Dedup/merge per 03 §4: fingerprint UNIQUE; later sightings merge — richer value wins per field, lists/dicts unioned (order-preserving), provenance unioned per field, confidence merged, original `opportunity_id`/`acquired_at`/`status_view`/`created_at` kept; `updated_at` refreshed.
- Validation: 17 new unit/integration tests (round-trip, dedup single-row, per-field richer-wins, list union, provenance union, tie→existing, source/status/query filters, limit/offset, pipeline-job mapping); full regression 961 passed; ruff + mypy clean.
- No behavior change to pipeline; additive (API wiring arrives CP-1-13).

### 2026-08-02 — CP-1-02 (Text extraction utilities) — DONE
- Files: `src/copilot/ingestion/{fetcher.py, extract/{__init__,text,html,jsonld,pdf}.py}`, `tests/copilot/{test_extraction,test_fetcher}.py`, `requirements.txt` (+beautifulsoup4, +pypdf).
- `extract/text.py` `normalize_text` (NFKC + whitespace collapse; case preserved — fingerprint lowercases separately); `extract/html.py` `html_to_text` (strips script/style/noscript/template/svg), `extract_meta`, `page_title`, `canonical_url` (rel=canonical + urljoin); `extract/jsonld.py` `extract_jsonld` (all ld+json blocks, @graph flattened, malformed skipped); `extract/pdf.py` `pdf_to_text` (pypdf; unreadable/missing → ParseError; bad pages tolerated).
- `fetcher.py` `fetch_url` (httpx, follow-redirects, timeout/UA/robots): timeout → FetchTimeoutError; network error / non-http scheme / robots-disallow → UnresolvableError; non-2xx returned not raised; robots cached per origin, fail-open on unreadable robots; module seams `_get`/`_fetch_robots` for tests.
- Validation: 27 new unit tests (text/html/jsonld/pdf incl. hand-built minimal PDF fixture; fetcher error mapping, scheme rejection, robots allow/cache/fail-open, UA passthrough); full regression 944 passed; ruff + mypy clean.
- No behavior change to pipeline; additive utilities, consumed by adapters CP-1-04+.

### 2026-08-02 — CP-1-10 (CopilotOpportunity model) — DONE
- Files: `src/copilot/oppstore/{__init__,model}.py`, `tests/copilot/test_oppstore.py`.
- Frozen 03 §2 contract implemented: `CopilotOpportunity` frozen dataclass (identity/role/company/compensation/skills/location/application/content/metadata/intelligence/status sections, ~50 fields) + sub-models `Attachment`, `ResumeRec`, `EffortEstimate`. `to_dict()`/`from_dict()` round-trip (JSON-safe, datetimes → ISO-8601, unknown keys ignored, required source/title/company enforced). `compute_fingerprint()` per 03 §4 / §7.2: sha256(normalize(title)|normalize(company)|normalize(city)|exp_bucket)[:16]; computed at construction when absent, preserved when provided.
- Provenance enforced at construction (keys ⊆ fields, values ⊆ Provenance enum); enum-valued fields (source, application_strategy, status_view, seniority, employment_type, work_mode, role_family, ats_type, fit_class) restricted to frozen vocabularies — fail-fast on drift.
- Validation: 40 new unit tests (round-trip incl. all types, fingerprint stability/bucketing, provenance + enum enforcement, immutability, defaults); full regression 917 passed; ruff + mypy clean.
- No behavior change to pipeline; additive (store/API not wired yet).

### 2026-08-02 — CP-1-01 (IngestionAdapter interface + registry + pipeline) — DONE
- Files: `src/copilot/ingestion/{__init__,base,registry,pipeline,models}.py`, `tests/copilot/test_ingestion.py`.
- Frozen §7.1 contract implemented exactly: `IngestionAdapter` ABC (`source_id`, `supports/fetch/parse` with `payload: Any` per contract); `IngestionPayload` envelope (`kind`/`data`/`meta`); `RawSourceContent` (`source/raw_text/raw_html?/attachments?/url?/meta`); `ParsedOpportunity` (normalized dict + field provenance). Registry: module-level `register`/`adapter_for` over `default_registry` + `IngestionRegistry` class (first-match-wins, duplicate `source_id` rejected, same-object re-register idempotent). Pipeline: `run_ingestion` = adapter_for → fetch → parse; typed boundary — raw `TimeoutError` → `FetchTimeoutError`, non-`RawSourceContent`/`ParsedOpportunity` results → `ParseError`.
- Error taxonomy subclasses `CopilotError` (per CP-0-01 docstring): `IngestionError` base + `UnsupportedSourceError`, `ParseError`, `FetchTimeoutError`, `UnresolvableError` (unsupported/parse/timeout/unresolvable per 08 §CP-1-01). Taxonomy lives in `ingestion/models.py` (within the planned 4-file scope).
- Validation: 28 new unit tests (dispatch, first-wins, duplicate register, pipeline happy-path simulation, error mapping, frozen models, taxonomy hierarchy); full regression 877 passed; ruff + mypy clean on new files.
- No behavior change to pipeline; no real adapters registered yet (rollback: additive).
### 2026-08-02 — CP-0-03 (CopilotEvent model + emitter) — DONE
- Files: `src/copilot/events/{__init__,models,emitter}.py`, `tests/copilot/test_events.py`.
- Frozen §7.7 shape; event types validated against the frozen `EventNamespace` set; `trace_id` explicit or generated (uuid hex), propagated by callers (repo convention, cf. `src/inference/events.py`); emit = insert + commit + one log line.
- Validation: 23 new unit tests; full regression 846 passed; ruff + mypy clean.
- No behavior change to pipeline.

### 2026-08-02 — CP-0-04 (Copilot API router + health) — DONE
- Files: `api/routers/copilot.py`, `api/main.py` (router mounted at `/api/copilot`), `tests/copilot/test_api.py`.
- GET `/api/copilot/health` returns `{ok, data:{status, version, subsystems}}` per §7.9; bootstraps copilot.db on first use; CORS via existing global middleware (consistent).
- `api/schemas.py` untouched: no request models needed for health; first models arrive with CP-1-13.
- Validation: 3 new integration tests; full regression 849 passed; ruff/mypy clean on new files (main.py E402s are pre-existing load_dotenv convention).
- No behavior change to pipeline.

### 2026-08-02 — CP-0-05 (Frontend Copilot shell) — DONE
- Files: `frontend/src/App.tsx` (Copilot nav group per 07_UI.md §2, routes, ⌘K entries, health badge), `frontend/src/pages/copilot/*` (8 placeholder pages + shared `CopilotPlaceholder`), `frontend/src/lib/api/copilot.ts`, `frontend/src/lib/hooks.ts` (`useCopilotHealth`), `frontend/src/lib/types/copilot.ts`, `frontend/src/store/copilot.ts` (workspace step skeleton).
- Nav badge on Inbox wired to health (down-subsystem count / '!' when unreachable); real pending count arrives with PH6.
- Validation: `npm run build` (tsc + vite) green; oxlint clean on all touched files; backend regression 849 passed (untouched).
- No behavior change to pipeline.

## PH0 Certification Report

**Phase:** PH0 — Foundations & Interface Freeze (Epic FND) · **Date:** 2026-08-02

### Completed Tasks (5/5)
| ID | Task | Result |
|---|---|---|
| CP-0-01 | Scaffold `src/copilot/` package | DONE |
| CP-0-02 | copilot.db schema + migrations | DONE |
| CP-0-03 | CopilotEvent model + emitter | DONE |
| CP-0-04 | Copilot API router + health | DONE |
| CP-0-05 | Frontend Copilot shell | DONE |

### Acceptance Criteria Verification
- Package imports cleanly; enums match frozen interface §7 (pinned by tests). ✅
- All frozen §7.8 tables created; migrations idempotent; WAL enabled; fresh + migrated paths tested. ✅
- Event emit persists row + logs; trace_id propagates. ✅
- `/api/copilot/health` live with `{ok, data, error}` convention; CORS consistent (global middleware). ✅
- Routes render empty states; nav badge wired to health; ⌘K entries present; `npm run build` passes. ✅

### Tests Executed
- 56 copilot unit/integration tests (package 21, db 9, events 23, api 3).
- Full regression: 849 passed, 0 failed (pipeline untouched).
- ruff clean on all new files (baseline 1352 pre-existing errors untouched); mypy clean (`src/copilot`, `api/routers/copilot.py`); frontend: tsc + vite build green, oxlint clean.

### Coverage
- `src/copilot` + `api/routers/copilot.py`: 99% (275 stmts, 3 missed — one un-hit config-error path).

### Documentation Status
- `10_PROGRESS.md` session log current; `09_TASK_BOARD.md` statuses current; `11_DECISIONS.md` D-008 recorded (10 vs 11 table count). Frozen docs untouched.

### Architecture Compliance
- Frozen interfaces §7.1–7.9 implemented exactly; only Copilot-owned writes to `copilot.db` (ADR-007/010); no pipeline DB access; no scope expansion; D-001 route layout honored.

### Known Issues
- None within PH0 scope. Pre-existing repo lint debt (1352 ruff errors in legacy code) left untouched per no-opportunistic-refactoring rule.

### Risks (next phase)
- PH1 adapter/URL-fetch variance and LLM over-use (mitigation: fixtures + provenance + gated LLM per 08 §4).

### Recommendation
- **GO** — proceed to PH1.

## PH1 Certification Report

**Phase:** PH1 — Ingestion & Opportunity Normalization (Tier 1) · **Date:** 2026-08-02

### Completed Tasks (13/13)
| ID | Task | Result |
|---|---|---|
| CP-1-01 | IngestionAdapter interface + registry + pipeline | DONE |
| CP-1-02 | Text/HTML/JSON-LD/PDF extraction + URL fetcher | DONE |
| CP-1-03 | Manual queue adapter | DONE |
| CP-1-04 | Generic URL adapter | DONE |
| CP-1-05 | LinkedIn URL adapter | DONE |
| CP-1-06 | Wellfound URL adapter | DONE |
| CP-1-07 | Careers URL adapter | DONE |
| CP-1-08 | Pasted text adapter | DONE |
| CP-1-09 | PDF adapter | DONE |
| CP-1-10 | CopilotOpportunity model | DONE |
| CP-1-11 | Opportunity store + dedup + mapping | DONE |
| CP-1-12 | Status read view | DONE |
| CP-1-13 | Ingest/list/detail API | DONE |

### Acceptance Criteria Verification
- 7 Tier-1 adapters normalize via `run_ingestion` → `ParsedOpportunity`: manual_queue, generic_url, linkedin_url, wellfound_url, careers_url, pasted_text, pdf (ADR-004 Tier 1). Fixtures green per adapter (CP-1-03..09). ✅
- Opportunities persisted + deduped: `store.upsert` fingerprint dedup (03 §4), per-field richer-wins merge, list/provenance union, original id/acquired_at kept; API `/ingest` persists through the registry. Dedup matrix green (8 dedicated tests). ✅
- Status view accurate: `reconcile()` (ledger funnel > lifecycle > workflow > NEW) + `StatusViewResolver` wired to real read-only pipeline sources; 42 matrix tests (full lifecycle/workflow/funnel precedence). ✅
- Fixture suite green: all adapter + extraction fixtures pass (256 copilot tests). ✅
- Frozen §7.1 contract implemented exactly; provenance enforced; typed error taxonomy (unsupported/parse/timeout/unresolvable) under `CopilotError`. ✅

### Tests Executed
- 256 copilot unit/integration tests (ingestion 28, extraction/fetcher 27, manual queue 6, generic URL 7, LinkedIn 6, Wellfound 3, careers 3, pasted text 9, PDF 6, model 40, store 17, status view 42, API 10, events 23, package 21, db 9).
- Full regression: **1049 passed, 0 failed** (849 PH0 baseline → 1049; pipeline untouched).
- ruff clean on all new files (baseline 1352 pre-existing errors untouched); mypy clean (`src/copilot`, `api/routers/copilot.py`).

### Coverage
- `src/copilot` + `api/routers/copilot.py`: **96%** (1312 stmts, 46 missed — config error paths and guidance branches).

### Documentation Status
- `10_PROGRESS.md` session log current through CP-1-09; `09_TASK_BOARD.md` 13/13 DONE; `11_DECISIONS.md` D-008 (10 tables) + D-009 (`ParsedOpportunity.meta`) Active. Frozen docs/ADRs untouched.

### Architecture Compliance
- Frozen interfaces §7.1–7.9 implemented exactly; no pipeline imports inside `src/copilot` (importlib lazy loads + string-keyed maps, ADR-007); only Copilot-owned writes to `copilot.db` (ADR-007/010); provenance restricted to frozen `Provenance` values; enums match frozen vocabularies (fail-fast on drift); LLM use gated (confidence ≥ 0.7) and disabled by default.

### Known Issues
- Scanned/image-only PDFs produce empty-title/company partial opportunities by design, flagged `guidance=scanned_pdf` + `needs_manual_verify` (D-009 pattern) — OCR out of scope.
- `pdf_to_text` now preserves line structure (`normalize_lines`) — additive change required by the shared line-based structuring rules; existing tests unchanged.
- `ParsedOpportunity.meta` model change landed as a follow-up commit to CP-1-07 (documented in session log).
- No other known issues within PH1 scope.

### Risks (next phase)
- PH2 (Brief assembler) depends on CP-1-11 store — READY. Gated LLM infrastructure (CP-2-06, confidence-gated) arrives in PH2; pasted_text/generic_url seams already wired. Frontend untouched (PH6).

### Recommendation
- **GO** — proceed to PH2 (CP-2-01 Brief assembler).
