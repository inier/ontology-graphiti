"""TDD：ontology_semantics MCP 工具（子项目 C E-1~E-4, E-10）。

三层映射（content/schema/tool）+ cost 对账 + 失败降级（不 raise）。
注入 fake USL / retrieval 服务，验证 handler 组装逻辑。
"""
from __future__ import annotations

import asyncio

import pytest

from odap.biz.core.ontology.mcp.semantics_tools import (
    create_ontology_semantics_handler,
)


class _FakeUsl:
    def __init__(self, items=None, boom=False):
        self._items = items or []
        self._boom = boom
        self.calls = []

    def list_terms(self, domain_id=None, semantic_type=None,
                   synonym_keyword=None, page=1, page_size=100):
        self.calls.append(synonym_keyword)
        if self._boom:
            raise RuntimeError("usl down")
        return {"items": self._items, "total": len(self._items),
                "page": 1, "page_size": page_size}


class _FakeRetrieval:
    def __init__(self, rows=None, boom=False):
        self._rows = rows if rows is not None else []
        self._boom = boom
        self.calls = []

    async def search(self, workspace_id, request):
        self.calls.append(request.query)
        if self._boom:
            raise RuntimeError("graph down")
        return {"query": request.query, "mode": "graph",
                "total": len(self._rows), "rows": self._rows}


def _run(coro):
    return asyncio.run(coro)


_USL_TERM = {
    "id": "t1", "domain_id": "sanguo", "canonical": "人物",
    "semantic_type": "对象类型",
    "synonyms": ["历史人物"], "near_synonyms": ["名将"], "aliases": ["人"],
}


def test_content_layer_returns_canonical_and_synonyms():
    usl = _FakeUsl(items=[_USL_TERM])
    h = create_ontology_semantics_handler(usl_service=usl, retrieval_service=_FakeRetrieval())
    out = _run(h({"expression": "司马懿", "domain_id": "sanguo", "kinds": ["content"]}))
    assert out["content"]["canonical"] == "人物"
    assert out["content"]["synonyms"] == ["历史人物"]
    assert out["content"]["near_synonyms"] == ["名将"]
    assert out["content"]["semantic_type"] == "对象类型"
    assert "schema" not in out          # kinds 只含 content
    assert out["cost"]["round_trips"] >= 1


def test_content_layer_no_match_returns_none_canonical_without_error():
    usl = _FakeUsl(items=[])
    h = create_ontology_semantics_handler(usl_service=usl, retrieval_service=_FakeRetrieval())
    out = _run(h({"expression": "不存在词", "kinds": ["content"]}))
    assert out["content"]["canonical"] is None
    assert out["cost"].get("error") is None or "content" not in (out["cost"].get("error") or "")


def test_schema_layer_returns_object_type_fields():
    rows = [{"object_type": "Person", "properties": ["age", "name"],
             "relation_types": ["knows"]}]
    h = create_ontology_semantics_handler(usl_service=_FakeUsl(), retrieval_service=_FakeRetrieval(rows=rows))
    out = _run(h({"expression": "Person", "domain_id": "d1", "kinds": ["schema"]}))
    assert out["schema"]["object_type"] == "Person"
    assert out["schema"]["properties"] == ["age", "name"]
    assert out["schema"]["relation_types"] == ["knows"]
    assert "content" not in out


def test_all_three_layers_default():
    h = create_ontology_semantics_handler(
        usl_service=_FakeUsl(items=[_USL_TERM]),
        retrieval_service=_FakeRetrieval(rows=[{"object_type": "Person"}]))
    out = _run(h({"expression": "司马懿", "domain_id": "sanguo"}))
    assert set(out.keys()) >= {"content", "schema", "tool", "cost"}
    assert out["tool"]["engines"]


def test_retrieval_failure_degrades_with_cost_error_no_raise():
    h = create_ontology_semantics_handler(
        usl_service=_FakeUsl(), retrieval_service=_FakeRetrieval(boom=True))
    out = _run(h({"expression": "x", "kinds": ["content", "schema"]}))
    assert out["cost"]["error"]                       # 显式记录失败
    assert out["schema"] == {} or out["schema"].get("object_type") is None
    assert "content" in out                           # content 仍可用（USL 正常）


def test_usl_failure_degrades_with_cost_error_no_raise():
    h = create_ontology_semantics_handler(
        usl_service=_FakeUsl(boom=True), retrieval_service=_FakeRetrieval())
    out = _run(h({"expression": "x", "kinds": ["content"]}))
    assert out["cost"]["error"]
    assert out["content"]["canonical"] is None


def test_missing_expression_returns_error_no_raise():
    h = create_ontology_semantics_handler(usl_service=_FakeUsl(), retrieval_service=_FakeRetrieval())
    out = _run(h({}))
    assert out["cost"]["error"]
