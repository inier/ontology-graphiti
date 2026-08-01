"""TDD 单元测试：ReasoningPersistenceService（推理结论 → USL Candidate 持久化）。

设计文档：specs/008-semantic-retrieval-bus/design-reasoning-persistence.md

Sandbox 策略（遵循 test_semantic_admin_candidate_store.py 约定）：
  - SQLite 用 tmp_path 真实 DB，严禁 MagicMock 模拟存储层
  - 每个测试用例用独立临时 DB，互不污染
  - 8 个测试用例覆盖映射规则、容错、边界、链路追溯、审计无明文

测试用例：
  T-PERS-1: chain 推理 → 关键节点过滤（s0/s2 跳过，s1/s3/s4 落盘）
  T-PERS-2: mdl 推理 → extraction.entities 各落 1 条
  T-PERS-3: status=degraded → 跳过持久化，返回 skipped_reason
  T-PERS-4: 未知 mode → 跳过，返回 skipped_reason
  T-PERS-5: steps 全被过滤（仅 init）→ 跳过，返回 skipped_reason
  T-PERS-6: bulk_insert 异常 → 不抛出，返回 error
  T-PERS-7: parent_candidates_json 链路正确（#2.parent 指向 #1.id）
  T-PERS-8: provenance_json 含 chain_id/step_index/engine_mode/cycle_aborted
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from odap.biz.core.ontology.semantic_retrieval.impl.reasoning_persistence_service import (
    ReasoningPersistenceService,
)
from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage


# =====================================================================
# Sandbox Fixtures
# =====================================================================


@pytest.fixture
def sandbox_storage(tmp_path: Path) -> SQLiteCandidateStorage:
    """Sandbox：独立临时 DB，测试间互不污染。"""
    db = tmp_path / "reasoning_persist_test.db"
    return SQLiteCandidateStorage(db_path=str(db))


@pytest.fixture
def persistence_service(sandbox_storage: SQLiteCandidateStorage) -> ReasoningPersistenceService:
    return ReasoningPersistenceService(sandbox_storage)


@pytest.fixture
def sample_chain_reasoning() -> Dict[str, Any]:
    """5 步推理（含 init + 1 个 input==output 占位 + 3 个关键节点）。"""
    return {
        "mode": "chain",
        "reasoning": {
            "chain_id": "chain-test123",
            "steps": [
                {"step_id": "s0", "rule_id": "init", "input": "A", "output": "A", "duration_ms": 0},
                {"step_id": "s1", "rule_id": "r1", "input": "A", "output": "B", "duration_ms": 50},
                {"step_id": "s2", "rule_id": "r2", "input": "B", "output": "B", "duration_ms": 50},
                {"step_id": "s3", "rule_id": "r3", "input": "B", "output": "C", "duration_ms": 50},
                {"step_id": "s4", "rule_id": "r4", "input": "C", "output": "D", "duration_ms": 50},
            ],
            "status": "ok",
            "confidence": 0.85,
            "cycle_detected": False,
            "conflicts": [],
        },
        "warnings": [],
        "total": 5,
    }


@pytest.fixture
def sample_mdl_reasoning() -> Dict[str, Any]:
    """MDL 推理：2 个抽取实体。"""
    return {
        "mode": "mdl",
        "reasoning": {
            "chain_id": "mdl-test456",
            "template": "entity_extract_v1",
            "entity": "测试实体",
            "status": "ok",
            "confidence": 0.75,
            "extraction": {
                "entities": [
                    {"text": "公司A", "type": "对象类型", "aliases": ["A公司"]},
                    {"text": "产品B", "type": "对象类型", "aliases": []},
                ],
                "relations": [],
            },
        },
        "warnings": [],
        "total": 1,
    }


# =====================================================================
# T-PERS-1: chain 推理 → 关键节点过滤
# =====================================================================


def test_pers_1_chain_filters_init_and_noop_steps(
    persistence_service: ReasoningPersistenceService,
    sample_chain_reasoning: Dict[str, Any],
):
    """T-PERS-1: s0(init) 和 s2(input==output) 跳过；s1/s3/s4 落盘 3 条。"""
    result = persistence_service.persist(sample_chain_reasoning, "ws-test")

    assert result["persisted_count"] == 3, f"应落盘 3 条，实际 {result['persisted_count']}"
    assert "run_id" in result
    assert len(result["candidate_ids"]) == 3

    # 验证 canonical 分别是 B/C/D（过滤掉 A/A 和 B/B）
    storage = persistence_service._storage
    for cid in result["candidate_ids"]:
        cand = storage.get_candidate(cid)
        assert cand is not None
        assert cand["canonical"] in ("B", "C", "D"), f"canonical={cand['canonical']} 不在预期内"
        assert cand["canonical"] != "A", "init 步骤的 A 不应落盘"


# =====================================================================
# T-PERS-2: mdl 推理 → extraction.entities 各落 1 条
# =====================================================================


def test_pers_2_mdl_persists_each_entity(
    persistence_service: ReasoningPersistenceService,
    sample_mdl_reasoning: Dict[str, Any],
):
    """T-PERS-2: 2 个实体 → 2 条 candidate。"""
    result = persistence_service.persist(sample_mdl_reasoning, "ws-test")

    assert result["persisted_count"] == 2
    assert len(result["candidate_ids"]) == 2

    storage = persistence_service._storage
    canonicals = []
    for cid in result["candidate_ids"]:
        cand = storage.get_candidate(cid)
        assert cand is not None
        canonicals.append(cand["canonical"])
    assert set(canonicals) == {"公司A", "产品B"}


# =====================================================================
# T-PERS-3: status=degraded → 跳过持久化
# =====================================================================


def test_pers_3_degraded_status_skips_persist(
    persistence_service: ReasoningPersistenceService,
    sample_chain_reasoning: Dict[str, Any],
):
    """T-PERS-3: reasoning.status=degraded → 不写库，返回 skipped_reason。"""
    sample_chain_reasoning["reasoning"]["status"] = "degraded"
    result = persistence_service.persist(sample_chain_reasoning, "ws-test")

    assert result["persisted_count"] == 0
    assert "skipped_reason" in result
    assert "degraded" in result["skipped_reason"]


# =====================================================================
# T-PERS-4: 未知 mode → 跳过
# =====================================================================


def test_pers_4_unknown_mode_skips(
    persistence_service: ReasoningPersistenceService,
    sample_chain_reasoning: Dict[str, Any],
):
    """T-PERS-4: mode 不是 chain/mdl → 跳过。"""
    sample_chain_reasoning["mode"] = "unknown"
    result = persistence_service.persist(sample_chain_reasoning, "ws-test")

    assert result["persisted_count"] == 0
    assert "skipped_reason" in result


# =====================================================================
# T-PERS-5: steps 全被过滤（仅 init）→ 跳过
# =====================================================================


def test_pers_5_all_steps_filtered_skips(
    persistence_service: ReasoningPersistenceService,
    sample_chain_reasoning: Dict[str, Any],
):
    """T-PERS-5: 仅 1 个 init 步骤 → 过滤后 0 条 → 跳过。"""
    sample_chain_reasoning["reasoning"]["steps"] = [
        {"step_id": "s0", "rule_id": "init", "input": "A", "output": "A", "duration_ms": 0},
    ]
    result = persistence_service.persist(sample_chain_reasoning, "ws-test")

    assert result["persisted_count"] == 0
    assert "skipped_reason" in result


# =====================================================================
# T-PERS-6: bulk_insert 异常 → 不抛出，返回 error
# =====================================================================


def test_pers_6_storage_exception_does_not_raise(
    sandbox_storage: SQLiteCandidateStorage,
    sample_chain_reasoning: Dict[str, Any],
):
    """T-PERS-6: 模拟 storage 异常 → persist 不抛出，返回 error 字段。"""

    class _BoomStorage:
        def create_pipeline_run(self, **kw):
            raise RuntimeError("DB 磁盘满模拟")

        def bulk_insert_candidates(self, cands):
            raise RuntimeError("不可达")

    svc = ReasoningPersistenceService(_BoomStorage())  # type: ignore[arg-type]
    result = svc.persist(sample_chain_reasoning, "ws-test")

    assert result["persisted_count"] == 0
    assert "error" in result
    assert "磁盘满" in result["error"]


# =====================================================================
# T-PERS-7: parent_candidates_json 链路正确
# =====================================================================


def test_pers_7_parent_chain_linkage(
    persistence_service: ReasoningPersistenceService,
    sample_chain_reasoning: Dict[str, Any],
):
    """T-PERS-7: #1.parent=[] ; #2.parent=[#1.id] ; #3.parent=[#2.id]。"""
    result = persistence_service.persist(sample_chain_reasoning, "ws-test")
    cand_ids = result["candidate_ids"]
    assert len(cand_ids) == 3

    storage = persistence_service._storage
    c1 = storage.get_candidate(cand_ids[0])
    c2 = storage.get_candidate(cand_ids[1])
    c3 = storage.get_candidate(cand_ids[2])

    # 第 1 条 parent 为空
    assert c1["parent_candidates"] == [], "第 1 条 parent 应为空"
    # 第 2 条 parent 指向第 1 条
    assert c2["parent_candidates"] == [cand_ids[0]], "第 2 条 parent 应指向 #1"
    # 第 3 条 parent 指向第 2 条
    assert c3["parent_candidates"] == [cand_ids[1]], "第 3 条 parent 应指向 #2"


