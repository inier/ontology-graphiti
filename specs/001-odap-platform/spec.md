# Feature Specification: ODAP 本体驱动分析决策平台

**Feature Branch**: `001-odap-platform`

**Created**: 2025-06-13

**Status**: Draft

**Input**: 从项目文档体系提取 — DOCUMENT_RELATIONSHIP.md + 00-requirements/req-ok.md

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 本体设计与知识结构化 (Priority: P1)

领域专家通过可视化界面设计本体模型（实体类型、属性、关系、约束），将非结构化知识转化为结构化本体。系统支持本体版本管理，每次变更生成版本记录，支持一键回滚。用户可批量导入本体实例数据，系统自动验证属性完整性。

**Why this priority**: 本体是平台的核心基础，没有结构化知识，后续的推理、问答、推演都无法运作。这是平台存在的根本价值。

**Independent Test**: 可通过创建一个包含 3 种实体类型和 2 种关系的本体，导入 10 条实例数据，验证 CRUD 和版本回滚来独立测试。

**Acceptance Scenarios**:

1. **Given** 用户进入本体设计器, **When** 创建实体类型"装备"并添加属性"名称/类型/状态", **Then** 实体类型保存成功，属性面板显示完整属性列表
2. **Given** 已有本体版本 v1, **When** 修改实体属性并保存, **Then** 系统生成版本 v2，版本历史记录变更内容
3. **Given** 当前版本为 v3, **When** 用户选择回滚到 v1, **Then** 本体恢复到 v1 状态，关联逻辑自动更新
4. **Given** 用户上传包含 50 条实例的 CSV 文件, **When** 执行批量导入, **Then** 系统验证属性完整性，无效数据被标记并跳过

---

### User Story 2 - 多智能体协同调度 (Priority: P2)

指挥官通过自然语言下达任务意图，系统自动识别意图并分发给对应角色的智能体（指挥官/情报分析员/操作员）。智能体之间通过消息传递协同工作，决策过程可追溯、可回放。

**Why this priority**: 多智能体协同是平台的核心差异化能力，但依赖本体知识基础，因此排在 P1 之后。

**Independent Test**: 可通过发送一条自然语言指令，验证意图识别、任务分发、Agent 响应和消息传递链路来独立测试。

**Acceptance Scenarios**:

1. **Given** 3 个 Agent 角色已配置, **When** 用户输入"分析当前态势", **Then** 系统识别为情报分析意图，分发给 Intelligence Agent
2. **Given** Intelligence Agent 完成分析, **When** 生成分析报告, **Then** 报告自动传递给 Commander Agent，决策链路可追溯
3. **Given** Agent 正在执行任务, **When** 用户查看决策过程, **Then** 系统展示完整思维链和推理步骤

---

### User Story 3 - 策略治理与权限控制 (Priority: P2)

管理员通过 Markdown 编写 OPA 策略规则，策略可热更新无需重启服务。系统基于 ABAC 模型执行细粒度权限校验，所有操作记录审计日志。

**Why this priority**: 安全和合规是平台生产化的前提，与多智能体协同同等重要但可并行开发。

**Independent Test**: 可通过编写一条策略规则、验证策略生效、查看审计日志来独立测试。

**Acceptance Scenarios**:

1. **Given** 管理员编写 Markdown 策略, **When** 提交策略, **Then** 策略自动编译为 Rego 并加载，30 秒内生效
2. **Given** 策略限制"普通用户不可删除工作空间", **When** 普通用户尝试删除, **Then** 操作被拒绝并记录审计日志
3. **Given** 管理员更新策略, **When** 策略加载失败, **Then** 系统保持旧策略运行（fail-close），告警通知管理员

---

### User Story 4 - 模拟推演与决策支持 (Priority: P3)

用户在沙箱环境中配置推演参数，运行多方案并行推演。推演过程通过 WebSocket 实时推送，支持 What-if 参数敏感性分析。推演结果与决策推荐模块集成，支持多策略对比。

**Why this priority**: 推演是高价值功能但依赖本体和 Agent 基础设施，属于增强层。

**Independent Test**: 可通过创建一个推演方案、配置参数、运行推演并查看实时结果来独立测试。

**Acceptance Scenarios**:

