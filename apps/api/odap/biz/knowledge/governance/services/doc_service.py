"""纳管文档查询服务（F2，AC-09）。

AC-09 要求列表项必须返回 `owner / status / role / last_verified / superseded_by` 五字段。
文档详情额外带 `citations`（统一纳管模型下，引用挂在同 source_ref 的 wiki 条目上）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from odap.common import api_errors as E
from odap.common.api_errors import ApiError
from odap.biz.knowledge.governance.models.doc import GovernedDoc
from odap.biz.knowledge.governance.repositories.doc_repo import GovernedDocRepository
from odap.biz.knowledge.util import days_between, today_iso
from odap.biz.knowledge.wiki.repositories.citation_repo import WikiCitationRepository
from odap.biz.knowledge.wiki.repositories.entry_repo import WikiEntryRepository

STALE_DAYS = 180


class DocService:
    """纳管文档查询编排。"""

    def __init__(
        self,
        doc_repo: Optional[GovernedDocRepository] = None,
        entry_repo: Optional[WikiEntryRepository] = None,
        citation_repo: Optional[WikiCitationRepository] = None,
        db_path: Optional[str] = None,
        today: Optional[str] = None,
    ) -> None:
        self.docs = doc_repo or GovernedDocRepository(db_path)
        self.entries = entry_repo or WikiEntryRepository(db_path)
        self.citations = citation_repo or WikiCitationRepository(db_path)
        self.today = today or today_iso()

    def list_documents(
        self,
        *,
        status: Optional[str] = None,
        stale: bool = False,
        no_owner: bool = False,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        stale_before = None
        if stale:
            stale_before = _shift_days(self.today, -STALE_DAYS)
        items, total = self.docs.list_docs(
            status=status, stale_before=stale_before, no_owner=no_owner,
            page=page, limit=limit,
        )
        return {
            "items": [self._dump(doc) for doc in items],
            "total": total,
            "page": page,
            "limit": limit,
            "hasMore": page * limit < total,
        }

    def get_document(self, doc_id: str) -> Dict[str, Any]:
        doc = self.docs.get(doc_id)
        if doc is None:
            raise ApiError(
                E.DOC_NOT_FOUND, f"纳管文档不存在：{doc_id}", status_code=404,
                detail={"doc_id": doc_id},
            )
        payload = self._dump(doc)
        payload["citations"] = [
            c.model_dump(mode="json") for c in self._entry_citations(doc)
        ]
        return payload

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _entry_citations(self, doc: GovernedDoc) -> List[Any]:
        if not doc.source_ref:
            return []
        entry = self.entries.get_by_source_ref(doc.source_ref)
        if entry is None:
            return []
        return self.citations.list_outgoing(entry.id)

    def _dump(self, doc: GovernedDoc) -> Dict[str, Any]:
        payload = doc.model_dump(mode="json")
        payload.pop("content", None)  # 列表/详情接口不返回全量正文（体积控制）
        payload["stale"] = self._is_stale(doc)
        return payload

    def _is_stale(self, doc: GovernedDoc) -> bool:
        if not doc.last_verified:
            return False
        try:
            return days_between(doc.last_verified, self.today) > STALE_DAYS
        except ValueError:
            return True


def _shift_days(date_str: str, delta: int) -> str:
    from datetime import datetime, timedelta

    base = datetime.strptime(date_str[:10], "%Y-%m-%d")
    return (base + timedelta(days=delta)).date().isoformat()


__all__ = ["DocService", "STALE_DAYS"]
