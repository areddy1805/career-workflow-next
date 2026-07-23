import os
from types import SimpleNamespace
from unittest.mock import patch

from src.orchestration.pipeline import CareerWorkflowPipeline


def test_selection_uses_scan_budget_not_attempt_budget(tmp_path):
    pipeline = CareerWorkflowPipeline(
        dry_run=False,
        max_applications=1,
        artifacts_root=tmp_path,
    )

    # select() is normally called through run(), which creates the
    # per-run artifact directory. This unit test invokes select()
    # directly, so reproduce that lifecycle precondition.
    pipeline.run_dir.mkdir(parents=True, exist_ok=True)

    jobs = [
        SimpleNamespace(
            job_id=str(i),
            title=f"Job {i}",
            company=f"C{i}",
        )
        for i in range(10)
    ]

    pipeline.context.acquired_jobs = jobs
    pipeline.context.classified_jobs = [{"job_id": str(i)} for i in range(10)]
    pipeline.context.score_map = {str(i): {"score": 90 - i} for i in range(10)}

    pipeline.context.ledger = SimpleNamespace(
        applied_job_ids=lambda: set(),
        metadata_completeness=lambda: {"coverage": 1.0},
        company_application_counts=lambda: {},
    )

    strategy = SimpleNamespace(
        max_applications_per_run=1,
    )

    with (
        patch.object(
            pipeline,
            "_build_adaptive_strategy",
            return_value=strategy,
        ),
        patch(
            "src.orchestration.pipeline.rank_candidates_adaptively",
            side_effect=lambda jobs, **_: jobs,
        ),
        patch(
            "src.orchestration.pipeline.diversify_jobs",
            side_effect=lambda jobs, **_: jobs,
        ),
        patch(
            "src.orchestration.pipeline.select_candidates_with_exploration",
            side_effect=lambda jobs, limit, **_: jobs[:limit],
        ),
        patch(
            "src.orchestration.pipeline.strategy_audit_payload",
            return_value={},
        ),
        patch.dict(
            os.environ,
            {"APPLICATION_SCAN_MULTIPLIER": "5"},
        ),
    ):
        pipeline.select()

    assert len(pipeline.context.selected_jobs) == 5
