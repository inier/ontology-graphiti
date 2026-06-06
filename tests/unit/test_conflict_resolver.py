"""
ConflictResolver / ConflictService 单元测试 (T319, TDD)

按 AGENTS.md 规则 9 必测，使用 `unittest.mock` 模拟 LLM/服务依赖。
"""
from __future__ import annotations

import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from odap.biz.core.ontology.conflict.impl import ConflictResolverImpl
from odap.biz.core.ontology.conflict.models import (
    ConflictCandidate,
    ConflictRecord,
    ConflictResolution,
    ConflictStatus,
    ConflictType,
)
from odap.biz.core.ontology.conflict.services import ConflictService


def _make_candidate(source_id: str, value, observed_at: datetime, confidence: float = 1.0) -> ConflictCandidate:
    return ConflictCandidate(
        source_id=source_id, value=value, observed_at=observed_at, confidence=confidence
    )


def _make_conflict(candidates) -> ConflictRecord:
    return ConflictRecord(
        id="conf-001",
        entity_id="ent-1",
        entity_type="Customer",
        field_name="email",
        conflict_type=ConflictType.VALUE_MISMATCH,
        candidates=candidates,
    )


class TestConflictResolverStrategies(unittest.TestCase):
    """4 策略实现测试"""

    def setUp(self):
        self.t0 = datetime(2026, 6, 1, 12, 0, 0)
        self.t1 = self.t0 + timedelta(hours=1)
        self.t2 = self.t0 + timedelta(hours=2)
        self.resolver = ConflictResolverImpl()

    # ---------- FIRST_WINS ----------

    def test_first_wins_picks_earliest_observed(self):
        cands = [
            _make_candidate("src1", "alice@x.com", self.t2),
            _make_candidate("src2", "alice@y.com", self.t0),
            _make_candidate("src3", "alice@z.com", self.t1),
        ]
        conflict = _make_conflict(cands)
        result = self.resolver.resolve(conflict, ConflictResolution.FIRST_WINS)
        self.assertEqual(result.status, ConflictStatus.RESOLVED)
        self.assertEqual(result.chosen.source_id, "src2")
        self.assertEqual(result.chosen.value, "alice@y.com")
        self.assertIn("First-wins", result.rationale)

    # ---------- LAST_WINS ----------

    def test_last_wins_picks_latest_observed(self):
        cands = [
            _make_candidate("src1", "alice@x.com", self.t2),
            _make_candidate("src2", "alice@y.com", self.t0),
            _make_candidate("src3", "alice@z.com", self.t1),
        ]
        conflict = _make_conflict(cands)
        result = self.resolver.resolve(conflict, ConflictResolution.LAST_WINS)
        self.assertEqual(result.chosen.source_id, "src1")
        self.assertEqual(result.chosen.value, "alice@x.com")

    # ---------- LLM_JUDGE ----------

    def test_llm_judge_uses_provided_client(self):
        mock_client = MagicMock()
        mock_client.complete.return_value = "src3"
        cands = [
            _make_candidate("src1", "alice@x.com", self.t2),
            _make_candidate("src2", "alice@y.com", self.t0),
            _make_candidate("src3", "alice@z.com", self.t1),
        ]
        conflict = _make_conflict(cands)
        result = self.resolver.resolve(conflict, ConflictResolution.LLM_JUDGE, {"llm_client": mock_client})
        self.assertEqual(result.status, ConflictStatus.RESOLVED)
        self.assertEqual(result.chosen.source_id, "src3")
        mock_client.complete.assert_called_once()

    def test_llm_judge_fallback_when_no_client(self):
        """未提供 llm_client 时降级为 AWAITING_HUMAN"""
        cands = [_make_candidate("src1", "x", self.t0)]
        conflict = _make_conflict(cands)
        result = self.resolver.resolve(conflict, ConflictResolution.LLM_JUDGE, context={})
        self.assertEqual(result.status, ConflictStatus.AWAITING_HUMAN)
        self.assertIsNone(result.chosen)

    def test_llm_judge_fallback_on_exception(self):
        """LLM 异常时降级为 AWAITING_HUMAN"""
        mock_client = MagicMock()
        mock_client.complete.side_effect = RuntimeError("upstream timeout")
        cands = [_make_candidate("src1", "x", self.t0)]
        conflict = _make_conflict(cands)
        result = self.resolver.resolve(conflict, ConflictResolution.LLM_JUDGE, {"llm_client": mock_client})
        self.assertEqual(result.status, ConflictStatus.AWAITING_HUMAN)
        self.assertIn("LLM_JUDGE exception", result.rationale)

    def test_llm_judge_unknown_source_id_falls_back(self):
        """LLM 返回未知 source_id 时降级"""
        mock_client = MagicMock()
        mock_client.complete.return_value = "src-unknown"
        cands = [_make_candidate("src1", "x", self.t0)]
        conflict = _make_conflict(cands)
        result = self.resolver.resolve(conflict, ConflictResolution.LLM_JUDGE, {"llm_client": mock_client})
        self.assertEqual(result.status, ConflictStatus.AWAITING_HUMAN)

    # ---------- MANUAL ----------

    def test_manual_sets_awaiting_human(self):
        cands = [_make_candidate("src1", "x", self.t0)]
        conflict = _make_conflict(cands)
        result = self.resolver.resolve(conflict, ConflictResolution.MANUAL)
        self.assertEqual(result.status, ConflictStatus.AWAITING_HUMAN)
        self.assertIsNone(result.chosen)
        self.assertIn("Manual", result.rationale)

    # ---------- 错误处理 ----------

    def test_unknown_strategy_raises_value_error(self):
        cands = [_make_candidate("src1", "x", self.t0)]
        conflict = _make_conflict(cands)
        with self.assertRaises(ValueError):
            self.resolver.resolve(conflict, "invalid_strategy")  # type: ignore[arg-type]


