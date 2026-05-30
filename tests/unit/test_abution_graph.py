import pytest
import os
from datetime import datetime

from odap.biz.core.ontology.abution_graph.models.types import (
    TemporalDimension, PatternType, ForceType, ActionDimension,
    TemporalNode, PatternNode, ForceNode, ActionNode, AbutionGraphSnapshot,
)
from odap.biz.core.ontology.abution_graph.storage.sqlite_abution_storage import SQLiteAbutionStorage
from odap.biz.core.ontology.abution_graph.services.abution_graph_service import AbutionGraphService


def _make_temporal_node(**overrides):
    defaults = {
        "node_id": "tn-001", "dimension": TemporalDimension.PRESENT,
        "timestamp": datetime.now().isoformat(), "description": "test temporal",
        "confidence": 0.9, "metadata": {},
    }
    defaults.update(overrides)
    return TemporalNode(**defaults)


def _make_pattern_node(**overrides):
    defaults = {
        "pattern_id": "pn-001", "pattern_type": PatternType.STRUCTURAL,
        "name": "test pattern", "description": "test",
        "evidence": ["e1"], "strength": 0.7, "metadata": {},
    }
    defaults.update(overrides)
    return PatternNode(**defaults)


def _make_force_node(**overrides):
    defaults = {
        "force_id": "fn-001", "force_type": ForceType.DRIVING,
        "name": "test force", "magnitude": 0.8, "direction": 1.0,
        "description": "test", "metadata": {},
    }
    defaults.update(overrides)
    return ForceNode(**defaults)


def _make_action_node(**overrides):
    defaults = {
        "action_id": "an-001", "dimension": ActionDimension.DECIDE,
        "name": "test action", "trigger_condition": "cond",
        "effect": "eff", "priority": 5, "metadata": {},
    }
    defaults.update(overrides)
    return ActionNode(**defaults)


def _make_snapshot(**overrides):
    defaults = {
        "snapshot_id": "snap-001", "name": "test snapshot",
        "temporal_nodes": [], "pattern_nodes": [],
        "force_nodes": [], "action_nodes": [],
        "cross_dimension_links": [],
    }
    defaults.update(overrides)
    return AbutionGraphSnapshot(**defaults)


class TestEnums:
    def test_temporal_dimension_values(self):
        assert TemporalDimension.PAST.value == "past"
        assert TemporalDimension.PRESENT.value == "present"
        assert TemporalDimension.FUTURE.value == "future"
        assert TemporalDimension.HYPOTHETICAL.value == "hypothetical"

    def test_pattern_type_values(self):
        assert PatternType.STRUCTURAL.value == "structural"
        assert PatternType.BEHAVIORAL.value == "behavioral"
        assert PatternType.TEMPORAL.value == "temporal"
        assert PatternType.CAUSAL.value == "causal"

    def test_force_type_values(self):
        assert ForceType.DRIVING.value == "driving"
        assert ForceType.RESTRAINING.value == "restraining"
        assert ForceType.LEVERAGING.value == "leveraging"
        assert ForceType.EMERGING.value == "emerging"

    def test_action_dimension_values(self):
        assert ActionDimension.OBSERVE.value == "observe"
        assert ActionDimension.ORIENT.value == "orient"
        assert ActionDimension.DECIDE.value == "decide"
        assert ActionDimension.ACT.value == "act"


class TestDataclasses:
    def test_temporal_node_defaults(self):
        node = _make_temporal_node()
        assert node.confidence == 0.9
        assert node.metadata == {}

    def test_pattern_node_defaults(self):
        node = _make_pattern_node()
        assert node.evidence == ["e1"]
        assert node.strength == 0.7

    def test_force_node_defaults(self):
        node = _make_force_node()
        assert node.magnitude == 0.8
        assert node.direction == 1.0

    def test_action_node_defaults(self):
        node = _make_action_node()
        assert node.priority == 5

    def test_snapshot_auto_created_at(self):
        snap = _make_snapshot()
        assert snap.created_at is not None


