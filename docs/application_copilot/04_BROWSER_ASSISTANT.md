# Browser Assistant

**Version:** 1.0.0
**Status:** Approved (ADR-002, ADR-003, ADR-005)

---

## 1. Role & Thesis

The Browser Assistant is the **delivery vehicle**, not the product. It operates **only on a normalized `CopilotOpportunity`** (ADR-005). Its job: take the user from "open apply URL" to "human submits" in under 30 seconds of human effort — by filling every field it can truthfully resolve, and pausing precisely where it cannot.

**It never submits without a human gesture** (ADR-002). It is a **local backend agent** — Playwright driven by the FastAPI process, launching a **visible browser the human can take over at any moment** (ADR-003).

## 2. Capabilities

- Open `apply_url` in a controlled visible browser (Chromium via Playwright).
- Build a **typed form model** from the DOM (see §4).
- Resolve each field against the **Answer Bank** → typed, confidence-scored value.
- Pre-fill high-confidence fields; stage lower-confidence fields for the review checkpoint.
- Raise **checkpoints** at safety gates (upload, submit, sensitive fields, unexpected pages).
- Fill multi-page forms; track progress across pages.
- Recover from DOM drift (rescan, retry with backoff, guidance mode).
- **Guidance mode**: show the human the next field + suggested answer; human types it. Still <30s.
- Full audit log of every action.

## 3. Limitations (accepted, not defects)

| Limitation | Handling |
|---|---|
| Workday/Rippling anti-bot, CAPTCHA | Assist/guidance only (Tier 3). Never fight CAPTCHA. |
| Dynamically shifted DOM | Rebuild form model; recover; else guidance mode. |
| Complex file-upload dialogs | Checkpoint before any upload; user confirms. |
| LinkedIn auto-submit | Explicit non-goal. |
| SSO/email-verify flows | Detect → checkpoint → guidance. |

## 4. Form Understanding

- **Input**: DOM snapshot + accessibility tree.
- **Field extraction** (`browser/form/model.py`): structural heuristics (label→input via aria/label/for, placeholder, name/id) → typed fields:
  `TypedField {field_id, kind: text|number|date|select|radio|checkbox|textarea|upload|email|phone|url, label, name, options[], required, page, confidence}`
- **ATS adapters (optimizations only)**: Greenhouse/Lever/Ashby provide known field semantics for speed and accuracy; if an adapter is missing/stale, generic extraction is the fallback — the assistant is **never blocked** on an adapter (ADR-005).
- **Multi-page**: page detection via URL change/DOM swap; form model accumulates across pages.

## 5. Field → Answer Resolution

`browser/resolver.py`:
1. Normalize label → **question fingerprint** (same fingerprinting as Answer Bank).
2. `answerbank.resolve(question, profile, {kind, options, required})`.
3. Type-match: convert semantic answer to the field kind (select→option id, radio→value, date→iso, checkbox→multi).
4. Output `FieldFill {field_id, resolution, filled: bool, confidence, source, reason}`.

## 6. Confidence Thresholds (frozen)

| Confidence | Behavior |
|---|---|
| ≥ 0.95, non-sensitive | Fill silently |
| 0.80 – 0.95 | Fill + flag for review at checkpoint |
| < 0.80 | Do not fill; raise inline question |
| Any sensitive field (PAN/DOB/address/bank) | Never auto-fill; always ask |
| `manual_review` answer | Never fill; ask |
| Unknown field (no fingerprint) | Skip; surface in review list |

## 7. Human-in-the-Loop Workflow

```
open → form model → fill pass → CHECKPOINT 1 (review flagged fills)
      → fill remaining → CHECKPOINT 2 (before upload / sensitive)
      → CHECKPOINT 3 (before submit: human gesture REQUIRED)
      → submit → outcome parse → capture
Esc / takeover → user takes the wheel, assistant annotates
```

Checkpoints are always dismissible; the human can override any field value.

## 8. Architecture (subsystem)

| Module | Responsibility |
|---|---|
| `browser/controller.py` | Playwright session lifecycle, visible browser, launch/teardown, takeover |
| `browser/form/model.py` | DOM → `FormModel` (typed fields, pages) |
| `browser/resolver.py` | field → fingerprint → answer resolution |
| `browser/checkpoint.py` | gate engine + checkpoint state |
| `browser/recovery.py` | DOM rescan, retry/backoff, guidance fallback |
| `browser/adapters/{greenhouse,lever,ashby}.py` | ATS field semantics (optimizations) |
| `browser/safety.py` | read-only-until-submit invariant, PII rules, action audit |
| `browser/guidance.py` | guidance-mode plan (next field + instruction) |

## 9. Recovery

- DOM drift → rebuild form model → re-run resolver for remaining fields.
- Playwright crash → relaunch browser → reopen URL → restore from session snapshot.
- Timeout → guidance mode with remaining plan.
- CAPTCHA detected → never attempt; checkpoint + guidance.
- Kill-switch: `Esc` or `/api/copilot/browser/abort` at any time.

## 10. Safety (non-negotiable)

1. Read-only until final submit; no blind clicks.
2. Human gesture required for submit (default); autopilot is opt-in per session.
3. No PII typed without confirmation.
4. No automated retries after a rejection/failure page.
5. Every action recorded in `copilot_browser_actions` with audit note.
6. No fighting anti-bot; degrade gracefully.
7. No autonomous LinkedIn/Workday submission (ADR-004).

## 11. Success Criteria (browser)

- Tier 1/Tier 2 field auto-fill rate ≥ 85%; median human time to submit < 30s.
- Checkpoint correctness: assistant never submits with a `manual_review` field blank.
- Recovery: DOM-drift → guidance mode within one retry.
- Audit: 100% of filled fields have provenance + confidence + audit row.
