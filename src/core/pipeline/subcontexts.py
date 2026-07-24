from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

@dataclass(frozen=True)
class RunContext:
    run_id: str
    started_at: str = ""
    environment: str = "production"

@dataclass(frozen=True)
class ExecutionContext:
    dry_run: bool = False
    test_mode: bool = False
    acquisition_mode: str = "full"
    force_live: bool = False

@dataclass(frozen=True)
class CandidateContext:
    profile: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class DependencyContext:
    metrics_collector: Any = None
    event_publisher: Any = None
    cache_manager: Any = None
    feature_store: Any = None
    knowledge_store: Any = None
    decision_ledger: Any = None
    observability: Any = None

@dataclass(frozen=True)
class RuntimeContext:
    pid: int = 0
    job_batch: Tuple[Any, ...] = field(default_factory=tuple)

@dataclass(frozen=True)
class MetricsContext:
    stage_durations: Dict[str, int] = field(default_factory=dict)

@dataclass(frozen=True)
class BudgetContext:
    daily_token_limit: int = 100000
    current_tokens_used: int = 0

@dataclass(frozen=True)
class KnowledgeContext:
    knowledge_store_ptr: Any = None

@dataclass(frozen=True)
class ConfigurationContext:
    config_dict: Dict[str, Any] = field(default_factory=dict)
