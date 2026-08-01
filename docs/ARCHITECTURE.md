# Application Orchestrator V2 — Architecture

Branch: feature/application-orchestrator-v2
Status: Architecture Freeze

## System Overview

Replaces run_application_batch() with an opportunity-aware scheduler that maximizes interview probability under real-world platform constraints.

### V2 Architecture

Acquisition → Opportunity Repository (Ledger) → Priority Engine (stateless pure function) → Constraint Engine (one class per rule) → Capacity Planner (provider-agnostic) → Application Scheduler (thin executor) → Ledger + Metrics

## Data Flow

Per-run:
1. OpportunityRepository.get_pool() → SCORED + DEFERRED_QUOTA + RESUMED
2. PriorityEngine.rank(pool) → list[(Opportunity, DecisionExplanation)]
3. CapacityPlanner.plan(ranked, CapacityModel, Constraints) → ApplicationPlan
4. ApplicationScheduler.execute(plan) → AUTO/EXTERNAL dispatch + DEFERRED_QUOTA ledger

Cross-run: Old jobs re-enter pool, everything re-ranked. No automatic advantage for old or new.

## Subsystems

- OpportunityRepository: Only interface between engines and ledger. No business logic. Full API: get_pool(for_date), get_deferred(), get_by_company(company, since), count_by_provider(), count_by_company(for_date), count_by_resume(for_date), mark_status(job_id, status, explanation), mark_applied(job_id, explanation), mark_deferred(job_id, explanation), mark_expired(job_id), record_opportunity(job, status).
- PriorityEngine: Pure function. No state/cache/persistence/side effects. Input: list[ApplicationOpportunity]. Output: list[(ApplicationOpportunity, DecisionExplanation)].
- AgePolicy: Configurable decay function. 0-2d:1.0, 3-5d:0.85, 6-10d:0.65, 11-14d:0.40, >14d:expired. Pure function: apply(age_days) -> float.
- ConstraintEngine: Each constraint is one IConstraint class. Built-in: CompanyCapConstraint (max 2/company/day), ResumeMinimumConstraint (AI>=15, FDE>=10), ProviderQuotaConstraint (global budget), AgeExpiryConstraint (>14d discard), QualityConstraint (min score), DuplicateConstraint (no re-apply).
- CapacityPlanner: Provider-agnostic. Knows budget number, never provider name. Iterates ranked pool, evaluates each against constraints, stops when budget exhausted. Produces ApplicationPlan with per-decision DecisionExplanation.
- ApplicationScheduler: Thin AUTO/EXTERNAL/DEFERRED dispatcher. AUTO->process_job_application(), EXTERNAL->manual_action_queue, DEFERRED->ledger.mark_deferred().
- ProviderCapacityDiscovery: Live quota from providers. Never persisted. Calls provider.remaining_quota() if supported, returns None for unlimited providers.

## State Machine (Scheduler Scope)

DISCOVERED → CLASSIFIED → SCORED → ELIGIBLE → PLANNED → APPLYING → APPLIED
                              ↘ DEFERRED_QUOTA → EXPIRED (>14d)

Note: INTERVIEW, REJECTED, OFFER, CLOSED, and TRACKING are application tracking/outcome events reserved for a future interview tracking pipeline. The scheduler only reasons about pre-application and application states.

## Interfaces

IConstraint: evaluate(opportunity, context) → ConstraintResult(allowed: bool, reason: str, constraint_name: str)
DecisionExplanation: final_score(float), components(dict[str, float]), summary(str), applied(bool), deferred_reason(str)
ApplicationOpportunity: job_id(str), provider_id(str), title(str), company(str), score(float), status(str), acquired_at(datetime), last_evaluated(datetime), evaluation_count(int), age_days(float), resume_profile(str), apply_url(str|None), is_external(bool), meta(dict), explanation(str|None)
ApplicationPlan: planned(list[PlannedApplication]), deferred(list[DeferredOpportunity]), summary(ApplicationPlanSummary)
PlannedApplication: opportunity(ApplicationOpportunity), mode(ApplicationMode), explanation(DecisionExplanation)
DeferredOpportunity: opportunity(ApplicationOpportunity), explanation(DecisionExplanation)
ApplicationPlanSummary: total_pool(int), planned(int), deferred(int), expired(int), rejected(int)
CapacityModel: daily_budget(int), company_limit(int=2), resume_minimums(dict), quality_threshold(int=68), max_age_days(int=14)

## Provider Abstraction

| Provider | Mode | Quota | Discovery |
| Naukri | AUTO | 50 | remaining_quota() via API |
| JobSpy | EXTERNAL | None | N/A |
| HiringCafe | EXTERNAL | None | N/A |

## Design Rules

Lifecycle scope: The scheduler lifecycle ends at APPLIED. Post-application tracking (INTERVIEW, REJECTED, OFFER, CLOSED) is reserved for a future interview tracking pipeline and is excluded from the scheduler's state machine.

- No new JSON files. Ledger is truth.
- Quota never persisted. Live-discovered every run.
- Priority Engine is pure function.
- Planner knows budget, never "Naukri".
- One class per constraint.
- Quality-optimized diversity.
- Resume minimums (AI≥15, FDE≥10), surplus to highest score.
- Every decision has DecisionExplanation.
- Adaptive Learning excluded from this branch.

## Commit History

1  docs: ARCHITECTURE.md -- Application Orchestrator V2
2  feat: Opportunity Lifecycle states, events, and data model
3  feat: Opportunity Repository -- abstracted ledger queries
4  feat: Provider Capacity Discovery -- live quota, no persistence
5  feat: Stateless Priority Engine with explainability
6  feat: Constraint Engine -- one class per rule
7  feat: Provider-agnostic Capacity Planner
8  feat: Application Scheduler replaces run_application_batch
9  feat: Planner Decision Report + Application Capacity observability
10 test: 6 production simulation scenarios

## Sequence Diagrams

Main Pipeline Run:
OpportunityRepository.get_pool() -> PriorityEngine.rank() -> CapacityPlanner.plan() -> ApplicationScheduler.execute() -> Ledger

Day-2 Re-Ranking:
OpportunityRepository.get_pool(DEFERRED_QUOTA + SCORED) -> PriorityEngine.rank() (age penalty applied to old jobs) -> 150 opportunities compete re-ranked -> Top 50 applied -> Rest deferred via ledger

## Implementation Order

1. Opportunity Lifecycle (foundation)
2. Opportunity Repository (abstraction)
3. Provider Capacity Discovery (live quota)
4. Priority Engine (pure ranking)
5. Constraint Engine (one class per rule)
6. Capacity Planner (plan builder)
7. Application Scheduler (integration)
8. Observability (metrics + reports)
9. Production Simulation (6 scenarios)
