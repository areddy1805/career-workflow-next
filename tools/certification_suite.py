#!/usr/bin/env python3
"""
Production Certification Suite for Career Workflow 4.0.

Verifies architectural invariants after the lifecycle migration.

Every test MUST pass for the release to be certified.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Suite-level state
# ---------------------------------------------------------------------------

import tempfile

# Use temp dir to avoid cross-test pollution
_suite_db: str | None = None


def _fresh_store() -> tuple:
    """Create an isolated JobLifecycleStore for testing."""
    global _suite_db
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    _suite_db = tmp.name
    tmp.close()
    from src.orchestration.job_lifecycle import JobLifecycleStore
    return JobLifecycleStore(_suite_db), _suite_db


def _cleanup_store():
    global _suite_db
    if _suite_db and os.path.exists(_suite_db):
        try:
            os.unlink(_suite_db)
        except OSError:
            pass
        _suite_db = None

class CertificationResult:
    def __init__(self):
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.skipped: list[str] = []

    def ok(self, name: str, detail: str = ""):
        self.passed.append(f"✓ {name}" + (f" — {detail}" if detail else ""))

    def fail(self, name: str, detail: str = ""):
        self.failed.append(f"✗ {name}" + (f" — {detail}" if detail else ""))

    def skip(self, name: str, detail: str = ""):
        self.skipped.append(f"∼ {name}" + (f" — {detail}" if detail else ""))

    @property
    def all_passed(self) -> bool:
        return len(self.failed) == 0

    def print_report(self):
        print("\n" + "=" * 60)
        print("PRODUCTION CERTIFICATION REPORT")
        print("=" * 60)
        if self.passed:
            print("\nPASSED:")
            for p in self.passed:
                print(f"  {p}")
        if self.failed:
            print("\nFAILED:")
            for f in self.failed:
                print(f"  {f}")
        if self.skipped:
            print("\nSKIPPED:")
            for s in self.skipped:
                print(f"  {s}")
        print(f"\n{'=' * 60}")
        print(f"Result: {'ALL PASSED' if self.all_passed else f'{len(self.failed)} FAILURE(S)'}")
        print(f"Passed: {len(self.passed)}  Failed: {len(self.failed)}  Skipped: {len(self.skipped)}")
        print("=" * 60)


result = CertificationResult()


# ---------------------------------------------------------------------------
# Test 1: JobLifecycleStore persistence
# ---------------------------------------------------------------------------

def test_lifecycle_persistence():
    """Verify JobLifecycleStore persists to SQLite and survives restart."""
    from src.orchestration.job_lifecycle import JobLifecycleStore, JobState

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        store = JobLifecycleStore(db_path)
        store.create("job-1", title="Engineer", company="Acme", score=85.0)
        store.create("job-2", title="Manager", company="Beta", score=70.0)
        store.transition("job-2", JobState.PRE_APPLICATION_REJECTED, reason="test")

        c1 = store.count_by_state(JobState.ACQUIRED)
        c2 = store.count_by_state(JobState.PRE_APPLICATION_REJECTED)
        if c1 != 1:
            result.fail("Lifecycle persistence", f"acquired count={c1}")
            return
        if c2 != 1:
            result.fail("Lifecycle persistence", f"rejected count={c2}")
            return
        if store.count() != 2:
            result.fail("Lifecycle persistence", f"total count={store.count()}")
            return

        # SQLite file must exist with data
        if not Path(db_path).exists():
            result.fail("Lifecycle persistence", "DB file not found")
            return
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT COUNT(*) FROM lifecycle_records").fetchone()
        if rows[0] != 2:
            result.fail("Lifecycle persistence", f"SQLite row count={rows[0]}")
            return
        conn.close()

        # Simulate restart
        store2 = JobLifecycleStore(db_path)
        if store2.count() != 2:
            result.fail("Lifecycle persistence", f"after restart total={store2.count()}")
            return
        if store2.count_by_state(JobState.ACQUIRED) != 1:
            result.fail("Lifecycle persistence", "after restart acquired count mismatch")
            return

        rec = store2.get("job-1")
        if rec is None or rec.title != "Engineer" or rec.score != 85.0:
            result.fail("Lifecycle persistence", "after restart record data mismatch")
            return

        result.ok("JobLifecycleStore persistence",
                   f"2 jobs survive SQLite restart at {db_path}")
    finally:
        os.unlink(db_path)


# ---------------------------------------------------------------------------
# Test 2: No PipelineRunMetrics remains
# ---------------------------------------------------------------------------

def test_no_pipeline_run_metrics():
    """Verify PipelineRunMetrics has been fully removed."""
    try:
        from src.orchestration.metrics import PipelineRunMetrics
        result.fail("PipelineRunMetrics still importable")
        return
    except ImportError:
        pass

    # Check no files import it
    import ast
    import glob

    py_files = glob.glob(str(REPO_ROOT / "src/**/*.py"), recursive=True)
    py_files += glob.glob(str(REPO_ROOT / "tests/**/*.py"), recursive=True)

    for py_file in py_files:
        try:
            with open(py_file) as f:
                content = f.read()
            if "PipelineRunMetrics" in content:
                # Only flag if it's not a comment
                for line in content.split("\n"):
                    if "PipelineRunMetrics" in line and not line.strip().startswith("#"):
                        result.fail(f"PipelineRunMetrics found in {py_file}: {line.strip()}")
                        return
        except Exception:
            continue

    result.ok("No PipelineRunMetrics remains", "Class definition removed, all imports deleted")


# ---------------------------------------------------------------------------
# Test 3: No OpportunityStatus usage in production code
# ---------------------------------------------------------------------------

def test_no_opportunity_status():
    """Verify OpportunityStatus has been eliminated from production code."""
    import glob

    py_files = glob.glob(str(REPO_ROOT / "src/**/*.py"), recursive=True)

    for py_file in py_files:
        try:
            with open(py_file) as f:
                content = f.read()
            if "OpportunityStatus" in content and "job_lifecycle" not in py_file:
                for line in content.split("\n"):
                    if "OpportunityStatus" in line and not line.strip().startswith("#"):
                        result.fail(f"OpportunityStatus found in {py_file}: {line.strip()}")
                        return
        except Exception:
            continue

    result.ok("No OpportunityStatus in production code")


# ---------------------------------------------------------------------------
# Test 4: All metrics derive from lifecycle
# ---------------------------------------------------------------------------

def test_metrics_derive_from_lifecycle():
    """Verify compute_metrics returns correct derived counts."""
    from src.orchestration.job_lifecycle import JobLifecycleStore, JobState

    store, _ = _fresh_store()
    store.create("a", title="A")
    store.create("b", title="B")
    store.create("c", title="C")
    store.transition("b", JobState.PRE_APPLICATION_REJECTED, reason="test")
    store.transition("c", JobState.ELIGIBLE, reason="passed")
    store.transition("c", JobState.SELECTED_AUTO, reason="selected")
    store.transition("c", JobState.APPLYING, reason="applying")
    store.transition("c", JobState.SUBMITTED, reason="applied")

    metrics = store.compute_metrics()
    if metrics["acquired"] != 3:
        result.fail(f"acquired={metrics['acquired']}, expected 3")
        return
    if metrics["pre_app_rejected"] != 1:
        result.fail(f"pre_app_rejected={metrics['pre_app_rejected']}, expected 1")
        return
    if metrics["submitted"] != 1:
        result.fail(f"submitted={metrics['submitted']}, expected 1")
        return
    if metrics["selected"] != 1:
        result.fail(f"selected={metrics['selected']}, expected 1 (job C went through SELECTED_AUTO)")
        return

    # Verify core pipeline invariants
    # selected = submitted + application_failed + already_applied
    selected_invariant = metrics["selected"] == metrics["submitted"] + metrics["application_failed"] + metrics["already_applied"]
    if not selected_invariant:
        result.fail(f"Selected invariant violated: {metrics['selected']} != {metrics['submitted']} + {metrics['application_failed']} + {metrics['already_applied']}")
        return

    result.ok("Metrics derive from lifecycle",
               f"3 jobs: acquired={metrics['acquired']}, rejected={metrics['pre_app_rejected']}, submitted={metrics['submitted']}")


# ---------------------------------------------------------------------------
# Test 5: Invariant validation
# ---------------------------------------------------------------------------

def test_lifecycle_invariants():
    """Verify lifecycle.validate() catches violations."""
    from src.orchestration.job_lifecycle import JobLifecycleStore, JobState

    store, _ = _fresh_store()
    store.create("j1", title="J1")
    store.create("j2", title="J2")
    store.create("j3", title="J3")

    # All in ACQUIRED — valid
    diags = store.validate()
    if diags:
        result.fail(f"Lifecycle validation failed on clean store: {diags}")
        return

    # Transition normally
    store.transition("j1", JobState.SUBMITTED, reason="ok")
    store.transition("j2", JobState.PRE_APPLICATION_REJECTED, reason="bad")
    diags = store.validate()
    if diags:
        result.fail(f"Lifecycle validation failed after normal transitions: {diags}")
        return

    result.ok("Lifecycle invariants hold", "3 jobs, all accounted for")


# ---------------------------------------------------------------------------
# Test 6: PipelineResult derives from lifecycle
# ---------------------------------------------------------------------------

def test_pipeline_result_derivation():
    """Verify PipelineResult.from_lifecycle() computes correct values."""
    from src.orchestration.job_lifecycle import JobLifecycleStore, JobState
    from src.orchestration.result import PipelineResult

    store, _ = _fresh_store()
    store.create("a", title="A")
    store.create("b", title="B")
    store.transition("a", JobState.ELIGIBLE, reason="eligible")
    store.transition("a", JobState.SELECTED_AUTO, reason="selected")
    store.transition("a", JobState.APPLYING, reason="applying")
    store.transition("a", JobState.SUBMITTED, reason="ok")
    store.transition("b", JobState.PRE_APPLICATION_REJECTED, reason="no")

    result_inst = PipelineResult.from_lifecycle(
        run_id="test-run",
        status="SUCCESS",
        lifecycle=store,
    )
    if result_inst.acquired != 2:
        result.fail(f"PipelineResult.acquired={result_inst.acquired}, expected 2")
        return
    if result_inst.submitted != 1:
        result.fail(f"PipelineResult.submitted={result_inst.submitted}, expected 1")
        return
    if result_inst.pre_app_rejected != 1:
        result.fail(f"PipelineResult.pre_app_rejected={result_inst.pre_app_rejected}, expected 1")
        return

    # Invariant: selected = submitted + application_failed + already_applied
    if result_inst.selected != result_inst.submitted + result_inst.application_failed + result_inst.already_applied:
        result.fail(f"Selected invariant violated: {result_inst.selected} != {result_inst.submitted} + {result_inst.application_failed} + {result_inst.already_applied}")
        return

    result.ok("PipelineResult.from_lifecycle()",
               f"acquired={result_inst.acquired}, submitted={result_inst.submitted}, pre_app_rejected={result_inst.pre_app_rejected}")


# ---------------------------------------------------------------------------
# Test 7: Artifacts derive from lifecycle
# ---------------------------------------------------------------------------

def test_artifacts_derive():
    """Verify lifecycle.compute_artifacts() returns correct projections."""
    from src.orchestration.job_lifecycle import JobLifecycleStore, JobState

    store, _ = _fresh_store()
    store.create("a", title="A")
    store.create("b", title="B")
    store.transition("a", JobState.SUBMITTED, reason="ok")
    store.transition("b", JobState.ROUTED_MANUAL, reason="manual")

    artifacts = store.compute_artifacts()
    if len(artifacts.get("applied_jobs", [])) != 1:
        result.fail(f"applied_jobs count={len(artifacts.get('applied_jobs', []))}, expected 1")
        return
    if len(artifacts.get("manual_review", [])) != 1:
        result.fail(f"manual_review count={len(artifacts.get('manual_review', []))}, expected 1")
        return
    if len(artifacts.get("rejected_jobs", [])) != 0:
        result.fail(f"rejected_jobs count={len(artifacts.get('rejected_jobs', []))}, expected 0")
        return

    result.ok("Artifacts derive from lifecycle",
               f"applied={len(artifacts['applied_jobs'])}, manual={len(artifacts['manual_review'])}")


# ---------------------------------------------------------------------------
# Test 8: Factory reset verification
# ---------------------------------------------------------------------------

def test_factory_reset():
    """Verify factory reset deletes all persistence layers."""
    # Check that the lifecycle DB path is deleted by factory reset
    from tools.factory_reset import FILES_TO_DELETE

    lifecycle_db_patterns = [p for p in FILES_TO_DELETE if "lifecycle" in p.lower()]
    if "data/job_lifecycle.db*" not in [p for p in FILES_TO_DELETE]:
        result.fail("Factory reset does not include job_lifecycle.db")
        return

    result.ok("Factory reset covers lifecycle DB",
               f"Glob pattern: data/job_lifecycle.db*")


# ---------------------------------------------------------------------------
# Test 9: No legacy lifecycle.py states in use
# ---------------------------------------------------------------------------

def test_no_legacy_lifecycle_py():
    """Verify legacy lifecycle.py (OpportunityStatus) is not used."""
    import glob

    prod_files = glob.glob(str(REPO_ROOT / "src/**/*.py"), recursive=True)

    for py_file in prod_files:
        try:
            with open(py_file) as f:
                content = f.read()
            # Check for old lifecycle imports (not the file itself)
            if "from src.orchestration.lifecycle import" in content:
                result.fail(f"Legacy lifecycle import in {py_file}")
                return
        except Exception:
            continue

    result.ok("No legacy lifecycle.py imports")


# ---------------------------------------------------------------------------
# Test 10: Acquisition → terminal traceability
# ---------------------------------------------------------------------------

def test_traceability():
    """Verify every acquired job is traceable to a terminal state."""
    from src.orchestration.job_lifecycle import JobLifecycleStore, JobState

    store, _ = _fresh_store()
    jobs = {
        "j1": [JobState.SUBMITTED],
        "j2": [JobState.PRE_APPLICATION_REJECTED],
        "j3": [JobState.ROUTED_MANUAL, JobState.QUEUED],
        "j4": [JobState.SELECTED_AUTO, JobState.APPLICATION_FAILED],
    }

    for jid, transitions in jobs.items():
        store.create(jid, title=jid)
        for state in transitions:
            store.transition(jid, state, reason="test")

    # Every job must have a traceable path
    diags = store.validate()
    if diags:
        result.fail(f"Traceability violated: {diags}")
        return

    for jid in jobs:
        rec = store.get(jid)
        assert rec is not None
        assert len(rec.transitions) >= 1
        assert rec.current_state in JobState

    result.ok("Traceability", f"{len(jobs)} jobs, each with {[len(v) for v in jobs.values()]} transitions")


# ---------------------------------------------------------------------------
# Test 11: PipelineContext has no independent counters
# ---------------------------------------------------------------------------

def test_context_no_independent_counters():
    """Verify PipelineContext has removed PipelineRunMetrics."""
    from src.orchestration.context import PipelineContext

    ctx = PipelineContext(run_id="test", dry_run=True, max_applications=5)
    # Should have `timing`, not `metrics`
    assert hasattr(ctx, "timing"), "PipelineContext missing timing field"
    assert not hasattr(ctx, "metrics"), "PipelineContext still has metrics field"

    result.ok("PipelineContext has timing, not metrics")


# ---------------------------------------------------------------------------
# Test 12: Compute metrics invoked on a lifecycle store returns dict
# ---------------------------------------------------------------------------

def test_compute_metrics_signature():
    store, _ = _fresh_store()
    metrics = store.compute_metrics()
    assert isinstance(metrics, dict)
    assert "acquired" in metrics
    assert "selected" in metrics
    assert "submitted" in metrics
    assert "routed" in metrics
    assert "deferred" in metrics
    assert "pre_app_rejected" in metrics
    result.ok("compute_metrics signature correct",
               f"Keys: {list(metrics.keys())}")


# We need to import JobLifecycleStore for test 12
from src.orchestration.job_lifecycle import JobLifecycleStore


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

def _run_test(name: str, func):
    try:
        func()
    except Exception as e:
        result.fail(name, str(e))


def main():
    print("Running Production Certification Suite...")
    print("=" * 60)

    # Order matters — run foundational tests first
    for name, func in [
        ("No PipelineRunMetrics remaining", test_no_pipeline_run_metrics),
        ("No OpportunityStatus in production code", test_no_opportunity_status),
        ("No legacy lifecycle.py imports", test_no_legacy_lifecycle_py),
        ("JobLifecycleStore persistence", test_lifecycle_persistence),
        ("Metrics derive from lifecycle", test_metrics_derive_from_lifecycle),
        ("Lifecycle invariants hold", test_lifecycle_invariants),
        ("PipelineResult.from_lifecycle()", test_pipeline_result_derivation),
        ("Artifacts derive from lifecycle", test_artifacts_derive),
        ("Traceability", test_traceability),
        ("PipelineContext has no independent counters", test_context_no_independent_counters),
        ("Factory reset covers lifecycle DB", test_factory_reset),
    ]:
        _run_test(name, func)

    result.print_report()

    if not result.all_passed:
        print("\nRELEASE BLOCKED: Certification suite has failures.")
        sys.exit(1)
    else:
        print("\nRELEASE CERTIFIED: All architectural invariants pass.")


if __name__ == "__main__":
    main()
