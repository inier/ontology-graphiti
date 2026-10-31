"""Wiki 路由（薄装配层：只做参数绑定 + 调 service + 组装包络）。

10 个端点（SPEC-v2 §5 / openapi-v2.yaml）：
    GET    /api/v1/wiki/entries
    POST   /api/v1/wiki/entries
    GET    /api/v1/wiki/entries/{entry_id}
    PATCH  /api/v1/wiki/entries/{entry_id}
    DELETE /api/v1/wiki/entries/{entry_id}
    POST   /api/v1/wiki/entries/{entry_id}/publish
    GET    /api/v1/wiki/entries/{entry_id}/versions
    GET    /api/v1/wiki/entries/{entry_id}/references
    POST   /api/v1/wiki/sync/import
    POST   /api/v1/wiki/sync/export

纪律：本文件零业务逻辑（无 SQL、无状态判断）；错误统一由 ApiError 冒泡到全局处理器，
因此这里**没有** try/except 兜底，也没有 `detail=str(e)` 式的模糊文案（AC-56）。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from odap.common.envelope import envelope
from odap.biz.knowledge.governance.services.sync_service import SyncService
from odap.biz.knowledge.wiki.api.schemas import (
    DocsExportRequest,
    DocsImportRequest,
    WikiEntryCreate,
    WikiEntryUpdate,
)
from odap.biz.knowledge.wiki.services.citation_service import CitationService
from odap.biz.knowledge.wiki.services.entry_service import WikiEntryService
from odap.biz.knowledge.wiki.services.version_service import VersionService
from odap.infra.security.jwt_auth import get_current_user

router = APIRouter(prefix="/api/v1/wiki", tags=["LLM Wiki"])

_SERVICES: Dict[str, Any] = {}


def set_services(**services: Any) -> None:
    """注入服务实例（测试用；生产留空走默认构造）。"""
    _SERVICES.update(services)


def reset_services() -> None:
    _SERVICES.clear()


def _svc(name: str, factory):
    if name not in _SERVICES:
        _SERVICES[name] = factory()
    return _SERVICES[name]


def _entries() -> WikiEntryService:
    return _svc("entry", WikiEntryService)


def _versions() -> VersionService:
    return _svc("version", VersionService)


def _citations() -> CitationService:
    return _svc("citation", CitationService)


def _sync() -> SyncService:
    return _svc("sync", SyncService)


def _actor(user: Optional[dict]) -> str:
    payload = user or {}
    return str(payload.get("sub") or payload.get("user_id") or "")


@router.get("/entries")
async def list_entries(
    status: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _user=Depends(get_current_user),
):
    return envelope(_entries().list_entries(status=status, owner=owner, q=q,
                                            page=page, limit=limit))


@router.post("/entries", status_code=201)
async def create_entry(body: WikiEntryCreate, user=Depends(get_current_user)):
    entry = _entries().create(
        title=body.title,
        content=body.content,
        owner=body.owner,
        tags=body.tags,
        concept_refs=body.concept_refs,
        citations=body.citations,
        workspace_id=body.workspace_id,
        actor_id=_actor(user),
    )
    return envelope(entry.model_dump(mode="json"))


@router.get("/entries/{entry_id}")
async def get_entry(entry_id: str, _user=Depends(get_current_user)):
    return envelope(_entries().get(entry_id).model_dump(mode="json"))


@router.patch("/entries/{entry_id}")
async def update_entry(entry_id: str, body: WikiEntryUpdate, user=Depends(get_current_user)):
    patch = body.model_dump(exclude_unset=True, exclude={"version"})
    entry = _entries().update(
        entry_id,
        patch=patch,
        expected_version=body.version,
        actor_id=_actor(user),
    )
    return envelope(entry.model_dump(mode="json"))


@router.delete("/entries/{entry_id}")
async def archive_entry(entry_id: str, user=Depends(get_current_user)):
    entry = _entries().archive(entry_id, actor_id=_actor(user))
    return envelope({"id": entry.id, "status": entry.status.value})


@router.post("/entries/{entry_id}/publish")
async def publish_entry(entry_id: str, user=Depends(get_current_user)):
    entry = _entries().publish(entry_id, actor_id=_actor(user))
    return envelope(entry.model_dump(mode="json"))


@router.get("/entries/{entry_id}/versions")
async def list_versions(entry_id: str, _user=Depends(get_current_user)):
    _entries().get(entry_id)  # 404 语义复用条目存在性校验
    return envelope(_versions().list_versions(entry_id))


@router.get("/entries/{entry_id}/references")
async def get_references(entry_id: str, _user=Depends(get_current_user)):
    return envelope(_citations().build_graph(entry_id).model_dump(mode="json"))


@router.post("/sync/import", status_code=201)
async def import_from_repo(body: DocsImportRequest, user=Depends(get_current_user)):
    return envelope(_sync().import_from_repo(body.source_ref, actor_id=_actor(user)))


@router.post("/sync/export")
async def export_to_repo(body: DocsExportRequest, user=Depends(get_current_user)):
    return envelope(
        _sync().export_to_repo(
            entry_id=body.entry_id,
            target_path=body.target_path,
            approval_id=body.approval_id,
            user=user if isinstance(user, dict) else {},
        )
    )
