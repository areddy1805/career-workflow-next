"""Unit tests for CP-5-04: checkpoint engine (04 §6/§7).

Contract: the frozen §6 decision matrix per fill; the §7 three-checkpoint
sequence (review flagged → before upload/sensitive → before submit, human
gesture REQUIRED); never bypass submit (AC). Pure unit tests — FieldFill
built directly, no browser/DB.

DoD: gate matrix green (08 CP-5-04).
"""

import pytest

from src.copilot.browser.checkpoint import (
    FLAG_FILL_CONFIDENCE,
    SILENT_FILL_CONFIDENCE,
    CheckpointEngine,
    CheckpointError,
    CheckpointType,
    PendingItem,
    build_checkpoints,
    categorize,
    fill_action,
)
from src.copilot.browser.form.model import FieldKind
from src.copilot.browser.resolver import FieldFill


def fill(field_id="f1", confidence=1.0, source="stored", status="auto"):
    return FieldFill(
        field_id=field_id,
        resolution={"status": status, "semantic_answer": "v", "typed_value": "v"},
        filled=confidence is not None and confidence >= FLAG_FILL_CONFIDENCE,
        confidence=confidence,
        source=source,
        reason="test",
    )


KINDS = {
    "f1": FieldKind.TEXT,
    "f2": FieldKind.SELECT,
    "f3": FieldKind.UPLOAD,
    "flag": FieldKind.TEXT,
    "up": FieldKind.UPLOAD,
    "ask": FieldKind.TEXT,
    "sens": FieldKind.TEXT,
}


# -------------------------------------------------------------- §6 matrix


@pytest.mark.parametrize(
    "confidence,kind,sensitive,expected",
    [
        (1.0, FieldKind.TEXT, False, "silent"),  # ≥0.95 → silent
        (SILENT_FILL_CONFIDENCE, FieldKind.TEXT, False, "silent"),
        (0.95, FieldKind.TEXT, False, "silent"),
        (0.9, FieldKind.TEXT, False, "flag"),  # 0.80–0.95 → flag
        (FLAG_FILL_CONFIDENCE, FieldKind.TEXT, False, "flag"),
        (0.79, FieldKind.TEXT, False, "ask"),  # <0.80 → ask
        (0.5, FieldKind.TEXT, False, "ask"),
        (None, FieldKind.TEXT, False, "unknown"),  # unresolved → unknown
        (1.0, FieldKind.UPLOAD, False, "upload"),  # upload → confirm
        (1.0, FieldKind.TEXT, True, "sensitive"),  # sensitive → always ask
        (0.5, FieldKind.TEXT, True, "sensitive"),  # sensitivity wins
    ],
)
def test_fill_action_matrix(confidence, kind, sensitive, expected):
    action = fill_action(fill(confidence=confidence), kind, sensitive=sensitive)
    assert action == expected


def test_type_match_failure_surfaces_as_ask():
    """A value that cannot be mapped to the field (filled=False, high
    confidence) must surface for the human, not pass silently."""
    fill = FieldFill(
        field_id="f1",
        resolution={"status": "auto", "typed_value": None},
        filled=False,
        confidence=1.0,
        source="stored",
        reason="no type match for kind select",
    )
    assert fill_action(fill, FieldKind.SELECT) == "ask"


def test_categorize_buckets():
    categories = categorize(
        [
            fill("silent", 1.0),
            fill("flag", 0.85),
            fill("ask", 0.5),
            fill("unknown", None),
            fill("up", 1.0),
            fill("sens", 1.0),
        ],
        {"up": FieldKind.UPLOAD, "sens": FieldKind.TEXT},
        sensitive={"sens"},
    )
    assert [i.field_id for i in categories["flag"]] == ["flag"]
    assert [i.field_id for i in categories["ask"]] == ["ask"]
    assert [i.field_id for i in categories["unknown"]] == ["unknown"]
    assert [i.field_id for i in categories["upload"]] == ["up"]
    assert [i.field_id for i in categories["sensitive"]] == ["sens"]
    assert categories["silent"] == []


