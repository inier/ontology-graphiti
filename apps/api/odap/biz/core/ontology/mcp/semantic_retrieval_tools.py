"""Semantic Retrieval MCP Tools (spec 008 / FR-009/010 / US5 / ADR-026).

将统一检索能力注册为 MCP 工具，供 OpenHarness 等 Agent 框架调用。
工具调用结果与直接 REST API 调用完全一致 (FR-010) — 复用同一 RetrievalService。

注册模式 (ADR-026 / 镜像 platform/tool_registry/registry.py:register_function):
  registry.register_function(name, description, func, category="function")

7 个工具 (Phase 5 / FR-009 全端点覆盖):
  - ontology_query   → POST /query   (统一检索，auto 路由)
  - ontology_graph   → POST /graph   (分项图检索)
  - ontology_nl      → POST /nl      (分项 NL 检索 + USL 消歧)
  - ontology_metric  → POST /metric  (指标查询 count/density/trend)
  - ontology_reason  → POST /chain   (链式推理 + 循环检测)
  - ontology_mdl     → POST /mdl     (MDL/DSL 模板推理，复用 HE)
  - ontology_hybrid  → POST /hybrid  (混合检索编排 + 容错)
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from ..semantic_retrieval.models.schemas import SearchRequest
from ..semantic_retrieval.services.retrieval_service import RetrievalService

logger = logging.getLogger("semantic_retrieval.mcp")


# ── 工具描述（contracts L232-234 input_schema 关键字段文档化） ────────────

_DESC_QUERY = (
    "本体统一检索 — 自动路由到最合适的检索引擎 (graph/nl/chain/mdl/metric)。\n"
    "input_schema: query:str (自然语言或结构化查询), "
    "mode?:str=auto|chain|nl|mdl|graph|metric, "
    "limit?:int=1..200, workspace_id:str"
)

_DESC_REASON = (
    "本项链式推理 — rules[] 有序传导 + 循环检测 + 规则冲突收集 (FR-014)。\n"
    "input_schema: query:str (起点节点), rules?:list[str] (规则 ID 路径), "
    "max_depth?:int=1..10 (硬上限 10), "
    "persist_candidates?:bool=false (推理结论落盘 USL Candidate), "
    "workspace_id:str"
)

_DESC_METRIC = (
    "本体指标查询 — TBox 自动派生统计 count/density/trend。\n"
    "input_schema: metric:str=count|density|trend, "
    "object_type?:str (按对象类型过滤), "
    "granularity?:str=day|week|month (trend 必填), "
    "workspace_id:str"
)

_DESC_GRAPH = (
    "本体分项图检索 — 实体/关系图结构查询 (FR-005)。\n"
    "input_schema: query:str (Cypher 片段或实体关键词), "
    "limit?:int=1..200 (默认 20), "
    "workspace_id:str"
)

_DESC_NL = (
    "本体分项 NL 检索 — 自然语言查询 + USL 术语消歧 (FR-003/FR-016)。\n"
    "input_schema: query:str (自然语言), "
    "limit?:int=1..200 (默认 20), "
    "workspace_id:str"
)

_DESC_MDL = (
    "本体分项 MDL/DSL 推理 — 复用 HE YAML 模板引用 (FR-004 / US3 / Q6 不发明 DSL)。\n"
    "input_schema: query:str (含 template/entity/params 的 YAML 段), "
    "persist_candidates?:bool=false (推理结论落盘 USL Candidate), "
    "workspace_id:str"
)

_DESC_HYBRID = (
    "本体混合检索编排 — 多组件顺序执行 + on_failure 容错 (FR-007/008 / US4)。\n"
    "input_schema: components:list[{type,params,on_failure}], "
    "merge?:str=concat|interleave|rank (默认 concat), "
    "workspace_id:str"
)


# ── 工具 handler 工厂 — 返回 async callable(args: dict) ──────────────────

def create_ontology_query_handler(
    service: Optional[Any] = None,
) -> Callable[[Dict[str, Any]], Any]:
    """ontology_query handler: 调用 RetrievalService.search (FR-010 一致)。"""
    svc = service or RetrievalService()

    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        workspace_id = args.get("workspace_id", "default")
        request = SearchRequest(
            query=args["query"],
            mode=args.get("mode", "auto"),
            limit=int(args.get("limit", 20)),
        )
        result = await svc.search(workspace_id, request)
        # SearchResult → dict (FR-010 与 REST 响应一致)
        return result.model_dump() if hasattr(result, "model_dump") else dict(result)

    return handler


def create_ontology_reason_handler(
    service: Optional[Any] = None,
) -> Callable[[Dict[str, Any]], Any]:
    """ontology_reason handler: 调用 RetrievalService.chain_search (FR-010 一致)。"""
    svc = service or RetrievalService()

    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        workspace_id = args.get("workspace_id", "default")
        raw = await svc.chain_search(
            workspace_id,
            query=args["query"],
            rules=list(args.get("rules", [])),
            max_depth=int(args.get("max_depth", 5)),
            persist_candidates=bool(args.get("persist_candidates", False)),
        )
        return raw

    return handler


def create_ontology_metric_handler(
    service: Optional[Any] = None,
) -> Callable[[Dict[str, Any]], Any]:
    """ontology_metric handler: 调用 RetrievalService.metric_search (FR-010 一致)。"""
    svc = service or RetrievalService()

    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        workspace_id = args.get("workspace_id", "default")
        tw = args.get("time_window")
        raw = await svc.metric_search(
            workspace_id,
            args["metric"],
            object_type=args.get("object_type"),
            granularity=args.get("granularity"),
            time_window=tw if isinstance(tw, dict) else None,
            limit=int(args.get("limit", 20)),
        )
        return raw

    return handler


def create_ontology_graph_handler(
    service: Optional[Any] = None,
) -> Callable[[Dict[str, Any]], Any]:
    """ontology_graph handler: 调用 RetrievalService.graph_search (FR-010 一致)。"""
    svc = service or RetrievalService()

    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        workspace_id = args.get("workspace_id", "default")
        raw = await svc.graph_search(
            workspace_id,
            args["query"],
            limit=int(args.get("limit", 20)),
        )
        return raw

    return handler


def create_ontology_nl_handler(
    service: Optional[Any] = None,
) -> Callable[[Dict[str, Any]], Any]:
    """ontology_nl handler: 调用 RetrievalService.nl_search (FR-010 一致)。"""
    svc = service or RetrievalService()

    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        workspace_id = args.get("workspace_id", "default")
        raw = await svc.nl_search(
            workspace_id,
            args["query"],
            limit=int(args.get("limit", 20)),
        )
        return raw

    return handler


def create_ontology_mdl_handler(
    service: Optional[Any] = None,
) -> Callable[[Dict[str, Any]], Any]:
    """ontology_mdl handler: 调用 RetrievalService.mdl_search (FR-010 一致)。"""
    svc = service or RetrievalService()

    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        workspace_id = args.get("workspace_id", "default")
        raw = await svc.mdl_search(
            workspace_id,
            query=args["query"],
            persist_candidates=bool(args.get("persist_candidates", False)),
        )
        return raw

    return handler


def create_ontology_hybrid_handler(
    service: Optional[Any] = None,
) -> Callable[[Dict[str, Any]], Any]:
    """ontology_hybrid handler: 调用 RetrievalService.hybrid_search (FR-010 一致)。"""
    svc = service or RetrievalService()

    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        workspace_id = args.get("workspace_id", "default")
        components = list(args.get("components", []))
        raw = await svc.hybrid_search(
            workspace_id,
            components,
            merge=args.get("merge", "concat"),
        )
        return raw

    return handler


# ── 批量注册入口 ─────────────────────────────────────────────────────────

def register_all(
    registry: Optional[Any] = None,
    service: Optional[Any] = None,
) -> Dict[str, Callable]:
    """将 7 个 MCP 工具注册到 registry，返回 {name: handler} 供直接调用。

    registry 需提供 register_function(name, description, func, category) 方法
    （镜像 platform/tool_registry/registry.py 接口，ADR-026 bridge 兼容）。
    """
    if registry is None:
        registry = _get_default_registry()

    handlers = {
        "ontology_query": create_ontology_query_handler(service),
        "ontology_graph": create_ontology_graph_handler(service),
        "ontology_nl": create_ontology_nl_handler(service),
        "ontology_metric": create_ontology_metric_handler(service),
        "ontology_reason": create_ontology_reason_handler(service),
        "ontology_mdl": create_ontology_mdl_handler(service),
        "ontology_hybrid": create_ontology_hybrid_handler(service),
    }
    descs = {
        "ontology_query": _DESC_QUERY,
        "ontology_graph": _DESC_GRAPH,
        "ontology_nl": _DESC_NL,
        "ontology_metric": _DESC_METRIC,
        "ontology_reason": _DESC_REASON,
        "ontology_mdl": _DESC_MDL,
        "ontology_hybrid": _DESC_HYBRID,
    }
    for name, fn in handlers.items():
        registry.register_function(
            name=name,
            description=descs[name],
            func=fn,
            category="semantic_retrieval",
        )
        logger.info("MCP 工具已注册: %s", name)
    return handlers


def _get_default_registry():
    """获取平台默认工具注册表（延迟导入避免循环依赖）。"""
    from odap.biz.platform.tool_registry.registry import (
        get_tool_registry,
    )
    return get_tool_registry()
