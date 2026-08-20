# Phase 2 — 可观测与告警详细 Spec

> **目标**：Grafana/Loki 可观测栈 + OPA 决策监控仪表盘 + 自动化告警 + 前端监控页 + ABAC 增强
> **优先级**：P1
> **前置条件**：Phase 1 完成

---

## P2-01：OPA 指标采集器

### 新建 `apps/api/odap/infra/opa/metrics.py`

```python
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
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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

            # 按 package 分组
            by_package = defaultdict(lambda: {"allow": 0, "deny": 0})
            for d in recent:
                key = "allow" if d.allowed else "deny"
                by_package[d.package][key] += 1

            # DENY 原因 Top 5
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
            "deny_rate_5min": len(recent_deny_ts),  # 用于告警
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

    def get_cache_metrics(self, opa_manager) -> Dict[str, Any]:
        """获取缓存指标（委托给 OPAManager）"""
        return opa_manager.get_cache_stats()


def _percentile(sorted_list: list, pct: float) -> float:
    if not sorted_list:
        return 0
    idx = int(len(sorted_list) * pct / 100)
    idx = min(idx, len(sorted_list) - 1)
    return round(sorted_list[idx], 2)


# 模块级便捷函数
def record_decision(allowed: bool, duration_ms: float, package: str = "domain", reason: str = ""):
    OPAMetricsCollector().record_decision(allowed, duration_ms, package, reason)

def increment_audit_failure(error: str = ""):
    OPAMetricsCollector().increment_audit_failure(error)

def increment_opa_unavailable():
    OPAMetricsCollector().increment_opa_unavailable()

def get_metrics(window_seconds: int = 300) -> Dict[str, Any]:
    return OPAMetricsCollector().get_metrics(window_seconds)
```

### 接入 OPAManager

在 `opa_service.py` 的 `check_permission` / `check_permission_abac` / `check_package_permission` 中，决策完成后调用：

```python
from odap.infra.opa.metrics import record_decision
import time as _time

def check_permission_abac(self, user, action, resource, environment=None):
    _start = _time.monotonic()
    # ... 现有逻辑 ...
    _duration_ms = (_time.monotonic() - _start) * 1000
    record_decision(
        allowed=result.get("allow", False),
        duration_ms=_duration_ms,
        package="domain.abac",
        reason=result.get("reason", ""),
    )
    return result
```

### OPA 监控 API 路由

新建 `apps/api/odap/infra/opa/api/routes.py`：

```python
from fastapi import APIRouter, Depends
from odap.infra.security.jwt_auth import get_current_user
from odap.infra.opa.metrics import get_metrics, OPAMetricsCollector

router = APIRouter(prefix="/api/opa", tags=["opa-metrics"])

@router.get("/metrics")
async def opa_metrics(window: int = 300, user=Depends(get_current_user)):
    """获取 OPA 决策指标"""
    return get_metrics(window)

@router.get("/health")
async def opa_health(user=Depends(get_current_user)):
    """OPA 服务健康状态"""
    from odap.infra.opa.opa_service import OPAManager
    mgr = OPAManager()
    return {
        "opa_reachable": not getattr(mgr, '_opa_unavailable', False),
        "bundle_version": mgr.get_bundle_version(),
        "mode": "mock" if mgr.use_mock else "opa",
    }
```

---

## P2-02：OPA 告警管理器

### 新建 `apps/api/odap/infra/opa/alerting.py`

