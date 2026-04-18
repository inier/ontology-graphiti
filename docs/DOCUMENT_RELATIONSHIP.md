# ODAP 文档体系关系图

> **版本**: 1.1.0 | **日期**: 2026-04-17
> **状态**: 正式 | **优先级**: P0
> **用途**: 作为项目文档体系的索引文档，提供快速导航

---

## 0. 快速索引

| 角色 | 推荐阅读路径 |
|------|-------------|
| 新成员 | 需求 → 架构 → UI设计 → 前端开发路径 |
| 前端开发 | ADR-007 → ADR-037 → UI设计 → 移动优先规范 → 组件分级 |
| 后端开发 | 架构 → 模块设计 → TASK_BREAKDOWN |
| 架构师 | 需求 → 架构(全文) → ADR决策 |
| 产品经理 | 需求规格说明书 |

---

## 1. 文档目录结构

```
docs/
│
├── 根目录文档
│   ├── DOCUMENT_RELATIONSHIP.md  # 本文档
│   ├── ARCHITECTURE.md          # ⭐ 核心架构文档（必读）
│   ├── TASK_BREAKDOWN.md        # 任务拆分与开发计划
│   ├── req-alpha.md             # 原始技术研究（归档）
│   ├── req-beta.md              # 早期需求规格（归档）
│   ├── req-ok.md                # ⭐ 需求定稿（唯一权威来源）
│   ├── AUDIT_REPORT.md          # 审计报告
│   ├── RESTRUCTURE_PLAN.md      # 重构计划
│   │
│   ├── adr/                     # 架构决策记录 (37个)
│   │   ├── README.md            # ADR 索引
│   │   ├── ADR-001_agent_基础设施openharness_langgraph.md
│   │   ├── ADR-002_graphiti_作为双时态知识图谱.md
│   │   ├── ADR-003_opa_策略治理引擎mvp_生产化.md
│   │   ├── ADR-004_统一_skill_体系架构.md
│   │   ├── ADR-005_分层_agent_架构openharness_原生_领域扩展.md
│   │   ├── ADR-006_openharness_复用策略完全复用_适配复用_独立扩展.md
│   │   ├── ADR-007_前端采用_react_ant_design_技术栈.md
│   │   ├── ADR-008_审计日志完整记录.md
│   │   ├── ADR-009_markdown_编写_opa_策略.md
│   │   ├── ADR-010_多模态文档处理可配置.md
│   │   ├── ADR-011_角色配置热生效.md
│   │   ├── ADR-012_配置组合引擎.md
│   │   ├── ADR-013_多数据源统一接入.md
│   │   ├── ADR-014_技能热插拔架构.md
│   │   ├── ADR-015_可扩展图表系统.md
│   │   ├── ADR-016_完备文档体系.md
│   │   ├── ADR-017_原子提交规范.md
│   │   ├── ADR-018_domain_simulator_engine.md
│   │   ├── ADR-019_多模态文档处理流水线.md
│   │   ├── ADR-020_管理员控制台统一界面.md
│   │   ├── ADR-022_模拟数仓与统一查询服务.md
│   │   ├── ADR-023_多工作空间隔离架构.md
│   │   ├── ADR-024_本体驱动分析核心架构.md
│   │   ├── ADR-025_openharness_integration.md
│   │   ├── ADR-026_mcp_protocol_integration.md
│   │   ├── ADR-027_hook_system_architecture.md
│   │   ├── ADR-028_permission_checker_opa_integration.md
│   │   ├── ADR-029_tool_registry_architecture.md
│   │   ├── ADR-030_phase1_推迟引入openharness_保留现有编排器.md
│   │   ├── ADR-031_simulator_web_visualization_realtime_ontology.md
│   │   ├── ADR-032_standard_ontology_document_format.md
│   │   ├── ADR-033_项目目录结构重构.md
│   │   ├── ADR-036_palantir_ontology_reference.md
│   │   └── ADR-037_frontend_mobile_first_i18n.md   # ⭐ 新增
│   │
│   ├── modules/                 # 模块设计文档 (16个模块)
│   │   ├── README.md            # 模块索引
│   │   ├── agent/DESIGN.md
│   │   ├── decision_recommendation/DESIGN.md
│   │   ├── graphiti_client/DESIGN.md
│   │   ├── hook_system/DESIGN.md
│   │   ├── infra/DESIGN.md
│   │   ├── mcp_protocol/DESIGN.md
│   │   ├── mock_engine/DESIGN.md
│   │   ├── ontology/DESIGN.md
│   │   ├── opa_policy/DESIGN.md
│   │   ├── openharness_bridge/DESIGN.md
│   │   ├── permission_checker/DESIGN.md
│   │   ├── simulator/DESIGN.md
│   │   ├── skills/DESIGN.md
│   │   ├── swarm_orchestrator/DESIGN.md
│   │   ├── visualization/DESIGN.md
│   │   └── web/DESIGN.md
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
│  │ req-alpha   │  │  req-beta   │  │  req-ok ⭐  │  │ TASK_BREAK  │  │
│  │ 技术研究    │  │ 需求草稿    │  │ 需求定稿    │  │ 任务拆分    │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
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
│   37个ADR文档   │   │   16个模块设计   │   │   UI设计规范    │
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
1. docs/req-beta.md                    需求规格说明书
       ↓
2. docs/ARCHITECTURE.md               核心架构文档
       ↓
3. docs/ui/UI_DESIGN.md               UI 设计稿
       ↓
4. docs/modules/web/DESIGN.md         前端模块设计
       ↓
5. docs/frontend/src/                 前端代码
```

