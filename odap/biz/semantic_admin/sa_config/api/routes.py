"""sa_config FastAPI 路由：/api/semantic-admin/config。

6 个端点：
  GET     /config?scope=<opt>              list_configs
  GET     /config/{scope}/{key}            get_config
  PUT     /config/{scope}/{key}            set_config   (body SetConfigRequest)
  DELETE  /config/{scope}/{key}            delete_config
  GET     /config/domain/{domain_code}     get_domain_semantic
  POST    /config/ensure-builtin           ensure_builtin_domains  (migration helper)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from odap.infra.security.jwt_auth import (
    get_current_user,
    verify_admin,
)

from ..services import SaConfigService, get_sa_config_service
from .schemas import (
    EnsureBuiltinResponse,
    SaConfigDeleteResponse,
    SaConfigEntryResponse,
    SaConfigListResponse,
    SetConfigRequest,
)

router = APIRouter(prefix="/api/semantic-admin/config", tags=["semantic-admin-config"])
_svc: Optional[SaConfigService] = None


def _svc_instance() -> SaConfigService:
    global _svc
    if _svc is None:
        _svc = get_sa_config_service()
    return _svc


@router.get("", response_model=SaConfigListResponse)
async def list_configs(
    scope: Optional[str] = Query(None, description="按 scope 过滤，缺省返回全部"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        r = _svc_instance().list_configs(scope)
        if r.get("status") == "error":
            raise HTTPException(status_code=400, detail=r.get("message"))
        items = [SaConfigEntryResponse(**e) for e in r.get("items", [])]
        return SaConfigListResponse(items=items, count=len(items))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{scope}/{config_key}", response_model=SaConfigEntryResponse)
async def get_config(
    scope: str,
    config_key: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        r = _svc_instance().get_config(scope, config_key, default=None)
        if r.get("status") == "error":
            raise HTTPException(status_code=400, detail=r.get("message"))
        value = r.get("config_value")
        if value is None:
            raise HTTPException(status_code=404, detail=f"{scope}/{config_key} 不存在")
        entry = {
            "id": f"{scope}::{config_key}",
            "scope": scope,
            "config_key": config_key,
            "config_value": value if isinstance(value, dict) else {"value": value},
            "updated_by": "system",
            "created_at": "",
            "updated_at": "",
        }
        return SaConfigEntryResponse(**entry)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{scope}/{config_key}", response_model=SaConfigEntryResponse)
async def set_config(
    scope: str,
    config_key: str,
    body: SetConfigRequest,
    admin_user: Dict[str, Any] = Depends(verify_admin),
):
    try:
        r = _svc_instance().set_config(
            scope, config_key, body.value, updated_by=body.updated_by or admin_user.get("id", "admin")
        )
        if r.get("status") == "error":
            raise HTTPException(status_code=400, detail=r.get("message"))
        return SaConfigEntryResponse(
            id=r.get("id", f"{scope}::{config_key}"),
            scope=r.get("scope", scope),
            config_key=r.get("config_key", config_key),
            config_value=r.get("config_value", {}),
            updated_by=r.get("updated_by", "system"),
            created_at=r.get("updated_at", ""),
            updated_at=r.get("updated_at", ""),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{scope}/{config_key}", response_model=SaConfigDeleteResponse)
async def delete_config(
    scope: str,
    config_key: str,
    admin_user: Dict[str, Any] = Depends(verify_admin),
):
    try:
        r = _svc_instance().delete_config(scope, config_key)
        if r.get("status") == "error":
            raise HTTPException(status_code=400, detail=r.get("message"))
        return SaConfigDeleteResponse(
            scope=scope, config_key=config_key, deleted=bool(r.get("deleted"))
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/domain/{domain_code}")
async def get_domain_semantic(
    domain_code: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        r = _svc_instance().get_domain_semantic(domain_code)
        if r.get("status") == "error":
            raise HTTPException(status_code=400, detail=r.get("message"))
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ensure-builtin", response_model=EnsureBuiltinResponse)
async def ensure_builtin_domains(
    force: bool = Body(False, embed=True),
    admin_user: Dict[str, Any] = Depends(verify_admin),
):
    try:
        r = _svc_instance().ensure_builtin_domains(force_overwrite=bool(force))
        if r.get("status") == "error":
            raise HTTPException(status_code=400, detail=r.get("message"))
        return EnsureBuiltinResponse(
            scopes=r.get("scopes", []),
            migrated=r.get("migrated", {}),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
