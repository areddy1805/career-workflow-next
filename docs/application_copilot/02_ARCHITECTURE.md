# Application Copilot — Architecture

**Version:** 5.1.0-rc1
**Status:** Approved — Interface Freeze

---

## 1. Architectural Context

The Copilot is a **second product** layered on the frozen production pipeline (Acquisition, Classification, Ranking, Candidate Intelligence, Inference, Lifecycle, Routing, Scheduler, Queue Generation, Dashboard, Accounting, Capacity Discovery, Provider Integration, Manual/ATS/External Queues — all frozen).

**Coupling rule (ADR-007):** the Copilot **reads** the pipeline through stable interfaces and **writes outcomes only through existing repository/queue APIs**. It never mutates pipeline DBs directly, never re-implements pipeline logic, and must not cause accounting regressions.

## 2. Top-Level Structure

```
┌────────────────────────────────────────────────────────────┐
│                       src/copilot/                          │
│  ┌────────────┐  ┌──────────┐  ┌────────────┐  ┌─────────┐ │
│  │ ingestion/ │→│ oppstore/│→│  brief/    │  │ session/│ │
│  │ adapters   │  │ model+db │  │  engine    │→│  sm+ws  │ │
│  └────────────┘  └──────────┘  └────────────┘  └────┬────┘ │
│  ┌────────────┐  ┌──────────┐                      ▼      │
│  │ answerbank/│→│ browser/ │←──── session drives ──┘      │
│  └────────────┘  └──────────┘  ┌────────────┐              │
│  ┌────────────┐  ┌──────────┐  │ learning/  │  ┌─────────┐ │
│  │ telemetry/ │  │ events/  │  │ outcomes+fb│  │ config/ │ │
│  └────────────┘  └──────────┘  └────────────┘  └─────────┘ │
└────────────────────────┬───────────────────────────────────┘
          read-only reads │ writes ONLY via existing repo APIs
┌────────────────────────▼───────────────────────────────────┐
│  PRODUCTION PIPELINE (frozen): OpportunityRepository,       │
│  JobLifecycleStore, ApplicationLedger, WorkflowQueue,       │
│  CandidateIntelligence, CANDIDATE_EVIDENCE, ResumeRouter,   │
│  ResumeDeltaEngine, PriorityEngine, HybridQuestionResolver, │
│  InferenceEngine, JobDecisionLedger, capacity/accounting     │
└─────────────────────────────────────────────────────────────┘
```

## 3. Subsystems, Responsibilities, Boundaries

| Subsystem | Responsibility | Reads (read-only) | Writes | Owns |
|---|---|---|---|---|
| `ingestion/` | Adapters for every source → `CopilotOpportunity`; dedup fingerprint; provenance tagging | provider payloads, existing manual queues, fetched pages/PDFs/text | `copilot_opportunities` | normalization |
| `oppstore/` | Opportunity CRUD, source↔pipeline `job_id` mapping, status read view (ADR-012) | `ApplicationLedger`, `JobLifecycleStore`, `WorkflowQueue` | `copilot_opportunities`, `copilot_sources` | normalized truth |
| `brief/` | Assemble `ApplicationBrief` (deterministic-first, cached) | score components, `ResumeDelta`, `CandidateIntelligence`, evidence, learning priors | `copilot_briefs` | brief truth |
| `answerbank/` | Fingerprint, resolve (stored/generated/confirm), per-profile namespaces | `CANDIDATE_EVIDENCE`, `CandidateProfile`, `HybridQuestionResolver` (resolve), learning quality | `copilot_answers` | answer truth |
| `session/` | Per-application state machine + workspace service; outcome capture | brief, answers, resume rec, assistant events | `copilot_sessions`, `copilot_session_events`; outcomes via `WorkflowQueue.transition`/ledger APIs | one application attempt |
| `browser/` | Visible Playwright session; DOM→typed field model; field→answer resolution; checkpoints; recovery; ATS adapters | `answerbank` resolve, session | `copilot_browser_actions` (audit), session events | browser execution |
| `learning/` | Outcome/signal store; ranking feedback; answer weighting; provider success | ledger, job_lifecycle, answers, sessions | `copilot_learning_*`; feeds back via published bias | learning truth |
| `telemetry/` | Copilot metrics + events export | events | metrics tables | observability |
| `api/` | `api/routers/copilot.py` — all Copilot endpoints | subsystems | — | API contract |
| `frontend/` | Copilot pages under `frontend/src/pages/copilot/` | API | — | UI |

