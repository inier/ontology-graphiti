"""extractor-mode 专用端点：/api/semantic-admin/extractor-mode（ADR-089 C-D11）。

GET  读取当前提取模式（显式配置 + 生效 mode + 可选集 + 描述）
PUT  切换提取模式（admin）→ 写 sa_config（scope=entity_extractor / key=mode）

专用端点存在意义：单点承载 available_modes / default_mode / 语义描述 / 校验；
前端不硬编码。底层存储复用既有 sa_config 动态配置底座。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from odap.biz.data.qa.pipeline.understanding.extractor_mode import (
    AVAILABLE_MODES,
    CONFIG_KEY,
    CONFIG_SCOPE,
    DEFAULT_MODE,
    MODE_DESCRIPTIONS,
    effective_mode_from,
)
from odap.infra.security.jwt_auth import get_current_user, verify_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/semantic-admin/extractor-mode",
                   tags=["semantic-admin-extractor-mode"])

# 测试注入点（生产保持 None → 用 sa_config 单例）
_svc_override: Optional[Any] = None


def _svc():
    if _svc_override is not None:
        return _svc_override
    from odap.biz.semantic_admin.sa_config.services import get_sa_config_service
    return get_sa_config_service()


def _read_explicit() -> Dict[str, Any]:
    """返回 {mode, updated_by, updated_at}；未配置 → mode=None。"""
    try:
        r = _svc().list_configs(CONFIG_SCOPE)
        for e in (r.get("items") or []):
            if e.get("config_key") == CONFIG_KEY:
                v = e.get("config_value")
                if isinstance(v, dict):
                    v = v.get("value")
                return {
                    "mode": v if isinstance(v, str) else None,
                    "updated_by": e.get("updated_by"),
                    "updated_at": e.get("updated_at"),
                }
    except Exception as e:  # 规则 14：可观测降级
        logger.warning("读取 extractor-mode 配置失败：%s", e)
    return {"mode": None, "updated_by": None, "updated_at": None}


def _snapshot() -> Dict[str, Any]:
    cur = _read_explicit()
    return {
        "status": "ok",
        "mode": cur["mode"],
        "effective_mode": effective_mode_from(cur["mode"]),
        "default_mode": DEFAULT_MODE,
        "available_modes": list(AVAILABLE_MODES),
        "descriptions": dict(MODE_DESCRIPTIONS),
        "updated_by": cur["updated_by"],
        "updated_at": cur["updated_at"],
    }


@router.get("")
async def get_extractor_mode(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        return _snapshot()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("")
async def set_extractor_mode(
    body: Dict[str, Any] = Body(...),
    admin_user: Dict[str, Any] = Depends(verify_admin),
):
    try:
        mode = body.get("mode")
        if mode not in AVAILABLE_MODES:
            raise HTTPException(
                status_code=400,
                detail=f"非法 mode: {mode!r}，合法值 {list(AVAILABLE_MODES)}",
            )
        updated_by = body.get("updated_by") or admin_user.get("id", "admin")
        r = _svc().set_config(
            CONFIG_SCOPE, CONFIG_KEY, {"value": mode}, updated_by=updated_by)
        if isinstance(r, dict) and r.get("status") == "error":
            raise HTTPException(status_code=400, detail=r.get("message"))
        return _snapshot()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
