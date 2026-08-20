# 架构决策记录（ADR）

本目录存放所有架构决策记录（Architecture Decision Records）。

> **索引治理规则（2026-08-16 起生效）**：本索引为 ADR 状态的**唯一权威来源**，每份 ADR 文件头的状态必须与本表一致；新增/变更 ADR 状态时必须同 PR 更新本表。"状态核验"列记录该 ADR 最后一次与代码现实核对的日期。

## 状态图例

| 状态 | 含义 |
|------|------|
| 已接受 | 决策生效；括号内为落地情况注记（无注记 = 已在役或决策性质无需代码） |
| 提议 | 已提交未评审/未批准 |
| 已评审 | 已通过 grilling 审查，待批准开工 |
| 已废弃 / 被取代 | 不再生效，保留作历史记录，正文头部有取代说明 |

## 完整索引（按编号排序）

| ADR | 决策标题 | 状态 | 优先级 | 状态核验 | 文件 |
|-----|---------|------|:--:|:--:|------|
| ADR-001 | Agent 基础设施（OpenHarness + LangGraph） | 已接受 | P0 | 2026-08-16 | [ADR-001](ADR-001_agent_基础设施openharness_langgraph.md) |
| ADR-002 | Graphiti 作为双时态知识图谱 | 已接受 | P0 | 2026-08-16 | [ADR-002](ADR-002_graphiti_作为双时态知识图谱.md) |
| ADR-003 | OPA 策略治理引擎（MVP + 生产化） | 已接受 | P0 | 2026-08-16 | [ADR-003](ADR-003_opa_策略治理引擎mvp_生产化.md) |
| ADR-004 | 统一 Skill 体系架构 | 已接受 | P0 | 2026-08-16 | [ADR-004](ADR-004_统一_skill_体系架构.md) |
| ADR-005 | 分层 Agent 架构（OpenHarness 原生 + 领域扩展） | 已接受 | P0 | 2026-08-16 | [ADR-005](ADR-005_分层_agent_架构openharness_原生_领域扩展.md) |
| ADR-006 | OpenHarness 复用策略（完全复用 + 适配复用 + 独立扩展） | 已接受 | P0 | 2026-08-16 | [ADR-006](ADR-006_openharness_复用策略完全复用_适配复用_独立扩展.md) |
| ADR-007 | 前端采用 React + Ant Design 技术栈 | 已接受 | P0 | 2026-08-16 | [ADR-007](ADR-007_前端采用_react_ant_design_技术栈.md) |
| ADR-008 | 审计日志完整记录 | 已接受 | P0 | 2026-08-16 | [ADR-008](ADR-008_审计日志完整记录.md) |
| ADR-009 | Markdown 编写 OPA 策略 | 已接受 | P0 | 2026-08-16 | [ADR-009](ADR-009_markdown_编写_opa_策略.md) |
| ADR-010 | 多模态文档处理可配置 | 已接受 | P1 | 2026-08-16 | [ADR-010](ADR-010_多模态文档处理可配置.md) |
| ADR-011 | 角色配置热生效 | 已接受 | P0 | 2026-08-16 | [ADR-011](ADR-011_角色配置热生效.md) |
| ADR-012 | 配置组合引擎 | 已接受 | P1 | 2026-08-16 | [ADR-012](ADR-012_配置组合引擎.md) |
| ADR-013 | 多数据源统一接入 | 已接受 | P1 | 2026-08-16 | [ADR-013](ADR-013_多数据源统一接入.md) |
| ADR-014 | 技能热插拔架构 | 已接受 | P0 | 2026-08-16 | [ADR-014](ADR-014_技能热插拔架构.md) |
| ADR-015 | 可扩展图表系统 | 已接受 | P1 | 2026-08-16 | [ADR-015](ADR-015_可扩展图表系统.md) |
| ADR-016 | 完备文档体系 | 已接受 | P1 | 2026-08-16 | [ADR-016](ADR-016_完备文档体系.md) |
| ADR-017 | 原子提交规范 | 已接受 | P0 | 2026-08-16 | [ADR-017](ADR-017_原子提交规范.md) |
| ADR-018 | 模拟领域数据生成引擎 | 已接受 | P1 | 2026-08-16 | [ADR-018](ADR-018_domain_simulator_engine.md) |
| ADR-019 | 多模态文档处理流水线 | 已接受 | P1 | 2026-08-16 | [ADR-019](ADR-019_多模态文档处理流水线.md) |
| ADR-020 | 管理员控制台统一界面 | 已接受 | P0 | 2026-08-16 | [ADR-020](ADR-020_管理员控制台统一界面.md) |
| ADR-021 | QA 驱动本体搭建架构 | 已接受 | — | 2026-08-16 | [ADR-021](ADR-021_qa_driven_ontology_building.md) |
| ADR-022 | 模拟数仓与统一查询服务 | 已接受（+与 ADR-055 边界注记） | P1 | 2026-08-16 | [ADR-022](ADR-022_模拟数仓与统一查询服务.md) |
| ADR-023 | 多工作空间隔离架构 | 已接受 | P0 | 2026-08-16 | [ADR-023](ADR-023_多工作空间隔离架构.md) |
| ADR-024 | 本体驱动分析核心架构 | 已接受 | P0 | 2026-08-16 | [ADR-024](ADR-024_本体驱动分析核心架构.md) |
| ADR-025 | 基于 OpenHarness 实现多智能体协同 | 已接受 | P0 | 2026-08-16 | [ADR-025](ADR-025_openharness_integration.md) |
| ADR-026 | 采用 MCP 协议作为外部系统集成标准 | 已接受 | P1 | 2026-08-16 | [ADR-026](ADR-026_mcp_protocol_integration.md) |
| ADR-027 | Hook 系统作为可扩展性核心架构 | 已接受 | P1 | 2026-08-16 | [ADR-027](ADR-027_hook_system_architecture.md) |
| ADR-028 | OPA 作为统一权限校验引擎 | 已接受 | P0 | 2026-08-16 | [ADR-028](ADR-028_permission_checker_opa_integration.md) |
| ADR-029 | 统一工具注册表架构管理 AI Agent 工具 | 已接受 | P1 | 2026-08-16 | [ADR-029](ADR-029_tool_registry_architecture.md) |
| ADR-030 | Phase 1 推迟引入 OpenHarness，保留现有编排器 | 已接受 | P1 | 2026-08-16 | [ADR-030](ADR-030_phase1_推迟引入openharness_保留现有编排器.md) |
| ADR-031 | 模拟器 Web 可视化与实时本体热写入架构 | 已接受 | P0 | 2026-08-16 | [ADR-031](ADR-031_simulator_web_visualization_realtime_ontology.md) |
| ADR-032 | 标准化本体文档格式（OntologyDocument） | 已接受 | P0 | 2026-08-16 | [ADR-032](ADR-032_standard_ontology_document_format.md) |
| ADR-033 | 项目目录结构重构（分层模块化 odap/ 包） | **被 ADR-066 取代** | P0 | 2026-08-16 | [ADR-033](ADR-033_项目目录结构重构.md) |
| ADR-036 | 领域实体标准本体库（Palantir 参考） | 已接受 | P1 | 2026-08-16 | [ADR-036](ADR-036_palantir_ontology_reference.md) |
| ADR-037 | 前端采用移动优先 + 国际化架构 | 已接受 | P0 | 2026-08-16 | [ADR-037](ADR-037_frontend_mobile_first_i18n.md) |
| ADR-038 | 本体管理引擎与用户认知引擎架构 | 已废弃（被 ADR-068 取代） | P0 | 2026-08-16 | [ADR-038](ADR-038_本体管理引擎与用户认知引擎架构.md) |
| ADR-039 | 问答引擎架构 | 已接受 | P0 | 2026-08-16 | [ADR-039](ADR-039_qa_engine_architecture.md) |
| ADR-040 | API 网关统一入口 | 已接受 | P0 | 2026-08-16 | [ADR-040](ADR-040_api_gateway_unified_entry.md) |
| ADR-041 | 工作空间资源隔离架构 | 已接受 | P0 | 2026-08-16 | [ADR-041](ADR-041_workspace_resource_isolation.md) |
| ADR-042 | 审计日志存储查询架构 | 已接受 | P0 | 2026-08-16 | [ADR-042](ADR-042_audit_log_storage_query.md) |
| ADR-043 | Agent Router 语义路由架构 | 已接受 | P0 | 2026-08-16 | [ADR-043](ADR-043_agent_router_semantic_routing.md) |
| ADR-044 | 测试策略与框架 | 已接受 | P1 | 2026-08-16 | [ADR-044](ADR-044_test_strategy_framework.md) |
| ADR-045 | 前端可视化选型 — G6 + Leaflet | 已接受 | P0 | 2026-08-16 | [ADR-045](ADR-045_frontend_visualization_g6_leaflet.md) |
| ADR-046 | Phase 4 采用模块化单体部署架构 | 已接受 | P0 | 2026-08-16 | [ADR-046](ADR-046_modular_monolith_deployment.md) |
| ADR-047 | 工具注册表升级 P0 + 分步实现 | 已接受 | P0 | 2026-08-16 | [ADR-047](ADR-047_tool_registry_p0_phased_implementation.md) |
| ADR-048 | 本体管理引擎架构决策 | 已废弃（被 ADR-068 取代） | P0 | 2026-08-16 | [ADR-048](ADR-048_本体管理引擎架构决策.md) |
| ADR-049 | 用户认知引擎架构决策 | 已废弃（被 ADR-068 取代） | P0 | 2026-08-16 | [ADR-049](ADR-049_用户认知引擎架构决策.md) |
| ADR-050 | OADP 业务语义体系架构 | 已接受 | P0 | 2026-08-16 | [ADR-050](ADR-050_OADP业务语义体系架构.md) |
| ADR-051 | 闭环反馈机制设计 | 已接受 | P0 | 2026-08-16 | [ADR-051](ADR-051_闭环反馈机制设计.md) |
| ADR-052 | 智能问答 WebUI 开源项目选型（自研三栏布局） | 已接受（已执行） | P0 | 2026-08-16 | [ADR-052](ADR-052_webui_opensource_selection.md) |
| ADR-053 | Skill 可视化管理开源方案选型（React Flow 嵌入） | 已接受（已执行） | P0 | 2026-08-16 | [ADR-053](ADR-053_skill_management_selection.md) |
| ADR-054 | 规格与架构文档瘦身 | 已接受 | P2 | 2026-08-16 | [ADR-054](ADR-054_规格与架构文档瘦身.md) |
| ADR-055 | 统一查询服务（QueryService） | 已接受 | P0 | 2026-08-16 | [ADR-055](ADR-055-统一查询服务.md) |
| ADR-056 | 语义层修正（类型校验执行与模型统一） | **被 ADR-061+068 取代** | P0 | 2026-08-16 | [ADR-056](ADR-056-语义层修正.md) |
| ADR-057 | 领域本体语义层（四大名著中英文映射） | **被 ADR-061+068 取代** | P1 | 2026-08-16 | [ADR-057](ADR-057-domain-ontology-semantic-layer.md) |
| ADR-058 | RBAC 三级菜单管理架构 | 已接受 | P0 | 2026-08-16 | [ADR-058](ADR-058-rbac-menu-management.md) |
| ADR-059 | Dev/Prod 开发生产环境隔离架构 | 已接受 | P0 | 2026-08-16 | [ADR-059](ADR-059-dev-prod-environment-isolation.md) |
| ADR-060 | 知识库文档存储与图谱构建架构 | 已接受 | P0 | 2026-08-16 | [ADR-060](ADR-060-knowledge-base-document-storage.md) |
| ADR-061 | Semantic Admin Suite 独立业务域架构 | 已接受 | P0 | 2026-08-16 | [ADR-061](ADR-061-semantic-admin-suite-architecture.md) |
| ADR-061b | Skill 插件包分发与沙箱执行机制 | 已接受（backlog，未启动） | P2 | 2026-08-16 | [ADR-061b](ADR-061_skill_plugin_packaging.md) |
| ADR-062 | Graph CQRS 分层读写分离（Graphiti → Redis） | 已接受（未启动，现状为进程内 LRU 缓存） | P2 | 2026-08-16 | [ADR-062](ADR-062_graph_cqrs_tiering.md) |
| ADR-063 | 租户/工作空间双级感知与资源隔离 | 已接受（**部分落地**：tenant 零实现；workspace 强化由 ADR-076 §7 承接） | P1 | 2026-08-16 | [ADR-063](ADR-063_tenant_aware_isolation.md) |
| ADR-064 | 可观测性基线（Trace/Metrics/Log 三面） | 已接受（已落地；2026-08-16 修订增补 doctor 自检与流水线可观测） | P1 | 2026-08-16 | [ADR-064](ADR-064_observability_baseline.md) |
| ADR-065 | 模块化单体 → 微服务拆分剧本 | 已接受（预案性质） | P3 | 2026-08-16 | [ADR-065](ADR-065_microservice_extraction_playbook.md) |
| ADR-066 | Monorepo 重构（uv workspace + pnpm workspace） | 已接受 | P1 | 2026-08-16 | [ADR-066](ADR-066-monorepo-restructure.md) |
| ADR-067 | `biz/shared` 下沉到 `infra/storage/` | 已接受（已执行，`biz/shared/` 仅剩 Deprecated 重定向） | P2 | 2026-08-16 | [ADR-067](ADR-067_biz_shared_relocation.md) |
| ADR-068 | 本体模块 3+1 分层架构（Design→Construction→+Reasoning→Application） | 已接受 | P0 | 2026-08-16 | [ADR-068](ADR-068_本体模块四层分层架构.md) |
| ADR-069 | 统一 AI 助手与智能问答服务 | 已接受（Phase A 已上线；Phase B 前端统一未完成） | P0 | 2026-08-16 | [ADR-069](ADR-069_统一AI助手与智能问答服务.md) |
| ADR-070 | 基于 OpenHarness 全能力的 AI 助手架构 | 已接受（Phase A 已上线；已修正"取代 ADR-050"引用错误） | P0 | 2026-08-16 | [ADR-070](ADR-070_基于OpenHarness全能力的AI助手架构.md) |
| ADR-071 | BuildResultContract — L2 Construction 构建产物契约 | 已接受（契约代码已落地） | P1 | 2026-08-16 | [ADR-071](ADR-071_BuildResultContract_构建产物契约.md) |
| ADR-072 | ReasoningServiceContract — +AI Reasoning 推理服务契约 | 已接受（契约代码已落地；引擎实现由 ADR-075 承接） | P1 | 2026-08-16 | [ADR-072](ADR-072_ReasoningServiceContract_推理服务契约.md) |
| ADR-073 | 基于本体的数据服务四步落地架构（语义检索服务总线） | 已接受 | P0 | 2026-08-16 | [ADR-073](ADR-073_基于本体的数据服务四步落地架构.md) |
| ADR-074 | 情报驱动架构——HE 与 Graphiti 正确定位及分层审计 | 已接受 | P0 | 2026-08-16 | [ADR-074](ADR-074_情报驱动架构_HE与Graphiti正确定位及分层审计.md) |
| ADR-075 | 确定性推理引擎引入（Datalog/前向链接 + Allen 时态代数） | 已接受（2026-08-16 grilling 收尾；引擎已落地 pyDatalog 0.17.4） | P1 | 2026-08-20 | [ADR-075](ADR-075_确定性推理引擎引入.md) |
| ADR-076 | 决策智能架构——决策作为一等公民对象（7 端点全 API 面） | 已接受（Phase 1 已交付） | P0 | 2026-08-20 | [ADR-076](ADR-076_决策智能架构_决策作为一等公民对象.md) |
| ADR-077 | SHACL/OWL 本体治理（双轨制） | 已接受（2026-08-20 grilling 四轮裁决；SHACL/OWL 引擎已落地） | P2 | 2026-08-20 | [ADR-077](ADR-077_SHACL_OWL本体治理.md) |
| ADR-078 | 图分析服务（中心性/社区/链路预测/路径） | 提议（2026-08-20 编写，待评审；引擎已落地） | P2 | 2026-08-20 | [ADR-078](ADR-078_图分析服务.md) |
| ADR-079 | 本体论与 LLM 结合边界（推理/理解/生成三层治理） | 已接受（2026-08-20） | P0 | 2026-08-20 | [ADR-079](ADR-079_本体论与LLM结合边界.md) |

