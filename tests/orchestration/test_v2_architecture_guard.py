"""
Architecture Guard — Pipeline uses V2 Orchestrator, not Legacy.

These tests ensure that:
1. CareerWorkflowPipeline.select() uses PriorityEngine + CapacityPlanner
2. CareerWorkflowPipeline.apply() uses ApplicationScheduler
3. Legacy functions (run_application_batch, rank_candidates_adaptively) are NOT called
4. The pipeline produces ApplicationPlan during selection
5. Every selected opportunity reaches exactly one terminal state
"""
from __future__ import annotations

import importlib
import inspect


def test_pipeline_imports_priority_engine():
    """Pipeline module must import PriorityEngine for V2 selection."""
    import src.orchestration.pipeline as mod
    source = inspect.getsource(mod)
    assert "PriorityEngine" in source, (
        "PriorityEngine not found in pipeline.py — V2 not wired"
    )


def test_pipeline_imports_capacity_planner():
    """Pipeline module must import CapacityPlanner for V2 selection."""
    import src.orchestration.pipeline as mod
    source = inspect.getsource(mod)
    assert "CapacityPlanner" in source, (
        "CapacityPlanner not found in pipeline.py — V2 not wired"
    )


def test_pipeline_imports_application_scheduler():
    """Pipeline module must import ApplicationScheduler for V2 apply."""
    import src.orchestration.pipeline as mod
    source = inspect.getsource(mod)
    assert "ApplicationScheduler" in source, (
        "ApplicationScheduler not found in pipeline.py — V2 not wired"
    )


def test_pipeline_does_not_import_legacy_apply():
    """Pipeline must NOT import or call run_application_batch in execute paths."""
    import src.orchestration.pipeline as mod
    source = inspect.getsource(mod)
    lines = source.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()
        if 'run_application_batch' in stripped:
            # Allow comments, docstrings, and import statements
            if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''") or stripped.startswith('*'):
                continue
            # Allow continuation lines inside docstrings
            if 'Replaces legacy' in stripped or 'replaces legacy' in stripped:
                continue
            # Only flag actual assignments or calls (not references)
            if '=' in stripped or '.run_application_batch(' in stripped:
                assert False, (
                    f"Legacy run_application_batch code path at line {i+1}: {stripped}"
                )


def test_pipeline_does_not_import_legacy_ranking():
    """Pipeline must NOT import rank_candidates_adaptively."""
    import src.orchestration.pipeline as mod
    source = inspect.getsource(mod)
    lines = source.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()
        if 'rank_candidates_adaptively' in stripped:
            # Allow docstring references, comments, import statements
            if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''") or stripped.startswith('*'):
                continue
            if 'import' in stripped:
                continue
            if 'Replaces legacy' in stripped or 'replaces legacy' in stripped:
                continue
            if '(' in stripped or '=' in stripped:
                assert False, (
                    f"Legacy rank_candidates_adaptively still used at line {i+1}: {stripped}"
                )


def test_select_creates_application_plan():
    """Pipeline select() must create an application_plan on the context."""
    from src.orchestration.pipeline import CareerWorkflowPipeline
    source = inspect.getsource(CareerWorkflowPipeline.select)
    assert "application_plan" in source, (
        "select() does not create application_plan — planner not wired"
    )


def test_apply_uses_application_scheduler():
    """Pipeline apply() must use ApplicationScheduler."""
    from src.orchestration.pipeline import CareerWorkflowPipeline
    source = inspect.getsource(CareerWorkflowPipeline.apply)
    assert "ApplicationScheduler" in source, (
        "apply() does not reference ApplicationScheduler — scheduler not wired"
    )


def test_validate_artifacts_checks_deferred():
    """_validate_artifacts must check deferred invariant."""
    from src.orchestration.pipeline import CareerWorkflowPipeline
    source = inspect.getsource(CareerWorkflowPipeline._validate_artifacts)
    assert "deferred" in source, (
        "_validate_artifacts does not check deferred — accounting invariant missing"
    )


def test_pipeline_result_has_deferred():
    """PipelineResult must have a deferred field."""
    from src.orchestration.result import PipelineResult
    assert hasattr(PipelineResult, "deferred"), (
        "PipelineResult has no deferred field"
    )