class TestConflictResolverDetection(unittest.TestCase):
    """detect_conflicts 逻辑测试"""

    def setUp(self):
        self.resolver = ConflictResolverImpl()

    def test_detect_no_sources_returns_empty(self):
        self.assertEqual(self.resolver.detect_conflicts([]), [])

    def test_detect_identical_values_no_conflict(self):
        sources = [
            {"source_id": "src1", "entities": [{"id": "e1", "type": "Cust", "fields": {"email": "a@x.com"}}]},
            {"source_id": "src2", "entities": [{"id": "e1", "type": "Cust", "fields": {"email": "a@x.com"}}]},
        ]
        self.assertEqual(self.resolver.detect_conflicts(sources), [])

    def test_detect_different_values_creates_conflict(self):
        sources = [
            {"source_id": "src1", "entities": [{"id": "e1", "type": "Cust", "fields": {"email": "a@x.com"}}]},
            {"source_id": "src2", "entities": [{"id": "e1", "type": "Cust", "fields": {"email": "a@y.com"}}]},
        ]
        conflicts = self.resolver.detect_conflicts(sources)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].field_name, "email")
        self.assertEqual(len(conflicts[0].candidates), 2)

    def test_detect_multiple_entities(self):
        sources = [
            {
                "source_id": "src1",
                "entities": [
                    {"id": "e1", "type": "Cust", "fields": {"name": "Alice"}},
                    {"id": "e2", "type": "Cust", "fields": {"name": "Bob"}},
                ],
            },
            {
                "source_id": "src2",
                "entities": [
                    {"id": "e1", "type": "Cust", "fields": {"name": "Alice"}},  # same
                    {"id": "e2", "type": "Cust", "fields": {"name": "Bobby"}},  # diff
                ],
            },
        ]
        conflicts = self.resolver.detect_conflicts(sources)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].entity_id, "e2")