```python
"""
OPA 告警管理器

白皮书 §5: 自动化告警
- 5 分钟内 DENY > 阈值 → Webhook SOC
- OPA 不可用 → 告警
- 决策延迟飙升 → 告警

告警通道：
1. WebSocket event_bus 实时推送前端
2. 审计日志 WARN 事件
3. Webhook（可配置 SOC URL）
"""

import asyncio
import time
import threading
from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import logging

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
        self._last_alerts: Dict[str, float] = {}  # 去重: type -> last_ts
        self._dedup_window = 300  # 5 分钟去重

    def start(self):
        """启动后台告警检查线程"""
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
        import httpx
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
        """评估指标是否触发告警"""
        alerts = []
        now = time.time()

        # DENY 风暴
        if metrics["deny_count"] >= ALERT_THRESHOLDS["deny_storm_5min"]:
            if self._should_alert("deny_storm", now):
                alerts.append(OPAAlert(
                    level="critical",
                    type="deny_storm",
                    message=f"5分钟内 DENY 决策 {metrics['deny_count']} 次，超过阈值 {ALERT_THRESHOLDS['deny_storm_5min']}",
                    timestamp=datetime.now().isoformat(),
                    metrics_snapshot=metrics,
                ))

        # 延迟飙升
        p95 = metrics.get("latency_ms", {}).get("p95", 0)
        if p95 >= ALERT_THRESHOLDS["latency_p95_ms"]:
            if self._should_alert("latency_spike", now):
                alerts.append(OPAAlert(
                    level="warning",
                    type="latency_spike",
                    message=f"OPA P95 延迟 {p95}ms 超过阈值 {ALERT_THRESHOLDS['latency_p95_ms']}ms",
                    timestamp=datetime.now().isoformat(),
                    metrics_snapshot=metrics,
                ))

        # 审计失败
        if metrics["audit_failures"] >= ALERT_THRESHOLDS["audit_failure_count"]:
            if self._should_alert("audit_failure", now):
                alerts.append(OPAAlert(
                    level="critical",
                    type="audit_failure",
                    message=f"审计写入失败 {metrics['audit_failures']} 次，超过阈值 {ALERT_THRESHOLDS['audit_failure_count']}",
                    timestamp=datetime.now().isoformat(),
                    metrics_snapshot=metrics,
                ))

        # OPA 不可用
        if metrics["opa_unavailable_count"] > 0:
            if self._should_alert("opa_unavailable", now):
                alerts.append(OPAAlert(
                    level="critical",
                    type="opa_unavailable",
                    message=f"OPA 服务不可用 {metrics['opa_unavailable_count']} 次",
                    timestamp=datetime.now().isoformat(),
                    metrics_snapshot=metrics,
                ))

        return alerts

    def _should_alert(self, alert_type: str, now: float) -> bool:
        """告警去重（同类型 5 分钟内不重复）"""
        last = self._last_alerts.get(alert_type, 0)
        if now - last < self._dedup_window:
            return False
        self._last_alerts[alert_type] = now
        return True

    def _emit(self, alert: OPAAlert):
        """发送告警（3 通道）"""
        logger.log(
            logging.WARNING if alert.level == "warning" else logging.ERROR,
            f"OPA 告警 [{alert.type}] {alert.message}"
        )

        # 通道 1: WebSocket 推送
        self._push_websocket(alert)

        # 通道 2: 审计日志
        self._write_audit(alert)

        # 通道 3: Webhook
        if self.webhook_url:
            self._send_webhook(alert)

    def _push_websocket(self, alert: OPAAlert):
        try:
            import asyncio
            from odap.web.ws.event_bus import get_event_bus
            bus = get_event_bus()
            data = alert.__dict__
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
            httpx.post(self.webhook_url, json=alert.__dict__, timeout=5.0)
        except Exception as e:
            logger.warning(f"Webhook 告警发送失败: {e}")
```

### 启动注册

在 `apps/api/odap/web/app.py` 的 `lifespan` 中启动告警管理器：

```python
from odap.infra.opa.alerting import OPAAlertManager
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... 现有初始化 ...
    alert_mgr = OPAAlertManager(
        check_interval=60,
        webhook_url=os.environ.get("OPA_ALERT_WEBHOOK_URL"),
    )
    alert_mgr.start()
    yield
    alert_mgr.stop()
```

### DENY 原因回传 Agent 上下文（P2-06）

在 PEP 的 `_audit` 中，当 `blocked_at="opa"` 时，通过 WebSocket 推送 DENY 事件给 Agent 前端：

