"""GapSignalEmitter —— 四类信号源的同步收敛点。

规则 14：兜底可观测。emitter 绝不 raise、绝不阻塞主响应；
异常 → logger.warning + 模块级 _emit_failures 计数（stats 暴露，重启归零）。
惰性导入 GapService 规避循环导入（resolver→emitter→service→candidate_store→resolver）。
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_emit_failures = 0
_service_singleton = None


def get_emit_failures() -> int:
    return _emit_failures


def _get_service():
    global _service_singleton
    if _service_singleton is None:
        from .gap_service import GapService
        _service_singleton = GapService()
    return _service_singleton


def report_gap_signal(source, expression: str, *,
                      workspace_id: Optional[str] = None,
                      domain_id: Optional[str] = None,
                      ref: Optional[str] = None,
                      detail: Optional[str] = None) -> None:
    """同步上报一条缺口信号。任何异常都被吞为 warning + 计数，绝不 raise。"""
    global _emit_failures
    try:
        svc = _get_service()
        svc.record_signal(
            source, expression, workspace_id=workspace_id,
            domain_id=domain_id, ref=ref, detail=detail,
        )
    except Exception as e:
        _emit_failures += 1
        logger.warning("缺口信号上报失败(gap emitter, source=%s): %s", source, e)
