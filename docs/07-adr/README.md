---
id: odap.l7.readme
status: active
owner: architect
version: ''
layer: L7
concern: adr
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
---

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
| ADR-080 | core.ontology 门面封装与 import-linter 分层契约棘轮 | 已接受（2026-09-06 Stage A–G：C1/C2/C3 零债账全严格；2026-09-07 Stage H：补 C4 守卫 infra 下层，续烧 22→19→18→14；2026-09-08 Stage I：依赖倒置续烧 14→10，见 ADR-081；2026-09-11 Stage J：`lint-imports` 接成 ci.yml/quality-gate.yml 阻塞门禁，此前只有手工命令） | P1 | 2026-09-06 | [ADR-080](ADR-080_ontology门面封装与分层契约.md) |
| ADR-081 | infra→biz 依赖倒置 provider 注册表 seam（C4 Stage I 烧账机制） | 已接受（2026-09-08 Stage I · Group A：新增 infra/providers.py 注册表 + biz/providers_bootstrap.py 工厂注册，3 个 query source 改 resolve_provider + 删死函数 register_query_tools，C4 14→10，`lint-imports` 4 kept/0 broken，OpenAPI 755/957 零丢路由） | P1 | 2026-09-08 | [ADR-081](ADR-081_infra依赖倒置provider注册表.md) |
| ADR-082 | 事件源与 BI 指标的语义候选抽取入口（资产流水线扩展） | 已接受（2026-09-25 设计获批；事件源捕获 PerceptionHub 既有 ExtractionResult 不重复抽取，BI 指标→属性确定性读取，均落 semantic-assets 流水线共用候选库；实现待 writing-plans 拆片） | P0 | 2026-09-25 | [ADR-082](ADR-082_事件源与BI指标语义抽取入口.md) |
| ADR-083 | 图谱实体软删除语义（invalid_at 失效 + 级联边失效 + 读侧过滤） | 已接受（2026-09-29 实现已落地：GraphManager.delete_entity 软删 + 级联失效关系边，~15 处读路径默认排除失效实体（get_entity include_deleted opt-in），state_at = valid_time <= vt < invalid_at，共享谓词真源 _soft_delete.py，GraphWriteProxy 为唯一合规删除通道经 graph_audit 审计，executor/execution_tool 删除路径接通；批次删除回滚链归 #13b） | P1 | 2026-09-29 | [ADR-083](ADR-083_图谱实体软删除语义.md) |
| ADR-084 | open/typed 双层事实模型与写路径不变量（借鉴 utopia） | 提议（2026-10-04 提交，设计已获用户认可，实现按 P0→P1 分片推进中：S1 F2 度量诚实化 + S2 F1 open 层暂存消除 zh_type + S3 F3 写前 USL 归一本轮落地；S4 F7 SHACL 挂写路径 + S5 competency questions 留后续 ADR） | P0 | 2026-10-04 | [ADR-084](ADR-084_open_typed双层事实模型与写路径不变量.md) |
| ADR-085 | SHACL 形状持久化与写路径校验不变量（关 F7 / ADR-084 切片 S4） | 提议（2026-10-04 提交，承接 ADR-084 D4 登记方向：形状落版本键控派生缓存（操作化 ADR-077 裁决1）+ 单一 WritePathValidator 车道级调用（不改 GraphWriteProxy 契约）+ observe-first 灰度违规进 sa_axiom_violation 队列 + G2.2/G2.3 真值替换占位。分片 S4a/S4c 低风险待批即落，S4b 中风险，S4d enforce+修订 ADR-077 须单独评审） | P1 | 2026-10-04 | [ADR-085](ADR-085_SHACL形状持久化与写路径校验不变量.md) |
| ADR-086 | 概念缺口回路（四信号源汇聚 heat 缺口池 + 人工裁决晋升复用审批飞轮 + side-channel 回调闭环） | 已接受（2026-10-07 设计获批；T1–T8 已以 TDD 实现，6 个 gap 单测 + 菜单 seed/迁移单测全绿；代码 staged 待用户提交，dev 容器手验与整分支终审待办） | P1 | 2026-10-07 | [ADR-086](ADR-086_概念缺口回路.md) |
| ADR-087 | 语义漂移检测（预留编号，spec/plans 已定稿待复审后落 ADR） | 提议（[spec](../superpowers/specs/2026-10-07-semantic-drift-detection-design.md)；"报告即不可变证据"纪律已被 ADR-088 借用） | P1 | 2026-10-08 | — |
| ADR-088 | EvoOntology 借鉴采纳：归因分层与配对回放门控 | 已接受（2026-10-09 设计获批；子项目 A 归因分层 + 子项目 B 缺口回归集/配对回放以 TDD 实现中；核心决策：门控归人不归模型、信号收集器模式（线程安全权衡如实登记）、模型指纹 + cost 记录补 EvoOntology 自认之缺；auto-accept 明确不采纳） | P1 | 2026-10-09 | [ADR-088](ADR-088_EvoOntology借鉴采纳_归因分层与配对回放门控.md) |
| ADR-089 | 子项目 C：`ontology_semantics` MCP 工具按需查询替代全量注入 | 已接受并实施（2026-10-09；三模式 off/inject/query 默认 query + 前端切换卡 + `sa_config` 三级解析 + cost 对账；实测新增 44 个 C 相关单测全绿；落稿时同步修复 EntityExtractor 构造默认值对 ADR-079 上下文驱动行为的覆盖回归） | P1 | 2026-10-09 | [ADR-089](ADR-089_子项目C_ontology_semantics%20MCP工具_按需查询替代全量注入.md) |
| ADR-090 | 子项目 D：`promote` 按 attribution.layer 路由（类型化编辑 + 完整路由工单工作流） | 已接受并实施（2026-10-09；`schema>tool>content` 风险倒序 + 三路薄壳调度 + `schema` 走 ChangeProposal（draft 门控）+ `tool` 走完整工单工作流（6 态状态机/P0~P3 SLA/事件审计/前端界面）+ `route-preview` 无副作用端点；gap 存储幂等加 `promoted_proposal_id`/`promoted_ticket_id`；C3 门面新增 `create_schema_proposal`/`get_goal_storage`） | P1 | 2026-10-09 | [ADR-090](ADR-090_子项目D_promote按attribution_layer路由_类型化编辑.md) |
| ADR-091 | 语义发布生命周期与本体单一写入通道 | **提议**（2026-10-28 提交，设计待复审；USL 草案/变更集/审核/发布版本四态 + 发布快照不可变与消费方版本固定 + `OntologyWriteGateway` 单一写入通道 + AI 只提案 + 一个工作台四区三视图；含 C5 import-linter 契约与 `USL_CONSUMPTION_MODE` 迁移开关） | P0 | 2026-10-28 | [ADR-091](ADR-091_语义发布生命周期与本体单一写入通道.md) |
| ADR-092 | 图标库锁定为 lucide-react（统一描边 SVG） | 已接受（2026-10-17；`@ant-design/icons` 为填充式 SVG 且无 stroke-width/linecap 控制，无法满足 1.5px 统一描边，改锁 lucide-react；描边单点收敛在 `Icon.tsx`，16px 复杂度门禁进 CI） | P0 | 2026-10-17 | [ADR-092](ADR-092_icon-library-lock.md) |
| ADR-093 | Design Token 分层与多主题切换机制 | 已接受（2026-10-17；三层 primitive→semantic→component；`data-appearance`(luminous/nebula) × `data-accent`(cobalt/teal/indigo/graphite) × `data-density` 正交切换） | P0 | 2026-10-17 | [ADR-093](ADR-093_design-token-theming.md) |
| ADR-094 | 本体约束编排层（六步管线）选型 | 已接受（2026-10-17；`IntentRouter → OntologyAligner → RuleGuard → RetrievalExecutor → AnswerComposer → OutputContractGate`，每步输入/输出契约与降级路径明确，OPA fail-closed） | P0 | 2026-10-17 | [ADR-094](ADR-094_ontology-constraint-orchestration.md) |
| ADR-095 | 意图识别分层方案与泛化度量 | 已接受（2026-10-17；L1 词典/别名 → L2 语义路由 → L3 受限 LLM 消歧 → L4 本体槽位填充四级漏斗；度量口径 Intent-Acc@1 / Slot-F1 / Gen-Gap / Clarify-Rate） | P0 | 2026-10-17 | [ADR-095](ADR-095_intent-recognition-generalization.md) |
| ADR-096 | LLM Wiki 存储与双向同步方案 | 已接受（2026-10-17；统一 front-matter 纳管模型 + 状态机 `draft→review→published→superseded|archived` + `content_hash` 冲突检测） | P1 | 2026-10-17 | [ADR-096](ADR-096_llm-wiki-storage-sync.md) |
| ADR-097 | 文档治理与溯源机制（真相源 + 可机械校验） | 已接受（2026-10-17；front-matter 为元数据唯一真相源；`DOCUMENT_MANAGEMENT.md` 升 v3、`DOC-GOVERNANCE-POLICY.yaml` 定规则、`scripts/doc_governance.py` 校验 R1~R14；第 1 条「其余 10 篇 ARCHITECTURE_* 全标 superseded」经复核收窄为「仅 `ARCHITECTURE.md`」，分层详设 5 篇保留 active） | P0 | 2026-10-17 | [ADR-097](ADR-097_docs-governance-provenance.md) |
| ADR-098 | frontend_compat 兼容层收敛与下线 | 已接受（2026-10-17；兼容层保留但只做形状适配，不承载业务逻辑；新功能一律走 `/api/v1` 原生契约） | P1 | 2026-10-17 | [ADR-098](ADR-098_frontend-compat-convergence.md) |
| ADR-099 | 前端 Agent 集成协议收敛为 AG-UI（放弃 AI SDK Data Stream 路线） | 已接受（2026-10-22；前端唯一协议为 AG-UI，移除 `@openharness/react` + `ai` 两个零引用且协议不兼容的依赖；取代 ADR-039 中的 Provider 集成片段） | P1 | 2026-10-22 | [ADR-099](ADR-099_frontend-agent-protocol-agui.md) |
| ADR-100 | 图谱与图表渲染栈收敛（拓扑浏览唯一化） | 已接受（2026-10-17；7 套渲染栈收敛为 3：sigma+@react-sigma/core+graphology 做拓扑浏览、@xyflow/react 做编辑、echarts 做统计；cytoscape 例外不再保留；原拟用 ADR-091，与「语义发布生命周期」撞号后改为 ADR-100） | P0 | 2026-10-17 | [ADR-100](ADR-100_graph-render-stack-consolidation.md) |

