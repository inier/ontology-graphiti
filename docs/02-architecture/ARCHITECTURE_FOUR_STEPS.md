# 基于本体四步法（建/见/演/用）的项目功能梳理与菜单归集

> **版本**: v1.0 (2026-08-01)
> **依据**: [CONTEXT.md](../../CONTEXT.md) 统一语言表 / [ADR-073](../07-adr/ADR-073_基于本体的数据服务四步落地架构.md) 四步落地架构
> **范围**: 前端 50+ 路由 + 后端 60+ 路由模块 + 5 个 spec feature (003/005/006/007/008)
> **目的**: 以"建本体/见本体/演本体/用本体"四步法为轴线，重新梳理项目全部功能模块，归集关联菜单，识别偏差与缺失项，为菜单重构提供事实依据。

---

## 1. 四步法架构定义

### 1.1 核心架构

| 阶段 | 核心能力 | 现有资产 | 关键约束 |
|------|---------|---------|---------|
| **建本体** (Ontology Construction) | 手动+AI 混合建模 | Ontology Designer、Hyper-Extract 链路、USL OL 流水线 | USL OL 6 层流水线 + HITL 飞轮 |
| **见本体** (Ontology Exploration) | 图谱探查（编辑态/探查态分离） | OntologyGraphPage、graph_viewer、USL 候选双写 | 候选态默认对业务人员不可见；`valid=false` 过滤 |
| **演本体** (Ontology Simulation) | 微观推演 + 宏观孪生 | DeductionEngine、DecisionRecommendation、sandbox 隔离 | 双时态隔离（`scenario_id` + `valid=false`） |
| **用本体** (Ontology Consumption) | API/SDK/MCP 开放 | 语义检索服务总线（spec 008）、MCP 桥 | 三层架构（统一/分项/混合检索）+ FR-010 一致性 |
| **横向支撑** | USL 语义规范总线 + 平台基础设施 | 工作空间/权限/审计/配置 | USL 贯穿四步（独立于本体） |

### 1.2 术语关系

```
本体 (Ontology) = TBox (结构) + ABox (实例)
USL (Unified Semantic Layer) = 横向语义规范总线（独立于本体，贯穿四步）

建本体 ──→ 构造 TBox/ABox
见本体 ──→ 探查 TBox/ABox（编辑态/探查态分离）
演本体 ──→ 基于 TBox 规则 + ABox 数据推演（双时态隔离）
用本体 ──→ 开放本体能力（REST/MCP/SDK + 语义检索总线）
```

---

## 2. 建本体（Ontology Construction）

**定义**：通过 Ontology Designer 手动建模 + Hyper-Extract AI 智能辅助建模，构建 TBox/ABox 的过程。对应 User Story 1/2。

### 2.1 归集菜单

| 菜单路径 | 页面路由 | 后端模块 | 功能说明 |
|---------|---------|---------|---------|
| 建本体 / 本体设计器 | `/ontology/designer` | `ontology_model`, `ontology_engine`, `ontology_api`, `registry` | TBox 结构设计（ObjectType/RelationType/Property/ActionType） |
| 建本体 / 蓝图设计器 | `/blueprint` | `blueprint_designer`, `blueprint_runtime`, `harness` | 可视化蓝图编排 + Harness 装配 |
| 建本体 / 目标看板 | `/ontology/goals` | `goal` | 建模目标管理 + 进度追踪 |
| 建本体 / 版本管理 | `/versions` | `ontology_version`, `branch`, `conflict` | 版本快照 + 分支管理 + 冲突解决 |
| 建本体 / 数据摄入 | `/ingest` | `unified_ingest`, `web_collection`, `ingestion` | 统一数据摄入 + Web 爬取 + 文档导入 |
| 建本体 / 知识库 | `/knowledge` | `kb` | 知识库管理（文档源） |
| 建本体 / HE 抽取链 | （后端 API） | `he`, `extraction` | Hyper-Extract 模板引擎 + 抽取链（spec 006） |
| 建本体 / 冷启动/继承/计算 | （后端 API） | `cold_start`, `inheritance`, `computed` | 本体冷启动模板 + 继承链 + 计算属性 |

### 2.2 语义管理子菜单（USL 建模侧 — spec 007）