1. **Given** 用户创建推演方案, **When** 配置参数并启动, **Then** 推演在隔离沙箱中运行，不影响生产数据
2. **Given** 推演正在运行, **When** 用户修改参数重新推演, **Then** 系统支持多方案并行，结果以并排对比视图展示，高亮关键指标差异
3. **Given** 推演完成, **When** 用户查看决策建议, **Then** 系统以并排对比视图展示多策略结果和优化建议

---

### User Story 5 - 问答引擎与知识检索 (Priority: P3)

用户通过自然语言提问，系统融合本体知识和图谱检索生成回答，支持多轮对话上下文理解。问答结果可附带多种图表展示，用户可一键将当前视图信息添加到问答上下文。

**Why this priority**: 问答是用户与知识交互的主要方式，但依赖本体和图谱基础设施。

**Independent Test**: 可通过输入自然语言问题、验证回答准确性、检查图表展示来独立测试。

**Acceptance Scenarios**:

1. **Given** 本体已加载知识数据, **When** 用户提问"当前有哪些高风险装备", **Then** 系统返回基于图谱的准确回答
2. **Given** 用户已提问一次, **When** 追问"其中哪些需要维修", **Then** 系统理解上下文，返回关联结果
3. **Given** 问答结果包含数据, **When** 用户选择图表展示, **Then** 系统渲染对应图表，支持 8 种以上图表类型

---

### User Story 6 - 用户认知引擎 (Priority: P2)

用户通过自然语言与系统交互，系统自动识别用户意图和角色，提供基于本体的知识导航和推理路径可视化。不同角色（指挥官/分析员/操作员）获得定制化视图，AI 决策过程可解释、可追溯。基于 OpenHarness 进行相关设计。

**Why this priority**: 用户认知引擎是"全流程可视化"目标的关键支撑，需求定稿中 FR-1100~FR-1104 均为 P0，但依赖本体和 Agent 基础设施，因此排在 P2。

**Independent Test**: 可通过切换角色视图、提问并验证意图识别结果、查看推理链路解释来独立测试。

**Acceptance Scenarios**:

1. **Given** 用户以指挥官角色登录, **When** 输入"当前态势如何", **Then** 系统识别为态势分析意图，展示指挥官定制视图
2. **Given** 用户查看 AI 决策结果, **When** 点击"为什么", **Then** 系统展示完整推理链路和决策依据
3. **Given** 用户在知识图谱中导航, **When** 选择某实体追溯关联, **Then** 系统高亮推理路径，支持逐步回溯

---

### Edge Cases

- 本体版本回滚时，如果当前有 Agent 正在使用该本体的知识，如何处理？系统 MUST 通知相关 Agent 刷新知识缓存
- 推演沙箱资源耗尽时（内存/时间超限），系统 MUST 自动终止推演并返回部分结果和超时提示
- OPA 策略编译失败时，系统 MUST 保持旧策略运行（fail-close），MUST NOT 暴露 Rego 编译错误细节给非管理员用户
- 多个用户同时修改同一本体时，系统 MUST 使用乐观锁检测冲突，保留双方版本并提示用户手动选择合并
- 问答引擎在图谱数据为空时，MUST 返回友好提示而非错误信息

## Clarifications

### Session 2025-06-13