> **编号基线核对表（ADR-097 第 6 条）**
>
> - 已用：ADR-001 ~ ADR-033、ADR-036 ~ ADR-086、ADR-088 ~ ADR-100（共 97 个编号，99 个文件）
> - 预留永不复用：ADR-034、ADR-035（设计已合并至 ADR-038）
> - 待启用：ADR-087（语义漂移检测 spec 已定稿，ADR 落稿时启用）
> - **重号债务**：ADR-061 一号两文（`ADR-061-semantic-admin-suite-architecture.md` / `ADR-061_skill_plugin_packaging.md`），重编须先核清引用方；跨目录撞号 `docs/02-architecture/reports/ADR-065_BULKHEAD_AUDIT.md` 与 `ADR-065_microservice_extraction_playbook.md`；**ADR-091 一号两文待收口**（`ADR-091_语义发布生命周期与本体单一写入通道.md` 已在用，决策主线代码注释引用的「ADR-091 §5.x」属另一篇，需单独立项重编）
> - 机械校验：`python scripts/doc_governance.py audit` 的 R8（层编号唯一）与 R12（ADR 状态可解析）

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
- ADR-080：core.ontology 门面封装与 import-linter 分层契约棘轮（ADR-068 迁移策略的实现与 CI 守卫，2026-09-06）
- ADR-081：infra→biz 依赖倒置 provider 注册表 seam（C4 棘轮 Stage I 烧账机制，续接 ADR-080，2026-09-08）
- ADR-082：事件源与 BI 指标的语义候选抽取入口（资产流水线扩展，补齐「散落结构化数据自动抽取业务语义」的两类入口，2026-09-25）
- ADR-083：图谱实体软删除语义（invalid_at 失效 + 级联边失效 + 读侧默认过滤 + 时态 as-of 上界，打通行动闭环删除路径，2026-09-29）
- ADR-084：open/typed 双层事实模型与写路径不变量（借鉴 utopia：消除摄入车道 zh_type 桶、未治理类型转候选、质量闸占位子项标 not_evaluated 剔出均分、写前 USL 归一，联动 F1/F2/F3/F7，2026-10-04）
- ADR-085：SHACL 形状持久化与写路径校验不变量（关 F7 / ADR-084 切片 S4：形状落版本键控派生缓存、单一 WritePathValidator 车道级校验不改 proxy 契约、observe-first 违规进 sa_axiom_violation 队列、G2.2/G2.3 真值替换占位，2026-10-04）
- ADR-086：概念缺口回路（四类运行时未答信号 term_resolve_miss/mapping_failure/qa_unanswered/nl_query_unanswered 经同步 emitter 汇聚成带 heat 的 `concept_gaps` 缺口池，人工裁决 promote/dismiss，晋升复用 candidate 审批飞轮，writeback side-channel 回调闭环，借鉴 BeModel 模式不借栈，2026-10-07）
- ADR-087（预留）：语义漂移检测（spec/plans 2026-10-07 定稿，ADR 待其复审通过后落稿）
- ADR-088：EvoOntology 借鉴采纳——归因分层与配对回放门控（gap 加 attribution 双层结构（schema/content/tool 三层枚举，最佳努力不造数）+ 缺口回归集固化不可变 + 配对回放 answered 差分判定（verdict=pass ⇔ 回归 0 且修复≥1）+ 模型指纹与 cost 记录；借鉴 EvoOntology 归因引导编辑与 backbone-conditional 配对评估两机制，auto-accept 明确不采纳——门控归人不归模型，2026-10-09）
- ADR-091：语义发布生命周期与本体单一写入通道（USL 草案/变更集/审核/发布四态 + 不可变发布快照与消费方版本固定 + `OntologyWriteGateway` 唯一写入通道 + AI 只提案 + 一个工作台四区三视图；含 C5 import-linter 契约、`USL_CONSUMPTION_MODE` 迁移开关与现有域 bootstrap v1，2026-10-28）
- 编号冲突处理：若同日提审新 ADR 时编号已被占用，**禁止采用后缀 `b/c/d`**，必须使用下一个可用编号。**永远不重命名已被外部链接引用的 ADR 文件**。

