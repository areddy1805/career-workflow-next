# Progress

**Last Updated:** 2026-08-02
**Phase:** PH0–PH4 certified; PH5 in progress (Browser Assistant) — see certification reports below.

| Phase | Status | % | Last task | Notes |
|---|---|---|---|---|
| PH0 | ✅ Complete (certified) | 100 | CP-0-05 DONE | See PH0 Certification below |
| PH1 | ✅ Complete (certified) | 100 | CP-1-09 DONE | 13/13; see PH1 Certification below |
| PH2 | ✅ Complete (certified) | 100 | CP-2-07 DONE | 7/7; see PH2 Certification below |
| PH3 | ✅ Complete (certified) | 100 | CP-3-06 DONE | 6/6; see PH3 Certification below |
| PH4 | ✅ Complete (certified) | 100 | CP-4-05 DONE | 5/5; see PH4 Certification below |
| PH5 | In progress | 63 | CP-5-05 DONE | Playwright pinned (c911288); Browser Assistant 5/8 |
| PH6 | Pending | 0 | — | Blocked on PH1–PH5 |
| PH7 | Pending | 0 | — | Blocked on PH4 |
| PH8 | Pending | 0 | — | Blocked on PH1/PH4/PH7 |
| PH9 | Pending | 0 | — | Blocked on all |

Session convention: every session updates this file + `09_TASK_BOARD.md`. Task statuses: TODO/IN PROGRESS/DONE/BLOCKED/CANCELLED.

## Session Log

### 2026-08-02 — CP-5-05 (Recovery) — DONE
- Files: `src/copilot/browser/recovery.py`, `src/copilot/browser/guidance.py`, `tests/copilot/test_browser_recovery.py`.
- `recovery.py` implements 04 §9: `detect_drift(page, expected_field_ids, page_index)` = model-vs-DOM field-id diff (removed + added); `rebuild_model` = fresh rescan; `recover(controller, model, *, session_id, opportunity_id, expected_url, page_index, max_attempts=3, backoff_ms=200)` orchestrates — drift → rebuild → rebuilt model returned (AC: within one retry); dead page/browser → abort slot + relaunch → reopen URL → model restored from the fresh page (relaunched); relaunch failure, unrecognizable page, or CAPTCHA (rebuild `auto_fillable=False`) → guidance mode with the remaining plan — a CAPTCHA is never attempted (04 §3/§9); takeover → guidance with “annotates only” reason, no recovery (04 §7). One deterministic outcome per run (D-022: `no_drift|rebuilt|relaunched|guidance`); never raises — failures become guidance.
- `guidance.py` (04 §8 module map) owns the §7.6 `GuidancePlan` shape: `GuidanceStep{field_id, label, instruction}` + `build_guidance_plan(model, unfilled=None, reason)` → ordered next-field steps; `unfilled` lets the API limit the plan to unresolved fields.
- D-022 recorded (recovery outcome vocabulary, guidance.py placement, takeover guard).
- Validation: 12 new tests (no-drift fast path; drift diff incl. removed+added; drift→rebuild one retry; dead browser → relaunch + model restored; relaunch failure → guidance with remaining plan + retry count; simulated CAPTCHA swap → guidance, never attempted; takeover → guidance + session stays taken_over; rebuild_model rescan; RecoveryResult/GuidancePlan/GuidanceStep to_dict shapes; unfilled filter; MAX_RETRIES sane); full regression **1358** passed (+12); ruff + mypy clean.

### 2026-08-02 — CP-5-04 (Checkpoint engine) — DONE
- Files: `src/copilot/browser/checkpoint.py`, `tests/copilot/test_browser_checkpoint.py`.
- `checkpoint.py` implements the frozen gates of 04 §6 (per-fill decision matrix) and the §7 three-checkpoint workflow. `fill_action(fill, kind, *, sensitive)` is the §6 matrix verbatim: sensitive→`sensitive` (never auto-fill, always ask), upload→`upload` (confirm at checkpoint), `confidence is None`→`unknown` (skip, surface in review list), <0.80→`ask` (do not fill, inline question), 0.80–0.95→`flag` (fill + review), ≥0.95→`silent`. `categorize` buckets fills; `build_checkpoints` yields `cp1 review_flagged` (flag + unknown), `cp2 upload_sensitive` (upload + sensitive), `cp3 submit` (ask) — cp1/cp2 dismissible, **cp3 never dismissible** (human gesture REQUIRED, ADR-002).
- `CheckpointEngine` owns the gate sequence (D-021): `evaluate(fills, kinds, sensitive=)` returns the next open gate in §7 order (non-submit gates with no pending are skipped; cp3 is always presented once earlier gates are confirmed), `confirm(checkpoint_id, action)` records acknowledgement and rejects out-of-order gates + any dismissal of cp3, `submit_authorized` is True only after cp3 is confirmed — the submit gate can never be bypassed (AC). Checkpoint shape per §7.6: `{checkpoint_id, type, gates_open, pending: [{type, field_id, reason}], dismissible}`.
- D-021 recorded (checkpoint taxonomy, strict sequence, unresolved→unknown mapping).
- Validation: 22 new unit tests (full §6 matrix parametrized incl. threshold boundaries 0.95/0.80/0.79 and sensitivity-wins; categorize buckets; build order + dismissibility; silent fills reach submit gate; flag→submit sequence with out-of-order reject; upload+sensitive gate; cp3 dismiss rejected; never-bypass full sequence; wrong-gate confirm rejected; ask surfaces at submit gate; to_dict shapes; empty form reaches submit); full regression **1346** passed (+22); ruff + mypy clean.

