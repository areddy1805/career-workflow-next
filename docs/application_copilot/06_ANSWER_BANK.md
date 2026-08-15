# Universal Answer Bank

**Version:** 1.0.0
**Status:** Approved (ADR-009)

---

## 1. Purpose

One source of truth for "how do I answer this question" across every ATS, every questionnaire, every form. Reuses the pipeline's proven resolution stack (`HybridQuestionResolver`) as the **resolution engine** and `CANDIDATE_EVIDENCE`/`CandidateIntelligence` as the **truth source** (ADR-009). Adds persistence, per-profile namespaces, confirmation workflow, and a learning-quality loop.

## 2. Answer Taxonomy (frozen)

| Class | Stored once? | Generated? | Human confirmation? | Examples |
|---|---|---|---|---|
| **Identity** | ✅ stored (per profile) | never | on create/edit | name, email, phone, address, city |
| **Profile facts** | ✅ stored | never | on change | total experience, CTC, notice period, location, relocation |
| **Per-tech years** | ✅ stored (deterministic rules) | — | only if conflict | `experience.rag_years`, `experience.python_years` |
| **Approved summaries** | ✅ stored (from `approved_answers`) | — | on change | job-change reason, GenAI summary, MLOps summary |
| **Capability binary** | — | ✅ generated from evidence | if `manual_review` | "Have you used Ollama?" → Yes (verified) |
| **Descriptive technical** | — | ✅ generated (cached by fp+profile) | if `manual_review` | "Describe your RAG experience" |
| **Exact-metric claims** | — | ❌ never invented | ✅ always | user counts, ROI, uptime, latency % |
| **Sensitive (PAN/DOB/bank/address)** | 🔒 stored as placeholder | — | ✅ always | PAN, DOB, exact address |
| **Preference/availability** | ✅ stored | — | on change | willing HackerRank, remote, F2F |
| **Combined-technology questions** | — | ✅ generated | ✅ if any part unsupported | "Did you use vLLM/Ollama?" |

## 3. Resolution Order (frozen, mirrors hybrid_resolver)

1. **Stored answer** (exact fingerprint match, profile namespace, status != superseded).
2. **Deterministic resolver** (`questionnaire_resolver.resolve_answer` → constraints → serialize).
3. **Generated LLM** (evidence-grounded; `manual_review` on abstain/low-confidence) — then **cached** by `fingerprint + profile_id`.
4. **Human input** (always authoritative; stored and re-used).

## 4. Fingerprinting

`fingerprint(question) = sha256(normalized_label | normalized_options_keys | kind)[:16]`.
Canonical label extraction maps variant phrasings to a canonical slot (e.g., "How many years of RAG?" → `experience.rag_years`). A `canonical_label` registry lives in `answerbank/canonical.py` and grows from real questionnaires (backlog `12_BACKLOG.md`).

## 5. Personalization & Profile Switching

- **Profiles** = AI, FDE, generic (matches `ResumeRouter`). Each has an isolated answer namespace (`question_fp, profile_id` PK).
- **Profile switching** (`switch_profile`) is atomic: swap namespace + resume mapping; the UI re-renders all resolved values. No cross-profile leakage.
- An answer is promoted from "generated" to "confirmed" when the user confirms it; confirmed answers always win over generated ones (same fp+profile).

## 6. Confirmation Workflow

- Auto-answers: filled silently at confidence ≥ 0.95 (status `auto`).
- Confirmable: `0.80–0.95` or descriptive/LLM → status `confirm` → surfaced in Workspace review step; user confirms → `confirmed`.
- Locked: user pins (status `locked`); never auto-overwritten.
- Overrides are stored as `human` provenance and become the stored answer.

## 7. Learning-Quality Loop (ADR-011)

- Each answer use records the outcome (interview/offer/reject) → `outcome_quality` on `copilot_answers`.
- Confirmed answers that correlate with interviews are weighted up; corrected/abstained answers are pushed toward `manual_review`.
- Deterministic hit-rate grows as confirmed fingerprints accumulate — fewer LLM calls over time (cost + latency win, AGENTS.md).

## 8. Persistence

`copilot_answers` schema (frozen in `02_ARCHITECTURE.md` §7.8). Indexes: `(question_fp, profile_id)`, `status`, `last_used_at`.

## 9. Success Criteria

- Auto-resolve rate ≥ 90% of screening questions across Tier 1/Tier 2.
- Auto-answer correction rate < 5% (user edits auto answers).
- Zero fabricated claims in generated answers (guardrail audit).
- LLM resolution calls decline quarter-over-quarter (caching + stored growth).