| 菜单路径 | 页面路由 | 后端模块 | 功能说明 |
|---------|---------|---------|---------|
| 建本体 / 语义管理 / USL 配置 | `/semantic-admin/usl` | `usl_manager`, `sa_config` | USL 域管理 + 术语配置 |
| 建本体 / 语义管理 / OL 流水线 | `/semantic-admin/pipeline` | `ol_pipeline` | 6 层 OL 流水线运行管理 |
| 建本体 / 语义管理 / 候选管理 | `/semantic-admin/candidates` | `candidate_store` | Candidate CRUD + 批量操作 + 导出 |
| 建本体 / 语义管理 / 审批工作流 | `/semantic-admin/approvals` | `approval_workflow` | 2 级审批（L1 质检 → L2 评审） |
| 建本体 / 语义管理 / 质量仪表盘 | `/semantic-admin/quality` | `quality_gate` | QualityGate 16 指标评估 |
| 建本体 / 语义管理 / USL 写回 | （后端 API） | `usl_writeback` | APPROVED 候选写回图谱 |

### 2.3 后端 API 路由（无前端页面）

| 后端模块 | 路由前缀 | 功能 |
|---------|---------|------|
| `ontology_model` | 本体模型 CRUD | ObjectType/RelationType 定义 |
| `ontology_engine` | 本体引擎 | 模型校验 + 引擎执行 |
| `ingestion` | 数据注入 | 文档/结构化数据注入 |
| `ontology_version` | 版本管理 | 快照 + 版本对比 |
| `registry` | TypeRegistry | 统一类型定义读写入口 |
| `extraction` | 抽取 | HE 抽取执行 |
| `goal` | 目标 | 建模目标管理 |
| `branch` | 分支 | 本体分支管理 |
| `conflict` | 冲突 | 冲突检测与解决 |
| `cold_start` | 冷启动 | 本体冷启动模板 |
| `inheritance` | 继承 | 本体继承链 |
| `computed` | 计算属性 | 计算属性定义 |
| `harness` | Harness | 装配运行时 |
| `blueprint_designer` | 蓝图 | 蓝图设计 |
| `blueprint_runtime` | 蓝图运行时 | 蓝图执行 |
| `he` | Hyper-Extract | HE 模板/抽取/验证 |
| `unified_ingest` | 统一摄入 | 多源数据摄入 |
| `web_collection` | Web 采集 | 网页爬取 |
| `kb` | 知识库 | 文档管理 |
| `usl_manager` | USL 管理 | 域/术语 CRUD |
| `ol_pipeline` | OL 流水线 | 6 层流水线执行 |
| `candidate_store` | 候选存储 | Candidate CRUD |
| `approval_workflow` | 审批工作流 | 2 级审批 |
| `quality_gate` | 质量闸 | 16 指标评估 |
| `usl_writeback` | USL 写回 | 候选写回图谱 |
| `sa_config` | 语义管理配置 | 内置常量落库 |

---

## 3. 见本体（Ontology Exploration）

**定义**：以图形化方式探查和浏览本体内容，面向开发者（编辑态）和业务人员（探查态）提供不同权限视图。编辑态与探查态强制分离；候选态默认对业务人员不可见。

### 3.1 归集菜单

| 菜单路径 | 页面路由 | 后端模块 | 功能说明 |
|---------|---------|---------|---------|
| 见本体 / 本体图谱 | `/ontology/graph` | `object_view`, `ontology_api` | Sigma.js 图谱探查（编辑态/探查态切换） |
| 见本体 / 图谱查看器 | `/iframe-viewer` | `graph_viewer` | 嵌入式图谱查看器（业务人员只读） |
| 见本体 / 知识导航 | `/knowledge/navigation` | `query`, `data_warehouse` | 知识检索 + 数据仓库浏览 |
| 见本体 / 总览仪表盘 | `/semantic-admin/dashboard` | `quality_gate` | 语义管理总览仪表盘 |
| 见本体 / 语义地图 | （后端 API） | `semantic_map` | 基于场景的语义地图生成 |
| 见本体 / 消歧图 | （后端 API） | `abution_graph` | 实体消歧图可视化 |
| 见本体 / 认知图谱 | （后端 API） | `cognition`, `thought` | 认知图谱 + 思维图探查 |
| 见本体 / QA 管理 | `/qa` | `qa` | QA 问答对管理（探查态） |

