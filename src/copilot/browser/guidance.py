"""Guidance-mode plan (CP-5-05, 04_BROWSER_ASSISTANT.md §8/§9).

When automation cannot safely proceed (unrecoverable drift, timeout,
CAPTCHA, takeover), the assistant degrades to guidance mode: the human
types, the assistant points at the next field. ``build_guidance_plan``
produces the ordered next-field steps (02_ARCHITECTURE.md §7.6
``degrade_to_guidance -> GuidancePlan``).
"""

from dataclasses import dataclass
from typing import Any

from src.copilot.browser.form.model import FormModel


@dataclass(frozen=True)
class GuidanceStep:
    """One guided fill: the field + what the human should do."""

    field_id: str
    label: str
    instruction: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "label": self.label,
            "instruction": self.instruction,
        }


@dataclass(frozen=True)
class GuidancePlan:
    """The remaining plan when the assistant hands the wheel to the human."""

    reason: str
    steps: tuple[GuidanceStep, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "steps": [step.to_dict() for step in self.steps],
        }


def build_guidance_plan(
    model: FormModel,
    *,
    unfilled: list[str] | None = None,
    reason: str = "",
) -> GuidancePlan:
    """Next-field guidance for every field that still needs the human's input.

    ``unfilled`` limits the plan to the given field_ids (the API passes the
    unresolved ones); by default the whole model is guided.
    """
    target = set(unfilled) if unfilled is not None else None
    steps: list[GuidanceStep] = []
    for f in model.fields:
        if target is not None and f.field_id not in target:
            continue
        label = f.label or f.name or f.field_id
        steps.append(
            GuidanceStep(
                field_id=f.field_id,
                label=label,
                instruction=(
                    f"Enter your answer for {label!r} into the highlighted "
                    "field — the assistant will not touch it (04 §9 guidance)"
                ),
            )
        )
    return GuidancePlan(reason=reason, steps=tuple(steps))
