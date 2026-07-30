"""Metric Engine — BI 工具指标查询引擎 (spec 008 / US2 / FR-006).

Phase 1 不引入 MetricType 一等公民（T012 plan.md 要求），
TBox 自动派生 {count, density, trend} 三个聚合指标。

Constitution IV:
  - 不新建 IRetrievalEngine 接口（待 Phase 2 出现第二引擎再提）
  - 薄适配器：复用 QueryService.execute_async 与 DSL，不直连 Neo4j
  - 引擎仅提供 .metric() 异步方法；UnifiedRouter 通过 MetricEngineWrapper 适配为 .search()

Constitution I: 函数体 ≤ 40 行。

支持项（T011 验收覆盖）：
  - count:      实例数（按 object_type 过滤，空集返回 0）
  - density:    连接密度 = edges/vertices（孤立图 0 不除零）
  - trend:      时间趋势（granularity=day/week/month + time_window 边界）
  - 未知 metric: status='degraded' 优雅降级
  - granularity: 非 {day,week,month,None} 抛 ValueError
  - limit ≤ 0 或 > 200 抛 ValueError
"""

import logging
from typing import Any, Dict, List, Optional

from odap.infra.query.service import get_query_service

logger = logging.getLogger("semantic_retrieval.metric_engine")

_GRANULARITIES = ("day", "week", "month")
_SEARCH_MAX = 200
_SEARCH_MIN = 1


class MetricEngine:
    """BI 指标适配器：DSL 化 QueryService → 指标值。"""

    def __init__(self, query_service=None):
        self._qs = query_service or get_query_service()

    # ------------------------------------------------------------------
    # Public: MetricEngine.metric(workspace_id, metric, **) — test 调用
    # ------------------------------------------------------------------

    async def metric(
        self,
        workspace_id: str,
        metric: str,
        *,
        object_type: Optional[str] = None,
        granularity: Optional[str] = None,
        time_window: Optional[Dict[str, Any]] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """TBox 自动派生指标入口。"""
        self._validate_limit(limit)
        self._validate_granularity(granularity)

        dsl = self._build_dsl(metric, object_type, granularity, time_window)
        raw = await self._qs.execute_async(workspace_id, dsl, limit=limit)
        rows = list(raw.rows) if hasattr(raw, "rows") else list(raw.get("rows", []))

        if self._is_unknown(metric, rows):
            return {
                "mode": "metric",
                "metrics": [],
                "rows": [],
                "total": 0,
                "explain": {"source": "metric", "dsl": dsl, "status": "degraded"},
            }
        metrics = self._derive_metrics(metric, rows, object_type, granularity)
        return {
            "mode": "metric",
            "metrics": metrics,
            "rows": metrics,
            "total": len(metrics),
            "explain": {"source": "metric", "dsl": dsl, "status": "ok"},
        }

    # ------------------------------------------------------------------
    # Public (UnifiedRouter adapter): .search(ws, query, limit) dict
    # ------------------------------------------------------------------

    async def search(self, workspace_id: str, query: str, limit: int = 20) -> Dict[str, Any]:
        """UnifiedRouter 适配：query=count|density|trend|auto(→count)。"""
        metric_choice = self._infer_metric_from_query(query) or "count"
        return await self.metric(workspace_id, metric_choice, limit=limit)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if not isinstance(limit, int) or limit < _SEARCH_MIN or limit > _SEARCH_MAX:
            raise ValueError(f"limit must be {_SEARCH_MIN}..{_SEARCH_MAX}, got {limit}")

    @staticmethod
    def _validate_granularity(granularity: Optional[str]) -> None:
        if granularity is None:
            return
        if granularity not in _GRANULARITIES:
            raise ValueError(
                f"granularity must be one of {_GRANULARITIES} (or None), got {granularity!r}"
            )

    @staticmethod
    def _build_dsl(metric, object_type, granularity, time_window) -> str:
        """构建 Metric DSL（QueryService 会按 metric:前缀路由到统计分支）。"""
        parts = [f"metric:{metric}"]
        if object_type:
            parts.append(f"object_type:{object_type}")
        if granularity:
            parts.append(f"granularity:{granularity}")
        if time_window:
            parts.append(f"tw:{time_window.get('start', '')}/{time_window.get('end', '')}")
        return " ".join(parts)

    @staticmethod
    def _is_unknown(metric: str, rows: List[Dict[str, Any]]) -> bool:
        """QueryService 无法识别 metric 时返回空行 → 视为 unknown。"""
        KNOWN = ("count", "density", "trend")
        if metric not in KNOWN:
            return True
        if not rows:
            # count 返回 {"metric":"count", "value":0} 时 rows=[{...}] 非空
            # 当完全无 rows 时说明 metric 前缀不被识别
            return True
        return False

    @staticmethod
    def _derive_metrics(
        metric: str,
        rows: List[Dict[str, Any]],
        object_type: Optional[str],
        granularity: Optional[str],
    ) -> List[Dict[str, Any]]:
        """将 QueryService 返回的 row 转为 MetricValue 列表
        ({metric_name, value, unit, dimensions})。"""
        if metric == "count":
            name = f"{object_type or 'entity'}_count"
            value = (rows[0].get("value", 0) if rows else 0)
            return [{"metric_name": name, "value": value, "unit": "count", "dimensions": {}}]
        if metric == "density":
            value = (rows[0].get("value", 0.0) if rows else 0.0)
            return [
                {
                    "metric_name": "graph_connection_density",
                    "value": float(value),
                    "unit": "edges_per_vertex",
                    "dimensions": {},
                }
            ]
        if metric == "trend":
            out = []
            for row in rows:
                dimensions = {}
                if "date" in row:
                    dimensions["date"] = row["date"]
                if granularity:
                    dimensions["granularity"] = granularity
                out.append(
                    {
                        "metric_name": f"{object_type or 'entity'}_trend",
                        "value": row.get("value", 0),
                        "unit": "count",
                        "dimensions": dimensions,
                    }
                )
            return out
        # 理论上 _is_unknown 已覆盖；保留安全零值
        return []
