# 模块设计文档索引

> **版本**: 3.0.0 | **更新日期**: 2026-07-03
> 本文档索引了 ODAP（本体驱动 AI 平台）的所有模块设计文档。

---

## 模块总览

### 后端模块（39 个，按 9 大业务领域组织）

#### core/ — 核心领域（4 模块）

| 模块 | 路径 | 职责 | 状态 |
|------|------|------|------|
| Agent 编排 | `odap/biz/core/agent/` | 多 Agent 协同、Swarm 调度 | ✅ 活跃 |
| Assistant 助手 | `odap/biz/core/assistant/` | AI 助手服务、插件系统 | ✅ 活跃 |
| Cognition 认知 | `odap/biz/core/cognition/` | 认知引擎、思维图谱 | ✅ 活跃 |
| Ontology 本体 | `odap/biz/core/ontology/` | 本体管理、版本控制、蓝图设计、语义层、服务化（17+ 子模块） | ✅ 活跃 |

#### data/ — 数据领域（8 模块）

| 模块 | 路径 | 职责 | 状态 |
|------|------|------|------|
| Data Warehouse 数仓 | `odap/biz/data/data_warehouse/` | 模拟数据仓库 | ✅ 活跃 |
| Hyper Extract 超提取 | `odap/biz/data/hyper_extract/` | 高性能实体/关系提取 | ✅ 活跃 |
| Ingest 摄入 | `odap/biz/data/ingest/` | 统一数据摄入 API | ✅ 活跃 |
| Knowledge Base 知识库 | `odap/biz/data/knowledge_base/` | 文档管理、图谱构建、双轨存储 | ✅ 活跃 |
| Perception 感知 | `odap/biz/data/perception/` | 观察者模式感知层 | ✅ 活跃 |
| QA 问答 | `odap/biz/data/qa/` | RAG 问答引擎、语义检索 | ✅ 活跃 |
| Semantic Map 语义地图 | `odap/biz/data/semantic_map/` | 本体可视化语义地图 | ✅ 活跃 |
| Web Crawl 网页抓取 | `odap/biz/data/web_crawl/` | 网页内容采集与解析 | ✅ 活跃 |

#### decision/ — 决策领域（3 模块）

| 模块 | 路径 | 职责 | 状态 |
|------|------|------|------|
| Action Service 动作服务 | `odap/biz/decision/action_service/` | 动作执行、OPA 校验、回写 | ✅ 活跃 |
| Decision Pipeline 管线 | `odap/biz/decision/decision_pipeline/` | 决策流水线编排 | ✅ 活跃 |
| Decision Recommendation 推荐 | `odap/biz/decision/decision_recommendation/` | 方案推荐与风险评估 | ✅ 活跃 |

#### integration/ — 集成领域（5 模块）

| 模块 | 路径 | 职责 | 状态 |
|------|------|------|------|
| Channel Management 通道 | `odap/biz/integration/channel_management/` | 外部通信通道管理 | ✅ 活跃 |
| Frontend Compat 前端兼容 | `odap/biz/integration/frontend_compat/` | 前端 API 兼容层 | ✅ 活跃 |
| Hook System 钩子 | `odap/biz/integration/hook_system/` | 事件订阅/发布、异步广播 | ✅ 活跃 |
| MCP Adapter 适配器 | `odap/biz/integration/mcp_adapter/` | Model Context Protocol 集成 | ✅ 活跃 |
| OpenHarness Agent | `odap/biz/integration/openharness_agent/` | OpenHarness v1/v2 适配 | ✅ 活跃 |

#### management/ — 管理领域（2 模块）

| 模块 | 路径 | 职责 | 状态 |
|------|------|------|------|
| Agent Management 智能体管理 | `odap/biz/management/agent_management/` | 智能体 CRUD、配置 | ✅ 活跃 |
| Business 业务 | `odap/biz/management/business/` | 业务实体/规则/流程管理 | ✅ 活跃 |

#### platform/ — 平台领域（11 模块）

