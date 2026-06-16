# Feature Specification: 数据采集功能优化

**Feature Branch**: `005-data-collection-opt`

**Created**: 2026-06-13

**Status**: Draft

**Input**: User description: "数据采集功能优化评估，包括现在agent部分、有哪些skill、联网检索或爬虫功能是什么？请评估实现的合理性和效果，爬虫爬取是否可使用BrowserAct等Skill"

## 现状评估

### 当前 Agent 架构

ODAP 采用三层 Agent 编排体系，由 `AgentOrchestrator` 统一分派：

| Agent 类型 | 类名 | 模式 | 职责 |
|------------|------|------|------|
| DomainSwarm | `DomainSwarm` | OODA 多 Agent 协同 | Observe→Orient→Decide→Act 循环 |
| IntelligenceAgent | `IntelligenceAgent` | LLM ReAct | 最多 5 轮推理+工具调用 |
| GraphitiAgentLoop | OpenHarness v2 | Harness 适配 | 外部框架集成 |

**关键发现**：所有 Agent 的工具调用均基于 `SKILL_CATALOG`，而当前 40+ 个 Skill **全部仅查询内部图谱数据**（GraphManager/Neo4j/NetworkX），**没有任何联网搜索或网页爬取能力**。

### 当前 Skill 清单（10 类 40+ 个）

| 类别 | Skill 数量 | 能力范围 | 联网能力 |
|------|-----------|---------|---------|
| intelligence | 2 | 雷达搜索、领域态势分析 | 无 |
| analysis | 6 | 实体/事件/力量/武器/基础设施/态势分析 | 无 |
| operations | 2 | 攻击目标、指挥部队（需 OPA 权限） | 无 |
| recommendation | 4 | 打击目标/任务规划/兵力部署/风险推荐 | 无 |
| planning | 4 | 计划创建/工作流执行/验证/资源估算 | 无 |
| policy | 10 | 策略模拟/版本/导入导出/权限/历史 | 无 |
| computation | 4 | 距离/预测/威胁/毁伤计算 | 无 |
| visualization | 4 | 地图叠加/任务摘要/报告/态势感知 | 无 |
| task_management | 6 | 任务预留/查询/取消/状态管理 | 无 |
| agent_tools | 9 | 图谱查询/三国时间线/势力/人物/事件 | 无 |

### 当前联网检索/爬虫功能

联网检索和网页爬取功能**仅存在于数据摄入（Ingest）模块**中，**未注册为 Agent Skill**：

| 组件 | 位置 | 能力 | 局限 |
|------|------|------|------|
| WebScraper (infra) | `odap/infra/utils/web_scraper.py` | requests + BeautifulSoup 抓取 | 无法处理 JS 渲染页面 |
| WebScraper (ingestion) | `odap/biz/core/ontology/design/ingestion_split/web_scraper.py` | 同上，与摄入流程集成 | 同上 |
| SearchService | `odap/biz/core/ontology/design/services/search_service.py` | Tavily→SerpAPI→DuckDuckGo→Mock 四级降级 | 仅搜索，不爬取 |
| NewsIngester | `odap/biz/core/ontology/design/ingestion_split/news_ingester.py` | 新闻搜索 + LLM 归纳 | 仅新闻，需 API Key |
| FreeNewsIngester | `odap/biz/core/ontology/design/ingestion_split/free_news_ingester.py` | 免费新闻抓取 | 规则提取，精度低 |
| WebFetchTool | `openharness/src/openharness/tools/web_fetch_tool.py` | httpx 抓取 + HTML 转文本 | 无浏览器自动化 |
| WebSearchTool | `openharness/src/openharness/tools/web_search_tool.py` | DuckDuckGo HTML 搜索 | 仅搜索，不爬取 |

### 关键能力缺口

