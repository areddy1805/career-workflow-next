"""Career Application Copilot extension API — /api/v1 (CP-0-05).

Owned by the extension. Auth: require_ext_token (loopback + bearer +
chrome-extension Origin). Never logs tokens. Endpoints added per slice:
S1 auth/config/profile/evidence/resumes; S2+ resolve/answers/policies/etc.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from src.copilot.auth import require_ext_token, require_loopback, pair
from src.copilot.groundtruth import (
    is_placeholder,
    resolve_profile,
    sha256_file,
    source_artifact,
)

router = APIRouter(prefix="/v1", tags=["copilot-ext"])


def _err(message: str, error_type: str) -> dict[str, Any]:
    return {"error": {"type": error_type, "message": message}}


@router.get("/health", dependencies=[Depends(require_loopback)])
def ext_health() -> dict[str, Any]:
    return {"status": "ok", "service": "career-application-copilot", "version": "0.1.0"}


@router.post("/auth/pair", dependencies=[Depends(require_loopback)])
def ext_pair() -> dict[str, Any]:
    """Pair: returns (or rotates) the bearer token. Called once from the
    extension onboarding flow; token persisted by the extension only."""
    return {"token": pair(), "note": "store locally; never share"}


@router.get("/config", dependencies=[Depends(require_ext_token)])
def ext_config() -> dict[str, Any]:
    """Runtime config for the extension: fill thresholds, modes, versions."""
    return {
        "intents_version": 1,
        "ground_truth_sha256": source_artifact().get("sha256"),
        "fill_modes": {
            "SAFE": {"sensitivities": ["LOW", "NORMAL"], "max_tier": 2},
            "ASSISTED": {"sensitivities": ["LOW", "NORMAL", "STRATEGIC"], "max_tier": 2},
            "FULL": {"sensitivities": ["LOW", "NORMAL", "STRATEGIC"], "max_tier": 2},
        },
        "confidence": {"auto_fill_min": 0.95, "confirm_min": 0.80, "hard_floor": 0.0},
        "high_risk_policy": "never_auto_fill_unless_tier_0",
        "offline": {"mirror_ttl_seconds": 86400, "answers_ttl_seconds": 604800},
    }


@router.get("/profile", dependencies=[Depends(require_ext_token)])
def ext_profile(profile_id: str = "ai") -> dict[str, Any]:
    """Canonical candidate ground truth view with conflicts + verification gates."""
    if profile_id not in ("ai", "fde", "generic"):
        raise HTTPException(status_code=422, detail="unknown profile_id")
    return resolve_profile(profile_id=profile_id)


@router.get("/evidence", dependencies=[Depends(require_ext_token)])
def ext_evidence() -> dict[str, Any]:
    """Candidate evidence summary (certifications, projects, guardrails,
    unsupported claims, sensitive policy). Compact, no raw claim dumps."""
    from config.candidate_evidence import CANDIDATE_EVIDENCE  # type: ignore

    ce = CANDIDATE_EVIDENCE
    try:
        return {
            "professional_profile": ce.get("professional_profile"),
            "certifications": ce.get("certifications", []),
            "projects": list(ce.get("projects", {}).keys()),
            "capability_summary": {
                k: v.get("status") for k, v in (ce.get("capabilities") or {}).items()
            },
            "approved_answers": (ce.get("approved_answers") or {}),
            "positionable_claims": list((ce.get("positionable_claims") or {}).keys()),
            "unsupported_claims": (ce.get("unsupported_claims") or {}).get("never_invent", []),
            "sensitive_information": (ce.get("sensitive_information") or {}),
            "llm_policy": ce.get("llm_policy"),
        }
    except Exception:  # noqa: BLE001 — evidence format may vary; never fail the API
        return {"error": "evidence_unavailable", "message": "candidate_evidence shape changed"}


@router.get("/resumes", dependencies=[Depends(require_ext_token)])
def ext_resumes() -> dict[str, Any]:
    """Resume registry with freshness + sha256 per profile."""
    import yaml

    root = Path(__file__).resolve().parents[2]  # repo root
    reg_path = root / "config" / "resumes.yaml"
    if not reg_path.is_file():
        raise HTTPException(status_code=500, detail="resumes.yaml missing")
    reg = yaml.safe_load(reg_path.read_text(encoding="utf-8")) or {}
    out: dict[str, Any] = {"profiles": {}}
    for profile, entry in reg.items():
        rel = entry.get("path")
        if not rel:
            out["profiles"][profile] = {"status": "MISSING", "path": None}
            continue
        abs_path = root / rel
        if not abs_path.is_file():
            out["profiles"][profile] = {"status": "MISSING", "path": rel}
            continue
        stat = abs_path.stat()
        out["profiles"][profile] = {
            "status": "AVAILABLE",
            "path": rel,
            "sha256": sha256_file(abs_path),
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
        }
    return out


@router.post("/resolve", dependencies=[Depends(require_ext_token)])
def ext_resolve(payload: dict[str, Any]) -> dict[str, Any]:
    """Batch field/question resolution (SLICE 2/3).

    Body: {profile_id, mode, fields: [{field_id, label, kind, options,
    required, context}], job_context?}
    Frozen order L0..L6; max 1 LLM call per form. Never mutates ground truth.
    """
    from src.copilot.resolve import Field, resolve_batch
    from src.copilot.answerbank import fingerprint as fp_mod

    profile_id = payload.get("profile_id", "ai")
    mode = payload.get("mode", "ASSISTED")
    if profile_id not in ("ai", "fde", "generic"):
        raise HTTPException(status_code=422, detail="unknown profile_id")
    if mode not in ("SAFE", "ASSISTED", "FULL"):
        raise HTTPException(status_code=422, detail="unknown fill mode")

    fields = [
        Field(
            field_id=f["field_id"],
            label=f.get("label", ""),
            kind=f.get("kind", "text"),
            options=f.get("options", []),
            context=f.get("context"),
            required=f.get("required", False),
        )
        for f in payload.get("fields", [])
    ]
    if not fields:
        raise HTTPException(status_code=422, detail="no fields provided")

    conn = None
    try:
        from src.copilot.db.db import open_copilot_db

        conn = open_copilot_db()
    except Exception:  # noqa: BLE001 — resolution still works without answer bank
        conn = None

    llm = None
    try:
        from src.copilot.resolve.llm_batch import default_batch_llm

        llm = default_batch_llm()
    except Exception:  # noqa: BLE001 — no LLM -> human review fallback
        llm = None

    return resolve_batch(
        fields=fields,
        profile_id=profile_id,
        mode=mode,
        job_context=payload.get("job_context"),
        conn=conn,
        llm=llm,
    )


@router.get("/answers", dependencies=[Depends(require_ext_token)])
def ext_answers(profile_id: str = "ai", limit: int = 100) -> dict[str, Any]:
    """Stored answer memory for a profile (SLICE 3)."""
    from src.copilot.answerbank.store import list_answers
    from src.copilot.db.db import open_copilot_db

    conn = open_copilot_db()
    rows = list_answers(conn, profile_id=profile_id, limit=limit)
    return {"profile_id": profile_id, "answers": [r.to_dict() for r in rows]}


@router.put("/answers", dependencies=[Depends(require_ext_token)])
def ext_answer_upsert(payload: dict[str, Any]) -> dict[str, Any]:
    """Save a reusable answer (user-approved only; explicit confirmation by
    the extension before calling this)."""
    from src.copilot.answerbank.fingerprint import Question, fingerprint
    from src.copilot.answerbank.store import StoredAnswer, save
    from src.copilot.db.db import open_copilot_db

    label = payload.get("label", "")
    profile_id = payload.get("profile_id", "ai")
    if not label:
        raise HTTPException(status_code=422, detail="label required")
    q = Question.from_dict(
        {
            "label": label,
            "options": payload.get("options", []),
            "kind": payload.get("kind", "text"),
        }
    )
    qfp = fingerprint(q)
    conn = open_copilot_db()
    answer = StoredAnswer(
        question_fp=qfp,
        profile_id=profile_id,
        canonical_label=payload.get("intent_id"),
        category=payload.get("category", "question"),
        source=payload.get("source", "manual"),
        semantic_answer=payload.get("value"),
        serialized_answer=payload.get("serialized_value"),
        confidence=payload.get("confidence", 1.0),
        status=payload.get("status", "confirmed"),
        reason=payload.get("reason", "user-approved reusable answer"),
    )
    saved = save(conn, answer)
    return {"question_fp": qfp, "answer": saved.to_dict()}


@router.post("/answers/{question_fp}/confirm", dependencies=[Depends(require_ext_token)])
def ext_answer_confirm(question_fp: str, profile_id: str = "ai") -> dict[str, Any]:
    """Confirm a stored answer (promotes status -> confirmed)."""
    import dataclasses

    from src.copilot.answerbank.store import get, save
    from src.copilot.db.db import open_copilot_db

    conn = open_copilot_db()
    stored = get(conn, question_fp, profile_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="answer not found")
    updated = dataclasses.replace(stored, status="confirmed", reason="user_confirmed")
    save(conn, updated)
    return {"question_fp": question_fp, "status": "confirmed"}


@router.post("/answers/{question_fp}/lock", dependencies=[Depends(require_ext_token)])
def ext_answer_lock(question_fp: str, profile_id: str = "ai") -> dict[str, Any]:
    """Lock a stored answer (pinned; never auto-overwritten)."""
    import dataclasses

    from src.copilot.answerbank.store import get, save
    from src.copilot.db.db import open_copilot_db

    conn = open_copilot_db()
    stored = get(conn, question_fp, profile_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="answer not found")
    updated = dataclasses.replace(stored, status="locked", reason="user_locked")
    save(conn, updated)
    return {"question_fp": question_fp, "status": "locked"}


__all__ = ["router"]


# ------------------------------------------------------------------ SLICE 5
# Contextual value policy + submitted field values. Owned by this slice only:
# no session/event/ledger endpoints here (parent agent owns those).
# Idempotency key for submitted values: (session_id, job_id, field_intent).


@router.get("/policies", dependencies=[Depends(require_ext_token)])
def ext_policies(profile_id: str = "ai") -> dict[str, Any]:
    """List field value policies (active + draft) for a profile (SLICE 5).

    Seed profile policies (config/policy_rules.yaml) are merged in as active;
    DB rows carry learned drafts and user-activated policies.
    """
    from src.copilot.db.db import open_copilot_db
    from src.copilot.policy.loader import seed_policies
    from src.copilot.policy.store import list_policies

    conn = open_copilot_db()
    try:
        merged: dict[str, dict[str, Any]] = {
            p.policy_id: p.to_dict() for p in seed_policies(profile_id=profile_id)
        }
        for p in list_policies(conn, profile_id=profile_id):
            merged[p.policy_id] = p.to_dict()
        ordered = sorted(
            merged.values(),
            key=lambda p: (p["status"] != "active", p["created_at"] or ""),
        )
        return {"profile_id": profile_id, "policies": ordered}
    finally:
        conn.close()


@router.get("/policies/recommend", dependencies=[Depends(require_ext_token)])
def ext_recommend(
    request: Request, field_intent: str, profile_id: str = "ai"
) -> dict[str, Any]:
    """Contextual value recommendation (SLICE 5, resolution layer L4).

    job_context is built from the remaining query params (e.g.
    job_priority=high, company_type=startup, remote_required=true).
    """
    from src.copilot.db.db import open_copilot_db
    from src.copilot.policy.engine import recommend

    job_context = {
        k: v
        for k, v in request.query_params.items()
        if k not in ("field_intent", "profile_id")
    }
    conn = open_copilot_db()
    try:
        return recommend(field_intent, profile_id, job_context, conn)
    finally:
        conn.close()


@router.post(
    "/policies/{policy_id}/activate", dependencies=[Depends(require_ext_token)]
)
def ext_activate_policy(policy_id: str) -> dict[str, Any]:
    """Explicit user activation of a draft policy: draft -> active only."""
    from src.copilot.db.db import open_copilot_db
    from src.copilot.exceptions import PolicyStateError
    from src.copilot.policy.loader import seed_policies
    from src.copilot.policy.store import activate_policy

    if any(p.policy_id == policy_id for p in seed_policies()):
        raise HTTPException(
            status_code=409, detail=f"seed policy {policy_id} is already active"
        )
    conn = open_copilot_db()
    try:
        try:
            updated = activate_policy(conn, policy_id)
        except PolicyStateError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        if updated is None:
            raise HTTPException(status_code=404, detail="policy not found")
        return {
            "policy_id": policy_id,
            "status": updated.status,
            "activated_at": updated.activated_at,
        }
    finally:
        conn.close()


@router.post("/field-values", dependencies=[Depends(require_ext_token)])
def ext_record_field_value(payload: dict[str, Any]) -> dict[str, Any]:
    """Record a submitted field value (append-only evidence, idempotent).

    Idempotency key: (session_id, job_id, field_intent). Re-POSTing the same
    key returns the original row id and inserts nothing.
    """
    missing = [
        k
        for k in ("session_id", "job_id", "field_intent", "submitted_value")
        if not payload.get(k)
    ]
    if missing:
        raise HTTPException(
            status_code=422, detail=f"missing fields: {', '.join(missing)}"
        )
    from src.copilot.db.db import open_copilot_db
    from src.copilot.policy.store import record_submitted

    conn = open_copilot_db()
    try:
        row_id = record_submitted(
            field_intent=payload["field_intent"],
            profile_id=payload.get("profile_id", "ai"),
            session_id=payload["session_id"],
            job_id=payload["job_id"],
            recommended=payload.get("recommended_value"),
            source=payload.get("recommendation_source"),
            confidence=payload.get("confidence"),
            user_override=payload.get("user_override"),
            submitted=payload["submitted_value"],
            outcome=payload.get("outcome"),
            conn=conn,
            job_context=payload.get("job_context"),
        )
        return {"id": row_id, "field_intent": payload["field_intent"]}
    finally:
        conn.close()


@router.get(
    "/field-values/{field_intent}/history", dependencies=[Depends(require_ext_token)]
)
def ext_field_value_history(
    field_intent: str, profile_id: str = "ai"
) -> dict[str, Any]:
    """Chronological submitted values for one field intent (append-only evidence)."""
    from src.copilot.db.db import open_copilot_db
    from src.copilot.policy.store import history

    conn = open_copilot_db()
    try:
        return {
            "field_intent": field_intent,
            "profile_id": profile_id,
            "values": history(conn, field_intent, profile_id),
        }
    finally:
        conn.close()
