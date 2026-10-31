"""检索执行：语义检索服务总线 + 降级链（AC-29）。

降级链（ARCHITECTURE-v2 §2.1 第 4 步 / §11）：
    graph → nl → mdl → metric
单引擎失败不算整体失败：记录 `degraded_engines[]` 后继续下一个；
全部失败则返回空证据（下游 AnswerComposer 必须给 `no_answer`，禁止编造，AC-30）。

引擎接口：既有 `semantic_retrieval` 引擎的 `async search(workspace_id, query, limit)`
（`impl/{graph,nl,mdl,metric}_engine.py`）。构造代价高（连 Neo4j / QueryService），
故每次执行时惰性构造，构造失败同样计入降级而不是抛错。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Sequence

from odap.biz.core.ontology.orchestration.contracts import (
    Evidence,
    MappedQuery,
    RetrievalResult,
    StepProv,
)

logger = logging.getLogger(__name__)

DEGRADATION_CHAIN: Sequence[str] = ("graph", "nl", "mdl", "metric")


def default_engine_factories() -> Dict[str, Callable[[], Any]]:
    """既有检索引擎工厂（惰性 import，避免模块导入期连库）。"""

    def _graph():
        from odap.biz.core.ontology.semantic_retrieval.impl.graph_engine import GraphEngine

        return GraphEngine()

    def _nl():
        from odap.biz.core.ontology.semantic_retrieval.impl.nl_engine import NLEngine

        return NLEngine()

    def _mdl():
        from odap.biz.core.ontology.semantic_retrieval.impl.mdl_engine import MdlEngine

        return MdlEngine()

    def _metric():
        from odap.biz.core.ontology.semantic_retrieval.impl.metric_engine import MetricEngine

        return MetricEngine()

    return {"graph": _graph, "nl": _nl, "mdl": _mdl, "metric": _metric}


class MultiEngineRetrievalExecutor:
    """按降级链执行的检索器（插槽实现）。"""

    name = "RetrievalExecutor"
    version = "v2.0"

    def __init__(
        self,
        engine_factories: Optional[Dict[str, Callable[[], Any]]] = None,
        chain: Sequence[str] = DEGRADATION_CHAIN,
        timeout_seconds: float = 8.0,
        limit: int = 20,
    ) -> None:
        self._factories = engine_factories or default_engine_factories()
        self.chain = tuple(chain)
        self.timeout_seconds = timeout_seconds
        self.limit = limit

    async def execute(self, mapped: MappedQuery, query: str,
                      workspace_id: str, mode: str = "auto") -> RetrievalResult:
        prov = StepProv(component=self.name, version=self.version)
        result = RetrievalResult(prov=prov)
        modes = self._resolve_modes(mode)

        for engine_name in modes:
            factory = self._factories.get(engine_name)
            if factory is None:
                result.degraded_engines.append(engine_name)
                continue
            try:
                engine = factory()
                raw = await asyncio.wait_for(
                    engine.search(workspace_id, query, limit=self.limit),
                    timeout=self.timeout_seconds,
                )
            except Exception as exc:  # noqa: BLE001 - 单引擎失败 → 降级，不整体失败
                logger.warning(
                    "retrieval engine degraded: engine=%s workspace=%s error_type=%s error=%s",
                    engine_name, workspace_id, type(exc).__name__, exc,
                )
                result.degraded_engines.append(engine_name)
                continue

            rows = list((raw or {}).get("rows") or [])
            citations = _rows_to_evidence(raw or {}, rows)
            if citations:
                result.chains.append({
                    "engine": engine_name,
                    "total": int((raw or {}).get("total") or len(rows)),
                    "rows": rows[: self.limit],
                })
                result.citations.extend(citations)
                prov.evidence.extend(citations)
                result.evidence_count = len(result.citations)
                return result
            # 引擎可用但零命中：不算降级，继续下一个引擎以扩大召回
            result.chains.append({
                "engine": engine_name,
                "total": int((raw or {}).get("total") or 0),
                "rows": [],
            })

        if result.degraded_engines:
            prov.evidence.append(
                Evidence(kind="decision", ref="decision:retrieval_degraded")
            )
        if not result.citations:
            prov.evidence.append(Evidence(kind="decision", ref="decision:no_evidence"))
        return result

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _resolve_modes(self, mode: str) -> List[str]:
        if not mode or mode == "auto":
            return list(self.chain)
        if mode not in self._factories:
            # 非法 mode 由路由层 Pydantic 枚举拦截；此处兜底走整条降级链
            return list(self.chain)
        # 指定引擎失败后仍允许按链路继续降级（AC-29）
        return [mode] + [m for m in self.chain if m != mode]


def _rows_to_evidence(raw: Dict[str, Any], rows: List[Any]) -> List[Evidence]:
    """把检索行转成可解析证据；**只使用行里真实存在的标识字段**。"""
    evidence: List[Evidence] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ref = (
            row.get("source_ref") or row.get("doc_id") or row.get("chunk_id")
            or row.get("entity_id") or row.get("id")
        )
        if not ref:
            continue
        kind = "doc" if (row.get("doc_id") or row.get("chunk_id")
                         or str(ref).startswith("repo:")) else "graph_edge"
        evidence.append(Evidence(kind=kind, ref=str(ref), asof=row.get("asof")))
    for citation in (raw or {}).get("citations") or []:
        if isinstance(citation, dict) and citation.get("ref"):
            evidence.append(Evidence(
                kind=str(citation.get("kind") or "doc"), ref=str(citation["ref"])
            ))
    return evidence


__all__ = ["MultiEngineRetrievalExecutor", "default_engine_factories", "DEGRADATION_CHAIN"]