| 缺口 | 说明 |
|------|------|
| Agent 无法联网 | Agent 的 SKILL_CATALOG 中无任何联网工具，只能查询内部图谱 |
| 无 JS 渲染能力 | 所有爬取基于 HTTP 请求 + HTML 解析，无法处理 SPA/动态页面 |
| 无浏览器自动化 | 无 Playwright/Selenium/Puppeteer，无法处理登录/交互场景 |
| 搜索未注册为 Skill | SearchService/Tavily 仅在 Ingest 流程中可用，Agent 无法调用 |
| 无定时/增量抓取 | 无 Cron/Scheduler 机制，无增量去重 |
| 无深度爬取 | 仅单页抓取，无站内链接跟踪 |

### BrowserAct 评估

BrowserAct 是基于浏览器自动化的 AI Agent 网页交互框架，核心循环为"观察→推理→动作→观察"（ReAct 模式），由 LLM 驱动 Playwright 执行浏览器操作。类似工具包括 browser-use、Crawl4AI、FireCrawl 等。

| 工具 | JS 渲染 | AI 集成 | 部署复杂度 | 适合场景 |
|------|:-------:|:-------:|:----------:|----------|
| BrowserAct | Yes | 原生 | 中 | 复杂网页交互任务 |
| browser-use | Yes | 原生 | 中 | AI Agent 深度集成 |
| Crawl4AI | Yes | LLM 友好 | 低 | 结构化数据提取 |
| FireCrawl | Yes | API | 极低 | 快速集成、无部署 |
| Playwright | Yes | 需封装 | 低 | 精确控制、测试 |

**结论**：BrowserAct 类工具**可以且应该**作为 Skill 集成到 ODAP，但需分阶段实施。推荐优先集成 Crawl4AI（轻量级 JS 渲染），再逐步引入 browser-use/BrowserAct 级别的 AI 浏览器自动化。

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent 主动联网搜索 (Priority: P1)

作为分析人员，我在与 Agent 对话时，希望 Agent 能够主动联网搜索相关信息，而不是仅依赖内部图谱数据。当用户提问涉及外部实时信息时，Agent 应自动识别并调用联网搜索工具获取最新数据。

**Why this priority**: 这是当前系统最大的能力空白。Agent 目前完全无法联网，所有 40+ 个 Skill 仅查询内部图谱，严重限制了 Agent 的实用性。

**Independent Test**: 可以通过向 Agent 提问一个需要联网才能回答的问题（如"今天某领域的最新动态"），验证 Agent 是否能调用搜索工具并返回实时结果。

**Acceptance Scenarios**:

1. **Given** Agent 处于对话状态，**When** 用户提问需要实时信息的问题，**Then** Agent 自动识别联网需求并调用搜索工具返回结果
2. **Given** 搜索服务不可用（API Key 缺失），**When** Agent 尝试联网搜索，**Then** 系统优雅降级，返回提示信息而非报错
3. **Given** Agent 已获取搜索结果，**When** 结果需要与内部图谱数据关联分析，**Then** Agent 能将外部数据与内部知识结合生成综合分析

---

### User Story 2 - JavaScript 渲染页面爬取 (Priority: P2)

作为数据分析师，我希望系统能够爬取 JavaScript 渲染的网页内容（如 SPA 应用、动态加载页面），而不仅仅是静态 HTML 页面，从而获取更完整和准确的数据。

**Why this priority**: 当前 WebScraper 仅支持静态 HTML 解析，大量现代网站使用 JS 渲染，导致数据采集不完整。这是数据质量的核心瓶颈。

**Independent Test**: 可以通过爬取一个已知的 JS 渲染页面（如 React SPA），验证系统是否能获取动态加载的内容。

**Acceptance Scenarios**:

1. **Given** 目标网页使用 JavaScript 动态渲染内容，**When** 用户通过摄入界面提交该 URL，**Then** 系统能正确获取并提取动态加载的文本内容
2. **Given** 目标网页需要滚动加载更多内容，**When** 系统爬取该页面，**Then** 能获取首屏及滚动后的全部内容
3. **Given** JS 渲染页面加载超时，**When** 爬取操作超过合理等待时间，**Then** 系统返回已获取的部分内容并标记为不完整

