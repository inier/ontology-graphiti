"""supersede 链服务（F2，AC-10）。

不变量（AC-10 逐字）：
    标记 A 被 B 取代后 ——
      A.status = superseded
      A.superseded_by = B
      B.supersedes 含 A
      且 **不得删除 A**（真相源链完整可追溯）

额外护栏（真实业务必需）：
- A 不能取代自己（DOC_SUPERSEDE_SELF）。
- B 必须存在且不是已归档（DOC_SUPERSEDE_TARGET_INVALID）。
- 链上不得成环（DOC_SUPERSEDE_CYCLE）：沿 B.superseded_by 向上追溯若回到 A 即拒绝。

若被取代文档通过 `source_ref` 映射到 wiki 条目，则同步条目侧 superseded 标记，
保持「统一纳管模型」两侧一致（SPEC-v2 §6 关联说明）。
"""

from __future__ import annotations

from typing import Optional

from odap.common import api_errors as E
from odap.common.api_errors import ApiError
from odap.biz.knowledge.governance.models.doc import GovernedDoc
from odap.biz.knowledge.governance.repositories.doc_repo import GovernedDocRepository
from odap.biz.knowledge.models.common import DocStatus
from odap.biz.knowledge.util import now_iso
from odap.biz.knowledge.wiki.repositories.entry_repo import WikiEntryRepository

_MAX_CHAIN_HOPS = 64


class SupersedeService:
    """取代关系编排。"""

    def __init__(
        self,
        doc_repo: Optional[GovernedDocRepository] = None,
        entry_repo: Optional[WikiEntryRepository] = None,
        db_path: Optional[str] = None,
    ) -> None:
        self.docs = doc_repo or GovernedDocRepository(db_path)
        self.entries = entry_repo or WikiEntryRepository(db_path)

    def supersede(self, doc_id: str, superseded_by: str) -> GovernedDoc:
        if not (superseded_by or "").strip():
            raise ApiError(
                E.DOC_SUPERSEDE_TARGET_INVALID, "superseded_by 不能为空", status_code=400,
                detail={"doc_id": doc_id},
            )
        target_id = superseded_by.strip()
        if target_id == doc_id:
            raise ApiError(
                E.DOC_SUPERSEDE_SELF, "文档不能取代自身", status_code=400,
                detail={"doc_id": doc_id},
            )

        old_doc = self._require(doc_id)
        new_doc = self._require(target_id)
        if new_doc.status == DocStatus.ARCHIVED:
            raise ApiError(
                E.DOC_SUPERSEDE_TARGET_INVALID,
                f"目标文档 {target_id} 已归档，不能作为替代者（canonical）",
                status_code=400, detail={"doc_id": doc_id, "target": target_id},
            )
        self._assert_no_cycle(doc_id, new_doc)

        ts = now_iso()
        # 1) A：置 superseded + 指向 B
        self.docs.update(
            doc_id,
            {
                "status": DocStatus.SUPERSEDED.value,
                "superseded_by": target_id,
                "updated_at": ts,
            },
        )
        # 2) B：反向记录 supersedes（去重、保持稳定顺序）
        supersedes = list(new_doc.supersedes)
        if doc_id not in supersedes:
            supersedes.append(doc_id)
        self.docs.update(target_id, {"supersedes": supersedes, "updated_at": ts})

        # 3) 统一纳管模型：wiki 条目侧镜像（source_ref ↔ entry 双向映射）
        self._mirror_to_entry(old_doc, new_doc)

        return self._require(doc_id)

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _require(self, doc_id: str) -> GovernedDoc:
        doc = self.docs.get(doc_id)
        if doc is None:
            raise ApiError(
                E.DOC_NOT_FOUND, f"纳管文档不存在：{doc_id}", status_code=404,
                detail={"doc_id": doc_id},
            )
        return doc

    def _assert_no_cycle(self, origin_id: str, new_doc: GovernedDoc) -> None:
        """沿 new_doc 的 superseded_by 链上溯，若回到 origin 即成环。"""
        seen = {new_doc.id}
        current = new_doc
        for _ in range(_MAX_CHAIN_HOPS):
            next_id = current.superseded_by
            if not next_id:
                return
            if next_id == origin_id:
                raise ApiError(
                    E.DOC_SUPERSEDE_CYCLE,
                    f"取代关系会成环：{origin_id} → {new_doc.id} → … → {origin_id}",
                    status_code=409,
                    detail={"origin": origin_id, "target": new_doc.id, "chain": sorted(seen)},
                )
            if next_id in seen:
                raise ApiError(
                    E.DOC_SUPERSEDE_CYCLE,
                    f"目标文档所在取代链已存在环（重复节点 {next_id}），拒绝写入",
                    status_code=409, detail={"target": new_doc.id, "chain": sorted(seen)},
                )
            seen.add(next_id)
            current = self._require(next_id)
        raise ApiError(
            E.DOC_SUPERSEDE_CYCLE,
            f"取代链超过 {_MAX_CHAIN_HOPS} 跳，疑似脏数据，拒绝写入",
            status_code=409, detail={"target": new_doc.id},
        )

    def _mirror_to_entry(self, old_doc: GovernedDoc, new_doc: GovernedDoc) -> None:
        """把 docs 侧的 supersede 结果镜像到同 source_ref 的 wiki 条目（若有）。"""
        ts = now_iso()
        old_entry = None
        if old_doc.source_ref:
            old_entry = self.entries.get_by_source_ref(old_doc.source_ref)
        if old_entry is not None:
            new_entry = (
                self.entries.get_by_source_ref(new_doc.source_ref)
                if new_doc.source_ref else None
            )
            target_entry_id = new_entry.id if new_entry else new_doc.id
            self.entries.update(
                old_entry.id,
                {
                    "status": DocStatus.SUPERSEDED.value,
                    "superseded_by": target_entry_id,
                    "updated_at": ts,
                },
            )
            if new_entry is not None:
                supersedes = list(new_entry.supersedes)
                if old_entry.id not in supersedes:
                    supersedes.append(old_entry.id)
                self.entries.update(
                    new_entry.id, {"supersedes": supersedes, "updated_at": ts}
                )


__all__ = ["SupersedeService"]
