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

指挥官通过自然语言下达任务意图，系统自动识别意图并分发给对应角色的智能体（指挥官/情报分析员/操作员）。智能体之间通过消息传递协同工作，决策过程可追溯、可回放。多轮对话过程中，系统基于会话记忆（SessionMemory）保持上下文连续性，Agent 协同过程中基于消息总线（agent_messages）保持状态同步。

**Why this priority**: 多智能体协同是平台的核心差异化能力，但依赖本体知识基础，因此排在 P1 之后。

**Independent Test**: 可通过发送一条自然语言指令，验证意图识别、任务分发、Agent 响应和消息传递链路来独立测试。

**Acceptance Scenarios**:

1. **Given** 3 个 Agent 角色已配置, **When** 用户输入"分析当前态势", **Then** 系统识别为情报分析意图，分发给 Intelligence Agent
2. **Given** Intelligence Agent 完成分析, **When** 生成分析报告, **Then** 报告自动传递给 Commander Agent，决策链路可追溯
3. **Given** Agent 正在执行任务, **When** 用户查看决策过程, **Then** 系统展示完整思维链和推理步骤
4. **Given** 用户进行多轮对话(>3 轮), **When** 用户引用前文结果(如"刚才分析的目标中"), **Then** 系统从短期记忆(滑动窗口 N 轮)准确检索前文实体和意图
5. **Given** 多轮对话超过滑动窗口, **When** 用户引用更早内容, **Then** 系统从长期记忆(持久化到 Graphiti)恢复上下文,保持对话连续性
6. **Given** Agent A 完成任务 T1, **When** Agent B 需要 T1 结果作为输入, **Then** 系统通过 agent_messages 消息总线传递 T1 结果,B 能基于 T1 上下文继续推理
7. **Given** 会话超过 30 分钟无活动, **When** 用户恢复会话, **Then** 系统自动加载会话记忆(含工作记忆和长期记忆),无缝恢复上下文

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

用户在沙箱环境中配置推演参数，运行多方案并行推演。推演过程通过 WebSocket 实时推送，支持 What-if 参数敏感性分析。推演结果与决策推荐模块集成，支持多策略对比。场景支持完整导出/导入（含本体/技能/配置/测试数据），跨工作空间数据完全隔离，禁止未授权跨场景访问。

**Why this priority**: 推演是高价值功能但依赖本体和 Agent 基础设施，属于增强层。

**Independent Test**: 可通过创建一个推演方案、配置参数、运行推演并查看实时结果来独立测试。

**Acceptance Scenarios**:

1. **Given** 用户创建推演方案, **When** 配置参数并启动, **Then** 推演在隔离沙箱中运行，不影响生产数据
2. **Given** 推演正在运行, **When** 用户修改参数重新推演, **Then** 系统支持多方案并行，结果以并排对比视图展示，高亮关键指标差异
3. **Given** 推演完成, **When** 用户查看决策建议, **Then** 系统以并排对比视图展示多策略结果和优化建议
4. **Given** 用户已配置好一个完整场景(含本体/技能/数据), **When** 用户选择"导出场景", **Then** 系统生成场景包(包含 ontology.json + skills.yaml + config.json + testdata.json)并提供下载链接
5. **Given** 用户在另一工作空间导入场景包, **When** 上传场景包并确认, **Then** 系统解析包内容,创建独立本体/技能/配置,生成新的 scenario_id
6. **Given** 用户在工作空间 W1 登录, **When** 尝试访问 W2 的实体/场景/数据, **Then** 系统通过 OPA 策略拦截,返回 403 禁止跨空间访问
7. **Given** 用户在工作空间 W1 摄入数据, **When** 数据写入 Graphiti, **Then** 实体 MUST 自动打 workspace_id=W1 标签,W2 用户的查询 MUST NOT 返回该实体
8. **Given** 审计日志记录跨工作空间访问尝试, **When** admin 查看审计, **Then** 系统 MUST 显示拒绝原因和发起方 user_id/workspace_id

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

### User Story 6 - 用户认知引擎 (Priority: P0)

用户通过自然语言与系统交互，系统自动识别用户意图和角色，提供基于本体的知识导航和推理路径可视化。不同角色（指挥官/分析员/操作员）获得定制化视图，AI 决策过程可解释、可追溯。基于 OpenHarness 进行相关设计。

**Why this priority**: 用户认知引擎是"全流程可视化"目标和"业务理解"能力的核心支撑，需求定稿中 FR-1100~FR-1104 均为 P0，全流程可视化要求"过程解释与溯源"是平台核心价值，因此提升为 P0。

**Independent Test**: 可通过切换角色视图、提问并验证意图识别结果、查看推理链路解释来独立测试。

**Acceptance Scenarios**:

1. **Given** 用户以指挥官角色登录, **When** 输入"当前态势如何", **Then** 系统识别为态势分析意图，展示指挥官定制视图
2. **Given** 用户查看 AI 决策结果, **When** 点击"为什么", **Then** 系统展示完整推理链路和决策依据
3. **Given** 用户在知识图谱中导航, **When** 选择某实体追溯关联, **Then** 系统高亮推理路径，支持逐步回溯

---

### User Story 7 - 工作空间管理与隔离 (Priority: P1)

> **注**: 工作空间管理在 User Story 1 (本体设计) 基础上独立为 Story 7，强调工作空间作为隔离容器的独立价值

