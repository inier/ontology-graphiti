"""
ColdStartService - 服务编排层
- 返回 Dict[str, Any]（AGENTS.md 规则 2）
- 错误格式: {"status": "error", "message": "..."}
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..impl import ColdStartBootstrap
from ..models import Industry
from ..models.template_loader import list_industries as _list_industries


class ColdStartService:
    """冷启动服务编排层"""

    def __init__(self, bootstrap: ColdStartBootstrap | None = None):
        self.bootstrap = bootstrap or ColdStartBootstrap()

    def list_available_industries(self) -> Dict[str, Any]:
        try:
            industries = _list_industries()
            return {"industries": industries, "count": len(industries)}
        except Exception as exc:
            return {"status": "error", "message": f"list_industries failed: {exc}"}

    def bootstrap_workspace(
        self,
        workspace_id: str,
        industry: str,
    ) -> Dict[str, Any]:
        """触发冷启动（自动检测 + 引导）"""
        try:
            # 验证 industry 合法
            valid = {i.value for i in Industry}
            if industry not in valid and industry not in _list_industries():
                return {
                    "status": "error",
                    "message": f"unknown industry: {industry}. Available: {sorted(valid)}",
                }
            return self.bootstrap.bootstrap_if_needed(workspace_id, industry)
        except Exception as exc:
            return {"status": "error", "message": f"bootstrap failed: {exc}"}
