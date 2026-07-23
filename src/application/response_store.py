import json
from datetime import UTC, datetime
from pathlib import Path

RESPONSE_DIRECTORY = Path("data/responses")


def save_response(
    job_id: str,
    stage: str,
    response: dict,
) -> str:
    RESPONSE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")

    safe_stage = stage.strip().lower().replace(" ", "_").replace("/", "_")

    filename = f"{timestamp}__" f"{job_id}__" f"{safe_stage}.json"

    path = RESPONSE_DIRECTORY / filename

    with path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            response,
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    return str(path)
