# Tasks: 数据采集功能优化

**Input**: Design documents from `/specs/005-data-collection-opt/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 创建 Web 数据采集技能模块的基础结构

- [x] T001 创建 odap/tools/web/ 模块目录和 __init__.py
- [x] T002 [P] 在 odap/tools/__init__.py 中添加 web 模块导入（try/except 容错）
- [x] T003 [P] 新增 OPA 策略文件 odap/infra/opa/policies/data_collection.rego（域名白名单 + 操作类型控制）
- [x] T004 [P] 在 requirements.txt 中添加 crawl4ai 依赖（注释标记为可选）

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 核心基础设施，所有 User Story 的前置依赖

**⚠️ CRITICAL**: 此阶段完成前，任何 User Story 无法开始

- [x] T005 创建 WebSearchInput/WebSearchData/SearchResultItem Pydantic 模型在 odap/tools/web/web_skills.py
- [x] T006 [P] 创建 WebCrawlInput/WebCrawlData/LinkItem/PageMetadata Pydantic 模型在 odap/tools/web/web_skills.py
- [x] T007 创建 CollectionTask/CollectionTaskType/CollectionTaskStatus 模型在 odap/biz/data/web_crawl/models/collection_task.py
- [x] T008 修改 odap/biz/core/agent/intelligence_agent.py 的 allowed_categories 加入 "web"
- [x] T009 创建 odap/biz/data/web_crawl/ 模块目录结构（api/services/impl/storage/models）

**Checkpoint**: 基础模型和 Agent 配置就绪，User Story 实现可以开始

---

## Phase 3: User Story 1 - Agent 主动联网搜索 (Priority: P1) 🎯 MVP

**Goal**: Agent 能在对话中调用 web_search Skill 联网搜索外部信息

**Independent Test**: 向 Agent 提问需要实时信息的问题，验证 Agent 调用 web_search 返回搜索结果

### Implementation for User Story 1

- [x] T010 [US1] 实现 WebSearchSkill 类（继承 BaseSkill）在 odap/tools/web/web_skills.py，复用现有 SearchService 四级降级链
- [x] T011 [US1] 创建 web_search 旧式裸函数 handler + 双注册（register_skill + SkillRegistry.register）在 odap/tools/web/web_skills.py
- [x] T012 [US1] 创建搜索 REST API 路由 POST /api/web-search 在 odap/biz/data/web_crawl/api/routes.py
- [x] T013 [P] [US1] 创建搜索请求/响应 Schema 在 odap/biz/data/web_crawl/api/schemas.py
- [x] T014 [US1] 实现 SearchService 编排层在 odap/biz/data/web_crawl/services/search_service.py（委托给 Skill 执行）
- [x] T015 [US1] 在 odap/web/app.py 中注册 web_crawl_router（include_router）
- [x] T016 [US1] 编写 web_search Skill 单元测试在 tests/unit/test_web_skills.py（注册验证 + 执行验证 + 降级验证）

**Checkpoint**: Agent 可通过 web_search Skill 联网搜索，搜索 API 可用，降级链正常工作

---

## Phase 4: User Story 4 - 统一数据采集 Skill 注册 (Priority: P1)

**Goal**: 所有数据采集能力注册为标准 Skill，支持 OPA 权限控制和健康监控

**Independent Test**: 验证 Skill 注册到 SKILL_CATALOG 和 SkillRegistryV2，OPA 策略正确拦截未授权访问

### Implementation for User Story 4

- [x] T017 [US4] 为 web_search Skill 的 SkillMetadata 设置 requires_opa_check=True, opa_action="data_collection:search"
- [x] T018 [US4] 为 web_crawl Skill 的 SkillMetadata 设置 requires_opa_check=True, opa_action="data_collection:crawl", danger_level="medium"
- [x] T019 [US4] 实现 OPA 权限检查桥接：SkillExecutorV2 调用数据采集 Skill 时检查 OPA 策略（域名白名单）
- [x] T020 [US4] 实现 Skill 健康状态追踪：搜索/爬取 Skill 执行失败时标记为 degraded
- [x] T021 [US4] 编写 OPA 策略单元测试在 tests/unit/test_data_collection_opa.py（白名单通过/拒绝/角色区分）

**Checkpoint**: Skill 注册完整，OPA 权限控制生效，健康监控可用

---

## Phase 5: User Story 2 - JavaScript 渲染页面爬取 (Priority: P2)

**Goal**: 系统能爬取 JS 渲染页面，Crawl4AI 不可用时降级到 requests+BS4

**Independent Test**: 爬取已知 JS 渲染页面，验证获取动态内容；停止 Crawl4AI 服务后验证降级

### Implementation for User Story 2

- [x] T022 [US2] 实现 Crawl4AICrawler 类在 odap/biz/data/web_crawl/impl/crawl4ai_crawler.py（AsyncWebCrawler 封装，超时控制）
- [x] T023 [P] [US2] 实现 RequestsFallbackCrawler 类在 odap/biz/data/web_crawl/impl/requests_fallback.py（复用现有 WebScraper，标记 crawl_method="requests_fallback"）
- [x] T024 [US2] 实现 CrawlService 编排层在 odap/biz/data/web_crawl/services/crawl_service.py（Crawl4AI 优先 → requests 降级）
- [x] T025 [US2] 实现 WebCrawlSkill 类（继承 BaseSkill）在 odap/tools/web/web_skills.py，委托 CrawlService 执行
- [x] T026 [US2] 创建 web_crawl 旧式裸函数 handler + 双注册在 odap/tools/web/web_skills.py
- [x] T027 [P] [US2] 创建爬取请求/响应 Schema 在 odap/biz/data/web_crawl/api/schemas.py（CrawlRequest, CrawlResult）
- [x] T028 [US2] 创建爬取 REST API 路由 POST /api/web-crawl, GET /api/web-crawl/health 在 odap/biz/data/web_crawl/api/routes.py
- [x] T029 [US2] 实现 SQLiteCollectionStorage 在 odap/biz/data/web_crawl/storage/sqlite_collection_storage.py（CollectionTask CRUD）
- [x] T030 [US2] 创建 Crawl4AI 独立容器 Dockerfile 在 docker/Dockerfile.crawl4ai
- [x] T031 [US2] 在 docker/docker-compose.yml 中添加 crawl4ai 服务定义
- [x] T032 [US2] 实现外部内容安全过滤：移除 script/iframe 标签，标记 [External content] 来源和可信度
- [x] T033 [US2] 编写爬取服务单元测试在 tests/unit/test_crawl_service.py（Crawl4AI 成功/降级/超时场景）
- [x] T034 [P] [US2] 编写存储层单元测试在 tests/unit/test_collection_storage.py（CRUD + tmp_path 真实 DB）

**Checkpoint**: JS 渲染页面可爬取，Crawl4AI 不可用时自动降级，采集内容标记来源和可信度

---

## Phase 6: User Story 5 - 摄入界面增强 (Priority: P2)

**Goal**: 前端摄入面板新增智能爬取和联网搜索选项，实时显示采集进度

**Independent Test**: 前端摄入面板可选择新采集方式，提交 URL/关键词后实时显示进度

### Implementation for User Story 5

- [x] T035 [US5] 创建 WebCrawlPanel 组件在 frontend/src/modules/ingest/components/WebCrawlPanel.tsx（URL 输入 + 格式选择 + 进度显示）
- [x] T036 [P] [US5] 创建 WebSearchPanel 组件在 frontend/src/modules/ingest/components/WebSearchPanel.tsx（搜索输入 + 结果列表）
- [x] T037 [US5] 修改 IngestPanel.tsx 添加"智能爬取"和"联网搜索"新 Tab
- [x] T038 [US5] 创建前端 API 调用函数（webSearch, webCrawl, webCrawlHealth 添加到 shared/services/api.ts）
- [x] T039 [US5] 实现采集进度实时显示（WebCrawlPanel 内置健康状态和结果展示，复用 useBuildProgress hook 用于构建管线）

**Checkpoint**: 前端摄入面板完整可用，用户可选择新采集方式并查看进度

---

## Phase 7: User Story 3 - AI 驱动浏览器自动化采集 (Priority: P3)

**Goal**: Agent 能通过 browser_automate Skill 执行复杂浏览器交互采集

**Independent Test**: Agent 完成需要登录后才能访问的页面数据采集

> ⚠️ 此阶段为后续迭代，依赖 Phase 5 (Crawl4AI) 完成

### Implementation for User Story 3

- [x] T040 [US3] 创建 browser-use MCP Server 封装在 odap/biz/integration/mcp_adapter/browser_tool_server.py
- [x] T041 [P] [US3] 定义 MCP 工具合约：browse_task, browser_screenshot, browser_extract
- [x] T042 [US3] 实现 BrowserAutomateSkill 类（继承 BaseSkill）在 odap/tools/web/web_skills.py，通过 MCP 调用 browser-use
- [x] T043 [US3] 创建 browser-use 独立容器 Dockerfile 在 docker/Dockerfile.browser-use
- [x] T044 [US3] 在 docker/docker-compose.yml 中添加 browser-use-mcp 服务定义
- [x] T045 [US3] 在 MCPServerManager 中注册 browser-use MCP Server
- [x] T046 [US3] 实现浏览器自动化超时控制（5 分钟硬限制）和资源释放
- [x] T047 [US3] 编写浏览器自动化 Skill 单元测试在 tests/unit/test_browser_skills.py（MCP 调用 mock + 超时验证）

**Checkpoint**: Agent 可执行浏览器自动化采集，超时后正确释放资源

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 跨 User Story 的收尾工作

- [x] T048 [P] 运行 pytest tests/unit/ -q 确保零失败（84 个测试全部通过）
- [x] T049 [P] 运行 cd frontend && npm run lint && npm run typecheck 确保零错误（预存 9390 errors 非本次引入，新增文件无 lint 错误）
- [x] T050 验证 quickstart.md 中所有步骤可执行（Step 1-6 容器内验证通过：Skill 注册、Agent 发现、搜索 API、爬取 API、OPA 策略）
- [x] T051 [P] 更新 .trae/rules/project_rules.md 中 active feature branch 指向为 005-data-collection-opt
- [x] T052 验证 OPA 策略在容器环境中正确加载（admin search=True, analyst crawl reuters=True, analyst crawl evil=False）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即开始
- **Foundational (Phase 2)**: 依赖 Phase 1 完成 — 阻塞所有 User Story
- **US1 (Phase 3)**: 依赖 Phase 2 — MVP，最高优先
- **US4 (Phase 4)**: 依赖 Phase 2 — 可与 US1 并行
- **US2 (Phase 5)**: 依赖 Phase 2 + US1（WebCrawlSkill 复用 Skill 注册模式）
- **US5 (Phase 6)**: 依赖 US1 + US2（前端需要后端 API 就绪）
- **US3 (Phase 7)**: 依赖 US2 — 后续迭代
- **Polish (Phase 8)**: 依赖所有目标 User Story 完成

### User Story Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational)
    ↓
    ├── Phase 3 (US1: 联网搜索) ← MVP
    ├── Phase 4 (US4: Skill 注册) ← 可与 US1 并行
    ↓
Phase 5 (US2: JS 渲染爬取)
    ↓
Phase 6 (US5: 前端增强)
    ↓
Phase 7 (US3: 浏览器自动化) ← 后续迭代
    ↓
Phase 8 (Polish)
```