用户创建工作空间（Workspace）作为隔离的场景容器，每个工作空间包含独立的本体、技能、配置和策略。用户可在工作空间之间切换，切换后所有上下文（本体/技能/配置/策略/会话）自动加载。

**Why this priority**: 工作空间是平台"多场景支持"战略定位的基础，没有工作空间隔离，多场景能力无法实现。

**Independent Test**: 可通过创建两个工作空间、分别配置不同本体和数据、验证数据完全隔离来独立测试。

**Acceptance Scenarios**:

1. **Given** 用户已登录, **When** 创建工作空间 W1 并选择隔离级别(standard), **Then** 系统创建独立的工作空间 ID，本体/技能/配置初始化为空
2. **Given** 工作空间 W1 和 W2 已存在, **When** 用户切换 W1 → W2, **Then** 系统自动加载 W2 的本体/技能/配置/策略,清空当前会话上下文
3. **Given** W1 摄入数据 a, **When** 在 W2 查询, **Then** 系统 MUST NOT 返回 a (数据隔离)
4. **Given** W1 配置策略禁止删除本体, **When** 用户在 W1 尝试删除, **Then** 操作被 OPA 拒绝,审计日志记录

---

### User Story 8 - 决策推荐引擎 (Priority: P0)

> **注**: 决策推荐引擎从 User Story 4 (推演与决策) 独立为 Story 8，强调其作为 RAG 增强推理核心组件的独立价值

Commander Agent 基于 Graphiti RAG 增强推理，针对当前态势生成多个候选方案，每个方案附带多维度风险评估（成本/收益/风险/置信度）。系统对方案进行排序，提供最优推荐和决策理由的可解释性。所有推荐结果持久化到 Graphiti，支持历史方案对比。

**Why this priority**: 决策推荐是 OADP 闭环的"Decide"环节核心，是业务理解能力的最终输出形式，FR-019 明确要求 P0 优先级。

**Independent Test**: 可通过触发一次决策场景、验证方案生成、风险评估、推荐排序、决策理由可视化来独立测试。

**Acceptance Scenarios**:

1. **Given** 当前态势已分析(态势报告可用), **When** Commander 触发决策推荐, **Then** 系统生成 ≥ 3 个候选方案,每个方案包含名称/描述/关键参数
2. **Given** 多个候选方案已生成, **When** 系统执行风险评估, **Then** 每个方案 MUST 输出 4 维度评分(成本/收益/风险/置信度,0-100 分)
3. **Given** 多方案评分已计算, **When** 系统排序推荐, **Then** 系统按综合得分降序展示,Top 1 方案 MUST 高亮显示
4. **Given** 用户查看 Top 1 方案, **When** 点击"为什么推荐", **Then** 系统展示决策依据: 引用本体中相关业务规则 + 知识图谱关联实体 + 风险评估明细
5. **Given** 决策推荐已生成, **When** 用户在推演沙箱中试运行, **Then** 推演结果回写到决策推荐,作为方案可行性验证
6. **Given** 历史决策推荐已存在, **When** 新场景与历史相似度 > 80%, **Then** 系统 MUST 主动推荐历史方案作为参考
7. **Given** 决策推荐 API 被调用, **When** Graphiti 不可用, **Then** 系统 MUST 返回明确错误,降级为基于规则引擎的简单推荐(不静默失败)

---

### Edge Cases

- 本体版本回滚时，如果当前有 Agent 正在使用该本体的知识，如何处理？系统 MUST 通知相关 Agent 刷新知识缓存——通知机制基于 Hook 系统（FR-018）的 Post-Hook 实现，触发 Agent 知识缓存失效和重新加载
- 推演沙箱资源耗尽时（内存/时间超限），系统 MUST 自动终止推演并返回部分结果和超时提示
- OPA 策略编译失败时，系统 MUST 保持旧策略运行（fail-close），MUST NOT 暴露 Rego 编译错误细节给非管理员用户
- 多个用户同时修改同一本体时，系统 MUST 使用编辑锁定机制——同一本体同时只允许一个用户编辑，其他用户只能查看；编辑锁定基于 WebSocket 心跳维持，断开自动释放
- 问答引擎在图谱数据为空时，MUST 返回友好提示而非错误信息
- LLM 服务不可用时（API 超时/限流/宕机），意图识别（FR-005）和问答引擎（FR-011）MUST 返回明确错误提示，告知用户 LLM 不可用并建议稍后重试；MUST NOT 静默失败或返回空结果
- Neo4j 宕机时，所有图谱相关功能 MUST 降级为不可用并返回明确错误提示；SQLite 存储的数据（本体定义/版本/配置等）仍可正常访问；MUST NOT 使用 NetworkX 回退以避免数据不一致
- 批量导入实例数据（FR-003）时，如果部分记录验证失败，系统 MUST 保留成功导入的记录，返回包含成功数/失败数/失败详情的部分成功报告；MUST NOT 因部分失败而回滚全部导入
- 推演沙箱（FR-009）并行方案上限为 10 个，超过 10 个方案 MUST 排队等待；排队顺序按提交时间 FIFO
- 多轮对话（FR-011）无轮数硬性限制，但上下文窗口采用滑动窗口策略，仅取最近 N 轮对话作为当前上下文；更早的对话自动归档到长期记忆（FR-024），归档周期按会话活跃度动态调整
- 自然语言输入 MUST 防御 Cypher 注入（参数化查询）、LLM prompt 注入（输入消毒 + system prompt 隔离）和 XSS（输出编码）三层防御
- 工作空间删除时 MUST 级联删除所有关联数据（本体/实例/Agent/推演方案/缓存），操作不可恢复；删除前 MUST 二次确认
- 新用户首次登录时，空工作空间 MUST 显示引导性空状态页面，提供快速入门操作和示例数据展示，帮助用户完成首次体验
- 所有写操作 MUST 支持全局撤销（Ctrl+Z），撤销历史保留 30 天；本体版本回滚作为特殊撤销操作，与全局撤销机制统一