### 2026-08-02 — CP-5-03 (Field resolver) — DONE
- Files: `src/copilot/browser/resolver.py`, `tests/copilot/test_browser_resolver.py`.
- `resolver.py` implements 04 §5: `resolve_field(conn, field, profile_id, *, context, sensitive=False) -> FieldFill {field_id, resolution, filled, confidence, source, reason}` — (1) fingerprint the field's label with the Answer Bank (D-020: **label-only** `Question(label=field.label)`, the same key space the certified brief path uses to resolve/store `copilot_answers`, so form fields hit the same stored answers); (2) `answerbank.resolve` (06 §3 order stored → deterministic → generated); (3) type-match the semantic answer to the field kind — select→option id, radio→value (normalized equality on option label then value), date→iso (`%Y-%m-%d`/US/EU/human formats), checkbox→`"on"` for truthy / `""` for falsy, number→numeric text (`"5 years"` → `"5"`), upload→never, free-text passthrough; (4) `FieldFill` with `filled` = type-matched value available (the §6 gates are CP-5-04's job), `resolution` = the §7.4 `AnswerResolution` dict + browser `typed_value` key (the exact value the fill pass writes). `sensitive=True` stages the suggestion at the checkpoint but never fills (04 §6); uploads always `filled=False` (04 §7 upload checkpoint). `resolve_fields` runs the whole form's fill pass (sensitive set by field_id).
- D-020 recorded (label-only fingerprint key space + `typed_value` in resolution).
- Validation: 17 new unit tests (select label/value match, unmatched → not filled, radio value, date iso + invalid, checkbox truthy/falsy, number leading-numeric, free-text passthrough for all kinds, upload never filled, sensitive never filled with suggestion staged, unknown/abstain → not filled, deterministic engine fill, LLM confidence passthrough, batch resolve, sensitive set, to_dict shapes incl. `typed_value`); full regression **1324** passed (+17); ruff + mypy clean.

### 2026-08-02 — CP-5-02 (Form field model) — DONE
- Files: `src/copilot/browser/form/model.py`, `src/copilot/browser/form/__init__.py`, `tests/copilot/conftest.py` (shared `browser_env`/`browser_controller` fixtures, headed=False + vendored `PLAYWRIGHT_BROWSERS_PATH`), `tests/copilot/fixtures/browser/{greenhouse_form,lever_form,ashby_form,multistep_step1,multistep_step2,captcha_form}.html`, `tests/copilot/test_form_model.py`.
- `model.py` implements 04 §4: `extract_fields(page, page_index)` reads the DOM + a11y attrs (one `[id]` textContent pass + one `label[for]` pass, then per-control aria-labelledby → aria-label → label[for] → wrapped label → placeholder → name/id) and produces the frozen `TypedField {field_id, kind, label, name, options[], required, page, confidence}` (kind vocabulary `FieldKind`: text|number|date|select|radio|checkbox|textarea|upload|email|phone|url — password maps to text, hidden/submit/button/reset/image inputs skipped). `extract_form_model(page, ats_type=None, page_index)` returns the §7.6 `FormModel {fields, pages, ats_type, auto_fillable}`; `FormModel.add_page` accumulates multi-page forms deduping by `field_id` (04 §4 multi-page; recovery re-scans never duplicate). CAPTCHA markers (recaptcha/hcaptcha/captcha/turnstile iframe srcs or `.g-recaptcha`/`.h-captcha`/id*="captcha") set `auto_fillable=False` (04 §3/§9 — never attempt CAPTCHA). `detect_ats_type(url)` is a best-effort hostname hint (greenhouse.io/lever.co/ashbyhq.com/workday/rippling → `AtsType`, else generic); extraction never depends on it (ADR-005) and callers may override.
- D-019 recorded: `TypedField.confidence` = label-association quality ladder (1.0 label[for]/wrap, 0.95 aria-labelledby, 0.9 aria-label, 0.8 placeholder, 0.7 name/id, 0.5 none) so CP-5-03's thresholds have a defined input; `options[]` = `FieldOption{value, label}`; radios = one logical field per shared name (legend → fieldset aria-label → first radio label), empty-value select options skipped.
- Validation: 9 new integration tests (greenhouse fixture → exact typed fields incl. kinds/required/select options/hidden+submit skipped; lever fixture → wrapped labels, checkbox, radio group with legend + option labels; ashby fixture → aria-label/aria-labelledby/placeholder/name fallbacks with exact confidences; detect_ats_type URL unit; ats_type override; multi-page accumulation p0+p1 → pages=2 with page indices; rescan dedupe; CAPTCHA → auto_fillable False; to_dict shapes per §7.6/§4); full regression **1307** passed (+9); ruff + mypy clean.

