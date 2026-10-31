"""引用关系服务（F1，AC-06）。

引用图语义：
- `outgoing[]`：本条目的 citations（它引用了谁）。
- `incoming[]`：引用了本条目的其他条目（谁引用了它）。
- `links[]`：把 cites / supersedes 两类边统一成图结构（openapi `ReferenceGraph.links`）。

ref 归一化口径（AC-06 与 AC-11 共用，必须一致）：
    `doc:kb/123#chunk-4`  → target = `kb/123`（去 `#fragment`）
    `entry:doc-01J...`    → target = `doc-01J...`（去 `entry:` 前缀）
    `doc:01J...`          → target = `01J...`
条目可被 `id` 或 `source_ref` 命中（仓库导入的条目两者都存在）。
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from pydantic import ValidationError

from odap.common import api_errors as E
from odap.common.api_errors import ApiError
from odap.biz.knowledge.models.common import Citation, CitationKind, DocStatus
from odap.biz.knowledge.wiki.models.entry import (
    ReferenceGraph,
    ReferenceLink,
    ReferenceNode,
)
from odap.biz.knowledge.wiki.repositories.citation_repo import WikiCitationRepository
from odap.biz.knowledge.wiki.repositories.entry_repo import WikiEntryRepository

_DOC_PREFIX = re.compile(r"^(?:doc|entry|wiki):", re.IGNORECASE)
_FRAGMENT = re.compile(r"#.*$")


def normalize_ref(ref: str) -> str:
    """把 citation.ref 归一化为可比较的目标标识。"""
    value = (ref or "").strip()
    value = _FRAGMENT.sub("", value)
    if value.lower().startswith("repo:"):
        value = value[5:]
    return _DOC_PREFIX.sub("", value).strip()


def ref_targets_entry(ref: str, entry_id: str, source_ref: Optional[str]) -> bool:
    """判断一条 ref 是否指向指定条目（按 id 或 source_ref）。"""
    target = normalize_ref(ref)
    if not target:
        return False
    if target == entry_id:
        return True
    if source_ref:
        source = normalize_ref(source_ref.replace("repo:", ""))
        return target == source or source.endswith("/" + target)
    return False


def parse_citations(raw: List[object]) -> List[Citation]:
    """把请求里的 citations（dict / Citation）解析为领域模型。

    非法 kind 必须显式 400（不静默丢弃引用，否则会伪造「无悬空引用」的假通过）。
    """
    parsed: List[Citation] = []
    for item in raw or []:
        if isinstance(item, Citation):
            parsed.append(item)
            continue
        try:
            parsed.append(Citation.model_validate(item))
        except ValidationError as exc:
            raise ApiError(
                E.WIKI_CITATION_INVALID,
                f"citation 结构非法：{exc.errors()[0].get('msg', 'invalid citation')}",
                status_code=400, detail={"citation": item, "field": "citations"},
            ) from exc
    return parsed


class CitationService:
    """引用图查询服务。"""

    def __init__(
        self,
        entry_repo: Optional[WikiEntryRepository] = None,
        citation_repo: Optional[WikiCitationRepository] = None,
        db_path: Optional[str] = None,
    ) -> None:
        self.entries = entry_repo or WikiEntryRepository(db_path)
        self.citations = citation_repo or WikiCitationRepository(db_path)

    def build_graph(self, entry_id: str) -> ReferenceGraph:
        entry = self.entries.get(entry_id)
        if entry is None:
            raise ApiError(
                E.WIKI_ENTRY_NOT_FOUND, f"Wiki 条目不存在：{entry_id}", status_code=404,
                detail={"entry_id": entry_id},
            )

        outgoing = self.citations.list_outgoing(entry_id)
        incoming: List[Citation] = []
        incoming_entries: List[Tuple[str, str]] = []
        for row in self.citations.list_all():
            if row["entry_id"] == entry_id:
                continue
            if ref_targets_entry(row["ref"], entry_id, entry.source_ref):
                incoming.append(Citation(kind=CitationKind(row["kind"]), ref=row["ref"]))
                incoming_entries.append((row["entry_id"], row["ref"]))

        nodes = {entry_id: ReferenceNode(
            id=entry.id, title=entry.title, status=entry.status
        )}
        links: List[ReferenceLink] = []

        # outgoing → cites 边
        for cite in outgoing:
            target = normalize_ref(cite.ref)
            if not target:
                continue
            if cite.kind == CitationKind.DOC:
                node = self.entries.get(target)
                if node is not None:
                    nodes[node.id] = ReferenceNode(
                        id=node.id, title=node.title, status=node.status
                    )
                    links.append(ReferenceLink(from_id=entry_id, to_id=node.id, kind="cites"))
                else:
                    nodes[target] = ReferenceNode(id=target, title=target)
                    links.append(ReferenceLink(from_id=entry_id, to_id=target, kind="cites"))

        # incoming → cites 边（反向）
        for source_id, _ref in incoming_entries:
            source = self.entries.get(source_id)
            if source is None:
                continue
            nodes[source.id] = ReferenceNode(id=source.id, title=source.title,
                                            status=source.status)
            links.append(ReferenceLink(from_id=source.id, to_id=entry_id, kind="cites"))

        # supersedes 双向链（AC-10）也是图上的边
        if entry.superseded_by:
            target = self.entries.get(entry.superseded_by)
            if target is not None:
                nodes[target.id] = ReferenceNode(id=target.id, title=target.title,
                                                status=target.status)
                links.append(ReferenceLink(from_id=entry_id, to_id=target.id,
                                           kind="supersedes"))
        for superseded_id in entry.supersedes:
            source = self.entries.get(superseded_id)
            if source is not None:
                nodes[source.id] = ReferenceNode(id=source.id, title=source.title,
                                                 status=source.status)
                links.append(ReferenceLink(from_id=source.id, to_id=entry_id,
                                           kind="supersedes"))

        return ReferenceGraph(
            nodes=list(nodes.values()),
            links=links,
            outgoing=outgoing,
            incoming=incoming,
        )

    @staticmethod
    def status_of(entry_id: str, entries: Optional[WikiEntryRepository] = None) -> str:
        repo = entries or WikiEntryRepository()
        entry = repo.get(entry_id)
        return entry.status.value if entry else DocStatus.ARCHIVED.value


__all__ = ["CitationService", "normalize_ref", "ref_targets_entry", "parse_citations"]
