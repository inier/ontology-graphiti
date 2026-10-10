"""TDD：ontology_semantics 注册为第 8 个 MCP 工具（子项目 C E-10）。

验证：
  - 既有 7 工具注册不受影响（register_all 仍返回 7 键）
  - 追加 semantics 后总数 = 8，含 ontology_semantics
"""
from __future__ import annotations

from odap.biz.core.ontology.mcp.semantic_retrieval_tools import register_all
from odap.biz.core.ontology.mcp.semantics_tools import register_semantics_tool


class _FakeRegistry:
    def __init__(self):
        self.funcs = {}

    def register_function(self, name, description, func, category="function"):
        self.funcs[name] = {"description": description, "func": func,
                            "category": category}


def test_seven_tools_unchanged():
    reg = _FakeRegistry()
    handlers = register_all(registry=reg)
    assert len(handlers) == 7
    assert "ontology_query" in handlers


def test_semantics_is_eighth_tool():
    reg = _FakeRegistry()
    register_all(registry=reg)
    register_semantics_tool(registry=reg)
    assert len(reg.funcs) == 8
    assert "ontology_semantics" in reg.funcs
    assert reg.funcs["ontology_semantics"]["category"] == "semantic_retrieval"