### 2026-08-02 — CP-5-01 (Browser controller) — DONE
- Files: `src/copilot/browser/controller.py`, `src/copilot/browser/__init__.py`, `tests/copilot/test_browser_controller.py`.
- `controller.py` implements 04 §8 (Playwright session lifecycle, visible browser, launch/teardown, takeover) as `BrowserController` — a single Chromium instance behind the assistant with **one session at a time** (AC): `open(url, session_id, opportunity_id) -> BrowserSession` (launch-on-first-use, goto, session snapshot `{session_id, opportunity_id, url, state, page_url, title}`), `navigate` (controller-initiated multi-page nav), `close`/`abort` (teardown + slot release; `abort` returns the terminal `aborted` session), `current_session`/`page` reads. Visible browser by default (ADR-003); tests force `headless=True` (08 CP-5-01 AC: integration headed=False in CI). Feature-gated: `BROWSER_ENABLED = False` off by default, `open` raises `BrowserNotEnabled` while off (DoD rollback). Failed opens tear the browser down (no leak); a navigation failure is `BrowserError`, never a raw Playwright error. `BrowserSession.to_dict()` serves the §7.6 read shape.
- **Takeover hook (D-018)**: `add_takeover_handler` registers callbacks; they fire when the human takes the wheel — detected as a main-frame navigation the controller did not initiate (`framenavigated` + controller-initiated flag; subframes ignored), or forced via `take_over(reason)` (Esc path, CP-5-08). After takeover the session is `taken_over` and `navigate` raises `BrowserSessionError` — the assistant annotates, never steers (04 §7).
- Browser resolution: Playwright reads `PLAYWRIGHT_BROWSERS_PATH` → project-local vendor `<repo>/.playwright/` (setup c911288). Tests set it via fixture; teardown calls the sync API's `stop()` (not `close()`) so the dispatcher loop never leaks — without it every later launch trips Playwright's “Sync API inside the asyncio loop” guard.
- D-018 recorded (takeover detection + stop-steering reading); 04 §8 freezes the hook, not the mechanism.
- Validation: 9 new integration tests (feature gate, open→navigate→close smoke incl. title/page_url, one-session-at-a-time + slot release after abort, takeover on unexpected navigation + handler + stop-steering, forced take_over idempotent, abort-without-session error, failed open tears down + slot free for retry, to_dict shape, visible default); full regression **1298** passed (+9); ruff + mypy clean.

### 2026-08-02 — CP-3-06 (Answer bank API) — DONE
- Files: `src/copilot/answerbank/api.py`, `api/routers/copilot.py` (+include), `api/schemas.py` (+`AnswerSaveRequest`/`AnswerConfirmRequest`/`AnswerLockRequest`/`ProfileSwitchRequest`), `tests/copilot/test_answerbank_api.py`.
- Frozen §7.9 surface mounted at `/api/copilot` via `src/copilot/answerbank/api.py` included into the copilot router (D-015 reading — the router file is the mount point; endpoints live in copilot-owned modules): `GET /answers` (per-profile namespace + status/text filters + pagination; default profile `generic`), `PUT /answers/{fp}` (upsert; `serialized_answer` falls back to `semantic_answer`; defaults source=manual/status=confirmed), `POST /answers/confirm` (frozen §7.4 `confirm`; locked → 400), `POST /answers/lock` (frozen §7.4 `set_locked`; pin/unpin/idempotent; missing → 400), `POST /profiles/switch` (`switch_profile` → `{profile_id, resume_type}` context). `{ok, data, error}` envelope; no pipeline seams (store/confirm/profiles take the connection directly, mirroring `brief/api.py`).
- Validation: 11 new integration tests (empty list, profile-namespace isolation via API, status filter, update defaults + overwrite single row, confirm creates human answer with actor reason, confirm-on-locked 400, lock pin/unpin/idempotent flow, lock missing 400, profile switch context, switch leaves answers undisturbed); full regression 1289 passed; ruff + mypy clean.

