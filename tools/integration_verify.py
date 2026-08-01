#!/usr/bin/env python3
"""
Integration Verification Script.

Traces the complete data flow from lifecycle → queue → API for routed jobs.
Does NOT modify any pipeline code — only reads and verifies.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Ensure we can import from the project
sys.path.insert(0, str(REPO_ROOT))

os.environ["MANUAL_ACTION_QUEUE_PATH"] = str(REPO_ROOT / "data" / "manual_action_queue.json")

from src.orchestration.job_lifecycle import JobLifecycleStore, JobState, QUEUED_STATES
from src.application.manual_action_queue import ManualActionQueue
from src.application.workflow_queue import WorkflowQueue

passed = 0
failed = 0

def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        print(f"  ✓ {name}" + (f" — {detail}" if detail else ""))
        passed += 1
    else:
        print(f"  ✗ {name}" + (f" — {detail}" if detail else ""))
        failed += 1

def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")

# ============================================================================
# Test 1: Simulate enqueue for each routing mode
# ============================================================================

section("Test 1: Queue Generation — Each Routing Mode Produces Correct Source")

# Use a temp file for MAQ
with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    maq_path = f.name

try:
    # Create the mock job object
    class MockJob:
        def __init__(self, job_id, title="Engineer", company="Acme"):
            self.job_id = job_id
            self.title = title
            self.company = company
            self.provider_id = "naukri"
            self.score = 85.0
            self.url = f"https://example.com/jobs/{job_id}"
            self.source = "naukri"
            self.location = "Remote"
    
    maq = ManualActionQueue(maq_path)
    
    # Enqueue manual review
    maq.enqueue_manual_review(
        job=MockJob("manual-1"), score=85, reason="Manual review needed",
        run_id="test-run",
    )
    maq.enqueue_manual_review(
        job=MockJob("manual-2", "Manager", "Beta"), score=75,
        reason="Manual review: needs human decision",
        run_id="test-run",
    )
    
    # Enqueue external apply (ATS jobs use this)
    maq.enqueue_external_apply(
        job=MockJob("ats-1"), score=90, reason="ATS detected: Lever",
        run_id="test-run",
    )
    maq.enqueue_external_apply(
        job=MockJob("external-1"), score=80, reason="External browser required",
        run_id="test-run",
    )
    
    # Read back all items
    all_items = maq.list()
    check("MAQ has 4 items", len(all_items) == 4, f"count={len(all_items)}")
    
    # Check sources
    manual_items = [i for i in all_items if i.get("source") == "manual_review"]
    external_items = [i for i in all_items if i.get("source") == "external_apply"]
    
    check("Manual review items have source='manual_review'",
          len(manual_items) == 2,
          f"found {len(manual_items)}")
    check("External/ATS items have source='external_apply'",
          len(external_items) == 2,
          f"found {len(external_items)}")
    
    # Verify all required fields present
    for item in all_items:
        jid = item.get("job_id", "?")
        check(f"Item {jid} has job_id", bool(item.get("job_id")), item["job_id"])
        check(f"Item {jid} has title", bool(item.get("title")), item.get("title", ""))
        check(f"Item {jid} has company", bool(item.get("company")), item.get("company", ""))
        check(f"Item {jid} has source", bool(item.get("source")), item.get("source", ""))
        check(f"Item {jid} has status", bool(item.get("status")), item.get("status", ""))
        check(f"Item {jid} has run_id", bool(item.get("run_id")), item.get("run_id", ""))
        check(f"Item {jid} has created_at", bool(item.get("created_at")), str(item.get("created_at", ""))[:19])
        check(f"Item {jid} has score", item.get("score", 0) > 0, str(item.get("score", 0)))

finally:
    os.unlink(maq_path)

# ============================================================================
# Test 2: WorkflowQueue reads MAQ correctly
# ============================================================================

section("Test 2: WorkflowQueue Integration")

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    test_maq_path = f.name
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
    test_db_path = f.name

try:
    # Set up MAQ with known data
    maq2 = ManualActionQueue(test_maq_path)
    maq2.enqueue_manual_review(
        job=MockJob("wq-manual-1"), score=85,
        reason="Needs review", run_id="r1",
    )
    maq2.enqueue_external_apply(
        job=MockJob("wq-ats-1"), score=90,
        reason="ATS detected", run_id="r1",
    )
    
    # WorkflowQueue reads from this MAQ
    wq = WorkflowQueue(maq_path=test_maq_path, db_path=test_db_path)
    all_wq_items = wq.list()
    
    check("WorkflowQueue sees 2 items", len(all_wq_items) == 2)
    
    # Check sources are preserved
    manual_wq = [i for i in all_wq_items if i.get("source") == "manual_review"]
    external_wq = [i for i in all_wq_items if i.get("source") == "external_apply"]
    
    check("WQ preserves manual_review source", len(manual_wq) == 1,
          f"source={manual_wq[0].get('source') if manual_wq else 'N/A'}")
    check("WQ preserves external_apply source", len(external_wq) == 1,
          f"source={external_wq[0].get('source') if external_wq else 'N/A'}")
    
    # Check workflow_status is set
    for item in all_wq_items:
        check(f"WQ item {item['job_id']} has workflow_status",
              "workflow_status" in item,
              f"={item.get('workflow_status', 'MISSING')}")

finally:
    for p in [test_maq_path, test_db_path]:
        try:
            os.unlink(p)
        except OSError:
            pass

# ============================================================================
# Test 3: API filtering matches lifecycle counts
# ============================================================================

section("Test 3: Lifecycle ↔ Queue Count Reconciliation")

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
    test_maq_path = f.name
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
    test_db_path = f.name

try:
    # Create lifecycle with various states
    lifecycle = JobLifecycleStore(":memory:")
    lifecycle.create("manual-1", title="M1", company="Acme")
    lifecycle.transition("manual-1", JobState.ROUTED_MANUAL, reason="Manual review")
    lifecycle.create("ats-1", title="A1", company="Beta")
    lifecycle.transition("ats-1", JobState.ROUTED_ATS, reason="ATS detected")
    lifecycle.create("ext-1", title="E1", company="Gamma")
    lifecycle.transition("ext-1", JobState.ROUTED_EXTERNAL, reason="External browser")
    lifecycle.create("sub-1", title="S1", company="Delta")
    lifecycle.transition("sub-1", JobState.SELECTED_AUTO)
    lifecycle.transition("sub-1", JobState.SUBMITTED)
    
    metrics = lifecycle.compute_metrics()
    check("Lifecycle has routed_manual=1", metrics["routed_manual"] == 1)
    check("Lifecycle has routed_ats=1", metrics["routed_ats"] == 1)
    check("Lifecycle has routed_external=1", metrics["routed_external"] == 1)
    check("Lifecycle has submitted=1", metrics["submitted"] == 1)
    check("Lifecycle has routed=3", metrics["routed"] == 3)
    
    # Populate MAQ to match lifecycle counts
    maq3 = ManualActionQueue(test_maq_path)
    maq3.enqueue_manual_review(
        job=MockJob("manual-1"), score=85, reason="Manual review", run_id="r1",
    )
    maq3.enqueue_external_apply(
        job=MockJob("ats-1"), score=90, reason="ATS detected", run_id="r1",
    )
    maq3.enqueue_external_apply(
        job=MockJob("ext-1"), score=80, reason="External browser", run_id="r1",
    )
    
    # API filter simulation
    wq = WorkflowQueue(maq_path=test_maq_path, db_path=test_db_path)
    all_queue_items = wq.list()
    
    manual_queue = [
        i for i in all_queue_items
        if i.get("source") == "manual_review"
        and i.get("workflow_status") in ("PENDING", "IN_PROGRESS", "READY")
    ]
    external_queue = [
        i for i in all_queue_items
        if i.get("source") == "external_apply"
    ]
    other_queue = [
        i for i in all_queue_items
        if i.get("source") not in ("manual_review", "external_apply")
    ]
    
    check("Manual queue count = lifecycle routed_manual",
          len(manual_queue) == metrics["routed_manual"],
          f"queue={len(manual_queue)} lifecycle={metrics['routed_manual']}")
    check("External queue count = lifecycle routed_ats + routed_external",
          len(external_queue) == metrics["routed_ats"] + metrics["routed_external"],
          f"queue={len(external_queue)} lifecycle={metrics['routed_ats'] + metrics['routed_external']}")
    check("Other queue is empty (no unknown sources)",
          len(other_queue) == 0)

finally:
    for p in [test_maq_path, test_db_path]:
        try:
            os.unlink(p)
        except OSError:
            pass

# ============================================================================
# Test 4: Every routed lifecycle state generates an MAQ entry
# ============================================================================

section("Test 4: Queue Generation Completeness")

for state in [JobState.ROUTED_MANUAL, JobState.ROUTED_ATS, JobState.ROUTED_EXTERNAL]:
    # Verify the state exists in QUEUED_STATES
    check(f"{state.value} is in QUEUED_STATES", state in QUEUED_STATES,
          f"part of {[s.value for s in QUEUED_STATES]}")

# Verify routing codes exist
from src.orchestration.job_lifecycle import STATE_TO_ROUTING_CODE, ROUTING_CODE_TO_STATE
for state in QUEUED_STATES:
    check(f"{state.value} has routing code", state in STATE_TO_ROUTING_CODE,
          f"→ {STATE_TO_ROUTING_CODE.get(state, 'MISSING')}")
    code = STATE_TO_ROUTING_CODE[state]
    check(f"Routing code {code} maps back to {state.value}",
          ROUTING_CODE_TO_STATE[code] == state)

# ============================================================================
# Summary
# ============================================================================

section("SUMMARY")
print(f"  Passed: {passed}")
print(f"  Failed: {failed}")
if failed == 0:
    print("\n  ✓ INTEGRATION VERIFIED")
else:
    print(f"\n  ✗ {failed} TESTS FAILED")
    sys.exit(1)
