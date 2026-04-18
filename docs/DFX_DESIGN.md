# DFX 设计文档 (Design for eXcellence)

> **版本**: 1.0.0 | **日期**: 2026-04-19
> **关联**: req-ok.md NFR-P/S/R/M/U/C 系列

---

## 1. 概述

DFX（Design for eXcellence）是面向质量属性的设计方法论，确保系统在性能、安全、可靠性、可维护性、可用性、兼容性等维度满足非功能需求。本文档将 req-ok.md 中的 NFR 映射为具体的设计决策和实现策略。

---

## 2. 性能设计 (Design for Performance)

### 2.1 NFR 目标

| 编号 | 指标 | 目标 | 设计保障 |
|------|------|------|---------|
| NFR-P01 | 问答响应时间 | < 3s (P95) | 见 §2.2 |
| NFR-P02 | 图谱查询延迟 | < 500ms (P95) | 见 §2.3 |
| NFR-P03 | 并发用户数 | 100+ 同时在线 | 见 §2.4 |
| NFR-P04 | Skill 加载时间 | < 30s | 见 §2.5 |
| NFR-P05 | 系统可用性 | 99.9% | 见 §3 |
| NFR-P06 | 推演并发数 | ≥ 10 方案并行 | 见 §2.6 |
| NFR-P07 | 推演参数配置响应 | < 1s | 见 §2.6 |
| NFR-P08 | 单次推演时长 | 平均 < 30s | 见 §2.6 |

### 2.2 问答响应时间 (< 3s P95)

**瓶颈分析**：
```
用户提问 → 查询理解(LLM) → 图谱检索(Graphiti) → 答案生成(LLM) → 返回
           ~500ms          ~300ms              ~1000ms
总计: ~1800ms (P50), 目标 P95 < 3s
```

**优化策略**：

| 策略 | 目标阶段 | 预期效果 |
|------|---------|---------|
| 查询理解缓存 | 查询理解 | 相似问题命中缓存，跳过 LLM 调用 (~0ms) |
| Graphiti 三级缓存 | 图谱检索 | Memory→Redis→Disk，热点查询 < 50ms |
| 流式输出 | 答案生成 | 首 token < 500ms，用户体验即时响应 |
| 检索结果预取 | 图谱检索 | 预加载高频实体关联，减少冷查询 |
| LLM Provider 路由 | 全链路 | 快分析模型(Intelligence) vs 强推理模型(Commander) |

### 2.3 图谱查询延迟 (< 500ms P95)

**策略**：

| 层级 | 策略 | 实现 |
|------|------|------|
| Graphiti Client | 三级缓存 | M-01 设计：Memory(1min) → Redis(10min) → Disk(1h) |
| Neo4j | 索引优化 | 节点 type/name 索引，边 source/target 复合索引 |
| Neo4j | 查询计划 | PROFILE 分析慢查询，强制索引提示 |
| 连接池 | 连接复用 | GraphitiClient 内置连接池，避免频繁建连 |
| 批量查询 | 减少往返 | `search()` 返回批量结果，避免 N+1 查询 |

### 2.4 并发用户数 (100+)

**策略**：

| 组件 | 并发模型 | 容量规划 |
|------|---------|---------|
| API Gateway (FastAPI) | async/await + uvicorn | 4 workers × 256 连接 = 1024 并发 |
| Graphiti Client | 连接池 (max 50) | 50 并发 Neo4j 连接 |
| LLM Provider | 速率限制 | 按 Provider 限制，排队机制 |
| WebSocket | 连接管理器 | 500 并发 WS 连接 |

### 2.5 Skill 加载时间 (< 30s)

**策略**：
- Skill 懒加载：按需加载，启动时仅加载元数据
- Skill 缓存：已加载 Skill 内存缓存，重启后热加载
- 并行初始化：多个 Skill 并行加载

### 2.6 推演性能

| 指标 | 策略 |
|------|------|
| NFR-P06 (≥10 并发推演) | 每推演独立 TimelineEngine + 隔离 Neo4j 数据库 |
| NFR-P07 (配置响应 < 1s) | 配置缓存 + 增量更新，避免全量重载 |
| NFR-P08 (推演 < 30s) | 事件批量注入 + Graphiti 批量写入 |

---

## 3. 安全设计 (Design for Security)

### 3.1 NFR 目标

| 编号 | 指标 | 设计保障 |
|------|------|---------|
| NFR-S01 | SSO/OAuth2/本地认证 | M-16 API Gateway AuthHandler |
| NFR-S02 | TLS 1.3 | Nginx/反向代理终止 TLS |
| NFR-S03 | 工作空间级数据隔离 | M-04 WorkspaceIsolator (Neo4j 多数据库) |
| NFR-S04 | 100% 操作审计覆盖 | M-07 AuditLogger + Hook 自动拦截 |
| NFR-S05 | 推演数据与生产隔离 | M-14 Simulator 沙箱隔离 |
| NFR-S06 | 基于角色的方案访问权限 | M-02 OPA ABAC 策略 |

