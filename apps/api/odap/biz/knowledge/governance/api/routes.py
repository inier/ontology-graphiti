"""文档治理路由（薄装配层）。

5 个端点（SPEC-v2 §5 / openapi-v2.yaml）：
    GET  /api/v1/docs/governance/documents
    GET  /api/v1/docs/governance/documents/{doc_id}
    POST /api/v1/docs/governance/documents/{doc_id}/supersede
    POST /api/v1/docs/governance/verify
    GET  /api/v1/docs/governance/dedupe
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from odap.common.envelope import envelope
from odap.biz.knowledge.governance.api.schemas import SupersedeRequest
from odap.biz.knowledge.governance.services.doc_service import DocService
from odap.biz.knowledge.governance.services.supersede_service import SupersedeService
from odap.biz.knowledge.governance.services.verify_service import VerifyService
from odap.biz.knowledge.wiki.services.dedupe_service import DedupeService
from odap.infra.security.jwt_auth import get_current_user

router = APIRouter(prefix="/api/v1/docs/governance", tags=["Doc Governance"])

_SERVICES: Dict[str, Any] = {}


def set_services(**services: Any) -> None:
    _SERVICES.update(services)


def reset_services() -> None:
    _SERVICES.clear()


def _svc(name: str, factory):
    if name not in _SERVICES:
        _SERVICES[name] = factory()
    return _SERVICES[name]


@router.get("/documents")
async def list_documents(
    status: Optional[str] = Query(None),
    stale: bool = Query(False),
    no_owner: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _user=Depends(get_current_user),
):
    service: DocService = _svc("doc", DocService)
    return envelope(service.list_documents(
        status=status, stale=stale, no_owner=no_owner, page=page, limit=limit
    ))


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, _user=Depends(get_current_user)):
    service: DocService = _svc("doc", DocService)
    return envelope(service.get_document(doc_id))


@router.post("/documents/{doc_id}/supersede")
async def supersede_document(doc_id: str, body: SupersedeRequest,
                             _user=Depends(get_current_user)):
    service: SupersedeService = _svc("supersede", SupersedeService)
    doc = service.supersede(doc_id, body.superseded_by)
    payload = doc.model_dump(mode="json")
    payload.pop("content", None)
    return envelope(payload)


@router.post("/verify")
async def verify_governance(_user=Depends(get_current_user)):
    service: VerifyService = _svc("verify", VerifyService)
    report = service.run()
    return envelope(report.model_dump(mode="json", by_alias=True))


@router.get("/dedupe")
async def list_dedupe_candidates(
    threshold: float = Query(0.9, ge=0.0, le=1.0),
    _user=Depends(get_current_user),
):
    service: DedupeService = _svc("dedupe", DedupeService)
    return envelope([c.model_dump(mode="json") for c in service.list_candidates(threshold)])