### 3.2 后端 API 路由（无前端页面）

| 后端模块 | 路由前缀 | 功能 |
|---------|---------|------|
| `object_view` | 对象视图 | 视图定义 + 字段映射 |
| `graph_viewer` | 图谱查看器 | 嵌入式图谱查询 |
| `semantic_map` | 语义地图 | 场景语义地图 |
| `abution_graph` | 消歧图 | 实体消歧 |
| `cognition` | 认知 | 认知图谱 |
| `thought` | 思维图 | 思维图管理 |
| `query` | 查询 | 跨源查询服务 |
| `data_warehouse` | 数据仓库 | 数仓查询 |
| `qa` | QA | 问答对管理 |
| `qa_nl` | QA NL | 自然语言问答 |
| `oms` | OMS | 本体管理服务 |
| `ontology_nl` | 本体 NL | 本体自然语言查询 |
| `ontology_ingest` | 本体摄入 | 本体数据摄入查询 |

---

## 4. 演本体（Ontology Simulation）

**定义**：基于本体模型（TBox 规则 + ABox 数据）进行沙盘推演，预测不同策略的可能结果。包含微观规则推演（Deduction）和宏观孪生推演（Decision）。推演数据双时态隔离（带 `scenario_id` + `valid=false`），默认对查询服务不可见。

### 4.1 归集菜单

| 菜单路径 | 页面路由 | 后端模块 | 功能说明 |
|---------|---------|---------|---------|
| 演本体 / 策略推演 | `/simulation/deduction` | `deduction`, `sandbox` | 微观规则推演（DeductionEngine） |
| 演本体 / 仿真沙盘 | `/simulation` | `event_simulator`, `sandbox_api`, `parallel` | 宏观孪生推演 + 事件注入 + 并行沙箱 |
| 演本体 / 模拟器 | `/simulator` | `sandbox` | 沙箱模拟器（数据注入/时钟控制） |
| 演本体 / 业务流程 | `/business/process` | `business` | 业务流程编排 |
| 演本体 / 业务规则 | `/business/rules` | `business`, `policy` | 业务规则管理 |
| 演本体 / 业务指标 | `/business/indicators` | `business` | 业务指标定义 |
| 演本体 / 业务逻辑 | `/business/logic` | `business` | 业务逻辑编排 |
| 演本体 / 对象管理 | `/business/entities` | `business` | 业务对象管理 |
| 演本体 / 策略编辑器 | `/policy-editor` | `policy`, `markdown_policy` | OPA Rego 策略编辑 + 版本管理 |

### 4.2 后端 API 路由（无前端页面）

| 后端模块 | 路由前缀 | 功能 |
|---------|---------|------|
| `deduction` | 推演 | 微观规则推演引擎 |
| `event_simulator` | 事件模拟 | 事件注入 + 时钟控制 |
| `sandbox` | 沙箱 | 沙箱隔离 + 生命周期 |
| `sandbox_api` | 沙箱 API | 沙箱操作接口 |
| `parallel` | 并行 | 并行沙箱执行 |
| `feedback` | 反馈 | 推演结果反馈 |
| `runtime` | 运行时 | 本体运行时引擎 |
| `state_machine` | 状态机 | 状态机执行 |
| `action_type` | 动作类型 | ActionType 执行 |
| `ontology_memory` | 本体记忆 | 记忆持久化 |
| `decay` | 记忆衰减 | 衰减策略 |
| `memory_sync` | 记忆同步 | 图谱同步 |
| `shared_memory` | 共享记忆 | 共享工作空间 |
| `consensus` | 共识 | 多智能体共识 |
| `decision_pipeline` | 决策流水线 | 决策编排 |
| `decision_recommendation` | 决策推荐 | 推荐引擎 |
| `perception` | 感知 | 数据感知 |
| `business` | 业务管理 | 流程/规则/指标/逻辑 |
| `policy` | 策略 | OPA Rego 策略 |
| `markdown_policy` | Markdown 策略 | Markdown 策略文档 |

---

## 5. 用本体（Ontology Consumption）

