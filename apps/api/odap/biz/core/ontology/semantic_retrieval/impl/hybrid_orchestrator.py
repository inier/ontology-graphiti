"""HybridOrchestrator — 混合检索编排 Thin Adapter (spec 008 / FR-007/008 / US4).

设计 (Q5 §5.7 决策):
  · PipelineService 是本体构建 6 阶段管道，与混合检索编排语义不符
  · 复用其"有序步骤 + on_failure + 结果聚合"模式 → Thin Adapter
  · 注入 engines: Dict[str, Any]，每引擎须有 .search(ws, query, limit) 适配器
  · 容错策略：skip(跳过继续) / abort(中止全部) / degrade(降级返回)
  · 组件数 1-10，>5 性能警告 (FR-007 边界 + spec §99)
  · 所有函数体 ≤ 40 行 (Constitution I)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List

logger = logging.getLogger("semantic_retrieval.hybrid")

MAX_COMPONENTS = 10
PERFORMANCE_WARN_THRESHOLD = 5


class HybridOrchestrator:
    """混合检索编排：按 components[] 顺序执行各引擎，应用 on_failure 策略。"""

    def __init__(self, *, engines: Dict[str, Any] = None):
        self._engines = dict(engines or {})

    # ── 公共 API ─────────────────────────────────────────────────────────

    async def orchestrate(
        self,
        workspace_id: str,
        components: List[Dict[str, Any]],
        *,
        merge: str = "concat",
    ) -> Dict[str, Any]:
        """执行混合编排，返回 {mode, rows, total, components, warnings, request_id}。"""
        self._validate_components(components, engines=self._engines)
        warnings: List[str] = []
        if len(components) > PERFORMANCE_WARN_THRESHOLD:
            warnings.append(
                f"组件数 {len(components)} 超过 {PERFORMANCE_WARN_THRESHOLD}，可能影响性能"
            )
        results = await self._run_components(workspace_id, components, warnings)
        rows = self._merge_rows(results, merge, warnings)
        return {
            "mode": "hybrid",
            "request_id": f"hybrid-{uuid.uuid4().hex[:8]}",
            "rows": rows,
            "total": len(rows),
            "components": results,
            "warnings": warnings,
        }

    # ── 内部辅助（Constitution I：≤ 40 行） ──────────────────────────────

    @staticmethod
    def _validate_components(components: List[Dict[str, Any]],
                              engines: Dict[str, Any] | None = None) -> None:
        """组件数边界 (1 ≤ N ≤ 10) + 类型存在性校验（缺失抛 ValueError）。"""
        n = len(components)
        if n < 1:
            raise ValueError("组件数至少 1 个")
        if n > MAX_COMPONENTS:
            raise ValueError(
                f"组件数 {n} 超过上限 {MAX_COMPONENTS}（FR-007 边界约束）"
            )
        if not engines:
            return
        registered = set(engines.keys())
        for idx, comp in enumerate(components):
            ctype = comp.get("type")
            if ctype not in registered:
                raise ValueError(
                    f"组件 #{idx + 1} 的类型 '{ctype}' 未注册（可用引擎: {sorted(registered)}）"
                )

    async def _run_components(
        self,
        workspace_id: str,
        components: List[Dict[str, Any]],
        warnings: List[str],
    ) -> List[Dict[str, Any]]:
        """按顺序执行组件，应用 on_failure 策略，返回各组件 ComponentResult。

        若某组件因 abort 提前结束，后续未执行组件标记 not_executed，保持 results 长度 == components 长度。
        """
        results: List[Dict[str, Any]] = []
        aborted_at: int | None = None
        for idx, comp in enumerate(components):
            if aborted_at is not None:
                results.append({
                    "type": comp.get("type", f"#{idx}"),
                    "status": "not_executed",
                    "rows": [],
                    "total": 0,
                    "error": f"因组件 #{aborted_at + 1} abort，未执行",
                })
                continue
            result = await self._run_one(workspace_id, comp, idx, warnings)
            results.append(result)
            if result["status"] == "aborted":
                aborted_at = idx
        return results

    async def _run_one(
        self,
        workspace_id: str,
        comp: Dict[str, Any],
        idx: int,
        warnings: List[str],
    ) -> Dict[str, Any]:
        """执行单个组件，捕获异常 → 应用 on_failure（缺省 degrade 保守策略）。"""
        ctype = comp["type"]
        params = comp.get("params", {})
        on_failure = comp.get("on_failure", "degrade")
        query = params.get("query", "")
        limit = int(params.get("limit", 20))
        engine = self._engines.get(ctype)
        if engine is None:
            return self._handle_no_engine(ctype, idx, on_failure, warnings)
        try:
            raw = await engine.search(workspace_id, query, limit=limit)
            return {
                "type": ctype,
                "status": "ok",
                "rows": list(raw.get("rows", [])),
                "total": raw.get("total", 0),
                "explain": raw.get("explain"),
            }
        except Exception as exc:  # noqa: BLE001 — 容错策略覆盖所有异常
            return self._handle_failure(ctype, idx, on_failure, exc, warnings)

    @staticmethod
    def _handle_no_engine(ctype, idx, on_failure, warnings) -> Dict[str, Any]:
        """组件类型未注册引擎 → 按 on_failure 处理（默认 skip）。"""
        msg = f"组件 #{idx + 1} ({ctype}) 引擎未注册"
        warnings.append(f"{msg}，已跳过")
        return {"type": ctype, "status": "skipped", "rows": [], "total": 0, "error": msg}

    @staticmethod
    def _handle_failure(ctype, idx, on_failure, exc, warnings) -> Dict[str, Any]:
        """按 on_failure 策略处理组件失败。"""
        msg = f"组件 #{idx + 1} ({ctype}) 执行失败: {exc}"
        if on_failure == "abort":
            warnings.append(f"{msg}，已中止整条链")
            return {"type": ctype, "status": "aborted", "rows": [], "total": 0, "error": str(exc)}
        if on_failure == "degrade":
            warnings.append(f"{msg}，已降级返回部分结果")
            return {"type": ctype, "status": "degraded", "rows": [], "total": 0, "error": str(exc)}
        # default: skip
        warnings.append(f"{msg}，已跳过")
        return {"type": ctype, "status": "skipped", "rows": [], "total": 0, "error": str(exc)}

    @staticmethod
    def _merge_rows(
        results: List[Dict[str, Any]],
        merge: str,
        warnings: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        """合并各组件 rows（仅 status=ok 参与）。支持 concat/interleave/rank。"""
        ok_results = [r for r in results if r.get("status") == "ok"]
        if merge == "interleave":
            return HybridOrchestrator._merge_interleave(ok_results)
        if merge == "rank":
            return HybridOrchestrator._merge_rank(ok_results)
        if merge != "concat":
            msg = f"merge='{merge}' 未实现，回退 concat"
            logger.warning(msg)
            if warnings is not None:
                warnings.append(msg)
        return HybridOrchestrator._merge_concat(ok_results)

    @staticmethod
    def _merge_concat(ok_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """concat: 各组件 rows 顺序追加。"""
        merged: List[Dict[str, Any]] = []
        for r in ok_results:
            merged.extend(r.get("rows", []))
        return merged

    @staticmethod
    def _merge_interleave(ok_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """interleave: 多组件 rows 轮询交替拼接（短组件耗尽后剩余追加）。"""
        row_lists = [list(r.get("rows", [])) for r in ok_results]
        merged: List[Dict[str, Any]] = []
        max_len = max((len(rl) for rl in row_lists), default=0)
        for i in range(max_len):
            for rl in row_lists:
                if i < len(rl):
                    merged.append(rl[i])
        return merged

    @staticmethod
    def _merge_rank(ok_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """rank: 按 row.score 降序稳定排序（无 score 视为 0.0）。"""
        merged: List[Dict[str, Any]] = []
        for r in ok_results:
            merged.extend(r.get("rows", []))
        # 稳定排序：按 score 降序（Python sort 稳定，同分保持原序）
        merged.sort(key=lambda row: float(row.get("score", 0.0)), reverse=True)
        return merged
