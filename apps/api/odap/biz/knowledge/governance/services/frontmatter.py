"""front-matter 解析/序列化（F3，AC-15 / AC-16）。

纳管字段（SPEC-v2 §5.2 + ADR-097 三元正交模型）：
    id / title / status / owner / version / source_ref / superseded_by /
    supersedes / content_hash / last_verified / tags / citations
    layer / concern / lifecycle / authority

后四个键来自 `docs/DOC-GOVERNANCE-POLICY.yaml` 的 `roundtrip_preserved_keys`：
它们是仓库侧文档治理的元数据（在哪一层 / 管什么主题 / 是否还在维护 / 多大权威）。
不纳入纳管字段的后果是**双向同步静默丢字段**——`serialize_document` 只输出
`MANAGED_FIELDS` 内的键，回写时这四项会被抹掉（数据丢失，不是显示问题）。

实现约束：
- 只解析头部 `---\\n...\\n---` 块；非法 YAML 必须显式报错（不静默丢字段，否则
  导入会伪造「字段齐全」的假象）。
- 序列化与解析互逆：`serialize(parse(text))` 的 front-matter 字段集不丢。
- 不引入第三方 markdown 库；pyyaml 已是项目依赖（apps/api/pyproject.toml）。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

import yaml

_FM_BLOCK = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

#: 纳管字段白名单（顺序即序列化顺序，便于 diff 稳定）
MANAGED_FIELDS: Tuple[str, ...] = (
    "id", "title", "status", "owner", "version", "source_ref", "superseded_by",
    "supersedes", "content_hash", "last_verified", "tags", "citations",
    # 文档治理三元正交模型 + 权威度（policy: roundtrip_preserved_keys）
    "layer", "concern", "lifecycle", "authority",
)

#: 纯字符串字段（None → 空串）；用于 normalize 的类型归一
_STR_FIELDS: Tuple[str, ...] = (
    "id", "title", "status", "owner", "version", "source_ref", "superseded_by",
    "content_hash", "layer", "concern", "lifecycle", "authority",
)


class FrontMatterError(ValueError):
    """front-matter 非法（缺块 / YAML 语法错误 / 根节点非映射）。"""


def parse_document(text: str) -> Tuple[Dict[str, Any], str]:
    """解析 `(front_matter, body)`；无 front-matter 时返回 `({}, 全文)`。"""
    if text is None:
        raise FrontMatterError("文档内容为 None")
    match = _FM_BLOCK.match(text)
    if not match:
        return {}, text
    raw = match.group(1)
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise FrontMatterError(f"front-matter YAML 解析失败：{exc}") from exc
    if not isinstance(data, dict):
        raise FrontMatterError(
            f"front-matter 根节点必须是映射（key: value），实际为 {type(data).__name__}"
        )
    return {str(k): v for k, v in data.items()}, text[match.end():]


def normalize_front_matter(data: Dict[str, Any]) -> Dict[str, Any]:
    """只保留纳管字段，并做类型归一（list/str/bool）。"""
    normalized: Dict[str, Any] = {}
    for key in MANAGED_FIELDS:
        if key not in data:
            continue
        value = data[key]
        if key in ("supersedes", "tags"):
            if value is None:
                normalized[key] = []
            elif isinstance(value, str):
                normalized[key] = [value] if value else []
            else:
                normalized[key] = [str(v) for v in value]
        elif key == "citations":
            normalized[key] = _normalize_citations(value)
        elif key == "last_verified":
            normalized[key] = str(value)[:10] if value else None
        elif key in _STR_FIELDS:
            normalized[key] = "" if value is None else str(value)
        else:  # pragma: no cover - 白名单已穷举
            normalized[key] = value
    return normalized


def _normalize_citations(value: Any) -> List[Dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, str):
        return [{"kind": "doc", "ref": value}]
    items: List[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict) and item.get("ref"):
            items.append({"kind": str(item.get("kind", "doc")), "ref": str(item["ref"])})
        elif isinstance(item, str) and item:
            items.append({"kind": "doc", "ref": item})
        else:
            raise FrontMatterError(f"citations 条目非法：{item!r}")
    return items


def serialize_document(front_matter: Dict[str, Any], body: str) -> str:
    """生成 `---\\n<yaml>---\\n\\n<body>` 文本。"""
    payload = {key: front_matter[key] for key in MANAGED_FIELDS if key in front_matter}
    header = yaml.safe_dump(
        payload, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).strip()
    return f"---\n{header}\n---\n\n{body.lstrip()}"


__all__ = [
    "MANAGED_FIELDS",
    "FrontMatterError",
    "parse_document",
    "normalize_front_matter",
    "serialize_document",
]
