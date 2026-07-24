import pytest
from src.core.inference.budget_manager import HierarchicalBudgetManager
from src.core.ranking.decision_graph import DecisionGraph
from src.core.ranking.evaluator import ContinuousEvaluator, RunMetrics

def test_release_3_1_subsystems():
    # 1. BudgetManager
    bm = HierarchicalBudgetManager("config/inference_budget.yaml")
    assert bm.can_invoke_llm("qwen", "classification") is True
    bm.record_llm_invocation(100, "qwen", "classification")
    assert bm.run_llm_calls_used == 1

    # 2. DecisionGraph
    graph = DecisionGraph("job_101", "hash_abc_123")
    graph.record_step("Normalization", 2.5, {"status": "SUCCESS"})
    graph.record_step("RuleEngine", 1.2, {"boosts": 15.0})
    dict_repr = graph.to_dict()
    assert dict_repr["job_id"] == "job_101"
    assert len(dict_repr["steps"]) == 2

    # 3. ContinuousEvaluator
    baseline = RunMetrics(runtime_sec=100.0, total_jobs=1700, llm_calls=1100, llm_reduction_pct=35.0, cache_hit_rate=0.50, false_negative_rate=0.01)
    current = RunMetrics(runtime_sec=20.0, total_jobs=1700, llm_calls=180, llm_reduction_pct=89.4, cache_hit_rate=0.92, false_negative_rate=0.005)
    
    evaluator = ContinuousEvaluator(baseline)
    res = evaluator.evaluate_run(current)
    
    assert res["passed_gate"] is True
    assert res["vs_baseline"]["runtime_speedup"] == 5.0
    assert res["vs_best_ever"]["is_new_best_ever"] is True
