
# JOBSPY_PROVIDER_IMPLEMENTATION_SPEC.md

# Career Workflow 2.0
## JobSpy Provider Integration Specification

**Status:** Completed
**Estimated Effort:** Completed (2–3 Days)
**Primary Goal:** Expand job discovery by integrating JobSpy into the existing acquisition pipeline with minimal architectural changes.

---

# 1. Objective

## Goal

Integrate JobSpy as an additional acquisition provider.

This is **not** an acquisition layer rewrite. We are extending the existing provider model so Career Workflow can acquire jobs from multiple sources while preserving the current pipeline.

## Expected Outcome

- Existing Naukri provider remains untouched.
- JobSpy can be enabled or disabled through configuration.
- Acquired jobs enter the existing pipeline as NormalizedJob objects.
- Ranking, classification, routing, applications and event sourcing continue to work unchanged.

---

# 2. Scope

## In Scope

- JobSpyProvider
- Provider configuration
- Job normalization
- Duplicate handling (lightweight improvements only)
- Acquisition events
- Tests

## Out of Scope

- ATS automation
- Resume changes
- Ranking logic
- Classification logic
- Routing
- Application engine
- Event sourcing redesign

---

# 3. Current vs Target

## Current

CLI
→ Acquisition
→ NaukriProvider
→ Normalization
→ Existing Pipeline

## Target

CLI
→ Acquisition
    → NaukriProvider
    → JobSpyProvider
→ Merge Results
→ Existing Normalization
→ Existing Pipeline

No new AcquisitionManager abstraction should be introduced unless implementation reveals a concrete need.

---

# 4. JobSpy Review

Use JobSpy only for discovery.

Recommended enabled sites:
- Google Jobs
- LinkedIn
- Indeed

Optional:
- Naukri fallback

Do NOT depend on JobSpy for:
- Login
- Applying
- ATS automation
- Session management

---

# 5. Implementation Plan

## Phase 1 – Research & Provider Skeleton

Deliverables:
- Install dependency
- Study returned schema
- Create JobSpyProvider
- Register provider
- Smoke test

Exit Criteria:
- Provider loads successfully.
- Empty search does not crash.

Commit:
feature(jobspy): provider skeleton

---

## Phase 2 – Normalization

Map fields into internal model:

- title
- company
- location
- description
- salary
- url
- source
- posted_date

Missing fields should degrade gracefully.

Exit Criteria:
- NormalizedJob objects created successfully.

Commit:
feature(jobspy): normalization

---

## Phase 3 – Configuration

Add configuration:

providers:
  jobspy:
    enabled: true
    sites:
      - google
      - linkedin
      - indeed
    max_results: 500

Provider must be completely optional.

Exit Criteria:
- Toggle works.
- Existing users unaffected.

Commit:
feature(jobspy): configuration

---

## Phase 4 – Merge & Deduplication

Merge JobSpy and Naukri results.

Reuse existing duplicate logic where possible.

Only enhance if required.

Priority:
1. URL
2. Provider ID
3. Company + Title + Location

Exit Criteria:
- Duplicate jobs removed.
- No duplicate applications possible.

Commit:
feature(jobspy): deduplication

---

## Phase 5 – Testing

Run:

- Unit tests
- Provider tests
- Full acquisition
- Dry run
- Live run

Validate:

- Metrics
- Events
- Job counts
- Pipeline health

Commit:
feature(jobspy): production ready

---

# 6. Acceptance Criteria

- Existing Naukri workflow unchanged.
- JobSpy optional.
- Existing pipeline untouched.
- No duplicate applications.
- Existing tests green.
- Live acquisition successful.

---

# 7. Instructions for Antig

## MUST

- Work phase-by-phase.
- Commit after every phase.
- Run pytest after every phase.
- Run one acquisition after every phase.
- Preserve existing interfaces.
- Keep implementation focused.

## MUST NOT

- Refactor unrelated code.
- Modify ranking.
- Modify classifier.
- Modify routing.
- Modify application engine.
- Rewrite event sourcing.
- Introduce unnecessary abstractions.

If a required architectural change is discovered, stop and document it before implementing.

---

# 8. Future Enhancements (Not Part of This Work)

Possible future providers:

- Greenhouse
- Lever
- Workday
- Ashby
- Company career pages
- RSS feeds
- Public Job APIs

This implementation should make adding future providers straightforward, but no work beyond JobSpy is included in this phase.

---

# Final Deliverables

- JobSpyProvider
- Provider registration
- Configuration support
- Normalization mapping
- Merge with existing acquisition
- Deduplication validation
- Automated tests
- Updated documentation

**Success Definition:** A user can enable JobSpy in configuration, run the existing acquisition pipeline, and receive additional normalized jobs from Google Jobs, LinkedIn, and Indeed without changing any downstream pipeline behavior.
