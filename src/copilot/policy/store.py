"""SLICE 5 policy + submitted field values store.

Two invariants from the product directive:

1. Submitted values are APPEND-ONLY immutable evidence. There is no UPDATE or
   DELETE on ``application_field_values`` rows; a correction inserts a NEW row
   whose ``supersedes`` column points at the superseded row id. Learning never
   averages submissions into ground truth — ground truth is never mutated here.

2. Idempotency key: (session_id, job_id, field_intent) on PRIMARY submissions
   (``supersedes IS NULL``), enforced by the partial unique index
   ``idx_afv_submission_key``. ``record_submitted`` returns the existing row id
   when the key is already present instead of inserting a duplicate. Correction
   rows carry ``supersedes`` and therefore do not collide with the key.

Learning output is always a DRAFT ``FieldValuePolicy`` (status='draft'); drafts
are never auto-activated. ``activate_policy`` is the only draft -> active
transition and requires an explicit user action.
"""

import hashlib
import json
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from src.copilot.exceptions import PolicyStateError

#: Subset of submissions that counts as a learned pattern (directive).
MIN_BUCKET_ROWS = 5
MIN_DOMINANT_SHARE = 0.8  # strictly more than 80% of bucket submissions

POLICY_STATUSES = ("draft", "active", "disabled")
RULE_SOURCES = ("profile_policy", "learned_suggestion")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bucket_key(ctx: dict[str, Any] | None) -> str:
    """Canonical bucket key for a job context (condition syntax: k=v joined by &)."""
    if not ctx:
        return ""
    return "&".join(f"{k}={v}" for k, v in sorted(ctx.items()))


@dataclass(frozen=True)
class PolicyRule:
    """One rule inside a FieldValuePolicy.

    ``condition`` uses the ``key=value`` syntax, multiple conjuncts joined by
    ``&`` (e.g. ``job_priority=high&remote_required=true``). An empty condition
    matches any application context.
    ``recommended_value`` may be null when the rule resolves its value at
    runtime via ``recommended_from`` (e.g. ``profile.notice_period_days``).
    """

    condition: str
    recommended_value: str | None = None
    recommended_from: str | None = None
    rationale: str | None = None
    source: str = "profile_policy"
    created_from_override_pattern: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["created_from_override_pattern"] = bool(d["created_from_override_pattern"])
        return d


@dataclass(frozen=True)
class FieldValuePolicy:
    """One ``field_value_policies`` row (frozen shape)."""

    policy_id: str
    field_intent: str
    profile_id: str
    status: str = "draft"
    ground_truth_ref: str | None = None
    rules_json: str = "[]"
    stats_json: str | None = None
    created_at: str | None = None
    activated_at: str | None = None

    def rules(self) -> list[PolicyRule]:
        try:
            raw = json.loads(self.rules_json or "[]")
        except json.JSONDecodeError:
            return []
        return [_rule_from_dict(r) for r in raw if isinstance(r, dict)]

    def to_dict(self) -> dict[str, Any]:
        try:
            stats = json.loads(self.stats_json) if self.stats_json else None
        except json.JSONDecodeError:
            stats = None
        return {
            "policy_id": self.policy_id,
            "field_intent": self.field_intent,
            "profile_id": self.profile_id,
            "ground_truth_ref": self.ground_truth_ref,
            "status": self.status,
            "rules": [r.to_dict() for r in self.rules()],
            "stats": stats,
            "created_at": self.created_at,
            "activated_at": self.activated_at,
        }

    @classmethod
    def from_row(cls, row: Any) -> "FieldValuePolicy":
        return cls(**{k: row[k] for k in cls.__dataclass_fields__})


def _rule_from_dict(d: dict[str, Any]) -> PolicyRule:
    kwargs = {
        k: d.get(k)
        for k in (
            "condition",
            "recommended_value",
            "recommended_from",
            "rationale",
            "source",
            "created_from_override_pattern",
        )
    }
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    return PolicyRule(**kwargs)


# ---------------------------------------------------------------- policies