# =====================================================================
# T-PERS-8: provenance_json 含 chain_id/step_index/engine_mode/cycle_aborted
# =====================================================================


def test_pers_8_provenance_fields(
    persistence_service: ReasoningPersistenceService,
    sample_chain_reasoning: Dict[str, Any],
):
    """T-PERS-8: provenance 含 source/engine_mode/chain_id/step_index/rule_id/cycle_aborted。"""
    result = persistence_service.persist(sample_chain_reasoning, "ws-test")
    storage = persistence_service._storage
    cand = storage.get_candidate(result["candidate_ids"][0])

    prov = cand["provenance"]
    assert prov["source"] == "reasoning"
    assert prov["engine_mode"] == "chain"
    assert prov["chain_id"] == "chain-test123"
    assert "step_index" in prov
    assert "rule_id" in prov
    assert prov["cycle_aborted"] is False


def test_pers_8b_mdl_provenance_fields(
    persistence_service: ReasoningPersistenceService,
    sample_mdl_reasoning: Dict[str, Any],
):
    """T-PERS-8b: mdl provenance 含 source/engine_mode/chain_id/template/entity_index。"""
    result = persistence_service.persist(sample_mdl_reasoning, "ws-test")
    storage = persistence_service._storage
    cand = storage.get_candidate(result["candidate_ids"][0])

    prov = cand["provenance"]
    assert prov["source"] == "reasoning"
    assert prov["engine_mode"] == "mdl"
    assert prov["chain_id"] == "mdl-test456"
    assert prov["template"] == "entity_extract_v1"
    assert "entity_index" in prov


