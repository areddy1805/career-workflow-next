from dataclasses import dataclass, field
from src.core.pipeline.subcontexts import (
    RunContext, ExecutionContext, CandidateContext, DependencyContext,
    RuntimeContext, MetricsContext, BudgetContext, KnowledgeContext, ConfigurationContext
)

@dataclass
class PipelineContext:
    """
    Composed PipelineContext composed of explicit immutable subcontexts.
    Prevents god-object anti-pattern as the system expands.
    """
    run: RunContext
    execution: ExecutionContext = field(default_factory=ExecutionContext)
    candidate: CandidateContext = field(default_factory=CandidateContext)
    dependencies: DependencyContext = field(default_factory=DependencyContext)
    runtime: RuntimeContext = field(default_factory=RuntimeContext)
    metrics: MetricsContext = field(default_factory=MetricsContext)
    budget: BudgetContext = field(default_factory=BudgetContext)
    knowledge: KnowledgeContext = field(default_factory=KnowledgeContext)
    configuration: ConfigurationContext = field(default_factory=ConfigurationContext)