def test_build_checkpoints_order_and_dismissibility():
    categories = categorize([fill("f1", 0.85), fill("f2", 0.5)], KINDS)
    cps = build_checkpoints(categories)
    assert [cp.checkpoint_id for cp in cps] == ["cp1", "cp2", "cp3"]
    assert [cp.type for cp in cps] == [
        CheckpointType.REVIEW_FLAGGED,
        CheckpointType.UPLOAD_SENSITIVE,
        CheckpointType.SUBMIT,
    ]
    assert cps[0].dismissible is True
    assert cps[1].dismissible is True
    assert cps[2].dismissible is False  # human gesture REQUIRED
    # cp1 holds the flag; cp3 holds the ask.
    assert [i.field_id for i in cps[0].pending] == ["f1"]
    assert [i.field_id for i in cps[2].pending] == ["f2"]


# ------------------------------------------------------------ gate sequence


def test_silent_fills_reach_submit_gate():
    engine = CheckpointEngine()
    gate = engine.evaluate([fill("f1", 1.0)], KINDS)
    assert gate is not None and gate.type == CheckpointType.SUBMIT
    assert gate.pending == ()
    assert engine.submit_authorized is False


def test_sequence_flag_then_submit():
    engine = CheckpointEngine()
    assert engine.evaluate([fill("f1", 0.85)], KINDS).checkpoint_id == "cp1"
    with pytest.raises(CheckpointError):  # out-of-order confirm rejected
        engine.confirm("cp3", action="confirm")
    engine.confirm("cp1", action="dismiss")  # checkpoints always dismissible
    gate = engine.evaluate([fill("f1", 0.85)], KINDS)
    assert gate is not None and gate.type == CheckpointType.SUBMIT
    engine.confirm("cp3")
    assert engine.submit_authorized is True
    assert engine.evaluate([fill("f1", 0.85)], KINDS) is None


def test_upload_and_sensitive_gate():
    engine = CheckpointEngine()
    gate = engine.evaluate(
        [fill("up", 1.0), fill("sens", 1.0)], KINDS, sensitive={"sens"}
    )
    assert gate is not None and gate.type == CheckpointType.UPLOAD_SENSITIVE
    kinds = {i.kind for i in gate.pending}
    assert kinds == {"upload", "sensitive"}
    engine.confirm("cp2")
    assert engine.evaluate([fill("up", 1.0)], KINDS).type == CheckpointType.SUBMIT


def test_submit_gate_never_dismissible():
    engine = CheckpointEngine()
    gate = engine.evaluate([fill("f1", 1.0)], KINDS)
    assert gate is not None and gate.type == CheckpointType.SUBMIT
    with pytest.raises(CheckpointError, match="not dismissible"):
        engine.confirm("cp3", action="dismiss")
    assert engine.submit_authorized is False  # gesture still required


def test_never_bypass_submit():
    """submit_authorized requires the full cp1→cp2→cp3 sequence."""
    engine = CheckpointEngine()
    fills = [fill("flag", 0.85), fill("up", 1.0), fill("ask", 0.5)]
    assert engine.evaluate(fills, KINDS).checkpoint_id == "cp1"
    engine.confirm("cp1")
    assert engine.evaluate(fills, KINDS).checkpoint_id == "cp2"
    engine.confirm("cp2")
    assert engine.evaluate(fills, KINDS).checkpoint_id == "cp3"
    engine.confirm("cp3")
    assert engine.submit_authorized is True


def test_confirm_wrong_gate_rejected():
    engine = CheckpointEngine()
    engine.evaluate([fill("f1", 0.85)], KINDS)
    with pytest.raises(CheckpointError):
        engine.confirm("cp2", action="confirm")
    with pytest.raises(CheckpointError):
        engine.confirm("nope", action="confirm")


def test_ask_surfaces_at_submit_gate():
    """manual_review / <0.80 must not be blank at submit (§11)."""
    engine = CheckpointEngine()
    gate = engine.evaluate([fill("ask", 0.5)], KINDS)
    assert gate is not None and gate.type == CheckpointType.SUBMIT
    assert [i.field_id for i in gate.pending] == ["ask"]


def test_to_dict_shapes():
    categories = categorize([fill("f1", 0.85)], KINDS)
    cp = build_checkpoints(categories)[0]
    data = cp.to_dict()
    assert set(data) == {
        "checkpoint_id",
        "type",
        "gates_open",
        "pending",
        "dismissible",
    }
    assert data["gates_open"] is True
    assert set(data["pending"][0]) == {"type", "field_id", "reason"}
    assert PendingItem("flag", "f1", "r").to_dict() == {
        "type": "flag",
        "field_id": "f1",
        "reason": "r",
    }


def test_empty_form_reaches_submit():
    engine = CheckpointEngine()
    gate = engine.evaluate([], {})
    assert gate is not None and gate.type == CheckpointType.SUBMIT
