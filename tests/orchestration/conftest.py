"""
Pytest configuration for orchestration tests.

Ensures every test gets an isolated JobLifecycleStore (:memory:) so that
test data never leaks between tests via the shared default SQLite path.
"""

import pytest
from src.orchestration.context import PipelineContext


@pytest.fixture(autouse=True)
def _isolated_lifecycle(monkeypatch):
    """Patch PipelineContext to use :memory: lifecycle store."""
    from src.orchestration.job_lifecycle import JobLifecycleStore
    original_init = PipelineContext.__init__
    def _patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.lifecycle = JobLifecycleStore(":memory:")
    monkeypatch.setattr(PipelineContext, "__init__", _patched_init)
