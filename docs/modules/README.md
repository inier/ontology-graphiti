# 模块设计文档索引

> **版本**: 2.0.0 | **更新日期**: 2026-04-19
> 本文档索引了 ODAP（本体驱动 AI 平台）的所有模块设计文档。

---

## 模块总览

### 活跃模块（18 个）

| 模块 ID | 模块名称 | 路径 | 架构层 | 优先级 | 状态 |
|---------|---------|------|--------|--------|------|
| M-01 | Graphiti 客户端 | `graphiti_client/DESIGN.md` | L1 基础设施 | P0 | ✅ 活跃 |
| M-02 | OPA 策略管理 | `opa_policy/DESIGN.md` | L1 基础设施 | P0 | ✅ 活跃 |
| M-03 | 本体管理 | `ontology/DESIGN.md` | L1 基础设施 | P0 | ✅ 活跃 |
| M-04 | 工作空间管理 | `workspace/DESIGN.md` | L1 基础设施 | P0 | 🆕 新增 |
| M-05 | Hook 系统 | `hook_system/DESIGN.md` | L1 基础设施 | P0 | ✅ 活跃 |
| M-06 | MCP 协议集成 | `mcp_protocol/DESIGN.md` | L1 基础设施 | P1 | ✅ 活跃 |
| M-07 | 审计日志 | `audit_log/DESIGN.md` | L1 基础设施 | P0 | 🆕 新增 |
| M-08 | Skill 领域工具 | `skills/DESIGN.md` | L2 领域技能 | P0 | ✅ 活跃 |
| M-09 | Swarm 编排 | `swarm_orchestrator/DESIGN.md` | L3 Agent 编排 | P0 | ✅ 活跃 |
| M-10 | Agent 路由 | `agent/DESIGN.md` | L3 Agent 编排 | P0 | ✅ 活跃 |
| M-11 | 工具注册表 | `tool_registry/DESIGN.md` | L2 领域技能 | P0 | 🆕 新增 |
| M-12 | 问答引擎 | `qa_engine/DESIGN.md` | L4 应用服务 | P0 | 🆕 新增 |
| M-13 | 决策推荐 | `decision_recommendation/DESIGN.md` | L4 应用服务 | P0 | ✅ 活跃 |
| M-14 | 模拟推演 | `simulator/DESIGN.md` | L4 应用服务 | P0 | ✅ 活跃 |
| M-15 | 事件模拟器 | `event_simulator/DESIGN.md` | L2 领域技能 | P1 | 🆕 新增 |
| M-16 | API 网关 | `api_gateway/DESIGN.md` | L5 网关 | P0 | 🆕 新增 |
| M-17 | Web 前端 | `web_frontend/DESIGN.md` | L6 用户交互 | P0 | 🆕 新增 |
| M-18 | 可视化引擎 | `visualization/DESIGN.md` | L4 应用服务 | P1 | ✅ 活跃 |

### 已合并/推迟模块

| 原模块 | 状态 | 目标 | 原因 |
|--------|------|------|------|
| permission_checker | ⚠️ 已合并 | → M-02 opa_policy | 与 OPA 策略管理高度重叠 |
| mock_engine | ⚠️ 已合并 | → M-15 event_simulator | 静态数据生成作为模板引擎子功能 |
| web | ⚠️ 已拆分 | → M-16 api_gateway + M-17 web_frontend | 按六层架构职责拆分 |
| openharness_bridge | ⏸️ 推迟 | Phase 4 | ADR-030，OpenHarness 实现延期 |
| infra | 📎 保留 | 辅助模块 | 基础设施辅助（GraphManager/OPAManager 等） |

---

