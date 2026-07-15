"""OntoFlow Goal - 单元测试 (T427)

覆盖：
- Goal / ChangeProposal / ImpactAnalysis 领域模型
- SQLiteGoalStorage 3 表 CRUD + JSON 序列化 (tmp_path 真实 DB)
- GoalRepositoryImpl 域对象 ↔ dict 转换
- RationaleGenerator 多轮追问 + 依赖注入 + 降级
- ImpactAnalyzerImpl 静态 JSON Patch 分析 + 风险映射
- GoalService 业务编排 + 状态机 + 错误处理
- FastAPI 路由 HTTP 状态码 + HTTPException 透传
"""
from __future__ import annotations

import asyncio
import unittest
from datetime import datetime
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.testclient import TestClient

from odap.biz.core.ontology.goal.api.routes import router as goal_router
from odap.biz.core.ontology.goal.api.schemas import (
    CreateGoalRequest,
    ProposeChangeRequest,
    ReviewProposalRequest,
    StatusTransitionRequest,
    UpdateGoalRequest,
)
from odap.biz.core.ontology.goal.impl import (
    GoalRepositoryImpl,
    ImpactAnalyzerImpl,
    MockLLMClient,
    RationaleGenerator,
)
from odap.biz.core.ontology.goal.impl.goal_repository_impl import (
    GoalRepositoryImpl as _RepoImpl,
)
from odap.biz.core.ontology.goal.models import (
    ChangeProposal,
    Goal,
    GoalStatus,
    ImpactAnalysis,
    ImpactCost,
    ProposalStatus,
    RiskLevel,
)
from odap.biz.core.ontology.goal.models.goal import (
    GOAL_STATE_TRANSITIONS,
    is_valid_goal_transition,
)
from odap.biz.core.ontology.goal.services import GoalService
from odap.biz.core.ontology.goal.storage import SQLiteGoalStorage


# ============================================================
# 工厂函数
# ============================================================


def _make_goal(**overrides) -> Goal:
    """构造测试用 Goal"""
    defaults = dict(
        title="Reduce customer churn by 20%",
        description="Lower churn via proactive engagement",
        business_objective=(
            "Reduce quarterly churn rate from 8% to 6% by 2026-Q4"
        ),
        workspace_id="ws-1",
        created_by="alice",
    )
    defaults.update(overrides)
    return Goal(**defaults)


def _make_proposal(**overrides) -> ChangeProposal:
    """构造测试用 ChangeProposal"""
    defaults = dict(
        goal_id="g-1",
        title="Add churn risk property",
        description="Add churn_risk_score property to Customer",
        changes=[
            {
                "op": "add",
                "path": "/object_types/Customer/properties/churn_risk",
                "value": {"type": "number", "min": 0, "max": 1},
            }
        ],
        proposed_by="bob",
        estimated_benefit="Better targeting",
    )
    defaults.update(overrides)
    return ChangeProposal(**defaults)


def _make_impact(**overrides) -> ImpactAnalysis:
    """构造测试用 ImpactAnalysis"""
    defaults = dict(
        proposal_id="p-1",
        affected_object_types=["Customer"],
        affected_action_types=[],
        affected_instances_count=100,
        breaking_changes=[],
        estimated_migration_cost=ImpactCost.LOW,
        risk_level=RiskLevel.LOW,
    )
    defaults.update(overrides)
    return ImpactAnalysis(**defaults)


# ============================================================
# 1. Goal 模型 (15 cases)
# ============================================================


class TestGoalModel(unittest.TestCase):
    """Goal 必填字段、默认值、UUID、Enum 序列化"""

    def test_minimal_construction(self):
        g = _make_goal()
        self.assertEqual(g.title, "Reduce customer churn by 20%")
        self.assertEqual(g.workspace_id, "ws-1")
        self.assertEqual(g.status, GoalStatus.PROPOSED)
        self.assertIsNone(g.rationale)
        self.assertIsNone(g.parent_goal_id)
        self.assertEqual(g.tags, [])
        self.assertEqual(g.metadata, {})

    def test_uuid_auto_unique(self):
        a = _make_goal()
        b = _make_goal()
        self.assertNotEqual(a.id, b.id)
        self.assertEqual(len(a.id), 36)

    def test_timestamps_auto(self):
        g = _make_goal()
        self.assertIsInstance(g.created_at, datetime)
        self.assertIsInstance(g.updated_at, datetime)

    def test_default_factory_container_fields(self):
        """容器字段必须用 default_factory（规则 5）"""
        g1 = _make_goal()
        g1.tags.append("urgent")
        g2 = _make_goal()
        self.assertNotIn("urgent", g2.tags)
        g1.metadata["k"] = "v"
        g2 = _make_goal()
        self.assertNotIn("k", g2.metadata)

    def test_title_empty_raises(self):
        with self.assertRaises(ValueError):
            _make_goal(title="")

    def test_title_whitespace_raises(self):
        with self.assertRaises(ValueError):
            _make_goal(title="   ")

    def test_business_objective_empty_raises(self):
        with self.assertRaises(ValueError):
            _make_goal(business_objective="")

    def test_workspace_empty_raises(self):
        with self.assertRaises(ValueError):
            _make_goal(workspace_id="")

    def test_no_self_parent(self):
        """不能将 parent_goal_id 设为自身 id"""
        g = _make_goal()
        with self.assertRaises(ValueError):
            Goal(
                id=g.id,
                title="x",
                business_objective="x",
                workspace_id="ws-1",
                created_by="a",
                parent_goal_id=g.id,
            )

    def test_parent_goal_id_optional(self):
        g = _make_goal(parent_goal_id="parent-1")
        self.assertEqual(g.parent_goal_id, "parent-1")

    def test_rationale_optional(self):
        g = _make_goal(rationale="some explanation")
        self.assertEqual(g.rationale, "some explanation")

    def test_goal_status_enum_values(self):
        """Enum 必须 (str, Enum) 双继承"""
        for s in [
            "proposed", "approved", "rejected", "in-progress",
            "achieved", "abandoned",
        ]:
            self.assertIn(s, [st.value for st in GoalStatus])
        # 序列化值
        self.assertEqual(GoalStatus.PROPOSED.value, "proposed")
        self.assertEqual(str(GoalStatus.IN_PROGRESS.value), "in-progress")

    def test_goal_status_json_serialization(self):
        """Enum 可直接 JSON 序列化"""
        import json
        g = _make_goal()
        data = json.loads(g.model_dump_json())
        self.assertEqual(data["status"], "proposed")

    def test_metadata_and_tags_round_trip(self):
        g = _make_goal(tags=["a", "b"], metadata={"k": 1})
        s = g.model_dump()
        g2 = Goal(**s)
        self.assertEqual(g2.tags, ["a", "b"])
        self.assertEqual(g2.metadata, {"k": 1})

    def test_state_transitions_defined(self):
        """状态机定义存在并合理"""
        self.assertIn(GoalStatus.PROPOSED, GOAL_STATE_TRANSITIONS)
        self.assertIn(GoalStatus.APPROVED, GOAL_STATE_TRANSITIONS)
        self.assertIn(GoalStatus.IN_PROGRESS, GOAL_STATE_TRANSITIONS)
        # 终态不能转出
        self.assertEqual(GOAL_STATE_TRANSITIONS[GoalStatus.ACHIEVED], [])
        self.assertEqual(GOAL_STATE_TRANSITIONS[GoalStatus.ABANDONED], [])
        self.assertEqual(GOAL_STATE_TRANSITIONS[GoalStatus.REJECTED], [])

    def test_is_valid_goal_transition(self):
        """合法/非法转换校验"""
        self.assertTrue(
            is_valid_goal_transition(GoalStatus.PROPOSED, GoalStatus.APPROVED)
        )
        self.assertTrue(
            is_valid_goal_transition(
                GoalStatus.APPROVED, GoalStatus.IN_PROGRESS
            )
        )
        self.assertTrue(
            is_valid_goal_transition(
                GoalStatus.IN_PROGRESS, GoalStatus.ACHIEVED
            )
        )
        self.assertFalse(
            is_valid_goal_transition(GoalStatus.PROPOSED, GoalStatus.ACHIEVED)
        )
        self.assertFalse(
            is_valid_goal_transition(GoalStatus.REJECTED, GoalStatus.APPROVED)
        )
        # 相同状态视为合法（幂等操作）
        self.assertTrue(
            is_valid_goal_transition(GoalStatus.PROPOSED, GoalStatus.PROPOSED)
        )


