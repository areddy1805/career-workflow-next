# Progress

**Last Updated:** 2026-08-02
**Phase:** PH2 complete (certified) — PH4 in progress; see certification reports below.

| Phase | Status | % | Last task | Notes |
|---|---|---|---|---|
| PH0 | ✅ Complete (certified) | 100 | CP-0-05 DONE | See PH0 Certification below |
| PH1 | ✅ Complete (certified) | 100 | CP-1-09 DONE | 13/13; see PH1 Certification below |
| PH2 | ✅ Complete (certified) | 100 | CP-2-07 DONE | 7/7; see PH2 Certification below |
| PH3 | In Progress | 15 | CP-3-01 DONE | CP-3-02 next (blocks CP-4-03) |
| PH4 | In Progress | 10 | CP-4-02 DONE | CP-4-03 next |
| PH5 | Pending | 0 | — | Blocked on PH3 |
| PH6 | Pending | 0 | — | Blocked on PH1–PH5 |
| PH7 | Pending | 0 | — | Blocked on PH4 |
| PH8 | Pending | 0 | — | Blocked on PH1/PH4/PH7 |
| PH9 | Pending | 0 | — | Blocked on all |

Session convention: every session updates this file + `09_TASK_BOARD.md`. Task statuses: TODO/IN PROGRESS/DONE/BLOCKED/CANCELLED.

## Session Log

### 2026-08-02 — CP-3-01 (Question fingerprinting + canonical labels) — DONE
- Files: `src/copilot/answerbank/{fingerprint,canonical}.py`, `tests/copilot/test_answerbank_fingerprint.py`.
- `fingerprint.py`: frozen 06 §4 `Question{label, options, kind}` (+`from_dict`); `normalize_label` (lowercase, punctuation → space, collapse); `fingerprint(question) = sha256(normalized_label | normalized_options_keys | kind)[:16]` — stable, 16-hex, sensitive to options/kind/label. `normalized_options_keys` = option labels normalized + `|`-joined.
- `canonical.py`: `CANONICAL_SLOTS` registry (06 §2 taxonomy: identity.*, profile.*, experience.* per-tech years, summary.*, capability.*, preference.*) — ordered most-specific-first, first word-boundary match wins (D-012); `canonical_label(text)` → slot or None (unknown phrasings fall through to normal resolution, never guessed; registry grows from real questionnaires per 06 §4).
- Note: CP-3-01/3-02 sit on the PH4 critical path — 08 §PH4 lists CP-4-03 as Dep CP-3-02 — so PH3 tasks 1–2 were pulled ahead of CP-4-03 per the frozen dependency table.
- Validation: 13 new unit tests (normalization, stability + hex, variant-phrasing equivalence, options/kind/label sensitivity, from_dict, synonym table 9 slots × variant phrasings, most-specific-first shadowing, unknown → None, registry sanity); full regression 1198 passed; ruff + mypy clean.

### 2026-08-02 — CP-4-02 (Session persistence + events) — DONE
- Files: `src/copilot/session/{store,events}.py`, `tests/copilot/test_session_store.py`.
- `events.py`: `copilot_session_events` log (§7.8) — `SessionEvent{session_id, seq, event_type, occurred_at, payload}` with **per-session** auto-increment seq (`MAX(seq)+1`); `append_session_event` writes the log row AND emits the namespaced CopilotEvent `ses.<event.lower()>` (CP-0-03) so per-session log + global audit trail stay in sync; `list_session_events` ordered by seq.
- `store.py`: `copilot_sessions` CRUD — `save_session` (upsert, full §7.8 row incl. brief/answers snapshot JSON + outcome cols), `load_session` (row → Session with state enum), `create_session` (machine creation path `transition(None, SESSION_CREATED)` → BRIEF_READY; records SESSION_CREATED log row + `ses.session_created`), `advance_session` (load → `Session.advance` via machine → save → log + emit `ses.*` with `{from, to, **payload}`; raises `InvalidTransitionError` before ANY write on invalid pairs; missing session → `CopilotError`).
- Validation: 10 new integration tests (create persists + events, full-field round-trip, full chain ANSWERS_CONFIRMED→…→HUMAN_SUBMIT with submitted_at + OUTCOME_RECORDED self-loop with outcome payload, invalid transition persists nothing, missing session, abort, per-session seq isolation, upsert, standalone append); full regression 1185 passed; ruff + mypy clean.

