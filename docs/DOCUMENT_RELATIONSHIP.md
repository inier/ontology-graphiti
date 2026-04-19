# ODAP 文档体系关系图

> **版本**: 1.2.0 | **日期**: 2026-04-19
> **状态**: 正式 | **优先级**: P0
> **用途**: 作为项目文档体系的索引文档，提供快速导航

---

## 0. 快速索引

| 角色 | 推荐阅读路径 |
|------|-------------|
| 新成员 | docs/README.md → req-ok.md → ARCHITECTURE_PLAN_v4.md → ARCHITECTURE.md |
| 前端开发 | ADR-007 → ADR-037 → ADR-045 → UI设计 → 前端开发路径 |
| 后端开发 | 架构规划 → 核心架构 → 模块设计 → ADR决策 → TASK_BREAKDOWN |
| 架构师 | 需求定稿 → 架构规划 → 核心架构 → ADR决策 → CHECKLIST_v2.md |
| 产品经理 | 需求定稿 → 架构规划 → Checklist |

---

## 1. 文档目录结构

```
docs/
│
├── 根目录文档
│   ├── README.md                # ⭐ 文档体系入口（新）
│   ├── DOCUMENT_RELATIONSHIP.md  # 本文档
│   ├── ARCHITECTURE.md          # ⭐ 核心架构文档（必读）
│   ├── ARCHITECTURE_PLAN.md     # 架构规划
│   ├── ARCHITECTURE_PLAN_v4.md  # ⭐ 架构规划 v4.0（新）
│   ├── TASK_BREAKDOWN.md        # 任务拆分与开发计划
│   ├── req-alpha.md             # 原始技术研究（归档）
│   ├── req-beta.md              # 早期需求规格（归档）
│   ├── req-ok.md                # ⭐ 需求定稿（唯一权威来源）
│   ├── AUDIT_REPORT.md          # 审计报告
│   ├── RESTRUCTURE_PLAN.md      # 重构计划
│   ├── CHECKLIST.md             # 旧 Checklist
│   ├── CHECKLIST_v1.md          # Checklist v1
│   ├── CHECKLIST_v2.md          # ⭐ 完整 Checklist v2（新）
│   ├── ANOMALY_REPORT.md        # 异常报告
│   ├── COMPLETENESS_REPORT.md   # 完整性报告
│   ├── DFX_DESIGN.md            # DFX设计
│   ├── TEST_DESIGN.md           # 测试设计
│   ├── TEST_REPORT.md           # 测试报告
│   │
│   ├── adr/                     # 架构决策记录 (47个)
│   │   ├── README.md            # ADR 索引
│   │   ├── ADR-001~ADR-037      # 现有ADR
│   │   ├── ADR-038_本体管理引擎与用户认知引擎架构.md  # ⭐ 新增
│   │   ├── ADR-039_qa_engine_architecture.md                 # ⭐ 新增
│   │   ├── ADR-040_api_gateway_unified_entry.md              # ⭐ 新增
│   │   ├── ADR-041_workspace_resource_isolation.md            # ⭐ 新增
│   │   ├── ADR-042_audit_log_storage_query.md                 # ⭐ 新增
│   │   ├── ADR-043_agent_router_semantic_routing.md           # ⭐ 新增
│   │   ├── ADR-044_test_strategy_framework.md                 # ⭐ 新增
│   │   ├── ADR-045_frontend_visualization_g6_leaflet.md       # ⭐ 新增
│   │   ├── ADR-046_modular_monolith_deployment.md             # ⭐ 新增
│   │   └── ADR-047_tool_registry_p0_phased_implementation.md  # ⭐ 新增
│   │
│   ├── modules/                 # 模块设计文档 (23个模块)
│   │   ├── README.md            # 模块索引
│   │   ├── agent/DESIGN.md
│   │   ├── api_gateway/DESIGN.md                # ⭐ 新增
│   │   ├── audit_log/DESIGN.md                  # ⭐ 新增
│   │   ├── decision_recommendation/DESIGN.md
│   │   ├── event_simulator/DESIGN.md            # ⭐ 新增
│   │   ├── graphiti_client/DESIGN.md
│   │   ├── hook_system/DESIGN.md
│   │   ├── infra/DESIGN.md
│   │   ├── mcp_protocol/DESIGN.md
│   │   ├── mock_engine/DESIGN.md
│   │   ├── ontology/DESIGN.md
│   │   ├── opa_policy/DESIGN.md
│   │   ├── openharness_bridge/DESIGN.md
│   │   ├── permission_checker/DESIGN.md
│   │   ├── qa_engine/DESIGN.md                 # ⭐ 新增
│   │   ├── simulator/DESIGN.md
│   │   ├── skills/DESIGN.md
│   │   ├── swarm_orchestrator/DESIGN.md
│   │   ├── tool_registry/DESIGN.md             # ⭐ 新增
│   │   ├── user_cognition_engine/DESIGN.md     # ⭐ 新增
│   │   ├── visualization/DESIGN.md
│   │   ├── web/DESIGN.md
│   │   ├── web_frontend/DESIGN.md             # ⭐ 新增
│   │   ├── workspace/DESIGN.md                  # ⭐ 新增
│   │   └── ontology_management_engine/DESIGN.md # ⭐ 新增
│   │
│   ├── security/
│   │   └── SECURITY.md
│   │
│   └── ui/                     # UI 设计规范
│       ├── UI_DESIGN.md               # UI 设计稿
│       ├── MOBILE_FIRST_DESIGN.md    # ⭐ 移动优先设计规范
│       └── COMPONENT_HIERARCHY.md    # ⭐ 组件分级管理
```