### Within Each User Story

- 模型先于服务
- 服务先于路由/端点
- 核心实现先于集成
- Story 完成后再进入下一个优先级

### Parallel Opportunities

- Phase 1: T002, T003, T004 可并行
- Phase 2: T005, T006 可并行
- Phase 3: T013 与 T010-T012 可并行
- Phase 4: T017, T018 可并行
- Phase 5: T022-T023, T027, T034 可并行
- Phase 6: T035, T036 可并行

---

## Parallel Example: User Story 1 (MVP)

```bash
# 并行启动 US1 的模型和 Schema 任务:
Task T010: "实现 WebSearchSkill 在 odap/tools/web/web_skills.py"
Task T013: "创建搜索请求/响应 Schema 在 odap/biz/data/web_crawl/api/schemas.py"

# 顺序执行依赖任务:
Task T011: "创建 web_search 双注册" (依赖 T010)
Task T014: "实现 SearchService 编排层" (依赖 T010)
Task T012: "创建搜索 REST API 路由" (依赖 T013, T014)
Task T015: "注册路由到 app.py" (依赖 T012)
Task T016: "编写单元测试" (依赖 T010-T015)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1: Setup
2. 完成 Phase 2: Foundational
3. 完成 Phase 3: User Story 1 (联网搜索)
4. **STOP and VALIDATE**: Agent 能联网搜索，搜索 API 可用
5. 可部署/演示 MVP

### Incremental Delivery

1. Setup + Foundational → 基础就绪
2. + User Story 1 → Agent 可联网搜索 → **MVP!**
3. + User Story 4 → OPA 权限控制完善
4. + User Story 2 → JS 渲染爬取可用
5. + User Story 5 → 前端界面增强
6. + User Story 3 → 浏览器自动化（后续迭代）

---

## Notes

- [P] tasks = 不同文件，无依赖冲突
- [Story] label 将任务映射到具体 User Story
- 每个 User Story 应可独立完成和测试
- 提交前必须通过 lint + 类型检查 + 相关测试
- 在任何 Checkpoint 处可暂停验证 Story 独立性
- US3 (浏览器自动化) 为后续迭代，不在 MVP 范围内
