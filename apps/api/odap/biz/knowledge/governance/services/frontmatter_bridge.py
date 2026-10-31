"""仓库 front-matter ↔ 产品治理模型的状态桥（跨模块契约）。

依据 `docs/DOC-GOVERNANCE-POLICY.yaml` 第八节（2026-10-17 项目总监裁定）：

1. 两套 status 词表**都保留**，不合并：仓库侧表达「有多大权威」
   （authoritative / active / reference / proposed / superseded / archived / vendor），
   产品侧 `DocStatus` 表达「生命周期走到哪步」（draft / review / published / …）。
2. 同步边界做单向映射（仓库 → 产品），权威度另用 `authority:<值>` tag 承载，不丢信息。
3. 回写必须保留 `layer / concern / lifecycle`（`authority` 由 status 承载，
   不在同一份文件里再写一遍，避免出现两个权威度真相源）。

约定纪律：
- 映射表**只从 policy 文件读**（`status_mapping_to_product`），代码里不另存一份。
  抄一份必然漂移，且漂移是静默的——docs 侧新增权威度词，产品侧会对整批文档报 400。
- policy 缺失/残缺 → 500 且带文件路径，不静默套默认值（默认值等于第二真相源）。
- `layer/concern/lifecycle` 在产品侧以 tag 承载（`layer:L2` / `concern:adr` /
  `lifecycle:frozen`），因为 `wiki_entries.tags` 与 `governed_documents.tags`
  本来就是自由元数据位；不新增列的收益是不动 8 表共享 DDL 与既有库迁移。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import yaml

from odap.common import api_errors as E
from odap.common.api_errors import ApiError
from odap.biz.knowledge.models.common import DocStatus

#: policy 相对仓库根的路径（唯一真相源，禁止在代码里复制映射表）
POLICY_RELATIVE = "docs/DOC-GOVERNANCE-POLICY.yaml"
#: 显式覆盖 policy 路径（测试/部署用）
POLICY_ENV = "ODAP_DOC_POLICY"

#: 往返需要保留、以 tag 承载的元数据键（authority 单独处理，见模块头）
SIDECAR_KEYS: Tuple[str, ...] = ("layer", "concern", "lifecycle")
AUTHORITY_KEY = "authority"
_TAG_SEP = ":"

#: 反向（产品 → 仓库）**无法由 policy 唯一推导**：published 对应 authoritative /
#: active / reference 三个权威度词。这里取 `active`（在位且非唯一权威）作兜底，
#: 细分由 `authority:<值>` tag 还原；仅在条目从未从仓库导入过、因而没有 tag 时才会用到。
_FALLBACK_REPO_STATUS: Mapping[str, str] = {
    "draft": "proposed",
    "review": "proposed",
    "published": "active",
    "superseded": "superseded",
    "archived": "archived",
}

#: mtime 缓存：policy 改动后无需重启即生效
_POLICY_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def policy_path() -> Path:
    """定位 policy 文件：`ODAP_DOC_POLICY` 优先，否则从本文件上溯查找。"""
    override = os.environ.get(POLICY_ENV)
    if override:
        return Path(override).expanduser().resolve()
    for parent in Path(__file__).resolve().parents:
        candidate = parent / POLICY_RELATIVE
        if candidate.is_file():
            return candidate
    raise ApiError(
        E.INTERNAL_ERROR,
        f"未找到文档治理策略文件 {POLICY_RELATIVE}"
        f"（从 {Path(__file__).resolve()} 向上未命中；可用环境变量 {POLICY_ENV} 指定）",
        status_code=500,
        detail={"policy": POLICY_RELATIVE, "env": POLICY_ENV},
    )


def load_policy(path: Optional[Path] = None) -> Dict[str, Any]:
    """读 policy（按 mtime 缓存）；缺失/非法 YAML 一律显式 500。"""
    target = path or policy_path()
    try:
        mtime = target.stat().st_mtime
    except OSError as exc:
        raise ApiError(
            E.INTERNAL_ERROR, f"文档治理策略文件不可读：{target}（{exc}）",
            status_code=500, detail={"policy": str(target)},
        ) from exc
    cached = _POLICY_CACHE.get(str(target))
    if cached is not None and cached[0] == mtime:
        return cached[1]
    try:
        payload = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ApiError(
            E.INTERNAL_ERROR, f"文档治理策略文件 YAML 非法：{target}（{exc}）",
            status_code=500, detail={"policy": str(target)},
        ) from exc
    if not isinstance(payload, dict):
        raise ApiError(
            E.INTERNAL_ERROR,
            f"文档治理策略文件根节点必须是映射，实际为 {type(payload).__name__}：{target}",
            status_code=500, detail={"policy": str(target)},
        )
    _POLICY_CACHE[str(target)] = (mtime, payload)
    return payload


def status_mapping(path: Optional[Path] = None) -> Dict[str, str]:
    """仓库权威度词 → 产品 DocStatus 值（读 policy 第八节）。"""
    table = load_policy(path).get("status_mapping_to_product") or {}
    mapping = {
        str(key).strip(): str(value).strip()
        for key, value in table.items()
        if str(key).strip()
    }
    if not mapping:
        raise ApiError(
            E.INTERNAL_ERROR,
            f"策略文件缺少 status_mapping_to_product（见 {policy_path()} 第八节）",
            status_code=500, detail={"policy": str(policy_path())},
        )
    return mapping


def authority_tag_prefix(path: Optional[Path] = None) -> str:
    """权威度 tag 前缀（policy `authority_tag_prefix`）。"""
    return str(load_policy(path).get("authority_tag_prefix") or "authority:")


# ── 仓库 → 产品 ────────────────────────────────────────────────────────────
def to_product_status(
    value: Any, *, source_path: str = "", path: Optional[Path] = None
) -> Tuple[DocStatus, Optional[str]]:
    """仓库 status 值 → (产品状态, 权威度 tag)。

    - 仓库权威度词（authoritative/active/…）→ 按 policy 映射，并给出 `authority:<值>` tag；
    - 已是产品词表的值（draft/published/…）→ 直通，不造 tag（历史文档就是这么写的）；
    - 其余 → 400 `DOC_STATUS_INVALID`，错误文案带值、允许集合与 policy 路径。
    """
    raw = str(value or "").strip()
    mapping = status_mapping(path)
    if not raw:
        return DocStatus.DRAFT, None
    if raw in mapping:
        target = mapping[raw]
        try:
            status = DocStatus(target)
        except ValueError as exc:
            raise ApiError(
                E.INTERNAL_ERROR,
                f"policy 的映射目标不是产品状态：{raw} → {target!r}（见 {policy_path()}）",
                status_code=500,
                detail={"status": raw, "mapped_to": target, "policy": str(policy_path())},
            ) from exc
        return status, f"{authority_tag_prefix(path)}{raw}"
    try:
        return DocStatus(raw), None
    except ValueError as exc:
        allowed = sorted(set(mapping) | {s.value for s in DocStatus})
        raise ApiError(
            "DOC_STATUS_INVALID",
            f"{source_path or 'front-matter'} status 非法：{raw!r}；"
            f"允许值（仓库权威度 + 产品生命周期）={allowed}；映射表见 {policy_path()}",
            status_code=400,
            detail={"path": source_path, "status": raw, "allowed": allowed,
                    "policy": str(policy_path())},
        ) from exc


def sidecar_tags(front_matter: Dict[str, Any], *, path: Optional[Path] = None) -> List[str]:
    """把 `layer/concern/lifecycle`（及显式给出的 authority）编码成 tag。"""
    tags: List[str] = []
    for key in SIDECAR_KEYS:
        value = str((front_matter or {}).get(key) or "").strip()
        if value:
            tags.append(f"{key}{_TAG_SEP}{value}")
    authority = str((front_matter or {}).get(AUTHORITY_KEY) or "").strip()
    if authority:
        tags.append(f"{authority_tag_prefix(path)}{authority}")
    return tags


def read_sidecar(tags: Sequence[str]) -> Dict[str, str]:
    """从 tag 里解出 `layer/concern/lifecycle/authority`（同键取第一个）。"""
    known = set(SIDECAR_KEYS) | {AUTHORITY_KEY}
    out: Dict[str, str] = {}
    for tag in tags or []:
        key, sep, value = str(tag or "").partition(_TAG_SEP)
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if key in known and value and key not in out:
            out[key] = value
    return out


def strip_sidecar(tags: Sequence[str]) -> List[str]:
    """去掉承载元数据的 tag —— 它们属于产品侧存储细节，不该出现在仓库文档里。"""
    known = set(SIDECAR_KEYS) | {AUTHORITY_KEY}
    kept: List[str] = []
    for tag in tags or []:
        key, sep, _value = str(tag or "").partition(_TAG_SEP)
        if sep and key.strip() in known:
            continue
        kept.append(str(tag))
    return kept


def merge_tags(tags: Sequence[str], extra: Sequence[str] = ()) -> List[str]:
    """保序去重合并（sidecar tag 追加在后，不覆盖用户自定义 tag）。"""
    merged: List[str] = []
    for tag in list(tags) + list(extra):
        text = str(tag or "").strip()
        if text and text not in merged:
            merged.append(text)
    return merged


# ── 产品 → 仓库 ────────────────────────────────────────────────────────────
def to_repo_status(
    status: DocStatus, tags: Sequence[str], *, path: Optional[Path] = None
) -> str:
    """产品状态 → 仓库 status：有权威度 tag 就还原原词，否则按兜底表反推。"""
    authority = read_sidecar(tags).get(AUTHORITY_KEY)
    if authority and authority in status_mapping(path):
        return authority
    return _FALLBACK_REPO_STATUS.get(DocStatus(status).value, "active")


def derive_layer_meta(relative_path: str, *, path: Optional[Path] = None) -> Dict[str, str]:
    """按 policy `layers` 的最长前缀规则推出 layer/concern（回写缺失元数据时用）。

    与 `scripts/doc_governance.py` 的 resolve_layer 同口径；放这里是为了让
    "条目从未从仓库导入过" 时回写出的文档也满足审计（layer 必填）。
    """
    normalized = (relative_path or "").replace("\\", "/").lstrip("/")
    policy = load_policy(path)
    best: Optional[Dict[str, Any]] = None
    best_len = -1
    for layer in policy.get("layers") or []:
        prefix = str(layer.get("dir") or "").rstrip("/")
        if prefix and normalized.startswith(prefix) and len(prefix) > best_len:
            best, best_len = layer, len(prefix)
    if best is None:
        return {}
    meta = {"layer": str(best.get("id") or ""), "concern": str(best.get("concern") or "")}
    defaults = (policy.get("layer_defaults") or {}).get(meta["layer"], {}) or {}
    if not meta["concern"]:
        meta["concern"] = str(defaults.get("concern") or "")
    if defaults.get("lifecycle"):
        meta["lifecycle"] = str(defaults["lifecycle"])
    return {k: v for k, v in meta.items() if v}


__all__ = [
    "POLICY_RELATIVE",
    "POLICY_ENV",
    "SIDECAR_KEYS",
    "AUTHORITY_KEY",
    "policy_path",
    "load_policy",
    "status_mapping",
    "authority_tag_prefix",
    "to_product_status",
    "sidecar_tags",
    "read_sidecar",
    "strip_sidecar",
    "merge_tags",
    "to_repo_status",
    "derive_layer_meta",
]