> 预留编号：ADR-034/035（对应设计已合并至 ADR-038，永不复用）。

---

## ADR 模板

新建 ADR 时请使用以下模板：

```markdown
# ADR-XXX: [决策标题]

## 状态
提议 | 已接受 | 已弃用 | 被 ADR-XXX 取代

## 上下文
我们看到的促使此决策的问题是什么？

## 决策
我们提议和/或正在进行的更改是什么？

## 后果
因为此更改，什么变得更容易或更难？

## 可逆性
高 | 中 | 低。说明如何逆转此决策。
```

## 编号规则

- ADR-001 ~ ADR-024：从 `ARCHITECTURE.md` 第 17 章提取的核心架构决策
- ADR-025 ~ ADR-029：从独立 ADR 文件迁移的详细决策（原编号 ADR-006~010）
- ADR-030：Phase 1+ 演进决策（OpenHarness 推迟）
- ADR-031 ~ ADR-032：Phase 3 模拟器增强（Web 可视化 + 标准本体格式）
- ADR-033：Phase 3+ 项目目录结构重构 — **2026-08-16 起被 ADR-066 取代**
- ADR-034 ~ ADR-038：Phase 4 文档体系。注：ADR-034/035 为预留编号，对应设计已合并至 ADR-038
- ADR-039 ~ ADR-047：Phase 4 问答/网关/工作空间/审计/路由/测试/可视化/部署/工具注册表
- ADR-048 ~ ADR-049：Phase 4 引擎架构决策 — **2026-07-18 已废弃，被 ADR-068 取代**
- ADR-050 ~ ADR-051：Phase 4-5 语义体系 + 闭环反馈
- ADR-052 ~ ADR-053：Phase 5 WebUI 与 Skill 选型 — **2026-08-16 清算为已接受（均已执行）**
- ADR-054：Phase 4 规格与架构文档瘦身（原编号 ADR-049b，2026-07-18 重编号解决冲突）
- ADR-055 ~ ADR-057：Phase 5 统一查询与语义层 — **056/057 于 2026-08-16 清算为被 ADR-061+068 取代**
- ADR-058 ~ ADR-061：Phase 5 RBAC/环境隔离/知识库存储/Semantic Admin Suite
- ADR-061b：Phase 5 Skill 插件包分发与沙箱执行（与 ADR-061 同日提审，共享编号后缀 `b`）
- ADR-062 ~ ADR-065：Phase 6 CQRS/租户隔离/可观测性/微服务剧本 — **清算后均为已接受，落地情况见索引注记**
- ADR-066：Phase 6 Monorepo 重构（继承 ADR-033 分层语义）
- ADR-067 ~ ADR-072：Phase 6 存储下沉/本体 3+1 分层/AI 助手/契约层 — **2026-08-16 清算为已接受**
- ADR-073 ~ ADR-074：Phase 6 数据服务四步落地/情报驱动架构
- ADR-075 ~ ADR-076：Phase 7 Semantica 能力引入（推理引擎/决策智能，2026-08-16 修订）
- ADR-077 ~ ADR-078：Phase 3/4 本体治理标准化（SHACL/OWL）+ 图分析服务（2026-08-20）
- ADR-079：本体论与 LLM 结合边界（推理/理解/生成三层治理，2026-08-20）
- 编号冲突处理：若同日提审新 ADR 时编号已被占用，**禁止采用后缀 `b/c/d`**，必须使用下一个可用编号。**永远不重命名已被外部链接引用的 ADR 文件**。

## 状态清算记录

| 日期 | 动作 | 范围 |
|------|------|------|
| 2026-08-16 | 全面清算：索引与文件头状态对齐；4 份提议转已接受（052/053/067 + 069/070/071/072）；2 份标记取代（056/057 → 061+068）；033 → 被 066 取代；022 补边界注记；063/062/069 补落地情况注记；070 修正引用错误；索引重构为单一权威表并新增"状态核验"列 | 全量 76 份 |
| 2026-08-20 | 登记 ADR-077/078/079；075/076 状态同步为已接受（此前 grilling 收尾/Phase 1 交付未回写索引）；新增 ADR-079 本体论与 LLM 结合边界原则 | 075~079 |
