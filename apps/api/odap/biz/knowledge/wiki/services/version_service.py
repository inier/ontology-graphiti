"""版本快照服务（F1，AC-05）。

职责：把「当前条目状态」冻结为一条不可变 `wiki_versions` 记录。
快照只追加，不提供修改/删除入口（AC-07 保留全部版本）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from odap.common.ids import new_doc_id
from odap.biz.knowledge.util import now_iso
from odap.biz.knowledge.wiki.models.entry import WikiEntry, WikiVersion
from odap.biz.knowledge.wiki.repositories.version_repo import WikiVersionRepository


class VersionService:
    """版本历史服务。"""

    def __init__(self, version_repo: Optional[WikiVersionRepository] = None,
                 db_path: Optional[str] = None) -> None:
        self.repo = version_repo or WikiVersionRepository(db_path)

    def append_snapshot(
        self, entry: WikiEntry, *, author_id: str = "", change_note: str = ""
    ) -> WikiVersion:
        """为条目写一条版本快照（content / content_hash / version 取自当前条目）。"""
        snapshot = WikiVersion(
            id=new_doc_id("ver"),
            entry_id=entry.id,
            version=entry.version,
            content=entry.content,
            content_hash=entry.content_hash,
            author_id=author_id or entry.owner,
            change_note=change_note,
            created_at=now_iso(),
        )
        self.repo.append(snapshot)
        return snapshot

    def list_versions(self, entry_id: str) -> List[Dict[str, object]]:
        """AC-05：按 created_at DESC 返回全部快照，含 change_note。"""
        return [v.model_dump(mode="json") for v in self.repo.list_by_entry(entry_id)]

    def count(self, entry_id: str) -> int:
        return self.repo.count_by_entry(entry_id)


__all__ = ["VersionService"]