class TestSQLiteAbutionStorage:
    def test_save_and_get(self, tmp_path):
        db_path = str(tmp_path / "test_abution.db")
        storage = SQLiteAbutionStorage(db_path=db_path)
        snapshot = _make_snapshot(temporal_nodes=[_make_temporal_node()])
        storage.save(snapshot)
        result = storage.get("snap-001")
        assert result is not None
        assert result.snapshot_id == "snap-001"
        assert result.name == "test snapshot"
        assert len(result.temporal_nodes) == 1

    def test_get_not_found(self, tmp_path):
        db_path = str(tmp_path / "test_abution.db")
        storage = SQLiteAbutionStorage(db_path=db_path)
        result = storage.get("nonexistent")
        assert result is None

    def test_list_snapshots(self, tmp_path):
        db_path = str(tmp_path / "test_abution.db")
        storage = SQLiteAbutionStorage(db_path=db_path)
        storage.save(_make_snapshot(snapshot_id="s1", name="snap1"))
        storage.save(_make_snapshot(snapshot_id="s2", name="snap2"))
        results = storage.list(limit=10)
        assert len(results) == 2

    def test_delete_snapshot(self, tmp_path):
        db_path = str(tmp_path / "test_abution.db")
        storage = SQLiteAbutionStorage(db_path=db_path)
        storage.save(_make_snapshot())
        assert storage.delete("snap-001") is True
        assert storage.get("snap-001") is None

    def test_delete_not_found(self, tmp_path):
        db_path = str(tmp_path / "test_abution.db")
        storage = SQLiteAbutionStorage(db_path=db_path)
        assert storage.delete("nonexistent") is False

    def test_save_with_all_node_types(self, tmp_path):
        db_path = str(tmp_path / "test_abution.db")
        storage = SQLiteAbutionStorage(db_path=db_path)
        snapshot = _make_snapshot(
            temporal_nodes=[_make_temporal_node()],
            pattern_nodes=[_make_pattern_node()],
            force_nodes=[_make_force_node()],
            action_nodes=[_make_action_node()],
            cross_dimension_links=[{"source_dim": "temporal", "source_id": "tn-001",
                                    "target_dim": "force", "target_id": "fn-001",
                                    "link_type": "causal"}],
        )
        storage.save(snapshot)
        result = storage.get("snap-001")
        assert len(result.temporal_nodes) == 1
        assert len(result.pattern_nodes) == 1
        assert len(result.force_nodes) == 1
        assert len(result.action_nodes) == 1
        assert len(result.cross_dimension_links) == 1

    def test_upsert_overwrite(self, tmp_path):
        db_path = str(tmp_path / "test_abution.db")
        storage = SQLiteAbutionStorage(db_path=db_path)
        storage.save(_make_snapshot(name="v1"))
        storage.save(_make_snapshot(name="v2"))
        result = storage.get("snap-001")
        assert result.name == "v2"