### 3.2 前端开发路径

```
1. docs/ARCHITECTURE.md (第11章)      前端界面架构
       ↓
2. docs/adr/ADR-007_前端技术栈.md     技术选型
       ↓
3. docs/adr/ADR-037_frontend_mobile_first_i18n.md  ⭐ 移动优先+国际化
       ↓
4. docs/ui/UI_DESIGN.md               UI 设计稿
       ↓
5. docs/ui/MOBILE_FIRST_DESIGN.md    移动优先规范
       ↓
6. docs/ui/COMPONENT_HIERARCHY.md    组件分级管理
       ↓
7. frontend/src/                      前端代码实现
```

### 3.3 后端开发路径

```
1. docs/ARCHITECTURE.md               核心架构文档（全文）
       ↓
2. docs/TASK_BREAKDOWN.md             任务拆分与 Phase 规划
       ↓
3. docs/modules/*/DESIGN.md           相关模块设计
       ↓
4. odap/                              后端代码
```

### 3.4 架构师路径

```
1. docs/req-beta.md                   需求规格
       ↓
2. docs/ARCHITECTURE.md              核心架构（全文精读）
       ↓
3. docs/adr/README.md               ADR 索引
       ↓
4. 相关 ADR 文档                      架构决策详情
```

---

## 4. 文档关系矩阵