### 3.2 安全架构

```
外部请求 → TLS 终止 → API Gateway → 认证(JWT) → 权限(OPA) → 服务层
                                                    ↓
                                              OPA 策略引擎
                                              ├─ 网关级: API 访问控制
                                              ├─ 服务级: 资源级控制
                                              └─ 数据级: 行级/属性级控制
```

### 3.3 OPA 策略层次

| 层次 | 策略文件 | 职责 |
|------|---------|------|
| L1 网关 | `gateway.rego` | API 路由级访问控制 |
| L2 资源 | `resource.rego` | 资源 CRUD 权限 |
| L3 数据 | `data.rego` | 行级/属性级过滤 |
| L4 操作 | `operation.rego` | 操作约束（如禁止攻击民用设施） |

### 3.4 Fail-Close 机制

```rego
# 默认拒绝 — 任何未明确允许的操作都被拒绝
default allow = false

# 显式允许规则
allow {
    some i
    input.subject.roles[i] == "admin"
    input.action == "workspace:update"
}
```

- OPA 不可达时，所有请求返回 503（安全降级）
- 策略编译错误时，拒绝加载新策略，保留旧策略

### 3.5 数据隔离

| 隔离维度 | 实现 | 验证 |
|----------|------|------|
| 工作空间 | Neo4j 多数据库 | WorkspaceIsolator.verify_isolation() |
| 推演沙箱 | 独立 Neo4j 实例 | Simulator 沙箱状态检查 |
| API | JWT 中的 workspace_ids | AuthHandler + PermissionBridge |
| 文件存储 | 按空间路径隔离 | 定期扫描越权访问 |

---

## 4. 可靠性设计 (Design for Reliability)

### 4.1 NFR 目标

| 编号 | 指标 | 设计保障 |
|------|------|---------|
| NFR-R01 | 推演成功率 > 99% | 见 §4.2 |
| NFR-R02 | 版本回退数据完全恢复 | 见 §4.3 |
| NFR-R03 | 沙箱无内存泄漏 | 见 §4.4 |

### 4.2 推演可靠性

| 故障场景 | 检测 | 恢复 |
|----------|------|------|
| Graphiti 写入失败 | 写入返回错误 | 重试 3 次 → 标记事件失败 → 记录审计 |
| Neo4j 连接断开 | 健康检查 | 自动重连 + 指数退避 |
| OPA 策略校验超时 | 超时检测 | Fail-Close：拒绝操作 |
| 推演过程 OOM | 内存监控 | 自动暂停推演 + 告警 |

### 4.3 数据恢复

| 机制 | 实现 |
|------|------|
| 版本管理 | OntologyManager Git-style 版本，每个版本一个快照 |
| 事件溯源 | AuditLogger 记录所有变更，可回放 |
| 双时态回退 | Graphiti valid_time 可查询任意时间点状态 |
| 备份 | Neo4j 定期全量备份 + 增量导出 |

### 4.4 内存安全

| 措施 | 实现 |
|------|------|
| 内存监控 | HealthMonitor 定期采集内存指标 |
| 资源限制 | WorkspaceConfig.resource_limits 限制单空间资源 |
| 推演清理 | Simulator 结束后主动释放 Neo4j 临时数据库 |
| Python GC | 长运行进程定期 gc.collect() |

---

## 5. 可维护性设计 (Design for Maintainability)

### 5.1 NFR 目标

| 编号 | 指标 | 设计保障 |
|------|------|---------|
| NFR-M01 | PEP8/TypeScript 规范 | Linter + Pre-commit |
| NFR-M02 | 单元测试覆盖率 > 80% | 见 §5.3 |
| NFR-M03 | 100% API 有文档 | OpenAPI 自动生成 |
| NFR-M04 | Docker/K8s 部署 | 容器化 + 编排 |
| NFR-M05 | 模块松耦合 | 接口标准化，模块可独立升级 |
| NFR-M06 | Skill/本体/策略热插拔 | 见 §5.4 |

### 5.2 模块松耦合

| 机制 | 实现 |
|------|------|
| 接口抽象 | 每个模块对外暴露 Protocol/Interface，不暴露实现 |
| 依赖注入 | 构造函数注入，不使用全局单例 |
| 事件驱动 | 模块间通过 Hook/事件通信，避免直接调用 |
| 配置外部化 | 模块行为通过配置控制，不硬编码 |

### 5.3 测试策略

| 层级 | 覆盖目标 | 工具 |
|------|---------|------|
| 单元测试 | > 80% 行覆盖率 | pytest + pytest-asyncio |
| 集成测试 | 模块间交互 | pytest + testcontainers (Neo4j/OPA) |
| E2E 测试 | 关键用户流程 | Playwright |
| 性能测试 | NFR-P 系列指标 | Locust |
| 安全测试 | 权限绕过/注入 | OWASP ZAP |

### 5.4 热插拔

