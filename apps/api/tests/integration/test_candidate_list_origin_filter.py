"""Iter 3 D8 集成测试：候选列表 origin 过滤 + provenance/chain_id 暴露 + latent 500 修复。

验证点：
  T-D8-1: GET /api/semantic-admin/candidates 返回 200（修复 latent 500：definition=None coercion）
  T-D8-2: 响应 items 含 origin + provenance 字段
  T-D8-3: ?origin=llm 仅返回 origin=llm 的候选
  T-D8-4: 推理持久化候选（origin=llm + provenance.source=reasoning）含 chain_id
  T-D8-5: ?keyword= 兼容别名 → canonical 模糊搜索

Sandbox：tmp_path 真实 SQLite，注入独立 CandidateService，不污染生产数据。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from odap.biz.semantic_admin.candidate_store.api import routes as cand_routes
from odap.biz.semantic_admin.candidate_store.services import CandidateService
from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage
from odap.infra.security.jwt_auth import get_current_user


@pytest.fixture
def sandbox_client(tmp_path: Path) -> TestClient:
    """构造 sandbox DB + 注入独立 service 的 TestClient。"""
    db_path = str(tmp_path / "cand_origin_test.db")
    storage = SQLiteCandidateStorage(db_path=db_path)
    cand_routes._candidate_service = CandidateService(storage=storage)

    # 种子：1 条推理持久化候选（llm + reasoning）+ 1 条人工候选 + 1 条 usl 候选
    storage.bulk_insert_candidates([
        {
            "id": "c-reason", "run_id": "r1", "canonical": "推理结论A",
            "semantic_type": "对象类型", "origin": "llm", "status": "DRAFT",
            "confidence": 0.85, "definition": None,
            "provenance": {
                "source": "reasoning", "engine_mode": "chain",
                "chain_id": "chain-xyz-123", "step_index": 2,
            },
        },
        {
            "id": "c-human", "run_id": "r1", "canonical": "人工条目B",
            "semantic_type": "对象类型", "origin": "human", "status": "DRAFT",
            "confidence": 0.5, "definition": "人工录入", "provenance": {},
        },
        {
            "id": "c-usl", "run_id": "r1", "canonical": "USL条目C",
            "semantic_type": "对象类型", "origin": "usl", "status": "DRAFT",
            "confidence": 0.9, "definition": None, "provenance": {},
        },
    ])

    app = FastAPI()
    app.include_router(cand_routes.router)
    app.dependency_overrides[get_current_user] = lambda: {"sub": "u1"}
    return TestClient(app, raise_server_exceptions=False)


def test_d8_1_list_returns_200_not_500(sandbox_client: TestClient):
    """T-D8-1: 列表返回 200（修复 latent 500：definition=None 致 Pydantic 校验失败）。"""
    r = sandbox_client.get("/api/semantic-admin/candidates")
    assert r.status_code == 200, f"期望 200，实际 {r.status_code}: {r.text}"
    j = r.json()
    assert j["total"] == 3, f"应有 3 条，实际 {j['total']}"


def test_d8_2_items_expose_origin_and_provenance(sandbox_client: TestClient):
    """T-D8-2: items 含 origin + provenance 字段（CandidateRow 暴露）。"""
    r = sandbox_client.get("/api/semantic-admin/candidates")
    items = r.json()["items"]
    by_id = {it["id"]: it for it in items}
    c = by_id["c-reason"]
    assert c["origin"] == "llm", f"origin 应为 llm，实际 {c['origin']}"
    assert isinstance(c["provenance"], dict), "provenance 应为 dict"
    assert c["provenance"].get("chain_id") == "chain-xyz-123"


def test_d8_3_origin_filter_llm_only(sandbox_client: TestClient):
    """T-D8-3: ?origin=llm 仅返回 origin=llm 候选（推理持久化条目）。"""
    r = sandbox_client.get("/api/semantic-admin/candidates?origin=llm")
    assert r.status_code == 200
    j = r.json()
    assert j["total"] == 1, f"origin=llm 应仅 1 条，实际 {j['total']}"
    assert j["items"][0]["id"] == "c-reason"
    assert j["items"][0]["origin"] == "llm"


def test_d8_4_reasoning_candidate_has_chain_id(sandbox_client: TestClient):
    """T-D8-4: 推理持久化候选 provenance 含 source=reasoning + chain_id。"""
    r = sandbox_client.get("/api/semantic-admin/candidates?origin=llm")
    c = r.json()["items"][0]
    prov = c["provenance"]
    assert prov.get("source") == "reasoning"
    assert prov.get("engine_mode") == "chain"
    assert "chain_id" in prov and prov["chain_id"]


def test_d8_5_keyword_alias_canonical_search(sandbox_client: TestClient):
    """T-D8-5: ?keyword= 别名触发 canonical 模糊搜索（修复前端 keyword 不生效）。"""
    r = sandbox_client.get("/api/semantic-admin/candidates?keyword=推理")
    assert r.status_code == 200
    j = r.json()
    assert j["total"] == 1, f"keyword=推理 应匹配 1 条，实际 {j['total']}"
    assert j["items"][0]["canonical"] == "推理结论A"


def test_d8_6_origin_filter_human(sandbox_client: TestClient):
    """T-D8-6: ?origin=human 仅返回人工候选。"""
    r = sandbox_client.get("/api/semantic-admin/candidates?origin=human")
    j = r.json()
    assert j["total"] == 1
    assert j["items"][0]["id"] == "c-human"
