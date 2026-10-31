"""knowledge.governance 对外公共门面。

暴露：纳管文档查询 / 取代链 / 机械校验 / 双向同步。
仓库文档治理脚本（scripts/verify_doc_governance.py）与路由层均经此入口，
避免外部直接依赖 services 内部路径。
"""

from __future__ import annotations

from typing import Optional

from odap.biz.knowledge.governance.models.doc import (
    DedupeCandidate,
    GovernedDoc,
    GovernanceIssue,
    GovernanceIssueCode,
    GovernanceReport,
)
from odap.biz.knowledge.governance.repositories.doc_repo import GovernedDocRepository
from odap.biz.knowledge.governance.services.doc_service import DocService
from odap.biz.knowledge.governance.services.frontmatter import (
    parse_document,
    serialize_document,
)
from odap.biz.knowledge.governance.services.supersede_service import SupersedeService
from odap.biz.knowledge.governance.services.sync_service import SyncService
from odap.biz.knowledge.governance.services.verify_service import VerifyService


def get_doc_service(db_path: Optional[str] = None) -> DocService:
    return DocService(db_path=db_path)


def get_verify_service(db_path: Optional[str] = None) -> VerifyService:
    return VerifyService(db_path=db_path)


def get_supersede_service(db_path: Optional[str] = None) -> SupersedeService:
    return SupersedeService(db_path=db_path)


def get_sync_service(db_path: Optional[str] = None, approval_checker=None) -> SyncService:
    return SyncService(db_path=db_path, approval_checker=approval_checker)


def get_doc_repository(db_path: Optional[str] = None) -> GovernedDocRepository:
    return GovernedDocRepository(db_path=db_path)


__all__ = [
    "GovernedDoc",
    "GovernanceIssue",
    "GovernanceIssueCode",
    "GovernanceReport",
    "DedupeCandidate",
    "DocService",
    "VerifyService",
    "SupersedeService",
    "SyncService",
    "get_doc_service",
    "get_verify_service",
    "get_supersede_service",
    "get_sync_service",
    "get_doc_repository",
    "parse_document",
    "serialize_document",
]
