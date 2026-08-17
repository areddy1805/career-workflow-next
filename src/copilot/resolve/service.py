"""Extension-facing batch field resolver (SLICE 2/3 backbone).

Frozen resolution order (FINAL ADDENDUM §5):
  L0 exact field mapping (fingerprint -> stored answer)
  L1 verified candidate ground truth
  L2 confirmed/locked answer memory
  L3 deterministic aliases/rules (canonical intents + profile facts)
  L4 contextual application policy (recommendation base, SLICE 5 rules)
  L5 semantic LLM inference (career-copilot, ONE batched call per form)
  L6 human review

Safety: legal/identity/sensitive intents never reach the LLM; model
output is validated then marked confirm until user approval; nothing here
mutates ground truth.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any, Callable

from src.copilot.answerbank import fingerprint as fp_mod
from src.copilot.answerbank.store import StoredAnswer, get as answer_get
from src.copilot.canonical import classify
from src.copilot.groundtruth import fillable_field, load_facts, resolve_profile
from src.copilot.inference import llm_blocked

# Intent -> ground-truth fact key (L1) for identity/contact facts.
_FACT_KEYS: dict[str, str] = {
    "identity.first_name": "first_name",
    "identity.last_name": "last_name",
    "identity.full_name": "full_name",
    "contact.email": "email",
    "contact.phone": "phone",
    "contact.city": "city",
    "contact.current_location": "city",
    "contact.country": "country",
    "employment.current_employer": "employer_current",
    "employment.current_designation": "employer_current",
}

# Intent -> candidate_profile key (L3 deterministic profile facts).
_PROFILE_KEYS: dict[str, str] = {
    "employment.total_experience_years": "total_experience_years",
    "compensation.current_salary": "current_ctc_inr",
    "compensation.expected_salary": "expected_ctc_inr",
    "compensation.notice_period": "notice_period_days",
}

# Answer-bank statuses usable without user confirmation.
TRUSTED_ANSWER_STATUSES = ("confirmed", "locked", "auto")


@dataclass
class Field:
    field_id: str
    label: str
    kind: str = "text"
    options: list[str] = field(default_factory=list)
    context: str | None = None
    required: bool = False


@dataclass
class Resolution:
    field_id: str
    intent_id: str | None
    value: Any
    source: str  # L0..L6
    confidence: float
    status: str  # auto | confirm | review
    sensitivity: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "intent_id": self.intent_id,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "status": self.status,
            "sensitivity": self.sensitivity,
            "reason": self.reason,
        }


def _resolve_field_l0_l4(
    f: Field, profile_id: str, mode: str, conn: sqlite3.Connection | None,
    facts: dict[str, Any], profile: dict[str, Any],
) -> Resolution | None:
    """L0..L4 deterministic resolution. Returns None when the field must go
    to L5 (LLM) or L6 (human review)."""
    intent = classify(f.label, f.kind)

    # ---- L0/L2: answer memory (exact fingerprint) -----------------------
    if conn is not None and f.label:
        try:
            q = fp_mod.Question.from_dict(
                {"label": f.label, "options": f.options, "kind": f.kind}
            )
            qfp = fp_mod.fingerprint(q)
        except Exception:
            qfp = None
        if qfp:
            stored = answer_get(conn, qfp, profile_id)
            if stored is not None and stored.status in TRUSTED_ANSWER_STATUSES:
                return Resolution(
                    field_id=f.field_id,
                    intent_id=stored.canonical_label or (intent or {}).get("id"),
                    value=stored.semantic_answer,
                    source="L2_answer_memory",
                    confidence=stored.confidence if stored.confidence is not None else 1.0,
                    status="auto" if stored.status != "auto" else "auto",
                    sensitivity=(intent or {}).get("sensitivity", "NORMAL"),
                    reason=f"Stored answer (status={stored.status}) for fingerprint {qfp[:8]}",
                )
            if stored is not None and stored.status == "confirm":
                return Resolution(
                    field_id=f.field_id,
                    intent_id=stored.canonical_label,
                    value=stored.semantic_answer,
                    source="L2_answer_memory",
                    confidence=stored.confidence or 0.8,
                    status="confirm",
                    sensitivity=(intent or {}).get("sensitivity", "NORMAL"),
                    reason="Stored answer awaiting confirmation",
                )

    # ---- L1: verified ground truth --------------------------------------
    if intent:
        fact_key = _FACT_KEYS.get(intent["id"])
        if fact_key and fact_key in facts:
            fact = facts[fact_key]
            if fact["value"] is not None and fillable_field(fact, mode):
                return Resolution(
                    field_id=f.field_id,
                    intent_id=intent["id"],
                    value=fact["value"],
                    source="L1_ground_truth",
                    confidence=1.0 if fact["tier"] <= 1 else 0.9,
                    status="auto" if fact["tier"] <= 2 else "confirm",
                    sensitivity=fact["sensitivity"],
                    reason=f"{fact['tier_name']} ({fact['status']})",
                )

    # ---- L3: deterministic profile facts --------------------------------
    if intent:
        pkey = _PROFILE_KEYS.get(intent["id"])
        if pkey and pkey in profile:
            val = profile[pkey]
            if val not in (None, ""):
                status = "confirm" if intent["sensitivity"] == "STRATEGIC" else "auto"
                return Resolution(
                    field_id=f.field_id,
                    intent_id=intent["id"],
                    value=val,
                    source="L3_deterministic_profile",
                    confidence=0.9,
                    status=status,
                    sensitivity=intent["sensitivity"],
                    reason=f"candidate_profile.{pkey} (TIER_2 structured)",
                )

    # ---- L4: contextual policy (SLICE 5 base) ---------------------------
    # STRATEGIC intents reach here only when no profile fact maps directly
    # (e.g. joining date, remote, relocation). SLICE 5 adds rule engine.
    if intent and intent["sensitivity"] == "STRATEGIC" and intent["id"] not in _PROFILE_KEYS:
        return Resolution(
            field_id=f.field_id,
            intent_id=intent["id"],
            value=None,
            source="L4_contextual_policy",
            confidence=0.0,
            status="review",
            sensitivity="STRATEGIC",
            reason="Contextual value requires policy recommendation + user decision (SLICE 5)",
        )

    return None


def _llm_batch_schema(fields: list[Field], blocked: list[Field]) -> list[dict[str, Any]]:
    """Structured LLM request for the batch (ADDENDUM §7 classification schema)."""
    return [
        {
            "field_id": f.field_id,
            "question": f.label,
            "kind": f.kind,
            "options": f.options,
        }
        for f in fields
    ]


def resolve_batch(
    fields: list[Field],
    profile_id: str = "ai",
    mode: str = "ASSISTED",
    job_context: dict[str, Any] | None = None,
    conn: sqlite3.Connection | None = None,
    llm: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Resolve all fields. `llm` is injectable for tests; when None and fields
    remain after L0-L4, resolution falls to L6 human review (no fabricated
    answers when inference is unavailable)."""
    facts = load_facts()
    resolved_facts = resolve_profile(profile_id=profile_id)["facts"]
    profile = _profile_for(profile_id)

    resolutions: list[Resolution] = []
    llm_candidates: list[Field] = []
    blocked: list[Field] = []

    for f in fields:
        r = _resolve_field_l0_l4(f, profile_id, mode, conn, resolved_facts, profile)
        if r is not None:
            resolutions.append(r)
            continue
        intent = classify(f.label, f.kind)
        if llm_blocked(intent):
            blocked.append(f)
        else:
            llm_candidates.append(f)

    llm_calls = 0
    if llm_candidates and llm is not None:
        llm_calls = 1  # ADDENDUM §6: maximum 1 LLM inference request per form
        reqs = _llm_batch_schema(llm_candidates, blocked)
        try:
            raw = llm(reqs)
            for item in raw or []:
                fid = item.get("field_id")
                field = next((x for x in llm_candidates if x.field_id == fid), None)
                if field is None:
                    continue
                intent = classify(field.label, field.kind)
                resolutions.append(
                    Resolution(
                        field_id=fid,
                        intent_id=item.get("intent") or (intent or {}).get("id"),
                        value=item.get("draft_answer") or item.get("value"),
                        source="L5_semantic_llm",
                        confidence=float(item.get("confidence", 0.0)),
                        status="confirm" if item.get("requires_review", True) else "confirm",
                        sensitivity=(intent or {}).get("sensitivity", "NORMAL"),
                        reason=f"LLM draft (career-copilot); {item.get('reason_code', '')}".strip(),
                    )
                )
        except Exception as exc:  # noqa: BLE001 — inference failure -> human review
            for f in llm_candidates:
                resolutions.append(
                    Resolution(
                        field_id=f.field_id,
                        intent_id=classify(f.label, f.kind).get("id") if classify(f.label, f.kind) else None,
                        value=None,
                        source="L6_human_review",
                        confidence=0.0,
                        status="review",
                        sensitivity="NORMAL",
                        reason=f"LLM unavailable ({exc}); human review required",
                    )
                )
    else:
        # No LLM available: unknown fields -> human review (never fabricate).
        for f in llm_candidates + blocked:
            intent = classify(f.label, f.kind)
            resolutions.append(
                Resolution(
                    field_id=f.field_id,
                    intent_id=(intent or {}).get("id"),
                    value=None,
                    source="L6_human_review",
                    confidence=0.0,
                    status="review",
                    sensitivity=(intent or {}).get("sensitivity", "NORMAL"),
                    reason="No deterministic resolution and no inference available; human review required",
                )
            )

    summary = {"auto": 0, "confirm": 0, "review": 0}
    for r in resolutions:
        summary[r.status] = summary.get(r.status, 0) + 1
    return {
        "profile_id": profile_id,
        "mode": mode,
        "llm_calls": llm_calls,
        "resolutions": [r.to_dict() for r in resolutions],
        "summary": summary,
    }


def _profile_for(profile_id: str) -> dict[str, Any]:
    from config.candidate_profile import CANDIDATE_PROFILE  # type: ignore

    return CANDIDATE_PROFILE


__all__ = ["Field", "Resolution", "resolve_batch", "TRUSTED_ANSWER_STATUSES"]
