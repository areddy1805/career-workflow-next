import pytest
from pathlib import Path
import json
import shutil
import tempfile
from control_center.data import _effective_run_status

@pytest.fixture
def run_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)

def test_effective_run_status(run_dir):
    # Case 1: Empty directory (crashed before writing anything, dead process)
    assert _effective_run_status(run_dir, {}, {}, newest=False) == "FAILED"

    # Case 2: Partial state (dead process)
    state = {"status": "IN_PROGRESS"} # not terminal
    assert _effective_run_status(run_dir, state, {}, newest=False) == "FAILED"

    # Case 3: Success state (dead process)
    state = {"status": "SUCCESS"}
    assert _effective_run_status(run_dir, state, {}, newest=False) == "SUCCESS"

    # Case 4: Result has status (always prefer result)
    result = {"status": "SUCCESS"}
    state = {"status": "FAILED"}
    assert _effective_run_status(run_dir, state, result, newest=False) == "SUCCESS"

    # Case 5: Result empty, state is CANCELLED
    state = {"status": "CANCELLED"}
    assert _effective_run_status(run_dir, state, {}, newest=False) == "CANCELLED"
