from typing import Dict, List, Set
from src.core.features.registry import FeatureRegistry

class FeatureDependencyGraph:
    """
    Directed Acyclic Graph (DAG) representing explicit inter-feature dependencies.
    Validates cycle detection and dependency ordering.
    """
    def __init__(self, registry: FeatureRegistry):
        self.registry = registry

    def build_dag(self) -> Dict[str, List[str]]:
        dag: Dict[str, List[str]] = {}
        for feature in self.registry.list_enabled():
            dag[feature.id] = list(feature.dependencies)
        return dag

    def validate_no_cycles(self) -> bool:
        dag = self.build_dag()
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for dep in dag.get(node, []):
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for node in dag:
            if node not in visited:
                if dfs(node):
                    raise ValueError(f"Cyclic dependency detected in Feature Dependency Graph involving feature '{node}'.")
        return True
