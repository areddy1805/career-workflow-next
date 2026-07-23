from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    exit_path = Path(sys.argv[1])
    log_path = Path(sys.argv[2])
    command = sys.argv[3:]
    launcher_pid = __import__("os").getpid()

    with log_path.open("w", encoding="utf-8") as log_handle:
        completed = subprocess.run(
            command,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            check=False,
        )

    payload = {
        "launcher_pid": launcher_pid,
        "exit_code": completed.returncode,
        "completed_at": datetime.now(UTC).isoformat(),
    }
    temporary = exit_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(exit_path)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