# ============================================================
# 2. ChangeProposal 模型 (8 cases)
# ============================================================


class TestChangeProposalModel(unittest.TestCase):
    """ChangeProposal 必填字段、JSON Patch 格式校验"""

    def test_minimal_construction(self):
        p = _make_proposal()
        self.assertEqual(p.title, "Add churn risk property")
        self.assertEqual(p.status, ProposalStatus.DRAFT)
        self.assertEqual(p.proposed_by, "bob")
        self.assertIsNotNone(p.id)
        self.assertIsInstance(p.created_at, datetime)
        self.assertIsNone(p.impact_analysis_id)
        self.assertIsNone(p.reviewed_at)

    def test_proposal_status_enum_values(self):
        for s in [
            "draft", "submitted", "under-review", "approved",
            "rejected", "implemented",
        ]:
            self.assertIn(s, [st.value for st in ProposalStatus])

    def test_changes_default_empty(self):
        p = ChangeProposal(
            goal_id="g", title="t", proposed_by="b"
        )
        self.assertEqual(p.changes, [])

    def test_changes_valid_json_patch(self):
        patch = [
            {"op": "add", "path": "/a", "value": 1},
            {"op": "remove", "path": "/b"},
            {"op": "replace", "path": "/c", "value": "x"},
        ]
        p = _make_proposal(changes=patch)
        self.assertEqual(len(p.changes), 3)

    def test_changes_missing_op_raises(self):
        with self.assertRaises(ValueError):
            _make_proposal(changes=[{"path": "/a", "value": 1}])

    def test_changes_missing_path_raises(self):
        with self.assertRaises(ValueError):
            _make_proposal(changes=[{"op": "add", "value": 1}])

    def test_changes_invalid_op_raises(self):
        with self.assertRaises(ValueError):
            _make_proposal(changes=[{"op": "explode", "path": "/a"}])

    def test_changes_must_be_dict(self):
        with self.assertRaises(ValueError):
            _make_proposal(changes=["not-a-dict"])

    def test_goal_id_required(self):
        with self.assertRaises(ValueError):
            ChangeProposal(goal_id="", title="t", proposed_by="b")

    def test_title_required(self):
        with self.assertRaises(ValueError):
            ChangeProposal(goal_id="g", title="", proposed_by="b")

    def test_proposal_serialization_roundtrip(self):
        p = _make_proposal(
            changes=[{"op": "add", "path": "/x", "value": {"k": 1}}]
        )
        s = p.model_dump()
        p2 = ChangeProposal(**s)
        self.assertEqual(p.changes, p2.changes)


# ============================================================
# 3. ImpactAnalysis 模型 (6 cases)
# ============================================================


class TestImpactAnalysisModel(unittest.TestCase):
    """ImpactAnalysis 必填字段、默认值、Enum"""

    def test_minimal_construction(self):
        i = _make_impact()
        self.assertEqual(i.proposal_id, "p-1")
        self.assertEqual(i.affected_object_types, ["Customer"])
        self.assertEqual(i.affected_instances_count, 100)
        self.assertEqual(i.estimated_migration_cost, ImpactCost.LOW)
        self.assertEqual(i.risk_level, RiskLevel.LOW)
        self.assertIsInstance(i.created_at, datetime)

    def test_impact_cost_enum(self):
        self.assertEqual(ImpactCost.LOW.value, "low")
        self.assertEqual(ImpactCost.MEDIUM.value, "medium")
        self.assertEqual(ImpactCost.HIGH.value, "high")

    def test_risk_level_enum(self):
        self.assertEqual(RiskLevel.LOW.value, "low")
        self.assertEqual(RiskLevel.CRITICAL.value, "critical")

    def test_proposal_id_optional(self):
        """proposal_id 现在是可选的（静态分析时可能未关联）"""
        i = ImpactAnalysis(proposal_id="")
        self.assertEqual(i.proposal_id, "")
        i2 = ImpactAnalysis(proposal_id="p-1")
        self.assertEqual(i2.proposal_id, "p-1")

    def test_default_factory_lists(self):
        i = ImpactAnalysis(proposal_id="p")
        self.assertEqual(i.affected_object_types, [])
        self.assertEqual(i.affected_action_types, [])
        self.assertEqual(i.breaking_changes, [])
        self.assertEqual(i.affected_instances_count, 0)

    def test_serialization_roundtrip(self):
        i = _make_impact(
            breaking_changes=["a", "b"],
            affected_object_types=["X", "Y"],
        )
        s = i.model_dump()
        i2 = ImpactAnalysis(**s)
        self.assertEqual(i.breaking_changes, i2.breaking_changes)
        self.assertEqual(i.affected_object_types, i2.affected_object_types)