- Q: 多模态数据接入（FR-004）在当前阶段应覆盖哪些类型？ → A: 文档（PDF/Word）+ 图片 OCR，音视频后续阶段
- Q: 本体实例的唯一性标识如何判断？ → A: 基于主键属性组合（用户在实体类型中指定哪些属性构成唯一标识）
- Q: Skill 热插拔的注册机制（FR-014）如何实现？ → A: 当前阶段仅使用 OpenHarness 注册（覆盖 ADR-030 推迟决策，以此 spec 为准）
- Q: 推演结果展示方式？ → A: 并排对比视图（多方案关键指标同屏展示，高亮差异）
- Q: 本体并发编辑冲突如何解决？ → A: 保留双方版本，提示用户手动选择合并
- Q: OpenHarness 集成状态——ADR-030 推迟到 Phase 4，但 spec 要求当前阶段使用？ → A: 当前阶段必须基于 OpenHarness 集成，原有设计与此冲突的以此 spec 为准
- Q: 本体管理层是否拆分为两个子系统？ → A: 拆分为"本体模型层"（基于企业架构 BA 最小业务单元生成基础模型，设计参考 Palantir 结构）和"本体管理引擎"（摄入/构建/版本/验证）
- Q: 用户认知引擎是否纳入当前阶段？ → A: 纳入当前阶段，新增 User Story 6，基于 OpenHarness 进行相关设计
- Q: 对象服务层（OSv2）是否纳入当前 spec？ → A: 推迟到实施计划阶段，spec 不涉及基础设施层选型
- Q: 推演沙箱隔离方式？ → A: 进程级隔离，基于 OpenHarness 的沙箱机制实现（覆盖需求定稿 FR-601 的 Docker 容器隔离要求）
- Q: Agent 编排架构选择？ → A: 基于 OpenHarness Swarm 的 DomainSwarm（OODA 循环编排），支持按意图自动规划 subAgent
- Q: 可视化渲染策略？ → A: 混合模式——适合前端渲染的（图表/图谱/地图等轻量交互型可视化）放前端（G6+Leaflet+ECharts），必须后端渲染的（复杂 3D/热力图等计算密集型可视化）放后端
- Q: MCP 协议集成是否纳入当前阶段？ → A: 纳入当前阶段，基于 OpenHarness 实现 MCP 协议集成，支持外部领域仿真系统接入
- Q: Hook System 和 Decision Recommendation 是否纳入？ → A: 明确纳入两者——Hook System 作为安全横切层（基于 OpenHarness 生命周期钩子），Decision Recommendation 作为推演下游（基于 Graphiti RAG 的方案推荐和风险评估）
- Q: 事件模拟器是否纳入？ → A: 明确纳入事件模拟器作为推演引擎的上游依赖（事件生成 → 推演分析），支持自动/手动事件生成、时间线引擎和事件注入；事件模拟必须基于当前工作空间的本体定义展开，生成的事件必须与本体具有相关性（可以是间接关联，但不能文不对题）
- Q: 认证机制支持哪些方式？ → A: 当前阶段支持 OAuth2/OIDC（企业 SSO）+ 本地账号密码（离线环境），API Key 推迟到下一阶段
- Q: OADP 闭环反馈是否纳入？ → A: 纳入当前阶段，基于 OpenHarness 实现闭环反馈（如 OpenHarness 缺少则补充），实现"感知-理解-决策-执行-追踪"完整闭环
- Q: Agent 路由策略？ → A: 混合路由（规则优先 + LLM 兜底），不确定时默认路由到 Intelligence Agent；路由规则及置信度必须基于本体事实而定
- Q: 部署架构是否明确？ → A: 模块化单体部署（FastAPI 单进程 + Neo4j + OPA + OpenHarness in-process），Docker Compose 编排；代码层面必须保证 OpenHarness 的独立性，支持官方升级，不得 fork 或深度修改 OpenHarness 核心代码
- Q: Graphiti 双时态能力使用范围？ → A: 全面利用双时态能力——本体版本管理、问答时序推理、推演历史对比均基于 Graphiti 双时态（valid_time + transaction_time）
- Q: 统一查询服务（ADR-055）是否纳入？ → A: 必须纳入，消除 5 条分散查询路径，构建统一 QueryService（schema/entity/topo/temporal 四种查询源），通过 OpenHarness Tool 接口注册，实现 Agent Safe 默认只读
- Q: 会话记忆是否纳入？ → A: 纳入当前阶段，基于 OpenHarness Memory Plugin 实现会话记忆管理（短期记忆/工作记忆/长期记忆），长期记忆持久化到 Graphiti
- Q: 工具注册表是否纳入？ → A: 纳入当前阶段，统一工具注册表作为所有可调用能力（Skill/QueryService/MCP）的注册基础，避免能力管理碎片化
- Q: 语义层修正（ADR-056）是否纳入？ → A: 纳入当前阶段，引入结构化语义层（Intent → StructuredQuery → Agent Task）消除意图与执行之间的语义断裂；语义层需提供前端扩展功能，支持配置同义/近似和扩写等消除歧义的能力
- Q: 基础设施层（Infra）是否需要 FR？ → A: 不需要，基础设施层（配置管理/日志/健康检查/指标收集/错误处理）属于实施计划范畴，spec 聚焦功能需求
- Q: 数据库架构是否需要在 spec 中明确？ → A: 不需要，数据库选型属于实施计划范畴；但必须注意不能重复引入类似存储设计，已有存储引擎能满足需求的不应再引入新的
- Q: 安全架构的数据分类与加密是否需要在 spec 中明确？ → A: 需要，新增 FR 要求 4 级数据分类（TS/S/C/U）和对应加密要求（TLS 1.3 + AES-256-GCM + KMS）
- Q: 测试策略是否需要在 spec 中明确？ → A: 需要，新增 FR 要求测试金字塔（80% 单元/15% 集成/5% E2E）和质量门禁，与宪法原则 III"测试优先"对齐
- Q: 前端组件体系是否需要在 spec 中明确？ → A: 不需要新增 FR，但 5 级组件体系是规范要求，必须全项目统一组件库，且需做好组件库可替代性设计（隔离层）
- Q: API 设计规范是否需要在 spec 中明确？ → A: 不需要，API 设计规范（响应格式/request_id/分页/错误码）属于实施计划范畴
- Q: 前端响应式策略矛盾（ADR-037 移动优先 vs Assumptions 桌面优先）？ → A: 严格移动优先（ADR-037），当前阶段必须同时支持移动端和桌面端，遵循 6 断点响应式设计
- Q: OntologyDocument 统一格式是否需要 FR？ → A: 需要，OntologyDocument JSON 作为系统内数据流通的统一原子格式，与 Palantir AIP/OWL/RDF 语义层对齐
- Q: 国际化（i18n）是否纳入当前阶段？ → A: 纳入当前阶段，支持中英双语，翻译文件按模块拆分；提供后台管理配置界面，支持基于 LLM 模型的自动翻译功能
- Q: 多数据源统一接入（ADR-013）是否需要 FR？ → A: 不需要，DataSourceAdapter 属于实施计划范畴，FR-004 和 FR-017 已覆盖数据源接入的功能需求
- Q: 运维监控与告警是否需要 FR？ → A: 不需要，运维监控（Prometheus/Grafana/AlertManager/Golden Signals/备份恢复）属于实施计划范畴