## Clarifications

### Session 2025-06-13

- Q: 多模态数据接入（FR-004）在当前阶段应覆盖哪些类型？ → A: 文档（PDF/Word）+ 图片 OCR，音视频后续阶段
- Q: 本体实例的唯一性标识如何判断？ → A: 基于主键属性组合（用户在实体类型中指定哪些属性构成唯一标识）
- Q: Skill 热插拔的注册机制（FR-014）如何实现？ → A: 当前阶段仅使用 OpenHarness 注册（覆盖 ADR-030 推迟决策，以此 spec 为准）
- Q: 推演结果展示方式？ → A: 并排对比视图（多方案关键指标同屏展示，高亮差异）
- Q: 本体并发编辑冲突如何解决？ → A: 编辑锁定机制——同一本体同时只允许一个用户编辑，其他用户只能查看；编辑锁定基于 WebSocket 心跳维持，断开自动释放（覆盖之前"保留双方版本"的回答）
- Q: OpenHarness 集成状态——ADR-030 推迟到 Phase 4，但 spec 要求当前阶段使用？ → A: 当前阶段必须基于 OpenHarness 集成，原有设计与此冲突的以此 spec 为准
- Q: 本体管理层是否拆分为两个子系统？ → A: 拆分为"本体模型层"（基于企业架构 BA 最小业务单元生成基础模型，借鉴 Palantir AIP 核心概念）和"本体管理引擎"（摄入/构建/版本/验证）
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
- Q: OntologyDocument 统一格式是否需要 FR？ → A: 需要，OntologyDocument JSON 作为系统内数据流通的统一原子格式，参考 Palantir AIP 核心概念设计
- Q: 国际化（i18n）是否纳入当前阶段？ → A: 纳入当前阶段，支持中英双语，翻译文件按模块拆分；提供后台管理配置界面，支持基于 LLM 模型的自动翻译功能
- Q: 多数据源统一接入（ADR-013）是否需要 FR？ → A: 不需要，DataSourceAdapter 属于实施计划范畴，FR-004 和 FR-017 已覆盖数据源接入的功能需求
- Q: 运维监控与告警是否需要 FR？ → A: 不需要，运维监控（Prometheus/Grafana/AlertManager/Golden Signals/备份恢复）属于实施计划范畴

### Session 2026-05-30

- Q: 审计本体与业务本体的隔离机制？ → A: 审计本体物理隔离（独立 Graphiti 实例），仅平台内部使用，用户不可见审计本体查询入口
- Q: OADP 闭环反馈机制（Feedback Collector/Analyzer/Aggregator）与 OpenHarness 的关系？ → A: Feedback Collector/Analyzer/Aggregator 作为 OpenHarness 的外层封装，部署在同一进程内，通过 OpenHarness 的 Hook 机制触发
- Q: 用户角色体系（指挥官/情报分析员/操作员）是 Agent 角色还是用户角色？ → A: 这些是 Agent 角色（AI 代理），普通用户通过自然语言与 Agent 交互；ABAC 权限模型控制 Agent 的行为权限；注意这些仅为示例角色，系统采用通用 Agent 角色模型，具体角色可扩展
- Q: 性能基准与规模假设是否需要在 spec 中定义？ → A: 不在 spec 中定义具体数值，仅描述为"响应迅速"和"可扩展"，具体数值留到实施计划阶段
- Q: 架构守卫与查询安全边界（Agent Safe 默认只读）如何执行？ → A: 架构守卫(pytest)强制执行 Query First 规则——测试用例验证 Agent 代码中没有直接调用 graph_manager 的写方法；代码审查确保新增代码遵守

### Session 2026-06-02 (Brainstorm)

- Q: 单个本体允许的最大实体类型数量？ → A: 无硬性限制，但可视化设计器必须支持分页/懒加载，避免大规模本体导致渲染性能问题
- Q: 批量导入单次最大数据量？ → A: 无限制，但大文件必须采用流式处理+进度反馈
- Q: 单个本体最多保留多少历史版本？ → A: 基于 Graphiti 双时态自动管理，无需手动限制
- Q: 推演并行方案超过 10 个如何处理？ → A: 硬性上限 10 个并行，超过则排队等待（FIFO）
- Q: 多轮对话最大轮数？ → A: 无硬性限制，采用滑动窗口策略，更早的会话自动归档到长期记忆，归档周期按会话活跃度动态调整
- Q: LLM 服务不可用时如何降级？ → A: 返回明确错误提示，告知用户 LLM 不可用并建议稍后重试；MUST NOT 静默失败
- Q: Neo4j 宕机时如何降级？ → A: 图谱功能降级为不可用，返回明确错误提示；SQLite 数据仍可访问；MUST NOT 使用 NetworkX 回退以避免数据不一致
- Q: 批量导入部分失败如何处理？ → A: 保留成功部分，返回部分成功报告（成功数/失败数/失败详情）；MUST NOT 因部分失败回滚全部
- Q: 推演超时如何处理？ → A: 自动终止推演，返回已计算的部分结果+超时提示
- Q: 并发用户数预期？ → A: 50-200 人同时使用，需要负载均衡
- Q: 图谱数据规模预期？ → A: 不预设规模，查询必须分页，大结果集流式返回
- Q: 自然语言注入攻击防御？ → A: 三层防御——Cypher 注入（参数化查询）+ LLM prompt 注入（输入消毒+system prompt 隔离）+ XSS（输出编码）
- Q: 工作空间删除时关联数据如何处理？ → A: 级联删除所有关联数据，不可恢复；删除前必须二次确认
- Q: 新用户首次登录空状态体验？ → A: 显示引导性空状态页面，提供快速入门操作和示例数据展示
- Q: 误操作撤销机制？ → A: 所有写操作支持全局撤销（Ctrl+Z），撤销历史保留 30 天；本体版本回滚与全局撤销统一
- Q: 本体并发编辑冲突解决？ → A: 编辑锁定机制——同一本体同时只允许一个用户编辑，其他用户只能查看；编辑锁定基于 WebSocket 心跳维持，断开自动释放（覆盖之前"保留双方版本"的回答）