# ============================================================
# 4. SQLite 存储层 (20 cases) - 真实 tmp_path DB
# ============================================================


class TestSQLiteGoalStorage(unittest.TestCase):
    """SQLiteGoalStorage 3 表 CRUD + JSON 序列化"""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = f"{self.tmp.name}/test_goal.db"
        self.storage = SQLiteGoalStorage(db_path=self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    # ----- goals -----

    def test_save_and_get_goal(self):
        g = _make_goal()
        self.storage.save_goal(self._goal_to_dict(g))
        row = self.storage.get_goal(g.id)
        self.assertIsNotNone(row)
        self.assertEqual(row["title"], g.title)
        self.assertEqual(row["status"], "proposed")
        self.assertEqual(row["tags"], [])
        self.assertEqual(row["metadata"], {})

    def test_get_goal_not_found(self):
        self.assertIsNone(self.storage.get_goal("nope"))

    def test_goal_tags_metadata_roundtrip(self):
        g = _make_goal(tags=["x", "y"], metadata={"k": "v", "n": 1})
        self.storage.save_goal(self._goal_to_dict(g))
        row = self.storage.get_goal(g.id)
        self.assertEqual(row["tags"], ["x", "y"])
        self.assertEqual(row["metadata"], {"k": "v", "n": 1})

    def test_goal_parent_roundtrip(self):
        g = _make_goal(parent_goal_id="parent-1")
        self.storage.save_goal(self._goal_to_dict(g))
        row = self.storage.get_goal(g.id)
        self.assertEqual(row["parent_goal_id"], "parent-1")

    def test_list_goals_filter_workspace(self):
        for ws in ["ws-1", "ws-2"]:
            self.storage.save_goal(
                self._goal_to_dict(_make_goal(workspace_id=ws))
            )
        data = self.storage.list_goals("ws-1")
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["goals"][0]["workspace_id"], "ws-1")

    def test_list_goals_filter_status(self):
        for _ in range(2):
            self.storage.save_goal(self._goal_to_dict(_make_goal()))
        self.storage.save_goal(
            self._goal_to_dict(_make_goal(status="approved"))
        )
        data = self.storage.list_goals("ws-1", status="approved")
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["goals"][0]["status"], "approved")

    def test_list_goals_pagination(self):
        for i in range(5):
            self.storage.save_goal(self._goal_to_dict(_make_goal()))
        page1 = self.storage.list_goals("ws-1", page=1, page_size=2)
        page2 = self.storage.list_goals("ws-1", page=2, page_size=2)
        self.assertEqual(page1["total"], 5)
        self.assertEqual(len(page1["goals"]), 2)
        self.assertEqual(len(page2["goals"]), 2)
        self.assertEqual(page1["page"], 1)
        self.assertEqual(page2["page"], 2)

    def test_delete_goal(self):
        g = _make_goal()
        self.storage.save_goal(self._goal_to_dict(g))
        self.assertTrue(self.storage.delete_goal(g.id))
        self.assertIsNone(self.storage.get_goal(g.id))

    def test_delete_goal_not_found(self):
        self.assertFalse(self.storage.delete_goal("nope"))

    def test_list_goals_by_parent(self):
        parent = _make_goal()
        self.storage.save_goal(self._goal_to_dict(parent))
        for i in range(3):
            child = _make_goal(parent_goal_id=parent.id, title=f"c{i}")
            self.storage.save_goal(self._goal_to_dict(child))
        rows = self.storage.list_goals_by_parent(parent.id)
        self.assertEqual(len(rows), 3)

    # ----- change_proposals -----

    def test_save_and_get_proposal(self):
        p = _make_proposal()
        self.storage.save_proposal(self._proposal_to_dict(p))
        row = self.storage.get_proposal(p.id)
        self.assertIsNotNone(row)
        self.assertEqual(row["title"], p.title)
        self.assertEqual(len(row["changes"]), 1)
        self.assertEqual(row["changes"][0]["op"], "add")

    def test_get_proposal_not_found(self):
        self.assertIsNone(self.storage.get_proposal("nope"))

    def test_list_proposals_filter_goal(self):
        for gid in ["g-1", "g-2"]:
            self.storage.save_proposal(
                self._proposal_to_dict(_make_proposal(goal_id=gid))
            )
        rows = self.storage.list_proposals(goal_id="g-1")
        self.assertEqual(len(rows), 1)

    def test_list_proposals_filter_status(self):
        self.storage.save_proposal(self._proposal_to_dict(_make_proposal()))
        self.storage.save_proposal(
            self._proposal_to_dict(
                _make_proposal(status=ProposalStatus.APPROVED)
            )
        )
        rows = self.storage.list_proposals(status="approved")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "approved")

    def test_delete_proposals_by_goal(self):
        for _ in range(3):
            self.storage.save_proposal(self._proposal_to_dict(_make_proposal()))
        n = self.storage.delete_proposals_by_goal("g-1")
        self.assertEqual(n, 3)
        self.assertEqual(len(self.storage.list_proposals(goal_id="g-1")), 0)

    # ----- impact_analyses -----

    def test_save_and_get_impact(self):
        i = _make_impact()
        self.storage.save_impact(self._impact_to_dict(i))
        row = self.storage.get_impact(i.id)
        self.assertIsNotNone(row)
        self.assertEqual(row["affected_object_types"], ["Customer"])
        self.assertEqual(row["estimated_migration_cost"], "low")
        self.assertEqual(row["breaking_changes"], [])

    def test_get_impact_not_found(self):
        self.assertIsNone(self.storage.get_impact("nope"))

    def test_get_impact_by_proposal(self):
        i = _make_impact(proposal_id="p-99")
        self.storage.save_impact(self._impact_to_dict(i))
        row = self.storage.get_impact_by_proposal("p-99")
        self.assertIsNotNone(row)
        self.assertEqual(row["proposal_id"], "p-99")

    def test_impact_json_roundtrip(self):
        i = _make_impact(
            breaking_changes=["bc-1", "bc-2"],
            analysis_metadata={"a": [1, 2, 3]},
        )
        self.storage.save_impact(self._impact_to_dict(i))
        row = self.storage.get_impact(i.id)
        self.assertEqual(row["breaking_changes"], ["bc-1", "bc-2"])
        self.assertEqual(row["analysis_metadata"], {"a": [1, 2, 3]})

    def test_delete_impacts_by_proposal(self):
        for i in range(2):
            self.storage.save_impact(self._impact_to_dict(_make_impact()))
        n = self.storage.delete_impacts_by_proposal("p-1")
        self.assertEqual(n, 2)
        self.assertIsNone(self.storage.get_impact_by_proposal("p-1"))

    # ----- 工具 -----

    @staticmethod
    def _goal_to_dict(g: Goal) -> Dict[str, Any]:
        return {
            "id": g.id,
            "title": g.title,
            "description": g.description,
            "business_objective": g.business_objective,
            "rationale": g.rationale,
            "status": g.status.value,
            "parent_goal_id": g.parent_goal_id,
            "workspace_id": g.workspace_id,
            "created_by": g.created_by,
            "created_at": g.created_at.isoformat(),
            "updated_at": g.updated_at.isoformat(),
            "tags": list(g.tags or []),
            "metadata": dict(g.metadata or {}),
        }

    @staticmethod
    def _proposal_to_dict(p: ChangeProposal) -> Dict[str, Any]:
        return {
            "id": p.id,
            "goal_id": p.goal_id,
            "title": p.title,
            "description": p.description,
            "changes": list(p.changes or []),
            "impact_analysis_id": p.impact_analysis_id,
            "estimated_benefit": p.estimated_benefit,
            "estimated_cost": p.estimated_cost,
            "status": p.status.value,
            "proposed_by": p.proposed_by,
            "created_at": p.created_at.isoformat(),
            "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
            "reviewer_notes": p.reviewer_notes,
        }

    @staticmethod
    def _impact_to_dict(i: ImpactAnalysis) -> Dict[str, Any]:
        return {
            "id": i.id,
            "proposal_id": i.proposal_id,
            "affected_object_types": list(i.affected_object_types or []),
            "affected_action_types": list(i.affected_action_types or []),
            "affected_instances_count": int(i.affected_instances_count),
            "breaking_changes": list(i.breaking_changes or []),
            "estimated_migration_cost": i.estimated_migration_cost.value,
            "risk_level": i.risk_level.value,
            "analysis_metadata": dict(i.analysis_metadata or {}),
            "created_at": i.created_at.isoformat(),
        }