# =====================================================================
# 附加验证：origin=llm, status=DRAFT, 审计无明文
# =====================================================================


def test_pers_9_origin_and_status_defaults(
    persistence_service: ReasoningPersistenceService,
    sample_chain_reasoning: Dict[str, Any],
):
    """附加：所有 candidate origin=llm, status=new(legacy for DRAFT)。"""
    result = persistence_service.persist(sample_chain_reasoning, "ws-test")
    storage = persistence_service._storage
    for cid in result["candidate_ids"]:
        cand = storage.get_candidate(cid)
        assert cand["origin"] == "llm"
        # _deserialize_candidate_row 将 DRAFT 映射为 legacy "new"
        assert cand["status"] in ("new", "DRAFT")


def test_pers_10_audit_no_plaintext(
    persistence_service: ReasoningPersistenceService,
    sample_chain_reasoning: Dict[str, Any],
):
    """附加：audit_logs 表不含 canonical/step.output 明文。"""
    persistence_service.persist(sample_chain_reasoning, "ws-test")

    import sqlite3
    conn = sqlite3.connect(persistence_service._storage.db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM audit_logs").fetchall()
        for row in rows:
            payload = row["payload"] or "{}"
            # payload 中不应包含推理结论明文（B/C/D）
            assert "canonical" not in payload, "审计 payload 不应含 canonical 字段"
            assert '"B"' not in payload, "审计 payload 不应含推理结论明文 B"
            assert '"C"' not in payload, "审计 payload 不应含推理结论明文 C"
            assert '"D"' not in payload, "审计 payload 不应含推理结论明文 D"
    finally:
        conn.close()