---

## 2. 文档分层体系

```
┌─────────────────────────────────────────────────────────────────────┐
│                         战略层 (Business)                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ req-alpha   │  │  req-beta   │  │  req-ok ⭐  │  │TASK_BREAK↓  │  │
│  │ 技术研究    │  │ 需求草稿    │  │ 需求定稿    │  │ 任务拆分    │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
│  ┌─────────────┐  ┌─────────────┐                                      │
│  │ARCH_PLAN_v4│  │CHECKLIST_v2 │                                      │
│  │架构规划v4.0│  │ 完整Checklist│                                      │
│  └─────────────┘  └─────────────┘                                      │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         架构层 (Architecture)                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    ARCHITECTURE.md                           │    │
│  │                    核心架构文档（238KB）                       │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   决策层 (ADR)  │   │   模块层 (Design)│   │   设计层 (UI)   │
│   47个ADR文档   │   │   23个模块设计   │   │   UI设计规范    │
└─────────────────┘   └─────────────────┘   └─────────────────┘
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         实现层 (Implementation)                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │    frontend/    │  │      odap/      │  │   skills/       │    │
│  │    前端代码     │  │    后端代码     │  │   技能定义      │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心文档阅读路径

### 3.1 新成员入门路径（推荐）

```
1. docs/README.md                        文档体系入口
       ↓
2. docs/req-ok.md                       需求定稿（唯一权威）
       ↓
3. docs/ARCHITECTURE_PLAN_v4.md         架构规划 v4.0
       ↓
4. docs/ARCHITECTURE.md                 核心架构文档
       ↓
5. docs/CHECKLIST_v2.md                 完整 Checklist
```

### 3.2 前端开发路径

```
1. docs/ARCHITECTURE_PLAN_v4.md         架构规划（了解整体）
       ↓
2. docs/ARCHITECTURE.md (第11章)        前端界面架构
       ↓
3. docs/adr/ADR-007_前端技术栈.md       技术选型
       ↓
4. docs/adr/ADR-037_frontend_mobile_first_i18n.md  移动优先+国际化
       ↓
5. docs/adr/ADR-045_frontend_visualization_g6_leaflet.md  可视化技术
       ↓