# ============================================================
# 5. GoalRepositoryImpl (10 cases)
# ============================================================


class TestGoalRepositoryImpl(unittest.TestCase):
    """GoalRepositoryImpl 域对象 ↔ dict 转换"""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = SQLiteGoalStorage(
            db_path=f"{self.tmp.name}/test_repo.db"
        )
        self.repo = GoalRepositoryImpl(storage=self.storage)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_get_goal(self):
        g = _make_goal()
        self.repo.save_goal(g)
        loaded = self.repo.get_goal(g.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.title, g.title)
        self.assertEqual(loaded.tags, g.tags)
        self.assertEqual(loaded.status, GoalStatus.PROPOSED)

    def test_update_goal_updates_timestamp(self):
        g = _make_goal()
        self.repo.save_goal(g)
        old_updated = g.updated_at
        import time
        time.sleep(0.01)
        g.title = "new title"
        self.repo.save_goal(g)
        loaded = self.repo.get_goal(g.id)
        self.assertEqual(loaded.title, "new title")
        self.assertGreaterEqual(loaded.updated_at, old_updated)

    def test_list_goals(self):
        for _ in range(3):
            self.repo.save_goal(_make_goal())
        data = self.repo.list_goals("ws-1")
        self.assertEqual(data["total"], 3)
        self.assertEqual(len(data["goals"]), 3)

    def test_delete_goal_cascades(self):
        g = _make_goal()
        self.repo.save_goal(g)
        p = _make_proposal(goal_id=g.id)
        self.repo.save_proposal(p)
        self.assertTrue(self.repo.delete_goal(g.id))
        self.assertIsNone(self.repo.get_goal(g.id))
        # 关联 proposal 也被级联删除
        self.assertEqual(
            len(self.repo.list_proposals(goal_id=g.id)), 0
        )

    def test_save_and_get_proposal(self):
        p = _make_proposal()
        self.repo.save_proposal(p)
        loaded = self.repo.get_proposal(p.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.changes, p.changes)
        self.assertEqual(loaded.proposed_by, p.proposed_by)

    def test_save_and_get_impact(self):
        i = _make_impact()
        self.repo.save_impact(i)
        loaded = self.repo.get_impact(i.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.affected_object_types, ["Customer"])
        self.assertEqual(loaded.estimated_migration_cost, ImpactCost.LOW)

    def test_get_goal_lineage(self):
        root = _make_goal(title="root")
        self.repo.save_goal(root)
        child = _make_goal(parent_goal_id=root.id, title="child")
        self.repo.save_goal(child)
        grandchild = _make_goal(parent_goal_id=child.id, title="grand")
        self.repo.save_goal(grandchild)
        proposal = _make_proposal(goal_id=child.id)
        self.repo.save_proposal(proposal)
        lineage = self.repo.get_goal_lineage(child.id)
        self.assertEqual(lineage["goal"].id, child.id)
        self.assertEqual(len(lineage["ancestors"]), 1)
        self.assertEqual(lineage["ancestors"][0].id, root.id)
        self.assertEqual(len(lineage["children"]), 1)
        self.assertEqual(lineage["children"][0].id, grandchild.id)
        self.assertEqual(len(lineage["proposals"]), 1)
        self.assertEqual(lineage["proposals"][0].id, proposal.id)

    def test_get_goal_lineage_missing(self):
        lineage = self.repo.get_goal_lineage("nope")
        self.assertIsNone(lineage["goal"])
        self.assertEqual(lineage["ancestors"], [])
        self.assertEqual(lineage["children"], [])
        self.assertEqual(lineage["proposals"], [])

    def test_lineage_circular_safe(self):
        """循环引用时 ancestor 链路不无限递归"""
        # 手动制造循环：a->b->a
        a = _make_goal()
        b = _make_goal(parent_goal_id=a.id)
        self.repo.save_goal(a)
        self.repo.save_goal(b)
        # 反向修复 a.parent_goal_id = b.id（绕过 model validator 校验）
        # 这里直接走 storage 来模拟
        self.storage.save_goal({
            **a.model_dump(),
            "parent_goal_id": b.id,
        })
        lineage = self.repo.get_goal_lineage(a.id)
        # 不应爆栈
        self.assertIsNotNone(lineage["goal"])

    def test_list_proposals_filter(self):
        for i in range(2):
            self.repo.save_proposal(
                _make_proposal(goal_id=f"g-{i}")
            )
        items = self.repo.list_proposals(goal_id="g-0")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].goal_id, "g-0")


# ============================================================
# 6. RationaleGenerator (10 cases)
# ============================================================


