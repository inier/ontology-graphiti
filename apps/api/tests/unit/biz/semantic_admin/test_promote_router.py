"""TDD：promote_router 纯函数（子项目 D E-1/E-2/E-6）。"""
from __future__ import annotations

from odap.biz.semantic_admin.gap_pool.services.promote_router import (
    route, decide_layer, build_schema_patch, RouteResult,
)


def _gap(layer_counts=None, occs=None, expression="司马懿", **extra):
    g = {
        "id": "g1", "expression": expression, "scope_key": "ws::d1",
        "workspace_id": "ws", "domain_id": "d1",
        "attribution_counts_json": layer_counts or {},
        "sources_json": occs or [],
    }
    g.update(extra)
    return g


def test_no_attribution_defaults_to_content():
    r = route(_gap())
    assert r.layer == "content"
    assert r.routed_to == "candidate_store"
    assert r.target_kind == "term"


def test_schema_wins_over_content():
    # schema + content 同时存在 → 风险倒序取 schema
    r = route(_gap({"content": 2, "schema": 3}))
    assert r.layer == "schema"
    assert r.routed_to == "change_proposal"


def test_tool_layer_routes_to_tool_routing():
    r = route(_gap({"tool": 1}, occs=[{"attribution": {"layer": "tool",
                                                       "target_ref": "nl_engine"}}]))
    assert r.layer == "tool"
    assert r.routed_to == "tool_routing"
    assert r.payload["engine"] == "nl_engine"


def test_force_layer_overrides_attribution():
    r = route(_gap({"schema": 5}), force_layer="content")
    assert r.layer == "content"
    assert r.routed_to == "candidate_store"


def test_force_layer_invalid_falls_back_to_decide():
    r = route(_gap({"schema": 5}), force_layer="bogus")
    assert r.layer == "schema"


def test_build_schema_patch_object_type():
    occs = [{"attribution": {"layer": "schema", "target_kind": "object_type"}}]
    patches = build_schema_patch(_gap({"schema": 1}, occs), "object_type")
    assert patches == [{"op": "add", "path": "/object_types/司马懿",
                        "value": {"name": "司马懿"}}]


def test_build_schema_patch_relation_type():
    patches = build_schema_patch(_gap(expression="结义"), "relation_type")
    assert patches[0]["path"] == "/relation_types/结义"


def test_build_schema_patch_property_uses_parent():
    occs = [{"attribution": {"layer": "schema", "target_kind": "property",
                             "parent": "人物"}}]
    patches = build_schema_patch(_gap({"schema": 1}, occs), "property")
    assert patches[0]["path"] == "/object_types/人物/properties/司马懿"


def test_build_schema_patch_unknown_kind_empty():
    assert build_schema_patch(_gap(), "something_else") == []


def test_decide_layer_priority_direct():
    assert decide_layer(_gap({"content": 1, "schema": 1, "tool": 1})) == "schema"
    assert decide_layer(_gap({"content": 1, "tool": 1})) == "tool"
    assert decide_layer(_gap({"content": 1})) == "content"


def test_route_result_is_frozen():
    r = route(_gap())
    assert isinstance(r, RouteResult)
    try:
        r.layer = "x"      # type: ignore
        assert False, "RouteResult 应不可变"
    except Exception:
        pass