| 上游文档 | 下游文档 | 关系类型 |
|----------|----------|----------|
| req-beta.md | ARCHITECTURE.md | 需求→架构 |
| ARCHITECTURE.md | TASK_BREAKDOWN.md | 架构→任务 |
| ARCHITECTURE.md | docs/modules/*/DESIGN.md | 架构→模块 |
| ARCHITECTURE.md | docs/ui/UI_DESIGN.md | 架构→UI |
| ARCHITECTURE.md | docs/adr/* | 架构→决策 |
| ADR-007 | docs/ui/UI_DESIGN.md | 技术选型→UI |
| ADR-037 | docs/ui/MOBILE_FIRST_DESIGN.md | 响应式→移动 |
| UI_DESIGN.md | MOBILE_FIRST_DESIGN.md | 设计→规范 |
| UI_DESIGN.md | COMPONENT_HIERARCHY.md | 设计→组件 |
| TASK_BREAKDOWN.md | frontend/src/ | 任务→代码 |
| TASK_BREAKDOWN.md | odap/ | 任务→代码 |

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

### 5.2 前端与 UI

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-007 | 前端采用 React + Ant Design 技术栈 | 已接受 |
| ADR-015 | 可扩展图表系统 | 已接受 |
| ADR-020 | 管理员控制台统一界面 | 已接受 |
| ADR-031 | Simulator Web 可视化 | 已接受 |
| **ADR-037** | **前端移动优先、响应式设计和国际化策略** | **已接受** ⭐ |

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

### 5.5 技能与扩展

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-004 | 统一 Skill 体系架构 | 已接受 |
| ADR-011 | 角色配置热生效 | 已接受 |
| ADR-012 | 配置组合引擎 | 已接受 |
| ADR-014 | 技能热插拔架构 | 已接受 |
| ADR-026 | MCP 协议集成 | 已接受 |

### 5.6 运行时引擎

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-018 | Domain Simulator Engine | 已接受 |
| ADR-019 | 多模态文档处理流水线 | 已接受 |
| ADR-023 | 多工作空间隔离架构 | 已接受 |
| ADR-024 | 本体驱动分析核心架构 | 已接受 |

---

## 6. 模块设计索引

| 模块 | 路径 | 说明 |
|------|------|------|
| Agent | modules/agent/DESIGN.md | Agent 核心架构 |
| Web | modules/web/DESIGN.md | Web 前端模块 |
| Ontology | modules/ontology/DESIGN.md | 本体管理模块 |
| Simulator | modules/simulator/DESIGN.md | 模拟器模块 |
| Skills | modules/skills/DESIGN.md | 技能系统模块 |
| OPA Policy | modules/opa_policy/DESIGN.md | OPA 策略模块 |
| Visualization | modules/visualization/DESIGN.md | 可视化模块 |
| Hook System | modules/hook_system/DESIGN.md | 钩子系统模块 |
| Tool Registry | - | 工具注册（见 ADR-029） |
| Swarm Orchestrator | modules/swarm_orchestrator/DESIGN.md | 蜂群编排器 |

---

## 7. UI 设计文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| UI 设计稿 | ui/UI_DESIGN.md | 完整的 UI 视觉和交互设计 |
| 移动优先设计 | ui/MOBILE_FIRST_DESIGN.md | 响应式设计详细规范 |
| 组件分级管理 | ui/COMPONENT_HIERARCHY.md | 组件 L1-L5 分级体系 |
| **文档关系图** | ui/DOCUMENT_RELATIONSHIP.md | **本文档 - 项目索引** |

---

## 8. 文档更新规则

| 变更场景 | 必须更新的文档 |
|----------|---------------|
| 新功能需求 | req-beta.md → TASK_BREAKDOWN.md |
| 架构调整 | ARCHITECTURE.md → ADR → 模块 DESIGN |
| UI 变更 | UI_DESIGN.md → MOBILE_FIRST_DESIGN → 前端代码 |
| 前端技术选型 | ADR-007 → ARCHITECTURE.md |
| 响应式/国际化 | ADR-037 → MOBILE_FIRST_DESIGN → 前端代码 |
| 组件重构 | COMPONENT_HIERARCHY.md → 前端代码 |
| 模块设计变更 | 对应 modules/*/DESIGN.md → ARCHITECTURE.md |

---

## 9. 相关文档链接

### 需求文档
- [需求定稿 ⭐](../req-ok.md)（唯一权威来源）
- [原始技术研究](../req-alpha.md)（归档）
- [早期需求规格](../req-beta.md)（归档）
- [任务拆分与计划](../TASK_BREAKDOWN.md)

### 架构文档
- [核心架构文档](../ARCHITECTURE.md)
- [ADR 索引](../adr/README.md)

### UI 设计文档
- [UI 设计稿](./UI_DESIGN.md)
- [移动优先设计](./MOBILE_FIRST_DESIGN.md)
- [组件分级管理](./COMPONENT_HIERARCHY.md)
- [文档关系图](./DOCUMENT_RELATIONSHIP.md) ← 你在这里

### ADR 文档
- [ADR-007: 前端技术栈](../adr/ADR-007_前端采用_react_ant_design_技术栈.md)
- [ADR-037: 移动优先与国际化](../adr/ADR-037_frontend_mobile_first_i18n.md)
- [ADR-036: 领域实体标准本体库](../adr/ADR-036_palantir_ontology_reference.md)

### 模块设计
- [Web 模块设计](../modules/web/DESIGN.md)
- [Ontology 模块设计](../modules/ontology/DESIGN.md)
- [Simulator 模块设计](../modules/simulator/DESIGN.md)