class TestRationaleGenerator(unittest.TestCase):
    """RationaleGenerator: 多轮追问 + 注入 + 降级"""

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_basic_generation(self):
        gen = RationaleGenerator(llm_client=MockLLMClient())
        result = self._run(gen.generate(_make_goal()))
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_multi_round_follow_up(self):
        """多轮追问：初次不满足 → 追问 → 满足"""
        client = MockLLMClient()
        gen = RationaleGenerator(llm_client=client, max_rounds=3, min_length=80)
        goal = _make_goal()
        result = self._run(gen.generate(goal))
        # Mock 初次返回短文本，追问返回长文本 → 至少调用 2 次
        self.assertGreaterEqual(client.call_count, 2)
        self.assertIn("value", result.lower())

    def test_max_rounds_respected(self):
        """最多 max_rounds 次调用"""
        client = MockLLMClient()
        gen = RationaleGenerator(llm_client=client, max_rounds=2)
        self._run(gen.generate(_make_goal()))
        self.assertLessEqual(client.call_count, 2)

    def test_satisfactory_short_circuits(self):
        """初次已满足时不追问"""
        class _SatisfyingClient:
            call_count = 0
            async def chat(self, messages):
                self.call_count += 1
                return (
                    "Comprehensive rationale: the goal improves "
                    "business value by achieving the stated objective. "
                    "Success metric: reduced churn. Stakeholders: PM team. "
                    "Benefit: revenue retention. Risk: scope creep."
                )
        client = _SatisfyingClient()
        gen = RationaleGenerator(llm_client=client, max_rounds=3)
        result = self._run(gen.generate(_make_goal()))
        self.assertEqual(client.call_count, 1)
        self.assertIn("value", result.lower())

    def test_llm_exception_degrades_to_fallback(self):
        """LLM 抛异常时降级到 fallback"""
        client = MockLLMClient(raise_on_call=RuntimeError("LLM down"))
        gen = RationaleGenerator(llm_client=client)
        result = self._run(gen.generate(_make_goal()))
        self.assertIn("fallback", result.lower())

    def test_llm_client_protocol_compliance(self):
        """MockLLMClient 必须实现 LLMClientProtocol"""
        client = MockLLMClient()
        # 运行时检查
        self.assertTrue(hasattr(client, "chat"))
        self.assertTrue(callable(client.chat))

    def test_messages_history_accumulates(self):
        """多轮追问时 messages 累积"""
        client = MockLLMClient()
        gen = RationaleGenerator(llm_client=client, max_rounds=3, min_length=200)
        self._run(gen.generate(_make_goal()))
        # 至少第一次 messages 包含 system+user
        self.assertGreaterEqual(len(client.last_messages), 2)
        self.assertEqual(client.last_messages[0]["role"], "system")

    def test_fallback_contains_goal_title(self):
        """fallback 文本包含 goal 标题"""
        gen = RationaleGenerator(llm_client=MockLLMClient(raise_on_call=Exception()))
        result = self._run(gen.generate(_make_goal()))
        self.assertIn("Reduce customer churn", result)

    def test_missing_element_detection(self):
        """missing_elements 正确识别缺失项"""
        gen = RationaleGenerator()
        # 完全空
        missing = gen._missing_elements("")
        self.assertGreater(len(missing), 0)
        # 完整
        missing2 = gen._missing_elements(
            "metric stakeholder risk benefit value"
        )
        self.assertEqual(missing2, [])

    def test_is_satisfactory(self):
        gen = RationaleGenerator(min_length=10)
        self.assertFalse(gen._is_satisfactory(""))
        self.assertFalse(gen._is_satisfactory("short"))
        self.assertTrue(
            gen._is_satisfactory(
                "A sufficiently long rationale that includes a value "
                "statement for the business."
            )
        )


# ============================================================
# 7. ImpactAnalyzerImpl (10 cases)
# ============================================================


class TestImpactAnalyzerImpl(unittest.TestCase):
    """ImpactAnalyzerImpl 静态 JSON Patch 分析"""

    def test_add_property(self):
        a = ImpactAnalyzerImpl()
        result = a.analyze(
            [
                {
                    "op": "add",
                    "path": "/object_types/Person/properties/age",
                    "value": {"type": "number"},
                }
            ]
        )
        self.assertIn("Person", result.affected_object_types)
        self.assertEqual(result.estimated_migration_cost, ImpactCost.LOW)
        self.assertEqual(result.breaking_changes, [])

    def test_required_change_is_breaking(self):
        a = ImpactAnalyzerImpl()
        result = a.analyze(
            [{"op": "replace", "path": "/object_types/Person/required/0",
              "value": "ssn"}]
        )
        self.assertGreaterEqual(len(result.breaking_changes), 1)
        self.assertEqual(result.estimated_migration_cost, ImpactCost.MEDIUM)

    def test_type_change_is_breaking(self):
        a = ImpactAnalyzerImpl()
        result = a.analyze(
            [{"op": "replace",
              "path": "/object_types/Person/properties/age/type",
              "value": "string"}]
        )
        self.assertGreaterEqual(len(result.breaking_changes), 1)
        self.assertEqual(result.estimated_migration_cost, ImpactCost.MEDIUM)

    def test_remove_object_type_is_breaking(self):
        a = ImpactAnalyzerImpl()
        result = a.analyze(
            [{"op": "remove", "path": "/object_types/LegacyEntity"}]
        )
        self.assertGreaterEqual(len(result.breaking_changes), 1)
        self.assertEqual(result.estimated_migration_cost, ImpactCost.MEDIUM)

    def test_action_type_change(self):
        a = ImpactAnalyzerImpl()
        result = a.analyze(
            [
                {"op": "add", "path": "/action_types/SendEmail",
                 "value": {}},
            ]
        )
        self.assertIn("SendEmail", result.affected_action_types)

    def test_action_type_param_change_breaking(self):
        a = ImpactAnalyzerImpl()
        result = a.analyze(
            [
                {"op": "replace",
                 "path": "/action_types/SendEmail/parameters/recipient",
                 "value": {"type": "string"}},
            ]
        )
        self.assertIn("SendEmail", result.affected_action_types)
        self.assertGreaterEqual(len(result.breaking_changes), 1)

    def test_multiple_patches_accumulate_breaking(self):
        a = ImpactAnalyzerImpl()
        result = a.analyze(
            [
                {"op": "add",
                 "path": "/object_types/Person/properties/age"},
                {"op": "remove",
                 "path": "/object_types/Person/required/0"},
                {"op": "replace",
                 "path": "/object_types/Person/properties/age/type"},
                {"op": "remove", "path": "/action_types/LogAction"},
            ]
        )
        self.assertIn("Person", result.affected_object_types)
        self.assertIn("LogAction", result.affected_action_types)
        self.assertGreaterEqual(len(result.breaking_changes), 3)
        self.assertEqual(result.estimated_migration_cost, ImpactCost.HIGH)
        # 多个 breaking + 多个类型 → CRITICAL
        self.assertEqual(result.risk_level, RiskLevel.CRITICAL)

    def test_migration_cost_thresholds(self):
        a = ImpactAnalyzerImpl()
        # 0 breaking
        r1 = a.analyze([{"op": "add", "path": "/object_types/X/properties/a"}])
        self.assertEqual(r1.estimated_migration_cost, ImpactCost.LOW)
        # 1-2 breaking
        r2 = a.analyze([
            {"op": "replace", "path": "/object_types/X/required/0"},
        ])
        self.assertEqual(r2.estimated_migration_cost, ImpactCost.MEDIUM)
        # 3+ breaking
        r3 = a.analyze([
            {"op": "remove", "path": "/object_types/Y"},
            {"op": "remove", "path": "/object_types/Z"},
            {"op": "replace", "path": "/object_types/X/required/0"},
        ])
        self.assertEqual(r3.estimated_migration_cost, ImpactCost.HIGH)

    def test_risk_level_mapping(self):
        a = ImpactAnalyzerImpl()
        # LOW
        r1 = a.analyze([{"op": "add", "path": "/object_types/X/properties/a"}])
        self.assertEqual(r1.risk_level, RiskLevel.LOW)
        # MEDIUM
        r2 = a.analyze([
            {"op": "replace", "path": "/object_types/X/required/0"},
        ])
        self.assertEqual(r2.risk_level, RiskLevel.MEDIUM)
        # HIGH
        r3 = a.analyze([
            {"op": "remove", "path": "/object_types/X"},
            {"op": "remove", "path": "/object_types/Y"},
            {"op": "remove", "path": "/object_types/Z"},
        ])
        self.assertEqual(r3.risk_level, RiskLevel.HIGH)
        # CRITICAL: high + 多类型
        r4 = a.analyze([
            {"op": "remove", "path": "/object_types/X"},
            {"op": "remove", "path": "/object_types/Y"},
            {"op": "remove", "path": "/action_types/Z"},
        ])
        self.assertEqual(r4.risk_level, RiskLevel.CRITICAL)

    def test_empty_changes(self):
        a = ImpactAnalyzerImpl()
        result = a.analyze([])
        self.assertEqual(result.affected_object_types, [])
        self.assertEqual(result.affected_action_types, [])
        self.assertEqual(result.estimated_migration_cost, ImpactCost.LOW)
        self.assertEqual(result.risk_level, RiskLevel.LOW)

    def test_instance_counter_integration(self):
        a = ImpactAnalyzerImpl(instance_counter=lambda t: 100)
        result = a.analyze([
            {"op": "add", "path": "/object_types/Customer/properties/x"},
        ])
        self.assertEqual(result.affected_instances_count, 100)