| 模块 | 路径 | 职责 | 状态 |
|------|------|------|------|
| Config 配置 | `odap/biz/platform/config/` | 系统配置管理 | ✅ 活跃 |
| i18n 国际化 | `odap/biz/platform/i18n/` | 多语言支持 | ✅ 活跃 |
| Menu Config 菜单配置 | `odap/biz/platform/menu_config/` | RBAC 三级菜单管理 | 🆕 新增 |
| MinIO Admin 对象存储管理 | `odap/biz/platform/minio_admin/` | MinIO 管理界面 | ✅ 活跃 |
| Ontology Memory 本体记忆 | `odap/biz/platform/ontology_memory/` | 本体记忆、图同步、共享工作空间、衰减 | ✅ 活跃 |
| Roles 角色 | `odap/biz/platform/roles/` | 角色管理与分配 | ✅ 活跃 |
| Session Memory 会话记忆 | `odap/biz/platform/session_memory/` | 会话上下文记忆 | ✅ 活跃 |
| Skill System 技能系统 | `odap/biz/platform/skill_system/` | 技能注册、管理、扩展 | ✅ 活跃 |
| Tool Registry 工具注册表 | `odap/biz/platform/tool_registry/` | 统一工具发现与调度 | ✅ 活跃 |
| Undo 撤销 | `odap/biz/platform/undo/` | 操作撤销与回退 | ✅ 活跃 |
| Workspace 工作空间 | `odap/biz/platform/workspace/` | 多工作空间隔离、场景管理 | ✅ 活跃 |

#### simulation/ — 仿真领域（5 模块）

| 模块 | 路径 | 职责 | 状态 |
|------|------|------|------|
| Event Simulator 事件模拟器 | `odap/biz/simulation/event_simulator/` | 事件生成与图谱演化 | ✅ 活跃 |
| Feedback 反馈 | `odap/biz/simulation/feedback/` | 仿真反馈收集 | ✅ 活跃 |
| Simulation Deduction 推演 | `odap/biz/simulation/simulation_deduction/` | 策略推演引擎 | ✅ 活跃 |
| Simulation Sandbox 沙盘 | `odap/biz/simulation/simulation_sandbox/` | 并行沙盘推演 | ✅ 活跃 |
| Visualization 可视化 | `odap/biz/simulation/visualization/` | 仿真结果可视化 | ✅ 活跃 |

#### semantic_admin/ — 语义管理台顶级域（7 子服务）

