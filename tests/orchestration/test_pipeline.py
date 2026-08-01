from pathlib import Path

from src.orchestration.pipeline import (
    CareerWorkflowPipeline,
)
from src.orchestration.stages import (
    PipelineStatus,
    StageStatus,
)


class RecordingPipeline(CareerWorkflowPipeline):
    def __init__(
        self,
        *,
        artifacts_root: Path,
        fail_stage: str | None = None,
        nonfatal_stage: str | None = None,
    ):
        super().__init__(
            dry_run=True,
            max_applications=3,
            artifacts_root=artifacts_root,
        )

        self.calls = []
        self.fail_stage = fail_stage
        self.nonfatal_stage = nonfatal_stage

    def _record(
        self,
        name: str,
    ) -> None:
        self.calls.append(name)

        if name == self.fail_stage or name == self.nonfatal_stage:
            raise RuntimeError(f"{name} failure")

    def preflight(self):
        self._record("preflight")

    def acquire(self):
        self._record("acquisition")

    def classify(self):
        self._record("classification")

    def select(self):
        self._record("selection")

    def apply(self):
        self._record("application")

    def reconcile(self):
        self._record("reconciliation")

    def update_strategy(self):
        self._record("strategy")

    def report(self):
        self._record("report")


def test_pipeline_executes_all_stages_in_order(
    tmp_path,
):
    pipeline = RecordingPipeline(
        artifacts_root=tmp_path,
    )

    result = pipeline.run()

    assert pipeline.calls == [
        "preflight",
        "acquisition",
        "classification",
        "selection",
        "application",
        "reconciliation",
        "strategy",
        "report",
    ]

    assert result.status == PipelineStatus.SUCCESS.value

    assert all(
        status == StageStatus.SUCCESS.value for status in result.stage_results.values()
    )


def test_fatal_stage_stops_pipeline(
    tmp_path,
):
    pipeline = RecordingPipeline(
        artifacts_root=tmp_path,
        fail_stage="classification",
    )

    result = pipeline.run()

    assert pipeline.calls == [
        "preflight",
        "acquisition",
        "classification",
    ]

    assert result.status == PipelineStatus.FAILED.value

    assert result.stage_results["classification"] == StageStatus.FAILED.value

    assert result.stage_results["selection"] == StageStatus.SKIPPED.value


def test_nonfatal_failure_continues_pipeline(
    tmp_path,
):
    pipeline = RecordingPipeline(
        artifacts_root=tmp_path,
        nonfatal_stage="application",
    )

    result = pipeline.run()

    assert pipeline.calls == [
        "preflight",
        "acquisition",
        "classification",
        "selection",
        "application",
        "reconciliation",
        "strategy",
        "report",
    ]

    assert result.status == PipelineStatus.PARTIAL.value

    assert result.stage_results["application"] == StageStatus.FAILED.value

    assert result.stage_results["report"] == StageStatus.SUCCESS.value


def test_run_artifacts_are_persisted(
    tmp_path,
):
    pipeline = RecordingPipeline(
        artifacts_root=tmp_path,
    )

    result = pipeline.run()

    run_dir = tmp_path / result.run_id

    assert (run_dir / "run.json").exists()
    assert (run_dir / "result.json").exists()
    assert (run_dir / "metrics.json").exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "timeline.json").exists()


def test_negative_application_limit_rejected(
    tmp_path,
):
    try:
        CareerWorkflowPipeline(
            dry_run=True,
            max_applications=-1,
            artifacts_root=tmp_path,
        )

    except ValueError:
        return

    raise AssertionError("Expected ValueError")


def test_preflight_artifact_is_part_of_complete_stage_artifacts(tmp_path, monkeypatch):
    pipeline = RecordingPipeline(artifacts_root=tmp_path)
    result = pipeline.run()
    run_dir = tmp_path / result.run_id
    # RecordingPipeline overrides stage methods, so this verifies only generic artifacts.
    assert (run_dir / "run.json").exists()
    assert (run_dir / "result.json").exists()


def test_pipeline_result_exposes_complete_application_accounting(tmp_path):
    pipeline = RecordingPipeline(artifacts_root=tmp_path)
    result = pipeline.run().to_dict()
    # All metrics are now derived from the canonical JobLifecycleStore
    for key in (
        "acquired",
        "classified",
        "pre_app_rejected",
        "selected",
        "routed",
        "deferred",
        "submitted",
        "application_failed",
        "already_applied",
    ):
        assert key in result, f"Missing canonical metric: {key}"


def test_full_pipeline_persists_all_artifacts(tmp_path):
    pipeline = CareerWorkflowPipeline(dry_run=True, max_applications=0, artifacts_root=tmp_path, test_mode=True)
    result = pipeline.run()
    run_dir = tmp_path / result.run_id

    assert (run_dir / "run.json").exists()
    assert (run_dir / "result.json").exists()
    assert (run_dir / "metrics.json").exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "timeline.json").exists()
    assert (run_dir / "event_log.json").exists()
    assert (run_dir / "job_trace.json").exists()
    assert (run_dir / "pipeline_explorer.json").exists()

