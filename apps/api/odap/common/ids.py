"""ID 与哈希工具 —— common 叶子层（仅标准库）。

用途（SPEC-v2 §6/§9）：
- `wiki_entries.id` / `governed_documents.id` 使用 ULID（时间有序、可寻址），
  前缀 `doc-` 与 openapi-v2 示例一致（`doc-01J9ZK8P3Q7N2M`）。
- `content_hash` 使用 sha256（判重与版本锚定的依据，AC-04/AC-14）。
- `trace_id` 使用 `urn:odap:trace:<ulid>`（qa_traces / Provenance，AC-36）。

ULID 实现说明：Crockford Base32（去 I/L/O/U），前 48bit 毫秒时间戳 + 80bit 随机数，
26 字符输出。不引入第三方依赖（仓库未锁定 python-ulid）。
"""

from __future__ import annotations

import hashlib
import os
import time

_CROCKFORD32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_TIME_LEN = 10
_RAND_LEN = 16


def _encode(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(_CROCKFORD32[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def new_ulid(timestamp_ms: int | None = None) -> str:
    """生成 26 字符 ULID。"""
    ts = int(time.time() * 1000) if timestamp_ms is None else int(timestamp_ms)
    if ts < 0:
        raise ValueError(f"ULID 时间戳不能为负：{ts}")
    rand = int.from_bytes(os.urandom(10), "big")
    return _encode(ts, _TIME_LEN) + _encode(rand, _RAND_LEN)


def new_doc_id(prefix: str = "doc") -> str:
    """生成 `doc-<ULID>` 形式的资源 id。"""
    return f"{prefix}-{new_ulid()}"


def new_trace_id() -> str:
    """生成 `urn:odap:trace:<ULID>` 形式的溯源 id（AC-36）。"""
    return f"urn:odap:trace:{new_ulid()}"


def content_hash(content: str) -> str:
    """计算 sha256 内容哈希，形如 `sha256:<hex>`（AC-04 判重口径）。"""
    digest = hashlib.sha256((content or "").encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def stable_hash_percent(key: str) -> int:
    """把任意键稳定映射到 0..99（Feature Flag 百分比灰度，ARCHITECTURE-v2 §8.3）。"""
    digest = hashlib.sha256((key or "").encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % 100


__all__ = ["new_ulid", "new_doc_id", "new_trace_id", "content_hash", "stable_hash_percent"]