class TestAbutionGraphService:
    def test_create_snapshot(self, tmp_path):
        from unittest.mock import patch
        db_path = str(tmp_path / "test_abution.db")
        with patch.object(AbutionGraphService, '_instance', None):
            storage = SQLiteAbutionStorage(db_path=db_path)
            service = AbutionGraphService(storage=storage)
            result = service.create_snapshot(name="test")
            assert result["status"] == "success"
            assert "snapshot_id" in result

    def test_get_snapshot(self, tmp_path):
        from unittest.mock import patch
        db_path = str(tmp_path / "test_abution.db")
        with patch.object(AbutionGraphService, '_instance', None):
            storage = SQLiteAbutionStorage(db_path=db_path)
            service = AbutionGraphService(storage=storage)
            created = service.create_snapshot(name="test")
            result = service.get_snapshot(created["snapshot_id"])
            assert result["status"] == "success"
            assert result["name"] == "test"

    def test_get_snapshot_not_found(self, tmp_path):
        from unittest.mock import patch
        db_path = str(tmp_path / "test_abution.db")
        with patch.object(AbutionGraphService, '_instance', None):
            storage = SQLiteAbutionStorage(db_path=db_path)
            service = AbutionGraphService(storage=storage)
            result = service.get_snapshot("nonexistent")
            assert result["status"] == "error"

    def test_list_snapshots(self, tmp_path):
        from unittest.mock import patch
        db_path = str(tmp_path / "test_abution.db")
        with patch.object(AbutionGraphService, '_instance', None):
            storage = SQLiteAbutionStorage(db_path=db_path)
            service = AbutionGraphService(storage=storage)
            service.create_snapshot(name="s1")
            service.create_snapshot(name="s2")
            result = service.list_snapshots()
            assert result["status"] == "success"
            assert result["count"] == 2

    def test_delete_snapshot(self, tmp_path):
        from unittest.mock import patch
        db_path = str(tmp_path / "test_abution.db")
        with patch.object(AbutionGraphService, '_instance', None):
            storage = SQLiteAbutionStorage(db_path=db_path)
            service = AbutionGraphService(storage=storage)
            created = service.create_snapshot(name="test")
            result = service.delete_snapshot(created["snapshot_id"])
            assert result["status"] == "success"

    def test_delete_snapshot_not_found(self, tmp_path):
        from unittest.mock import patch
        db_path = str(tmp_path / "test_abution.db")
        with patch.object(AbutionGraphService, '_instance', None):
            storage = SQLiteAbutionStorage(db_path=db_path)
            service = AbutionGraphService(storage=storage)
            result = service.delete_snapshot("nonexistent")
            assert result["status"] == "error"

    def test_add_dimension_node_temporal(self, tmp_path):
        from unittest.mock import patch
        db_path = str(tmp_path / "test_abution.db")
        with patch.object(AbutionGraphService, '_instance', None):
            storage = SQLiteAbutionStorage(db_path=db_path)
            service = AbutionGraphService(storage=storage)
            created = service.create_snapshot(name="test")
            result = service.add_dimension_node(
                created["snapshot_id"], "temporal",
                {"dimension": "past", "timestamp": datetime.now().isoformat(),
                 "description": "new node"},
            )
            assert result["status"] == "success"
            snap = service.get_snapshot(created["snapshot_id"])
            assert len(snap["temporal_nodes"]) == 1

    def test_add_dimension_node_unknown(self, tmp_path):
        from unittest.mock import patch
        db_path = str(tmp_path / "test_abution.db")
        with patch.object(AbutionGraphService, '_instance', None):
            storage = SQLiteAbutionStorage(db_path=db_path)
            service = AbutionGraphService(storage=storage)
            created = service.create_snapshot(name="test")
            result = service.add_dimension_node(
                created["snapshot_id"], "unknown", {},
            )
            assert result["status"] == "error"

    def test_link_dimensions(self, tmp_path):
        from unittest.mock import patch
        db_path = str(tmp_path / "test_abution.db")
        with patch.object(AbutionGraphService, '_instance', None):
            storage = SQLiteAbutionStorage(db_path=db_path)
            service = AbutionGraphService(storage=storage)
            created = service.create_snapshot(name="test")
            result = service.link_dimensions(
                created["snapshot_id"], "temporal", "tn-1",
                "force", "fn-1", "causal",
            )
            assert result["status"] == "success"
            snap = service.get_snapshot(created["snapshot_id"])
            assert len(snap["cross_dimension_links"]) == 1

    def test_analyze_cross_dimension_patterns(self, tmp_path):
        from unittest.mock import patch
        db_path = str(tmp_path / "test_abution.db")
        with patch.object(AbutionGraphService, '_instance', None):
            storage = SQLiteAbutionStorage(db_path=db_path)
            service = AbutionGraphService(storage=storage)
            created = service.create_snapshot(
                name="test",
                temporal_nodes=[{"dimension": "past", "timestamp": datetime.now().isoformat(),
                                  "description": "t1"}],
                force_nodes=[{"force_type": "driving", "name": "f1", "magnitude": 0.9}],
                action_nodes=[{"dimension": "decide", "name": "a1", "priority": 3}],
            )
            service.link_dimensions(
                created["snapshot_id"], "temporal", "t1", "force", "f1", "causal",
            )
            result = service.analyze_cross_dimension_patterns(created["snapshot_id"])
            assert result["status"] == "success"
            assert result["total_links"] == 1
            assert "temporal_distribution" in result
            assert "dominant_force" in result

    def test_analyze_not_found(self, tmp_path):
        from unittest.mock import patch
        db_path = str(tmp_path / "test_abution.db")
        with patch.object(AbutionGraphService, '_instance', None):
            storage = SQLiteAbutionStorage(db_path=db_path)
            service = AbutionGraphService(storage=storage)
            result = service.analyze_cross_dimension_patterns("nonexistent")
            assert result["status"] == "error"

    def test_create_snapshot_with_all_nodes(self, tmp_path):
        from unittest.mock import patch
        db_path = str(tmp_path / "test_abution.db")
        with patch.object(AbutionGraphService, '_instance', None):
            storage = SQLiteAbutionStorage(db_path=db_path)
            service = AbutionGraphService(storage=storage)
            result = service.create_snapshot(
                name="full",
                temporal_nodes=[{"dimension": "present", "timestamp": datetime.now().isoformat(),
                                  "description": "t1"}],
                pattern_nodes=[{"pattern_type": "structural", "name": "p1",
                                 "description": "desc"}],
                force_nodes=[{"force_type": "driving", "name": "f1"}],
                action_nodes=[{"dimension": "act", "name": "a1"}],
            )
            assert result["status"] == "success"
            assert result["temporal_count"] == 1
            assert result["pattern_count"] == 1
            assert result["force_count"] == 1
            assert result["action_count"] == 1