**定义**：将本体能力通过 RESTful API / MCP Server / SDK 形式开放给下游智能体和业务系统调用。对外暴露 Facade 门面 `OntologyGateway` 和统一的 `SemanticRetrievalService`。核心新增架构是语义检索服务总线（spec 008 / ADR-073）。

### 5.1 语义检索服务总线（三层架构 — spec 008）

| 菜单路径 | API 端点 | MCP 工具 | 功能说明 |
|---------|---------|---------|---------|
| 用本体 / 语义检索 / 统一检索 | `POST /api/v1/ontology/query` | `ontology_query` | 自动路由检索 |
| 用本体 / 语义检索 / 链式推理 | `POST /api/v1/ontology/chain` | `ontology_reason` | chain 推理 + 循环检测 + 推理结论持久化(opt-in) |
| 用本体 / 语义检索 / NL 推理 | `POST /api/v1/ontology/nl` | `ontology_nl` | 自然语言推理 |
| 用本体 / 语义检索 / MDL 推理 | `POST /api/v1/ontology/mdl` | `ontology_mdl` | MDL/DSL 模板推理（复用 HE YAML）+ 推理结论持久化(opt-in) |
| 用本体 / 语义检索 / 图检索 | `POST /api/v1/ontology/graph` | `ontology_graph` | Cypher/GraphQL 图检索 |
| 用本体 / 语义检索 / 指标查询 | `POST /api/v1/ontology/metric` | `ontology_metric` | BI 指标聚合查询 |
| 用本体 / 语义检索 / 混合检索 | `POST /api/v1/ontology/hybrid` | `ontology_hybrid` | components 编排（concat/interleave/rank） |

### 5.2 QA 与查询服务

| 菜单路径 | 页面路由 | 后端模块 | 功能说明 |
|---------|---------|---------|---------|
| 用本体 / QA 查询 | `/qa/query` | `qa`, `qa_nl` | QA 问答查询 |
| 用本体 / QA 评估 | `/qa/evaluation` | `qa` | QA 质量评估 |

### 5.3 智能体子菜单

| 菜单路径 | 页面路由 | 后端模块 | 功能说明 |
|---------|---------|---------|---------|
| 用本体 / 智能体 / 我的智能体 | `/my-agents` | `agent_mgmt` | 智能体列表 |
| 用本体 / 智能体 / 对话 | `/agent-chat/:agentId` | `agent_dispatch`, `agent_decision` | 智能体对话交互 |
| 用本体 / 智能体 / 管理后台 | `/admin/agents` | `agent_mgmt` | 智能体管理 |
| 用本体 / 智能体 / 技能管理 | `/skills` | `skill_system`, `tool_registry` | 技能注册 + 工具注册 |

### 5.4 后端 API 路由（无前端页面）

| 后端模块 | 路由前缀 | 功能 |
|---------|---------|------|
| `semantic_retrieval` | 语义检索 | 7 端点 REST + 7 工具 MCP |
| `mcp_adapter` | MCP 适配 | MCP Server 桥接 |
| `agent_dispatch` | 智能体调度 | 智能体分发 |
| `agent_decision` | 智能体决策 | 决策路由 |
| `agent_mgmt` | 智能体管理 | 智能体 CRUD |
| `agui` | AGUI | AGUI 处理器 |
| `skill_system` | 技能系统 | 技能注册 + 执行 |
| `tool_registry` | 工具注册 | 工具注册表 |
| `hook_system` | 钩子系统 | 事件钩子 |
| `assistant` | AI 助手 | 助手服务 |
| `unified_chat` | 统一对话 | 对话服务（ADR-050） |
| `ontology_assistant` | 本体助手 | 本体 AI 辅助 |
| `session_memory` | 会话记忆 | 会话持久化 |
| `servitization` | 服务化 | 服务定义 |
| `deployment` | 部署 | 服务部署 |
| `catalog` | 目录 | 服务目录 |
| `osv2` | 对象服务 | 对象服务 v2 |
| `frontend_compat` | 前端兼容 | 兼容层 |
| `channel_management` | 渠道管理 | 渠道适配 |
| `openharness_agent` | OpenHarness | OpenHarness 适配 |

---

## 6. 横向支撑（跨四步平台基础设施）