# ============================================================
# 8. GoalService (12 cases)
# ============================================================


class TestGoalService(unittest.TestCase):
    """GoalService: CRUD + 状态机 + 编排"""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = SQLiteGoalStorage(
            db_path=f"{self.tmp.name}/test_svc.db"
        )
        self.mock_llm = MockLLMClient()
        self.rationale_gen = RationaleGenerator(llm_client=self.mock_llm)
        self.impact_analyzer = ImpactAnalyzerImpl()
        self.service = GoalService(
            storage=self.storage,
            rationale_generator=self.rationale_gen,
            impact_analyzer=self.impact_analyzer,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    # ----- create_goal -----

    def test_create_goal_with_auto_rationale(self):
        result = self._run(
            self.service.create_goal(
                title="Improve NPS",
                description="",
                business_objective="NPS from 30 to 50",
                workspace_id="ws-1",
                created_by="alice",
            )
        )
        # 成功：result["status"] 是 goal 的状态 "proposed"，不是 "error"
        self.assertNotEqual(result.get("status"), "error")
        self.assertEqual(result["title"], "Improve NPS")
        self.assertEqual(result["status"], "proposed")
        self.assertIsNotNone(result["rationale"])
        self.assertEqual(self.mock_llm.call_count, 1)

    def test_create_goal_without_auto_rationale(self):
        result = self._run(
            self.service.create_goal(
                title="G",
                description="",
                business_objective="O",
                workspace_id="ws-1",
                created_by="a",
                auto_rationale=False,
            )
        )
        self.assertNotEqual(result.get("status"), "error")
        self.assertIsNone(result["rationale"])

    def test_create_goal_missing_title(self):
        result = self._run(
            self.service.create_goal(
                title="",
                description="",
                business_objective="O",
                workspace_id="ws-1",
                created_by="a",
            )
        )
        self.assertEqual(result.get("status"), "error")
        self.assertIn("title", result["message"])

    def test_create_goal_missing_business_objective(self):
        result = self._run(
            self.service.create_goal(
                title="t",
                description="",
                business_objective="",
                workspace_id="ws-1",
                created_by="a",
            )
        )
        self.assertEqual(result.get("status"), "error")
        self.assertIn("business_objective", result["message"])

    def test_create_goal_missing_workspace(self):
        result = self._run(
            self.service.create_goal(
                title="t", description="",
                business_objective="o",
                workspace_id="", created_by="a",
            )
        )
        self.assertEqual(result.get("status"), "error")

    def test_create_goal_with_invalid_parent(self):
        result = self._run(
            self.service.create_goal(
                title="t", description="",
                business_objective="o",
                workspace_id="ws-1",
                created_by="a",
                parent_goal_id="nope",
            )
        )
        self.assertEqual(result.get("status"), "error")

    # ----- get / list / update / delete -----

    def test_get_goal_not_found(self):
        result = self.service.get_goal("nope")
        self.assertEqual(result.get("status"), "error")

    def test_list_goals(self):
        for _ in range(2):
            self._run(
                self.service.create_goal(
                    title="t", description="", business_objective="o",
                    workspace_id="ws-1", created_by="a",
                    auto_rationale=False,
                )
            )
        result = self.service.list_goals("ws-1")
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["count"], 2)

    def test_update_goal(self):
        created = self._run(
            self.service.create_goal(
                title="t", description="", business_objective="o",
                workspace_id="ws-1", created_by="a",
                auto_rationale=False,
            )
        )
        result = self.service.update_goal(
            created["id"], {"title": "new"}
        )
        self.assertEqual(result["title"], "new")

    def test_update_goal_not_found(self):
        result = self.service.update_goal("nope", {"title": "x"})
        self.assertEqual(result.get("status"), "error")

    def test_delete_goal(self):
        created = self._run(
            self.service.create_goal(
                title="t", description="", business_objective="o",
                workspace_id="ws-1", created_by="a",
                auto_rationale=False,
            )
        )
        result = self.service.delete_goal(created["id"])
        self.assertTrue(result["deleted"])
        # 再查 → not found
        self.assertEqual(
            self.service.get_goal(created["id"]).get("status"), "error"
        )

    # ----- 状态机 -----

    def test_state_machine_proposed_to_approved(self):
        created = self._run(
            self.service.create_goal(
                title="t", description="", business_objective="o",
                workspace_id="ws-1", created_by="a",
                auto_rationale=False,
            )
        )
        result = self.service.change_status(
            created["id"], "approved"
        )
        self.assertNotEqual(result.get("status"), "error")
        self.assertEqual(result["status"], "approved")

    def test_state_machine_approved_to_in_progress(self):
        created = self._run(
            self.service.create_goal(
                title="t", description="", business_objective="o",
                workspace_id="ws-1", created_by="a",
                auto_rationale=False,
            )
        )
        self.service.change_status(created["id"], "approved")
        result = self.service.change_status(
            created["id"], "in-progress"
        )
        self.assertEqual(result["status"], "in-progress")

    def test_state_machine_in_progress_to_achieved(self):
        created = self._run(
            self.service.create_goal(
                title="t", description="", business_objective="o",
                workspace_id="ws-1", created_by="a",
                auto_rationale=False,
            )
        )
        self.service.change_status(created["id"], "approved")
        self.service.change_status(created["id"], "in-progress")
        result = self.service.change_status(created["id"], "achieved")
        self.assertEqual(result["status"], "achieved")

    def test_state_machine_invalid_skip(self):
        """proposed → achieved 跳过步骤应返回 error"""
        created = self._run(
            self.service.create_goal(
                title="t", description="", business_objective="o",
                workspace_id="ws-1", created_by="a",
                auto_rationale=False,
            )
        )
        result = self.service.change_status(created["id"], "achieved")
        self.assertEqual(result.get("status"), "error")
        self.assertIn("invalid transition", result["message"])

    def test_state_machine_invalid_status_name(self):
        created = self._run(
            self.service.create_goal(
                title="t", description="", business_objective="o",
                workspace_id="ws-1", created_by="a",
                auto_rationale=False,
            )
        )
        result = self.service.change_status(created["id"], "garbage")
        self.assertEqual(result.get("status"), "error")

    def test_state_machine_goal_not_found(self):
        result = self.service.change_status("nope", "approved")
        self.assertEqual(result.get("status"), "error")

    # ----- propose_change / review -----

    def test_propose_change_triggers_impact(self):
        created = self._run(
            self.service.create_goal(
                title="t", description="", business_objective="o",
                workspace_id="ws-1", created_by="a",
                auto_rationale=False,
            )
        )
        result = self.service.propose_change(
            goal_id=created["id"],
            title="add prop",
            description="",
            changes=[
                {"op": "add", "path": "/object_types/Customer/properties/x"}
            ],
            proposed_by="bob",
        )
        self.assertNotIn("status", result)
        self.assertIn("proposal", result)
        self.assertIn("impact", result)
        self.assertEqual(
            result["proposal"]["impact_analysis_id"],
            result["impact"]["id"],
        )
        self.assertIn(
            "Customer", result["impact"]["affected_object_types"]
        )

    def test_propose_change_goal_not_found(self):
        result = self.service.propose_change(
            goal_id="nope", title="t", description="",
            changes=[], proposed_by="b",
        )
        self.assertEqual(result.get("status"), "error")

    def test_review_proposal_approved(self):
        created = self._run(
            self.service.create_goal(
                title="t", description="", business_objective="o",
                workspace_id="ws-1", created_by="a",
                auto_rationale=False,
            )
        )
        prop = self.service.propose_change(
            goal_id=created["id"],
            title="t", description="",
            changes=[{"op": "add", "path": "/x"}],
            proposed_by="b",
        )
        result = self.service.review_proposal(
            prop["proposal"]["id"], "approve", "looks good"
        )
        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["reviewer_notes"], "looks good")
        self.assertIsNotNone(result["reviewed_at"])

    def test_review_proposal_rejected(self):
        created = self._run(
            self.service.create_goal(
                title="t", description="", business_objective="o",
                workspace_id="ws-1", created_by="a",
                auto_rationale=False,
            )
        )
        prop = self.service.propose_change(
            goal_id=created["id"],
            title="t", description="",
            changes=[{"op": "add", "path": "/x"}],
            proposed_by="b",
        )
        result = self.service.review_proposal(
            prop["proposal"]["id"], "reject", "scope too big"
        )
        self.assertEqual(result["status"], "rejected")

    def test_review_proposal_invalid_decision(self):
        result = self.service.review_proposal("p", "garbage")
        self.assertEqual(result.get("status"), "error")

    def test_review_proposal_not_found(self):
        result = self.service.review_proposal("nope", "approve")
        self.assertEqual(result.get("status"), "error")

    def test_list_proposals(self):
        created = self._run(
            self.service.create_goal(
                title="t", description="", business_objective="o",
                workspace_id="ws-1", created_by="a",
                auto_rationale=False,
            )
        )
        for i in range(2):
            self.service.propose_change(
                goal_id=created["id"], title=f"p{i}", description="",
                changes=[], proposed_by="b",
            )
        result = self.service.list_proposals(goal_id=created["id"])
        self.assertEqual(result["count"], 2)

    # ----- lineage -----

    def test_get_goal_lineage(self):
        root = self._run(
            self.service.create_goal(
                title="root", description="", business_objective="o",
                workspace_id="ws-1", created_by="a",
                auto_rationale=False,
            )
        )
        child = self._run(
            self.service.create_goal(
                title="child", description="", business_objective="o",
                workspace_id="ws-1", created_by="a",
                auto_rationale=False,
                parent_goal_id=root["id"],
            )
        )
        result = self.service.get_goal_lineage(child["id"])
        self.assertNotIn("status", result)
        self.assertEqual(result["goal"]["id"], child["id"])
        self.assertEqual(len(result["ancestors"]), 1)
        self.assertEqual(result["ancestors"][0]["id"], root["id"])

    def test_get_goal_lineage_not_found(self):
        result = self.service.get_goal_lineage("nope")
        self.assertEqual(result.get("status"), "error")