### Session 2026-05-30

- Q: 审计本体与业务本体的隔离机制（FR-033）？ → A: 审计本体物理隔离（独立 Graphiti 实例），仅平台内部使用，用户不可见审计本体查询入口
- Q: OADP 闭环反馈机制（Feedback Collector/Analyzer/Aggregator）与 OpenHarness 的关系？ → A: Feedback Collector/Analyzer/Aggregator 作为 OpenHarness 的外层封装，部署在同一进程内，通过 OpenHarness 的 Hook 机制触发
- Q: 用户角色体系（指挥官/情报分析员/操作员）是 Agent 角色还是用户角色？ → A: 这些是 Agent 角色（AI 代理），普通用户通过自然语言与 Agent 交互；ABAC 权限模型控制 Agent 的行为权限；注意这些仅为示例角色，系统采用通用 Agent 角色模型，具体角色可扩展
- Q: 性能基准与规模假设是否需要在 spec 中定义？ → A: 不在 spec 中定义具体数值，仅描述为"响应迅速"和"可扩展"，具体数值留到实施计划阶段
- Q: 架构守卫与查询安全边界（Agent Safe 默认只读）如何执行？ → A: 架构守卫(pytest)强制执行 Query First 规则——测试用例验证 Agent 代码中没有直接调用 graph_manager 的写方法；代码审查确保新增代码遵守

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 提供可视化本体设计器，支持实体类型、属性、关系、约束的定义和编辑；本体模型层基于企业架构 BA 最小业务单元生成基础模型，设计参考 Palantir 结构
- **FR-002**: 系统 MUST 支持本体版本管理，基于 Graphiti 双时态能力（valid_time + transaction_time），每次变更生成版本记录，支持一键回滚和历史状态快照查询（本体管理引擎负责）
- **FR-003**: 系统 MUST 支持本体实例的 CRUD 操作和批量导入，导入时自动验证属性完整性（本体模型层负责 CRUD，本体管理引擎负责验证）
- **FR-004**: 系统 MUST 支持多模态数据接入（PDF/Word 文档 + 图片 OCR），自动抽取实体更新本体；音视频接入推迟到后续阶段
- **FR-005**: 系统 MUST 支持多 Agent 角色定义和协同调度，基于 OpenHarness Swarm 的 DomainSwarm 实现 OODA 循环编排，支持按意图自动规划 subAgent；采用混合路由策略（规则优先 + LLM 兜底），路由规则及置信度必须基于本体事实而定，不确定时默认路由到 Intelligence Agent；意图识别准确率 > 90%
- **FR-006**: 系统 MUST 展示 Agent 决策过程和推理链路（思维链可视化）
- **FR-007**: 系统 MUST 支持通过 Markdown 编写 OPA 策略，策略可热更新
- **FR-008**: 系统 MUST 基于 ABAC 模型执行细粒度权限校验，所有写操作记录审计日志
- **FR-009**: 系统 MUST 提供沙箱推演环境，基于 OpenHarness 的沙箱机制实现进程级隔离，推演数据与生产环境完全隔离
- **FR-010**: 系统 MUST 支持多方案并行推演和 What-if 参数敏感性分析
- **FR-011**: 系统 MUST 支持自然语言问答，融合本体知识与图谱检索，支持多轮对话；利用 Graphiti 双时态能力支持时序推理（"当时发生了什么"类问题）；图表展示采用混合渲染模式：图表/图谱/地图等轻量交互型可视化前端渲染（G6+Leaflet+ECharts），复杂 3D/热力图等计算密集型可视化后端渲染
- **FR-012**: 系统 MUST 支持工作空间创建与管理，工作空间之间数据完全隔离
- **FR-013**: 系统 MUST 支持场景切换，切换后本体、技能、配置、策略自动切换
- **FR-014**: 系统 MUST 支持 Skill 热插拔，新增 Skill 通过 OpenHarness Skill 管理功能注册和发现，无需重启服务即可生效；当前阶段必须基于 OpenHarness 集成（覆盖 ADR-030 推迟决策）
- **FR-015**: 系统 MUST 支持数据摄入审计，记录数据来源、处理过程和转换规则
- **FR-016**: 系统 MUST 提供用户认知引擎，基于 OpenHarness 设计，支持意图识别、知识导航、解释引擎和角色视图管理
- **FR-017**: 系统 MUST 基于 OpenHarness 实现 MCP 协议集成，支持外部领域仿真系统（雷达模拟器、气象数据源、卫星影像等）通过 MCP v1.0 协议标准化接入，支持运行时动态添加/移除 MCP Server
- **FR-018**: 系统 MUST 提供基于 OpenHarness 生命周期钩子的 Hook 系统，支持 Agent 执行前后的拦截、增强和监控；OPA 策略注入和审计日志通过 Hook 实现
- **FR-019**: 系统 MUST 提供决策推荐引擎，基于 Graphiti RAG 增强推理，为推演结果提供方案推荐、多维度风险评估和决策理由可解释性
- **FR-020**: 系统 MUST 提供事件模拟器作为推演引擎的上游依赖，支持按剧本/模板自动生成事件序列、手动注入关键事件、模拟时钟独立控制（加速/减速/暂停）；事件模拟必须基于当前工作空间的本体定义展开，生成的事件必须与本体具有相关性（可以是间接关联，但不能文不对题）
- **FR-021**: 系统 MUST 支持 OAuth2/OIDC（企业 SSO）和本地账号密码两种认证方式，签发 JWT Token 作为访问凭证；API Key 认证推迟到下一阶段
- **FR-022**: 系统 MUST 基于 OpenHarness 实现闭环反馈机制（如 OpenHarness 缺少则补充），完成"感知-理解-决策-执行-追踪"完整闭环；执行结果反馈到感知层，决策效果可量化评估，历史经验沉淀到知识图谱
- **FR-023**: 系统 MUST 提供统一查询服务（QueryService），整合分散的图谱查询路径为统一接口，支持 4 种查询源（schema/entity/topo/temporal），通过 OpenHarness Tool 接口注册，Agent Safe 默认只读
- **FR-024**: 系统 MUST 基于OpenHarness Memory Plugin 实现会话记忆管理，支持短期记忆（对话上下文）、工作记忆（当前任务状态）、长期记忆（持久化到 Graphiti）；多轮对话和 Agent 协同必须基于记忆上下文
- **FR-025**: 系统 MUST 提供统一工具注册表（ToolRegistry），所有可调用能力（Skill/QueryService/MCP Server）必须注册为 Tool，统一管理生命周期、权限和调用；基于 OpenHarness Tool 接口实现
- **FR-026**: 系统 MUST 提供结构化语义层，实现 Intent → StructuredQuery → Agent Task 的结构化映射，消除意图识别与 Agent 执行之间的语义断裂；语义层 MUST 提供前端扩展功能，支持用户配置同义词/近似词映射和扩写规则，消除自然语言输入的歧义
- **FR-027**: 系统 MUST 支持 4 级数据分类（TS 绝密/S 机密/C 内部/U 非密），TS/S 级数据 MUST 加密存储（AES-256-GCM）+ 传输加密（TLS 1.3），密钥通过 KMS 统一管理并支持轮换；C 级数据 MUST 传输加密；U 级数据采用标准安全措施
- **FR-028**: 系统 MUST 遵循测试金字塔策略（80% 单元测试 / 15% 集成测试 / 5% E2E 测试），PR 合并前 MUST 通过质量门禁：单元测试覆盖率 > 80%、集成测试 0 失败、Lint 0 error、类型检查 0 error；发版前 MUST 通过 E2E 核心流程测试、性能测试和安全扫描
- **FR-029**: 系统 MUST 采用 OntologyDocument JSON 作为数据流通的统一原子格式，所有数据摄入、导入导出、模块间数据交换 MUST 使用此格式；格式与 Palantir AIP 本体结构（Object Type/Property/Action/Rule）和 OWL/RDF 语义层对齐
- **FR-030**: 系统 MUST 支持国际化（i18n），当前阶段至少支持中英双语，翻译文件按模块拆分；MUST 提供后台管理配置界面管理翻译条目，MUST 支持基于 LLM 模型的自动翻译功能