### 2026-08-02 — CP-4-01 (Session state machine) — DONE
- Files: `src/copilot/session/{state_machine,models}.py`, `tests/copilot/test_session_state_machine.py`.
- `state_machine.py`: frozen §7.5 states/events via `TRANSITIONS` matrix (event → {from → to}); `transition(state, event)` validates and raises `InvalidTransitionError` (a `CopilotError`, API-catchable); `allowed_events(state)` (frozen declaration order, for UI/409 messages); `is_terminal` (SUBMITTED/ABORTED); `INITIAL_STATE = BRIEF_READY`; `SESSION_CREATED` valid only from the `None` sentinel (creation).
- D-011 reading of the frozen event list: `FORM_FILLING`/`CHECKPOINT_PENDING` self-loop (progress events, no state advance); `HUMAN_SUBMIT` is the trigger `FORM_FILLED → SUBMITTED` (ADR-002 gesture) and `SUBMITTED` is the CopilotEvent emitted on that transition — never a trigger (keeps the gesture requirement unbypassable at the machine level); `OUTCOME_RECORDED` self-loops on `SUBMITTED` (outcome is data, schema §7.8 `outcome`/`outcome_at`).
- `models.py`: `Session` aggregate mirroring the frozen §7.8 `copilot_sessions` row; `to_dict`/`from_dict` round-trip (string state coerced, unknown keys ignored); pure `advance(event)` applies a validated transition and stamps `updated_at` (+`submitted_at` on SUBMITTED).
- Validation: 30 new unit tests — exhaustive (state × event) matrix green (every valid pair transitions, every invalid pair raises), explicit invalid spots, SESSION_CREATED only from INITIAL, SUBMITTED-never-trigger (D-011), error message lists allowed events, per-state `allowed_events`, terminal states, Session round-trip/coercion/advance/submitted_at; full regression 1175 passed; ruff + mypy clean.

### 2026-08-02 — CP-2-07 (Brief persistence + cache + endpoints) — DONE
- Files: `src/copilot/brief/{store,api}.py`, `tests/copilot/{test_brief_store,test_brief_api}.py`; `brief/models.py` (+`ApplicationBrief.from_dict` round-trip) + `api/routers/copilot.py` (includes brief router).
- `store.py`: frozen `copilot_briefs` (§7.8) upsert/load/delete (brief_json, generated_at, model_used deterministic|llm, sections_version="1"); `build_brief` = full deterministic assembly (assembler + salary + effort + probability + questions + gated prose) → persist + in-memory cache + `brief.generated` event (CP-0-03); `get_brief` implements the 05 §3 pipeline (cache hit → DB → cold build); `invalidate_brief` drops cache + DB.
- `api.py`: GET `/api/copilot/opportunities/{id}/brief` (build-on-demand, 404 envelope for missing opportunity, brief-build 500 guard) — included into the copilot router; `{ok, data, error}` envelope per CP-1-13.
- Validation: 15 new tests (to_dict/from_dict round-trip incl. all sections, upsert, metadata, cache hit/DB-load/cold-build paths, invalidate + rebuild, brief.generated event, API build-on-demand/cached/missing-404/low-fit-skip); full regression 1145 passed; ruff + mypy clean.

