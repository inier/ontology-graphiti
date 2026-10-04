"""ADR-085 S4a-3 / F7-c：execute_l6 持久化 L6 公理到 sa_derived_axiom（停止丢弃）。

背景（F7-c）：execute_l6 原先只把公理**计数**写进 run stats（l6_axiom_total /
l6_axioms_by_type），公理本身被丢弃——形状生成的天然喂料被浪费。整改：L6 推导后
把公理整体持久化到 sa_derived_axiom（按 pipeline_run_id 归属，重跑幂等替换）。

规则 9：candidate/usl/shacl 三库均用真实 tmp_path SQLite，禁 MagicMock。
规则 14.6：持久化逻辑（execute_l6 → replace_axioms_for_run）走**真实函数体**；
  _FakeDeriver 仅控制 derive() 的**输出数据**（derive 真值另有 l6_axiom_deriver 单测），
  不替换被测的持久化代码。TestRealDeriverWiring 另走真实 AxiomDeriver 验证接线。
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage
from odap.biz.semantic_admin.ol_pipeline.services import PipelineService
from odap.biz.semantic_admin.shacl_store.storage import SQLiteShaclStorage
from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage


class _FakeDeriver:
    """返回固定公理集，控制持久化输入（不触碰被测的持久化逻辑）。"""

    def __init__(self, axioms):
        self._axioms = axioms
        self.calls = 0

    def derive(self, **_kwargs):
        self.calls += 1
        cnt = Counter(a["axiom_type"] for a in self._axioms)
        return {
            "axioms": list(self._axioms),
            "total": len(self._axioms),
            "counts_by_type": dict(cnt),
        }


_AXIOMS = [
    {
        "axiom_type": "sub_class_of",
        "subject": "库存周转率",
        "object": "指标",
        "confidence": 0.9,
        "source": "hierarchy_direct",
        "proof": {"direct_edge": True},
    },
    {
        "axiom_type": "disjoint_classes",
        "subject": "指标",
        "object": "维度",
        "confidence": 0.7,
        "source": "sibling_disjoint",
        "proof": {},
    },
    {
        "axiom_type": "object_property_cardinality",
        "subject": "持有",
        "object": "",
        "min_card": 1,
        "max_card": 3,
        "confidence": 0.65,
        "source": "frequency_based_cardinality",
        "proof": {"sample_size": 2},
    },
]


@pytest.fixture
def stores(tmp_path: Path):
    cand = SQLiteCandidateStorage(db_path=str(tmp_path / "c.db"))
    usl = SQLiteUslStorage(db_path=str(tmp_path / "u.db"))
    shacl = SQLiteShaclStorage(db_path=str(tmp_path / "s.db"))
    return cand, usl, shacl


def _make_svc(stores, deriver):
    cand, usl, shacl = stores
    return PipelineService(
        candidate_storage=cand,
        usl_storage=usl,
        shacl_storage=shacl,
        l6_axiom_deriver=deriver,
    )


class TestL6AxiomPersistence:
    def test_execute_l6_persists_all_axioms(self, stores):
        _cand, _usl, shacl = stores
        svc = _make_svc(stores, _FakeDeriver(_AXIOMS))
        run = svc.create_run(
            workspace_id="ws-fin", ontology_id="ont-1", source_type="nl"
        )
        rid = run["id"]

        res = svc.execute_l6(run_id=rid)

        assert res["status"] == "ok"
        assert res["total"] == 3
        rows, total = shacl.list_axioms(pipeline_run_id=rid)
        assert total == 3
        assert {r["axiom_type"] for r in rows} == {
            "sub_class_of",
            "disjoint_classes",
            "object_property_cardinality",
        }

    def test_axioms_tagged_with_run_and_workspace(self, stores):
        _cand, _usl, shacl = stores
        svc = _make_svc(stores, _FakeDeriver(_AXIOMS))
        rid = svc.create_run(workspace_id="ws-fin", source_type="nl")["id"]

        svc.execute_l6(run_id=rid)

        rows, _ = shacl.list_axioms(pipeline_run_id=rid)
        assert all(r["pipeline_run_id"] == rid for r in rows)
        # workspace_id 取自 run 记录（domain_id 不猜测：一个 run 跨多领域，规则 14.4）
        assert all(r["workspace_id"] == "ws-fin" for r in rows)

    def test_cardinality_min_max_persisted(self, stores):
        _cand, _usl, shacl = stores
        svc = _make_svc(stores, _FakeDeriver(_AXIOMS))
        rid = svc.create_run(workspace_id="ws-fin", source_type="nl")["id"]

        svc.execute_l6(run_id=rid)

        rows, _ = shacl.list_axioms(
            pipeline_run_id=rid, axiom_type="object_property_cardinality"
        )
        assert rows[0]["min_card"] == 1
        assert rows[0]["max_card"] == 3

    def test_proof_json_persisted(self, stores):
        _cand, _usl, shacl = stores
        svc = _make_svc(stores, _FakeDeriver(_AXIOMS))
        rid = svc.create_run(workspace_id="ws-fin", source_type="nl")["id"]

        svc.execute_l6(run_id=rid)

        rows, _ = shacl.list_axioms(pipeline_run_id=rid, axiom_type="sub_class_of")
        assert rows[0]["proof"] == {"direct_edge": True}

    def test_rerun_l6_replaces_not_appends(self, stores):
        _cand, _usl, shacl = stores
        svc = _make_svc(stores, _FakeDeriver(_AXIOMS))
        rid = svc.create_run(workspace_id="ws-fin", source_type="nl")["id"]

        svc.execute_l6(run_id=rid)
        svc.execute_l6(run_id=rid)  # 重跑

        _, total = shacl.list_axioms(pipeline_run_id=rid)
        assert total == 3  # 幂等替换，未翻倍成 6

    def test_counts_still_in_stats_patch(self, stores):
        # 持久化公理的同时，原有计数 stats_patch 行为不变（向后兼容）
        svc = _make_svc(stores, _FakeDeriver(_AXIOMS))
        rid = svc.create_run(workspace_id="ws-fin", source_type="nl")["id"]

        res = svc.execute_l6(run_id=rid)

        assert res["stats_patch"]["l6_axiom_total"] == 3
        assert res["stats_patch"]["l6_axioms_by_type"]["sub_class_of"] == 1


class TestRealDeriverWiring:
    def test_real_axiom_deriver_persists_consistently(self, stores):
        # 真实 AxiomDeriver（非 fake）：空 run 推导出 0 公理，持久化数与推导数一致，
        # 证明「真实 derive → 真实持久化」接线通畅（内容保证见 TestL6AxiomPersistence）。
        from odap.biz.semantic_admin.ol_pipeline.impl.l6_axiom_deriver import (
            AxiomDeriver,
        )

        _cand, _usl, shacl = stores
        svc = _make_svc(stores, AxiomDeriver())
        rid = svc.create_run(workspace_id="ws-real", source_type="nl")["id"]

        res = svc.execute_l6(run_id=rid)

        rows, total = shacl.list_axioms(pipeline_run_id=rid)
        assert res["status"] == "ok"
        assert total == res["total"] == len(res["axioms"]) == len(rows)
