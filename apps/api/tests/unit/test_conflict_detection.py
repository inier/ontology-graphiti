"""TDD 单元测试：ADR-078 冲突检测与消解（construction/conflicts）。

覆盖：
  T-CONF-1: 类型冲突检测（同实体多类型）
  T-CONF-2: 属性冲突检测（同属性多取值）
  T-CONF-3: 关系冲突检测（同关系多目标）
  T-CONF-4: 时态冲突检测（多区间）
  T-CONF-5: 无冲突（单源或一致）不产出冲突
  T-CONF-6: SourceTracker 可信度（Wilson 平滑）
  T-CONF-7: SourceTracker 归一化权重
  T-CONF-8: 可信度加权消解
  T-CONF-9: 最近优先消解
  T-CONF-10: 多数投票消解
"""

from __future__ import annotations

import pytest

from odap.biz.core.ontology.construction.conflicts.models import (
    Conflict, ConflictType, ConflictSeverity, ConflictReport,
)
from odap.biz.core.ontology.construction.conflicts.detector import ConflictDetector
from odap.biz.core.ontology.construction.conflicts.source_tracker import (
    SourceTracker, SourceCredibility,
)
from odap.biz.core.ontology.construction.conflicts.resolution import (
    ConfidenceWeightedStrategy, LatestWinsStrategy, MajorityVoteStrategy,
    resolve_conflict,
)


class TestConflictDetector:
    def test_type_conflict(self):
        entities = [
            {"entity_id": "e1", "type": "Unit", "source_id": "s1", "properties": {}},
            {"entity_id": "e1", "type": "Location", "source_id": "s2", "properties": {}},
        ]
        report = ConflictDetector().detect(entities)
        assert report.total == 1
        assert report.conflicts[0].conflict_type == ConflictType.TYPE
        assert report.conflicts[0].severity == ConflictSeverity.ERROR

    def test_property_conflict(self):
        entities = [
            {"entity_id": "e1", "type": "Unit", "source_id": "s1",
             "properties": {"name": "A"}},
            {"entity_id": "e1", "type": "Unit", "source_id": "s2",
             "properties": {"name": "B"}},
        ]
        report = ConflictDetector().detect(entities)
        assert report.total == 1
        assert report.conflicts[0].conflict_type == ConflictType.PROPERTY
        assert report.conflicts[0].attribute == "name"
        assert set(report.conflicts[0].values) == {"A", "B"}

    def test_relation_conflict(self):
        entities = [
            {"entity_id": "e1", "type": "Unit", "source_id": "s1",
             "properties": {}, "relations": [{"name": "part_of", "target": "u1"}]},
            {"entity_id": "e1", "type": "Unit", "source_id": "s2",
             "properties": {}, "relations": [{"name": "part_of", "target": "u2"}]},
        ]
        report = ConflictDetector().detect(entities)
        assert report.total == 1
        assert report.conflicts[0].conflict_type == ConflictType.RELATION

    def test_temporal_conflict(self):
        entities = [
            {"entity_id": "e1", "type": "Unit", "source_id": "s1",
             "properties": {}, "valid_from": "2026-01-01", "valid_to": "2026-12-31"},
            {"entity_id": "e1", "type": "Unit", "source_id": "s2",
             "properties": {}, "valid_from": "2026-06-01", "valid_to": "2026-12-31"},
        ]
        report = ConflictDetector().detect(entities)
        assert report.total == 1
        assert report.conflicts[0].conflict_type == ConflictType.TEMPORAL

    def test_no_conflict_single_source(self):
        entities = [
            {"entity_id": "e1", "type": "Unit", "source_id": "s1",
             "properties": {"name": "A"}},
        ]
        report = ConflictDetector().detect(entities)
        assert report.total == 0

    def test_no_conflict_consistent_multi_source(self):
        entities = [
            {"entity_id": "e1", "type": "Unit", "source_id": "s1",
             "properties": {"name": "A"}},
            {"entity_id": "e1", "type": "Unit", "source_id": "s2",
             "properties": {"name": "A"}},
        ]
        report = ConflictDetector().detect(entities)
        assert report.total == 0


class TestSourceTracker:
    def test_credibility_wilson(self):
        tracker = SourceTracker()
        # 无记录 → 默认 0.5
        assert tracker.credibility("s1") == 0.5
        # 1 次正确 → (1+1)/(1+2) = 0.667
        tracker.record_result("s1", True)
        assert abs(tracker.credibility("s1") - 2/3) < 1e-6
        # 2 次正确 → (2+1)/(2+2) = 0.75
        tracker.record_result("s1", True)
        assert abs(tracker.credibility("s1") - 0.75) < 1e-6

    def test_get_weights_normalized(self):
        tracker = SourceTracker()
        tracker.record_result("s1", True)
        tracker.record_result("s1", True)  # s1 = 0.75
        tracker.record_result("s2", False)  # s2 = (0+1)/(1+2) = 0.333
        weights = tracker.get_weights(["s1", "s2"])
        assert abs(sum(weights.values()) - 1.0) < 1e-6
        assert weights["s1"] > weights["s2"]


class TestResolution:
    def test_confidence_weighted(self):
        tracker = SourceTracker()
        tracker.record_result("s1", True)
        tracker.record_result("s1", True)  # s1 高可信
        tracker.record_result("s2", False)  # s2 低可信

        strategy = ConfidenceWeightedStrategy(tracker=tracker)
        conflict = Conflict(
            conflict_type=ConflictType.PROPERTY,
            entity_id="e1", attribute="name",
            values=["A", "B"], sources=["s1", "s2"],
        )
        result = strategy.resolve(conflict)
        assert result["resolved"] is True
        assert result["winner"] == "A"  # s1 高可信 → 选 A

    def test_latest_wins(self):
        strategy = LatestWinsStrategy()
        conflict = Conflict(
            conflict_type=ConflictType.PROPERTY,
            entity_id="e1", attribute="name",
            values=["old", "new"], sources=["s1", "s2"],
        )
        result = strategy.resolve(conflict)
        assert result["winner"] == "new"

    def test_majority_vote(self):
        strategy = MajorityVoteStrategy()
        conflict = Conflict(
            conflict_type=ConflictType.PROPERTY,
            entity_id="e1", attribute="name",
            values=["A", "A", "B"], sources=["s1", "s2", "s3"],
        )
        result = strategy.resolve(conflict)
        assert result["winner"] == "A"

    def test_resolve_conflict_convenience(self):
        conflict = Conflict(
            conflict_type=ConflictType.PROPERTY,
            entity_id="e1", attribute="name",
            values=["A", "B"], sources=["s1", "s2"],
        )
        result = resolve_conflict(conflict, strategy="majority_vote")
        assert conflict.resolved is True
        assert conflict.resolution == result

    def test_unknown_strategy(self):
        conflict = Conflict(
            conflict_type=ConflictType.PROPERTY,
            entity_id="e1", attribute="name",
            values=["A"], sources=["s1"],
        )
        with pytest.raises(ValueError):
            resolve_conflict(conflict, strategy="nope")