### Session 2026-06-05 (Brainstorm — 本体设计+应用 Deep Dive)

- Q: 本体版本管理是否需要支持分支与合并？ → A: 采纳 Palantir 范式——支持 git-like 分支与合并（FR-032）
- Q: Object Type 复用机制？ → A: 继承 (`inherits`) + 组合 (`mixins`) 并存——继承用于类型层级，组合用于横切关注点（FR-033）
- Q: Action Type 与 Skill 关系？ → A: 严格分层——Action Type 是本体层业务接口，Skill 是能力层工程实现；Action 1:N Skill（FR-034）
- Q: 是否支持计算属性？ → A: 支持——本体声明 `depends_on` 依赖，Graphiti 物化视图层执行计算（FR-035）
- Q: Data Health 范围？ → A: 完整性 + 一致性 + 漂移，规则语言声明式 JSON/YAML，与 OPA 严格分工（FR-031）
- Q: 本体演化是否业务目标驱动？ → A: 是——变更 MUST 关联 `goal` + `rationale`，形式类似 ADR（FR-036，OntoFlow 范式）
- Q: 多利益相关方协作方式？ → A: PR/MR 评审——不引入独立工作流引擎，按 Object Type 配置评审人
- Q: 是否引入对象视图（Object View）？ → A: 是——独立概念，与 OPA 属性控制职责分离（FR-037）
- Q: Agent 与本体关系？ → A: 严格护栏——Action Type 参数 MUST 通过 OPA 校验，Agent 只能调用本体重登记的 Action Type

## Brainstorm Log

### 2026-06-02 — Edge Case Deep Dive

**Scope**: 5 类别全覆盖（边界条件/错误场景/规模性能/安全隐私/用户体验）

**Key Insights**:
1. **并发编辑策略变更**: 从"乐观锁+双方保留"改为"编辑锁定"，简化冲突解决逻辑，避免手动合并的复杂 UX
2. **降级策略明确**: LLM 不可用→明确错误提示（非静默）；Neo4j 宕机→图谱功能不可用（非 NetworkX 回退），避免数据不一致
3. **批量导入部分成功**: 采用"部分成功+错误报告"模式，而非事务回滚，提升用户体验
4. **推演并行硬上限**: 10 个并行+排队，避免资源耗尽
5. **全局撤销机制**: 所有写操作支持 Ctrl+Z，30 天历史，与版本回滚统一
6. **三层安全防御**: Cypher 注入 + LLM prompt 注入 + XSS，覆盖自然语言输入全链路
7. **引导性空状态**: 新用户首次体验需要引导+示例数据，而非空白页面
8. **规模不预设**: 图谱规模和本体实体类型数量无硬性限制，但必须通过分页/懒加载/流式处理保证性能

**New Edge Cases Added**: 9 条（见 Edge Cases 章节）
**Clarifications Updated**: 1 条修正（并发编辑冲突），16 条新增

### 2026-06-05 — 本体设计+应用 Deep Dive (Palantir/OntoFlow 视角)

**Scope**: 聚焦「本体设计 + 本体应用」两大版块，参考 Palantir Foundry (AIP/Branch&Merge/Action Type/Object View) 和 OntoFlow (Goal-oriented Evolution/Multi-stakeholder Workflow)

**Decisions Made**:

### 本体设计 (Ontology Design)

1. **本体分支与合并**: 采纳 Palantir 范式——本体支持 git-like 分支与合并，多团队可在分支上并行演进，通过 PR/MR 合并回主分支。FR-002 需扩展为：分支模型 + 合并冲突解决（自动/手动）+ 主分支保护。

2. **Object Type 复用机制（继承 + 组合并存）**: 
   - 继承 (`inherits`)：用于稳定的领域类型层级（如 `Truck inherits Vehicle`），支持属性/动作继承与方法重写 (override)
   - 组合 (`mixins`)：用于横切关注点（`Auditable`, `Versioned`, `Localizable`），所有类型按需混入
   - 语法：`Truck { inherits: [Vehicle]; mixins: [Auditable, Localizable]; ... }`

3. **Action Type 与 Skill 分层**:
   - Action Type (本体层，业务接口)：与 Object Type 同级，参数/返回值引用 Object Type 实例，受 ABAC 控制，随本体版本管理
   - Skill (能力层，工程实现)：在 ToolRegistry (FR-025) 注册，热插拔，无类型约束
   - 关系：Action 1:N Skill——一个 Action 可由 1+ Skill 组合实现
   - Agent 调用 Action Type，平台自动路由到对应 Skill 组合
   - 类比：Action = REST API 契约，Skill = REST API 实现

