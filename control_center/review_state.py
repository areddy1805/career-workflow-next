import json
import os
from pathlib import Path
from typing import Dict, Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_STATE_PATH = REPO_ROOT / "data" / "review_state.json"


def _load_state() -> Dict[str, Any]:
    if not REVIEW_STATE_PATH.exists():
        return {}
    try:
        with open(REVIEW_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: Dict[str, Any]):
    REVIEW_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REVIEW_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def mark_reviewed(job_id: str, note: str = ""):
    state = _load_state()
    state[job_id] = {"status": "REVIEWED", "note": note}
    _save_state(state)


def dismiss_job(job_id: str, note: str = ""):
    state = _load_state()
    state[job_id] = {"status": "DISMISSED", "note": note}
    _save_state(state)


def get_review_states() -> Dict[str, Any]:
    return _load_state()
