"""Unified Router — 统一检索自动路由 (spec 008 / FR-001).

三层检索之「统一检索层」：调用方只给 query + mode=auto，路由器自动选择引擎。
Constitution IV：用 dict 策略表分发，不建抽象工厂/单实现接口。

mode 取值：auto|chain|nl|mdl|graph|metric
- auto：按默认策略选择（当前默认 nl）
- 其它：精确路由到对应引擎；未注册的 mode 抛 ValueError（由路由层翻译为 4xx）
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("semantic_retrieval.unified_router")


class UnifiedRouter:
    """统一检索路由器：mode → engine 分发。"""

    def __init__(
        self,
        engines: Optional[Dict[str, Any]] = None,
        auto_default: str = "nl",
    ):
        # engines: {mode: engine}，engine 需实现 async .search(workspace_id, query, limit)
        self._engines: Dict[str, Any] = dict(engines or {})
        self._auto_default = auto_default

    def register(self, mode: str, engine: Any) -> None:
        """注册一个检索引擎。"""
        self._engines[mode] = engine

    async def route(
        self,
        workspace_id: str,
        query: str,
        mode: str = "auto",
        limit: int = 20,
    ) -> Dict[str, Any]:
        """按 mode 路由到对应引擎并返回统一结果。"""
        resolved = self._resolve_mode(mode)
        engine = self._engines.get(resolved)
        if engine is None:
            raise ValueError(f"unsupported retrieval mode: {resolved}")
        raw = await engine.search(workspace_id, query, limit=limit)
        return {"mode": resolved, **raw}

    def _resolve_mode(self, mode: str) -> str:
        if mode == "auto":
            return self._auto_default
        return mode
