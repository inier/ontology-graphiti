"""knowledge.wiki 对外公共门面（C3 同类纪律：跨域只经 public）。

外部（governance、其他 biz 域、web）**只应**从本模块取 wiki 能力：

    from odap.biz.knowledge.wiki.public import get_entry_service

门面只暴露 service 工厂与领域模型，不暴露 repository —— 存储是实现细节。
"""

from __future__ import annotations

from typing import Optional

from odap.biz.knowledge.wiki.models.entry import (
    ReferenceGraph,
    WikiEntry,
    WikiEntryPage,
    WikiVersion,
)
from odap.biz.knowledge.wiki.repositories.citation_repo import WikiCitationRepository
from odap.biz.knowledge.wiki.repositories.entry_repo import WikiEntryRepository
from odap.biz.knowledge.wiki.services.citation_service import (
    CitationService,
    normalize_ref,
    parse_citations,
    ref_targets_entry,
)
from odap.biz.knowledge.wiki.services.dedupe_service import DedupeService
from odap.biz.knowledge.wiki.services.entry_service import WikiEntryService
from odap.biz.knowledge.wiki.services.version_service import VersionService


def get_entry_service(db_path: Optional[str] = None) -> WikiEntryService:
    return WikiEntryService(db_path=db_path)


def get_version_service(db_path: Optional[str] = None) -> VersionService:
    return VersionService(db_path=db_path)


def get_citation_service(db_path: Optional[str] = None) -> CitationService:
    return CitationService(db_path=db_path)


def get_dedupe_service(db_path: Optional[str] = None) -> DedupeService:
    return DedupeService(db_path=db_path)


def get_entry_repository(db_path: Optional[str] = None) -> WikiEntryRepository:
    """供同域（governance）编排使用；跨域消费者请改用 service。"""
    return WikiEntryRepository(db_path=db_path)


def get_citation_repository(db_path: Optional[str] = None) -> WikiCitationRepository:
    return WikiCitationRepository(db_path=db_path)


__all__ = [
    "WikiEntry",
    "WikiVersion",
    "WikiEntryPage",
    "ReferenceGraph",
    "WikiEntryService",
    "VersionService",
    "CitationService",
    "DedupeService",
    "get_entry_service",
    "get_version_service",
    "get_citation_service",
    "get_dedupe_service",
    "get_entry_repository",
    "get_citation_repository",
    "normalize_ref",
    "ref_targets_entry",
    "parse_citations",
]