## 4. State Ownership & Single Source of Truth

| Concern | Source of Truth |
|---|---|
| Opportunity normalized facts | `oppstore` (`copilot_opportunities`) |
| Lifecycle / accounting | `JobLifecycleStore` + `ApplicationLedger` (pipeline-owned, Copilot read-only) |
| Candidate truth | `CANDIDATE_EVIDENCE` + `CandidateIntelligence` (pipeline-owned) |
| Brief | `copilot_briefs` |
| Answers | `copilot_answers` |
| One application attempt | `copilot_sessions` |
| Learned weights/signals | `copilot_learning_*` |

**Invariant:** no fact appears in both a pipeline DB and `copilot.db` unless the pipeline DB is the authoritative copy and `copilot.db` is a derived cache with a `synced_from` + timestamp.

## 5. Data Flow (canonical sequence)

1. **Ingest:** adapter → normalize → fingerprint → `oppstore.upsert` (provenance recorded per field).
2. **Reconcile:** oppstore merges authoritative lifecycle from `JobLifecycleStore`/`WorkflowQueue` into the status read view.
3. **Brief:** `brief.assemble(opportunity_id)` → deterministic components → LLM augmentation (only for missing/uncertain pieces) → cache → `copilot_briefs`.
4. **Answers:** for each form question, `answerbank.resolve(question, profile)` → stored/deterministic/LLM/confirm decision with confidence.
5. **Session:** `session.create` (BRIEF_READY) → user reviews answers (ANSWERS_REVIEWED) → resume selected (RESUME_SELECTED) → assistant fills (FORM_FILLED) → human submits (SUBMITTED) → outcome captured (OUTCOME_RECORDED) → `WorkflowQueue.transition` + ledger update via existing APIs.
6. **Learn:** outcome → `learning` → published `learning_bias` → consumed by Brief probability + (next run) ranking via existing bias hook `priority_engine._score_one`.

## 6. Key Integrations (frozen)

| Integration | Interface used | Direction |
|---|---|---|
| Manual Queue | `WorkflowQueue.list(source="manual_review")`, `ManualActionQueue.list()` | read |
| Pipeline lifecycle | `OpportunityRepository.get_pool`, `JobLifecycleStore.current_state/find` | read |
| Outcomes | `WorkflowQueue.transition(job_id, to_status, note)` | write (only) |
| Candidate | `CandidateIntelligence.from_repository_sources()`, `CANDIDATE_EVIDENCE`, `CANDIDATE_PROFILE` | read |
| Resume | `ResumeRouter.route(job)`, `ResumeDeltaEngine.generate_delta(job)` | read |
| Scoring | `PriorityEngine._score_one` components; `DecisionExplanation` | read |
| Question resolution | `HybridQuestionResolver.resolve(question, profile)` | read (wrapped) |
| Inference | `InferenceEngine.complete(request)` | read (via existing LLM layer) |
| Decision ledger | `JobDecisionLedger` (duplicate/decision history) | read |

## 7. Frozen Interfaces (stable for the entire development cycle)

All changes require an ADR. Versioned as `copilot-interfaces/v1`.

