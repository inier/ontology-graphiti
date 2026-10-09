"""RegressionSetBuilder —— 把缺口 occurrence 固化为不可变回归集（ADR-088 D3）。

缺口天然就是"曾经答不上的问题集"——现成 held-out 验证集，不另造数据。
固化后不随 gap 后续变化更新（报告即不可变证据）；同参数二次 build 生成新集。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..models.gap import make_scope_key
from ..storage.sqlite_gap_storage import SQLiteGapStorage
from .runner import current_model_fingerprint
from .storage import SQLiteGapRegressionStorage

logger = logging.getLogger(__name__)


class RegressionSetBuilder:
    def __init__(self, gap_storage: Optional[SQLiteGapStorage] = None,
                 storage: Optional[SQLiteGapRegressionStorage] = None):
        self.gap_storage = gap_storage or SQLiteGapStorage()
        self.storage = storage or SQLiteGapRegressionStorage()

    def build(self, *, status: Optional[str] = None,
              workspace_id: Optional[str] = None,
              domain_id: Optional[str] = None,
              min_heat: int = 1) -> Dict[str, Any]:
        """按 scope + 过滤条件固化回归集。cases = [{query, expression, gap_id, source}]。

        query 取 expression 原文（缺口捕获的就是用户问出的词/问题原文）；
        source 取该缺口计数最高的信号源（真实记录，无推断）。
        """
        try:
            cases, gap_ids = [], []
            page = 1
            while True:
                items, total = self.gap_storage.list_gaps(
                    status=status, workspace_id=workspace_id,
                    page=page, page_size=200,
                )
                for g in items:
                    if min_heat and g.get("heat", 0) < min_heat:
                        continue
                    if domain_id and g.get("domain_id") != domain_id:
                        continue
                    cases.append({
                        "query": g["expression"],
                        "expression": g["expression"],
                        "gap_id": g["id"],
                        "source": self._dominant_source(g),
                    })
                    gap_ids.append(g["id"])
                if page * 200 >= total:
                    break
                page += 1

            fp = current_model_fingerprint()
            now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            name = f"gap-regression-{now}-{workspace_id or 'all'}"
            s = self.storage.save_set({
                "name": name,
                "scope_key": make_scope_key(workspace_id, domain_id),
                "cases": cases,
                "source_gap_ids": gap_ids,
                "model_id": fp["model_id"],
            })
            return {"status": "ok", "set_id": s["id"], "set": s,
                    "case_count": s["case_count"]}
        except Exception as e:  # 规则 14：显式失败
            logger.warning("构建回归集失败: %s", e, exc_info=True)
            return {"status": "error", "message": f"构建回归集失败: {e}"}

    @staticmethod
    def _dominant_source(gap: Dict[str, Any]) -> str:
        counts = gap.get("source_counts_json") or {}
        if not counts:
            return ""
        return max(counts.items(), key=lambda kv: kv[1])[0]
