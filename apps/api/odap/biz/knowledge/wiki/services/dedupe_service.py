"""去重合并候选（F2，AC-14）。

判重口径（ARCHITECTURE-v2 §5.3）：
1. `content_hash` 完全相同 → 必然重复，相似度 **1.0**（确定性，无需阈值）。
2. embedding 相似度 → 提示合并候选（需要向量库；本轮**未接入**，
   因此在代码里显式不产出 `high_similarity` 候选，禁止用估算值伪造相似度）。

候选合并范围：wiki 条目 + 仓库纳管文档（统一纳管视角，AC-09）。
`canonical_id` 取组内最早创建的一条（可追溯的「真相源」）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from odap.biz.knowledge.governance.models.doc import DedupeCandidate
from odap.biz.knowledge.governance.repositories.doc_repo import GovernedDocRepository
from odap.biz.knowledge.util import collapse_same_source
from odap.biz.knowledge.wiki.repositories.entry_repo import WikiEntryRepository

# TODO(SPEC-v2 F2 / AC-14): embedding 相似度候选（high_similarity）待接入向量检索后实现，
# 本轮只做 content_hash 精确判重，避免编造相似度数值。


class DedupeService:
    """去重候选服务。"""

    def __init__(
        self,
        entry_repo: Optional[WikiEntryRepository] = None,
        doc_repo: Optional[GovernedDocRepository] = None,
        db_path: Optional[str] = None,
    ) -> None:
        self.entries = entry_repo or WikiEntryRepository(db_path)
        self.docs = doc_repo or GovernedDocRepository(db_path)

    def _collect(self) -> Dict[str, List[Dict[str, str]]]:
        """按 content_hash 归组（hash → [{id, created_at, source, source_ref}]）。"""
        groups: Dict[str, List[Dict[str, str]]] = {}
        for entry in self.entries.list_all():
            if not entry.content_hash:
                continue
            groups.setdefault(entry.content_hash, []).append(
                {"id": entry.id, "created_at": entry.created_at, "source": "wiki",
                 "source_ref": entry.source_ref or ""}
            )
        for doc in self.docs.list_all():
            if not doc.content_hash:
                continue
            groups.setdefault(doc.content_hash, []).append(
                {"id": doc.id, "created_at": doc.created_at or "", "source": "repo",
                 "source_ref": doc.source_ref or ""}
            )
        return groups

    def list_candidates(self, threshold: float = 0.9) -> List[DedupeCandidate]:
        """返回合并候选；`threshold` 对精确同哈希无影响（相似度恒为 1.0）。"""
        if threshold < 0 or threshold > 1:
            raise ValueError(f"threshold 必须在 [0,1]：{threshold}")

        candidates: List[DedupeCandidate] = []
        for content_hash, members in self._collect().items():
            # 同一 source_ref 的 wiki/纳管文档是同一份文档的两个投影，不算「两份重复文档」
            distinct = collapse_same_source(members)
            if len(distinct) < 2:
                continue
            similarity = 1.0
            if similarity < threshold:
                continue
            candidates.append(
                DedupeCandidate(
                    doc_ids=[m["id"] for m in distinct],
                    similarity=similarity,
                    reason="same_hash",
                    canonical_id=distinct[0]["id"],
                )
            )
        candidates.sort(key=lambda c: (-len(c.doc_ids), c.doc_ids[0]))
        return candidates


__all__ = ["DedupeService"]