### 7.1 Ingestion adapter
```
IngestionAdapter:
  source_id: str                        # e.g. "linkedin_url", "pdf"
  supports(payload: Any) -> bool
  fetch(payload) -> RawSourceContent    # RawSourceContent: {source, raw_text, raw_html?, attachments?, url?, meta}
  parse(content) -> ParsedOpportunity   # ParsedOpportunity: normalized dict + field provenance
```
Registry: `ingestion/registry.py` → `register(adapter)`, `adapter_for(payload)`.

### 7.2 CopilotOpportunity (see `03_OPPORTUNITY_MODEL.md` — the frozen contract)
Serialization: `to_dict()` / `from_dict()`; `fingerprint()` (SHA-256 over provider-independent identity fields).

### 7.3 Brief engine
```
build_brief(opportunity_id) -> ApplicationBrief   # cached; idempotent
get_brief(opportunity_id) -> ApplicationBrief | None
invalidate_brief(opportunity_id)
```
`ApplicationBrief` shape: `03_OPPORTUNITY_MODEL.md` §Brief payload / `05_APPLICATION_BRIEF.md`.

### 7.4 Answer bank
```
resolve(question: Question, profile_id: str, context: ResolveContext) -> AnswerResolution
   # AnswerResolution: {question_fp, source: stored|deterministic|llm|manual, semantic_answer,
   #   serialized_answer, confidence, status: auto|confirm|locked, reasoning}
fingerprint(question: Question) -> str
confirm(question_fp, profile_id, answer, actor)
set_locked(question_fp, profile_id, locked: bool)
switch_profile(profile_id) -> ProfileContext   # atomic namespace swap
```

### 7.5 Session state machine (states, events)
States: `BRIEF_READY → ANSWERS_REVIEWED → RESUME_SELECTED → FORM_FILLED → SUBMITTED` | `ABORTED`.
Events: `SESSION_CREATED, ANSWERS_CONFIRMED, RESUME_CHOSEN, FORM_FILLING, FORM_FILLED, CHECKPOINT_PENDING, HUMAN_SUBMIT, SUBMITTED, ABORTED, OUTCOME_RECORDED`.
Transitions validated by `session/state_machine.py`; every transition emits a `CopilotEvent`.

### 7.6 Browser assistant
```
open(opportunity: CopilotOpportunity, session_id) -> BrowserSession
get_form_model(session_id) -> FormModel   # FormModel: {fields: TypedField[], pages: int, ats_type, auto_fillable: bool}
fill_field(session_id, field_id) -> FieldFill   # {field_id, resolution, filled: bool, confidence, source, reason}
checkpoint(session_id) -> Checkpoint           # {gates_open, pending: [{type, field_id, reason}]}
confirm_checkpoint(session_id, checkpoint_id, action) -> BrowserSession
submit(session_id, human_gesture: bool) -> SubmitResult   # requires human_gesture=true (ADR-002)
degrade_to_guidance(session_id) -> GuidancePlan   # next field + instruction, human types
abort(session_id, reason)
```
Safety invariant: browser is **read-only until final submit**; every action logged to `copilot_browser_actions` (ADR-002, `04_BROWSER_ASSISTANT.md` §Safety).

### 7.7 Copilot events (all subsystems)
```
CopilotEvent: {event_type: str, aggregate_id: str, aggregate_type: str,
  occurred_at: iso, payload: dict, trace_id: str}
```
Emitted → `copilot_events` table + logged. Event types namespaced by subsystem (`opp.*`, `brief.*`, `ans.*`, `ses.*`, `browser.*`, `learn.*`).