def save_policy(conn: sqlite3.Connection, policy: FieldValuePolicy) -> FieldValuePolicy:
    """Insert (or replace) one policy row; returns the persisted policy."""
    conn.execute(
        """
        INSERT INTO field_value_policies
            (policy_id, field_intent, profile_id, ground_truth_ref, rules_json,
             stats_json, status, created_at, activated_at)
        VALUES (:policy_id, :field_intent, :profile_id, :ground_truth_ref,
                :rules_json, :stats_json, :status, :created_at, :activated_at)
        ON CONFLICT(policy_id) DO UPDATE SET
            rules_json = excluded.rules_json,
            stats_json = excluded.stats_json
        """,
        {
            "policy_id": policy.policy_id,
            "field_intent": policy.field_intent,
            "profile_id": policy.profile_id,
            "ground_truth_ref": policy.ground_truth_ref,
            "rules_json": policy.rules_json,
            "stats_json": policy.stats_json,
            "status": policy.status,
            "created_at": policy.created_at,
            "activated_at": policy.activated_at,
        },
    )
    conn.commit()
    return policy


def get_policy(conn: sqlite3.Connection, policy_id: str) -> FieldValuePolicy | None:
    row = conn.execute(
        "SELECT * FROM field_value_policies WHERE policy_id = ?", (policy_id,)
    ).fetchone()
    return FieldValuePolicy.from_row(row) if row else None


def list_policies(
    conn: sqlite3.Connection,
    *,
    profile_id: str | None = None,
    status: str | None = None,
) -> list[FieldValuePolicy]:
    clauses: list[str] = []
    params: list[Any] = []
    if profile_id is not None:
        clauses.append("profile_id = ?")
        params.append(profile_id)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM field_value_policies {where} ORDER BY created_at", params
    ).fetchall()
    return [FieldValuePolicy.from_row(r) for r in rows]


def activate_policy(
    conn: sqlite3.Connection, policy_id: str
) -> FieldValuePolicy | None:
    """Explicit user activation: draft -> active only. Never touches ground truth.

    Returns the updated policy, None when the policy does not exist, and raises
    :class:`PolicyStateError` when the policy is not in draft status.
    """
    policy = get_policy(conn, policy_id)
    if policy is None:
        return None
    if policy.status != "draft":
        raise PolicyStateError(
            "policy {} has status '{}'; only draft can be activated".format(
                policy_id, policy.status
            )
        )
    activated_at = _now_iso()
    conn.execute(
        "UPDATE field_value_policies SET status = 'active', activated_at = ? "
        "WHERE policy_id = ?",
        (activated_at, policy_id),
    )
    conn.commit()
    return FieldValuePolicy.from_row(
        conn.execute(
            "SELECT * FROM field_value_policies WHERE policy_id = ?", (policy_id,)
        ).fetchone()
    )


# ----------------------------------------------------- submitted field values


def record_submitted(
    field_intent: str,
    profile_id: str,
    session_id: str,
    job_id: str,
    recommended: Any,
    source: str | None,
    confidence: float | None,
    user_override: Any,
    submitted: Any,
    outcome: Any = None,
    conn: sqlite3.Connection | None = None,
    *,
    job_context: dict[str, Any] | None = None,
    supersedes: int | None = None,
) -> int:
    """Append a submitted value (evidence). Returns the row id.

    Idempotency key: (session_id, job_id, field_intent) for PRIMARY submissions
    (supersedes IS NULL). When a row already exists for the key, that row id is
    returned and nothing is inserted. Corrections pass ``supersedes=<old id>``:
    a new evidence row is appended and the old row is never modified.
    """
    if conn is None:
        raise ValueError("record_submitted requires conn")
    ctx = json.dumps(job_context, sort_keys=True) if job_context is not None else None
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO application_field_values
            (session_id, job_id, field_intent, recommended_value,
             recommendation_source, confidence, user_override, submitted_value,
             outcome, profile_id, job_context_json, created_at, supersedes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            job_id,
            field_intent,
            str(recommended) if recommended is not None else None,
            source,
            confidence,
            str(user_override) if user_override is not None else None,
            str(submitted),
            outcome,
            profile_id,
            ctx,
            _now_iso(),
            supersedes,
        ),
    )
    conn.commit()
    if cur.rowcount == 1:
        # Fresh insert: the id of THIS evidence row (primary or correction).
        return int(cur.lastrowid)
    # Duplicate of the idempotency key: return the existing primary row.
    row = conn.execute(
        "SELECT id FROM application_field_values "
        "WHERE session_id = ? AND job_id = ? AND field_intent = ? "
        "AND supersedes IS NULL",
        (session_id, job_id, field_intent),
    ).fetchone()
    if row is None:
        raise ValueError("duplicate submission key without primary row")
    return int(row["id"])