```python
# pep.py — _audit 方法增强
def _audit(self, req, result):
    # ... 现有审计写入 ...
    if not result.allowed and result.blocked_at == "opa":
        self._push_deny_to_agent(req, result)

def _push_deny_to_agent(self, req, result):
    """白皮书 §3: DENY 原因反馈 Agent 上下文"""
    try:
        import asyncio
        from odap.web.ws.event_bus import get_event_bus
        bus = get_event_bus()
        data = {
            "agent_id": req.agent_id,
            "trace_id": req.trace_id,
            "tool_name": req.tool_name,
            "reason": result.reason,
            "opa_decision": result.opa_decision,
        }
        # 推送到 agent:{agent_id} 频道
        asyncio.ensure_future(bus.emit(f"agent:{req.agent_id}:denied", data))
    except Exception as e:
        logger.warning(f"DENY 回传失败: {e}")
```

---

## P2-03 / P2-04：Loki + Promtail + Grafana 可观测栈

### 新建 `docker/docker-compose.observability.yml`

```yaml
# 可观测性栈 — 白皮书 §4 基础设施
# 使用: docker-compose -f docker-compose.yml -f docker-compose.observability.yml up -d

services:
  loki:
    image: grafana/loki:2.9.0
    container_name: graphiti-loki
    ports:
      - "3100:3100"
    volumes:
      - loki-data:/loki
      - ./loki/loki-config.yml:/etc/loki/local-config.yaml
    command: -config.file=/etc/loki/local-config.yaml
    restart: unless-stopped

  promtail:
    image: grafana/promtail:2.9.0
    container_name: graphiti-promtail
    volumes:
      - ./promtail/promtail-config.yml:/etc/promtail/config.yml
      - ../apps/api/logs:/var/log/odap  # 挂载 ODAP 日志目录
    command: -config.file=/etc/promtail/config.yml
    depends_on:
      - loki
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.2.0
    container_name: graphiti-grafana
    ports:
      - "3001:3000"  # 避免与前端 5173 冲突，用 3001
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
      - GF_AUTH_ANONYMOUS_ENABLED=true
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
    depends_on:
      - loki
    restart: unless-stopped

volumes:
  loki-data:
  grafana-data:
```

### 新建 `docker/promtail/promtail-config.yml`

```yaml
# Promtail 配置 — 采集 ODAP 审计日志推送至 Loki
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: odap_audit
    static_configs:
      - targets: [localhost]
        labels:
          job: odap_audit
          __path__: /var/log/odap/*.log
    pipeline_stages:
      # 解析 JSON 格式审计日志
      - json:
          expressions:
            level: level
            timestamp: timestamp
            action: action
            actor_id: actor_id
            service: service
            result_status: result_status
            trace_id: trace_id
      # 提取标签
      - labels:
          level:
          service:
          result_status:
```

### 新建 `docker/grafana/provisioning/datasources/loki.yml`

```yaml
apiVersion: 1
datasources:
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    isDefault: true
    editable: true
```

### 新建 `docker/grafana/provisioning/dashboards/dashboards.yml`

```yaml
apiVersion: 1
providers:
  - name: 'ODAP Security Dashboards'
    folder: 'Security'
    type: file
    options:
      path: /var/lib/grafana/dashboards
```

### 新建 `docker/grafana/dashboards/opa-security.json`

> 仪表盘包含 4 个面板（白皮书 §4 要求）：
> 1. 决策分布饼图（Allow vs Deny）
> 2. 实时审计日志流
> 3. 工具调用热度排行
> 4. 高危拦截（DENY）时序图