6. docs/ui/UI_DESIGN.md                 UI 设计稿
       ↓
7. docs/ui/MOBILE_FIRST_DESIGN.md      移动优先规范
       ↓
8. docs/ui/COMPONENT_HIERARCHY.md      组件分级管理
       ↓
9. docs/modules/web_frontend/DESIGN.md  前端模块设计
       ↓
10. frontend/src/                       前端代码实现
```

### 3.3 后端开发路径

```
1. docs/ARCHITECTURE_PLAN_v4.md         架构规划 v4.0
       ↓
2. docs/ARCHITECTURE.md                 核心架构文档（全文）
       ↓
3. docs/TASK_BREAKDOWN.md               任务拆分与 Phase 规划
       ↓
4. docs/modules/*/DESIGN.md             相关模块设计
       ↓
5. docs/adr/ADR-038~ADR-047            新增架构决策
       ↓
6. odap/                                后端代码
```

### 3.4 架构师路径

```
1. docs/req-ok.md                       需求定稿
       ↓
2. docs/ARCHITECTURE_PLAN_v4.md         架构规划 v4.0
       ↓
3. docs/ARCHITECTURE.md                核心架构（全文精读）
       ↓
4. docs/adr/README.md                 ADR 索引
       ↓
5. docs/adr/ADR-038~ADR-047          新增架构决策
       ↓
6. docs/CHECKLIST_v2.md              完整 Checklist
```

---

## 4. 文档关系矩阵

| 上游文档 | 下游文档 | 关系类型 |
|----------|----------|----------|
| req-ok.md | ARCHITECTURE_PLAN_v4.md | 需求→规划 |
| req-ok.md | ARCHITECTURE.md | 需求→架构 |
| ARCHITECTURE_PLAN_v4.md | ARCHITECTURE.md | 规划→架构 |
| ARCHITECTURE.md | TASK_BREAKDOWN.md | 架构→任务 |
| ARCHITECTURE.md | docs/modules/*/DESIGN.md | 架构→模块 |
| ARCHITECTURE.md | docs/ui/UI_DESIGN.md | 架构→UI |
| ARCHITECTURE.md | docs/adr/* | 架构→决策 |
| ADR-007 | docs/ui/UI_DESIGN.md | 技术选型→UI |
| ADR-037 | docs/ui/MOBILE_FIRST_DESIGN.md | 响应式→移动 |
| ADR-045 | docs/modules/web_frontend/DESIGN.md | 可视化→前端 |
| UI_DESIGN.md | MOBILE_FIRST_DESIGN.md | 设计→规范 |
| UI_DESIGN.md | COMPONENT_HIERARCHY.md | 设计→组件 |
| TASK_BREAKDOWN.md | frontend/src/ | 任务→代码 |
| TASK_BREAKDOWN.md | odap/ | 任务→代码 |
| CHECKLIST_v2.md | ARCHITECTURE_PLAN_v4.md | 检查→规划 |

---

## 5. ADR 索引（按主题分类）

### 5.1 核心架构

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-001 | Agent 基础设施 OpenHarness + LangGraph | 已接受 |
| ADR-002 | Graphiti 作为双时态知识图谱 | 已接受 |
| ADR-005 | 分层 Agent 架构 | 已接受 |
| ADR-006 | OpenHarness 复用策略 | 已接受 |
| ADR-030 | Phase1 推迟引入 OpenHarness | 已接受 |
| **ADR-038** | **本体管理引擎与用户认知引擎架构** | **已接受** ⭐ |
| **ADR-046** | **模块化单体部署** | **已接受** ⭐ |

### 5.2 前端与 UI

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-007 | 前端采用 React + Ant Design 技术栈 | 已接受 |
| ADR-015 | 可扩展图表系统 | 已接受 |
| ADR-020 | 管理员控制台统一界面 | 已接受 |
| ADR-031 | Simulator Web 可视化 | 已接受 |
| **ADR-037** | **前端移动优先、响应式设计和国际化策略** | **已接受** ⭐ |
| **ADR-045** | **前端可视化 G6+Leaflet** | **已接受** ⭐ |

### 5.3 本体与数据

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-032 | 标准本体文档格式 | 已接受 |
| ADR-036 | 领域实体标准本体库（Palantir） | 已接受 |
| ADR-022 | 模拟数仓与统一查询服务 | 提议中 |

### 5.4 安全与治理

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-003 | OPA 策略治理引擎 | 已接受 |
| ADR-008 | 审计日志完整记录 | 已接受 |
| ADR-009 | Markdown 编写 OPA 策略 | 已接受 |
| ADR-028 | Permission Checker OPA 集成 | 已接受 |
| **ADR-042** | **审计日志存储与查询** | **已接受** ⭐ |

### 5.5 技能与扩展

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-004 | 统一 Skill 体系架构 | 已接受 |
| ADR-011 | 角色配置热生效 | 已接受 |
| ADR-012 | 配置组合引擎 | 已接受 |
| ADR-014 | 技能热插拔架构 | 已接受 |
| ADR-026 | MCP 协议集成 | 已接受 |
| ADR-029 | 工具注册架构 | 已接受 |
| **ADR-047** | **工具注册 P0 分阶段实现** | **已接受** ⭐ |

### 5.6 运行时引擎

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-018 | Domain Simulator Engine | 已接受 |
| ADR-019 | 多模态文档处理流水线 | 已接受 |
| ADR-023 | 多工作空间隔离架构 | 已接受 |
| ADR-024 | 本体驱动分析核心架构 | 已接受 |
| **ADR-039** | **QA 引擎架构** | **已接受** ⭐ |
| **ADR-040** | **API 网关统一入口** | **已接受** ⭐ |
| **ADR-041** | **工作空间资源隔离** | **已接受** ⭐ |
| **ADR-043** | **Agent 路由器语义路由** | **已接受** ⭐ |
| **ADR-044** | **测试策略与框架** | **已接受** ⭐ |

---

## 6. 模块设计索引

| 模块 | 路径 | 说明 |
|------|------|------|
| Agent | modules/agent/DESIGN.md | Agent 核心架构 |
| Web | modules/web/DESIGN.md | Web 前端模块 |
| Web Frontend | modules/web_frontend/DESIGN.md | ⭐ 前端应用 |
| Ontology | modules/ontology/DESIGN.md | 本体管理模块 |
| Simulator | modules/simulator/DESIGN.md | 模拟器模块 |
| Event Simulator | modules/event_simulator/DESIGN.md | ⭐ 事件模拟器 |
| Skills | modules/skills/DESIGN.md | 技能系统模块 |
| Tool Registry | modules/tool_registry/DESIGN.md | ⭐ 工具注册 |
| OPA Policy | modules/opa_policy/DESIGN.md | OPA 策略模块 |
| Permission Checker | modules/permission_checker/DESIGN.md | 权限检查 |
| Visualization | modules/visualization/DESIGN.md | 可视化模块 |
| Hook System | modules/hook_system/DESIGN.md | 钩子系统模块 |
| Swarm Orchestrator | modules/swarm_orchestrator/DESIGN.md | 蜂群编排器 |
| Decision Recommendation | modules/decision_recommendation/DESIGN.md | 决策推荐 |
| Graphiti Client | modules/graphiti_client/DESIGN.md | Graphiti 客户端 |
| Infra | modules/infra/DESIGN.md | 基础设施 |
| MCP Protocol | modules/mcp_protocol/DESIGN.md | MCP 协议 |
| Mock Engine | modules/mock_engine/DESIGN.md | Mock 引擎 |
| OpenHarness Bridge | modules/openharness_bridge/DESIGN.md | OpenHarness 桥接 |
| QA Engine | modules/qa_engine/DESIGN.md | ⭐ QA 引擎 |
| API Gateway | modules/api_gateway/DESIGN.md | ⭐ API 网关 |
| Audit Log | modules/audit_log/DESIGN.md | ⭐ 审计日志 |
| Workspace | modules/workspace/DESIGN.md | ⭐ 工作空间 |
| User Cognition Engine | modules/user_cognition_engine/DESIGN.md | ⭐ 用户认知引擎 |
| Ontology Management Engine | modules/ontology_management_engine/DESIGN.md | ⭐ 本体管理引擎 |

---

## 7. UI 设计文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| UI 设计稿 | ui/UI_DESIGN.md | 完整的 UI 视觉和交互设计 |
| 移动优先设计 | ui/MOBILE_FIRST_DESIGN.md | 响应式设计详细规范 |
| 组件分级管理 | ui/COMPONENT_HIERARCHY.md | 组件 L1-L5 分级体系 |
| **文档关系图** | DOCUMENT_RELATIONSHIP.md | **本文档 - 项目索引** |

---

## 8. 文档更新规则

| 变更场景 | 必须更新的文档 |
|----------|---------------|
| 新功能需求 | req-ok.md → ARCHITECTURE_PLAN_v4.md → TASK_BREAKDOWN.md → CHECKLIST_v2.md |
| 架构调整 | ARCHITECTURE_PLAN_v4.md → ARCHITECTURE.md → ADR → 模块 DESIGN |
| UI 变更 | UI_DESIGN.md → MOBILE_FIRST_DESIGN → 前端代码 |
| 前端技术选型 | ADR-007/037/045 → ARCHITECTURE.md |
| 响应式/国际化 | ADR-037 → MOBILE_FIRST_DESIGN → 前端代码 |
| 组件重构 | COMPONENT_HIERARCHY.md → 前端代码 |
| 模块设计变更 | 对应 modules/*/DESIGN.md → ARCHITECTURE.md |
| 新增 ADR | ADR-xxx.md → adr/README.md → DOCUMENT_RELATIONSHIP.md |