### 2026-08-02 — CP-3-05 (Profile switching service) — DONE
- Files: `src/copilot/answerbank/profiles.py`, `tests/copilot/test_answerbank_profiles.py`.
- `profiles.py`: frozen §7.4 `switch_profile(profile_id) -> ProfileContext` — the atomic namespace + resume-mapping swap of 06 §5. Because the answer namespace is the `(question_fp, profile_id)` composite key (CP-3-03), a switch is a pure context handoff: `ProfileContext{profile_id, resume_type}` is what every subsequent resolve/fill keys on; nothing in `copilot_answers` is moved/copied/rewritten, so the swap can never tear and cross-profile leakage is impossible by construction (06 §5 AC).
- D-017: resume mapping = deterministic `{ai: AI, fde: FDE, generic: generic}` (matches `ResumeRouter` per 06 §5); unknown profile ids stay free-form namespaces with resume_type = id (the session workspace already accepts arbitrary profile ids — no frozen-set validation).
- Validation: 7 new unit tests (known-profile mapping incl. case-insensitive, mapping family matches ResumeRouter, unknown free-form id, context round-trip, switch mutates nothing — atomic, no cross-profile leakage both directions); full regression 1278 passed; ruff + mypy clean.

### 2026-08-02 — CP-3-04 (Confirmation workflow + override) — DONE
- Files: `src/copilot/answerbank/confirm.py`, `tests/copilot/test_answerbank_confirm.py`.
- `confirm.py` implements frozen §7.4 `confirm(question_fp, profile_id, answer, actor)` + `set_locked(question_fp, profile_id, locked)` per 06 §6: confirm stores the human override as authoritative (`source=manual`, `status=confirmed`, confidence 1.0, reason `confirmed by <actor>`, preserves canonical_label/category); **locked rows reject confirm** until unlocked (06 §6 "never auto-overwritten"); `set_locked(True)` pins from auto/confirm/confirmed (idempotent on locked, rejects superseded tombstones), `set_locked(False)` returns locked → confirmed (rejects non-locked). Missing-row lock → `CopilotError`.
- D-016: 06 §6 says overrides carry "human provenance" but the frozen §7.4 source vocabulary is `stored|deterministic|llm|manual` — overrides are stored with `source=manual` (frozen vocabulary wins; `AnswerSource` enum untouched).
- Resolver integration: a confirmed/locked human answer is served as the stored answer (06 §3 step 1) with its status passed through verbatim (D-013) — overrides truly win over generated/deterministic on every resolve.
- Validation: 14 new tests (confirm creates human answer with actor reason, override wins over confirm/confirmed rows, locked rejects confirm + lock survives, confirm-after-unlock, canonical metadata preserved, pin/unpin transitions, lock idempotent, missing/superseded/not-locked guards, resolver serves confirmed + locked answers with D-013 passthrough); full regression 1271 passed; ruff + mypy clean.

### 2026-08-02 — CP-3-03 (Answer store CRUD + profiles) — DONE
- Files: `src/copilot/answerbank/store.py`, `tests/copilot/test_answerbank_store.py`.
- `store.py`: `StoredAnswer` dataclass mirroring the frozen §7.8 `copilot_answers` row (question_fp, profile_id, canonical_label, category, source, semantic_answer, serialized_answer, confidence, status, reason, use_count, last_used_at, outcome_quality; `to_dict`/`from_row`); `save` (upsert on `(question_fp, profile_id)` — one row per profile namespace, 06 §5), `get`, `list_answers(profile_id, status, query, limit, offset)` (namespace/status/text filters), `supersede` (tombstone → `status = superseded`, the state 06 §3 step 1 skips in resolution). Statuses/`source` use the frozen `AnswerStatus`/`AnswerSource` vocabularies; confirmation transitions themselves land in CP-3-04.
- Namespace isolation is the composite PK: a resolve/list for one profile can never see another profile's rows (tested: ai/fde/generic same fp → distinct values, filtered lists).
- Validation: 8 new tests (save/get round-trip incl. all fields, missing → None, upsert-on-conflict single row, 3-profile namespace isolation, list filters status/query/limit/offset, supersede tombstone + missing → False, **superseded answer skipped by the resolver** — falls through to deterministic, and to_dict round-trip); full regression 1257 passed; ruff + mypy clean.