class TestConflictServiceContract(unittest.TestCase):
    """服务层契约：返回 Dict、不抛 HTTPException"""

    def setUp(self):
        self.svc = ConflictService()
        self.t0 = datetime(2026, 6, 1, 12, 0, 0)
        self.t1 = self.t0 + timedelta(hours=1)

    def test_detect_conflicts_returns_dict(self):
        sources = [
            {"source_id": "s1", "entities": [{"id": "e1", "type": "Cust", "fields": {"x": 1}}]},
            {"source_id": "s2", "entities": [{"id": "e1", "type": "Cust", "fields": {"x": 2}}]},
        ]
        out = self.svc.detect_conflicts(sources)
        self.assertIsInstance(out, dict)
        self.assertIn("conflicts", out)
        self.assertEqual(out["count"], 1)
        # 类型转换：observed_at 必须为 ISO 字符串
        first = out["conflicts"][0]
        observed_at_str = first["candidates"][0]["observed_at"]
        # 解析回来应为 datetime
        parsed = datetime.fromisoformat(observed_at_str)
        self.assertIsInstance(parsed, datetime)
        # 转换前 < 现 now（实现用 datetime.now()）

    def test_detect_conflicts_invalid_input(self):
        out = self.svc.detect_conflicts("not a list")  # type: ignore[arg-type]
        self.assertEqual(out.get("status"), "error")
        self.assertIn("list", out["message"])

    def test_resolve_conflict_unknown_strategy(self):
        conflict = _make_conflict([_make_candidate("s1", 1, self.t0)])
        out = self.svc.resolve_conflict(conflict, "bogus_strategy")
        self.assertEqual(out.get("status"), "error")

    def test_resolve_conflict_first_wins(self):
        conflict = _make_conflict([
            _make_candidate("s1", "A", self.t1),
            _make_candidate("s2", "B", self.t0),
        ])
        out = self.svc.resolve_conflict(conflict, "first_wins")
        self.assertEqual(out["status"], "resolved")
        self.assertEqual(out["chosen"]["source_id"], "s2")
        self.assertEqual(out["strategy_used"], "first_wins")
        self.assertIn("duration_ms", out)

    def test_list_conflicts_filter_by_status(self):
        conflict_pending = _make_conflict([_make_candidate("s1", "x", self.t0)])
        conflict_resolved = _make_conflict([_make_candidate("s1", "y", self.t1)])
        conflict_resolved.status = ConflictStatus.RESOLVED
        out = self.svc.list_conflicts([conflict_pending, conflict_resolved], status="pending")
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["conflicts"][0]["status"], "pending")

    def test_list_conflicts_invalid_status(self):
        out = self.svc.list_conflicts([], status="bogus")
        self.assertEqual(out.get("status"), "error")


class TestConflictSchemas(unittest.TestCase):
    """Pydantic 模型验证（规则 4、5）"""

    def test_enum_is_str_compatible(self):
        """Enum 必须 (str, Enum) 双继承"""
        self.assertEqual(ConflictResolution.FIRST_WINS.value, "first_wins")
        self.assertEqual(ConflictResolution.FIRST_WINS, "first_wins")  # str 兼容

    def test_default_factory_on_container_fields(self):
        """容器字段必须 Field(default_factory=...)"""
        record = ConflictRecord(entity_id="e1", entity_type="Cust", field_name="x")
        self.assertEqual(record.candidates, [])
        self.assertEqual(record.notes, "")
        self.assertIsInstance(record.detected_at, datetime)

    def test_id_auto_generated(self):
        record = ConflictRecord(entity_id="e1", entity_type="Cust", field_name="x")
        self.assertTrue(len(record.id) > 0)
        # 两次实例的 id 不同
        record2 = ConflictRecord(entity_id="e1", entity_type="Cust", field_name="x")
        self.assertNotEqual(record.id, record2.id)


if __name__ == "__main__":
    unittest.main()
