import subprocess
import sys
from pathlib import Path
import os
import tempfile

def get_cw_executable():
    """Find the cw executable relative to the project root or in the path."""
    # Assuming this test runs from the project root or within the venv
    venv_cw = Path(__file__).parent.parent / ".venv" / "bin" / "cw"
    if venv_cw.exists():
        return str(venv_cw)
    return "cw"

def test_packaging_cli_help_works():
    """Test that the CLI help command works."""
    cw = get_cw_executable()
    result = subprocess.run([cw, "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Unified Operations CLI for Career Workflow" in result.stdout

def test_packaging_cli_import_works():
    """Test that the CLI modules can be imported normally."""
    try:
        from src.cli.main import app
        assert app is not None
    except ImportError as e:
        assert False, f"Failed to import CLI module: {e}"

def test_packaging_cli_works_outside_root():
    """Test that the CLI works when executed from outside the project root."""
    cw = get_cw_executable()
    
    # Check if cw is an absolute path, otherwise we can't run it from another dir easily
    if not Path(cw).is_absolute():
        cw = str(Path(cw).resolve())
        
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run([cw, "--help"], cwd=tmpdir, capture_output=True, text=True)
        assert result.returncode == 0
        assert "Unified Operations CLI for Career Workflow" in result.stdout

def test_packaging_doctor_works():
    """Test that a basic CLI command (doctor) works successfully."""
    cw = get_cw_executable()
    result = subprocess.run([cw, "doctor"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Diagnostic Checks" in result.stdout

def test_packaging_cache_stats_works():
    cw = get_cw_executable()
    result = subprocess.run([cw, "cache", "stats"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Cache Statistics:" in result.stdout

def test_packaging_validate_jobspy_works():
    cw = get_cw_executable()
    result = subprocess.run([cw, "validate", "jobspy", "--results", "1"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "STANDALONE JOBSPY VALIDATION" in result.stdout

def test_packaging_module_execution_works():
    """Test module execution via python -m without sys.path hacks."""
    result = subprocess.run([sys.executable, "-m", "src.cache.cli", "stats"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Cache Statistics:" in result.stdout

    result = subprocess.run([sys.executable, "tools/validate_jobspy.py", "--results", "1"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "STANDALONE JOBSPY VALIDATION" in result.stdout
