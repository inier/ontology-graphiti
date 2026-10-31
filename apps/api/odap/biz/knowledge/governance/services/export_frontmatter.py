"""回写前的 front-matter 组装（F3 AC-16）。

独立成文件的理由：这里的每一条都是「跨系统契约」，不是流程：
- `status` 必须写回**仓库权威度词**（产品生命周期态反推，见 `frontmatter_bridge`），
  否则仓库侧 R3「权威唯一」校验会被 `published` 抹平；
- `layer/concern/lifecycle` 必须写回（policy `roundtrip_preserved_keys`），
  否则产品侧回写会静默删掉仓库元数据；
- 承载这些值的 sidecar tag（`layer:L2` 等）**不能**出现在仓库文档里，
  它们只是产品侧存储细节。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from odap.biz.knowledge.governance.services.frontmatter_bridge import (
    derive_layer_meta,
    read_sidecar,
    strip_sidecar,
    to_repo_status,
)


def build_repo_front_matter(
    entry: Any,
    *,
    normalized: str,
    citations: Optional[Sequence[Dict[str, Any]]] = None,
    fallback_content_hash: str = "",
) -> Dict[str, Any]:
    """把产品侧条目还原成仓库 front-matter（键序与 `MANAGED_FIELDS` 对齐）。

    `entry` 只用到 id/title/status/owner/version/superseded_by/supersedes/
    content_hash/content/last_verified/tags，因此不绑定具体模型类型。
    """
    sidecar = {**derive_layer_meta(normalized), **read_sidecar(entry.tags)}
    return {
        "id": entry.id,
        "title": entry.title,
        "status": to_repo_status(entry.status, entry.tags),
        "owner": entry.owner,
        "version": entry.version,
        "layer": sidecar.get("layer", ""),
        "concern": sidecar.get("concern", ""),
        "lifecycle": sidecar.get("lifecycle", ""),
        "source_ref": f"repo:{normalized}",
        "superseded_by": entry.superseded_by,
        "supersedes": list(entry.supersedes or []),
        "content_hash": entry.content_hash or fallback_content_hash,
        "last_verified": entry.last_verified,
        "tags": strip_sidecar(entry.tags),
        "citations": list(citations or []),
    }


def missing_roundtrip_keys(front_matter: Dict[str, Any],
                           keys: Sequence[str] = ("layer", "concern", "lifecycle")) -> List[str]:
    """检查往返必需键是否齐全（供测试与自检断言用，未齐全即数据丢失）。"""
    return [key for key in keys if not str(front_matter.get(key) or "").strip()]


__all__ = ["build_repo_front_matter", "missing_roundtrip_keys"]
