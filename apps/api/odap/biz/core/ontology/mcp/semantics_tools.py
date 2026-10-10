"""Ontology Semantics MCP Tool —— 按需查询本体语义（ADR-089 / 子项目 C）。

第 8 个 MCP 工具 `ontology_semantics`：给一个 expression，返回三层语义：

  - content 层：USL 术语（canonical / synonyms / near_synonyms / aliases / semantic_type）
  - schema  层：TBox 结构（object_type / properties / relation_types）
  - tool    层：建议的检索引擎（哪个 MCP 工具能答这种查询）

外加 `cost` 对账块（round_trips / llm_tokens / wall_ms / error），补 EvoOntology
论文自承的「没做 cost accounting」空白。

设计约束（ADR-089）：
  C-D1  复用现有 7 工具的注册模板（registry.register_function）。
  C-D2  签名 (expression, domain_id, kinds) → {content, schema, tool, cost}。
  C-D4  复用 RetrievalService.nl_search / search，不新建检索引擎。
  C-D6  handler **失败降级**：任何 span 异常 → 记录 cost.error、字段返回空，**绝不 raise**。
  C-D7  同步暴露 HTTP 端点 /api/ontology/mcp/semantics（见 platform 路由）。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("ontology.mcp.semantics_tools")

_VALID_KINDS = ("content", "schema", "tool")

# 静态「tool 层」建议规则：expression 形态 → 建议引擎（确定性，不调 LLM）。
_METRIC_HINTS = ("多少", "数量", "统计", "总数", "占比", "趋势", "分布")
_CHAIN_HINTS = ("推导", "推理", "因果", "导致", "链")


class _CostRecorder:
    """一次调用的成本记录器（span 计数 round trip + wall time）。"""

    def __init__(self) -> None:
        self.round_trips = 0
        self.cache_hits = 0
        self.llm_tokens_in = 0
        self.llm_tokens_out = 0
        self.errors: List[str] = []
        self._t0 = time.perf_counter()

    def span(self, name: str, exc: Optional[BaseException] = None) -> None:
        self.round_trips += 1
        if exc is not None:
            self.errors.append(f"{name}: {type(exc).__name__}: {exc}")

    def snapshot(self) -> Dict[str, Any]:
        return {
            "round_trips": self.round_trips,
            "cache_hits": self.cache_hits,
            "llm_tokens_in": self.llm_tokens_in,
            "llm_tokens_out": self.llm_tokens_out,
            "wall_ms": round((time.perf_counter() - self._t0) * 1000.0, 3),
            "error": "; ".join(self.errors) if self.errors else None,
        }


def _extract_content(terms: List[Dict[str, Any]]) -> Dict[str, Any]:
    """从 USL list_terms 结果抽 content 层。未命中 → canonical=None（不造数）。"""
    if not terms:
        return {"canonical": None, "synonyms": [], "near_synonyms": [],
                "aliases": [], "semantic_type": None, "domain_id": None}
    t = terms[0]
    st = t.get("semantic_type")
    return {
        "canonical": t.get("canonical"),
        "synonyms": list(t.get("synonyms") or []),
        "near_synonyms": list(t.get("near_synonyms") or []),
        "aliases": list(t.get("aliases") or []),
        "semantic_type": str(st) if st is not None else None,
        "domain_id": t.get("domain_id"),
    }


def _extract_schema(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """从图检索 rows 抽 schema 层。无行 → 空（不造数）。"""
    if not rows:
        return {"object_type": None, "properties": [], "relation_types": []}
    r = rows[0]
    return {
        "object_type": r.get("object_type") or r.get("label") or r.get("name"),
        "properties": list(r.get("properties") or []),
        "relation_types": list(r.get("relation_types") or r.get("relations") or []),
    }


def _suggest_engines(expression: str, content: Dict[str, Any],
                     schema: Dict[str, Any]) -> List[str]:
    """tool 层：确定性地建议检索引擎（不调 LLM）。"""
    engines: List[str] = []
    if any(h in expression for h in _METRIC_HINTS):
        engines.extend(["metric"])
    if any(h in expression for h in _CHAIN_HINTS):
        engines.extend(["chain"])
    if content.get("canonical"):
        engines.extend(["nl", "graph"])
    elif schema.get("object_type"):
        engines.extend(["graph"])
    if not engines:
        engines = ["nl", "graph"]
    # 去重保序
    seen: set = set()
    out: List[str] = []
    for e in engines:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


def create_ontology_semantics_handler(
    retrieval_service: Optional[Any] = None,
    usl_service: Optional[Any] = None,
) -> Callable[[Dict[str, Any]], Any]:
    """ontology_semantics handler 工厂。返回 async callable(args: dict) -> dict。"""

    def _svc() -> Any:
        if retrieval_service is not None:
            return retrieval_service
        from ..semantic_retrieval.services.retrieval_service import RetrievalService
        return RetrievalService()

    def _usl() -> Any:
        if usl_service is not None:
            return usl_service
        from odap.biz.semantic_admin.usl_manager.services import UslManagerService
        return UslManagerService()

    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        cost = _CostRecorder()
        out: Dict[str, Any] = {}
        expression = (args.get("expression") or "").strip()
        domain_id = args.get("domain_id") or ""
        kinds = args.get("kinds") or list(_VALID_KINDS)
        kinds = [k for k in kinds if k in _VALID_KINDS]
        if not expression:
            cost.errors.append("expression: missing")
            out["cost"] = cost.snapshot()
            return out

        content: Dict[str, Any] = {}
        schema: Dict[str, Any] = {}

        if "content" in kinds:
            try:
                res = _usl().list_terms(synonym_keyword=expression, page_size=5)
                items = (res or {}).get("items", []) if isinstance(res, dict) else []
                content = _extract_content(items)
                cost.span("list_terms")
            except Exception as e:  # C-D6 降级
                cost.span("list_terms", exc=e)
                content = _extract_content([])
            out["content"] = content

        if "schema" in kinds:
            try:
                from ..semantic_retrieval.models.schemas import SearchRequest
                raw = await _svc().search(
                    workspace_id=domain_id or "default",
                    request=SearchRequest(query=expression, mode="graph", limit=5),
                )
                rows = raw.get("rows", []) if isinstance(raw, dict) else getattr(raw, "rows", [])
                schema = _extract_schema(list(rows))
                cost.span("graph_search")
            except Exception as e:  # C-D6 降级
                cost.span("graph_search", exc=e)
                schema = _extract_schema([])
            out["schema"] = schema

        if "tool" in kinds:
            out["tool"] = {"engines": _suggest_engines(expression, content, schema)}

        out["cost"] = cost.snapshot()
        return out

    return handler


# ── 工具描述（文档化 input_schema） ──────────────────────────────────────

_DESC_SEMANTICS = (
    "本体语义查询 — 给定 expression 返回三层语义（按需查询，替代全量注入）。\n"
    "input_schema: expression:str (术语/实体文本，必填), "
    "domain_id?:str (领域编码), "
    "kinds?:list[str]=['content','schema','tool'] (content=USL 术语, "
    "schema=TBox 结构, tool=建议引擎); "
    "输出 {content:{canonical,synonyms,near_synonyms,aliases,semantic_type,domain_id}, "
    "schema:{object_type,properties,relation_types}, tool:{engines}, "
    "cost:{round_trips,cache_hits,llm_tokens_in,llm_tokens_out,wall_ms,error}}"
)


def register_semantics_tool(
    registry: Optional[Any] = None,
    retrieval_service: Optional[Any] = None,
    usl_service: Optional[Any] = None,
) -> Callable[[Dict[str, Any]], Any]:
    """把 `ontology_semantics` 注册到 registry（第 8 个 MCP 工具）。返回 handler。"""
    if registry is None:
        from odap.biz.platform.tool_registry.registry import get_tool_registry
        registry = get_tool_registry()
    handler = create_ontology_semantics_handler(
        retrieval_service=retrieval_service, usl_service=usl_service)
    registry.register_function(
        name="ontology_semantics",
        description=_DESC_SEMANTICS,
        func=handler,
        category="semantic_retrieval",
    )
    logger.info("MCP 工具已注册: ontology_semantics")
    return handler


__all__ = [
    "create_ontology_semantics_handler",
    "register_semantics_tool",
    "_CostRecorder",
]
