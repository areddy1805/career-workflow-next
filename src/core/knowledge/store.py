from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

@dataclass
class KnowledgeEntity:
    """
    Generic versioned entity payload stored in KnowledgeStore.
    """
    entity_id: str
    entity_type: str  # "Company", "Recruiter", "Role", "Skill", "Question", "Job"
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    confidence: int = 90
    source: str = "pipeline"
    payload: Dict[str, Any] = field(default_factory=dict)

class KnowledgeStore:
    """
    Release 3.2 Phase 10: Generic Versioned Knowledge Store.
    Future-proof entity store managing Company, Recruiter, Role, Skill, Question, and Job historical decisions.
    """
    def __init__(self):
        self._store: Dict[str, KnowledgeEntity] = {}

    def put(self, entity: KnowledgeEntity) -> None:
        self._store[entity.entity_id] = entity

    def get(self, entity_id: str) -> Optional[KnowledgeEntity]:
        return self._store.get(entity_id)

    def list_by_type(self, entity_type: str) -> List[KnowledgeEntity]:
        return [e for e in self._store.values() if e.entity_type == entity_type]
