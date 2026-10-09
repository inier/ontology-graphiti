"""RegressionService —— 回归集编排层（规则 2：返回 dict；规则 6：routes→services→storage）。"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from .builder import RegressionSetBuilder
from .runner import PairedReplayRunner, current_model_fingerprint
from .storage import SQLiteGapRegressionStorage

logger = logging.getLogger(__name__)


class RegressionService:
    def __init__(self, storage: Optional[SQLiteGapRegressionStorage] = None,
                 builder: Optional[RegressionSetBuilder] = None,
                 runner: Optional[PairedReplayRunner] = None,
                 data_dir: Optional[str] = None):
        """data_dir：测试用隔离目录（缺口库/回归库均落在其下，规则 13）。"""
        if data_dir:
            from ..storage.sqlite_gap_storage import SQLiteGapStorage
            gap_storage = SQLiteGapStorage(
                db_path=os.path.join(data_dir, "concept_gaps.db"))
            storage = storage or SQLiteGapRegressionStorage(
                db_path=os.path.join(data_dir, "gap_regression.db"))
            builder = builder or RegressionSetBuilder(
                gap_storage=gap_storage, storage=storage)
        self.storage = storage or SQLiteGapRegressionStorage()
        self._builder = builder or RegressionSetBuilder(storage=self.storage)
        self._runner = runner

    # ---- 回归集 ----
    def build(self, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = body or {}
        return self._builder.build(
            status=body.get("status"),
            workspace_id=body.get("workspace_id"),
            domain_id=body.get("domain_id"),
            min_heat=int(body.get("min_heat") or 1),
        )

    def list_sets(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        try:
            items, total = self.storage.list_sets(page=page, page_size=page_size)
            return {"status": "ok", "items": items, "total": total}
        except Exception as e:
            logger.warning("list_sets 失败: %s", e, exc_info=True)
            return {"status": "error", "message": f"查询回归集失败: {e}"}

    def get_set(self, set_id: str) -> Dict[str, Any]:
        s = self.storage.get_set(set_id)
        if not s:
            return {"status": "error", "message": f"回归集 {set_id} 不存在",
                    "code": "SET_NOT_FOUND_404"}
        return {"status": "ok", "set": s}

    # ---- 配对回放 ----
    async def replay(self, set_id: str) -> Dict[str, Any]:
        s = self.storage.get_set(set_id)
        if not s:
            return {"status": "error", "message": f"回归集 {set_id} 不存在",
                    "code": "SET_NOT_FOUND_404"}
        try:
            runner = self._runner or PairedReplayRunner()
            workspace_id = s.get("scope_key", "").split("::")[0]
            if workspace_id in ("", "-"):
                workspace_id = None
            result = await runner.replay(
                s.get("cases_json") or [], workspace_id=workspace_id)
        except Exception as e:  # 规则 14：失败显式
            logger.warning("replay 失败(set=%s): %s", set_id, e, exc_info=True)
            return {"status": "error",
                    "message": f"配对回放失败: {type(e).__name__}: {e}"}

        # 模型指纹比对（D8）：与构建集不一致时报告头部警示（仍出报告，不拦截）
        result["set_id"] = set_id
        result["model_mismatch"] = bool(
            s.get("model_id") and result.get("model_id")
            and s["model_id"] != result["model_id"])
        if result["model_mismatch"]:
            result["warning"] = (
                f"当前模型 {result['model_id']!r} 与构建集模型 "
                f"{s['model_id']!r} 不一致，报告不可与构建时基线直接比较，"
                "建议重跑回归集")

        saved = self.storage.save_report(result)
        return {"status": "ok", "report": saved}

    # ---- 报告 ----
    def list_reports(self, *, set_id: Optional[str] = None,
                     page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        try:
            items, total = self.storage.list_reports(
                set_id=set_id, page=page, page_size=page_size)
            return {"status": "ok", "items": items, "total": total}
        except Exception as e:
            logger.warning("list_reports 失败: %s", e, exc_info=True)
            return {"status": "error", "message": f"查询回放报告失败: {e}"}

    def get_report(self, report_id: str) -> Dict[str, Any]:
        r = self.storage.get_report(report_id)
        if not r:
            return {"status": "error", "message": f"回放报告 {report_id} 不存在",
                    "code": "REPORT_NOT_FOUND_404"}
        return {"status": "ok", "report": r}

    # ---- writeback 侧道（ADR-088 D8：默认 off，异常绝不传播主路径） ----
    async def auto_replay_for_scope(self, scope_key: str) -> Optional[Dict[str, Any]]:
        """侧道入口：回放该 scope 最新回归集。无集 → no-op。异常向上抛由调用方吞。"""
        s = self.storage.latest_set_for_scope(scope_key)
        if not s:
            return None
        return await self.replay(s["id"])
