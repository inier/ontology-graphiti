"""TDD 集成测试：RetrievalService + ReasoningPersistenceService 端到端。

设计文档：specs/008-semantic-retrieval-bus/design-reasoning-persistence.md §8.3

Sandbox 策略：
  - tmp_path 真实 DB + FakeEngine（返回固定 reasoning dict）
  - 不启动 HTTP 服务器，直接调用 RetrievalService 方法
  - 验证 MCP handler 透传 persist_candidates 的 FR-010 一致性

测试用例：
  T-INT-1: RetrievalService.chain_search(persist_candidates=True) → candidates_meta 存在
  T-INT-2: RetrievalService.chain_search(persist_candidates=False) → 无 candidates_meta（回归）
  T-INT-3: 持久化失败 → 推理结果仍返回 + candidates_meta.error
  T-INT-4: MCP handler 透传 persist_candidates → 结果与 REST 一致（FR-010）
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from odap.biz.core.ontology.mcp.semantic_retrieval_tools import (
    create_ontology_mdl_handler,
    create_ontology_reason_handler,
)
from odap.biz.core.ontology.semantic_retrieval.impl.reasoning_persistence_service import (
    ReasoningPersistenceService,
)
from odap.biz.core.ontology.semantic_retrieval.services.retrieval_service import (
    RetrievalService,
)
from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage


# =====================================================================
# Sandbox Fixtures
# =====================================================================


@pytest.fixture
def sandbox_storage(tmp_path: Path) -> SQLiteCandidateStorage:
    db = tmp_path / "integration_persist.db"
    return SQLiteCandidateStorage(db_path=str(db))


@pytest.fixture
def persistence_service(sandbox_storage: SQLiteCandidateStorage) -> ReasoningPersistenceService:
    return ReasoningPersistenceService(sandbox_storage)


class _FakeChainEngine:
    """Fake chain engine：返回固定 reasoning dict（不依赖 Neo4j/LLM）。"""

    async def reason(
        self, workspace_id: str, *, query: str,
        rules: List[str] = None, max_depth: int = 5,
    ) -> Dict[str, Any]:
        return {
            "mode": "chain",
            "reasoning": {
                "chain_id": "chain-int-test",
                "steps": [
                    {"step_id": "s0", "rule_id": "init", "input": "A", "output": "A", "duration_ms": 0},
                    {"step_id": "s1", "rule_id": "r1", "input": "A", "output": "B", "duration_ms": 50},
                    {"step_id": "s2", "rule_id": "r2", "input": "B", "output": "C", "duration_ms": 50},
                ],
                "status": "ok",
                "confidence": 0.9,
                "cycle_detected": False,
                "conflicts": [],
            },
            "warnings": [],
            "total": 3,
        }


class _FakeMdlEngine:
    """Fake mdl engine。"""

    async def reason(self, workspace_id: str, *, query: str) -> Dict[str, Any]:
        return {
            "mode": "mdl",
            "reasoning": {
                "chain_id": "mdl-int-test",
                "template": "entity_extract_v1",
                "entity": "test",
                "status": "ok",
                "confidence": 0.8,
                "extraction": {
                    "entities": [{"text": "实体X", "type": "对象类型", "aliases": []}],
                    "relations": [],
                },
            },
            "warnings": [],
            "total": 1,
        }


@pytest.fixture
def retrieval_service(persistence_service: ReasoningPersistenceService) -> RetrievalService:
    """装配 RetrievalService：注入 Fake engine + 真实 persistence。"""
    return RetrievalService(
        chain_engine=_FakeChainEngine(),
        mdl_engine=_FakeMdlEngine(),
        persistence=persistence_service,
    )


# =====================================================================
# T-INT-1: persist_candidates=True → candidates_meta 存在
# =====================================================================


@pytest.mark.asyncio
async def test_int_1_chain_persist_returns_candidates_meta(
    retrieval_service: RetrievalService,
):
    """T-INT-1: chain_search(persist_candidates=True) → candidates_meta 含 persisted_count。"""
    result = await retrieval_service.chain_search(
        "ws-int-test", query="A", persist_candidates=True,
    )
    assert "candidates_meta" in result, "persist_candidates=True 时应有 candidates_meta"
    meta = result["candidates_meta"]
    assert meta["persisted_count"] == 2, f"应落盘 2 条（s0 init 跳过），实际 {meta['persisted_count']}"
    assert "run_id" in meta
    assert len(meta["candidate_ids"]) == 2


# =====================================================================
# T-INT-2: persist_candidates=False → 无 candidates_meta（回归）
# =====================================================================


@pytest.mark.asyncio
async def test_int_2_no_persist_no_candidates_meta(
    retrieval_service: RetrievalService,
):
    """T-INT-2: chain_search(persist_candidates=False) → 无 candidates_meta（回归）。"""
    result = await retrieval_service.chain_search(
        "ws-int-test", query="A", persist_candidates=False,
    )
    assert "candidates_meta" not in result, "persist_candidates=False 时不应有 candidates_meta"


# =====================================================================
# T-INT-3: 持久化失败 → 推理结果仍返回 + candidates_meta.error
# =====================================================================


@pytest.mark.asyncio
async def test_int_3_persist_failure_does_not_block_reasoning(
    sandbox_storage: SQLiteCandidateStorage,
):
    """T-INT-3: storage 异常 → 推理结果正常返回 + candidates_meta.error。"""

    class _BoomStorage:
        def create_pipeline_run(self, **kw):
            raise RuntimeError("集成测试模拟 DB 故障")

        def bulk_insert_candidates(self, cands):
            raise RuntimeError("不可达")

    persistence = ReasoningPersistenceService(_BoomStorage())  # type: ignore[arg-type]
    svc = RetrievalService(
        chain_engine=_FakeChainEngine(), persistence=persistence,
    )
    result = await svc.chain_search("ws-test", query="A", persist_candidates=True)

    # 推理结果仍返回
    assert "reasoning" in result
    assert result["mode"] == "chain"
    # candidates_meta 含 error
    assert "candidates_meta" in result
    assert result["candidates_meta"]["persisted_count"] == 0
    assert "error" in result["candidates_meta"]


# =====================================================================
# T-INT-4: MCP handler 透传 persist_candidates → 结果与 REST 一致（FR-010）
# =====================================================================


@pytest.mark.asyncio
async def test_int_4_mcp_handler_persists_consistent_with_rest(
    retrieval_service: RetrievalService,
):
    """T-INT-4: MCP ontology_reason handler 透传 persist_candidates → 与直接调 service 一致。"""
    handler = create_ontology_reason_handler(service=retrieval_service)
    args = {
        "query": "A",
        "rules": [],
        "max_depth": 5,
        "persist_candidates": True,
        "workspace_id": "ws-mcp-test",
    }
    mcp_result = await handler(args)

    # MCP 结果应含 candidates_meta（与 REST 路径一致）
    assert "candidates_meta" in mcp_result, "MCP handler 应透传 persist_candidates"
    assert mcp_result["candidates_meta"]["persisted_count"] == 2

    # 直接调 service 比对
    direct_result = await retrieval_service.chain_search(
        "ws-mcp-test", query="A", persist_candidates=True,
    )
    assert (
        mcp_result["candidates_meta"]["persisted_count"]
        == direct_result["candidates_meta"]["persisted_count"]
    ), "MCP 与 REST 持久化数量应一致（FR-010）"


@pytest.mark.asyncio
async def test_int_4b_mcp_mdl_handler_persists(
    retrieval_service: RetrievalService,
):
    """T-INT-4b: MCP ontology_mdl handler 透传 persist_candidates。"""
    handler = create_ontology_mdl_handler(service=retrieval_service)
    args = {
        "query": "template: test\nentity: X",
        "persist_candidates": True,
        "workspace_id": "ws-mcp-mdl-test",
    }
    mcp_result = await handler(args)
    assert "candidates_meta" in mcp_result
    assert mcp_result["candidates_meta"]["persisted_count"] == 1
