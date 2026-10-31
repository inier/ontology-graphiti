"""条目业务规则（校验 + 版本号 + 状态机）。

抽出来的原因：`entry_service.py` 的编排逻辑（事务、快照、引用）与「规则判定」
是两类变化原因，混在一个文件里会同时突破单文件行数上限与单一职责。

规则全部抛 `ApiError`（带具体 error_code），不感知 HTTP。
"""

from __future__ import annotations

from typing import Optional

from odap.common import api_errors as E
from odap.common.api_errors import ApiError
from odap.biz.knowledge.models.common import DocStatus

INITIAL_VERSION = "0.1.0"

#: 可发布来源状态（archived / superseded 不可复活，需新条目，保留真相源链）
PUBLISHABLE = frozenset({DocStatus.DRAFT, DocStatus.REVIEW, DocStatus.PUBLISHED})

#: 状态机（ARCHITECTURE-v2 §5.3）：draft → review → published → superseded|archived
ALLOWED_TRANSITIONS = {
    DocStatus.DRAFT: {DocStatus.DRAFT, DocStatus.REVIEW, DocStatus.ARCHIVED},
    DocStatus.REVIEW: {DocStatus.REVIEW, DocStatus.PUBLISHED, DocStatus.DRAFT,
                       DocStatus.ARCHIVED},
    DocStatus.PUBLISHED: {DocStatus.PUBLISHED, DocStatus.ARCHIVED, DocStatus.SUPERSEDED},
    DocStatus.SUPERSEDED: {DocStatus.SUPERSEDED},
    DocStatus.ARCHIVED: {DocStatus.ARCHIVED},
}


def bump_patch(version: str) -> str:
    """semver 补丁位 +1（0.1.0 → 0.1.1）；非法 semver 显式报错而非静默兜底。"""
    parts = (version or "").split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ApiError(
            E.INTERNAL_ERROR,
            f"条目版本号非法，无法递增：{version!r}（期望 semver 形如 0.1.0）",
            status_code=500,
            detail={"version": version},
        )
    major, minor, patch = (int(p) for p in parts)
    return f"{major}.{minor}.{patch + 1}"


def require_owner(owner: Optional[str]) -> str:
    value = (owner or "").strip()
    if not value:
        raise ApiError(
            E.WIKI_OWNER_REQUIRED,
            "创建/更新条目必须指定 owner（责任人）；无 owner 的条目不合格",
            status_code=400,
            detail={"field": "owner"},
        )
    return value


def require_title(title: Optional[str]) -> str:
    value = (title or "").strip()
    if not value:
        raise ApiError(
            E.WIKI_TITLE_REQUIRED, "条目标题不能为空", status_code=400,
            detail={"field": "title"},
        )
    return value


def require_content(content: Optional[str]) -> str:
    if content is None or not str(content).strip():
        raise ApiError(
            E.WIKI_CONTENT_REQUIRED, "条目正文不能为空", status_code=400,
            detail={"field": "content"},
        )
    return content


def transition(current: DocStatus, target: DocStatus) -> DocStatus:
    """校验状态迁移合法性；非法迁移抛 409 并给出允许集合。"""
    allowed = ALLOWED_TRANSITIONS[current]
    if target not in allowed:
        raise ApiError(
            E.WIKI_INVALID_STATUS_TRANSITION,
            f"非法状态迁移：{current.value} → {target.value}",
            status_code=409,
            detail={"from": current.value, "to": target.value,
                    "allowed": sorted(s.value for s in allowed)},
        )
    return target


__all__ = [
    "INITIAL_VERSION",
    "PUBLISHABLE",
    "ALLOWED_TRANSITIONS",
    "bump_patch",
    "require_owner",
    "require_title",
    "require_content",
    "transition",
]