# ============================================================
# 9. FastAPI 路由 (10 cases)
# ============================================================


class TestGoalRoutes(unittest.TestCase):
    """FastAPI 路由 HTTP 状态码 + HTTPException 透传"""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.app = FastAPI()
        self.app.include_router(goal_router)
        from odap.biz.core.ontology.goal.api import routes as routes_mod
        self._svc = routes_mod.goal_service
        # 替换 storage 避免污染默认 DB
        self._svc.storage = SQLiteGoalStorage(
            db_path=f"{self.tmp.name}/test_route.db"
        )
        self._svc.repository = GoalRepositoryImpl(storage=self._svc.storage)
        self._svc.rationale_generator = RationaleGenerator(
            llm_client=MockLLMClient()
        )
        self._svc.impact_analyzer = ImpactAnalyzerImpl()
        self.client = TestClient(self.app)

    def tearDown(self):
        self.tmp.cleanup()

    def _create_goal_body(self, **overrides) -> Dict[str, Any]:
        defaults = dict(
            title="Test Goal",
            description="",
            business_objective="Reduce churn",
            workspace_id="ws-1",
            created_by="alice",
            auto_rationale=False,
        )
        defaults.update(overrides)
        return defaults

    def test_post_create_goal_201(self):
        resp = self.client.post(
            "/api/ontology/goals",
            json=self._create_goal_body(),
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], "Test Goal")
        self.assertEqual(data["status"], "proposed")

    def test_post_create_goal_400_missing_title(self):
        body = self._create_goal_body(title="")
        resp = self.client.post("/api/ontology/goals", json=body)
        self.assertEqual(resp.status_code, 400)

    def test_get_goal_404(self):
        resp = self.client.get("/api/ontology/goals/nope")
        self.assertEqual(resp.status_code, 404)

    def test_get_goal_200(self):
        created = self.client.post(
            "/api/ontology/goals", json=self._create_goal_body()
        ).json()
        resp = self.client.get(f"/api/ontology/goals/{created['id']}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], created["id"])

    def test_get_list_goals(self):
        for _ in range(2):
            self.client.post(
                "/api/ontology/goals", json=self._create_goal_body()
            )
        resp = self.client.get(
            "/api/ontology/goals", params={"workspace_id": "ws-1"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 2)

    def test_get_list_goals_missing_workspace(self):
        resp = self.client.get("/api/ontology/goals")
        self.assertEqual(resp.status_code, 422)  # FastAPI validation

    def test_put_update_goal(self):
        created = self.client.post(
            "/api/ontology/goals", json=self._create_goal_body()
        ).json()
        resp = self.client.put(
            f"/api/ontology/goals/{created['id']}",
            json={"title": "updated"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "updated")

    def test_put_update_goal_404(self):
        resp = self.client.put(
            "/api/ontology/goals/nope", json={"title": "x"}
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_goal(self):
        created = self.client.post(
            "/api/ontology/goals", json=self._create_goal_body()
        ).json()
        resp = self.client.delete(
            f"/api/ontology/goals/{created['id']}"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["deleted"])

    def test_delete_goal_404(self):
        resp = self.client.delete("/api/ontology/goals/nope")
        self.assertEqual(resp.status_code, 404)

    def test_transition_400_invalid(self):
        created = self.client.post(
            "/api/ontology/goals", json=self._create_goal_body()
        ).json()
        resp = self.client.post(
            f"/api/ontology/goals/{created['id']}/transition",
            json={"new_status": "achieved"},  # 跳过 approved/in-progress
        )
        self.assertEqual(resp.status_code, 400)

    def test_transition_200(self):
        created = self.client.post(
            "/api/ontology/goals", json=self._create_goal_body()
        ).json()
        resp = self.client.post(
            f"/api/ontology/goals/{created['id']}/transition",
            json={"new_status": "approved"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "approved")

    def test_transition_404(self):
        resp = self.client.post(
            "/api/ontology/goals/nope/transition",
            json={"new_status": "approved"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_propose_change_201(self):
        created = self.client.post(
            "/api/ontology/goals", json=self._create_goal_body()
        ).json()
        resp = self.client.post(
            f"/api/ontology/goals/{created['id']}/propose-change",
            json={
                "title": "add prop",
                "description": "",
                "changes": [
                    {"op": "add",
                     "path": "/object_types/Customer/properties/x"}
                ],
                "proposed_by": "bob",
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("proposal", data)
        self.assertIn("impact", data)

    def test_propose_change_404(self):
        resp = self.client.post(
            "/api/ontology/goals/nope/propose-change",
            json={
                "title": "t", "description": "",
                "changes": [], "proposed_by": "b",
            },
        )
        self.assertEqual(resp.status_code, 404)

    def test_list_proposals_200(self):
        created = self.client.post(
            "/api/ontology/goals", json=self._create_goal_body()
        ).json()
        # 创建一个 proposal
        self.client.post(
            f"/api/ontology/goals/{created['id']}/propose-change",
            json={
                "title": "t", "description": "",
                "changes": [], "proposed_by": "b",
            },
        )
        resp = self.client.get(
            f"/api/ontology/goals/{created['id']}/proposals"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

    def test_review_proposal_200(self):
        created = self.client.post(
            "/api/ontology/goals", json=self._create_goal_body()
        ).json()
        prop = self.client.post(
            f"/api/ontology/goals/{created['id']}/propose-change",
            json={
                "title": "t", "description": "",
                "changes": [], "proposed_by": "b",
            },
        ).json()
        resp = self.client.post(
            f"/api/ontology/goals/proposals/{prop['proposal']['id']}/review",
            json={"decision": "approve", "reviewer_notes": "ok"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "approved")

    def test_review_proposal_404(self):
        resp = self.client.post(
            "/api/ontology/goals/proposals/nope/review",
            json={"decision": "approve"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_lineage_200(self):
        root = self.client.post(
            "/api/ontology/goals", json=self._create_goal_body()
        ).json()
        resp = self.client.get(
            f"/api/ontology/goals/{root['id']}/lineage"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("goal", data)
        self.assertIn("ancestors", data)
        self.assertIn("children", data)
        self.assertIn("proposals", data)

    def test_lineage_404(self):
        resp = self.client.get("/api/ontology/goals/nope/lineage")
        self.assertEqual(resp.status_code, 404)

    def test_route_exception_passthrough(self):
        """即使 service 抛异常，HTTPException 应被透传"""
        from fastapi import HTTPException
        from odap.biz.core.ontology.goal.api import routes as routes_mod

        original = routes_mod.goal_service.get_goal

        def _raise_http(goal_id):
            raise HTTPException(status_code=418, detail="teapot")

        routes_mod.goal_service.get_goal = _raise_http
        try:
            resp = self.client.get("/api/ontology/goals/whatever")
            # 透传 → 418 而不是 500
            self.assertEqual(resp.status_code, 418)
        finally:
            routes_mod.goal_service.get_goal = original


if __name__ == "__main__":
    unittest.main()
