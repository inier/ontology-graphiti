"""仓库路径解析与写权限判定（F3，AC-16 / AC-17 的安全边界）。

独立成文件的原因：路径白名单/穿越防护与目录判定是「安全边界」，与同步业务流程
（解析 front-matter、建条目、写引用）变化原因不同，混在一起既超长也难单独审计。

规则：
- 只允许 `docs/` 下的 `.md`；
- 解析后必须仍在仓库根内（防目录穿越、防符号链接逃逸）；
- 写权限 = 写角色集合命中，或持有写 scope。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from odap.common import api_errors as E
from odap.common.api_errors import ApiError

ALLOWED_PREFIX = "docs/"
ALLOWED_SUFFIX = ".md"
WRITE_ROLES = {"admin", "owner", "maintainer", "editor"}
WRITE_SCOPES = {"wiki:write", "wiki:export", "docs:write"}


def repo_root() -> Path:
    """仓库根目录（`ODAP_REPO_ROOT` 优先；否则从本文件上溯找含 `docs/` 的目录）。"""
    env_root = os.environ.get("ODAP_REPO_ROOT")
    if env_root:
        return Path(env_root).resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs").is_dir() and (parent / "apps").is_dir():
            return parent
    raise ApiError(
        E.INTERNAL_ERROR, "无法定位仓库根目录（未找到同时含 docs/ 与 apps/ 的祖先目录）",
        status_code=500,
    )


def resolve_repo_doc_path(relative_path: str) -> Tuple[str, Path]:
    """把 `docs/xxx.md` 解析为 (规范化相对路径, 绝对路径)，并做白名单校验。"""
    raw = (relative_path or "").strip()
    if raw.startswith("repo:"):
        raw = raw[5:]
    normalized = raw.replace("\\", "/").lstrip("/")
    if ".." in normalized.split("/"):
        raise ApiError(
            E.WIKI_IMPORT_PATH_INVALID, f"路径含目录穿越片段，拒绝访问：{relative_path!r}",
            status_code=400, detail={"path": relative_path},
        )
    if not normalized.startswith(ALLOWED_PREFIX):
        raise ApiError(
            E.WIKI_IMPORT_PATH_INVALID,
            f"路径必须位于仓库 {ALLOWED_PREFIX} 下：{normalized!r}",
            status_code=400, detail={"path": normalized},
        )
    if not normalized.lower().endswith(ALLOWED_SUFFIX):
        raise ApiError(
            E.WIKI_IMPORT_PATH_INVALID,
            f"仅支持 {ALLOWED_SUFFIX} 文档：{normalized!r}",
            status_code=400, detail={"path": normalized},
        )
    root = repo_root()
    absolute = (root / normalized).resolve()
    if root not in absolute.parents:
        raise ApiError(
            E.WIKI_IMPORT_PATH_INVALID, f"解析后的路径逃逸出仓库根：{absolute}",
            status_code=400, detail={"path": normalized},
        )
    return normalized, absolute


def has_write_permission(user: Optional[Dict[str, Any]]) -> bool:
    """写权限判定：角色命中写角色集合，或持有写 scope。"""
    payload = user or {}
    roles = {str(r).lower() for r in (payload.get("roles") or []) if r}
    single = str(payload.get("role") or "").lower()
    if single:
        roles.add(single)
    scopes = {str(s) for s in (payload.get("scopes") or []) if s}
    return bool(roles & WRITE_ROLES) or bool(scopes & WRITE_SCOPES)


__all__ = [
    "ALLOWED_PREFIX",
    "ALLOWED_SUFFIX",
    "WRITE_ROLES",
    "WRITE_SCOPES",
    "repo_root",
    "resolve_repo_doc_path",
    "has_write_permission",
]