---

### User Story 3 - AI 驱动的浏览器自动化采集 (Priority: P3)

作为高级用户，我希望 Agent 能够像人类一样操作浏览器完成复杂的数据采集任务，包括登录认证网站、多步表单交互、点击导航等，从而采集需要交互才能获取的数据。

**Why this priority**: 这是最复杂但价值最高的场景，适用于需要登录、多步操作才能获取数据的场景。依赖 P1/P2 的基础设施，应最后实施。

**Independent Test**: 可以通过让 Agent 完成一个需要登录后才能访问的页面数据采集任务，验证浏览器自动化能力。

**Acceptance Scenarios**:

1. **Given** 目标网站需要登录认证，**When** 用户提供登录凭据并请求采集，**Then** Agent 能自动完成登录并采集目标数据
2. **Given** 数据需要多步操作才能获取（如搜索→筛选→翻页），**When** 用户描述采集目标，**Then** Agent 自动规划并执行多步操作
3. **Given** 浏览器操作过程中出现异常（如验证码、页面错误），**When** Agent 遇到阻碍，**Then** 系统能识别异常并通知用户，而非无限等待

---

### User Story 4 - 统一数据采集 Skill 注册 (Priority: P1)

作为系统管理员，我希望所有数据采集能力（搜索、爬取、浏览器自动化）都注册为标准 Skill，使 Agent 能通过统一的 Skill 调用机制使用这些能力，同时支持 OPA 权限控制和健康监控。

**Why this priority**: 这是架构层面的基础要求。没有统一的 Skill 注册，Agent 无法调用任何新增的数据采集能力。与 P1-联网搜索同等重要。

**Independent Test**: 可以通过 Agent 的工具列表验证新增的搜索/爬取 Skill 是否正确注册，并通过 SkillExecutorV2 调用验证功能。

**Acceptance Scenarios**:

1. **Given** 新的数据采集 Skill 已开发完成，**When** 将其注册到 SkillRegistryV2，**Then** Agent 能通过 SKILL_CATALOG 发现并调用该 Skill
2. **Given** 数据采集 Skill 涉及外部网络访问，**When** Agent 调用该 Skill，**Then** OPA 策略能正确控制访问权限（如域名白名单）
3. **Given** 数据采集 Skill 执行失败，**When** SkillExecutorV2 检测到异常，**Then** 系统按重试策略（最多 3 次）执行，失败后标记 Skill 状态为 degraded

---

### User Story 5 - 摄入界面增强 (Priority: P2)

作为平台用户，我希望在前端摄入界面中能选择更丰富的数据采集方式（如智能爬取、深度爬取、浏览器自动化采集），并实时查看采集进度和结果预览。

**Why this priority**: 前端是用户直接交互的入口，增强摄入界面能让新能力真正可被用户使用。

**Independent Test**: 可以通过前端摄入面板验证新增的采集方式是否可选，并测试采集流程的端到端体验。

**Acceptance Scenarios**:

1. **Given** 用户打开摄入面板，**When** 查看可用的摄入方式，**Then** 能看到新增的"智能爬取"和"深度采集"选项
2. **Given** 用户选择了智能爬取方式，**When** 提交 URL 后，**Then** 界面实时显示采集进度（页面加载、内容提取、数据处理）
3. **Given** 采集完成，**When** 用户查看结果，**Then** 能预览采集到的内容并确认是否导入

---

### Edge Cases