def history(
    conn: sqlite3.Connection, field_intent: str, profile_id: str
) -> list[dict[str, Any]]:
    """Chronological submitted values (append-only evidence) for one profile."""
    rows = conn.execute(
        "SELECT * FROM application_field_values "
        "WHERE field_intent = ? AND profile_id = ? ORDER BY id",
        (field_intent, profile_id),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            raw_ctx = d.pop("job_context_json")
            d["job_context"] = json.loads(raw_ctx) if raw_ctx else None
        except json.JSONDecodeError:
            d["job_context"] = None
        out.append(d)
    return out


# ---------------------------------------------------------------- learning


def analyze_history(
    conn: sqlite3.Connection, field_intent: str, profile_id: str
) -> FieldValuePolicy | None:
    """Scan submitted evidence; produce a DRAFT policy when a pattern holds.

    Pattern (directive): >= 5 rows share the same job_context bucket AND the
    same submitted value AND that value was used by >80% of the bucket's
    submissions. Only current evidence counts (rows that are not themselves
    superseded by a later correction — the old evidence row is never counted).
    The resulting draft is status='draft', source
    'learned_suggestion', created_from_override_pattern=true. Drafts are never
    auto-activated; the bucket stats land in ``stats_json``.

    Deterministic policy_id from (field_intent, profile_id, bucket), so
    re-analysis returns the existing policy instead of duplicating it.
    """
    rows = conn.execute(
        "SELECT id, job_context_json, submitted_value FROM application_field_values "
        "WHERE field_intent = ? AND profile_id = ? "
        "AND id NOT IN (SELECT supersedes FROM application_field_values "
        "               WHERE supersedes IS NOT NULL) "
        "ORDER BY id",
        (field_intent, profile_id),
    ).fetchall()
    buckets: dict[str, dict[str, Any]] = {}
    for r in rows:
        try:
            ctx = json.loads(r["job_context_json"]) if r["job_context_json"] else {}
        except json.JSONDecodeError:
            ctx = {}
        if not isinstance(ctx, dict):
            ctx = {}
        key = _bucket_key(ctx)
        bucket = buckets.setdefault(key, {"context": ctx, "values": Counter()})
        bucket["values"][str(r["submitted_value"])] += 1

    for key, bucket in buckets.items():
        total = sum(bucket["values"].values())
        if total < MIN_BUCKET_ROWS:
            continue
        dominant, count = bucket["values"].most_common(1)[0]
        share = count / total
        if share <= MIN_DOMINANT_SHARE:
            continue
        policy_id = _learned_policy_id(field_intent, profile_id, key)
        existing = get_policy(conn, policy_id)
        if existing is not None:
            return existing
        rationale = (
            f"Learned from {count}/{total} submissions in job-context bucket "
            f"'{key or 'any'}': '{dominant}' used in {share:.0%} of them. "
            "Draft only; explicit user activation required."
        )
        rule = PolicyRule(
            condition=key,
            recommended_value=dominant,
            rationale=rationale,
            source="learned_suggestion",
            created_from_override_pattern=True,
        )
        stats = {
            "bucket_key": key,
            "bucket_context": bucket["context"],
            "bucket_size": total,
            "dominant_value": dominant,
            "count": count,
            "share": round(share, 4),
            "analyzed_at": _now_iso(),
        }
        policy = FieldValuePolicy(
            policy_id=policy_id,
            field_intent=field_intent,
            profile_id=profile_id,
            status="draft",
            ground_truth_ref=_ground_truth_ref(field_intent),
            rules_json=json.dumps([rule.to_dict()], sort_keys=True),
            stats_json=json.dumps(stats, sort_keys=True),
            created_at=_now_iso(),
        )
        save_policy(conn, policy)
        return policy
    return None


def _learned_policy_id(field_intent: str, profile_id: str, bucket_key: str) -> str:
    digest = hashlib.sha1(bucket_key.encode("utf-8")).hexdigest()[:8]
    return f"learned_{profile_id}_{field_intent}_{digest}"


def _ground_truth_ref(field_intent: str) -> str | None:
    """Best-effort ground_truth_ref for a field intent (may be None)."""
    return {
        "compensation.notice_period": "notice_period_days",
        "compensation.notice_period_negotiable": "notice_period_days",
        "compensation.current_salary": "current_ctc_inr",
        "compensation.expected_salary": "expected_ctc_inr",
    }.get(field_intent)


__all__ = [
    "FieldValuePolicy",
    "PolicyRule",
    "POLICY_STATUSES",
    "RULE_SOURCES",
    "save_policy",
    "get_policy",
    "list_policies",
    "activate_policy",
    "record_submitted",
    "history",
    "analyze_history",
]
