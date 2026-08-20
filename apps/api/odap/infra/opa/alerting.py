#!/usr/bin/env python3
"""
OPA 告警管理器

白皮书 §5: 自动化告警
- 5 分钟内 DENY > 阈值 → Webhook SOC
- OPA 不可用 → 告警
- 决策延迟飙升 → 告警
- 审计写入失败 → 告警

告警通道：
1. WebSocket event_bus 实时推送前端
2. 审计日志 WARN 事件
3. Webhook（可配置 SOC URL）

P2-06: DENY 原因回传 Agent 上下文
"""

import time
import threading
import logging
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# 告警阈值默认值
ALERT_THRESHOLDS = {
    "deny_storm_5min": 50,       # 5 分钟内 DENY > 50 触发
    "latency_p95_ms": 500,       # P95 延迟 > 500ms 触发
    "audit_failure_count": 10,   # 审计失败 > 10 触发
    "opa_unavailable": True,     # OPA 不可用立即触发
}


@dataclass
class OPAAlert:
    level: str          # "warning" | "critical"
    type: str           # "deny_storm" | "opa_unavailable" | "latency_spike" | "audit_failure"
    message: str
    timestamp: str
    metrics_snapshot: Dict[str, Any]


class OPAAlertManager:
    """OPA 告警管理器（后台线程轮询指标）"""

    _instance: Optional['OPAAlertManager'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init(*args, **kwargs)
        return cls._instance

    def _init(self, check_interval: int = 60, webhook_url: str = None):
        self.check_interval = check_interval
        self.webhook_url = webhook_url
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_alerts: Dict[str, float] = {}
        self._dedup_window = 300  # 5 分钟去重

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("OPA 告警管理器已启动")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        while self._running:
            try:
                from odap.infra.opa.metrics import get_metrics
                metrics = get_metrics(300)
                alerts = self._evaluate(metrics)
                for alert in alerts:
                    self._emit(alert)
            except Exception as e:
                logger.error(f"告警检查异常: {e}")
            time.sleep(self.check_interval)

    def _evaluate(self, metrics: Dict) -> list:
        alerts = []
        now = time.time()

        if metrics["deny_count"] >= ALERT_THRESHOLDS["deny_storm_5min"]:
            if self._should_alert("deny_storm", now):
                alerts.append(OPAAlert(
                    level="critical", type="deny_storm",
                    message=f"5分钟内 DENY 决策 {metrics['deny_count']} 次，超过阈值 {ALERT_THRESHOLDS['deny_storm_5min']}",
                    timestamp=datetime.now().isoformat(), metrics_snapshot=metrics,
                ))

        p95 = metrics.get("latency_ms", {}).get("p95", 0)
        if p95 >= ALERT_THRESHOLDS["latency_p95_ms"]:
            if self._should_alert("latency_spike", now):
                alerts.append(OPAAlert(
                    level="warning", type="latency_spike",
                    message=f"OPA P95 延迟 {p95}ms 超过阈值 {ALERT_THRESHOLDS['latency_p95_ms']}ms",
                    timestamp=datetime.now().isoformat(), metrics_snapshot=metrics,
                ))

        if metrics["audit_failures"] >= ALERT_THRESHOLDS["audit_failure_count"]:
            if self._should_alert("audit_failure", now):
                alerts.append(OPAAlert(
                    level="critical", type="audit_failure",
                    message=f"审计写入失败 {metrics['audit_failures']} 次，超过阈值 {ALERT_THRESHOLDS['audit_failure_count']}",
                    timestamp=datetime.now().isoformat(), metrics_snapshot=metrics,
                ))

        if metrics["opa_unavailable_count"] > 0:
            if self._should_alert("opa_unavailable", now):
                alerts.append(OPAAlert(
                    level="critical", type="opa_unavailable",
                    message=f"OPA 服务不可用 {metrics['opa_unavailable_count']} 次",
                    timestamp=datetime.now().isoformat(), metrics_snapshot=metrics,
                ))

        return alerts

    def _should_alert(self, alert_type: str, now: float) -> bool:
        last = self._last_alerts.get(alert_type, 0)
        if now - last < self._dedup_window:
            return False
        self._last_alerts[alert_type] = now
        return True

    def _emit(self, alert: OPAAlert):
        logger.log(
            logging.WARNING if alert.level == "warning" else logging.ERROR,
            f"OPA 告警 [{alert.type}] {alert.message}"
        )
        self._push_websocket(alert)
        self._write_audit(alert)
        if self.webhook_url:
            self._send_webhook(alert)

    def _push_websocket(self, alert: OPAAlert):
        try:
            import asyncio
            from odap.web.ws.event_bus import get_event_bus
            bus = get_event_bus()
            data = asdict(alert)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(bus.emit("opa:alert", data))
                else:
                    loop.run_until_complete(bus.emit("opa:alert", data))
            except RuntimeError:
                asyncio.run(bus.emit("opa:alert", data))
        except Exception as e:
            logger.warning(f"WebSocket 告警推送失败: {e}")

    def _write_audit(self, alert: OPAAlert):
        try:
            from odap.infra.security.unified_audit import log_audit
            log_audit(
                action=f"opa.alert.{alert.type}",
                resource="opa_engine",
                user="system",
                service="opa_alerting",
                result_status="warning" if alert.level == "warning" else "failure",
                result_message=alert.message,
                details=alert.metrics_snapshot,
            )
        except Exception as e:
            logger.warning(f"告警审计写入失败: {e}")

    def _send_webhook(self, alert: OPAAlert):
        try:
            import httpx
            httpx.post(self.webhook_url, json=asdict(alert), timeout=5.0)
        except Exception as e:
            logger.warning(f"Webhook 告警发送失败: {e}")


__all__ = ["OPAAlertManager", "OPAAlert", "ALERT_THRESHOLDS"]
