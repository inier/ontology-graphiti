"""SLA 派生（ADR-091 §10「SLA：后端派生，前端不自算」）

阈值走服务端配置，**不做入参**——否则前端调一个参数就能把"已超时 40 条"
改成"0 条"，SLA 变成摆设。

计时基准**按分组分档**，这一点不能统一：
- `to_resolve`（待裁定）自 `created_at` 起算——"等了多久没人拍板"
- `to_execute`（待执行确认）自 `resolution.at` 起算——"拍板后多久没落地"

统一取 `created_at` 会把"昨天刚裁决的"显示成"等了 5 天"，差一整个待裁定周期。
两者都不取 `updated_at`（`to_execute` 仅在缺 `resolution.at` 时回落它），
避免任意一次编辑把等待时长重置为 0。
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from odap.biz.decision.decision_record.models.timestamps import iso_utc, parse_iso, utcnow

logger = logging.getLogger(__name__)

DEFAULT_WARNING_MINUTES = 24 * 60   # ok <= 24h
DEFAULT_BREACH_MINUTES = 72 * 60    # warning 24-72h；breached > 72h

SLA_STATES = ("ok", "warning", "breached")


def _read_minutes(env_key: str, default: int) -> int:
    raw = os.environ.get(env_key, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        return default
    return value if value > 0 else default


def warning_minutes() -> int:
    return _read_minutes("ODAP_SLA_WARNING_MINUTES", DEFAULT_WARNING_MINUTES)


def breach_minutes() -> int:
    return _read_minutes("ODAP_SLA_BREACH_MINUTES", DEFAULT_BREACH_MINUTES)


def waited_minutes(created_at: datetime, now: Optional[datetime] = None) -> int:
    """自 `created_at` 起算的等待分钟数（负数按 0 处理，防止时钟漂移出负值）。"""
    reference = now or utcnow()
    delta = reference - created_at
    return max(0, int(delta.total_seconds() // 60))


def sla_state(minutes: int) -> str:
    """三档：ok <= warning；warning <= breach；其余 breached。"""
    if minutes <= warning_minutes():
        return "ok"
    if minutes <= breach_minutes():
        return "warning"
    return "breached"


def sla_bounds(now: Optional[datetime] = None) -> Tuple[str, str, str]:
    """把三档阈值换算成时间区间（供计数复用同一过滤条件）。

    Returns:
        (warning_from, warning_to, breached_to)
        - warning 档：基准时间 ∈ (warning_from, warning_to]
        - breached 档：基准时间 <= breached_to
    """
    reference = now or utcnow()
    breached_to = reference - timedelta(minutes=breach_minutes())
    warning_to = reference - timedelta(minutes=warning_minutes())
    return iso_utc(breached_to), iso_utc(warning_to), iso_utc(breached_to)


def _resolution_at(resolution: Optional[Dict[str, Any]]) -> Optional[datetime]:
    """取 `resolution.at`（缺失/不可解析返回 None，naive 时间按 UTC 归一）。"""
    if not isinstance(resolution, dict):
        return None
    parsed = parse_iso(resolution.get("at"))
    if parsed is None:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def decided_wait(
    resolution: Optional[Dict[str, Any]],
    updated_at: datetime,
    now: Optional[datetime] = None,
    decision_id: str = "",
) -> Tuple[Optional[int], int]:
    """次队列计时：返回 `(decided_waited_minutes, 用于 SLA 判定的分钟数)`。

    - `decided_waited_minutes` 自 `resolution.at` 起算；无该字段返回 `None`
      （前端整块不显示 SLA 标记，绝不拿 `waited_minutes` 顶替——那是另一个语义）
    - SLA 判定不能留空：缺 `resolution.at` 的异常记录回落 `updated_at` 并告警，
      与计数侧 `coalesce(n.decided_at, n.updated_at)` 保持同一口径，否则
      "徽标说超时、计数说没超时"会同时出现在同一个响应里
    """
    reference = now or utcnow()
    decided_at = _resolution_at(resolution)
    if decided_at is None:
        logger.warning(
            "决策 %s 缺 resolution.at，SLA 计时回落 updated_at", decision_id or "<unknown>"
        )
        return None, waited_minutes(updated_at, reference)
    minutes = waited_minutes(decided_at, reference)
    return minutes, minutes
