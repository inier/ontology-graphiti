"""文档治理机械校验（F2，AC-11/12/13/14）。

五类检查（全部确定性、可复算，不含 LLM 判断）：
    DANGLING_REF    引用 ref 指向不存在的文档/条目 id（error，AC-11）
    MISSING_OWNER   纳管文档或条目 owner 为空（error，AC-12）
    ORPHAN_DOC      无任何出入引用且非索引文档（warning）
    STALE           last_verified 超过 180 天（warning，AC-13）
    DUPLICATE_HASH  content_hash 相同（warning，AC-14）

`pass_ = 无 error 级问题`。CLI 门禁（scripts/verify_doc_governance.py）据此返回非零退出码。

设计说明：wiki 条目与仓库纳管文档是同一纳管模型的两个投影（SPEC-v2 §6），
所以校验对象是**并集**；文档 id 与 source_ref 都算可解析目标。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from odap.biz.knowledge.governance.models.doc import (
    GovernanceIssue,
    GovernanceIssueCode,
    GovernanceReport,
)
from odap.biz.knowledge.governance.repositories.doc_repo import GovernedDocRepository
from odap.biz.knowledge.util import collapse_same_source, days_between, today_iso
from odap.biz.knowledge.wiki.repositories.citation_repo import WikiCitationRepository
from odap.biz.knowledge.wiki.repositories.entry_repo import WikiEntryRepository
from odap.biz.knowledge.wiki.services.citation_service import normalize_ref

STALE_DAYS = 180

#: 索引类文档不参与「孤立文档」判定（README / INDEX / BASELINE 天然无出入引用）
_INDEX_MARKERS = ("readme", "index", "baseline", "_index", "目录", "索引")


def _is_index_doc(title: str, source_ref: Optional[str]) -> bool:
    haystack = f"{title or ''} {source_ref or ''}".lower()
    return any(marker in haystack for marker in _INDEX_MARKERS)


class VerifyService:
    """治理校验服务。"""

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

    def run(self) -> GovernanceReport:
        docs = self.docs.list_all()
        entries = self.entries.list_all()
        citations = self.citations.list_all()

        known_ids: Set[str] = {d.id for d in docs} | {e.id for e in entries}
        known_refs: Set[str] = {
            normalize_ref(x) for x in
            ([d.source_ref for d in docs if d.source_ref] +
             [e.source_ref for e in entries if e.source_ref])
        }

        issues: List[GovernanceIssue] = []
        issues.extend(self._dangling(citations, known_ids, known_refs, entries))
        issues.extend(self._missing_owner(docs, entries))
        issues.extend(self._orphans(docs, entries, citations))
        issues.extend(self._stale(docs, entries))
        issues.extend(self._duplicates(docs, entries))

        counts: Dict[str, int] = {}
        for issue in issues:
            counts[issue.code] = counts.get(issue.code, 0) + 1
        errors = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")

        return GovernanceReport(
            checked=len(docs) + len(entries),
            issues=issues,
            counts=counts,
            pass_=errors == 0,
            errors=errors,
            warnings=warnings,
        )

    # ── AC-11 悬空引用 ─────────────────────────────────────────────────────
    def _dangling(self, citations, known_ids, known_refs, entries) -> List[GovernanceIssue]:
        entry_titles = {e.id: e.title for e in entries}
        issues: List[GovernanceIssue] = []
        for row in citations:
            kind = row.get("kind", "doc")
            # 只有文档类引用属于文档治理域；metric/tbox_node/graph_edge/opa_decision
            # 的可解析性由各自的域保证（溯源校验 scripts/verify_provenance.py 负责）。
            if kind not in ("doc", "entry", "wiki"):
                continue
            target = normalize_ref(row.get("ref", ""))
            if not target:
                issues.append(
                    GovernanceIssue(
                        code=GovernanceIssueCode.DANGLING_REF.value, severity="error",
                        doc_id=row.get("entry_id", ""),
                        detail=f"引用为空引用：kind={kind} ref={row.get('ref', '')!r}",
                    )
                )
                continue
            if target in known_ids or target in known_refs:
                continue
            issues.append(
                GovernanceIssue(
                    code=GovernanceIssueCode.DANGLING_REF.value,
                    severity="error",
                    doc_id=row.get("entry_id", ""),
                    detail=(
                        f"引用目标不存在：ref={row.get('ref', '')} → {target}"
                        f"（引用方：{entry_titles.get(row.get('entry_id', ''), '未知条目')}）"
                    ),
                )
            )
        return issues

    # ── AC-12 缺 owner ────────────────────────────────────────────────────
    def _missing_owner(self, docs, entries) -> List[GovernanceIssue]:
        issues: List[GovernanceIssue] = []
        for doc in docs:
            if not (doc.owner or "").strip():
                issues.append(
                    GovernanceIssue(
                        code=GovernanceIssueCode.MISSING_OWNER.value, severity="error",
                        doc_id=doc.id,
                        detail=f"文档《{doc.title}》缺少 owner（责任人），不合格",
                    )
                )
        for entry in entries:
            if not (entry.owner or "").strip():
                issues.append(
                    GovernanceIssue(
                        code=GovernanceIssueCode.MISSING_OWNER.value, severity="error",
                        doc_id=entry.id,
                        detail=f"Wiki 条目《{entry.title}》缺少 owner（责任人），不合格",
                    )
                )
        return issues

    # ── 孤立文档 ───────────────────────────────────────────────────────────
    def _orphans(self, docs, entries, citations) -> List[GovernanceIssue]:
        outgoing = {row.get("entry_id", "") for row in citations}
        incoming_refs = {normalize_ref(row.get("ref", "")) for row in citations}
        issues: List[GovernanceIssue] = []
        for doc in docs:
            if _is_index_doc(doc.title, doc.source_ref):
                continue
            if doc.id in outgoing:
                continue
            if doc.id in incoming_refs or (doc.source_ref and normalize_ref(doc.source_ref) in incoming_refs):
                continue
            issues.append(
                GovernanceIssue(
                    code=GovernanceIssueCode.ORPHAN_DOC.value, severity="warning",
                    doc_id=doc.id,
                    detail=f"文档《{doc.title}》无任何出入引用（孤立文档）",
                )
            )
        for entry in entries:
            if _is_index_doc(entry.title, entry.source_ref):
                continue
            if entry.id in outgoing:
                continue
            if entry.id in incoming_refs:
                continue
            issues.append(
                GovernanceIssue(
                    code=GovernanceIssueCode.ORPHAN_DOC.value, severity="warning",
                    doc_id=entry.id,
                    detail=f"Wiki 条目《{entry.title}》无任何出入引用（孤立文档）",
                )
            )
        return issues

    # ── AC-13 陈旧 ────────────────────────────────────────────────────────
    def _stale(self, docs, entries) -> List[GovernanceIssue]:
        issues: List[GovernanceIssue] = []
        for doc in list(docs) + list(entries):
            verified = doc.last_verified
            if not verified:
                continue
            try:
                age = days_between(verified, self.today)
            except ValueError:
                issues.append(
                    GovernanceIssue(
                        code=GovernanceIssueCode.STALE.value, severity="warning",
                        doc_id=doc.id,
                        detail=f"last_verified 格式非法：{verified!r}（期望 YYYY-MM-DD）",
                    )
                )
                continue
            if age > STALE_DAYS:
                issues.append(
                    GovernanceIssue(
                        code=GovernanceIssueCode.STALE.value, severity="warning",
                        doc_id=doc.id,
                        detail=(
                            f"已 {age} 天未核验（阈值 {STALE_DAYS} 天），"
                            f"last_verified={verified}"
                        ),
                    )
                )
        return issues

    # ── AC-14 重复哈希 ────────────────────────────────────────────────────
    def _duplicates(self, docs, entries) -> List[GovernanceIssue]:
        groups: Dict[str, List[Dict[str, str]]] = {}
        for doc in docs:
            if doc.content_hash:
                groups.setdefault(doc.content_hash, []).append(
                    {"id": doc.id, "source_ref": doc.source_ref or "", "source": "repo"}
                )
        for entry in entries:
            if entry.content_hash:
                groups.setdefault(entry.content_hash, []).append(
                    {"id": entry.id, "source_ref": entry.source_ref or "", "source": "wiki"}
                )
        issues: List[GovernanceIssue] = []
        for content_hash, members in groups.items():
            # 同 source_ref 的两个投影（wiki_entries + governed_documents）是同一份文档，
            # 折叠后再判重，否则治理会长期报「自己和自己重复」的假问题。
            distinct = collapse_same_source(members)
            if len(distinct) < 2:
                continue
            for member in distinct:
                peers = [m["id"] for m in distinct if m["id"] != member["id"]]
                issues.append(
                    GovernanceIssue(
                        code=GovernanceIssueCode.DUPLICATE_HASH.value, severity="warning",
                        doc_id=member["id"],
                        detail=f"content_hash 与 {peers} 相同（{content_hash}），建议合并",
                    )
                )
        return issues


__all__ = ["VerifyService", "STALE_DAYS"]