```json
{
  "title": "OPA Security Operations Dashboard",
  "timezone": "browser",
  "schemaVersion": 38,
  "panels": [
    {
      "title": "决策分布 (Allow vs Deny)",
      "type": "piechart",
      "datasource": {"type": "loki", "uid": "loki"},
      "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0},
      "targets": [{
        "expr": "sum by (result_status) (count_over_time({job=\"odap_audit\"} |= \"opa\" [5m]))",
        "legendFormat": "{{result_status}}"
      }]
    },
    {
      "title": "实时审计日志流",
      "type": "logs",
      "datasource": {"type": "loki", "uid": "loki"},
      "gridPos": {"h": 8, "w": 18, "x": 6, "y": 0},
      "targets": [{
        "expr": "{job=\"odap_audit\"} |= \"opa\""
      }]
    },
    {
      "title": "工具调用热度排行",
      "type": "bargauge",
      "datasource": {"type": "loki", "uid": "loki"},
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
      "targets": [{
        "expr": "topk(10, sum by (action) (count_over_time({job=\"odap_audit\"} [1h])))",
        "legendFormat": "{{action}}"
      }]
    },
    {
      "title": "DENY 时序图 (5min 滚动)",
      "type": "timeseries",
      "datasource": {"type": "loki", "uid": "loki"},
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
      "targets": [{
        "expr": "sum(count_over_time({job=\"odap_audit\"} |= \"deny\" [5m]))",
        "legendFormat": "DENY count"
      }]
    }
  ],
  "time": {"from": "now-1h", "to": "now"},
  "refresh": "10s"
}
```

### Grafana Alerting 规则

在 Grafana 中配置告警（或通过 provisioning）：

```yaml
# docker/grafana/provisioning/alerting/opa-alerts.yml
apiVersion: 1
groups:
  - name: OPA Security Alerts
    interval: 60s
    rules:
      - alert: OPADenyStorm
        expr: sum(count_over_time({job="odap_audit"} |= "deny" [5m])) > 50
        for: 1m
        annotations:
          summary: "OPA DENY 风暴: 5分钟内超过 50 次拒绝"
        labels:
          severity: critical
      - alert: OPAAuditFailure
        expr: sum(count_over_time({job="odap_audit"} |= "audit_failure" [5m])) > 10
        for: 1m
        annotations:
          summary: "审计写入失败超过 10 次"
        labels:
          severity: critical
```

---

## P2-05：前端 OPA 监控页

### 新建 `apps/web/src/modules/audit/pages/OPAMonitorPage.tsx`

```tsx
// 白皮书 §4: Grafana 安全运营看板的前端轻量版
// 展示 OPA 实时指标，弥补 Grafana 不可用时的可视化

import { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Progress, Alert, Button, Space } from 'antd';
import { ReloadOutlined, WarningOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

export function OPAMonitorPage() {
  const { t } = useI18n();
  const [metrics, setMetrics] = useState<any>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const loadMetrics = async () => {
    setLoading(true);
    try {
      const data = await apiClient.get('/api/opa/metrics?window=300');
      setMetrics(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMetrics();
    const timer = setInterval(loadMetrics, 10000); // 10s 刷新
    return () => clearInterval(timer);
  }, []);

  const denyRate = metrics?.deny_rate_percent ?? 0;
  const denyRateColor = denyRate > 30 ? '#ff4d4f' : denyRate > 10 ? '#faad14' : '#52c41a';

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ReloadOutlined />} onClick={loadMetrics} loading={loading}>
          {t('刷新')}
        </Button>
      </Space>

      {denyRate > 30 && (
        <Alert
          type="error"
          message={t('DENY 率异常')}
          description={`${denyRate}% 的请求被拒绝，请检查策略配置`}
          showIcon
          icon={<WarningOutlined />}
          style={{ marginBottom: 16 }}
        />
      )}

      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card><Statistic title={t('总决策数')} value={metrics?.total_decisions ?? 0} loading={loading} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title={t('允许')} value={metrics?.allow_count ?? 0} loading={loading}
            styles={{ content: { color: '#52c41a' } }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title={t('拒绝')} value={metrics?.deny_count ?? 0} loading={loading}
            styles={{ content: { color: '#ff4d4f' } }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title={t('拒绝率')} value={`${denyRate}%`} loading={loading}
            styles={{ content: { color: denyRateColor } }} /></Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={8}>
          <Card title={t('延迟 (ms)')} size="small">
            <p>P50: {metrics?.latency_ms?.p50 ?? 0}</p>
            <p>P95: {metrics?.latency_ms?.p95 ?? 0}</p>
            <p>P99: {metrics?.latency_ms?.p99 ?? 0}</p>
            <p>平均: {metrics?.latency_ms?.avg ?? 0}</p>
          </Card>
        </Col>
        <Col span={8}>
          <Card title={t('审计失败')} size="small">
            <Statistic value={metrics?.audit_failures ?? 0}
              valueStyle={{ color: (metrics?.audit_failures ?? 0) > 0 ? '#ff4d4f' : '#52c41a' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card title={t('OPA 不可用次数')} size="small">
            <Statistic value={metrics?.opa_unavailable_count ?? 0}
              valueStyle={{ color: (metrics?.opa_unavailable_count ?? 0) > 0 ? '#ff4d4f' : '#52c41a' }} />
          </Card>
        </Col>
      </Row>

      <Card title={t('DENY 原因 Top 5')} style={{ marginTop: 16 }}>
        <Table
          dataSource={metrics?.top_deny_reasons || []}
          columns={[
            { title: t('原因'), dataIndex: 'reason', key: 'reason' },
            { title: t('次数'), dataIndex: 'count', key: 'count', width: 100 },
          ]}
          rowKey="reason"
          pagination={false}
          size="small"
        />
      </Card>

      <Card title={t('按策略包统计')} style={{ marginTop: 16 }}>
        <Table
          dataSource={Object.entries(metrics?.by_package || {}).map(([pkg, counts]: any) => ({
            package: pkg, ...counts,
          }))}
          columns={[
            { title: t('策略包'), dataIndex: 'package', key: 'package' },
            { title: t('允许'), dataIndex: 'allow', key: 'allow', width: 100,
              render: (v) => <Tag color="green">{v}</Tag> },
            { title: t('拒绝'), dataIndex: 'deny', key: 'deny', width: 100,
              render: (v) => <Tag color="red">{v}</Tag> },
          ]}
          rowKey="package"
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  );
}
```

