# ADR-047: 工具注册表（M-11）升级为 P0 并分步实现

## 状态

已接受

## 上下文

工具注册表（M-11）在 ARCHITECTURE_PLAN 和 TASK_BREAKDOWN 中被标注为 **P1**（WR-09），但在 DESIGN.md 头部标注为 P0。ANOMALY_REPORT I-36 提出需确认优先级。

### 依赖链冲突

Agent 编排层（P0）的多个模块直接依赖工具注册表：

```
WR-08 (Skill v2, P0) → WR-09 (工具注册表, P1)
                         ↓
                    WR-11 (Swarm v2, P0) — 需要 ToolRegistry.discover()
                    WR-12 (Agent Router, P0) — 需要 ToolRegistry.execute()
                    WR-13 (问答引擎, P0) — 需要 ToolRegistry
```

如果工具注册表保持 P1，则 P0 的 Agent 层无法端到端跑通 OODA 循环，只能硬编码工具列表或 mock。

## 决策

**将 M-11 工具注册表升级为 P0，但分两步实现，控制复杂度和工期影响。**

### Step 1 — 核心接口（P0 关键路径）

随 WR-08 同步开发，与 Skill 基础设施可并行：

| 组件 | 说明 | 包含 |
|------|------|------|
| ToolRegistry | 注册/注销/查询/发现 | register, unregister, get, discover (精确匹配+关键词) |
| ToolExecutor | 执行路由 | SkillExecutor + BuiltinExecutor |
| ToolPermissionBridge | OPA 权限校验 | check_permission |
| IToolRegistry | 接口协议 | 供 Agent 层依赖倒置 |

**不包含**：语义发现（embedding）、健康监控/熔断器、组合工具（工具链）、MCPExecutor、REST API

### Step 2 — 完整能力（P1，WR-09 原位）

| 组件 | 说明 |
|------|------|
| 语义发现 | embedding 匹配 capability 描述 |
| ToolHealthMonitor | 健康监控 + 熔断器 |
| CompositeExecutor | 工具链执行（串行/条件/并行） |
| MCPExecutor | MCP 协议工具桥接 |
| REST API | /api/tools/* 端点 |
| ToolMetrics | 性能指标采集 |

### 关键路径影响

- 原：WR-01→WR-03→WR-04→WR-05→WR-17→WR-18，11.5 周
- 新：WR-01→WR-03→WR-04→WR-05→**WR-09a**→WR-11→WR-17→WR-18，~12 周
- WR-09a（Step 1）与 WR-08 可并行，净增约 0.5 周

## 后果

### 变容易的
- Agent Router 可以动态发现工具，不再硬编码
- Swarm 编排器可以按能力描述选择工具
- 问答引擎可以编排工具调用链路
- OODA 循环端到端跑通

### 变困难的
- 关键路径延长约 0.5 周
- Step 1 需要确保核心接口足够稳定，避免 Step 2 时大量返工
- 并行开发 WR-08 和 WR-09a 需要更紧密的协调

### 风险缓解
- 核心 IToolRegistry 接口已在 DESIGN.md 中定义，稳定性有保障
- Step 1 砍掉了 60% 复杂度（健康监控、语义发现、工具链），实现风险可控
- 如果 Step 1 工期紧张，可进一步砍掉 ToolPermissionBridge，先用 skip_permission 走通

## 关联

- 取代：ANOMALY_REPORT I-36 的 P1 标注
- 关联 ADR：ADR-029（统一工具注册表架构）、ADR-043（Agent Router 语义路由）
- 关联工作项：WR-09（工具注册表）、WR-08（Skill 基础设施 v2）、WR-12（Agent Router）
