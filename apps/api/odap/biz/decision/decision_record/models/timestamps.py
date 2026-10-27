"""时间戳序列化助手

图节点上 `created_at` / `updated_at` 存字符串，且要参与范围过滤与排序。
`datetime.isoformat()` 在微秒为 0 时省略 `.000000` 段，导致同一天内
`...T10:00:00+00:00` 与 `...T10:00:00.123456+00:00` 字典序与时间序不一致。
故统一输出定宽格式 `YYYY-MM-DDTHH:MM:SS.ffffff+00:00`。
"""

from datetime import datetime, timezone
from typing import Optional

ISO_UTC_FORMAT = "%Y-%m-%dT%H:%M:%S.%f+00:00"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: Optional[datetime]) -> Optional[str]:
    """datetime -> 定宽 UTC ISO 字符串（None 透传）。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime(ISO_UTC_FORMAT)


def parse_iso(value: object) -> Optional[datetime]:
    """宽松解析：已是 datetime 直接返回，字符串失败返回 None。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