### 2026-08-02 — CP-4-05 (Session API) — DONE
- Files: `src/copilot/session/api.py`, `api/routers/copilot.py` (+include), `api/schemas.py` (+`SessionCreateRequest`/`SessionAdvanceRequest`), `src/copilot/session/service.py` (+`progress`/`abort`/`events` reads, `outcome_enabled` constructor flag, `NotFoundError` on missing opportunity in `start`), `src/copilot/exceptions.py` (+`NotFoundError`), `tests/copilot/test_session_api.py`.
- Frozen §7.9 surface mounted at `/api/copilot` via `src/copilot/session/api.py` included into the copilot router — the same reading as CP-2-07 (the doc's "api/routers/copilot.py" is the mount point; endpoints live in copilot-owned modules, D-015): `POST /sessions` (create → BRIEF_READY + brief snapshot; 404 missing opportunity, 500 brief build failure), `GET /sessions/{id}` (session state + ordered per-session events), `POST /sessions/{id}/advance` (event name → `SessionEventType`; workspace events route to the service methods that carry snapshot/pipeline side effects — ANSWERS_CONFIRMED→confirm_answers, RESUME_CHOSEN→select_resume(+payload.resume_id), FORM_FILLED→fill_form(payload), HUMAN_SUBMIT→submit(human_gesture default true), OUTCOME_RECORDED→record_outcome(payload.outcome, missing → 400), FORM_FILLING/CHECKPOINT_PENDING→progress self-loop (D-011)), `POST /sessions/{id}/abort`. Envelope `{ok, data, error}`; status codes 404 (missing), 409 (InvalidTransitionError), 400 (unknown event / bad payload / gesture).
- `get_session_service` is a FastAPI dependency (yields a `WorkspaceService` per request, owns its copilot.db conn) so integration tests override seams via `app.dependency_overrides` — the same DI pattern as `get_ingestion_registry`. `WorkspaceService` gained `outcome_enabled` constructor config (defaults to the CP-4-04 flag; per-call `enabled=` still honored) so the API's default service is off-by-default while test overrides can enable the pipeline write. `NotFoundError(CopilotError)` added to the exception taxonomy for precise 404s.
- Validation: 15 new integration tests (create + snapshot + 404, get state+events + 404, full-chain advance with event trail, unknown event 400, invalid transition 409 with nothing persisted, RESUME_CHOSEN payload + FORM_FILLING self-loop, submit gesture 400, OUTCOME_RECORDED missing-outcome 400, outcome session-data with flag off, **outcome through the API with flag on reaches the queue seam + learning row**, abort + abort-after-submit 409 + abort 404); full regression 1249 passed; ruff + mypy clean.

### 2026-08-02 — CP-4-04 (Outcome capture) — DONE
- Files: `src/copilot/session/outcome.py`, `src/copilot/session/service.py` (+`queue_transition` seam, `record_outcome`), `src/copilot/oppstore/store.py` (+`get_pipeline_job_id`), `tests/copilot/test_outcome.py`.
- `outcome.py`: `record_outcome(conn, session_id, outcome, *, transition=None, enabled=OUTCOME_CAPTURE_ENABLED, trace_id)` implements 02 §6 step 5 (outcome → `WorkflowQueue.transition` + ledger update via existing APIs, ADR-007) in three layers: (1) **session row** — `OUTCOME_RECORDED` self-loop on SUBMITTED (D-011) with `outcome`/`outcome_at` via the `updates=` hook, payload carries `{outcome, pipeline:{job_id, status, transitioned, reason}}`; (2) **pipeline** — the only pipeline-visible write is `WorkflowQueue.transition(job_id, status, actor="copilot", note=...)` through an injectable seam (importlib `_lazy_queue_transition` in production, fakes in tests; `WorkflowStatus` enum built via importlib, no static pipeline imports); transition only when `pipeline_job_id` present (mapped via `oppstore.get_pipeline_job_id`); a missing job (False), missing mapping, or raised exception is recorded in the event payload and **never crashes the session**; (3) **learning** — `copilot_learning_outcomes` insert (idempotent, `session_id` UNIQUE, `INSERT OR IGNORE`) + `learn.outcome_recorded` CopilotEvent (§7.7) with provider/ats/resume-profile from the opportunity + session.
- Outcome vocabulary (D-014): docs freeze no outcome strings; `OUTCOME_TO_STATUS` maps `applied/interview/offer/rejected/archived` → pipeline `WorkflowStatus` values so every write stays inside the workflow machine's transition rules. Unknown outcome → `CopilotError` before any write.
- Feature flag `OUTCOME_CAPTURE_ENABLED = False` off by default (08 DoD: rollback = leave off): when disabled the session-row outcome is still recorded (pure copilot data, machine already supports it) but the pipeline transition and learning signal are skipped. `WorkspaceService.record_outcome(session_id, outcome, *, enabled, trace_id)` mirrors the other ops and accepts the `queue_transition` seam.
- Validation: 12 new integration + ledger-consistency tests (vocabulary gate before any write, machine gate before SUBMITTED, happy path transition call args + event payload, all five outcomes map, missing `pipeline_job_id` records-but-skips, transition False/exception never crash the session, disabled flag = session-only, learning row fields + learn event, re-record keeps single learning row, **real `WorkflowQueue` integration** — enqueue → IN_PROGRESS → outcome APPLIED with merged status + MAQ alignment + copilot history entry, real queue missing job → False flagged); full regression 1234 passed; ruff + mypy clean.

### 2026-08-02 — CP-4-03 (Workspace service) — DONE
- Files: `src/copilot/session/{service,store}.py`, `tests/copilot/test_session_service.py`.
- `service.py`: `WorkspaceService` orchestrates one application attempt through the frozen §7.5 chain with consistent snapshots: `start(opportunity_id, profile_id, resume_id)` → BRIEF_READY + `brief_snapshot_json` (CP-2-07 brief, 404-style `CopilotError` for missing opp/brief); `confirm_answers` → resolves the brief's likely questions through the CP-3-02 Answer Bank stack (06 §3) + writes `answers_snapshot_json` atomically with the ANSWERS_CONFIRMED transition (event payload carries answers/auto/confirm counts); `select_resume` → `ResumeRouter.route(job)` via importlib seam (02 §6), explicit `resume_id` wins, router failure falls back to the brief's resume recommendation (never blocks the session); `fill_form(form_summary)` → FORM_FILLED; `submit(human_gesture=True)` → HUMAN_SUBMIT → SUBMITTED, raises `CopilotError` without the gesture (ADR-002). Reads: `get`, `workspace_view` (session + parsed brief/answers snapshots for CP-4-05).
- `store.advance_session` gained `updates=` (dataclass `replace` merged before save) so snapshots land in the same row write as the transition — no torn state.
- Integration notes: `ResumeDeltaEngine.generate_delta` is exposed as the `resume_delta` seam (typed pipeline objects make it heavy); the brief snapshot's resume recommendation serves as the delta record until wired. Browser fill is PH5 — `fill_form` records the transition + optional summary.
- Validation: 13 new integration tests (start snapshot + event, missing opp, confirm resolves+snapshots+counts incl. low-confidence confirm path, route recording + explicit id + router-failure fallback, fill summary, submit gesture guard + advance, full happy path with event trail, invalid ordering raises, workspace_view round-trip); full regression 1222 passed; ruff + mypy clean.

### 2026-08-02 — CP-3-02 (Resolution engine wrapper + cache) — DONE
- Files: `src/copilot/answerbank/{resolver,cache}.py`, `tests/copilot/test_answerbank_resolver.py`.
- `resolver.py`: `AnswerResolution` (frozen §7.4 shape: question_fp, source, semantic_answer, serialized_answer, confidence, status, reasoning; to_dict/from_dict) + `ResolveContext{conn, profile, hybrid_resolver, cache}`; `resolve()` implements frozen 06 §3 order: (1) stored answer — exact fp + profile namespace + `status != 'superseded'` (passes stored status through verbatim, D-013); (2) deterministic — pipeline `questionnaire_resolver.resolve_answer → apply_answer_constraints → serialize_answer` via importlib (ADR-009), `kind → questionType` + `options → answerOption` mapping, resolved → `auto`; a constraint/serialization failure **short-circuits to confirm** (mirrors pipeline hybrid: rejected deterministic values never reach the LLM); (3) generated LLM — cache-first by (fp, profile_id), then pipeline `HybridQuestionResolver` (importlib seam; dataclass result normalized to dict; injectable fake engines for tests), resolved → `confirm` (≥0.95 confidence → `auto`, 06 §6), abstain/error → `confirm`. `_load_profile` reads `config.candidate_profile.CANDIDATE_PROFILE` (pipeline-owned, read-only).
- `cache.py`: generated-answer cache keyed `(fp, profile_id)` (module `_CACHE` + injectable, mirrors brief pattern) — repeat resolves never re-invoke the LLM (06 §9).
- Validation: 11 new tests (round-trip; order — stored wins, profile namespacing, superseded skipped; real deterministic integration with `CANDIDATE_PROFILE` incl. select serialization via kind; LLM cached by fp+profile, profile-scoped, engine invoked once; ≥0.95 → auto; manual_review → confirm; deterministic-failure short-circuit); full regression 1209 passed; ruff + mypy clean.

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

## PH3 Certification Report

**Phase:** PH3 — Answer Bank (Epic ANS) · **Date:** 2026-08-02

### Completed Tasks (6/6)
| ID | Task | Result |
|---|---|---|
| CP-3-01 | Question fingerprinting + canonical labels | DONE |
| CP-3-02 | Resolution engine wrapper + cache | DONE |
| CP-3-03 | Answer store CRUD + profiles | DONE |
| CP-3-04 | Confirmation workflow + override | DONE |
| CP-3-05 | Profile switching service | DONE |
| CP-3-06 | Answer bank API | DONE |

### Acceptance Criteria Verification
- **Variant phrasings → same canonical slot; stable hash** (CP-3-01): `fingerprint = sha256(normalized_label | normalized_options_keys | kind)[:16]` (06 §4); canonical registry most-specific-first, word-boundary first-match (D-012); 13 synonym-table tests. ✅
- **Resolution order frozen §3; cached generated answers** (CP-3-02): stored (status != superseded) → deterministic (constraint/serialization failure short-circuits to confirm) → generated LLM (cache-first by fp+profile, ≥0.95 → auto); 11 tests. ✅
- **Namespace isolation; confirm/lock semantics** (CP-3-03): `(question_fp, profile_id)` composite PK = per-profile namespace; supersede tombstone is skipped by the resolver; 8 tests. ✅
- **Transitions validated; override wins** (CP-3-04): confirm from absent/auto/confirm/confirmed/superseded → confirmed with `source=manual` (D-016); locked rejects confirm until unlock; set_locked pin/unpin transitions validated; 14 tests. ✅
- **Atomic swap; no cross-leak** (CP-3-05): `switch_profile` is a pure context handoff — nothing in `copilot_answers` is mutated, the old namespace stays invisible/intact; resume mapping `{ai: AI, fde: FDE, generic: generic}` (D-017); 7 tests. ✅
- **Contract §7.9** (CP-3-06): GET /answers, PUT /answers/{fp}, POST /answers/confirm, /lock, /profiles/switch with `{ok, data, error}` envelope + Pydantic bodies; 11 tests. ✅
- **PH3 exit gate**: confirmed answers persist per profile — store + confirm + resolver integration green (confirmed/locked human answers served as stored on every resolve, D-013 passthrough). “≥90% of screening questions resolve” is an auto-resolve-rate metric (06 §9) requiring a real questionnaire sample — **manual, pending user feedback** (same caveat as PH2's verdict metric).

### Tests Executed
- 64 new copilot tests across CP-3-01..06 (fingerprint 13, resolver 11, store 8, confirm 14, profiles 7, API 11). Copilot suite now **496 tests**.
- Full regression: **1289 passed, 0 failed** (1249 PH4-cert → 1289; pipeline untouched).
- ruff clean on all new files; mypy clean (`src/copilot`, `api/routers/copilot.py`).

### Coverage
- `src/copilot` + `api/routers/copilot.py`: **97%** (2337 stmts, 78 missed — config/error-guard branches). Answer bank modules: store/confirm/profiles 100%, resolver + fingerprint + canonical + API all exercised via the 64-test suite.

### Documentation Status
- `10_PROGRESS.md` session log current through CP-3-06 (34 entries); `09_TASK_BOARD.md` 6/6 DONE; `11_DECISIONS.md` D-012 (canonical first-match), D-013 (stored status passthrough), D-016 (overrides stored as `source=manual`), D-017 (profile→resume map) Active. Frozen docs/ADRs untouched.

### Architecture Compliance
- Frozen 06 §2 taxonomy, §3 resolution order, §4 fingerprinting, §5 profiles, §6 confirmation, §8 persistence implemented; §7.4 surface (`resolve`/`fingerprint`/`confirm`/`set_locked`/`switch_profile`) complete; §7.8 `copilot_answers` schema used as-is; §7.9 endpoints mounted.
- ADR-009: pipeline `HybridQuestionResolver` + deterministic stack reached only via importlib seams (no static pipeline imports); ADR-007: candidate truth read-only; enums frozen (D-016 explicitly refuses a 5th source value).

### Known Issues
- “≥90% resolve” (PH3 exit gate / 06 §9) is a **manual-sample** metric pending user feedback on a real questionnaire corpus.
- Canonical registry grows from real questionnaires (backlog per 06 §4) — novel phrasing coverage depends on corpus accumulation.
- Generated/auto answers are served from the in-memory cache, not persisted: only human-confirmed answers land in `copilot_answers` (06 §6's silent-fill still works via resolution); durable generated-answer promotion + `outcome_quality` feedback is the PH7 learning loop (`copilot_answers.outcome_quality` column ready).

### Risks (next phase)
- PH5 (browser assistant) needs the **playwright dependency** (pin version + browser binaries per user recommendation) — answers from PH3 now unblock PH5 form-field resolution.
- PH7 learning store consumes `copilot_learning_outcomes` + answer `outcome_quality`; interview-probability calibration (16_SUCCESS_METRICS M09) pending outcome accumulation.

### Recommendation
- **GO** — PH3 certified. Next: PH5 (pending playwright confirmation) or parallel backlog/UI work.

## PH4 Certification Report

**Phase:** PH4 — Application Session (Epic SES) · **Date:** 2026-08-02

### Completed Tasks (5/5)
| ID | Task | Result |
|---|---|---|
| CP-4-01 | Session state machine (frozen states/events) | DONE |
| CP-4-02 | Session persistence + events (`copilot_sessions`, `copilot_session_events`) | DONE |
| CP-4-03 | Workspace service (brief→answers→resume→submit orchestration) | DONE |
| CP-4-04 | Outcome capture (pipeline-visible writes only via queue APIs + learn signal) | DONE |
| CP-4-05 | Session API (create/get/advance/abort) | DONE |

### Acceptance Criteria Verification
- **All valid/invalid transitions tested** (CP-4-01): exhaustive (state × event) matrix — 30 unit tests, every valid pair transitions, every invalid pair raises `InvalidTransitionError` (a `CopilotError`); D-011 reading enforced (progress self-loops, HUMAN_SUBMIT trigger, SUBMITTED never a trigger, OUTCOME_RECORDED self-loop on SUBMITTED). ✅
- **State + snapshot persisted; events appended** (CP-4-02): full §7.8 row round-trip (brief/answers snapshot JSON, submitted_at, outcome cols); per-session seq log + `ses.*` CopilotEvents in sync; invalid transition persists **nothing**; upsert idempotent. ✅
- **Workspace advances correctly; snapshots consistent** (CP-4-03): start → BRIEF_READY + brief snapshot; confirm → answers snapshot atomic with the transition (answers/auto/confirm counts); resume routing with explicit-id precedence + router-failure fallback; submit gesture guard (ADR-002); happy-path event trail in frozen order. ✅
- **No direct pipeline DB writes; accounting consistent; ledger tests pass** (CP-4-04): the only pipeline-visible write is `WorkflowQueue.transition` through an injectable seam (ADR-007) — a **real-queue integration test** verifies MAQ base status, `workflow_history` (actor=copilot, note=outcome), and merged `workflow_status` all align after an outcome; missing job / missing `pipeline_job_id` / raised exception are recorded in the event payload and never crash the session; learning insert idempotent per session + `learn.outcome_recorded` emitted. ✅
- **Contract §7.9** (CP-4-05): POST /sessions, GET /sessions/{id} (state + events), POST /sessions/{id}/advance (event-name → `SessionEventType`, workspace ops route to the snapshot/pipeline-carrying service methods), POST /sessions/{id}/abort; `{ok, data, error}` envelope; 404 missing / 409 invalid transition / 400 unknown event or payload; seams overridable via `app.dependency_overrides`. ✅
- **PH4 exit gate**: end-to-end session (brief→answers→resume→submit→outcome) runs through the API (full-chain advance test + outcome-through-queue test with the flag on) and the full regression passes with the pipeline untouched. ✅

### Tests Executed
- 80 new copilot tests: state machine 30, store 10, workspace service 13, outcome 12 (incl. real `WorkflowQueue` ledger integration), session API 15. Copilot suite now **456 tests**.
- Full regression: **1249 passed, 0 failed** (1175 → 1185 → 1222 → 1234 → 1249 across CP-4-01..05; pipeline untouched).
- ruff clean on all new files; mypy clean (`src/copilot`, `api/routers/copilot.py`).

### Coverage
- `src/copilot` + `api/routers/copilot.py`: **96%** (2190 stmts, 77 missed — config/error-guard branches). Session modules: api 88%, outcome 92%, service 97%, state_machine/events/models/store 100%.

### Documentation Status
- `10_PROGRESS.md` session log current through CP-4-05 (30 entries); `09_TASK_BOARD.md` 5/5 DONE; `11_DECISIONS.md` D-011 (transition reading), D-013 (answer status passthrough), D-014 (outcome vocabulary + gating), D-015 (session endpoints module placement) Active. Frozen docs/ADRs untouched.

### Architecture Compliance
- Frozen §7.5 states/events, §7.7 CopilotEvent namespaces (`ses.*` + `learn.*`), §7.8 schema used as-is (`copilot_sessions` incl. outcome cols, `copilot_session_events`, `copilot_learning_outcomes`), §7.9 API contract implemented.
- ADR-007: Copilot reads the pipeline through stable interfaces, writes outcomes only via `WorkflowQueue.transition` — verified by the ledger-consistency test. ADR-002: no autonomous submit (human gesture required). ADR-010/012: copilot.db is the sole Copilot store; `pipeline_job_id` mapping read-only.
- No pipeline imports inside `src/copilot` (importlib seams for `ResumeRouter`, `WorkflowQueue`, `WorkflowStatus`; injectable params everywhere else).

### Known Issues
- PH2 caveat carried forward: “verdict accepted ≥80%” (PH2 exit gate, 16_SUCCESS_METRICS) is a **manual-sample** metric pending user feedback — not machine-verifiable.
- Outcome capture is feature-flag **OFF by default** (`OUTCOME_CAPTURE_ENABLED = False`, D-014): pipeline transition + learning signal activate when the flag flips; session-row outcomes record regardless.
- Browser fill is PH5 — `fill_form` records the transition + optional summary; the exit-gate submit path is exercised at service/API level, not against a live ATS.
- `FORM_FILLING`/`CHECKPOINT_PENDING` are log-only progress events until PH5 drives them.

### Risks (next phase)
- PH5 (browser assistant) needs the **playwright dependency** — confirm with user before starting.
- PH3 remainder (CP-3-03..3-06 answer store/confirm/profile/API) is parallel-ready and unblocks answer persistence; `copilot_learning_outcomes` consumption lands with PH7 (learning store).
- Interview-probability calibration pending outcome accumulation (16_SUCCESS_METRICS M09).

### Recommendation
- **GO** — PH4 certified. Next: PH3 remainder (parallel) or PH5 (pending playwright confirmation).