4. **计算属性 (Function-backed Properties)**:
   - Object Type 可声明 `computed` 属性的依赖表达式（如 `Equipment.riskScore depends_on [status, maintenance_history]`）
   - 运行时由 Graphiti 物化视图层计算（不在本体引擎中执行）
   - 本体仅描述依赖，不包含计算函数
   - 缓存策略：实体变更时增量重算，定时全量校验

5. **Data Health（数据健康，FR-031 新增）**:
   - 与 OPA 分工：OPA 写时拦截（FR-007），Data Health 写后扫描+漂移检测
   - 范围：完整性（NOT NULL/UNIQUE/REFERENCES）+ 一致性（跨实例关系）+ 漂移（历史数据与最新本体不匹配）
   - 规则语言：声明式 JSON/YAML（类似 JSON Schema 约束），不含逻辑代码
   - 执行：定期扫描（@hourly/@daily）+ 按需触发
   - 输出：健康报告（实例级/类型级/总体）+ 通知渠道
   - 不重叠 OPA：OPA 负责访问控制，Data Health 负责数据质量

6. **OntoFlow 目标导向演化**:
   - 本体变更 MUST 关联 `goal` (业务目标) + `rationale` (变更理由) 字段
   - 变更日志可追溯到业务需求
   - 类似 ADR 但针对本体——支持 `goal_id` 引用外部需求管理

7. **多利益相关方协作（PR/MR 评审）**:
   - 不引入独立工作流引擎，使用 git-like PR/MR 评审
   - 评审人配置按 Object Type 分别设定（领域专家/数据架构师/业务负责人）
   - 合并需 ≥1 个指定评审者批准

8. **对象视图 (Object View, Palantir 范式)**:
   - Object View 是独立概念：定义"在不同角色/场景下，Object Type 暴露哪些属性/关系"
   - 与 OPA 属性控制不同：OPA 决定"能否访问"，View 决定"展示什么"
   - 一个 Object Type 可有多个 View（commander-view, operator-view, auditor-view）
   - View 本身受 OPA 保护（仍要走权限校验）

### 本体应用 (Ontology Application)

9. **Agent 与本体关系：严格护栏 (Strict Guardrail)**:
   - 本体是 Agent 的"Type-safe Function Calling"边界
   - Action Type 参数 MUST 通过 OPA 校验才可执行
   - Agent 只能调用本体重登记的 Action Type
   - 优势：调用安全、可审计、可解释
   - 配合 FR-026 语义层：意图→结构化查询→Action Type 强类型映射

(后续 brainstorm 继续追加)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 提供可视化本体设计器，支持实体类型、属性、关系、约束的定义和编辑；本体模型层基于企业架构 BA 最小业务单元生成基础模型，借鉴 Palantir AIP 核心概念（Object Type/Property/Action/Rule 四层结构），不要求严格对齐 Palantir 完整体系
- **FR-002**: 系统 MUST 支持本体版本管理，基于 Graphiti 双时态能力（valid_time + transaction_time），每次变更生成版本记录，支持一键回滚和历史状态快照查询（本体管理引擎负责）
- **FR-003**: 系统 MUST 支持本体实例的 CRUD 操作和批量导入，导入时自动验证属性完整性（本体模型层负责 CRUD，本体管理引擎负责验证）
- **FR-004**: 系统 MUST 支持多模态数据接入（PDF/Word 文档 + 图片 OCR），自动抽取实体更新本体；音视频接入推迟到后续阶段
- **FR-005**: 系统 MUST 支持多 Agent 角色定义和协同调度，基于 OpenHarness Swarm 的 DomainSwarm 实现 OODA 循环编排，支持按意图自动规划 subAgent；采用混合路由策略（规则优先 + LLM 兜底），路由规则及置信度必须基于本体事实而定，不确定时默认路由到 Intelligence Agent；意图识别准确率 > 90%（基于标注测试集测量：测试集包含 ≥ 100 条标注请求，覆盖所有 Agent 路由类别，准确率 = 正确路由数 / 总请求数）（注：此处的意图识别指 Agent 路由意图——将用户请求分发到正确的 Agent，与 FR-016 的用户认知意图识别职责不同）
- **FR-006**: 系统 MUST 展示 Agent 决策过程和推理链路（思维链可视化）
- **FR-007**: 系统 MUST 支持通过 Markdown 编写 OPA 策略，策略可热更新
- **FR-008**: 系统 MUST 基于 ABAC 模型执行细粒度权限校验，所有写操作记录审计日志
- **FR-009**: 系统 MUST 提供沙箱推演环境，基于 OpenHarness 的沙箱机制实现进程级隔离，推演数据与生产环境完全隔离
- **FR-010**: 系统 MUST 支持多方案并行推演和 What-if 参数敏感性分析
- **FR-011**: 系统 MUST 支持自然语言问答，融合本体知识与图谱检索，支持多轮对话；利用 Graphiti 双时态能力支持时序推理（"当时发生了什么"类问题）；图表展示采用混合渲染模式：图表/图谱/地图等轻量交互型可视化前端渲染（G6+Leaflet+ECharts），复杂 3D/热力图等计算密集型可视化后端渲染
- **FR-012**: 系统 MUST 支持工作空间创建与管理，工作空间之间数据完全隔离
- **FR-013**: 系统 MUST 支持场景切换，切换后本体、技能、配置、策略自动切换
- **FR-014**: 系统 MUST 支持 Skill 热插拔，新增 Skill 通过 OpenHarness Skill 管理功能注册和发现，无需重启服务即可生效；当前阶段必须基于 OpenHarness 集成（覆盖 ADR-030 推迟决策）
- **FR-015**: 系统 MUST 支持数据摄入审计，记录数据来源、处理过程和转换规则（注：此为 FR-008 审计日志在数据摄入场景的特化细化，数据摄入审计日志同时满足 FR-008 和 FR-015 的要求）
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
- **FR-027**: 系统 MUST 支持 4 级数据分类（TS 绝密/S 机密/C 内部/U 非密），TS/S 级数据 MUST 加密存储（AES-256-GCM）+ 传输加密（TLS 1.3），密钥通过 KMS 统一管理并支持轮换（注：当前阶段使用配置文件密钥 + 定期轮换，KMS 集成推迟到下一阶段；推迟不影响 AES-256-GCM 加密和 TLS 1.3 传输加密的当前交付）；C 级数据 MUST 传输加密；U 级数据采用标准安全措施
- **FR-028**: 系统 MUST 遵循测试金字塔策略（80% 单元测试 / 15% 集成测试 / 5% E2E 测试），PR 合并前 MUST 通过质量门禁：单元测试覆盖率 > 80%、集成测试 0 失败、Lint 0 error、类型检查 0 error；发版前 MUST 通过 E2E 核心流程测试、性能测试和安全扫描
- **FR-029**: 系统 MUST 采用 OntologyDocument JSON 作为数据流通的统一原子格式，所有数据摄入、导入导出、模块间数据交换 MUST 使用此格式；格式参考 Palantir AIP 本体结构（Object Type/Property/Action/Rule）设计，提供 OWL/RDF 导出能力；不要求与 Palantir AIP 严格对齐；OntologyDocument 版本化：JSON Schema 采用语义化版本（SemVer），major 变更（破坏性）必须提供迁移脚本，minor/patch 变更向后兼容；Schema 版本号记录在 `metadata.schema_version` 字段
- **FR-030**: 系统 MUST 支持国际化（i18n），当前阶段至少支持中英双语，翻译文件按模块拆分；MUST 提供后台管理配置界面管理翻译条目，MUST 支持基于 LLM 模型的自动翻译功能；翻译质量门禁：LLM 自动翻译结果 MUST 经过人工审核或双语对照确认后才可发布；LLM 翻译调用 MUST 通过统一 API 客户端，单次翻译 token 消耗限制在 2000 以内