---

## 9. 相关文档链接

### 需求文档
- [需求定稿 ⭐](./req-ok.md)（唯一权威来源）
- [原始技术研究](./req-alpha.md)（归档）
- [早期需求规格](./req-beta.md)（归档）
- [任务拆分与计划](./TASK_BREAKDOWN.md)

### 架构文档
- [架构规划 v4.0 ⭐](./ARCHITECTURE_PLAN_v4.md)
- [核心架构文档](./ARCHITECTURE.md)
- [ADR 索引](./adr/README.md)
- [完整 Checklist v2 ⭐](./CHECKLIST_v2.md)

### UI 设计文档
- [UI 设计稿](./ui/UI_DESIGN.md)
- [移动优先设计](./ui/MOBILE_FIRST_DESIGN.md)
- [组件分级管理](./ui/COMPONENT_HIERARCHY.md)
- [文档关系图](./DOCUMENT_RELATIONSHIP.md) ← 你在这里

### ADR 文档
- [ADR-007: 前端技术栈](./adr/ADR-007_前端采用_react_ant_design_技术栈.md)
- [ADR-037: 移动优先与国际化](./adr/ADR-037_frontend_mobile_first_i18n.md)
- [ADR-036: 领域实体标准本体库](./adr/ADR-036_palantir_ontology_reference.md)
- [ADR-038~047: 新增架构决策](./adr/)

### 模块设计
- [Web 模块设计](./modules/web/DESIGN.md)
- [Web Frontend 模块设计](./modules/web_frontend/DESIGN.md)
- [Ontology 模块设计](./modules/ontology/DESIGN.md)
- [Simulator 模块设计](./modules/simulator/DESIGN.md)
- [QA Engine 模块设计](./modules/qa_engine/DESIGN.md)
- [API Gateway 模块设计](./modules/api_gateway/DESIGN.md)
- [Workspace 模块设计](./modules/workspace/DESIGN.md)
- [所有模块设计](./modules/README.md)