### 2026-08-02 — CP-2-06 (LLM prose augmentation, gated) — DONE
- Files: `src/copilot/brief/llm.py`, `tests/copilot/test_llm.py`; `brief/models.py` + `brief/assembler.py` extended additively.
- `prose_summary(opportunity, *, llm_call, enabled, cache, max_input_chars=4000, max_output_chars=600)` → summary or None. Gated: `BRIEF_LLM_ENABLED = False` feature flag (08 DoD: off by default; rollback = leave off), injectable `llm_call` provider seam (caller pins temp 0, 05 §3 step 5), one pass cached in-memory per opportunity (durable brief cache arrives CP-2-07), input truncated + output capped (budget-respected), empty results → no augmentation.
- `ApplicationBrief` gained `prose_summary: str | None` (+ to_dict); `assemble_brief(prose_summary=...)` fills the section with **section source `llm`** (05 §5 — the one non-deterministic section; renders with the distinct llm marker).
- Validation: 9 new unit tests (flag off by default, disabled no-call, one-pass + cache hit, no provider, empty result, input truncation, output cap, brief llm-source wiring); full regression 1130 passed; ruff + mypy clean.

### 2026-08-02 — CP-2-05 (Likely questions service) — DONE
- Files: `src/copilot/brief/questions.py`, `tests/copilot/test_questions.py`; `brief/models.py` + `brief/assembler.py` extended additively.
- `likely_questions(opportunity, *, corpus, limit=5)` → top-N `LikelyQuestion{question, answer}` (05 §2 #8). Ranking: ATS-applicable entries (empty `ats_types` = any ATS) score 1.0, +0.5 per description-keyword word-boundary hit; zero-scoring excluded; stable tie order. `corpus` injectable — Answer Bank (CP-3-02) is the production source; small built-in starter corpus (3 generic + greenhouse/lever/workday) keeps the section deterministic-first until then.
- `ApplicationBrief` gained `questions: list[LikelyQuestion] | None` (+ to_dict); `assemble_brief(questions=...)` fills section 8 (source deterministic).
- Validation: 10 new unit tests (ATS selection/exclusion, keyword boost ranking, limit, zero-score exclusion, generic-any-ATS, empty corpus, no-description fallback, brief section/to_dict); full regression 1121 passed; ruff + mypy clean.

### 2026-08-02 — CP-2-04 (Interview probability v1) — DONE
- Files: `src/copilot/brief/probability.py`, `tests/copilot/test_probability.py`; `brief/models.py` + `brief/assembler.py` extended additively.
- `interview_probability(opportunity, *, priors, resume_profile)` → float. Bucket priors from the learning store (05 §2 #5): key = `(role_family, resume_profile, score_band)` with score bands low < 50 / mid 50–79 / high ≥ 80 (unknown band when no score); `priors` injected read-only (CP-7-01 seam — table does not exist yet); cold start / bucket miss → default **0.12**; no LLM. `resume_profile` overrides the profile inferred from the opportunity's resume recommendation (lowercased type, else "generic").
- `ApplicationBrief` gained `interview_probability: float | None` (+ to_dict); `assemble_brief(interview_probability=...)` fills section 5 (source deterministic). Does not gate the verdict.
- Validation: 11 new unit tests (cold default, bucket miss, prior hit, rounding, all four score bands, unknown band, role-family default, profile inference + override, brief section/to_dict); full regression 1111 passed; ruff + mypy clean. Calibration vs actual outcomes is a success metric (16_SUCCESS_METRICS) tracked once outcomes accumulate.

### 2026-08-02 — CP-2-03 (Effort estimator) — DONE
- Files: `src/copilot/brief/effort.py`, `tests/copilot/test_effort.py`; `brief/models.py` + `brief/assembler.py` extended additively.
- `estimate_effort(opportunity, *, fields, pages, auto_fillable_frac)` → `EffortEstimate` (03 §2 shape) per frozen 05 §6: ATS field-count heuristics (greenhouse 12, lever 10, ashby 9, workday 25 / rippling 20 — high + guidance mode; generic 15 until v2 description-length inference); `fields`/`pages` override for measured forms; `estimated_minutes = fields*0.4 + pages*1.2` floored, capped at 30, labeled "assisted estimate" by the caller; `auto_fillable_frac` carried for context (frozen formula does not discount auto-fill).
- `ApplicationBrief` gained `effort: EffortEstimate | None` (+ to_dict with `estimated_minutes`); `assemble_brief(effort=...)` fills section 7 (source deterministic). Effort does not gate the verdict.
- Validation: 11 new unit tests (per-ATS minutes, generic default, explicit overrides, pages, cap, frac passthrough, brief section + to_dict); full regression 1100 passed; ruff + mypy clean.

### 2026-08-02 — CP-2-02 (Salary assessment service) — DONE
- Files: `src/copilot/brief/salary.py`, `tests/copilot/test_salary.py`; `brief/models.py` + `brief/assembler.py` extended additively.
- `assess_salary(opportunity, *, target, market_median)` → `SalaryAssessment{status: within|above|below|unknown, reason, job_min/max, currency, target_min/max, market_median}` (05 §2 #6). Classification: job_max < target_min → below; job_min > target_max → above; overlap or boundary-equal → within; single bound treated as point value; unknown when job has no comp range or profile has no target. `market_median` (knowledge store, CP-7-01) carried for context only.
- `ApplicationBrief` gained `salary: SalaryAssessment | None` (+ to_dict); `assemble_brief(salary=...)` fills section 6 (source deterministic) and drives the 05 §4 verdict gate — below-band → CONSIDER (existing `salary_below_band` param still honored when salary absent).
- Validation: 15 new unit tests (full classification matrix incl. boundary-equal, single-bound, unknown paths, market passthrough; brief section + consider gate + to_dict); full regression 1089 passed; ruff + mypy clean.

### 2026-08-02 — CP-2-01 (Brief assembler) — DONE
- Files: `src/copilot/brief/{__init__,models,assembler}.py`, `tests/copilot/test_brief_assembler.py`.
- Frozen `05_APPLICATION_BRIEF.md` (ADR-013) §2 shape: `ApplicationBrief` (opportunity_id, verdict, verdict_reason, fit, missing_skills, resume_recommendation, strategy, risk_flags, section_sources, provenance_summary, confidence) + sub-models `Verdict`/`LearningCost` enums, `MissingSkill`, `FitBreakdown`, `ResumeRecommendation`, `RiskFlags` (with `blocks_apply` per §4 blocker set), `StrategySection`; `to_dict()` JSON-safe. Later sections (salary/effort/probability/questions) arrive additively with CP-2-02..05.
- `assemble_brief(opportunity, *, components, learning_costs, resume_recommendation, risk_flags, quality_threshold=68, salary_below_band=False)`: deterministic aggregation — fit score (opportunity.score, default 0), components injectable (DecisionExplanation seam, 05 §2 #2), missing skills (default cost med, injectable per-skill), resume rec (injected > opportunity.resume_recommendation > generic fallback), strategy reason map (ADR-004), deterministic risk flags (suspicious = missing title/company/description; low-confidence provenance = llm provenance on identity fields or field confidence < 0.7), all section sources `deterministic`, confidence = mean of input field confidences (cap 0.5 when low-confidence), provenance summary from the opportunity.
- Verdict rule (05 §4) exact: skip on deal-breaker/avoid-technology/expired/duplicate or fit < threshold; apply on fit ≥ threshold + no blocker + salary not below band; consider = salary gate (CP-2-02 seam, defaults unblocked). No pipeline imports (injectable-sources pattern like StatusViewResolver).
- Validation: 25 new unit tests (verdict matrix: fit bands, threshold edge 68/67, all four blockers, consider-via-salary, non-blocking flags, custom threshold; fit/strategy; missing skills default+injected costs; resume rec precedence; risk detection; confidence; to_dict; frozen dataclass); full regression 1074 passed; ruff + mypy clean.

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

## PH2 Certification Report

**Phase:** PH2 — Application Brief · **Date:** 2026-08-02

### Completed Tasks (7/7)
| ID | Task | Result |
|---|---|---|
| CP-2-01 | Brief assembler + ApplicationBrief model | DONE |
| CP-2-02 | Salary assessment service | DONE |
| CP-2-03 | Effort estimator | DONE |
| CP-2-04 | Interview probability v1 | DONE |
| CP-2-05 | Likely questions service | DONE |
| CP-2-06 | LLM prose augmentation (gated) | DONE |
| CP-2-07 | Brief persistence + cache + endpoints | DONE |

### Acceptance Criteria Verification
- Every opportunity gets a **complete, cached Brief** (PH2 exit gate): GET `/api/copilot/opportunities/{id}/brief` builds all deterministic sections (verdict, fit breakdown, missing skills, resume rec, strategy, risk, salary, effort, probability, questions) + gated prose; in-memory cache hit (<100ms, dict lookup) → DB (`copilot_briefs`) → cold deterministic build (<5s, pure rules + sqlite). ✅
- Verdict rule correct (05 §4): verdict matrix green (fit bands, threshold 68 edge, all four blockers, consider-via-salary, custom threshold). ✅
- Salary classification correct for fixture ranges (within/above/below/unknown incl. single-bound and boundary-equal). ✅
- Effort frozen heuristics (05 §6): per-ATS field counts → `fields*0.4 + pages*1.2`, floored, capped; Workday/Rippling high + guidance. ✅
- Interview probability: priors read from injectable learning-store table; **0.12 cold default**; no LLM. ✅
- LLM augmentation: gated (flag OFF by default), one cached pass, temp 0, input/output budgets, provenance `llm`. ✅
- Build cold <5s / cached <100ms by construction (deterministic + in-memory); invalidate works (cache + DB drop, rebuild verified). ✅

### Tests Executed
- 96 new copilot tests across CP-2-01..07 (assembler 25, salary 15, effort 11, probability 11, questions 10, llm 9, store 11, brief API 4).
- Full regression: **1145 passed, 0 failed** (1049 PH1 → 1145; pipeline untouched). Copilot suite now 352 tests.
- ruff clean on all new files; mypy clean (`src/copilot`, `api/routers/copilot.py`).

### Coverage
- `src/copilot` + `api/routers/copilot.py`: **97%** (1653 stmts, 47 missed — config/error-guard branches).

### Documentation Status
- `10_PROGRESS.md` session log current through CP-2-07; `09_TASK_BOARD.md` 7/7 DONE; `11_DECISIONS.md` D-008/D-009 Active (no new decisions required — sections followed 05 §2 exactly). Frozen docs/ADRs untouched.

### Architecture Compliance
- Frozen 05 §2–§6 implemented exactly (12-section shape, §4 verdict, §6 effort heuristics, §5 source/confidence); no pipeline imports in `src/copilot` (injectable seams: DecisionExplanation components, learning priors, Answer Bank corpus, LLM provider); provenance enforced; LLM gated off by default; `copilot_briefs` frozen §7.8 table used as-is; `brief.generated` event (CP-0-03) emitted on build.

### Known Issues
- Verdict acceptance ≥80% (PH2 exit gate, 16_SUCCESS_METRICS) requires a **manual sample** — not machine-verifiable; pending user feedback loop.
- Interview probability calibration (±5pp over 30+ outcomes) pending outcome accumulation (PH7 learning store).
- Answer Bank corpus + learning priors are injected seams with starter defaults until CP-3-02 / CP-7-01 land.
- In-memory brief cache is unbounded per-opportunity dict (ponytail: bounded by opportunity count; durable cache is the DB).

### Risks (next phase)
- PH4 (Session) is the critical-path next phase (dep CP-0-03 events — READY); PH3 (Answer Bank) schedulable in parallel. Gated LLM stays off by default.

### Recommendation
- **GO** — proceed to PH4 (CP-4-01 Session state machine); PH3 (CP-3-01 answerbank fingerprinting) parallel-ready.