### Key Entities

- **本体模型层 (Ontology Model)**: 领域知识的形式化定义，基于企业架构 BA 最小业务单元生成基础模型，借鉴 Palantir AIP 核心概念（Object Type/Property/Action/Rule）；包含实体类型、属性、关系、约束；负责实例 CRUD；实例唯一性基于主键属性组合判定
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
- **角色 (Role)**: 用户/Agent 的权限载体，基于 ABAC 模型定义；JWT Token 包含 `role` + `ws_id` + `ws_role` 三元组实现工作空间级隔离；至少包含 admin/commander/analyst/operator/observer 5 种基础角色
- **配置 (Configuration)**: 平台级和模块级配置项的统一管理；按组分类存储，支持表单/JSON 双模式编辑、版本对比与一键回滚（NFR-U04）；变更通过 Hook 系统记录审计
- **语义地图 (Semantic Map)**: 业务规则、逻辑模型、指标体系、业务过程等业务资产的形式化定义；与 OntologyVersion 1:N 关联；提供业务资产的可视化编辑与跨版本查询（FR-200 系列扩展）
- **数据源 (Data Source)**: 多模态数据接入的统一抽象（PDF/Word/图片 OCR），支持运行时动态添加/移除；通过 SourceInfo 描述数据来源（url/title/text/description/publish_date），作为摄入链路统一原子格式

## Technical Assumptions

### 语义层架构（Semantic Layer Architecture）

> **核心设计原则**: 借鉴阿里巴巴 UModel 的 Query Surface 设计模式，在 ODAP 内部构建统一的语义查询层

#### 设计动机

ODAP 存在多条独立的图谱查询路径（SelfCorrectingOrchestrator / DomainSwarm / IntelligenceAgent / UserCognitionEngine / frontend_compat API），缺乏统一抽象导致：
- 意图识别重复实现且质量参差不齐
- KnowledgeNavigator 与 GraphManager 接口断裂
- Agent 安全边界缺失（可直接写图谱）
- 查询结果无结构化类型（全部返回 List[Dict]）

#### 三源查询模型

所有图谱查询 MUST 通过统一查询服务（QueryService）的 4 种查询源访问：

| 查询源 | 读取对象 | 数据源 | 用途 |
|--------|---------|--------|------|
| `.schema` | OMS 类型定义（ObjectTypeDefinition / LinkDefinition / ActionTypeDefinition） | OMS SQLite | 本体类型元数据查询 |
| `.entity` | 运行时实体（OntologyEntity + 四层属性） | GraphManager (Neo4j/Graphiti/NetworkX) | 实例数据查询 |
| `.topo` | 拓扑关系（OntologyRelation + 图遍历） | GraphManager | 关系图谱遍历 |
| `.temporal` | 双时态数据（valid_time + transaction_time） | Graphiti | 历史时序查询 |

