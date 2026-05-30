import time
import threading
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DecayConfig:
    default_half_life_hours: float = 24.0
    min_importance_threshold: float = 0.1
    consolidation_threshold: float = 0.8
    decay_check_interval_seconds: float = 3600.0
    batch_size: int = 100


class MemoryDecayScheduler:
    _instance: Optional["MemoryDecayScheduler"] = None

    @classmethod
    def get_instance(cls, storage=None, config: DecayConfig = None):
        if cls._instance is None:
            cls._instance = cls(storage, config or DecayConfig())
        return cls._instance

    @classmethod
    def reset_instance(cls):
        if cls._instance is not None:
            cls._instance.stop()
        cls._instance = None

    def __init__(self, storage, config: DecayConfig):
        self._storage = storage
        self._config = config
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable] = []
        self._stats = {
            "total_decayed": 0,
            "total_consolidated": 0,
            "total_forgotten": 0,
            "last_run": None,
        }

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def register_callback(self, callback: Callable):
        self._callbacks.append(callback)

    def run_decay_cycle(self) -> Dict[str, Any]:
        if not self._storage:
            return {"status": "error", "message": "No storage configured"}
        now = datetime.now().isoformat()
        decayed_count = 0
        consolidated_count = 0
        forgotten_count = 0
        try:
            memories = self._storage.list_memories(limit=self._config.batch_size)
            for memory in memories:
                importance = self._calculate_importance(memory)
                if importance < self._config.min_importance_threshold:
                    self._storage.delete_memory(memory.get("memory_id", ""))
                    forgotten_count += 1
                    self._notify("forget", memory)
                elif importance >= self._config.consolidation_threshold:
                    self._storage.update_memory(
                        memory.get("memory_id", ""),
                        {"importance": importance, "status": "consolidated"},
                    )
                    consolidated_count += 1
                    self._notify("consolidate", memory)
                else:
                    self._storage.update_memory(
                        memory.get("memory_id", ""),
                        {"importance": importance},
                    )
                    decayed_count += 1
                    self._notify("decay", memory)
        except Exception as e:
            return {"status": "error", "message": str(e)}
        self._stats["total_decayed"] += decayed_count
        self._stats["total_consolidated"] += consolidated_count
        self._stats["total_forgotten"] += forgotten_count
        self._stats["last_run"] = now
        return {
            "status": "success",
            "decayed": decayed_count,
            "consolidated": consolidated_count,
            "forgotten": forgotten_count,
            "timestamp": now,
        }

    def get_stats(self) -> Dict[str, Any]:
        return {**self._stats}

    def update_config(self, **kwargs) -> Dict[str, Any]:
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        return {"status": "success", "config": {
            "default_half_life_hours": self._config.default_half_life_hours,
            "min_importance_threshold": self._config.min_importance_threshold,
            "consolidation_threshold": self._config.consolidation_threshold,
            "decay_check_interval_seconds": self._config.decay_check_interval_seconds,
            "batch_size": self._config.batch_size,
        }}

    def _calculate_importance(self, memory: Dict[str, Any]) -> float:
        current_importance = memory.get("importance", 0.5)
        created_at = memory.get("created_at", "")
        access_count = memory.get("access_count", 0)
        try:
            created = datetime.fromisoformat(created_at)
            hours_elapsed = (datetime.now() - created).total_seconds() / 3600
        except (ValueError, TypeError):
            hours_elapsed = 0
        half_life = self._config.default_half_life_hours
        decay_factor = 0.5 ** (hours_elapsed / half_life) if half_life > 0 else 1.0
        access_boost = min(access_count * 0.05, 0.3)
        return min(max(current_importance * decay_factor + access_boost, 0.0), 1.0)

    def _notify(self, event_type: str, memory: Dict[str, Any]):
        for cb in self._callbacks:
            try:
                cb(event_type, memory)
            except Exception:
                pass

    def _run_loop(self):
        while self._running:
            try:
                self.run_decay_cycle()
            except Exception:
                pass
            time.sleep(self._config.decay_check_interval_seconds)
