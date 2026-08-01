#!/usr/bin/env python3
"""
Trace the EXACT pipeline enqueue path used by the scheduler.
Stops at first failure. Does not swallow exceptions.
"""
import sys, os, json, tempfile, traceback, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.application.manual_action_queue import ManualActionQueue
from src.application.capability import ApplicationMode
from src.orchestration.capacity_planner import PlannedApplication, DeferredOpportunity
from src.orchestration.explanation import DecisionExplanation
from src.orchestration.opportunity import ApplicationOpportunity
from src.orchestration.opportunity_repository import OpportunityRepository
from src.orchestration.application_scheduler import ApplicationScheduler

step = 0
def check(label, condition, detail=""):
    global step
    step += 1
    status = "✓" if condition else "✗"
    print(f"  Step {step}: {status} {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        print(f"\n  FAILED at step {step}. Stopping.")
        sys.exit(1)

class MockJob:
    def __init__(self, job_id, title, company):
        self.job_id = job_id
        self.title = title
        self.company = company
        self.provider_id = "naukri"
        self.score = 85.0
        self.url = f"https://example.com/jobs/{job_id}"
        self.source = "naukri"
        self.location = "Remote"

print("=" * 60)
print("  PIPELINE ENQUEUE PATH TRACE")
print("=" * 60)

# ─────────────────────────────────────────────────────────────
# Create a minimal ledger and repo
# ─────────────────────────────────────────────────────────────
from src.application.ledger import ApplicationLedger
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    ledger_db_path = f.name
ledger = ApplicationLedger(ledger_db_path)
ledger._init_db()
check("Ledger initialized", True)

from src.orchestration.opportunity_repository import OpportunityRepository
repo = OpportunityRepository(ledger)
check("OpportunityRepository created", True)

# ─────────────────────────────────────────────────────────────
# Create stage context
# ─────────────────────────────────────────────────────────────
from src.orchestration.context import PipelineContext
from src.orchestration.execution_context import PipelineExecutionContext
from src.orchestration.job_lifecycle import JobLifecycleStore, JobState

ctx = PipelineContext(run_id="trace-run", dry_run=False, max_applications=100)
ctx.lifecycle = JobLifecycleStore(":memory:")

run_dir = Path(tempfile.mkdtemp())
exec_ctx = PipelineExecutionContext(run_id="trace-run", run_dir=run_dir)

# Create a mock ApplicationOpportunity the way the pipeline does
print("\n  1. Creating ApplicationOpportunity")
opp = ApplicationOpportunity.from_job(
    MockJob("pipeline-manual-1", "Pipeline Engineer", "PipeCorp"),
    status="CLASSIFIED"
)
opp.application_mode = ApplicationMode.MANUAL_REVIEW
check("Opp created with mode=MANUAL_REVIEW", 
      opp.application_mode == ApplicationMode.MANUAL_REVIEW,
      str(opp.application_mode))

# Also create one for ATS
opp_ats = ApplicationOpportunity.from_job(
    MockJob("pipeline-ats-1", "ATS Engineer", "ATSCorp"),
    status="CLASSIFIED"
)
opp_ats.application_mode = ApplicationMode.ATS
check("ATS opp created with mode=ATS",
      opp_ats.application_mode == ApplicationMode.ATS,
      str(opp_ats.application_mode))

# ─────────────────────────────────────────────────────────────
# Create PlannedApplication objects (like the capacity planner does)
# ─────────────────────────────────────────────────────────────
print("\n  2. Creating PlannedApplication objects")
explanation = DecisionExplanation(
    final_score=85,
    summary="Manual review needed: rank #3",
    applied=False,
    deferred_reason="",
)
planned_manual = PlannedApplication(
    opportunity=opp,
    mode="MANUAL_REVIEW",
    explanation=explanation,
)
check("PlannedApplication(MANUAL_REVIEW) created", True,
      f"mode={planned_manual.mode}, score={planned_manual.explanation.final_score}")

planned_ats = PlannedApplication(
    opportunity=opp_ats,
    mode="ATS",
    explanation=DecisionExplanation(
        final_score=90, summary="ATS detected: Lever", applied=False,
    ),
)
check("PlannedApplication(ATS) created", True, f"mode={planned_ats.mode}")

# ─────────────────────────────────────────────────────────────
# Create ManualActionQueue with a temp file
# ─────────────────────────────────────────────────────────────
with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
    maq_path = f.name

print(f"\n  3. MAQ path: {maq_path}")
maq = ManualActionQueue(maq_path)

# Define the EXACT _enqueue_external function as in the pipeline
def _enqueue_external(job, **kwargs):
    """Exact copy of pipeline.py's _enqueue_external."""
    app_mode = getattr(job, "application_mode", None)
    score = kwargs.get("score", int(getattr(job, "score", 0)))
    reason = kwargs.get("reason", "External apply")
    run_id = kwargs.get("run_id", ctx.run_id)
    jid = str(getattr(job, "job_id", ""))

    print(f"\n  _enqueue_external ENTER: job={jid} mode={app_mode} score={score}")
    
    if app_mode == ApplicationMode.MANUAL_REVIEW:
        print(f"    → calling enqueue_manual_review()")
        result = maq.enqueue_manual_review(
            job=job, score=score, reason=reason, run_id=run_id,
        )
        print(f"    → enqueue_manual_review returned {result}")
    else:
        print(f"    → calling enqueue_external_apply()")
        result = maq.enqueue_external_apply(
            job=job, score=score, reason=reason, run_id=run_id,
        )
        print(f"    → enqueue_external_apply returned {result}")

    # Verify file exists after write
    file_exists = os.path.exists(maq_path)
    print(f"    → File exists after save: {file_exists}")
    if file_exists:
        file_size = os.path.getsize(maq_path)
        print(f"    → File size: {file_size} bytes")
        data = json.loads(open(maq_path).read())
        print(f"    → Total records in MAQ: {len(data)}")

# Wrap MAQ methods to debug ALL subsequent calls
original_enqueue_manual = maq.enqueue_manual_review
original_enqueue_external = maq.enqueue_external_apply

def debug_enqueue_manual(job, score, reason, run_id):
    print(f"\n    [DEBUG] enqueue_manual_review:")
    print(f"      job type: {type(job).__name__}")
    jid = getattr(job, 'job_id', 'MISSING')
    print(f"      getattr(job, 'job_id', 'MISSING') = {repr(jid)}")
    print(f"      bool(job_id) = {bool(jid)}")
    result = original_enqueue_manual(job=job, score=score, reason=reason, run_id=run_id)
    print(f"      result: {result}")
    return result

def debug_enqueue_external(job, score, reason, run_id):
    print(f"\n    [DEBUG] enqueue_external_apply:")
    print(f"      job type: {type(job).__name__}")
    jid = getattr(job, 'job_id', 'MISSING')
    print(f"      getattr(job, 'job_id', 'MISSING') = {repr(jid)}")
    result = original_enqueue_external(job=job, score=score, reason=reason, run_id=run_id)
    print(f"      result: {result}")
    return result

maq.enqueue_manual_review = debug_enqueue_manual
maq.enqueue_external_apply = debug_enqueue_external

# ─────────────────────────────────────────────────────────────
# Test enqueue_manual_review directly
# ─────────────────────────────────────────────────────────────
print("\n── Phase A: Direct enqueue_manual_review call ──")
try:
    _enqueue_external(opp, score=85, reason="Manual review: rank #3", run_id="trace-run")
    check("enqueue_manual_review succeeded", True)
except Exception as e:
    check(f"enqueue_manual_review FAILED: {e}", False)
    traceback.print_exc()
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# Test enqueue_external_apply directly
# ─────────────────────────────────────────────────────────────
print("\n── Phase B: Direct enqueue_external_apply call ──")
try:
    _enqueue_external(opp_ats, score=90, reason="ATS detected: Lever", run_id="trace-run")
    check("enqueue_external_apply succeeded", True)
except Exception as e:
    check(f"enqueue_external_apply FAILED: {e}", False)
    traceback.print_exc()
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# Test via ApplicationScheduler (the EXACT path the pipeline uses)
# ─────────────────────────────────────────────────────────────
print("\n── Phase C: Via ApplicationScheduler (EXACT pipeline path) ──")

# Create WITH _enqueue_fn the same way the pipeline does
scheduler = ApplicationScheduler(
    opportunity_repo=repo,
    process_job_fn=None,  # No AUTO processing (test mode)
    enqueue_external_fn=_enqueue_external,
    exec_context=exec_ctx,
    ledger=ledger,
)
check("Scheduler created with enqueue_external_fn", 
      scheduler._enqueue_fn is not None, "fn set")
check("Scheduler._enqueue_fn is _enqueue_external", 
      scheduler._enqueue_fn is _enqueue_external, "same function")

# Create an ApplicationPlan with 1 manual + 1 ats
from src.orchestration.capacity_planner import ApplicationPlan, ApplicationPlanSummary

plan = ApplicationPlan(
    planned=[planned_manual, planned_ats],
    deferred=[],
    summary=ApplicationPlanSummary(
        total_pool=2, planned=2, deferred=0, expired=0, rejected=0,
    ),
)
check("ApplicationPlan created with 2 planned", len(plan.planned) == 2)

print("\n  4. Calling scheduler.execute()")

# Wrap MAQ methods to debug
original_enqueue_manual = maq.enqueue_manual_review
original_enqueue_external = maq.enqueue_external_apply

def debug_enqueue_manual(job, score, reason, run_id):
    print(f"\n    [DEBUG] enqueue_manual_review called:")
    print(f"      job type: {type(job).__name__}")
    print(f"      job_id attr: {getattr(job, 'job_id', 'MISSING')}")
    print(f"      dir(job)[:10]: {[a for a in dir(job) if not a.startswith('_')][:10]}")
    if hasattr(job, 'job_id'):
        print(f"      job.job_id = '{job.job_id}' (type={type(job.job_id).__name__})")
    result = original_enqueue_manual(job=job, score=score, reason=reason, run_id=run_id)
    print(f"      result: {result}")
    return result

def debug_enqueue_external(job, score, reason, run_id):
    print(f"\n    [DEBUG] enqueue_external_apply called:")
    print(f"      job type: {type(job).__name__}")
    print(f"      job.job_id = '{getattr(job, 'job_id', 'MISSING')}'")
    result = original_enqueue_external(job=job, score=score, reason=reason, run_id=run_id)
    print(f"      result: {result}")
    return result

maq.enqueue_manual_review = debug_enqueue_manual
maq.enqueue_external_apply = debug_enqueue_external
summary = scheduler.execute(plan, run_id="trace-run")
check("scheduler.execute returned", summary is not None)
check(f"  auto_applied={summary.auto_applied}", summary.auto_applied == 0, str(summary.auto_applied))
check(f"  manual_review={summary.manual_review}", summary.manual_review == 1, str(summary.manual_review))
check(f"  ats_queued={summary.ats_queued}", summary.ats_queued == 1, str(summary.ats_queued))
check(f"  errors={len(summary.errors)}", len(summary.errors) == 0, str(len(summary.errors)))

if summary.errors:
    print("\n  ERRORS FROM SCHEDULER:")
    for err in summary.errors:
        print(f"    {err}")

# ─────────────────────────────────────────────────────────────
# Verify final state
# ─────────────────────────────────────────────────────────────
print("\n── Phase D: Final verification ──")
check("MAQ file exists", os.path.exists(maq_path), maq_path)
final_data = json.loads(open(maq_path).read())
check(f"MAQ has {len(final_data)} records", len(final_data) == 4, f"expected=4 (2 from Phases A+B, 2 from Phase C)")
sources = [d.get("source") for d in final_data]
manual_count = sum(1 for s in sources if s == "manual_review")
external_count = sum(1 for s in sources if s == "external_apply")
check(f"  manual_review records: {manual_count}", manual_count == 2, str(manual_count))
check(f"  external_apply records: {external_count}", external_count == 2, str(external_count))

# Verify WorkflowQueue can read them
from src.application.workflow_queue import WorkflowQueue
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    wq_db = f.name
wq = WorkflowQueue(maq_path=maq_path, db_path=wq_db)
wq_items = wq.list()
check(f"WorkflowQueue sees {len(wq_items)} items", len(wq_items) == 4, str(len(wq_items)))

print(f"\n{'=' * 60}")
print(f"  ALL {step} STEPS PASSED")
print(f"  Pipeline enqueue path verified end-to-end")
print(f"  MAQ file: {maq_path}")
print(f"  Records: {len(final_data)} (manual={manual_count}, external={external_count})")
print(f"{'=' * 60}")

# Cleanup
for p in [maq_path, wq_db, ledger_db_path]:
    try: os.unlink(p)
    except: pass
try:
    shutil.rmtree(str(run_dir))
except: pass