#### Agent Safe 默认安全

- 查询工具默认只读（read-only），通过 QueryService 暴露
- 写操作（write_entity / write_relation / write_episode）需显式启用，且 MUST 经过 OPA 策略校验
- OpenHarness PreToolUse Hook 拦截写操作，调用 OPA 检查
- pytest 架构守卫测试：禁止业务模块直接导入 GraphManager（应通过 QueryService）

#### 统一查询服务架构

所有 Agent / 前端 / CLI / MCP Client MUST 通过统一入口访问图谱：

```
Agent / 前端 / CLI / MCP Client
        ↓
QueryService (统一查询服务)
        ↓
    ┌───────────────────────┐
    │  Query Parser + Planner  │ (基于 Semantic Layer 转换)
    └───────────────────────┘
        ↓
  ┌──────────┐ ┌──────────┐ ┌──────────┐
  │SchemaSource│ │EntitySource│ │ TopoSource│ (含 TemporalSource)
  │  (OMS)   │ │(GraphMgr)  │ │ (GraphMgr)│
  └──────────┘ └──────────┘ └──────────┘
```

#### 实施约束

- **禁止绕过**: 任何业务模块 MUST NOT 直接调用 GraphManager 的写方法，必须通过 OpenHarness Tool 接口调用 QueryService
- **架构守卫**: pytest 测试用例 `test_no_direct_graphmanager_import_in_agents` 强制执行边界规则
- **代码审查**: 新增 PR MUST 通过架构守卫测试，CI 流水线拦截违规

### 工作空间隔离硬约束

> **核心声明**: 跨场景图谱数据 MUST 物理隔离，禁止未授权跨场景查询

- **数据隔离**: 工作空间 A 的 Graphiti 实体加 `workspace_id` 标签，所有查询 MUST 自动加 workspace_id 过滤
- **会话隔离**: 会话状态（SessionMemory）MUST 按 workspace_id 路径隔离存储
- **审计隔离**: 审计日志 MUST 记录 workspace_id 字段，跨工作空间审计查询需 admin 权限
- **配置隔离**: 用户-工作空间联合主键，禁止跨工作空间配置覆盖
- **OPA 强制**: 跨工作空间访问 MUST 通过 OPA `policies.workspace.cross_boundary` 策略校验

## Success Criteria *(mandatory)*

### Measurable Outcomes

#### 性能指标（Performance Metrics）

- **SC-001 (性能-问答)**: 问答响应时间 P95 < 3 秒（含 RAG 检索 + LLM 调用），简单图谱查询延迟 P95 < 500ms（基于 100 并发用户负载测试）
- **SC-002 (性能-摄入)**: 摄入 1MB 文档（含 50 个实体 + 100 条关系）端到端延迟 < 10 秒；批量摄入 1000 个实体 < 60 秒
- **SC-003 (性能-图谱)**: Graphiti 实体写入 QPS > 100，实体查询 QPS > 500（图遍历深度 ≤ 3）
- **SC-004 (性能-会话)**: 多轮对话响应延迟 P95 < 4 秒（含短期记忆检索 + 长期记忆按需加载）
- **SC-005 (性能-推演)**: 推演沙箱支持至少 10 个方案并行运行，单次推演平均时长 < 30 秒（基准场景：50 个实体 + 100 条关系 + 5 个事件注入）
- **SC-006 (性能-并发)**: 系统支持 50-200 用户同时在线，核心 API QPS > 200，错误率 < 0.1%

#### 业务验收场景（Business Acceptance）

- **SC-010 (业务-本体设计)**: 领域专家可在 30 分钟内完成一个包含 5 种实体类型 + 10 种关系 + 20 条约束的本体设计
- **SC-011 (业务-版本回滚)**: 本体版本回滚在 5 秒内完成，关联逻辑（语义地图/业务规则/逻辑模型/指标）自动更新
- **SC-012 (业务-意图识别)**: Agent 路由意图识别准确率 > 90%（测试集：≥ 100 条标注请求，覆盖所有 Agent 路由类别），任务分发延迟 < 1 秒
- **SC-013 (业务-策略热更)**: OPA 策略热更新在 30 秒内生效，无需重启服务；策略编译失败时保持旧策略（fail-close）
- **SC-014 (业务-数据隔离)**: 工作空间 W1 用户尝试访问 W2 数据时，OPA 100% 拦截，审计日志 100% 记录；数据隔离可证伪测试通过
- **SC-015 (业务-决策推荐)**: Commander Agent 触发决策推荐时，生成 ≥ 3 个候选方案，每个方案输出 4 维度评分（成本/收益/风险/置信度，0-100 分），Top 1 方案可解释
- **SC-016 (业务-多轮对话)**: 多轮对话（>10 轮）上下文保持率 > 95%；引用前文实体/意图的准确率 > 90%
- **SC-017 (业务-场景导入导出)**: 完整场景包（含本体 + 技能 + 配置 + 测试数据）导出耗时 < 30 秒（基准 5MB 包），导入成功率 > 99%

#### 质量指标（Quality Metrics）

