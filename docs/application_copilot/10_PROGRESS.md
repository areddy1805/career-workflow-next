# Progress

**Last Updated:** 2026-08-02
**Phase:** PH1 in progress (CP-1-01 DONE).

| Phase | Status | % | Last task | Notes |
|---|---|---|---|---|
| PH0 | ✅ Complete (certified) | 100 | CP-0-05 DONE | See PH0 Certification below |
| PH1 | In progress | 46 | CP-1-04 DONE | 6/13 tasks; next: CP-1-12 / CP-1-05 / CP-1-13 |
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
