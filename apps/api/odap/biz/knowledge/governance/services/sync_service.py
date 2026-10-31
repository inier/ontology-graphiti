"""仓库 docs/ ↔ Wiki 双向同步（F3，AC-15 / AC-16 / AC-17）。

方向一：仓库 → 产品（AC-15）
    `import_from_repo(source_ref)` 解析 `docs/**/*.md` 的 front-matter，
    生成/更新 `wiki_entries`（幂等，按 `source_ref` 去重）并同步 `governed_documents`。
    `content_hash` 一律按**真实正文**重算（不信任 front-matter 里可能过期的哈希）。

方向二：产品 → 仓库（AC-16）
    `export_to_repo(entry_id, target_path, approval_id, user)` 回写 `.md`，
    front-matter 与条目字段一致。**双重门禁**：
      1. 写权限（AC-17）—— 无权限 403 `WIKI_EXPORT_FORBIDDEN`，文件零改动；
      2. 审批（AC-17）—— `approval_id` 必须是审批工作流中已通过（decision=APPROVE）的记录；
         审批服务不可用 → 503（fail-closed，不放行）。

路径安全：只允许 `docs/` 下的 `.md`，且解析后必须仍在仓库根内（防目录穿越）。
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from odap.common import api_errors as E
from odap.common.api_errors import ApiError
from odap.common.ids import content_hash, new_doc_id
from odap.biz.knowledge.governance.models.doc import GovernedDoc
from odap.biz.knowledge.governance.repositories.doc_repo import GovernedDocRepository
from odap.biz.knowledge.governance.services.export_frontmatter import (
    build_repo_front_matter,
)
from odap.biz.knowledge.governance.services.frontmatter import (
    FrontMatterError,
    normalize_front_matter,
    parse_document,
    serialize_document,
)
from odap.biz.knowledge.governance.services.frontmatter_bridge import (
    merge_tags,
    sidecar_tags,
    to_product_status,
)
from odap.biz.knowledge.governance.services.approval_gate import (
    default_approval_checker,
)
from odap.biz.knowledge.governance.services.repo_paths import (
    has_write_permission,
    repo_root,
    resolve_repo_doc_path,
)
from odap.biz.knowledge.models.common import Citation, DocStatus
from odap.biz.knowledge.util import now_iso, today_iso
from odap.biz.knowledge.wiki.models.entry import WikiEntry
from odap.biz.knowledge.wiki.repositories.citation_repo import WikiCitationRepository
from odap.biz.knowledge.wiki.repositories.entry_repo import WikiEntryRepository
from odap.biz.knowledge.wiki.services.entry_service import bump_patch
from odap.biz.knowledge.wiki.services.version_service import VersionService

def _first_heading(body: str) -> str:
    """取正文第一个标题（front-matter 缺 title 时的兜底来源，不是编造）。"""
    for line in (body or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        if stripped:
            break
    return ""


class SyncService:
    """双向同步服务。"""

    def __init__(
        self,
        entry_repo: Optional[WikiEntryRepository] = None,
        doc_repo: Optional[GovernedDocRepository] = None,
        citation_repo: Optional[WikiCitationRepository] = None,
        db_path: Optional[str] = None,
        approval_checker=None,
    ) -> None:
        self.entries = entry_repo or WikiEntryRepository(db_path)
        self.docs = doc_repo or GovernedDocRepository(db_path)
        self.citations = citation_repo or WikiCitationRepository(db_path)
        # 注入仓储时以其 db_path 为准，避免版本快照写到另一个库（测试与生产同源）
        self._versions = VersionService(db_path=getattr(self.entries, "db_path", db_path))
        self._approval_checker = approval_checker or default_approval_checker

    # ── AC-15 导入 ────────────────────────────────────────────────────────
    def import_from_repo(self, source_ref: str, *, actor_id: str = "") -> Dict[str, Any]:
        normalized, absolute = resolve_repo_doc_path(source_ref)
        if not absolute.is_file():
            raise ApiError(
                E.WIKI_IMPORT_SOURCE_NOT_FOUND, f"仓库文档不存在：{normalized}",
                status_code=404, detail={"path": normalized},
            )
        try:
            text = absolute.read_text(encoding="utf-8")
        except OSError as exc:
            raise ApiError(
                E.WIKI_IMPORT_SOURCE_NOT_FOUND, f"读取仓库文档失败：{exc}",
                status_code=500, detail={"path": normalized},
            ) from exc

        try:
            raw_fm, body = parse_document(text)
            fm = normalize_front_matter(raw_fm)
        except FrontMatterError as exc:
            raise ApiError(
                "DOC_FRONT_MATTER_INVALID", f"{normalized} front-matter 非法：{exc}",
                status_code=400, detail={"path": normalized},
            ) from exc

        repo_ref = f"repo:{normalized}"
        new_hash = content_hash(body)
        ts = now_iso()
        title = fm.get("title") or _first_heading(body) or absolute.stem
        version = fm.get("version") or "0.1.0"
        # 仓库权威度词 → 产品生命周期态（映射表来自 DOC-GOVERNANCE-POLICY 第八节），
        # 权威度同时落成 `authority:<值>` tag；layer/concern/lifecycle 也以 tag 承载，
        # 否则回写时这四项会被抹掉（双向同步的数据丢失）。
        status, authority_tag = to_product_status(fm.get("status"), source_path=normalized)
        tags = merge_tags(
            fm.get("tags") or [],
            sidecar_tags(fm) + ([authority_tag] if authority_tag else []),
        )

        existing = self.entries.get_by_source_ref(repo_ref)
        citations = [Citation.model_validate(c) for c in (fm.get("citations") or [])]

        if existing is None:
            entry = WikiEntry(
                id=new_doc_id("doc"),
                title=title,
                content=body,
                status=status,
                owner=(fm.get("owner") or actor_id or "").strip(),
                version=version,
                source_ref=repo_ref,
                superseded_by=fm.get("superseded_by") or None,
                supersedes=list(fm.get("supersedes") or []),
                content_hash=new_hash,
                last_verified=fm.get("last_verified"),
                tags=tags,
                concept_refs=[],
                created_at=ts,
                updated_at=ts,
            )
            if not entry.owner:
                raise ApiError(
                    E.WIKI_OWNER_REQUIRED,
                    f"{normalized} front-matter 缺 owner，且无导入人可承接责任",
                    status_code=400, detail={"path": normalized},
                )
            self.entries.insert(entry)
            action = "created"
        else:
            changed = existing.content_hash != new_hash
            self.entries.update(
                existing.id,
                {
                    "title": title,
                    "content": body,
                    "content_hash": new_hash,
                    "version": bump_patch(existing.version) if changed else existing.version,
                    "status": status.value,
                    "owner_id": (fm.get("owner") or existing.owner or actor_id or "").strip(),
                    "last_verified": fm.get("last_verified") or existing.last_verified,
                    "tags": tags or list(existing.tags),
                    "updated_at": ts,
                },
            )
            entry = self.entries.get(existing.id)
            action = "updated"
            if changed:
                self._versions.append_snapshot(
                    entry, author_id=actor_id or entry.owner, change_note="import from repo"
                )

        if citations:
            ts_row = now_iso()
            self.citations.replace_for_entry(
                entry.id,
                [
                    {"id": new_doc_id("cite"), "kind": c.kind.value, "ref": c.ref,
                     "created_at": ts_row}
                    for c in citations
                ],
            )

        doc_id = self._upsert_governed_doc(normalized, fm, title, body, new_hash, ts,
                                           status=status, tags=tags)
        return {
            **entry.model_dump(mode="json"),
            "action": action,
            "doc_id": doc_id,
        }

    def _upsert_governed_doc(self, normalized: str, fm: Dict[str, Any], title: str,
                              body: str, new_hash: str, ts: str, *,
                              status: DocStatus, tags: list[str]) -> str:
        repo_ref = f"repo:{normalized}"
        existing_doc = self.docs.get_by_source_ref(repo_ref)
        doc = GovernedDoc(
            id=existing_doc.id if existing_doc else new_doc_id("gov"),
            title=title,
            status=status,
            owner=(fm.get("owner") or None),
            version=fm.get("version") or "0.1.0",
            source_ref=repo_ref,
            superseded_by=fm.get("superseded_by") or None,
            supersedes=list(fm.get("supersedes") or []),
            content_hash=new_hash,
            content=body,
            last_verified=fm.get("last_verified"),
            role=str(fm.get("role") or ""),
            tags=tags,
            created_at=existing_doc.created_at if existing_doc else ts,
            updated_at=ts,
        )
        return self.docs.upsert(doc)

    # ── AC-16 / AC-17 导出 ────────────────────────────────────────────────
    def export_to_repo(
        self,
        *,
        entry_id: str,
        target_path: str,
        approval_id: Optional[str],
        user: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        entry = self.entries.get(entry_id)
        if entry is None:
            raise ApiError(
                E.WIKI_ENTRY_NOT_FOUND, f"Wiki 条目不存在：{entry_id}", status_code=404,
                detail={"entry_id": entry_id},
            )
        if not has_write_permission(user):
            raise ApiError(
                E.WIKI_EXPORT_FORBIDDEN,
                "当前账号不具备仓库回写权限（需要 admin/owner/maintainer/editor 角色或 wiki:write scope）",
                status_code=403,
                detail={"entry_id": entry_id, "reason": "write_permission_denied"},
            )
        if not (approval_id or "").strip():
            raise ApiError(
                E.WIKI_EXPORT_FORBIDDEN,
                "回写仓库必须提供 approval_id（审批未通过不得改动仓库文件）",
                status_code=403,
                detail={"entry_id": entry_id, "reason": "approval_missing"},
            )
        if not self._approval_checker(approval_id.strip()):
            raise ApiError(
                E.WIKI_EXPORT_FORBIDDEN,
                f"审批 {approval_id} 未通过（或无 APPROVE 记录），拒绝回写仓库",
                status_code=403,
                detail={"entry_id": entry_id, "reason": "approval_not_granted",
                        "approval_id": approval_id},
            )

        normalized, absolute = resolve_repo_doc_path(target_path)
        # 回写必须把仓库侧元数据还回去（status 用权威度词、layer/concern/lifecycle 不缺），
        # 组装规则见 export_frontmatter（每一项都是跨系统契约，单独成文件便于审计）。
        front_matter = build_repo_front_matter(
            entry,
            normalized=normalized,
            citations=[c.model_dump(mode="json")
                       for c in self.citations.list_outgoing(entry.id)],
            fallback_content_hash=content_hash(entry.content),
        )
        text = serialize_document(front_matter, entry.content)

        absolute.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = absolute.with_suffix(absolute.suffix + ".tmp")
        tmp_path.write_text(text, encoding="utf-8")
        os.replace(tmp_path, absolute)

        today = today_iso()
        self.entries.update(
            entry.id,
            {"source_ref": f"repo:{normalized}", "last_verified": today,
             "updated_at": now_iso()},
        )
        return {
            "target_path": normalized,
            "content_hash": content_hash(text),
            "entry_id": entry.id,
        }


__all__ = [
    "SyncService",
    "repo_root",
    "resolve_repo_doc_path",
    "has_write_permission",
    "default_approval_checker",
]