### 路由注册

`apps/web/src/AppRoutes.tsx` 增加：

```tsx
{ path: '/audit/opa-monitor', element: <OPAMonitorPage /> }
```

---

## P2-07：ABAC 补充会话时长维度

### 修改 `apps/api/odap/infra/opa/policies/abac_policy.rego`

```rego
# 白皮书 §2.2: 环境感知 — 高敏操作强制要求会话时长 > 5 分钟
# 高敏操作列表
high_privilege_actions := {
    "refund", "send_email", "delete_user", "transfer_money",
    "approve_mission", "authorize_engagements",
}

# 高敏操作额外检查
allow if {
    clearance_sufficient
    workspace_isolated
    action_permitted
    environment_ok
    high_privilege_check
}

# 高敏操作要求会话时长 > 300 秒（5 分钟）
high_privilege_check if {
    not input.action.type in high_privilege_actions
}

high_privilege_check if {
    input.action.type in high_privilege_actions
    input.environment.session_duration_seconds >= 300
}

# 新增 deny 原因
deny if {
    input.action.type in high_privilege_actions
    input.environment.session_duration_seconds < 300
}

deny_reasons := [reason |
    reason := "insufficient_session_duration"
    input.action.type in high_privilege_actions
    input.environment.session_duration_seconds < 300
]
```

### 涉及文件

| 文件 | 操作 |
|------|------|
| `apps/api/odap/infra/opa/policies/abac_policy.rego` | 修改 |
| `apps/api/odap/infra/opa/opa_service.py` `ABACService` | 传递 session_duration |

---

## Phase 2 验收标准

- [ ] `GET /api/opa/metrics` 返回完整指标
- [ ] OPA 不可用时 `OPAMetricsCollector.increment_opa_unavailable` 触发告警
- [ ] 5 分钟内 DENY > 50 时 `OPAAlertManager` 发出 critical 告警
- [ ] 告警通过 WebSocket 推送前端 + 写审计 + 发 Webhook（如配置）
- [ ] `docker-compose.observability.yml` 启动 Loki + Promtail + Grafana 正常
- [ ] Grafana 仪表盘展示 4 个面板（决策分布/日志流/工具热度/DENY 时序）
- [ ] 前端 `/audit/opa-monitor` 页面展示实时指标
- [ ] ABAC 策略对 `refund` 等高敏操作在 session_duration < 300s 时 DENY
- [ ] Phase 2 单元测试 + 集成测试通过
