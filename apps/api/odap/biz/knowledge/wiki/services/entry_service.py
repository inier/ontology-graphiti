"""Wiki 条目服务（F1）：CRUD + 发布状态机 + 乐观锁 + 判重。

设计纪律：
- **不 import fastapi**（service 不感知 HTTP）；业务拒绝统一抛 `ApiError`。
- 只经 Repository 访问存储；事务编排在本层。
- 每条拒绝都带具体 `error_code`（AC-56 禁止模糊文案）。

覆盖验收：
    AC-01 创建返回 ULID + version=0.1.0
    AC-02 缺 owner → 400 WIKI_OWNER_REQUIRED
    AC-03 发布置 published + 写版本快照
    AC-04 content_hash 重复 → 409 WIKI_DUPLICATE_CONTENT（附冲突条目 id）
    AC-05 版本历史（version_service）
    AC-07 删除 = archived，保留版本
    AC-08 乐观锁 version 不一致 → 409 WIKI_VERSION_CONFLICT
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from odap.common import api_errors as E
from odap.common.api_errors import ApiError
from odap.common.ids import content_hash, new_doc_id
from odap.biz.knowledge.models.common import Citation, DocStatus
from odap.biz.knowledge.util import now_iso
from odap.biz.knowledge.wiki.models.entry import WikiEntry
from odap.biz.knowledge.wiki.repositories.citation_repo import WikiCitationRepository
from odap.biz.knowledge.wiki.repositories.entry_repo import WikiEntryRepository
from odap.biz.knowledge.wiki.repositories.version_repo import WikiVersionRepository
from odap.biz.knowledge.wiki.services.entry_rules import (
    INITIAL_VERSION,
    PUBLISHABLE,
    bump_patch,
    require_content,
    require_owner,
    require_title,
    transition,
)
from odap.biz.knowledge.wiki.services.version_service import VersionService


class WikiEntryService:
    """条目编排服务。"""

    def __init__(
        self,
        entry_repo: Optional[WikiEntryRepository] = None,
        version_repo: Optional[WikiVersionRepository] = None,
        citation_repo: Optional[WikiCitationRepository] = None,
        db_path: Optional[str] = None,
    ) -> None:
        self.entries = entry_repo or WikiEntryRepository(db_path)
        self.versions = version_repo or WikiVersionRepository(db_path)
        self.citations = citation_repo or WikiCitationRepository(db_path)
        self._version_service = VersionService(self.versions)

    # ── AC-01 / AC-02 ─────────────────────────────────────────────────────
    def create(
        self,
        *,
        title: Optional[str],
        content: Optional[str],
        owner: Optional[str],
        tags: Optional[List[str]] = None,
        concept_refs: Optional[List[str]] = None,
        citations: Optional[List[Citation]] = None,
        workspace_id: str = "",
        actor_id: str = "",
    ) -> WikiEntry:
        owner_id = require_owner(owner)
        title_value = require_title(title)
        content_value = require_content(content)

        ts = now_iso()
        entry = WikiEntry(
            id=new_doc_id("doc"),
            title=title_value,
            content=content_value,
            status=DocStatus.DRAFT,
            owner=owner_id,
            version=INITIAL_VERSION,
            content_hash=content_hash(content_value),
            tags=list(tags or []),
            concept_refs=list(concept_refs or []),
            workspace_id=workspace_id or "",
            created_at=ts,
            updated_at=ts,
        )
        self.entries.insert(entry)

        # 初始版本快照（draft 也有基线，便于差异化对比与 AC-05 一致性）
        self._version_service.append_snapshot(
            entry, author_id=actor_id or owner_id, change_note="create"
        )
        if citations:
            self._write_citations(entry.id, citations)
        return self.get(entry.id)

    # ── 读 ────────────────────────────────────────────────────────────────
    def get(self, entry_id: str) -> WikiEntry:
        entry = self.entries.get(entry_id)
        if entry is None:
            raise ApiError(
                E.WIKI_ENTRY_NOT_FOUND, f"Wiki 条目不存在：{entry_id}", status_code=404,
                detail={"entry_id": entry_id},
            )
        entry.citations = self.citations.list_outgoing(entry_id)
        return entry

    def list_entries(
        self,
        *,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        if status and status not in {s.value for s in DocStatus}:
            raise ApiError(
                E.WIKI_INVALID_STATUS_TRANSITION, f"非法状态过滤值：{status}", status_code=400,
                detail={"status": status, "allowed": [s.value for s in DocStatus]},
            )
        items, total = self.entries.list_entries(
            status=status, owner=owner, q=q, page=page, limit=limit
        )
        return {
            "items": [i.model_dump(mode="json") for i in items],
            "total": total,
            "page": page,
            "limit": limit,
            "hasMore": page * limit < total,
        }

    # ── AC-08 乐观锁 + 部分更新 ────────────────────────────────────────────
    def update(
        self,
        entry_id: str,
        *,
        patch: Dict[str, Any],
        expected_version: Optional[str] = None,
        actor_id: str = "",
    ) -> WikiEntry:
        entry = self.get(entry_id)
        if entry.status == DocStatus.ARCHIVED:
            raise ApiError(
                E.WIKI_INVALID_STATUS_TRANSITION,
                "已归档条目不可编辑；请新建条目并在 citations 中引用原条目",
                status_code=409, detail={"entry_id": entry_id, "status": entry.status.value},
            )
        if expected_version is not None and expected_version != entry.version:
            raise ApiError(
                E.WIKI_VERSION_CONFLICT,
                f"条目已被他人修改：期望 version={expected_version}，服务端为 {entry.version}",
                status_code=409,
                detail={"expected": expected_version, "actual": entry.version},
            )

        fields: Dict[str, Any] = {"updated_at": now_iso()}
        change_notes: List[str] = []

        if "title" in patch and patch["title"] is not None:
            fields["title"] = require_title(patch["title"])
            change_notes.append("title")
        if "owner" in patch:
            fields["owner_id"] = require_owner(patch["owner"])
            change_notes.append("owner")
        if "tags" in patch and patch["tags"] is not None:
            fields["tags"] = list(patch["tags"])
            change_notes.append("tags")
        if "concept_refs" in patch and patch["concept_refs"] is not None:
            fields["concept_refs"] = list(patch["concept_refs"])
            change_notes.append("concept_refs")
        if "status" in patch and patch["status"] is not None:
            fields["status"] = transition(entry.status, DocStatus(patch["status"])).value
            change_notes.append(f"status:{fields['status']}")

        content_changed = (
            "content" in patch and patch["content"] is not None
            and patch["content"] != entry.content
        )
        if content_changed:
            new_content = require_content(patch["content"])
            fields["content"] = new_content
            fields["content_hash"] = content_hash(new_content)
            fields["version"] = bump_patch(entry.version)
            change_notes.append("content")
        elif "content" in patch and patch["content"] is not None:
            # 内容未变化：不递增版本，但仍需显式拒绝空正文
            require_content(patch["content"])

        self.entries.update(entry_id, fields)
        updated = self.get(entry_id)

        if content_changed:
            self._version_service.append_snapshot(
                updated, author_id=actor_id or updated.owner,
                change_note=str(patch.get("change_note") or "update content"),
            )
        if "citations" in patch and patch["citations"] is not None:
            self._write_citations(entry_id, list(patch["citations"]))
            updated = self.get(entry_id)
        return updated

    # ── AC-03 / AC-04 发布 ─────────────────────────────────────────────────
    def publish(self, entry_id: str, *, actor_id: str = "") -> WikiEntry:
        entry = self.get(entry_id)
        if entry.status == DocStatus.ARCHIVED:
            raise ApiError(
                E.WIKI_INVALID_STATUS_TRANSITION, "已归档条目不可发布", status_code=409,
                detail={"entry_id": entry_id, "status": entry.status.value},
            )
        if entry.status not in PUBLISHABLE:
            raise ApiError(
                E.WIKI_INVALID_STATUS_TRANSITION,
                f"当前状态 {entry.status.value} 不可发布", status_code=409,
                detail={"entry_id": entry_id, "status": entry.status.value},
            )
        # 发布前再校验一次 owner（历史数据可能为空，AC-02/AC-03 双保险）
        require_owner(entry.owner)
        require_content(entry.content)

        conflicts = self.entries.find_published_by_hash(entry.content_hash, exclude_id=entry_id)
        if conflicts:
            raise ApiError(
                E.WIKI_DUPLICATE_CONTENT,
                f"内容哈希与已发布条目重复（{entry.content_hash}），拒绝发布；"
                f"请合并或改写后重试",
                status_code=409,
                detail={
                    "content_hash": entry.content_hash,
                    "conflicting_entry_id": conflicts[0].id,
                    "conflicting_entry_ids": [c.id for c in conflicts],
                },
            )

        ts = now_iso()
        self.entries.update(
            entry_id,
            {"status": DocStatus.PUBLISHED.value, "last_verified": ts[:10], "updated_at": ts},
        )
        published = self.get(entry_id)
        self._version_service.append_snapshot(
            published, author_id=actor_id or published.owner, change_note="publish"
        )
        return published

    # ── AC-07 软删除 ───────────────────────────────────────────────────────
    def archive(self, entry_id: str, *, actor_id: str = "") -> WikiEntry:
        entry = self.get(entry_id)
        if entry.status != DocStatus.ARCHIVED:
            self.entries.update(
                entry_id,
                {"status": DocStatus.ARCHIVED.value, "updated_at": now_iso()},
            )
            entry = self.get(entry_id)
            self._version_service.append_snapshot(
                entry, author_id=actor_id or entry.owner, change_note="archive"
            )
        # 显式声明：版本数与引用一律保留（禁止物理删除，AC-07）
        return entry

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _write_citations(self, entry_id: str, citations: List[Any]) -> None:
        """写入引用集合；支持 `Citation` 与等价的 dict（统一走 parse_citations 校验）。"""
        from odap.biz.knowledge.wiki.services.citation_service import parse_citations

        ts = now_iso()
        rows = [
            {
                "id": new_doc_id("cite"),
                "kind": c.kind.value,
                "ref": c.ref,
                "created_at": ts,
            }
            for c in parse_citations(list(citations))
        ]
        self.citations.replace_for_entry(entry_id, rows)


__all__ = ["WikiEntryService", "INITIAL_VERSION", "bump_patch", "now_iso"]