### Key Entities

- **本体模型层 (Ontology Model)**: 领域知识的形式化定义，基于企业架构 BA 最小业务单元生成基础模型，设计参考 Palantir 结构；包含实体类型、属性、关系、约束；负责实例 CRUD；实例唯一性基于主键属性组合判定
- **本体管理引擎 (Ontology Management Engine)**: 本体生命周期管理，负责数据摄入审计、本体构建、版本管理（追踪/对比/回滚）、验证引擎（质量检查/一致性验证）
- **工作空间 (Workspace)**: 隔离的场景容器，包含独立的本体、技能、配置和策略；4 级隔离（low/standard/high/strict）
- **智能体 (Agent)**: 基于 OpenHarness Swarm 的 DomainSwarm 实现 OODA 循环编排，支持按意图自动规划 subAgent；至少 3 种角色（Commander/Intelligence/Operations）
- **技能 (Skill)**: 可热插拔的能力单元，由 Agent 按需调用；通过 OpenHarness Skill 管理功能注册和发现；支持分类浏览和生命周期管理
- **策略 (Policy)**: OPA 策略规则，支持 Markdown 编写和热更新；fail-close 模式
- **推演方案 (Simulation Scenario)**: 沙箱中的模拟推演配置，支持参数配置和版本管理
- **审计日志 (Audit Log)**: 所有操作的完整记录，包含 actor、action、resource、result、timestamp
- **用户认知引擎 (User Cognition Engine)**: 基于 OpenHarness 设计，包含意图识别器、知识导航器、解释引擎、角色视图管理器；连接用户与系统的桥梁
- **MCP 协议层 (MCP Protocol)**: 基于 OpenHarness 的外部系统集成接口层，遵循 MCP v1.0 标准；支持雷达模拟器、气象数据源、卫星影像等外部系统热插拔接入；MCP Server 在独立沙箱进程中运行
- **Hook 系统 (Hook System)**: 基于 OpenHarness 生命周期钩子的横切关注点框架；支持 Pre/Post Hook 拦截、策略注入（OPA）、审计日志、性能监控；Hook 注册表管理优先级和依赖
- **决策推荐引擎 (Decision Recommendation)**: 基于 Graphiti RAG 增强推理的方案推荐系统；支持方案生成、多维度风险评估、方案排序、决策理由可解释性
- **事件模拟器 (Event Simulator)**: 推演引擎的上游数据供应商；事件模拟必须基于当前工作空间的本体定义展开，生成的事件必须与本体具有相关性（间接关联可接受，但不能文不对题）；支持按剧本/模板自动生成事件序列、手动注入关键事件、模拟时钟独立控制；事件注入驱动本体状态演化
- **统一查询服务 (QueryService)**: 整合分散的图谱查询路径为统一接口，支持 4 种查询源（schema/entity/topo/temporal），通过 OpenHarness Tool 接口注册，Agent Safe 默认只读
- **会话记忆 (Session Memory)**: 基于 OpenHarness Memory Plugin 的记忆管理；短期记忆（对话上下文）、工作记忆（当前任务状态）、长期记忆（持久化到 Graphiti）；多轮对话和 Agent 协同的记忆上下文基础
- **工具注册表 (ToolRegistry)**: 基于 OpenHarness Tool 接口的统一能力注册中心；所有可调用能力（Skill/QueryService/MCP Server）必须注册为 Tool；统一管理生命周期、权限和调用
- **结构化语义层 (Semantic Layer)**: Intent → StructuredQuery → Agent Task 的结构化映射层；消除意图识别与 Agent 执行之间的语义断裂；提供前端扩展功能，支持用户配置同义词/近似词映射和扩写规则

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 领域专家可在 30 分钟内完成一个包含 5 种实体类型的本体设计
- **SC-002**: 本体版本回滚在 5 秒内完成，关联逻辑自动更新
- **SC-003**: Agent 意图识别准确率超过 90%，任务分发延迟 < 1 秒
- **SC-004**: OPA 策略热更新在 30 秒内生效，无需重启服务
- **SC-005**: 推演沙箱支持至少 10 个方案并行运行，单次推演平均时长 < 30 秒
- **SC-006**: 问答响应时间 P95 < 3 秒，图谱查询延迟 P95 < 500ms
- **SC-007**: 工作空间之间数据完全隔离，跨空间访问被策略拒绝
- **SC-008**: 100% 写操作有审计日志记录，支持时间线展示和溯源
- **SC-009**: 用户意图识别准确率 > 90%，角色视图切换后界面自动适配

