# 010 — 零信任 ABAC 安全架构落地

> **来源白皮书**：《AI Agent 零信任 ABAC 安全架构企业级落地白皮书》（基于 OpenHarness + OPA + Grafana/Loki 的全链路治理方案）
> **关联分支**：`010-zero-trust-abac-security`
> **优先级**：P0（安全基线）
> **状态**：📋 Spec 已创建，待评审

---

## 目录

- [1. 背景与目标](#1-背景与目标)
- [2. 白皮书能力要求 vs 当前实现差距矩阵](#2-白皮书能力要求-vs-当前实现差距矩阵)
- [3. 总体架构设计](#3-总体架构设计)
- [4. 分阶段实施计划](#4-分阶段实施计划)
- [5. 验收标准](#5-验收标准)
- [6. 文件清单](#6-文件清单)

---

## 1. 背景与目标

### 1.1 白皮书四大核心原则

| 原则 | 要求 | 当前状态 |
|------|------|----------|
| **默认拒绝，显式允许** (Default Deny) | 所有操作必须经过白名单与策略引擎双重校验 | ⚠️ 白名单分散，无统一 PEP |
| **动态 ABAC 评估** (Dynamic ABAC) | 基于主体/资源/环境/上下文实时动态决策 | ✅ ABAC 基础完整，缺上下文维度 |
| **Fail-Closed 安全降级** | OPA 不可用时默认阻断所有请求 | ✅ 已实现 fail-close |
| **全链路可观测** (Full Observability) | 不可篡改审计日志 + 可视化监控看板 + 告警 | ⚠️ 审计有，监控/告警缺失 |

### 1.2 目标

将当前项目 OPA 安全能力从「核心策略完整、监控告警缺失」升级为白皮书要求的「全链路零信任治理」水平，具体补齐：

1. **统一 PEP 白名单门控**（OpenHarness ↔ OPA 打通）
2. **OPA 决策审计全链路接入**（消除漏点）
3. **Grafana/Loki 可观测栈**（决策监控仪表盘）
4. **自动化告警通道**（DENY 风暴 / OPA 故障 / 延迟飙升）
5. **日志脱敏与长期留存**（合规审计）
6. **CI/CD 安全左移**（opa test 集成）

---

## 2. 白皮书能力要求 vs 当前实现差距矩阵

### 2.1 工具白名单机制 (§2.1)

| 白皮书要求 | 当前实现 | 差距 | 优先级 |
|-----------|----------|------|--------|
| PEP 在白名单校验阶段直接拦截未声明工具 | OpenHarness `PermissionChecker` 有 `allowed_tools`，但与 ODAP OPA **未打通**；ODAP 侧无统一 PEP | 两套权限体系并行 | P0 |
| 不在白名单的工具不进入 OPA 评估 | 无串联：OpenHarness 权限不调 OPA，ODAP OPA 不管 OpenHarness 工具 | 缺统一 PEP 编排层 | P0 |
| `.env` 文件读取禁止 | OpenHarness 有 `SENSITIVE_PATH_PATTERNS`（含 `*/.ssh/*` 等），但**未含 `.env`** | 补充 `.env` 模式 | P1 |

### 2.2 OPA 策略门控 (§2.2)

| 白皮书要求 | 当前实现 | 差距 | 优先级 |
|-----------|----------|------|--------|
| Rego 策略热更新 | ✅ `PolicyBundleManager.hot_update_bundle` | — | — |
| 环境感知（会话时长 > 5min） | `abac_policy.rego` 有时间窗口，**无会话时长维度** | 补充 session_duration 属性 | P1 |
| 资源隔离（禁止读 .env） | Rego 侧无文件级资源隔离规则 | 补充 file_resource 策略 | P1 |
| 绝对红线（禁止 Shell: rm -rf, sudo） | OpenHarness `denied_commands` 有，**ODAP OPA 侧无** | 补充 shell_deny 策略 | P1 |
| `/v1/data/agent/access` 决策 API | 当前用 `/v1/data/domain/allow`，路径不一致 | 新增 agent 包路由 | P1 |

### 2.3 全链路审计链 (§2.3)

| 白皮书要求 | 当前实现 | 差距 | 优先级 |
|-----------|----------|------|--------|
| PreToolUse / PostToolUse 钩子记录决策链 | 有 Hook 系统，但**OPA 决策未接入 Hook** | 接入 hook_system | P0 |
| `trace_id` 全局唯一 | ✅ `unified_audit.py` 有 trace_id | — | — |
| `agent_id` + `action` | AuditEvent 有 actor + action，但 OPA 决策审计未传 agent_id | 补充 agent_id 字段 | P0 |
| `opa_decision` + `opa_reason` | `audit_opa_decision` 有 result + reason | — | — |
| `input_context` + `output_artifact` | 审计记录 input，**无 output_artifact** | PostToolUse 补充输出产物 | P1 |
| 审计写入失败不可观测 | `try/except: pass` 静默吞异常 | 改为计数器 + 告警 | P0 |
| RBAC/mock/缓存路径不写审计 | `OPAManager.check_permission` 缓存命中不审计 | 缓存命中也写审计摘要 | P0 |
| `ABACService` 独立路径不写审计 | `ABACService.check_permission_abac` 未调 `audit_opa_decision` | 补审计调用 | P0 |

### 2.4 运行时执行流 (§3)

| 白皮书要求 | 当前实现 | 差距 | 优先级 |
|-----------|----------|------|--------|
| 意图生成 → 白名单校验(PEP) → OPA评估 → 决策执行 → 异步采集告警 | 串行流不完整：无统一 PEP 编排 | 新增 `PolicyEnforcementPoint` | P0 |
| DENY 原因反馈 Agent 上下文 | OPA 返回 reason，但**未回传 Agent 上下文** | DENY 事件推 WebSocket | P1 |
| Promtail 采集 → Loki 聚合 | ❌ 无 Promtail/Loki | 新增可观测栈 | P1 |

### 2.5 基础设施部署 (§4)

| 白皮书要求 | 当前实现 | 差距 | 优先级 |
|-----------|----------|------|--------|
| OPA Engine 容器化 + `--watch` 热更新 | ✅ docker-compose 有 OPA 容器 | 确认 `--watch` 配置 | P2 |
| OpenHarness Agent 内置 OPA 守卫 | OpenHarness 权限独立，**无 OPA 守卫** | 集成 OPA 调用 | P0 |
| Loki 日志聚合 | ❌ 无 | 新增 Loki 容器 | P1 |
| Promtail 日志采集 | ❌ 无 | 新增 Promtail 容器 | P1 |
| Grafana 安全运营看板 | ❌ 无 | 新增 Grafana + 仪表盘 JSON | P1 |

### 2.6 数据保护与合规 (§5)

| 白皮书要求 | 当前实现 | 差距 | 优先级 |
|-----------|----------|------|--------|
| 策略即代码 (Git 版本控制) | ✅ Rego 文件在 Git | — | — |
| 日志脱敏 (API Key/密码) | ❌ 审计写入无脱敏 | 新增 `audit_sanitizer` | P0 |
| 长期留存 1-2 年 | ✅ `audit_retention.py` 有分级保留（ERROR/CRITICAL 365d KEEP_FOREVER） | 确认 INFO 90d → 180d | P2 |
| 自动化告警 (5min DENY 风暴 → Webhook SOC) | ❌ 无 | Grafana Alerting + Webhook | P1 |

### 2.7 演进扩展 (§6)

| 白皮书要求 | 当前实现 | 差距 | 优先级 |
|-----------|----------|------|--------|
| CI/CD 集成 `opa test` | ❌ 无 | GitHub Actions 步骤 | P2 |
| AI 红队演练 | ❌ 无 | 独立 spec 推进 | P3 |
| JIT 权限（按需授权 + 自动吊销） | ❌ 无 | 独立 spec 推进 | P3 |

---

## 3. 总体架构设计

### 3.1 目标架构（白皮书对齐）

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AI Agent (OpenHarness)                        │
│  ┌─────────────┐   ┌──────────────────────────────────────────┐    │
│  │ 意图生成     │──▶│  PolicyEnforcementPoint (PEP)            │    │
│  │ (LLM)       │   │  ┌──────────┐  ┌────────┐  ┌─────────┐ │    │
│  └─────────────┘   │  │白名单校验 │─▶│OPA评估  │─▶│决策执行  │ │    │
│                    │  │AllowList │  │ABAC    │  │Allow/Deny│ │    │
│                    │  └──────────┘  └────────┘  └─────────┘ │    │
│                    │       │             │           │        │    │
│                    │  PreToolUse    OPA Eval    PostToolUse  │    │
│                    └──────┼─────────────┼───────────┼────────┘    │
└───────────────────────────┼─────────────┼───────────┼─────────────┘
                            ▼             ▼           ▼
                     ┌──────────────────────────────────┐
                     │     Unified Audit Trail           │
                     │  (SQLite + Graphiti + Sanitizer)  │
                     │  trace_id / agent_id / decision   │
                     │  reason / input / output_artifact │
                     └──────────────┬───────────────────┘
                                    ▼
                     ┌──────────────────────────────────┐
                     │  Promtail (日志采集)               │
                     └──────────────┬───────────────────┘
                                    ▼
              ┌─────────────────────┴──────────────────────┐
              ▼                                            ▼
    ┌─────────────────┐                        ┌───────────────────┐
    │  Loki (日志聚合)  │                        │ Grafana (看板+告警) │
    └─────────────────┘                        │ - 决策分布饼图      │
                                               │ - DENY 风暴告警     │
                                               │ - OPA 延迟监控      │
                                               │ - Webhook → SOC    │
                                               └───────────────────┘
```

### 3.2 关键新增组件

| 组件 | 职责 | 实现位置 |
|------|------|----------|
| `PolicyEnforcementPoint` | 统一 PEP：白名单→OPA→执行→审计 串联编排 | `infra/opa/pep.py` (新建) |
| `OPADecisionInterceptor` | OpenHarness 工具执行前调 OPA 守卫 | `biz/integration/openharness_agent/opa_guard.py` (新建) |
| `AuditSanitizer` | 审计写入前脱敏 API Key/密码/Token | `infra/security/audit_sanitizer.py` (新建) |
| `OPAMetricsCollector` | 收集决策计数/延迟/拒绝率指标 | `infra/opa/metrics.py` (新建) |
| `OPAAlertManager` | DENY 风暴/OPA 故障/延迟告警 | `infra/opa/alerting.py` (新建) |
| Grafana Dashboard | 决策监控仪表盘 JSON | `docker/grafana/dashboards/opa-security.json` (新建) |
| Loki + Promtail | 日志聚合与采集 | `docker/docker-compose.observability.yml` (新建) |

---

## 4. 分阶段实施计划

### Phase 1：安全基线修复（P0，必须先做）

> 目标：消除审计漏点 + 统一 PEP + OpenHarness↔OPA 打通 + 日志脱敏

| 任务 ID | 任务 | 涉及文件 | 详细 spec |
|---------|------|----------|-----------|
| P1-01 | OPA 决策审计全路径接入 | `opa_service.py` | [phase1-security-baseline.md](phase1-security-baseline.md) |
| P1-02 | 审计写入失败可观测化 | `unified_audit.py` | 同上 |
| P1-03 | 统一 PEP 编排层 | `infra/opa/pep.py` (新) | 同上 |
| P1-04 | OpenHarness OPA 守卫集成 | `biz/integration/openharness_agent/opa_guard.py` (新) | 同上 |
| P1-05 | 审计日志脱敏 | `infra/security/audit_sanitizer.py` (新) | 同上 |
| P1-06 | `.env` 纳入敏感路径 | `packages/openharness/.../checker.py` | 同上 |

### Phase 2：可观测与告警（P1）

> 目标：Grafana/Loki 栈 + OPA 决策监控仪表盘 + 自动化告警

| 任务 ID | 任务 | 涉及文件 | 详细 spec |
|---------|------|----------|-----------|
| P2-01 | OPA 指标采集器 | `infra/opa/metrics.py` (新) | [phase2-observability-alerting.md](phase2-observability-alerting.md) |
| P2-02 | OPA 告警管理器 | `infra/opa/alerting.py` (新) | 同上 |
| P2-03 | Loki + Promtail 容器化 | `docker/docker-compose.observability.yml` (新) | 同上 |
| P2-04 | Grafana 仪表盘 | `docker/grafana/dashboards/` (新) | 同上 |
| P2-05 | 前端 OPA 监控页 | `apps/web/src/modules/audit/pages/OPAMonitorPage.tsx` (新) | 同上 |
| P2-06 | DENY 原因回传 Agent 上下文 | `ws/event_bus.py` + Agent 端 | 同上 |
| P2-07 | ABAC 补充会话时长维度 | `policies/abac_policy.rego` | 同上 |

### Phase 3：合规与 CI/CD（P2）

> 目标：长期留存调优 + opa test CI 集成 + 策略沙箱增强

| 任务 ID | 任务 | 涉及文件 | 详细 spec |
|---------|------|----------|-----------|
| P3-01 | 审计保留期调优（INFO 90d→180d） | `web/app.py` 默认策略 | [phase3-compliance-cicd.md](phase3-compliance-cicd.md) |
| P3-02 | `opa test` CI 集成 | `.github/workflows/opa-test.yml` (新) | 同上 |
| P3-03 | PostToolUse 记录 output_artifact | Hook 系统 | 同上 |

### Phase 4：演进扩展（P3，独立 spec）

| 任务 ID | 任务 | 备注 |
|---------|------|------|
| P4-01 | AI 红队演练框架 | 独立 spec |
| P4-02 | JIT 权限与持续授权 | 独立 spec |

---

## 5. 验收标准

### 5.1 Phase 1 验收

- [ ] `OPAManager.check_permission`（RBAC/缓存/mock 路径）所有决策均写审计
- [ ] `ABACService.check_permission_abac` 写审计
- [ ] 审计写入失败时计数器递增并触发告警（非 `pass` 静默）
- [ ] 新增 `PolicyEnforcementPoint`，白名单→OPA→执行 串联完整
- [ ] OpenHarness 工具执行前调用 OPA 守卫，决策进审计
- [ ] `.env` 文件被 OpenHarness `SENSITIVE_PATH_PATTERNS` 拦截
- [ ] 审计日志中 API Key/密码字段被脱敏（`***REDACTED***`）
- [ ] 所有 Phase 1 单元测试通过

### 5.2 Phase 2 验收

- [ ] `GET /api/opa/metrics` 返回决策计数/延迟/拒绝率/缓存命中率
- [ ] OPA 不可用时触发告警（WebSocket + 审计 WARN 事件）
- [ ] 5 分钟内 DENY > 阈值时触发告警
- [ ] `docker-compose.observability.yml` 启动 Loki + Promtail + Grafana
- [ ] Grafana 仪表盘展示：决策分布饼图、实时日志流、工具热度排行、DENY 时序图
- [ ] 前端 `/audit/opa-monitor` 页面展示 OPA 实时指标
- [ ] ABAC 策略支持 `session_duration` 维度（高敏操作要求 > 5min）

### 5.3 Phase 3 验收

- [ ] INFO 级审计保留 180 天
- [ ] `opa test` 在 CI 流水线执行，策略测试失败阻断合并
- [ ] PostToolUse 审计含 `output_artifact` 字段

---

## 6. 文件清单

### 6.1 新增文件

| 文件 | 阶段 |
|------|------|
| `apps/api/odap/infra/opa/pep.py` | P1 |
| `apps/api/odap/biz/integration/openharness_agent/opa_guard.py` | P1 |
| `apps/api/odap/infra/security/audit_sanitizer.py` | P1 |
| `apps/api/odap/infra/opa/metrics.py` | P2 |
| `apps/api/odap/infra/opa/alerting.py` | P2 |
| `apps/api/odap/infra/opa/api/routes.py`（OPA 监控 API） | P2 |
| `docker/docker-compose.observability.yml` | P2 |
| `docker/grafana/dashboards/opa-security.json` | P2 |
| `docker/promtail/promtail-config.yml` | P2 |
| `apps/web/src/modules/audit/pages/OPAMonitorPage.tsx` | P2 |
| `.github/workflows/opa-test.yml` | P3 |

### 6.2 修改文件

| 文件 | 阶段 | 改动摘要 |
|------|------|----------|
| `apps/api/odap/infra/opa/opa_service.py` | P1 | 补全审计调用、消除 `pass` 静默 |
| `apps/api/odap/infra/security/unified_audit.py` | P1 | 接入 sanitizer、审计失败计数 |
| `packages/openharness/.../permissions/checker.py` | P1 | 补 `.env` 模式 |
| `apps/api/odap/infra/opa/policies/abac_policy.rego` | P2 | 增 session_duration |
| `apps/api/odap/web/app.py` | P2 | 注册 OPA 监控路由 |
| `apps/web/src/AppRoutes.tsx` | P2 | 增 OPA 监控页路由 |
| `apps/api/odap/web/app.py` | P3 | 调整保留策略 |

---

## 附录：白皮书原文要点索引

| 白皮书章节 | 关键要求 | 对应 spec 章节 |
|-----------|---------|---------------|
| §1 四大原则 | 默认拒绝 / 动态ABAC / Fail-Closed / 全链路可观测 | §2 全矩阵 |
| §2.1 工具白名单 | PEP 拦截未声明工具 | §2.1, P1-03 |
| §2.2 OPA 策略门控 | 环境感知/资源隔离/绝对红线 | §2.2, P2-07 |
| §2.3 全链路审计 | trace_id/agent_id/decision/reason/input/output | §2.3, P1-01 |
| §3 运行时执行流 | 意图→白名单→OPA→执行→采集告警 | §3.1, P1-03 |
| §4 基础设施 | OPA+OpenHarness+Loki+Promtail+Grafana | §2.5, P2-03 |
| §5 数据保护 | 策略即代码/日志脱敏/长期留存/自动告警 | §2.6, P1-05, P2-02 |
| §6 演进扩展 | CI/CD / AI红队 / JIT权限 | §2.7, P3, P4 |
