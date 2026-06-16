# Implementation Plan: 数据采集功能优化

**Branch**: `005-data-collection-opt` | **Date**: 2026-06-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-data-collection-opt/spec.md`

## Summary

为 ODAP 平台的 Agent 系统新增联网搜索和网页爬取能力。当前 40+ 个 Skill 全部仅查询内部图谱数据，Agent 无法获取外部实时信息。本功能将：1) 将现有 SearchService 封装为 `web_search` Skill 注册到 SKILL_CATALOG；2) 集成 Crawl4AI 实现 JS 渲染页面爬取，注册为 `web_crawl` Skill；3) 通过 OPA 策略控制域名访问权限；4) 增强前端摄入界面支持新采集方式。

## Technical Context

**Language/Version**: Python 3.10+ (后端), TypeScript (前端)

**Primary Dependencies**: FastAPI, Pydantic v2, Crawl4AI (新增), browser-use (P3 新增), Ant Design 6

**Storage**: SQLite (CollectionTask 持久化), Neo4j (采集结果写入图谱)

**Testing**: pytest (后端), Vitest (前端)

**Target Platform**: Linux server (Podman 容器化部署)

**Project Type**: Web service (前后端分离)

**Performance Goals**: 搜索响应 < 5s, 爬取响应 < 30s, 降级切换 < 2s

**Constraints**: 容器内存 ≥ 2GB (Crawl4AI), 并发爬取 ≤ 3, 浏览器自动化超时 ≤ 5min

**Scale/Scope**: 单实例部署, 10 并发用户

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Design Check

| 原则 | 合规 | 说明 |
|------|:----:|------|
| I. 简单 | PASS | 新增 Skill 遵循现有 BaseSkill 模式，不引入新抽象层 |
| II. 可维护 | PASS | 新模块遵循 biz 分层架构（routes→services→impl→storage），模块间单向依赖 |
| III. 测试优先 | PASS | 每个 Skill 配套单元测试，SQLite 用 tmp_path 真实 DB |
| IV. 避免过度设计 | PASS | P1 仅实现搜索+爬取两个 Skill，浏览器自动化留 P3 |
| Security | PASS | OPA 策略控制域名白名单，外部内容标记来源和可信度 |

### Post-Design Check

| 原则 | 合规 | 说明 |
|------|:----:|------|
| I. 简单 | PASS | WebSearchSkill/WebCrawlSkill 各一个类，无多余抽象 |
| II. 可维护 | PASS | 新增 `odap/tools/web/` 模块，不修改现有 Skill 代码 |
| III. 测试优先 | PASS | data-model 定义了完整输入/输出模型，可先写测试 |
| IV. 避免过度设计 | PASS | CollectionTask 仅用于追踪，不引入任务队列等复杂机制 |
| Security | PASS | OPA 策略已定义，域名白名单可配置 |
| G-1 | PASS | Spec 使用 Given/When/Then 格式 |
| G-4 | PASS | 预计每个 task 可在 1 天内完成 |
| G-7 | PASS | 新增路由需通过路由异常处理测试 |
| G-10 | PASS | 实施完成需运行 pytest tests/unit/ -q |

## Project Structure

### Documentation (this feature)

```text
specs/005-data-collection-opt/
├── plan.md              # This file
├── research.md          # Phase 0 output - 7 research decisions
├── data-model.md        # Phase 1 output - 12 entity definitions
├── quickstart.md        # Phase 1 output - verification steps
├── contracts/           # Phase 1 output
│   └── api-contracts.md # Skill/REST/MCP/OPA contracts
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
odap/
├── tools/
│   ├── web/                          # NEW: Web 数据采集技能模块
│   │   ├── __init__.py               #   模块入口，导出 Skill
│   │   └── web_skills.py             #   WebSearchSkill + WebCrawlSkill
│   └── __init__.py                   # MODIFY: 添加 web 模块导入
├── biz/
│   ├── data/
│   │   └── web_crawl/                # NEW: Web 爬取业务模块
│   │       ├── api/
│   │       │   ├── routes.py         #   POST /api/web-crawl, /api/web-search
│   │       │   └── schemas.py        #   CrawlRequest, SearchRequest, etc.
│   │       ├── services/
│   │       │   └── crawl_service.py  #   编排层
│   │       ├── impl/
│   │       │   ├── crawl4ai_crawler.py   #   Crawl4AI 实现
│   │       │   └── requests_fallback.py  #   requests+BS4 降级实现
│   │       └── storage/
│   │           ├── __init__.py
│   │           └── sqlite_collection_storage.py  # CollectionTask 持久化
│   └── core/
│       └── agent/
│           └── intelligence_agent.py # MODIFY: allowed_categories 加入 "web"
├── infra/
│   ├── opa/
│   │   └── policies/
│   │       └── data_collection.rego  # NEW: 域名白名单策略
│   └── utils/
│       └── web_scraper.py            # EXISTING: 不修改，作为降级后端
└── web/
    └── app.py                        # MODIFY: include_router(web_crawl_router)