## Assumptions

- 用户具备基本的领域知识，理解本体、实体、关系等概念
- 系统部署在内网环境，网络延迟 < 50ms
- LLM 服务可用且稳定，API 响应时间 < 2 秒
- Neo4j 图数据库已部署并可用
- OPA 策略引擎已部署并可用
- 前端用户使用现代浏览器（Chrome/Firefox/Edge 最新版）
- 前端采用移动优先（Mobile First）响应式设计策略（ADR-037），当前阶段必须同时支持移动端和桌面端，遵循 6 断点响应式设计
- 部署架构为模块化单体（FastAPI 单进程 + Neo4j + OPA + OpenHarness in-process），Docker Compose 编排
- OpenHarness 作为独立依赖集成，代码层面保证独立性，支持官方升级，不得 fork 或深度修改核心代码
- 存储引擎选型属于实施计划范畴，但必须遵循不重复引入原则：已有存储引擎能满足需求的不应再引入新的同类存储
- 前端必须遵循 5 级组件体系（L1 原子 → L2 分子 → L3 组织 → L4 模板 → L5 页面），全项目统一组件库，且必须做好组件库可替代性设计（隔离层），确保组件库可替换

### Spec-Docs 关系声明

- **权威性**: 本 spec 是当前阶段的唯一权威功能规格，docs/ 中的设计文档和 ADR 作为参考和实现指导
- **冲突处理**: 当 spec 与 docs/ADR 内容冲突时，以本 spec 为准；被覆盖的 ADR 在实施计划阶段统一修正状态
- **覆盖清单**: Clarifications 中已标记所有覆盖点（ADR-030 OpenHarness 推迟决策、FR-601 Docker 容器隔离、桌面优先假设）
- **归档准备**: 实施计划阶段需完成 docs 与 spec 的差异标注和 ADR 状态修正，为 docs 归档做准备
