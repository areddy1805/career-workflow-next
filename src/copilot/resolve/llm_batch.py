"""Batched LLM inference for the extension resolve path (FINAL ADDENDUM §6-§8).

Default implementation sends ONE request for all unresolved fields using the
career-copilot logical profile (OMLX pramya-4b). Injectable for tests.
Output is machine-validated against a strict schema; anything that fails
validation is excluded (the service marks it human review).
"""
from __future__ import annotations

import json
import re
from typing import Any

from src.copilot.inference import omlx_params


_CLASSIFICATION_SCHEMA_KEYS = {"field_id", "intent", "confidence", "answerable", "requires_review", "reason_code"}

_SYSTEM_PROMPT = """You are the classification module of a career application assistant.
You interpret application-form questions and map them to a canonical intent.
You NEVER state candidate facts. You NEVER answer identity/legal/salary questions.
Rules:
- Only use intents from the ontology you are given.
- If a question is identity/legal/sensitive, set answerable=false, requires_review=true.
- If unsure, confidence must be low and requires_review must be true.
- Respond with a single JSON array only. No prose, no markdown fences.
Each item: {"field_id": str, "intent": str, "confidence": 0.0-1.0,
"answerable": bool, "requires_review": bool, "reason_code": str}
"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _validate_item(item: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    missing = _CLASSIFICATION_SCHEMA_KEYS - set(item)
    if missing:
        return None
    try:
        item["confidence"] = float(item["confidence"])
    except (TypeError, ValueError):
        return None
    if not 0.0 <= item["confidence"] <= 1.0:
        return None
    item["requires_review"] = bool(item["requires_review"])
    item["answerable"] = bool(item["answerable"])
    return item


def default_batch_llm() -> Any:
    """Build the default batched LLM callable (OMLX via OMLXClient)."""
    from src.llm.client import OMLXClient

    params = omlx_params()
    client = OMLXClient(
        base_url=params["base_url"],
        model=params["model"],
        temperature=params["temperature"],
        timeout=params["timeout"],
    )

    def invoke(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not requests:
            return []
        question_bundle = json.dumps(
            [
                {
                    "field_id": r["field_id"],
                    "question": r["question"],
                    "kind": r.get("kind", "text"),
                    "options": r.get("options", []),
                }
                for r in requests
            ],
            ensure_ascii=False,
        )
        resp = client.chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Classify these fields. Return ONLY the JSON array:\n"
                        + question_bundle
                    ),
                },
            ],
            max_tokens=2048,
        )
        raw_text = resp if isinstance(resp, str) else str(resp)
        try:
            items = json.loads(_strip_fences(raw_text))
        except json.JSONDecodeError:
            return []
        if not isinstance(items, list):
            return []
        out: list[dict[str, Any]] = []
        for it in items:
            valid = _validate_item(it)
            if valid is not None:
                out.append(valid)
        return out

    return invoke
