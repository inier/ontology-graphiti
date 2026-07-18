# ODAP 运维架构设计

> **版本**: 1.0.0 | **日期**: 2026-05-07 | **状态**: 设计稿
> **对应需求**: NFR-P05 (可用性 99.9%), NFR-M04 (Docker/K8s), WR-08 (范围完整性)
> **上级文档**: [ARCHITECTURE.md](ARCHITECTURE.md)

---

## 目录

1. [监控告警系统](#1-监控告警系统)
2. [日志收集管道](#2-日志收集管道)
3. [备份与恢复策略](#3-备份与恢复策略)
4. [部署拓扑](#4-部署拓扑)
5. [健康检查与自愈](#5-健康检查与自愈)

---

## 1. 监控告警系统

### 1.1 监控架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          监控采集架构                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │  FastAPI App     │    │  Neo4j           │    │  OPA Server      │  │
│  │  prometheus_fastapi│   │  neo4j-exporter  │    │  opa-exporter    │  │
│  │  _instrumentator │    │  (metrics)       │    │  (metrics)       │  │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘  │
│           │                       │                       │            │
│           └───────────────────────┼───────────────────────┘            │
│                                   ▼                                    │
│                          ┌──────────────────┐                          │
│                          │    Prometheus    │                          │
│                          │  (pull /metrics) │                          │
│                          └────────┬─────────┘                          │
│                                   │                                    │
│                    ┌──────────────┼──────────────┐                     │
│                    ▼              ▼              ▼                     │
│            ┌──────────┐  ┌──────────┐  ┌──────────────┐              │
│            │ Grafana  │  │AlertManager│ │ Node Exporter│              │
│            │ Dashboard │  │ 告警规则   │ │ 主机指标      │              │
│            └──────────┘  └─────┬────┘  └──────────────┘              │
│                                │                                       │
│                    通知渠道: 企业微信 / 邮件 / Webhook                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心指标 (Golden Signals)

| 类别 | 指标 | 采集来源 | 告警阈值 |
|------|------|---------|---------|
| **延迟** | P50/P95/P99 响应时间 | FastAPI (histogram) | P95 > 3s |
| **流量** | QPS (requests/sec) | FastAPI (counter) | 与基线偏离 > 50% |
| **错误** | 5xx 错误率 | FastAPI (counter) | > 1% / 5min |
| **饱和度** | CPU / Memory / DB 连接池 | Node Exporter / Neo4j | CPU > 80% / Mem > 85% |
| **业务** | 问答成功率 / Skill 执行成功率 | 应用埋点 | 成功率 < 95% |

### 1.3 Prometheus 配置

```yaml
# docker/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "odap-api"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["odap-api:8000"]
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: "http_request_duration_seconds.*"
        action: keep

  - job_name: "neo4j"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["neo4j-exporter:2004"]
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: "neo4j_(node_count|relationship_count|db_size|tx_.*)"
        action: keep

  - job_name: "opa"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["opa:8181"]

  - job_name: "node"
    static_configs:
      - targets: ["node-exporter:9100"]
```

### 1.4 告警规则

```yaml
# docker/prometheus/alerts.yml
groups:
  - name: odap-critical
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "API 5xx 错误率超过 1% (当前 {{ $value | humanizePercentage }})"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P95 API 延迟超过 3 秒 (当前 {{ $value }}s)"

      - alert: Neo4jLowDisk
        expr: neo4j_db_size_bytes / neo4j_disk_total_bytes > 0.8
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Neo4j 磁盘使用率超过 80%"

      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "服务 {{ $labels.instance }} 已宕机"
```

### 1.5 Grafana Dashboard 推荐面板

| 面板 | 类型 | 数据源 |
|------|------|--------|
| API QPS & Latency Overview | Time Series | Prometheus |
| Error Rate by Endpoint | Heatmap | Prometheus |
| Neo4j Node/Edge Growth | Stat + Graph | Prometheus |
| LLM Token Usage & Cost | Bar Gauge | 应用自定义指标 |
| Workspace Resource Usage | Table | 应用自定义指标 |
| Skill Execution Success Rate | Gauge | 应用自定义指标 |

---

## 2. 日志收集管道

### 2.1 日志架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          日志收集架构                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐                                                   │
│  │   应用容器        │  Python structlog → stdout (JSON Lines)          │
│  │   结构化日志      │                                                   │
│  └────────┬─────────┘                                                   │
│           │ Docker logging driver (json-file / loki)                    │
│           ▼                                                             │
│  ┌──────────────────┐                                                   │
│  │   Loki / Vector   │  日志聚合 + 标签索引                             │
│  └────────┬─────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐     ┌──────────────────┐                        │
│  │     Grafana      │     │  Elasticsearch   │ (可选，高级搜索)        │
│  │   (日志查看)      │     │      + Kibana    │                        │
│  └──────────────────┘     └──────────────────┘                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 结构化日志格式

```python
import structlog
import uuid

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()

# 使用示例
logger.info("qa.answer.generated",
    session_id=str(uuid4()),
    workspace_id="ws_abc12345",
    tokens_used=1523,
    latency_ms=2340,
    entities_linked=5,
    skill_suggestions=2,
)
```

### 2.3 日志级别策略

| 环境 | 控制台 | 文件 | 聚合 |
|------|:------:|:----:|:----:|
| 开发 | DEBUG | — | — |
| 测试 | INFO | JSON | Loki |
| 生产 | INFO | JSON | Loki + ES |
| 生产 (DEBUG 排查) | DEBUG (动态切换) | JSON | Loki + ES |

### 2.4 日志保留策略

| 存储 | 保留周期 | 说明 |
|------|---------|------|
| Docker stdout | 最后 10MB | 容器重启后丢失 |
| Loki | 30 天 | 按时间分区，自动清理 |
| Elasticsearch | 90 天 (审计日志) / 30 天 (应用日志) | ILM 策略自动管理 |
| 审计日志 (DB) | 永久 | 合规要求，可归档到冷存储 |

---

## 3. 备份与恢复策略

### 3.1 备份对象与策略

| 备份对象 | 策略 | 频率 | RPO | RTO | 工具 |
|---------|------|:----:|:---:|:---:|------|
| **Neo4j 图数据** | 全量 + 增量 (WAL) | 每日全量 / 每小时增量 | 1h | 30min | `neo4j-admin backup` |
| **PostgreSQL 元数据** | 全量 dump | 每日 | 24h | 15min | `pg_dump` |
| **OPA Bundle** | Git 版本控制 | 每次变更 | — | — | Git + 文件系统快照 |
| **Skill 配置文件** | Git 版本控制 | 每次变更 | — | — | Git |
| **审计日志 (DB)** | 全量 dump + 归档 | 每周全量 | 7d | 2h | `pg_dump` |

### 3.2 Neo4j 备份

```bash
# docker-compose.ops.yml
services:
  neo4j-backup:
    image: neo4j:5-enterprise
    entrypoint: /bin/bash
    command:
      - -c
      - |
        while true; do
          DATE=$$(date +%Y%m%d)
          neo4j-admin database backup \
            --from=neo4j:7687 \
            --to-path=/backups/full/$$DATE \
            --database=neo4j
          find /backups/full -mtime +7 -exec rm -rf {} \;
          sleep 86400
        done
    volumes:
      - ./backups/neo4j:/backups
```

### 3.3 Neo4j 恢复

```bash
# 恢复步骤
1. 停止 ODAP API 容器
2. neo4j-admin database restore --from-path=/backups/full/20260501/neo4j --database=neo4j --force
3. 重新启动 ODAP API 容器
4. 运行一致性检查: neo4j-admin database check neo4j
5. 健康检查通过后恢复服务
```

### 3.4 PostgreSQL 备份

```bash
# 每日备份脚本 (cron in backup container)
#!/bin/bash
BACKUP_DIR="/backups/postgres/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h postgres -U odap -d odap_meta \
  --format=custom --compress=9 \
  -f "$BACKUP_DIR/odap_meta.dump"

# 保留最近 14 天
find /backups/postgres -maxdepth 1 -mtime +14 -exec rm -rf {} \;
```

### 3.5 灾难恢复演练

| 场景 | 频率 | 步骤 |
|------|:----:|------|
| Neo4j 数据损坏 | 每季度 | 1. 从最新备份恢复 2. 重放 WAL 增量日志 3. 验证节点/边数量 |
| PostgreSQL 故障 | 每季度 | 1. pg_restore 恢复 2. 验证工作空间列表和用户表 |
| 全站灾难 | 每半年 | 1. 全新 Docker Compose 环境 2. 按序恢复所有组件 3. 端到端验证 |

---

## 4. 部署拓扑

### 4.1 Docker Compose 生产拓扑

```yaml
# docker-compose.prod.yml
services:
  odap-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - OPA_URL=http://opa:8181
      - POSTGRES_URL=postgresql://odap:${DB_PASSWORD}@postgres:5432/odap_meta
      - PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus
      - LOG_LEVEL=INFO
    volumes:
      - ./data/uploads:/app/data/uploads
      - ./data/skills:/app/data/skills
    depends_on:
      neo4j:
        condition: service_healthy
      opa:
        condition: service_healthy
      postgres:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 2G

  neo4j:
    image: neo4j:5-enterprise
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_server_memory_heap_initial__size=1G
      - NEO4J_server_memory_heap_max__size=2G
    volumes:
      - ./data/neo4j:/data
      - ./data/neo4j-logs:/logs
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "${NEO4J_PASSWORD}", "RETURN 1"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: unless-stopped

  opa:
    image: openpolicyagent/opa:latest
    command: run --server --log-level info /policies/bundle.tar.gz
    ports:
      - "8181:8181"
    volumes:
      - ./data/opa/policies:/policies
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8181/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=odap
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=odap_meta
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U odap -d odap_meta"]
      interval: 10s
      timeout: 5s
      retries: 5

  # — 运维组件 —
  prometheus:
    image: prom/prometheus
    volumes:
      - ./docker/prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    command: --config.file=/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    volumes:
      - grafana_data:/var/lib/grafana
      - ./docker/grafana/dashboards:/etc/grafana/provisioning/dashboards
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}

  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"

  # — 反向代理 —
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./docker/nginx/certs:/etc/nginx/certs
    depends_on:
      - odap-api

volumes:
  prometheus_data:
  grafana_data:
```

### 4.2 Nginx 配置

```nginx
# docker/nginx/nginx.conf
upstream odap_api {
    server odap-api:8000;
}

server {
    listen 443 ssl http2;
    server_name odap.example.com;

    ssl_protocols TLSv1.3;
    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    add_header Strict-Transport-Security "max-age=63072000" always;

    location /api/ {
        proxy_pass http://odap_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;               # SSE 流式响应需要
        proxy_read_timeout 300s;           # 长连接超时
    }

    location /ws/ {
        proxy_pass http://odap_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_read_timeout 86400s;         # WebSocket 长连接
    }

    location / {
        root /usr/share/nginx/html;
        try_files $uri /index.html;
    }
}

server {
    listen 80;
    return 301 https://$host$request_uri;
}
```

---

## 5. 健康检查与自愈

### 5.1 健康检查端点

```python
# apps/api/odap/web/health.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "2.0.0"}

@router.get("/health/ready")
async def readiness_check():
    """就绪探针：检查所有依赖服务可用"""
    checks = {
        "neo4j": await check_neo4j_connectivity(),
        "opa": await check_opa_health(),
        "postgres": await check_postgres_connectivity(),
    }
    all_ready = all(checks.values())
    status_code = 200 if all_ready else 503
    return JSONResponse({"ready": all_ready, "checks": checks}, status_code=status_code)

@router.get("/health/live")
async def liveness_check():
    """存活探针：仅检查进程存活"""
    return {"alive": True}
```

### 5.2 自愈策略

| 组件 | 检测方式 | 自愈动作 | 最大恢复时间 |
|------|---------|---------|:-----------:|
| odap-api | Docker healthcheck / K8s liveness probe | 自动重启容器 | < 30s |
| Neo4j | readiness check 失败 → API 503 | Docker restart policy | < 60s |
| OPA | readiness check 失败 → API 503 | Docker restart policy | < 30s |
| 内存泄漏 | Prometheus memory 持续上升 | AlertManager → 通知运维人工介入 | 按 SLO |

### 5.3 容量规划指南

| 规模 | 工作空间数 | Neo4j 堆内存 | API 实例数 |
|------|:--------:|:----------:|:--------:|
| 小 (POC) | 1-3 | 1G | 1 |
| 中 | 3-15 | 2-4G | 1-2 |
| 大 | 15-50 | 4-8G | 2-4 |

---

## 6. 相关文档

- [ARCHITECTURE.md](ARCHITECTURE.md) — 核心架构入口
- [ARCHITECTURE_INFRA.md](ARCHITECTURE_INFRA.md) — L1 基础设施层
- [ADR-046: 模块化单体部署](../07-adr/ADR-046_modular_monolith_deployment.md)
- [infra/DESIGN.md](../03-modules/infra/DESIGN.md) — 基础设施模块设计
- [auth/DESIGN.md](../03-modules/auth/DESIGN.md) — 身份认证模块设计