**定义**：USL 语义规范总线（贯穿四步）+ 平台基础设施（工作空间/权限/审计/配置）。

### 6.1 归集菜单

| 菜单路径 | 页面路由 | 后端模块 | 功能说明 |
|---------|---------|---------|---------|
| 系统管理 / 工作空间 | `/workspace/manage` | `workspace` | 工作空间管理 |
| 系统管理 / 角色权限 | `/roles` | `roles` | RBAC 角色管理 |
| 系统管理 / 用户管理 | `/users` | `roles` | 用户管理 |
| 系统管理 / 审计日志 | `/audit` | `audit`, `data_classification` | 审计日志 + 数据分级 |
| 系统管理 / 菜单配置 | `/menu-config` | `menu_config` | 菜单树 + 角色权限分配 |
| 系统管理 / 设置 | `/settings` | `config` | 全局配置 |
| 系统管理 / 渠道管理 | `/settings/channels/:workspaceId` | `channel_management` | 渠道适配管理 |
| 系统管理 / 国际化 | `/i18n-admin` | `i18n` | i18n 翻译管理 |
| 帮助 / 使用指南 | `/guide` | — | 使用指南（首页默认） |

### 6.2 后端 API 路由（无前端页面）

| 后端模块 | 路由前缀 | 功能 |
|---------|---------|------|
| `workspace` | 工作空间 | 工作空间 CRUD + 场景兼容 |
| `roles` | 角色 | RBAC 角色权限 |
| `audit` | 审计 | 审计日志 |
| `auth` | 认证 | JWT 认证 |
| `data_classification` | 数据分级 | 数据分级标记 |
| `menu_config` | 菜单配置 | 菜单树 CRUD |
| `config` | 配置 | 全局配置 |
| `i18n` | 国际化 | i18n 翻译 |
| `undo` | 撤销 | 操作撤销栈 |
| `minio_admin` | MinIO | 对象存储管理 |
| `ws` | WebSocket | 实时推送 |
| `monitoring` | 监控 | 监控指标 |

---

## 7. 菜单结构总览（目标树形）

```
├── 建本体
│   ├── 本体设计器          (/ontology/designer)
│   ├── 蓝图设计器          (/blueprint)
│   ├── 目标看板            (/ontology/goals)
│   ├── 版本管理            (/versions)
│   ├── 数据摄入            (/ingest)
│   ├── 知识库              (/knowledge)
│   ├── HE 抽取链           (API / spec 006)
│   └── 语义管理 (USL)
│       ├── USL 配置        (/semantic-admin/usl)
│       ├── OL 流水线       (/semantic-admin/pipeline)
│       ├── 候选管理        (/semantic-admin/candidates)
│       ├── 审批工作流      (/semantic-admin/approvals)
│       └── 质量仪表盘      (/semantic-admin/quality)
│
├── 见本体
│   ├── 本体图谱            (/ontology/graph)
│   ├── 图谱查看器          (/iframe-viewer)
│   ├── 知识导航            (/knowledge/navigation)
│   ├── 总览仪表盘          (/semantic-admin/dashboard)
│   ├── 语义地图            (API)
│   ├── 消歧图              (API)
│   ├── 认知图谱            (API)
│   └── QA 管理             (/qa)
│
├── 演本体
│   ├── 策略推演            (/simulation/deduction)
│   ├── 仿真沙盘            (/simulation)
│   ├── 模拟器              (/simulator)
│   ├── 业务流程            (/business/process)
│   ├── 业务规则            (/business/rules)
│   ├── 业务指标            (/business/indicators)
│   ├── 业务逻辑            (/business/logic)
│   ├── 对象管理            (/business/entities)
│   └── 策略编辑器          (/policy-editor)
│
├── 用本体
│   ├── 语义检索服务总线
│   │   ├── 统一检索        (API: POST /query)
│   │   ├── 链式推理        (API: POST /chain)
│   │   ├── NL 推理         (API: POST /nl)
│   │   ├── MDL 推理        (API: POST /mdl)
│   │   ├── 图检索          (API: POST /graph)
│   │   ├── 指标查询        (API: POST /metric)
│   │   └── 混合检索        (API: POST /hybrid)
│   ├── QA 查询             (/qa/query)
│   ├── QA 评估             (/qa/evaluation)
│   ├── MCP 工具集          (7 tools)
│   └── 智能体
│       ├── 我的智能体      (/my-agents)
│       ├── 对话            (/agent-chat/:id)
│       ├── 管理后台        (/admin/agents)
│       └── 技能管理        (/skills)
│
├── 系统管理
│   ├── 工作空间            (/workspace/manage)
│   ├── 角色权限            (/roles)
│   ├── 用户管理            (/users)
│   ├── 审计日志            (/audit)
│   ├── 菜单配置            (/menu-config)
│   ├── 设置                (/settings)
│   ├── 渠道管理            (/settings/channels)
│   └── 国际化              (/i18n-admin)
│
└── 帮助
    └── 使用指南            (/guide, /)
```

