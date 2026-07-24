from typing import List, Dict, Set
from collections import deque
from src.core.features.graph import FeatureDependencyGraph

class ExecutionPlanner:
    """
    Execution Planner: Generates topological and levelized execution plans for feature extraction based on DAG dependencies.
    """
    def __init__(self, graph: FeatureDependencyGraph):
        self.graph = graph

    def plan_execution(self) -> List[str]:
        """Flat topological ordering."""
        levels = self.plan_execution_levels()
        flat_plan = []
        for level in levels:
            flat_plan.extend(level)
        return flat_plan

    def plan_execution_levels(self) -> List[List[str]]:
        """Levelized execution ordering: Features at the same level can execute concurrently."""
        self.graph.validate_no_cycles()
        dag = self.graph.build_dag()
        
        in_degree = {node: len(deps) for node, deps in dag.items()}
        adj_list: Dict[str, List[str]] = {node: [] for node in dag}

        for node, deps in dag.items():
            for dep in deps:
                if dep in adj_list:
                    adj_list[dep].append(node)

        # Level 0: nodes with 0 dependencies
        current_level = [node for node, deg in in_degree.items() if deg == 0]
        levels: List[List[str]] = []

        while current_level:
            levels.append(sorted(current_level))
            next_level = []
            
            for curr in current_level:
                for neighbor in adj_list.get(curr, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_level.append(neighbor)
                        
            current_level = next_level

        return levels