- 当目标网站返回反爬机制（如 Cloudflare 验证、频率限制）时，系统如何处理？
- 当联网搜索返回大量结果时，系统如何筛选和排序？
- 当浏览器自动化任务执行时间过长（超过 5 分钟）时，系统如何超时处理？
- 当多个 Agent 同时请求联网搜索时，系统如何管理并发和资源？
- 当采集到的外部内容包含恶意脚本或误导性信息时，系统如何安全处理？
- 当 MCP Server 中的浏览器自动化工具不可用时，Agent 如何降级？

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 将联网搜索能力注册为 Agent 可调用的 Skill，使 Agent 能在对话中主动搜索外部信息
- **FR-002**: 系统 MUST 支持多搜索引擎降级链（Tavily→SerpAPI→DuckDuckGo→Mock），确保搜索服务的可用性
- **FR-003**: 系统 MUST 支持爬取 JavaScript 渲染的网页内容，获取动态加载的数据
- **FR-004**: 系统 MUST 将网页爬取能力注册为 Agent 可调用的 Skill，使 Agent 能主动爬取指定 URL 的内容
- **FR-005**: 系统 MUST 通过 OPA 策略控制数据采集 Skill 的访问权限，包括可访问的域名范围和操作类型
- **FR-006**: 系统 MUST 在数据采集 Skill 执行失败时支持重试机制（最多 3 次），并标记 Skill 健康状态
- **FR-007**: 系统 MUST 对外部采集的内容标记来源和可信度，区分内部图谱数据与外部采集数据
- **FR-008**: 系统 SHOULD 支持 AI 驱动的浏览器自动化采集，处理需要登录、多步交互的复杂采集场景
- **FR-009**: 系统 SHOULD 支持通过 MCP 协议集成外部浏览器自动化工具（如 BrowserAct/browser-use），实现可插拔的工具扩展
- **FR-010**: 系统 SHOULD 在前端摄入界面提供新增采集方式的入口，支持智能爬取和深度采集
- **FR-011**: 系统 MUST 对采集到的外部内容进行安全过滤，防止恶意脚本注入
- **FR-012**: 系统 MUST 对浏览器自动化任务设置超时限制，防止资源无限占用

### Key Entities

- **DataCollectionSkill**: 数据采集技能，继承 BaseSkill，包含搜索/爬取/浏览器自动化三种类型，关联 SkillMetadata（含 danger_level 和 OPA 策略）
- **CollectionTask**: 采集任务，记录采集目标（URL/搜索词）、采集类型、状态、结果、来源标记、可信度评分
- **CollectionResult**: 采集结果，包含原始内容、提取的结构化数据、来源 URL、采集时间戳、可信度标记
- **BrowserSession**: 浏览器会话（仅浏览器自动化场景），管理浏览器实例生命周期、Cookie/Session、操作历史

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Agent 能在对话中成功调用联网搜索 Skill 并返回实时搜索结果，搜索响应时间在 5 秒以内
- **SC-002**: 系统能正确爬取 JavaScript 渲染页面的核心内容，内容完整度比现有 WebScraper 提升 50% 以上
- **SC-003**: 数据采集 Skill 注册后，Agent 能在工具列表中发现并正确调用，调用成功率不低于 95%
- **SC-004**: OPA 策略能正确拦截未授权的域名访问请求，拦截准确率 100%
- **SC-005**: 搜索服务在主引擎不可用时，能在 2 秒内自动降级到备用引擎，用户无感知
- **SC-006**: 浏览器自动化任务在超时后能正确释放资源，无内存泄漏
- **SC-007**: 外部采集内容均标记来源和可信度，用户能清晰区分内部数据与外部数据

## Assumptions

- 用户有稳定的互联网连接，能访问外部搜索 API 和目标网站
- Tavily API Key 为可选配置，系统需在无 API Key 时降级到免费方案
- 浏览器自动化功能部署在独立容器/进程中，避免影响主服务稳定性
- 现有 MCP 适配器架构（MCPServerManagerV2 + MCPToolBridge）可用于集成外部浏览器工具
- 现有 SkillRegistryV2 和 SkillExecutorV2 框架可直接复用，无需重新设计注册机制
- 第一阶段（P1）仅实现搜索 Skill 注册和 JS 渲染爬取，浏览器自动化（P3）为后续迭代
- 外部采集内容的安全过滤遵循现有 WebFetchTool 的 `[External content]` 标记模式
- 域名白名单策略由 OPA 管理，默认允许常见新闻/资讯站点