### 7.8 Persistence schema (v1) — `copilot.db`
```
copilot_opportunities(id TEXT PK, fingerprint TEXT UNIQUE, source TEXT, source_ref TEXT,
  data_json TEXT, provenance_json TEXT, pipeline_job_id TEXT, status_view TEXT,
  created_at, updated_at, synced_from TEXT)
copilot_sources(opportunity_id, source, raw_ref TEXT, fetched_at, raw_hash TEXT)
copilot_briefs(opportunity_id PK, brief_json TEXT, generated_at, model_used, sections_version)
copilot_answers(question_fp TEXT, profile_id TEXT, canonical_label TEXT, category TEXT,
  source TEXT, semantic_answer TEXT, serialized_answer TEXT, confidence REAL,
  status TEXT, reason TEXT, use_count INT, last_used_at, outcome_quality REAL,
  PRIMARY KEY(question_fp, profile_id))
copilot_sessions(session_id TEXT PK, opportunity_id TEXT, state TEXT, profile_id TEXT,
  resume_id TEXT, brief_snapshot_json, answers_snapshot_json, created_at, updated_at,
  submitted_at, outcome TEXT, outcome_at)
copilot_session_events(session_id, seq, event_type, occurred_at, payload_json)
copilot_browser_actions(id INTEGER PK, session_id, occurred_at, action TEXT, target TEXT,
  field_id TEXT, resolution_json, audit_note TEXT)
copilot_learning_outcomes(opportunity_id, session_id, job_id, provider_id, ats_type,
  resume_profile, outcome TEXT, timestamps_json, created_at)
copilot_learning_weights(key TEXT PK, value_json, updated_at, source TEXT)
copilot_events(event_id INTEGER PK, event_type, aggregate_id, aggregate_type,
  occurred_at, payload_json, trace_id)
```
All writes to `copilot.db` are Copilot-owned; pipeline DBs untouched (ADR-007, ADR-010).

### 7.9 API contract (`api/routers/copilot.py`, mounted at `/api/copilot`)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/copilot/health` | Liveness + subsystem status |
| POST | `/api/copilot/ingest` | Ingest any source payload → opportunity |
| GET | `/api/copilot/opportunities` | List (filters: source, status, query) |
| GET | `/api/copilot/opportunities/{id}` | Detail |
| GET | `/api/copilot/opportunities/{id}/brief` | Brief (build-on-demand, cached) |
| GET | `/api/copilot/answers` · `PUT /api/copilot/answers/{fp}` | Answer bank list/update/confirm |
| POST | `/api/copilot/answers/confirm` · `/lock` | Confirm/lock |
| POST | `/api/copilot/profiles/switch` | Atomic profile switch |
| POST | `/api/copilot/sessions` | Create session |
| GET | `/api/copilot/sessions/{id}` | Session state + events |
| POST | `/api/copilot/sessions/{id}/advance` | Advance state (validated) |
| POST | `/api/copilot/sessions/{id}/abort` | Abort |
| POST | `/api/copilot/browser/open` · `/form` · `/fill/{field}` · `/checkpoint` · `/confirm` · `/submit` · `/guidance` · `/abort` | Assistant control |
| GET | `/api/copilot/history` · `/analytics` | History + analytics |
| GET | `/api/copilot/learning` | Learning overview |

Response convention: `{ok: bool, data?, error?}`; request bodies via Pydantic in `api/schemas.py`.

## 8. Performance & Caching Rules

- Briefs and generated answers are cached; LLM only on cache miss and only for missing/uncertain pieces (AGENTS.md "treat every inference as cost").
- Browser session: one Playwright instance; sessions serialized (no concurrent submissions).
- Polling (UI) ≤ 5s for inbox, ≤ 1s during active session; no busy loops.
- All heavy LLM steps carry budget/cooldown via existing `inference_budget.yaml` and capacity discovery.

## 9. Design Rules (non-negotiable)

1. Normalize-then-execute; assistant never reads raw source-specific DOM logic except inside ATS adapters.
2. Every field the assistant fills has a provenance + confidence.
3. No autonomous submit without a human gesture (default); autopilot is opt-in, per-session, off by default.
4. No new JSON files for state; `copilot.db` is the Copilot source of truth.
5. No duplicate accounting: all pipeline-visible outcomes go through existing APIs.
6. Small, incremental changes; every task independently releasable (see `08_IMPLEMENTATION_PLAN.md`).