## 状态清算记录

| 日期 | 动作 | 范围 |
|------|------|------|
| 2026-08-16 | 全面清算：索引与文件头状态对齐；4 份提议转已接受（052/053/067 + 069/070/071/072）；2 份标记取代（056/057 → 061+068）；033 → 被 066 取代；022 补边界注记；063/062/069 补落地情况注记；070 修正引用错误；索引重构为单一权威表并新增"状态核验"列 | 全量 76 份 |
| 2026-08-20 | 登记 ADR-077/078/079；075/076 状态同步为已接受（此前 grilling 收尾/Phase 1 交付未回写索引）；新增 ADR-079 本体论与 LLM 结合边界原则 | 075~079 |
| 2026-09-06 | 登记 ADR-080（core.ontology 门面封装 + import-linter 三契约棘轮，Stage A–G 落地，C1/C2/C3 零债账全严格） | 080 |
| 2026-09-07 | ADR-080 Stage H：补第四条契约 C4（infra 不得直接 import biz），grimp 精确复测 22 边；分三批烧账 —— Tier1 删 2 vestigial shim（22→19）、Tier3 PermissionScope 下沉 common（19→18）、Tier2 object_service 整体迁移 biz.data（18→14）；`lint-imports` 3 kept → 4 kept/0 broken；同步 DOC_SYNC_CHECKLIST 契约审计 gate、ARCHITECTURE_INFRA、03-modules README | 080 |
| 2026-09-08 | 登记 ADR-081（infra→biz 依赖倒置 provider 注册表 seam）；ADR-080 Stage I · Group A 烧账：新增 `infra/providers.py` 注册表 + `biz/providers_bootstrap.py` 工厂注册，3 个 query source 改 `resolve_provider` + 删死函数 `register_query_tools`，C4 14→10；反向探针验证注册表受 C4 守卫；运行期 smoke 5 provider 全解析；定向回归 139 passed；容器 OpenAPI 755/957 零丢路由；顺带修正 `SemanticObjectRetriever` 存量导入缺陷 | 080/081 |
| 2026-09-11 | ADR-080 Stage J：`lint-imports` 接成 CI 阻塞门禁（`ci.yml` step + `quality-gate.yml` 独立 job 进 `needs`），补上 Stage A–I 期间「宣称有 CI 守卫、实际只有手工命令」的缺口。首版接线（`working-directory: apps/api` + `uv run --frozen lint-imports`）经干净环境实测是坏的——`import-linter`/`grimp` 在仓库根 `[dependency-groups] dev`，`uv sync --no-dev --package odap` 不装它，且从 `apps/api` 执行 `uv run` 解析到 odap 项目、闭包同样不含，门禁恒以 `Failed to spawn: lint-imports` 退出；已改为「根 `uv sync --frozen --inexact` + `cd apps/api && uv run --frozen --no-sync lint-imports`」并在空环境逐步验证退出码全 0。复测 `4 kept/0 broken`，1360 files/2380 deps，C4 棘轮仍 10 条。同轮架构缺口审计发现并修复一批「幻影调用 + 静默兜底」断链（perception hub 抽取链路恒返回空、QA 单例把 Neo4j 瞬时故障固化为进程级永久降级、executor 丢弃 GraphWriteProxy 错误状态恒报 success、rollback_manager `hasattr` 探测式假成功、graph_retriever/execution_tool 调不存在的 API、6 个 `biz/**/__init__.py` 裸 `except: pass` 再导出含 1 个幻影模块）；据此扩充 AGENTS.md 规则 14（新增 `hasattr` 探测式降级 / 幻影调用 / 无视被调方错误状态三种禁止形态，降级实例禁入长生命周期缓存，测试必须执行真实函数体） | 080 |
| 2026-09-25 | 登记 ADR-082（事件源与 BI 指标的语义候选抽取入口）：审计确认语义构建编排器真实，但两类散落结构化数据抽不到——事件源经 PerceptionHub 真实 LLM 抽取后门面只留 extraction_confidence、丢弃整个 ExtractionResult 致候选恒 0；BI 指标（business.db）零入口进 semantic_admin。决策：宿主为 semantic-assets 资产流水线（非 text-only 的 ol_pipeline）；事件源改门面返回体透传 ExtractionResult + 新 `_collect_event_candidates`（不重复抽取、不落 OntologyDocument）；BI 指标新增 source_type `business_indicators` → `_run_indicator` 经 `BusinessService.list_indicators` 确定性读取 → 映射为 USL「属性」候选；两路复用断链 2 的 `_resolve_domain_code` 领域归属与共用候选库。sensor 因门面只入队无 event_id 暂缓（保持显式 error）；warehouse schema/本体类型定义暂缓。设计已获用户批准，实现待 writing-plans 拆片 | 082 |
| 2026-09-29 | 登记 ADR-083（图谱实体软删除语义）：删除语义决策为软删默认——节点/关系边打 `invalid_at`（ISO-8601 UTC 字符串）标记失效时刻，`GraphManager.delete_entity` 级联失效关系边（in_edges+out_edges 并集，幂等），~15 处读路径（Neo4j ~10 + fallback 5）默认排除失效实体（`get_entity(include_deleted=)` opt-in），时态 `state_at(vt)` = `valid_time <= vt < invalid_at`，共享谓词真源 `_soft_delete.py`，`GraphWriteProxy` 为唯一合规删除通道（结构化审计经 GraphManager 层 `graph_audit`）；executor delete 分支与 execution_tool `delete_entity` 动作由恒失败/unsupported 转为真实软删透传；Graphiti 向量检索（EntityEdge fact 层）不联动软删为已知边界；批次删除回滚链归 #13b。实现已落地（#13a Task 1-8），`lint-imports` 4 kept/0 broken | 083 |
| 2026-10-04 | 登记 ADR-084（open/typed 双层事实模型与写路径不变量，借鉴 deeplethe/utopia commit 8de3988）：源自 2026-10-03 对照 Talisman《The Ontology Pipeline》六阶段/九工序的架构评审（F1–F8）。决策：①消除摄入车道 `zh_type` 垃圾桶——未治理类型不再自由落图，改「open 层暂存 + 转 candidate_store 候选」（复用既有审批飞轮，不在 Neo4j 另开 open 层，typed 图强不变量=只含受治理事实）；②质量闸占位子项（G2.2 基数/G2.3 is_a 无环/G2.4 LLM Judge 未接入）标 `evaluated=False` 并剔出 gate 均分，消除伪绿 KPI；③写前经 `UslTermResolver.canonical_of` 归一类型，未命中打 `unresolved_term`（禁静默降级）；④F7 SHACL 挂写图路径 + violation 队列、⑤competency questions 度量 + 治理只读人类先例/熔断留后续独立 ADR。仅移植模式不移植栈（不引入 Rust/PG/Tantivy），不照搬 utopia "types never gate" 与 embedding 缺失静默降级。分片 S1(F2)/S2(F1)/S3(F3) 本轮落地，补真实 tmp_path 单测；新增 biz.data.knowledge_base→biz.semantic_admin.candidate_store 依赖边（import-linter 无契约禁止，先例 qa→usl_manager） | 084 |
| 2026-10-04 | 登记 ADR-085（SHACL 形状持久化与写路径校验不变量，关 F7 / 落地 ADR-084 D4 切片 S4）：勘验确认 SHACLValidator/ShapeGenerator 真实且已测但**零写路径调用方**（仅 2 个 HTTP 端点），形状不持久化，L6 AxiomDeriver 公理被丢弃只留计数，G2.2/G2.3 rego 为 `if { false }` 占位，`schema_source.validate_cardinality` 为零调用死代码，GraphWriteProxy 是意图性 chokepoint 但 `add_entity` 无 ontology/domain 上下文且有 3 个 infra 旁路 + episode 车道盖不住。决策：①形状落 `sa_shacl_shape` **版本键控派生缓存**（操作化 ADR-077 裁决1 已允许的「带 Schema 版本号失效键缓存」，非推翻；单一事实源仍是类型定义+usl 约束+L6 公理；守裁决3 校验输入显式传入不读 Neo4j）；②扩展 ShapeGenerator 消费 `usl_cardinalities`/`usl_disjoint_pairs`/L6 公理，公理持久化不再丢弃；③写路径校验点=单一 `WritePathValidator` 实现 + **上下文感知车道级调用**（摄入 typed 车道 / 治理 writeback），**不改 GraphWriteProxy 契约**，3 旁路+episode 缺口显式登记归 S4d；④**observe-first 灰度**——Phase1 违规进 `sa_axiom_violation`(status=pending) + warning 审计但**放行**（非静默，守规则14.2/14.3），Phase2 enforce 按车道 flag 阻断（可达终态，非 utopia "never gate"）；⑤G2.2 基数/G2.3 is_a 无环用持久化约束真值替换占位 + `evaluated=True`，删死代码。分片 S4a(形状/公理持久化,低)/S4c(G2.2/G2.3 真值,低) 待批即 TDD 落地，S4b(observe 校验点,中) 获批后落，**S4d(enforce+收敛旁路+修订已接受 ADR-077,高 blast radius) 须单独评审**。须在 ADR-077 加「Superseded in part by ADR-085」批注 | 085 |
| 2026-10-07 | 登记 ADR-086（概念缺口回路，借鉴 BeModel concept-gap-loop 模式不借栈）：四类运行时"未答"信号源（term_resolve_miss `usl_term_resolver.py:113/123` / nl_query_unanswered `nl_engine.py:68` / qa_unanswered `qa_engine.py:1322` / mapping_failure `intent_recognizer.py:163`）此前只落 logger、化石化速度不可见。决策：①新建 semantic_admin 第 10 子服务 `gap_pool`（缺口≠候选，不扩展 candidate_store）；②同步 emitter 收敛点绝不 raise 绝不阻塞主响应（异常→warning+`_emit_failures` 内存计数经 stats 暴露，**重启归零**为登记取舍）；③heat 聚合 + `scope_key={ws}::{domain}` 唯一索引 + sources 最近 50 条截断，表名 `concept_gaps`（**不带 sa_ 前缀**，如实登记）；④人工裁决 promote/dismiss，晋升经 `create_candidate_from_gap` **复用既有审批飞轮**（幂等 already_promoted），rejected+新信号回 open 续累；⑤writeback side-channel 回调 `on_candidate_resolved`（adopted/rejected）闭环，无匹配 no-op 绝不 raise，writeback 失败不改 gap 状态；⑥resolve-check 非 term 类如实 resolvable=False、stats adoption_rate 分母 0 返回 null 不造数。6 端点 `/api/semantic-admin/gaps`（promote/dismiss 走 verify_semantic_writer，/stats 声明先于 /{gap_id}）+ 前端三页（list/detail/stats）+ 菜单 seed/迁移。T1–T8 TDD 落地，6 个 gap 单测 + 回路验收测试（"同一个问题下次能答上"）全绿；代码 staged 待用户提交，dev 容器手验与整分支终审待办 | 086 |
| 2026-10-09 | 登记 ADR-088（EvoOntology 借鉴采纳：归因分层与配对回放门控，借鉴 EvoOntology attribution-guided typed edits + backbone-conditional paired evaluation 两机制，auto-accept 明确不采纳）：源自 2026-10-08 对照 EvoOntology（RUC，arXiv 2609.15779）审视 ADR-086 已落地回路的评审——回路能"闭"不能"验证"。决策：①gap 加 attribution 双层结构（gap 级 `attribution_counts_json` 全量计数 + occurrence 级 attribution 键，镜像既有 source 双层模式；GapLayer 三层枚举 schema/content/tool；最佳努力归因不造数；emitter 加可选参数向后兼容）；②缺口 occurrence 固化为不可变回归集（缺口即现成 held-out 验证集）+ 配对回放（信号收集器判定 answered，verdict=pass ⇔ 回归 0 且修复≥1；EM/F1 明确排除防全零失真）；③**门控归人不归模型**——paired 报告只作审批证据不自动接受/驳回（ODAP 本体挂 OPA 权限/审计/版本不可变，爆炸半径与 EvoOntology 不同）；④回放期间绝不写 concept_gaps（M1 只读守卫延伸）；⑤模型指纹 model_id+prompt_version（LM Studio 换模型常态下报告保持可复现）+ cost_json 补 EvoOntology 论文自认未做的 cost accounting，侧道自动回放默认 off；⑥落 gap_pool/regression/ 子包不新建顶级模块，resolve_check fast 语义不动，paired 独立端点；⑦promote 归因透传 semantic_type（无 attribution 行为不变）。信号收集器模块级补丁的线程安全权衡如实登记（顺序同步执行 + 管理端手动触发缓解，pipeline response 自带 fallback 标记则优先，emitter 内置 collector 协议记为后备不预实现）。同轮预留 ADR-087 编号给语义漂移检测（spec/plans 已定稿待复审） | 088 |
| 2026-10-09 | 登记 ADR-089（子项目 C：ontology_semantics MCP 工具替代 EntityExtractor 全量注入；EvoOntology「查询优于注入」论点的工程落地）：源自 ADR-088 §4.3 立项框。决策：①复用现有 7 工具注册机制（`mcp/semantic_retrieval_tools.py:223-261` 模板），新增第 8 工具 `ontology_semantics`；②工具签名 `(expression, domain_id, kinds) → {content, schema, tool, cost}` 镜像论文 schema/content/tool 三层；③EntityExtractor 双模式 `inject/query`（默认 query，向后兼容，旧调用零行为变化）；④复用现有 `RetrievalService.nl_search / search`，不新建引擎（C3 守门）；⑤成本对账 `cost_audit` 不可变表（补论文自承空白），注入 vs 查询均摊 wall_ms 对比；⑥失败降级 handler 不 raise + 客户端二次兜底走原词（规则 14）；⑦第 8 端点 `/api/ontology/mcp/semantics` 仅诊断用，agent 走 MCP 协议；⑧既有 7 工具 OpenAPI schema 零变化；⑨报告不可变纪律延伸；⑩缓存只在客户端（per-extract 内存），server 端无 cache（防幽灵一致性 + 论文无状态假设一致） | 089 |
| 2026-10-09 | 登记 ADR-090（子项目 D：promote 按 attribution.layer 路由到 USL candidate / ChangeProposal / tool_routing_ticket，类型化编辑）：源自 ADR-088 §4.3 立项框。决策：①promote 入参加 `force_layer=None`（None = 按 attribution 自动），保留向后兼容；②风险倒序优先级 schema > tool > content（结构问题先于术语解决）；③content 路径行为零变化（既有 test_gap_promote 零回归红线）；④schema 路径存 ChangeProposal 不立即 ImpactAnalyzer（避免被驳回时浪费算力，审批前手动跑）；⑤落 `change_proposals` 表沿用 goal 既有存储；⑥tool 路径落 `tool_routing_tickets` 最小集（open → resolved_by + note），不调 unified_router 改路由；⑦门控归人（ADR-088 D3 延伸）——EvoOntology 自动接受在本项目不适用，本体挂 OPA/审计/版本不可变；⑧promote_router 单独模块（gap_service.promote 保持薄壳调度三条 _route_*）；⑨不接 pair-replay（不自动改无必要，proposal.model_validator 静态校验足够）；⑩旧数据（无 attribution）走 content（与 ADR-088 D10 不造数一致） | 090 |
| 2026-10-28 | 登记 ADR-091（语义发布生命周期与本体单一写入通道）：源自统一语义层工作台设计（对照 microsoft/Ontology-Playground 的语义层展示能力评审）。勘验确认 USL 六表无状态/版本/修订、直接 CRUD 即被消费（QA/SHACL/写回）、本体 TBox 有五条写入路径（人工/AI/USL 写回/HE/感知）、AI 写工具直写 `OntologyService`、USL 写回按 `USL__` 命名建本体且关系缺端点静默降级。决策：①`usl_*` 工作表=草案，发布版本=不可变 `snapshot_json`（`usl-package-v1`），消费方只读 `PublishedUslView`；②生命周期 `draft→pending_review→published→deprecated`，版本只在发布时创建；③三层保存（600ms 自动保存写草案 / 变更集聚合 + 复合原子 / 发布人工门），L1 只做单行校验，同字段窗口内合并 items；④变更集状态机 + 四眼 + `base_content_hash` rebase 409；⑤`OntologyWriteGateway` 唯一写入通道，W1–W5 全转提案/网关应用，`origin` 矩阵；⑥AI 任何权限下只提案，`ai.write_mode` 仅 `proposal`；⑦一个工作台四区（定义/审核/发布/探查）三视图（图谱/卡片/表格），探查/编辑=模式+服务端权限，`embed=1` 仅布局开关；⑧USL 不含本体特有构造；⑨RDF 只导出发布版、导入落草案；⑩消费方固定 `version_id`，`USL_CONSUMPTION_MODE` 显式切换；⑪新增 C5 import-linter 契约（`allow_indirect_imports=true`，`public.py` 只导出网关与读服务，ignore_imports 只减不增）；⑫迁移把现有域 bootstrap 为 `v1` 快照。设计为 P0–P5 分期，P0–P2 可覆盖首个实施计划 | 091 |