- **SC-020 (质量-测试)**: 单元测试覆盖率 > 80%，集成测试 0 失败，E2E 核心流程 100% 通过
- **SC-021 (质量-审计)**: 100% 写操作有审计日志记录（actor/action/resource/result/timestamp），支持时间线展示和溯源
- **SC-022 (质量-架构)**: 架构守卫测试 100% 通过——业务模块 MUST NOT 直接调用 GraphManager 写方法，违例 0 容忍
- **SC-023 (质量-Lint)**: PR 合并前 Lint 0 error，类型检查 0 error
- **SC-024 (质量-文档)**: 100% API 有 OpenAPI/TypeScript 类型定义，100% 模块有 README 文档
- **SC-025 (质量-可用性)**: 系统可用性 99.9%（SLA），平均故障恢复时间 (MTTR) < 5 分钟

#### 降级与边界（Degradation & Boundary）

- **SC-030 (降级-LLM)**: LLM 服务不可用时（API 超时/限流/宕机），意图识别和问答 MUST 返回明确错误提示，MUST NOT 静默失败或返回空结果
- **SC-031 (降级-Neo4j)**: Neo4j 宕机时，所有图谱相关功能 MUST 降级为不可用并返回明确错误；SQLite 存储数据仍可访问；MUST NOT 使用 NetworkX 回退以避免数据不一致
- **SC-032 (降级-批量导入)**: 批量导入部分失败时 MUST 保留成功记录，返回部分成功报告（成功数/失败数/失败详情），MUST NOT 因部分失败回滚全部
- **SC-033 (降级-推演超时)**: 推演沙箱资源耗尽时（内存/时间超限）MUST 自动终止推演，返回已计算的部分结果+超时提示
- **SC-034 (降级-并发)**: 推演并行方案上限 10 个，超过 MUST 排队等待（FIFO）；问答并发上限 50，超出排队

## Glossary

### 核心架构术语

- **ODAP (Ontology-Driven Analysis & Decision Platform)**: 本体驱动分析决策平台，项目正式名称
- **OADP (Observe-Analyze-Decide-Perform)**: 业务语义闭环（感知-理解-决策-执行），区别于传统 OODA
- **OntologyDocument**: 数据流通的统一原子格式（JSON），包含 ObjectType/Property/Action/Rule 四层结构，参考 Palantir AIP 设计
- **QueryService**: 统一查询服务，整合分散的图谱查询路径，支持 4 种查询源（schema/entity/topo/temporal）
- **Agent Safe**: Agent 默认安全策略——查询工具只读，写操作需 OPA 校验

### 知识图谱术语

- **Graphiti**: 双时态知识图谱（valid_time + transaction_time），支持时序推理和历史回溯
- **OMS (Ontology Metadata Service)**: 本体元数据服务，Palantir AIP 风格的 ObjectTypeDefinition 管理体系
- **SemanticMap (语义地图)**: 业务资产（业务规则/逻辑模型/指标体系/业务过程）的形式化定义
- **Episode**: Graphiti 中的事件记录单元，每次摄入产生一个或多个 Episode

### 记忆与上下文术语

- **SessionMemory (会话记忆)**: 基于 OpenHarness Memory Plugin 的记忆管理
  - **短期记忆 (Short-term Memory)**: 对话上下文，滑动窗口 N 轮
  - **工作记忆 (Working Memory)**: 当前任务状态，任务级生命周期
  - **长期记忆 (Long-term Memory)**: 持久化到 Graphiti，跨会话保留
- **Semantic Layer (语义层)**: Intent → StructuredQuery → Agent Task 的结构化映射层

### 安全与治理术语

- **OPA (Open Policy Agent)**: 策略治理引擎，支持 ABAC 细粒度权限控制
- **ABAC (Attribute-Based Access Control)**: 基于属性的访问控制模型
- **JWT (JSON Web Token)**: 访问凭证，Payload 包含 `role` + `ws_id` + `ws_role` 三元组
- **4 级数据分类**: TS 绝密 / S 机密 / C 内部 / U 非密，对应不同加密策略
- **fail-close**: 策略加载失败时保持旧策略运行，不暴露错误细节给非管理员

### 集成与协议术语

- **MCP (Model Context Protocol)**: 外部系统集成协议，遵循 v1.0 标准
- **OpenHarness**: Agent 基础设施，提供 Swarm 协调、Tool 接口、Memory Plugin、Hook 机制
- **Hook**: 生命周期钩子，Pre/Post Hook 拦截 Agent 执行
- **ToolRegistry**: 统一工具注册表，所有可调用能力（Skill/QueryService/MCP）注册为 Tool

### 测试与质量术语

- **测试金字塔**: 80% 单元测试 + 15% 集成测试 + 5% E2E 测试
- **架构守卫 (Architecture Guard)**: 通过 pytest 强制执行架构边界（禁止绕过 QueryService）
- **质量门禁**: 单元测试覆盖率 > 80%、集成测试 0 失败、Lint 0 error、类型检查 0 error

### 前端与可视化术语

- **6 断点响应式**: 移动优先策略下的 6 个断点（xs/sm/md/lg/xl/xxl）
- **5 级组件体系**: L1 原子 → L2 分子 → L3 组织 → L4 模板 → L5 页面
- **混合渲染模式**: 轻量交互型可视化前端渲染（G6+Leaflet+ECharts），计算密集型可视化后端渲染

### 业务领域术语

- **推演沙箱 (Simulation Sandbox)**: 隔离的模拟推演环境，进程级隔离，推演数据与生产完全隔离
- **决策推荐 (Decision Recommendation)**: 基于 Graphiti RAG 增强推理的方案推荐系统
- **事件模拟器 (Event Simulator)**: 推演引擎的上游数据供应商，支持自动/手动事件生成
- **What-if 分析**: 参数敏感性分析，识别关键影响参数



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
