#!/usr/bin/env python3
"""
OPA 指标采集器

白皮书 §3: 异步采集与告警
白皮书 §4: Grafana 可视化展示

采集指标：
- 决策计数 (allow/deny 按 package 分组)
- 决策延迟 (p50/p95/p99)
- 缓存命中率
- OPA 服务健康状态
- 审计写入失败计数
- DENY 率 (滚动窗口)
"""

import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class DecisionRecord:
    timestamp: float
    allowed: bool
    duration_ms: float
    package: str
    reason: str


def _percentile(sorted_list: list, pct: float) -> float:
    if not sorted_list:
        return 0
    idx = int(len(sorted_list) * pct / 100)
    idx = min(idx, len(sorted_list) - 1)
    return round(sorted_list[idx], 2)


class OPAMetricsCollector:
    """OPA 决策指标采集器（线程安全单例）"""

    _instance: Optional['OPAMetricsCollector'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._decisions: deque = deque(maxlen=10000)
        self._deny_timestamps: deque = deque(maxlen=10000)
        self._audit_failures = 0
        self._opa_unavailable_count = 0
        self._lock_data = threading.Lock()

    def record_decision(self, allowed: bool, duration_ms: float,
                        package: str = "domain", reason: str = ""):
        """记录一次 OPA 决策"""
        with self._lock_data:
            rec = DecisionRecord(
                timestamp=time.time(),
                allowed=allowed,
                duration_ms=duration_ms,
                package=package,
                reason=reason,
            )
            self._decisions.append(rec)
            if not allowed:
                self._deny_timestamps.append(time.time())

    def increment_audit_failure(self, error: str = ""):
        """审计写入失败计数"""
        with self._lock_data:
            self._audit_failures += 1
            logger.warning(f"审计写入失败 #{self._audit_failures}: {error}")

    def increment_opa_unavailable(self):
        """OPA 不可用计数"""
        with self._lock_data:
            self._opa_unavailable_count += 1

    def get_metrics(self, window_seconds: int = 300) -> Dict[str, Any]:
        """获取指标快照（默认 5 分钟窗口）"""
        now = time.time()
        cutoff = now - window_seconds

        with self._lock_data:
            recent = [d for d in self._decisions if d.timestamp >= cutoff]
            denies = [d for d in recent if not d.allowed]
            recent_deny_ts = [t for t in self._deny_timestamps if t >= cutoff]

            durations = [d.duration_ms for d in recent if d.duration_ms > 0]
            durations_sorted = sorted(durations)

            by_package = defaultdict(lambda: {"allow": 0, "deny": 0})
            for d in recent:
                key = "allow" if d.allowed else "deny"
                by_package[d.package][key] += 1

            deny_reasons = defaultdict(int)
            for d in denies:
                deny_reasons[d.reason] += 1
            top_deny_reasons = sorted(deny_reasons.items(), key=lambda x: -x[1])[:5]

        total = len(recent)
        deny_count = len(denies)
        deny_rate = (deny_count / total * 100) if total > 0 else 0

        return {
            "window_seconds": window_seconds,
            "window_start": datetime.fromtimestamp(cutoff).isoformat(),
            "window_end": datetime.fromtimestamp(now).isoformat(),
            "total_decisions": total,
            "allow_count": total - deny_count,
            "deny_count": deny_count,
            "deny_rate_percent": round(deny_rate, 2),
            "deny_rate_5min": len(recent_deny_ts),
            "latency_ms": {
                "p50": _percentile(durations_sorted, 50),
                "p95": _percentile(durations_sorted, 95),
                "p99": _percentile(durations_sorted, 99),
                "avg": round(sum(durations) / len(durations), 2) if durations else 0,
            },
            "by_package": dict(by_package),
            "top_deny_reasons": [{"reason": r, "count": c} for r, c in top_deny_reasons],
            "audit_failures": self._audit_failures,
            "opa_unavailable_count": self._opa_unavailable_count,
        }


# ---------------------------------------------------------------------------
# 模块级便捷函数
# ---------------------------------------------------------------------------

def record_decision(allowed: bool, duration_ms: float, package: str = "domain", reason: str = ""):
    OPAMetricsCollector().record_decision(allowed, duration_ms, package, reason)

def increment_audit_failure(error: str = ""):
    OPAMetricsCollector().increment_audit_failure(error)

def increment_opa_unavailable():
    OPAMetricsCollector().increment_opa_unavailable()

def get_metrics(window_seconds: int = 300) -> Dict[str, Any]:
    return OPAMetricsCollector().get_metrics(window_seconds)


__all__ = [
    "OPAMetricsCollector",
    "DecisionRecord",
    "record_decision",
    "increment_audit_failure",
    "increment_opa_unavailable",
    "get_metrics",
]