## 六层架构图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ L6  用户交互层                                                                │
│     M-17 Web 前端 (React SPA)                                                │
├──────────────────────────────────────────────────────────────────────────────┤
│ L5  API 网关层                                                                │
│     M-16 API 网关 (认证/限流/路由/权限)                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│ L4  应用服务层                                                                │
│     M-12 问答引擎 │ M-13 决策推荐 │ M-14 模拟推演 │ M-18 可视化引擎           │
├──────────────────────────────────────────────────────────────────────────────┤
│ L3  Agent 编排层                                                              │
│     M-09 Swarm 编排 │ M-10 Agent 路由                                         │
├──────────────────────────────────────────────────────────────────────────────┤
│ L2  领域技能层                                                                │
│     M-08 Skill 工具 │ M-11 工具注册表 │ M-15 事件模拟器                        │
├──────────────────────────────────────────────────────────────────────────────┤
│ L1  基础设施层                                                                │
│     M-01 Graphiti │ M-02 OPA │ M-03 本体 │ M-04 工作空间                      │
│     M-05 Hook │ M-06 MCP │ M-07 审计日志                                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 核心依赖链

### 问答链（用户 → 知识 → 答案）

```
M-17 Web → M-16 Gateway → M-12 QA → M-01 Graphiti + M-08 Skill
                              ↓
                        M-09 Swarm (复杂问题升级)
```

### 决策链（情报 → 分析 → 决策）

```
M-15 EventSim → M-14 Simulator → M-13 DecisionRec → M-09 Swarm
                    ↓                    ↓
              M-01 Graphiti          M-02 OPA (策略校验)
```

### 管理链（配置 → 生效 → 审计）

```
M-03 Ontology → M-04 Workspace → M-05 Hook → M-07 AuditLog
       ↓              ↓
  M-01 Graphiti   M-02 OPA
```

---

## 新增模块摘要

### M-04 工作空间管理
- **职责**: 多场景隔离，工作空间 CRUD/切换/导入导出
- **隔离策略**: Neo4j 多数据库 + OPA Bundle 路径隔离 + Skill 注册表命名空间
- **关键接口**: `IWorkspaceProvider` — 供基础设施层组件获取当前上下文

### M-07 审计日志
- **职责**: 100% 操作覆盖的审计追踪，时间线可视化，防篡改校验链
- **写入策略**: 异步 Channel + 批量落盘，CRITICAL 级别同步写入
- **关键接口**: `AuditLogger.log()` / `AuditLogger.start_span()`

### M-11 工具注册表
- **职责**: 统一管理 Skill/内置/MCP/外部 API 工具，运行时发现与调度
- **与 Skill 关系**: Skill 是编写规范，Tool Registry 是运行时注册表
- **关键接口**: `IToolRegistry.discover()` / `IToolRegistry.execute()`

### M-12 问答引擎
- **职责**: 自然语言问答，RAG 增强生成，双时态查询，溯源追踪
- **升级策略**: 简单→QAEngine 直处理，复杂→升级到 Intelligence Agent
- **关键接口**: `QAEngine.ask()` / `QAEngine.ask_with_tools()`

### M-15 事件模拟器
- **职责**: 自动/手动生成模拟事件，驱动知识图谱状态演化
- **与推演关系**: 事件模拟器生成"发生了什么"，推演引擎分析"该怎么做"
- **关键接口**: `EventSimulator.create_scenario()` / `EventSimulator.inject_event()`

### M-16 API 网关
- **职责**: 统一入口，认证鉴权，流量治理，协议适配
- **管道**: Request → CORS → Auth → RateLimit → Route → Permission → Proxy → Response
- **关键接口**: REST API + WebSocket + SSE

### M-17 Web 前端
- **职责**: 用户交互界面，全流程可视化
- **技术栈**: React 18 + TypeScript + Ant Design 5 + Zustand + Vite
- **关键页面**: 智能问答(P0)、审计日志(P0)、工具管理(P1)

---

## 文档维护

| 规则 | 说明 |
|------|------|
| 更新时机 | 模块重构、接口变更、重大功能调整时更新 |
| 审批 | 需技术负责人 Review 后合并 |
| 版本 | 与模块代码版本保持一致 |
| 合并/拆分 | 在原文档头部标注合并声明，保留供历史参考 |