| 模块 | 路径 | 职责 | 状态 |
|------|------|------|------|
| Semantic Admin 语义管理台 | `odap/biz/semantic_admin/` | 顶级域 — USL 管理 + OL 6 层流水线 + 质量闸 + 2级审批 + HITL 飞轮（[specs/007-semantic-admin-suite/](file:///e:/DEMO/AI/ontology-graphiti/specs/007-semantic-admin-suite/)） | ✅ 活跃 |
|   - usl_manager USL 管理 | `odap/biz/semantic_admin/usl_manager/` | USL 元数据 CRUD、分类层级、版本快照发布/回滚、角色分配、Seed 迁移脚本（--check/--apply/--rollback/--domain） | ✅ 活跃 |
|   - ol_pipeline OL 流水线 | `odap/biz/semantic_admin/ol_pipeline/` | 6 层 Ontology Learning 状态机（L1 term tokenize Ngram + BGE embedding + HDBSCAN 聚类 → L2 concept merge 聚类 → L3 FCA 形式概念格+BordNet 层级 → L4 4 类关系分类 is-a/part-of/attr-of/related → L5 三分类融合 merge/keep/flag → L6 OWL 公理 subClassOf/disjoint/domain/range/card） | ✅ 活跃 |
|   - candidate_store 候选存储 | `odap/biz/semantic_admin/candidate_store/` | 语义草稿去重、MinHash 聚类、增量合并、SQLite + Neo4j 双写持久化 | ✅ 活跃 |
|   - quality_gate 质量闸 | `odap/biz/semantic_admin/quality_gate/` | 16 子指标三关公式化、O(N) 纯算 P95≤100ms | ✅ 活跃 |
|   - approval_workflow 审批 | `odap/biz/semantic_admin/approval_workflow/` | 10 状态机 + OPA 二级审批 + 加速通道判定 | ✅ 活跃 |
|   - usl_writeback 写回 | `odap/biz/semantic_admin/usl_writeback/` | 审批通过写回本体 TBox + 同步 Neo4j 从副本 + 语义地图 + I4T8 手动触发/状态查询 API | ✅ 活跃 |
|   - sa_config 动态配置 | `odap/biz/semantic_admin/sa_config/` | 语义层配置从硬编码迁移到 SQLite 持久化（scoped key/value）+ ensure-builtin 内置常量化石回填 | ✅ 活跃 |

#### shared/ — 共享工具（无子模块）

### 前端模块（23 个）

| 模块 | 路径 | 职责 |
|------|------|------|
| Agent | `frontend/src/modules/agent/` | 智能体对话、管理 |
| AI Assistant | `frontend/src/modules/ai-assistant/` | AI 助手组件 |
| Audit | `frontend/src/modules/audit/` | 审计日志查看 |
| Business | `frontend/src/modules/business/` | 业务实体/规则/流程 |
| Channels | `frontend/src/modules/channels/` | 通信通道管理 |
| Config | `frontend/src/modules/config/` | 系统配置 |
| Guide | `frontend/src/modules/guide/` | 新手引导 |
| i18n Admin | `frontend/src/modules/i18n-admin/` | 国际化管理 |
| Iframe Viewer | `frontend/src/modules/iframe-viewer/` | 外部页面嵌入 |
| Ingest | `frontend/src/modules/ingest/` | 数据摄入 |
| Knowledge | `frontend/src/modules/knowledge/` | 知识库文档管理 |
| Menu Config | `frontend/src/modules/menu-config/` | RBAC 菜单配置 |
| MinIO Admin | `frontend/src/modules/minio-admin/` | 对象存储管理 |
| Ontology | `frontend/src/modules/ontology/` | 本体构建、蓝图设计 |
| QA | `frontend/src/modules/qa/` | 问答界面、AgUI |
| Roles | `frontend/src/modules/roles/` | 角色管理 |
| Settings | `frontend/src/modules/settings/` | 用户设置 |
| Shared | `frontend/src/modules/shared/` | 共享组件、布局、API |
| Simulation | `frontend/src/modules/simulation/` | 仿真推演 |
| System | `frontend/src/modules/system/` | 系统管理（技能等） |
| Version | `frontend/src/modules/version/` | 版本历史 |
| Workspace | `frontend/src/modules/workspace/` | 工作空间管理 |
| Semantic Admin | `frontend/src/modules/semantic-admin/` | 语义管理台（路由 /semantic-admin/*，子页：/usl /pipeline /candidates /quality） |

### API 路由注册（80 个路由）

所有后端路由通过 `odap/web/router_registry.py` 集中注册到生产入口 `odap/web/app.py`。

---

## 六层架构图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ L6  用户交互层                                                                │
│     frontend/ (React 19 + Ant Design 6 + Zustand)                            │
├──────────────────────────────────────────────────────────────────────────────┤
│ L5  API 网关层                                                                │
│     odap/web/gateway/ (认证/限流/路由/权限)                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ L4  应用服务层                                                                │
│     biz/data/qa        │ biz/decision/       │ biz/simulation/ │ biz/data/    │
│     (问答引擎)          │ (决策推荐/管线/动作)  │ (推演/沙盘/模拟) │ semantic_map │
├──────────────────────────────────────────────────────────────────────────────┤
│ L3  Agent 编排层                                                              │
│     biz/core/agent (Swarm 编排) │ biz/management/agent_management (Agent 管理) │
├──────────────────────────────────────────────────────────────────────────────┤
│ L2  领域技能层                                                                │
│     biz/platform/skill_system │ biz/platform/tool_registry │ biz/integration/ │
│     (技能系统)                │ (工具注册表)                 │ openharness_agent│
├──────────────────────────────────────────────────────────────────────────────┤
│ L1  基础设施层                                                                │
│     infra/graph/ (Graphiti) │ infra/opa/ (OPA) │ biz/core/ontology/ (本体)    │
│     biz/platform/workspace/ │ biz/integration/hook_system/ (Hook)            │
│     biz/integration/mcp_adapter/ (MCP) │ infra/security/ (审计日志)            │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 核心依赖链

### 问答链（用户 → 知识 → 答案）

```
frontend/ → web/gateway/ → biz/data/qa/ → infra/graph/ + biz/platform/skill_system/
                                    ↓
                              biz/core/agent/ (复杂问题升级)
```

### 决策链（情报 → 分析 → 决策 → 执行）

```
biz/simulation/event_simulator/ → biz/simulation/simulation_sandbox/ → biz/decision/ → biz/core/agent/
                                                                              ↓
                                                                        infra/opa/ 校验
                                                                              ↓
                                                                        infra/graph/
```

### 管理链（配置 → 生效 → 审计）

```
biz/core/ontology/ → biz/platform/workspace/ → biz/integration/hook_system/ → infra/security/ (审计)
       ↓                    ↓
  infra/graph/         infra/opa/
```

---

## 核心模块摘要

### biz/platform/workspace/ — 工作空间管理
- **职责**: 多场景隔离，工作空间 CRUD/切换/导入导出
- **隔离策略**: Neo4j 多数据库 + OPA Bundle 路径隔离 + Skill 注册表命名空间
- **关键接口**: `IWorkspaceProvider` — 供基础设施层组件获取当前上下文

### infra/security/ — 审计日志
- **职责**: 100% 操作覆盖的审计追踪，时间线可视化，防篡改校验链
- **写入策略**: 异步 Channel + 批量落盘，CRITICAL 级别同步写入
- **关键接口**: `AuditLogger.log()` / `AuditLogger.start_span()`

### biz/platform/tool_registry/ — 工具注册表
- **职责**: 统一管理 Skill/内置/MCP/外部 API 工具，运行时发现与调度
- **与 Skill 关系**: Skill 是编写规范，Tool Registry 是运行时注册表
- **关键接口**: `IToolRegistry.discover()` / `IToolRegistry.execute()`

### biz/data/qa/ — 问答引擎
- **职责**: 自然语言问答，RAG 增强生成，双时态查询，溯源追踪
- **升级策略**: 简单→QAEngine 直处理，复杂→升级到 Intelligence Agent
- **关键接口**: `QAEngine.ask()` / `QAEngine.ask_with_tools()`

### biz/decision/decision_recommendation/ — 决策推荐
- **职责**: OADP 决策阶段核心，基于分析结果生成方案推荐与风险评估
- **核心能力**: 方案生成、优先级排序、OPA 策略校验、RAG 增强推理、反馈记录
- **关键接口**: `DecisionRecommendationEngine.generate_recommendation()` / `record_feedback()`

### biz/simulation/event_simulator/ — 事件模拟器
- **职责**: 自动/手动生成模拟事件，驱动知识图谱状态演化
- **与推演关系**: 事件模拟器生成"发生了什么"，推演引擎分析"该怎么做"
- **关键接口**: `EventSimulator.create_scenario()` / `EventSimulator.inject_event()`

### odap/web/gateway/ — API 网关
- **职责**: 统一入口，认证鉴权，流量治理，协议适配
- **管道**: Request → CORS → Auth → RateLimit → Route → Permission → Proxy → Response
- **关键接口**: REST API + WebSocket + SSE

### frontend/ — Web 前端
- **职责**: 用户交互界面，全流程可视化
- **技术栈**: React 19 + TypeScript + Ant Design 6 + Zustand + Vite
- **关键页面**: 智能问答(P0)、审计日志(P0)、工具管理(P1)

---

## 文档维护

| 规则 | 说明 |
|------|------|
| 更新时机 | 模块重构、接口变更、重大功能调整时更新 |
| 审批 | 需技术负责人 Review 后合并 |
| 版本 | 与模块代码版本保持一致 |
| 合并/拆分 | 在原文档头部标注合并声明，保留供历史参考 |
| **防腐机制** | 新增/删除模块必须同步更新本文档；提交前对照 `docs/09-checklists/DOC_SYNC_CHECKLIST.md` 检查 |
| **过期检测** | 对比 `odap/biz/` 和 `frontend/src/modules/` 实际目录与本文档列表，不一致时立即修正 |
| **优先级** | 本文档与代码冲突时以 `agents.md` 为最高裁决；发现不一致不留 TODO，立即修正 |
