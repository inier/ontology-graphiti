"""PROV 溯源完整性原语（P0-3）。

解决的问题：溯源导出只能证明「我们导出了这些三元组」，不能证明「导出的审计
记录没有被改过」。补齐两件事：

1. **内容指纹**：``event_digest`` 对事件做规范化 JSON（键排序、紧凑分隔符、
   UTF-8）后取 SHA-256，同一事件在任何机器上指纹一致。
2. **链式摘要**：``chain_digest`` 把「前一条链哈希 + 本条内容指纹」编码成
   链哈希，任何一条被改写都会使其后的链哈希全部失配。

**为什么用长度前缀而不是分隔符拼接**：Semantica #2136 就是
``f"{a}|{b}"`` 这类拼接造成的碰撞 —— ``("a|b", "c")`` 与 ``("a", "b|c")``
序列化后完全相同，两批不同的事件会得到同一个摘要，篡改因此不可见。
长度前缀（``8 字节大端长度 + 内容``）保证编码是单射的。
"""

from __future__ import annotations

import hashlib
import json
import struct
from typing import Any, Iterable, Mapping

# 空链锚点：64 个 '0'，与 sha256 十六进制等长，便于统一按字符串比较
GENESIS_DIGEST = "0" * 64

# 派生字段不参与内容指纹：它们本身由内容计算得出，纳入会形成自引用
_DERIVED_FIELDS = frozenset({
    "checksum",
    "event_digest",
    "prev_digest",
    "chain_hash",
    "sealed_at",
    # audit_logger_v2 的链字段同样是派生值
    "previous_hash",
    "current_hash",
})


def event_key(event: Mapping[str, Any]) -> str:
    """事件主键：兼容 ``id`` / ``event_id`` 两种写法。"""
    for field in ("id", "event_id"):
        value = event.get(field)
        if value:
            return str(value)
    raise ValueError("audit event has neither 'id' nor 'event_id'")


def _json_default(obj: Any) -> Any:
    """规范化 JSON 的兜底序列化：datetime → ISO，集合 → 排序列表，其余 → str。"""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, (set, frozenset)):
        return sorted(obj, key=str)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return str(obj)


def canonical_bytes(payload: Any) -> bytes:
    """键序无关、分隔符紧凑、UTF-8 编码的规范化 JSON 字节串。"""
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")


def event_digest(event: Mapping[str, Any]) -> str:
    """事件内容指纹（SHA-256 十六进制）。

    只剔除派生字段；``id``/``event_id`` 保留在指纹内，避免「主键被换掉」
    这类篡改逃逸。
    """
    payload = {k: v for k, v in event.items() if k not in _DERIVED_FIELDS}
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _length_prefixed(data: bytes) -> bytes:
    """8 字节大端长度前缀 + 内容。保证拼接编码是单射的。"""
    return struct.pack(">Q", len(data)) + data


def chain_digest(prev_digest: str, current_digest: str) -> str:
    """链哈希 = SHA-256(len(prev)||prev||len(cur)||cur)。"""
    return hashlib.sha256(
        _length_prefixed(str(prev_digest).encode("utf-8"))
        + _length_prefixed(str(current_digest).encode("utf-8"))
    ).hexdigest()


def collection_digest(digests: Iterable[str]) -> str:
    """有序摘要集合的聚合指纹（用于导出清单）。"""
    hasher = hashlib.sha256()
    for digest in digests:
        hasher.update(_length_prefixed(str(digest).encode("utf-8")))
    return hasher.hexdigest()


__all__ = [
    "GENESIS_DIGEST",
    "canonical_bytes",
    "chain_digest",
    "collection_digest",
    "event_digest",
    "event_key",
]
