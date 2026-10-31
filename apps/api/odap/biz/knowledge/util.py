"""知识域内部工具（时间戳口径统一，避免 service 间循环 import）。"""

from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    """当前 UTC 时间（ISO-8601，含时区）。"""
    return datetime.now(timezone.utc).isoformat()


def today_iso() -> str:
    """当前 UTC 日期（`YYYY-MM-DD`，`last_verified` 口径，AC-13）。"""
    return datetime.now(timezone.utc).date().isoformat()


def days_between(older_iso_date: str, newer_iso_date: str) -> int:
    """两个 `YYYY-MM-DD` 之间相差天数（newer - older）。"""
    older = datetime.strptime(older_iso_date[:10], "%Y-%m-%d").date()
    newer = datetime.strptime(newer_iso_date[:10], "%Y-%m-%d").date()
    return (newer - older).days


def collapse_same_source(members: list[dict]) -> list[dict]:
    """把同 `source_ref` 的多条投影折叠为一条代表记录。

    为什么需要：同一份仓库文档在统一纳管模型里会同时存在 `wiki_entries` 与
    `governed_documents` 两条记录（同一 `source_ref` 的两个投影）。若把它们当成
    「内容重复」，治理校验会永远报假重复，去重候选也会给出无意义的「自己合并自己」。

    代表记录选取：`source == "wiki"` 优先（产品侧真相源），否则取首条；
    输出按 `(created_at, id)` 排序，保证「最早创建者为 canonical」可复算。
    """
    representatives: dict[str, dict] = {}
    for member in members:
        source_ref = str(member.get("source_ref") or "").strip()
        key = source_ref or str(member.get("id") or "")
        if not key:
            continue
        current = representatives.get(key)
        if current is None or (member.get("source") == "wiki"
                               and current.get("source") != "wiki"):
            representatives[key] = member
    return sorted(representatives.values(),
                  key=lambda m: (str(m.get("created_at") or ""), str(m.get("id") or "")))


__all__ = ["now_iso", "today_iso", "days_between", "collapse_same_source"]
