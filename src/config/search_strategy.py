import os
import yaml
from dataclasses import dataclass, field


@dataclass
class SummaryScoringConfig:
    mandatory_weight: int = 3
    skills_weight: int = 1
    recency_weight: int = 2


@dataclass
class SearchStrategyConfig:
    spray_and_pray: bool = True
    summary_fetch_budget: int = 500
    detail_fetch_budget: int = 500
    application_budget: int = 500
    rank_before_fetch: bool = True
    ai_is_ranking_only: bool = True
    reject_non_engineering: bool = True
    reject_walkins: bool = True
    reject_duplicates: bool = True
    summary_scoring: SummaryScoringConfig = field(default_factory=SummaryScoringConfig)


def load_search_strategy() -> SearchStrategyConfig:
    config_path = os.environ.get(
        "SEARCH_STRATEGY_CONFIG", "config/search_strategy.yaml"
    )
    if not os.path.exists(config_path):
        return SearchStrategyConfig()

    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
            strategy_data = data.get("strategy", {})
            if "summary_scoring" in strategy_data:
                strategy_data["summary_scoring"] = SummaryScoringConfig(
                    **strategy_data["summary_scoring"]
                )
            return SearchStrategyConfig(**strategy_data)
    except Exception as e:
        print(f"Warning: Failed to load search strategy from {config_path}: {e}")
        return SearchStrategyConfig()