---

## 8. 偏差分析与缺失项

### 8.1 当前菜单与四步架构的偏差

| # | 问题 | 现状 | 建议归属 | 优先级 |
|---|------|------|---------|--------|
| D1 | `/business/*` 归属模糊 | 5 个业务页面散落在顶层 | 演本体（业务规则即推演规则） | P0 |
| D2 | `/semantic-admin/*` 跨建/见 | 6 个语义管理页面在同一个 Tab 下 | 建本体（USL/流水线/候选/审批）+ 见本体（仪表盘/质量） | P0 |
| D3 | `/qa/*` 跨见/用 | 3 个 QA 页面在顶层 | QA 管理 → 见本体；QA 查询/评估 → 用本体 | P1 |
| D4 | `/simulator` vs `/simulation` | 两个仿真入口易混淆 | 合并为"演本体 / 仿真沙盘"统一入口 | P1 |
| D5 | `/ontology/graph` 命名冲突 | 与 `/api/v1/ontology/graph`（图检索 API）同名 | 前端改为 `/ontology/explorer`，API 保持 `/graph` | P2 |
| D6 | `/ingest` 含 HE 抽取 | 数据摄入与 HE 抽取链未关联 | 建本体下新增"HE 抽取链"子项关联 spec 006 | P2 |
| D7 | MCP 工具集无前端入口 | 7 个 MCP 工具仅 API 可用 | 用本体下新增"MCP 工具集"页面 | P2 |
| D8 | 推理结论持久化无入口 | 新增的 `persist_candidates` 无 UI | 候选管理页面增加"来源=reasoning"筛选 | P2 |

### 8.2 缺失的前端页面（有后端无前端）

| 后端模块 | 建议归属 | 功能 | 优先级 |
|---------|---------|------|--------|
| `servitization`/`catalog`/`deployment` | 用本体 / 服务化 | 服务目录 + 部署管理 | P2 |
| `semantic_map` | 见本体 / 语义地图 | 语义地图生成 | P3 |
| `abution_graph` | 见本体 / 消歧图 | 消歧图可视化 | P3 |
| `ontology_memory` 系列 | 演本体 / 本体记忆 | 记忆系统 | P3 |
| `perception` | 演本体 / 感知 | 数据感知 | P3 |

### 8.3 统计汇总

| 维度 | 数量 |
|------|------|
| 前端路由总数 | 51 |
| 后端路由模块总数 | 68 |
| 建本体归集（前端页面） | 14 |
| 见本体归集（前端页面） | 8 |
| 演本体归集（前端页面） | 9 |
| 用本体归集（前端页面） | 8 |
| 横向支撑归集（前端页面） | 9 |
| 缺失前端页面（有后端无前端） | 5 |
| 偏差项（需重构） | 8 |

---

## 9. 附录：Spec Feature 对照

| Spec | 标题 | 归属阶段 | 状态 |
|------|------|---------|------|
| 003 | 本体重设计 (ontology-redesign) | 建本体 | completed |
| 005 | 数据采集优化 (data-collection-opt) | 建本体 | completed |
| 006 | HE 抽取链 (he-extraction-chain) | 建本体 | active |
| 007 | 语义管理套件 (semantic-admin-suite) | 建本体 + 见本体 | active |
| 008 | 语义检索总线 (semantic-retrieval-bus) | 用本体 | active |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-08-01 | 初始版本：基于四步法梳理 51 路由 + 68 模块，识别 8 偏差 + 5 缺失 |
