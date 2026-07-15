from typing import Dict, Any, List, Optional
from ..models import MemoryEntry, MemoryType, MemoryStatus, DecayConfig


class IOntologyMemoryEngine:
    def store(self, entry: MemoryEntry) -> MemoryEntry:
        raise NotImplementedError

    def retrieve(self, query: str, memory_type: Optional[MemoryType] = None,
                 top_k: int = 10, scenario_id: Optional[str] = None,
                 method_weights: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def consolidate(self, memory_ids: List[str], strategy: str = "merge") -> Dict[str, Any]:
        raise NotImplementedError

    def decay_update(self, config: Optional[DecayConfig] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def forget(self, threshold: float = 0.1, archive: bool = False) -> Dict[str, Any]:
        raise NotImplementedError

    def get_statistics(self, scenario_id: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError
