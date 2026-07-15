import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from odap.biz.platform.ontology_memory.services.decay_scheduler import (
    MemoryDecayScheduler, DecayConfig,
)


def _make_memory(**overrides):
    defaults = {
        "memory_id": "mem-001",
        "importance": 0.5,
        "created_at": datetime.now().isoformat(),
        "access_count": 0,
    }
    defaults.update(overrides)
    return defaults


class TestDecayConfig:
    def test_default_values(self):
        config = DecayConfig()
        assert config.default_half_life_hours == 24.0
        assert config.min_importance_threshold == 0.1
        assert config.consolidation_threshold == 0.8
        assert config.decay_check_interval_seconds == 3600.0
        assert config.batch_size == 100

    def test_custom_values(self):
        config = DecayConfig(
            default_half_life_hours=48.0,
            min_importance_threshold=0.2,
            consolidation_threshold=0.9,
        )
        assert config.default_half_life_hours == 48.0
        assert config.min_importance_threshold == 0.2
        assert config.consolidation_threshold == 0.9


class TestMemoryDecayScheduler:
    def setup_method(self):
        MemoryDecayScheduler.reset_instance()

    def teardown_method(self):
        MemoryDecayScheduler.reset_instance()

    def test_no_storage_error(self):
        scheduler = MemoryDecayScheduler(storage=None, config=DecayConfig())
        result = scheduler.run_decay_cycle()
        assert result["status"] == "error"
        assert "No storage" in result["message"]

    def test_decay_cycle_basic(self):
        storage = MagicMock()
        old_time = (datetime.now() - timedelta(hours=48)).isoformat()
        storage.list_memories.return_value = [
            _make_memory(memory_id="m1", importance=0.5, created_at=old_time, access_count=0),
        ]
        scheduler = MemoryDecayScheduler(storage=storage, config=DecayConfig(
            default_half_life_hours=24.0, min_importance_threshold=0.1,
            consolidation_threshold=0.8,
        ))
        result = scheduler.run_decay_cycle()
        assert result["status"] == "success"

    def test_forgotten_memory(self):
        storage = MagicMock()
        old_time = (datetime.now() - timedelta(hours=200)).isoformat()
        storage.list_memories.return_value = [
            _make_memory(memory_id="m1", importance=0.05, created_at=old_time, access_count=0),
        ]
        scheduler = MemoryDecayScheduler(storage=storage, config=DecayConfig(
            default_half_life_hours=24.0, min_importance_threshold=0.1,
            consolidation_threshold=0.8,
        ))
        result = scheduler.run_decay_cycle()
        assert result["forgotten"] == 1
        storage.delete_memory.assert_called_once_with("m1")

    def test_consolidated_memory(self):
        storage = MagicMock()
        recent_time = datetime.now().isoformat()
        storage.list_memories.return_value = [
            _make_memory(memory_id="m1", importance=0.95, created_at=recent_time, access_count=10),
        ]
        scheduler = MemoryDecayScheduler(storage=storage, config=DecayConfig(
            default_half_life_hours=24.0, min_importance_threshold=0.1,
            consolidation_threshold=0.8,
        ))
        result = scheduler.run_decay_cycle()
        assert result["consolidated"] == 1

    def test_decayed_memory(self):
        storage = MagicMock()
        mid_time = (datetime.now() - timedelta(hours=12)).isoformat()
        storage.list_memories.return_value = [
            _make_memory(memory_id="m1", importance=0.5, created_at=mid_time, access_count=0),
        ]
        scheduler = MemoryDecayScheduler(storage=storage, config=DecayConfig(
            default_half_life_hours=24.0, min_importance_threshold=0.1,
            consolidation_threshold=0.8,
        ))
        result = scheduler.run_decay_cycle()
        assert result["decayed"] == 1

    def test_get_stats(self):
        storage = MagicMock()
        storage.list_memories.return_value = []
        scheduler = MemoryDecayScheduler(storage=storage, config=DecayConfig())
        stats = scheduler.get_stats()
        assert "total_decayed" in stats
        assert "total_consolidated" in stats
        assert "total_forgotten" in stats

    def test_register_callback(self):
        storage = MagicMock()
        storage.list_memories.return_value = []
        scheduler = MemoryDecayScheduler(storage=storage, config=DecayConfig())
        callback = MagicMock()
        scheduler.register_callback(callback)
        assert callback in scheduler._callbacks

    def test_update_config(self):
        storage = MagicMock()
        scheduler = MemoryDecayScheduler(storage=storage, config=DecayConfig())
        result = scheduler.update_config(default_half_life_hours=48.0)
        assert result["status"] == "success"
        assert result["config"]["default_half_life_hours"] == 48.0

    def test_start_stop(self):
        storage = MagicMock()
        config = DecayConfig(decay_check_interval_seconds=0.1)
        scheduler = MemoryDecayScheduler(storage=storage, config=config)
        scheduler.start()
        assert scheduler._running is True
        scheduler.stop()
        assert scheduler._running is False

    def test_calculate_importance_with_access_boost(self):
        storage = MagicMock()
        scheduler = MemoryDecayScheduler(storage=storage, config=DecayConfig(
            default_half_life_hours=24.0,
        ))
        recent_time = datetime.now().isoformat()
        memory = _make_memory(importance=0.5, created_at=recent_time, access_count=5)
        importance = scheduler._calculate_importance(memory)
        assert importance > 0.5

    def test_calculate_importance_old_memory(self):
        storage = MagicMock()
        scheduler = MemoryDecayScheduler(storage=storage, config=DecayConfig(
            default_half_life_hours=24.0,
        ))
        old_time = (datetime.now() - timedelta(hours=100)).isoformat()
        memory = _make_memory(importance=0.5, created_at=old_time, access_count=0)
        importance = scheduler._calculate_importance(memory)
        assert importance < 0.5

    def test_callback_notified_on_forget(self):
        storage = MagicMock()
        old_time = (datetime.now() - timedelta(hours=200)).isoformat()
        storage.list_memories.return_value = [
            _make_memory(memory_id="m1", importance=0.05, created_at=old_time, access_count=0),
        ]
        scheduler = MemoryDecayScheduler(storage=storage, config=DecayConfig(
            default_half_life_hours=24.0, min_importance_threshold=0.1,
            consolidation_threshold=0.8,
        ))
        callback = MagicMock()
        scheduler.register_callback(callback)
        scheduler.run_decay_cycle()
        callback.assert_called_once()
        assert callback.call_args[0][0] == "forget"