frontend/
└── src/
    └── modules/
        └── ingest/
            ├── components/
            │   └── WebCrawlPanel.tsx  # NEW: 智能爬取面板
            └── pages/
                └── IngestPanel.tsx    # MODIFY: 添加新 Tab

docker/
├── docker-compose.yml                # MODIFY: 添加 crawl4ai 服务
└── Dockerfile.crawl4ai               # NEW: Crawl4AI 独立容器

tests/
└── unit/
    ├── test_web_skills.py            # NEW: Skill 注册和执行测试
    ├── test_crawl_service.py         # NEW: 爬取服务测试
    └── test_collection_storage.py    # NEW: 存储层测试
```

**Structure Decision**: 遵循现有 biz 模块分层架构（routes→services→impl→storage），新增 `odap/tools/web/` 技能模块和 `odap/biz/data/web_crawl/` 业务模块。Skill 模块负责 Agent 调用链，业务模块负责 REST API 和持久化。

## Implementation Phases

### Phase 1: P1 - Agent 联网搜索 + Skill 注册 (MVP)

**目标**: 让 Agent 能通过 web_search Skill 联网搜索

**变更范围**:
1. 新增 `odap/tools/web/web_skills.py` — WebSearchSkill
2. 修改 `odap/tools/__init__.py` — 导入 web 模块
3. 修改 `odap/biz/core/agent/intelligence_agent.py` — allowed_categories 加入 "web"
4. 新增 `odap/infra/opa/policies/data_collection.rego` — 搜索权限策略
5. 新增 `tests/unit/test_web_skills.py` — 搜索 Skill 测试

**验证**: Agent 对话中提问实时信息问题，能调用 web_search 返回结果

### Phase 2: P1 - 统一 Skill 注册 + JS 渲染爬取

**目标**: Agent 能通过 web_crawl Skill 爬取 JS 渲染页面

**变更范围**:
1. 新增 `odap/tools/web/web_skills.py` — WebCrawlSkill
2. 新增 `odap/biz/data/web_crawl/` — 完整业务模块
3. 新增 `docker/Dockerfile.crawl4ai` — Crawl4AI 容器
4. 修改 `docker/docker-compose.yml` — 添加 crawl4ai 服务
5. 修改 `odap/web/app.py` — 注册爬取路由
6. 新增 `tests/unit/test_crawl_service.py` — 爬取服务测试
7. 新增 `tests/unit/test_collection_storage.py` — 存储层测试

**验证**: 爬取 JS 渲染页面获取完整内容，Crawl4AI 不可用时降级到 requests

### Phase 3: P2 - 前端摄入界面增强

**目标**: 前端摄入面板新增智能爬取和联网搜索选项

**变更范围**:
1. 新增 `frontend/src/modules/ingest/components/WebCrawlPanel.tsx`
2. 修改 `frontend/src/modules/ingest/pages/IngestPanel.tsx` — 添加新 Tab

**验证**: 前端摄入面板可选择新采集方式，实时显示进度

### Phase 4: P3 - AI 浏览器自动化 (后续迭代)

**目标**: 通过 MCP 集成 browser-use，支持复杂交互采集

**变更范围**: 待 P1/P2 完成后规划

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 新增 Crawl4AI 独立容器 | Chromium 进程内存需求大，不能与主服务同容器 | 主容器内安装会导致镜像膨胀 500MB+ 和内存争用 |
| 新增 "web" Skill 类别 | 联网能力与现有 intelligence/analysis 语义不同 | 归入 intelligence 类别语义不准确，不利于权限细分 |