| 组件 | 热插拔机制 |
|------|----------|
| Skill | ToolRegistry.register()/unregister()，运行时增删 |
| 本体版本 | OntologyManager.switch_version()，零停机切换 |
| OPA 策略 | OPAManager.update_bundle()，实时生效 |
| Hook | HookRegistry.register()/unregister()，运行时增删 |

---

## 6. 可用性设计 (Design for Usability)

### 6.1 NFR 目标

| 编号 | 指标 | 设计保障 |
|------|------|---------|
| NFR-U01 | 操作直观 | UI_DESIGN.md 规范 |
| NFR-U02 | 操作反馈 < 200ms | 见 §6.2 |
| NFR-U03 | 容错友好 | 见 §6.3 |
| NFR-U04 | 可视化配置 | 表单 + JSON 双模式 |

### 6.2 反馈时效

| 场景 | 反馈方式 | 延迟目标 |
|------|---------|---------|
| 按钮点击 | Button loading 态 | < 100ms |
| 表单提交 | Spin + 成功 Toast | < 200ms |
| 图谱操作 | 增量更新 | < 200ms |
| 问答 | 流式输出首 token | < 500ms |
| 文件操作 | 进度条 | < 1s |

### 6.3 容错设计

| 场景 | 处理 |
|------|------|
| 输入错误 | 实时验证 + 内联错误提示 + 自动修正建议 |
| 网络断开 | 离线提示 + 自动重连 + 本地缓存 |
| 操作失误 | Undo 支持（图谱编辑）+ 确认弹窗（危险操作） |
| 数据不一致 | 页面加载时校验 + 提示修复 |

---

## 7. 兼容性设计 (Design for Compatibility)

### 7.1 NFR 目标

| 编号 | 指标 | 设计保障 |
|------|------|---------|
| NFR-C01 | 不绑定垂直领域 | 工作空间 + 本体模板机制 |
| NFR-C02 | 多数据源 (Kafka/API/文件) | MCP 协议 + DataTransformer |
| NFR-C03 | MCP 协议外部集成 | M-06 MCP 模块 |

### 7.2 场景无关设计

| 机制 | 实现 |
|------|------|
| 工作空间 | 每个场景独立工作空间，领域仅影响本体/Skill |
| 本体模板 | 预定义领域模板，一键实例化 |
| Skill 插件 | 领域 Skill 按工作空间注册，不同场景不同 Skill 集 |
| OPA 策略 | 每个工作空间独立策略 Bundle |

### 7.3 数据源适配

| 数据源类型 | 适配器 | 协议 |
|-----------|--------|------|
| Kafka | MCP Kafka Source | Kafka Consumer |
| REST API | MCP HTTP Source | HTTP/HTTPS |
| 文件 | MCP File Source | CSV/JSON/XML |
| 数据库 | MCP DB Source | JDBC/ODBC |
| 实时流 | MCP WebSocket | WS/WSS |

---

## 8. 可观测性设计 (Design for Observability)

### 8.1 指标体系

| 维度 | 指标 | 采集方式 |
|------|------|---------|
| **RED** (Request) | Rate / Errors / Duration | API Gateway MetricsCollector |
| **USE** (Resource) | Utilization / Saturation / Errors | HealthMonitor |
| **业务指标** | 问答量 / 推演数 / 图谱节点数 | 各模块上报 |

### 8.2 日志规范

| 级别 | 用途 | 输出 |
|------|------|------|
| DEBUG | 开发调试 | stdout (开发环境) |
| INFO | 关键操作 | stdout + 文件 |
| WARN | 退化/需注意 | stdout + 文件 + 告警 |
| ERROR | 操作失败 | stdout + 文件 + 告警 |
| CRITICAL | 系统故障 | stdout + 文件 + 即时告警 |

**日志格式** (JSON):
```json
{
  "timestamp": "2026-04-19T00:00:00.000Z",
  "level": "INFO",
  "module": "qa_engine",
  "trace_id": "abc123",
  "workspace_id": "ws_001",
  "message": "Query processed",
  "duration_ms": 1250,
  "metadata": {"intent": "entity_lookup", "confidence": 0.95}
}
```

### 8.3 追踪

| 追踪类型 | 实现 |
|----------|------|
| 分布式追踪 | trace_id 贯穿 Gateway → Service → Graphiti/OPA |
| 审计追踪 | AuditLogger 因果链 (parent_event_id) |
| Agent 追踪 | OODA Loop 状态机 (Observation → Orientation → Decision → Action) |

### 8.4 告警规则

| 规则 | 条件 | 级别 | 通知 |
|------|------|------|------|
| 服务不可用 | 健康检查连续 3 次失败 | CRITICAL | 即时 |
| 响应超时 | P95 > 阈值持续 5 分钟 | WARN | 5 分钟 |
| 错误率升高 | 5xx > 5% 持续 2 分钟 | WARN | 2 分钟 |
| 磁盘空间 | > 85% | WARN | 10 分钟 |
| 内存泄漏 | RSS 持续增长 30 分钟 | ERROR | 即时 |
