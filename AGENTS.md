# AGENTS.md — AI 代理工作规则

> **ODAP**（本体驱动分析决策平台）—— 基于 Graphiti 双时态知识图谱，提供本体管理、智能体编排、决策推演与模拟仿真能力。后端 Python/FastAPI + 前端 React 19/TypeScript，7大业务领域、30+ 路由模块、Podman 容器化部署。
> **技术栈**：Python 3.10+ · FastAPI · Pydantic v2 · Neo4j/SQLite/Redis · OPA · OpenHarness v1/v2 · React 19 · TypeScript · Ant Design 6 · Zustand 5 · Podman

---

## 目录

- [§ 1. 项目概述](#1-项目概述)
- [§ 2. 快速命令](#2-快速命令)
  - [§ 2.1 环境准备](#21-环境准备)
  - [§ 2.2 启动命令（dev vs prod 严格区分）](#22-启动命令dev-vs-prod-严格区分)
  - [§ 2.3 环境变量速查](#23-环境变量速查)
- [§ 3. 后端架构](#3-后端架构)
- [§ 4. 前端架构](#4-前端架构)
- [§ 5. 关键约定（硬性规则）](#5-关键约定硬性规则)
- [§ 6. 本地开发及验证流程](#6-本地开发及验证流程)
- [§ 7. 质量检查](#7-质量检查)
- [§ 8. 系统架构与数据关系约束](#8-系统架构与数据关系约束)
- [§ 9. 参考项目约定](#9-参考项目约定)
- [§ 10. 文档导航](#10-文档导航)
- [附录](#附录)
  - [A. 两个 Web 入口（极易混淆）](#a-两个-web-入口极易混淆)
  - [B. 核心编码规则速查](#b-核心编码规则速查)
  - [C. 测试规则](#c-测试规则)
  - [D. 陷阱与禁忌](#d-陷阱与禁忌)

---

## 1. 项目概述

ODAP 是一个**本体驱动的分析决策平台**，核心能力围绕 Graphiti 双时态知识图谱构建。平台支持用户定义本体（Ontology）、管理多版本本体定义、通过智能体（Agent）进行问答与推演、基于场景进行模拟仿真，最终形成"摄入→构建→问答→执行→反馈"的完整闭环。

```
ontology-graphiti/           # 项目根目录
├── odap/                   # 后端主包（7大业务领域）
│   ├── biz/                #   业务模块：core / decision / integration / platform / data / simulation / management
│   ├── infra/              #   基础设施：graph / query / opa / security / openharness / llm 等
│   ├── tools/              #   领域 Skills（base.py + registry.py + 9个技能包）
│   └── web/                #   Web 入口与网关
├── frontend/               # 前端（React 19 + Vite + Ant Design 6）
│   └── src/modules/        #   业务模块：agent / audit / business / config / ingest / knowledge / ontology / qa / roles / simulation / system / version / workspace
├── openharness/            # Git Submodule（OpenHarness v1/v2 适配层）
├── docker/                 # Dockerfile + Podman Compose 配置
├── tests/                  # unit / integration / e2e
├── docs/                   # 文档体系（需求→设计→架构→模块→UI→安全→DFX→ADR）
├── bootstep.py             # 一键容器启动脚本（Podman）
└── main.py                 # CLI 入口（本地开发用）
```

---

## 2. 快速命令

### 2.1 环境准备

```bash
# 1. 克隆 + 初始化子模块
git clone --recursive <repo-url>                # 含子模块
git submodule update --init --recursive         # 已有仓库时初始化

# 2. 安装依赖
pip install -r requirements.txt                   # 后端（含 -e ./openharness）
cd frontend && npm install                        # 前端

# 3. 环境变量（复制并修改）
cp .env.example .env.docker                       # 必填：OPENAI_API_KEY / NEO4J_* / JWT_SECRET
```

### 2.2 启动命令（dev vs prod 严格区分）

> **核心原则**：开发与生产使用**不同命令、不同镜像、不同挂载策略**。禁止混用。

#### 2.2.1 一键启动对照表

| 场景 | 命令 | 镜像 | 挂载策略 | 启动耗时 | 热重载 |
|------|------|------|----------|----------|--------|
| **日常开发** ⭐ | `python bootstep.py dev` | `docker_app:latest` + `docker_frontend:dev` | bind mount 源码 | **< 30s** | ✅ 前端 HMR + 后端 uvicorn --reload |
| **生产部署** | `python bootstep.py up` | `docker_app:latest` + `docker_frontend:latest` | 命名卷（app-data） | < 60s | ❌ |
| **重建后端镜像** | `python bootstep.py rebuild main` | 重建后启动 | 同 prod | 3-5 min | ❌ |
| **重建前端镜像** | `python bootstep.py rebuild frontend` | 重建后启动 | bind mount | 3-5 min | ✅ |
| **仅查看状态** | `python bootstep.py status` | — | — | < 5s | — |
| **停止所有** | `python bootstep.py down` | — | — | < 10s | — |
| **重启服务** | `python bootstep.py restart` | 复用已有 | 复用 | < 30s | ✅（dev）/ ❌（prod） |
| **清理镜像** | `python bootstep.py clean` | 删除 dangling | — | < 30s | — |

#### 2.2.2 开发模式 (`bootstep.py dev`) — 唯一推荐

**使用场景**：日常开发、改后端/前端代码、调 bug、写新功能。

**工作机制**：
```
┌─────────────────────────────────────────────────────────────┐
│  1. 复用本地镜像（不重建）                                     │
│     - docker_app:latest   (后端 + 全部 pip 依赖)              │
│     - docker_frontend:dev (前端 + node_modules)              │
│  2. 启动容器 (compose override + 不带 --build)                │
│  3. bind mount 源码到容器内：                                  │
│     - ../odap → /app/odap    (后端代码)                       │
│     - ../frontend/src → /app/src (前端代码)                   │
│  4. 启动命令改为：                                             │
│     - 后端: uvicorn --reload (检测 .py 变化自动重启)          │
│     - 前端: vite dev (HMR 热模块替换)                         │
└─────────────────────────────────────────────────────────────┘
```

**典型启动耗时**：
- 首次启动（Neo4j 初始化）：60-90s
- 二次启动（数据已持久化）：< 30s

**代码修改后**：
| 改了什么 | 需要做什么 | 等待 |
|---------|-----------|------|
| `odap/**/*.py` | 无（uvicorn --reload） | 2-3s |
| `frontend/src/**/*` | 无（Vite HMR） | < 1s |
| `requirements.txt` | `python bootstep.py rebuild main` 后 `dev` | 3-5 min |
| `frontend/package.json` | `podman exec graphiti-frontend-dev npm i <pkg>` | 30s |
| `docker/Dockerfile` | `python bootstep.py rebuild all` | 5-10 min |
| `.env.docker` | `python bootstep.py restart` | < 30s |

#### 2.2.3 生产模式 (`bootstep.py up`)

**使用场景**：部署、冒烟测试、CI/CD 流水线验证。

**工作机制**：
```
┌─────────────────────────────────────────────────────────────┐
│  1. 强制重建镜像（无 build cache 复用）                       │
│  2. 启动容器 (compose 主文件 + --build)                      │
│  3. 数据卷挂载（无源码 bind mount）                            │
│     - app-data → /app/data (SQLite/缓存)                    │
│  4. 启动命令：                                                │
│     - 后端: uvicorn --workers 4 (4 进程)                     │
│     - 前端: nginx (静态文件)                                  │
└─────────────────────────────────────────────────────────────┘
```

**典型启动耗时**：
- 首次部署：5-10 min（拉镜像 + 构建 + Neo4j 初始化）
- 后续部署：2-3 min（构建命中缓存）

#### 2.2.4 常见启动问题速查

| 症状 | 原因 | 解决 |
|------|------|------|
| `ModuleNotFoundError: No module named 'jwt'` | 镜像缺少 pyjwt | 已修复：`requirements.txt` + `Dockerfile` 已加 `pyjwt>=2.8.0`，重建镜像 |
| `RuntimeError: bcrypt is not installed` | 镜像缺少 bcrypt | 已修复：`requirements.txt` + `Dockerfile` 已加 `bcrypt>=4.1.0`，重建镜像 |
| `JWT_SECRET has a placeholder value` | 默认 `.env.docker` 密钥太短 | 已修复：`.env.docker` 默认值改为 64 字符 |
| OPA 启动报 `merge error` | `/policies` 目录含 bundles JSON | 已修复：`docker-compose.yml` 改为挂载 `../odap/infra/opa/policies:/policies` |
| `Module not found: 'react-i18next'` | 旧前端镜像未含此包 | 已修复：在容器内 `npm i react-i18next i18next`；下次 `rebuild frontend` 时会基于最新 `package.json` |
| `apt-get` 拉 gcc/g++ 失败 | dev 构建时容器无外网 | 已修复：`docker-compose.override.yml` 改用 `docker_app:latest` 而非重新构建 |
| 容器启动后立即退出 | bind mount 路径不存在 | 已修复：根目录创建 `app/` 空目录 |
| 端口 8000 占用 | 旧容器未清理 | `podman rm -f --depend graphiti-main-app graphiti-frontend-dev` |

#### 2.2.5 标准启动流程（推荐）

```powershell
# 1. 首次启动 - 仅做一次
python bootstep.py dev
# 等待 30-90s, 看到所有容器 Up

# 2. 验证健康
podman ps --format "table {{.Names}} {{.Status}} {{.Ports}}"
# 期望: graphiti-main-app Up X minutes (healthy)

# 3. 浏览器访问
# 前端: http://localhost:5173
# 后端 API 文档: http://localhost:8000/docs
# 健康检查: http://localhost:8000/health

# 4. 日常开发 - 仅在以下情况重启
#    - 改了 .env.docker / Dockerfile / 依赖
python bootstep.py restart

# 5. 查看日志（开发时常用）
podman logs -f graphiti-main-app
podman logs -f graphiti-frontend-dev

# 6. 收工
python bootstep.py down
```

**服务访问地址**：
| 服务 | 端口 | URL |
|------|------|-----|
| 前端（dev） | 5173 | http://localhost:5173 |
| 后端 API | 8000 | http://localhost:8000 |
| API 文档 | 8000 | http://localhost:8000/docs |
| 健康检查 | 8000 | http://localhost:8000/health |
| Neo4j 浏览器 | 7474 | http://localhost:7474 |
| Neo4j Bolt | 7687 | bolt://localhost:7687 |
| OPA | 8181 | http://localhost:8181 |
| Redis | 6379 | localhost:6379 |
| MinIO | 9000-9001 | http://localhost:9000 |

#### 2.2.6 关键文件速查

| 文件 | 作用 | 修改时机 |
|------|------|----------|
| `bootstep.py` | 一键启动脚本 | 添加新容器/调整流程 |
| `docker/docker-compose.yml` | 生产 compose | 添加/修改服务 |
| `docker/docker-compose.override.yml` | 开发 compose 覆盖 | 调整 bind mount 或 dev 镜像 |
| `docker/Dockerfile` | 生产后端镜像 | 添加系统依赖 |
| `docker/Dockerfile.dev` | 开发后端镜像（备用） | 一般用最新镜像 |
| `frontend/Dockerfile` | 生产前端镜像 | 添加 nginx 配置 |
| `frontend/Dockerfile.dev` | 开发前端镜像 | 基础 Node 镜像 |
| `.env.docker` | 环境变量 | API Key / 密码 / 端口 |
| `requirements.txt` | 后端依赖 | 添加新 pip 包 |
| `frontend/package.json` | 前端依赖 | 添加新 npm 包 |
| `.dockerignore` | 构建上下文排除 | 排除新的大目录 |

> **关键约束**：**禁止在宿主机直接执行** `python main.py --web` 或 `npm run dev`。所有开发服务必须运行在 Podman 容器内。

### 2.3 环境变量速查

| 变量 | 必填 | 说明 |
|------|:--:|------|
| `OPENAI_API_KEY` | 是 | LLM API Key |
| `OPENAI_API_BASE` | 是 | LLM API 基地址 |
| `OPENAI_MODEL` | 是 | 模型名称 |
| `NEO4J_URI` | 是 | 图数据库连接（容器内用 `graphiti-neo4j:7687`） |
| `NEO4J_USER` / `NEO4J_PASSWORD` | 是 | Neo4j 认证 |
| `JWT_SECRET` | 是 | JWT 签名密钥（≥ 32 字符） |
| `TAVILY_API_KEY` | 否 | 搜索增强 |
| `OPA_URL` | 否 | OPA 策略引擎地址 |
| `REDIS_URL` | 否 | 缓存服务 |
| `CORS_ORIGINS` | 否 | 跨域白名单 |

---

## 3. 后端架构

### 3.1 包结构树

```
odap/
├── biz/                           # 业务模块（7 个领域，禁止跨层调用）
│   ├── core/                      #   本体(Ontology) + 认知(Cognition) + Agent 编排
│   │   └── {module}/
│   │       ├── api/
│   │       │   ├── routes.py      #       FastAPI 路由（唯一入口）
│   │       │   └── schemas.py     #       Pydantic 请求/响应模型
│   │       ├── models/            #       领域模型 (Pydantic BaseModel)
│   │       ├── interfaces/          #       抽象基类 (ABC)
│   │       ├── impl/               #       接口实现（核心逻辑）
│   │       ├── services/          #       编排层（路由 ↔ 实现 桥梁）
│   │       └── storage/            #       SQLite 持久化
│   │           ├── __init__.py      #           Storage = SQLiteXxxStorage（别名导出）
│   │           └── sqlite_xxx_storage.py
│   ├── decision/                  #   action_service + decision_pipeline + decision_recommendation
│   ├── integration/               #   openharness_agent + mcp_adapter + hook_system + frontend_compat
│   ├── platform/                  #   workspace + roles + skill_system + tool_registry + session_memory + ontology_memory
│   ├── data/                      #   data_warehouse + knowledge_base + perception + qa + semantic_map
│   ├── simulation/                #   event_simulator + simulation_sandbox + feedback + simulation_deduction
│   └── management/                #   agent_management + business
├── infra/                         # 基础设施（可横向复用）
│   ├── graph/                     #   GraphManager（Neo4j 生产 / NetworkX 回退）
│   ├── query/                     #   统一查询服务 (ADR-055)
│   ├── opa/                       #   OPA 策略引擎（Rego + bundles）
│   ├── security/                  #   JWT + OAuth2 + 审计路由
│   ├── openharness/               #   v1/v2 适配层
│   └── llm/ monitoring/ resilience/ data_pipeline/ config/ object_service/ storage/ utils/
├── tools/                         # 领域 Skills（base.py + registry.py + 9 个技能包）
└── web/
    ├── app.py                     #   ⭐ 生产入口（端口 8000）—— 新增路由必须在此注册
    ├── api/app.py                 #   本地开发入口（端口 8765，MockDataWebService）
    ├── gateway/                   #   API 网关
    └── ws/                        #   WebSocket 事件总线
```

### 3.2 核心子系统

| 子系统 | 职责 | 入口文件 | 详细文档 |
|--------|------|----------|----------|
| **本体管理** | 本体 CRUD、版本控制、场景绑定 | `odap/biz/core/ontology/api/routes.py` | [docs/03-modules/ontology/DESIGN.md](docs/03-modules/ontology/DESIGN.md) |
| **Agent 编排** | 多 Agent 协同、Swarm 调度 | `odap/biz/core/agent/` | [docs/03-modules/swarm_orchestrator/DESIGN.md](docs/03-modules/swarm_orchestrator/DESIGN.md) |
| **OPA 策略** | 权限决策、工作空间隔离 | `odap/infra/opa/` | [docs/03-modules/opa_policy/DESIGN.md](docs/03-modules/opa_policy/DESIGN.md) |
| **Hook 系统** | 事件订阅/发布、异步广播 | `odap/biz/integration/hook_system/` | [docs/03-modules/hook_system/DESIGN.md](docs/03-modules/hook_system/DESIGN.md) |
| **MCP 适配** | Model Context Protocol 集成 | `odap/biz/integration/mcp_adapter/` | [docs/03-modules/mcp_protocol/DESIGN.md](docs/03-modules/mcp_protocol/DESIGN.md) |
| **问答引擎** | 基于本体的 RAG 问答 | `odap/biz/data/qa/` | [docs/03-modules/qa_engine/DESIGN.md](docs/03-modules/qa_engine/DESIGN.md) |
| **模拟仿真** | 事件推演、沙盘推演 | `odap/biz/simulation/` | [docs/03-modules/event_simulator/DESIGN.md](docs/03-modules/event_simulator/DESIGN.md) |
| **审计日志** | 全链路审计、统一写入/读取 | `odap/infra/security/unified_audit.py` | [docs/03-modules/audit_log/DESIGN.md](docs/03-modules/audit_log/DESIGN.md) |
| **统一查询** | 多数据源查询抽象 | `odap/infra/query/` | ADR-055 |

### 3.3 前后端术语映射

| 后端术语 | 前端术语 | 说明 |
|----------|----------|------|
| Ontology | 本体 / 语义网络 | 知识图谱 schema 定义 |
| OntologyVersion | 版本历史 | 本体的多版本管理 |
| Scenario | 场景 | 工作空间下的业务场景 |
| Workspace | 工作空间 | 顶级资源容器 |
| Agent | 智能体 | AI 代理实例 |
| Skill | 技能 | 可注册复用的能力单元 |
| Ingest | 数据摄入 | 文档/数据导入流程 |
| Simulation / Sandbox | 模拟器 / 推演 | 事件仿真与策略推演 |
| SemanticMap | 语义地图 | 本体可视化呈现 |
| BusinessRule | 业务规则 | 基于本体的规则引擎 |
| Harness | 蓝图设计器 | 本体可视化编排工具 |

---

## 4. 前端架构

### 4.1 技术栈

- **框架**: React 19 + TypeScript
- **构建**: Vite 8.x
- **UI 库**: Ant Design 6.x + `@ant-design/icons`
- **状态管理**: Zustand 5.x
- **路由**: React Router DOM 7.x
- **图表**: AntV G6 5.x + ECharts 6.x + `@xyflow/react`（React Flow）
- **地图**: Leaflet + React-Leaflet
- **测试**: Vitest + `@testing-library/react`
- **代码检查**: ESLint + TypeScript-ESLint

### 4.2 路由方案

前端路由定义于 [`frontend/src/AppRoutes.tsx`](frontend/src/AppRoutes.tsx)，采用**声明式路由**，主要页面如下：

| 路径 | 组件 | 模块 |
|------|------|------|
| `/login` | `LoginPage` | shared |
| `/my-agents` | `MyAgents` | agent |
| `/agent-chat/:agentId` | `AgentChat` | agent |
| `/ontology` | `OntologySemanticNetwork` | ontology |
| `/blueprint` | `BlueprintDesignerPage` | ontology |
| `/versions` | `VersionHistory` | version |
| `/business/process` | `BusinessProcess` | business |
| `/business/rules` | `Rules` | business |
| `/business/indicators` | `Indicators` | business |
| `/business/logic` | `Logic` | business |
| `/business/entities` | `ObjectManagement` | business |
| `/business/extraction` | `SmartGeneration` | business |
| `/skills` | `SkillManagement` | system |
| `/simulator` | `Simulator` | ingest |
| `/simulation/deduction` | `StrategyDeduction` | simulation |
| `/ingest` | `IngestPanel` | ingest |
| `/knowledge` | `KnowledgeBase` | knowledge |
| `/workspace` | `WorkspaceManager` | workspace |
| `/roles` | `RoleManager` / `UserManagement` | roles |

### 4.3 API 层约定

- **Base URL**: 通过 `VITE_API_BASE` 环境变量配置，默认空（同域）
- **代理**: Vite dev server 将 `/api` 代理到后端（默认 `http://localhost:8765`）
- **认证**: JWT Token 存储于 `localStorage`，请求头携带 `Authorization: Bearer <token>`
- **模块组织**: 每个前端模块独立维护 API 调用逻辑，建议按模块划分 `api/` 目录

### 4.4 组件库规范

- **基础组件**: Ant Design 6 组件（Button、Table、Form、Modal 等）
- **业务组件**: 各 `modules/{name}/components/` 下维护，禁止跨模块直接引用
- **图表组件**: G6（图谱可视化）、ECharts（统计图表）、React Flow（流程/蓝图编排）
- **共享组件**: `modules/shared/components/` 放置通用组件（如 LoginPage）

### 4.5 详细文档

- [docs/03-modules/web_frontend/DESIGN.md](docs/03-modules/web_frontend/DESIGN.md) — Web 前端模块设计
- [docs/04-ui/COMPONENT_HIERARCHY.md](docs/04-ui/COMPONENT_HIERARCHY.md) — 组件层级
- [docs/04-ui/COMPONENT_SPEC.md](docs/04-ui/COMPONENT_SPEC.md) — 组件规范
- [docs/04-ui/ONTOLOGY_BUILD_UI.md](docs/04-ui/ONTOLOGY_BUILD_UI.md) — 本体构建 UI 设计

---

## 5. 关键约定（硬性规则）

> 违反以下规则将直接导致功能异常或线上故障。

### 规则 1：新增路由必须注册到生产入口

新增路由必须在 `odap/web/app.py` 中通过 `include_router()` 注册。本地开发入口 `odap/web/api/app.py` 有独立路由逻辑，不自动同步。
- 📎 [路由定义规则](#路由定义规则)

### 规则 2：服务层不抛 HTTPException

服务层（`services/`）必须返回 `Dict[str, Any]`，错误格式为 `{"status": "error", "message": "..."}`。路由层负责翻译为 `HTTPException`。禁止在服务层抛出 HTTPException。
- 📎 [错误处理规则](#错误处理规则)

### 规则 3：路由层必须透传 HTTPException

路由层的 `except` 块必须包含 `except HTTPException: raise`，否则已构造的 HTTP 异常会被外层 `except Exception` 兜底吞为 500。
- 📎 [路由定义规则](#路由定义规则)

### 规则 4：Enum 必须 `(str, Enum)` 双继承

所有枚举必须 `class XxxStatus(str, Enum)`，确保 JSON 序列化正常。禁止用纯 `Enum`。
- 📎 [领域模型规则](#领域模型规则)

### 规则 5：容器字段必须 `Field(default_factory=...)`

List/Dict/Set 等可变容器字段必须用 `Field(default_factory=list)` 或 `Field(default_factory=dict)`，禁止 `= []` 或 `= {}`（会导致实例间共享引用）。
- 📎 [领域模型规则](#领域模型规则)

### 规则 6：调用链禁止跨层

严格遵循 `routes.py → services/ → impl/ → storage/` 调用链，禁止跨层调用（如路由层直接访问 storage）。
- 📎 [biz 模块内部结构](#biz-模块内部结构)

### 规则 7：开发环境用 Podman 容器

前后端服务统一通过 `python bootstep.py dev` 在 Podman 容器内运行。**禁止在宿主机直接 `uvicorn` 或 `npm run dev`**。代码修改后需执行 `bootstep.py restart` 或 `rebuild` 才能生效。
- 📎 [开发环境部署规则](#开发环境部署规则)

### 规则 8：SQLite 无连接池，每次 connect/close

SQLite 存储层每次操作必须 `sqlite3.connect()` → 用完 `conn.close()`，禁止保持长连接。复杂字段（Dict/List）存 JSON TEXT，Enum 存 `.value` 字符串，datetime 存 ISO 字符串。
- 📎 [SQLite 存储规则](#sqlite-存储规则)

### 规则 9：新增模块必须同步新增测试文件

每个新增模块必须在 `tests/unit/` 下创建对应 `test_{module}.py`，不允许零测试提交。SQLite 存储层测试用 `tmp_path` 真实 DB，禁止 MagicMock。
- 📎 [测试规则](#测试规则)

### 规则 10：Neo4j URI 必须使用容器服务名

容器环境下 `NEO4J_URI` 必须使用 `bolt://graphiti-neo4j:7687`，禁止写 `localhost`。容器间通过 Podman 网络通信。
- 📎 [环境变量速查](#环境变量速查)

---

## 6. 本地开发及验证流程

### 6.1 「改 → 构建 → 启动 → 验证」闭环

```
┌─────────────────────────────────────────────────────────────────────┐
│  Step 1: 修改代码                                                    │
│  ─────────────────────────────────────────────────────────────────  │
│  • 后端：odap/ 下的 .py 文件                                          │
│  • 前端：frontend/src/ 下的 .ts/.tsx/.css 文件                         │
├─────────────────────────────────────────────────────────────────────┤
│  Step 2: 构建/重启                                                    │
│  ─────────────────────────────────────────────────────────────────  │
│  • 容器开发：python bootstep.py restart      (代码修改后必须执行)      │
│  • 依赖变更：python bootstep.py rebuild      (requirements/package.json) │
│  • 本地后端：python main.py --web             (仅快速调试)             │
│  • 本地前端：cd frontend && npm run dev      (仅快速调试)             │
├─────────────────────────────────────────────────────────────────────┤
│  Step 3: 启动服务                                                     │
│  ─────────────────────────────────────────────────────────────────  │
│  • 容器模式：python bootstep.py dev                                  │
│    - 前端 http://localhost:5173   (Vite 热重载)                      │
│    - 后端 http://localhost:8000   (生产入口)                         │
│  • 本地模式：                                                         │
│    - 前端 http://localhost:5173   (Vite dev server)                  │
│    - 后端 http://localhost:8765   (本地开发入口)                      │
├─────────────────────────────────────────────────────────────────────┤
│  Step 4: 验证                                                         │
│  ─────────────────────────────────────────────────────────────────  │
│  • 健康检查：curl http://localhost:8000/health                       │
│  • 登录获取 Token → 携带 Token 访问业务接口                            │
│  • 运行测试：pytest tests/unit/ -v                                   │
│  • 前端检查：cd frontend && npm run lint && npm run typecheck        │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.2 Token 获取与使用

```bash
# 1. 登录获取 Token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
# 响应：{"access_token":"...","refresh_token":"..."}

# 2. 携带 Token 访问受保护接口
curl -H "Authorization: Bearer <access_token>" \
  http://localhost:8000/api/workspaces

# 3. 刷新 Token
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"..."}'
```

### 6.3 常用验证请求

```bash
# 健康检查
curl http://localhost:8000/health

# 获取工作空间列表（需 Token）
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/workspaces

# 创建本体（需 Token）
curl -X POST http://localhost:8000/api/ontology \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"test-ontology","description":"Test"}'

# 获取本体列表（需 Token）
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/ontology
```

### 6.4 日志路径

| 日志类型 | 路径/命令 |
|----------|----------|
| 后端容器日志 | `python bootstep.py logs` |
| 前端容器日志 | `python bootstep.py logs fe` |
| 本地后端日志 | `app.log`（由 `LOG_FILE` 环境变量控制） |
| 审计日志 | `odap/infra/security/unified_audit.py` 统一写入 SQLite |

---

## 7. 质量检查

### 7.1 命令矩阵

| 检查项 | 后端命令 | 前端命令 |
|--------|--------|----------|
| **Lint** | `ruff check .` / `flake8` | `cd frontend && npm run lint` |
| **Format** | `ruff format .` / `black` | `cd frontend && npx prettier --write .` |
| **Type Check** | Python 类型（运行时检查） | `cd frontend && npm run typecheck` |
| **Test** | `pytest tests/unit/ -v` | `cd frontend && npm test` |
| **Test (Integration)** | `pytest tests/integration/ -v` | — |
| **Coverage** | `pytest --cov=odap tests/unit/` | `cd frontend && npm run test:coverage` |
| **Build** | — | `cd frontend && npm run build` |

### 7.2 pytest 标记

```python
# 单元测试（默认）
pytest tests/unit/ -v

# 集成测试（需要 Neo4j 运行，否则跳过）
pytest tests/integration/ -v -m integration

# 慢速测试
pytest tests/ -v -m slow

# 端到端测试
pytest tests/e2e/ -v -m e2e
```

---

## 8. 系统架构与数据关系约束

### 8.1 核心实体关系图

```
User ─┬─ 1:N ─→ Role              (用户拥有多个角色)
      └─ 1:N ─→ Workspace         (用户属于多个工作空间)
                Workspace ─ 1:N ─→ Scenario       (工作空间包含多个场景)
                              Scenario ─ N:M ─→ Ontology     (场景绑定多个本体)
                                            Ontology ─ 1:N ─→ OntologyVersion (本体多版本)
                                            Ontology ─ 1:1 ─→ OntologyDefinition (本体定义)
                              OntologyVersion ─ 1:N ─→ SemanticMap   (语义地图)
                              OntologyVersion ─ 1:N ─→ BusinessRule  (业务规则)
                              OntologyVersion ─ 1:N ─→ LogicModel    (逻辑模型)
                              OntologyVersion ─ 1:N ─→ MetricSystem  (指标体系)
                              OntologyVersion ─ 1:N ─→ BusinessProcess(业务过程)
      Agent ─┬─ N:1 ─→ Role       (智能体关联角色)
             └─ N:1 ─→ Workspace  (智能体关联工作空间)
      Skill ─ N:1 ─→ OntologyDefinition (Skill 关联本体定义)
      Simulation ─ N:1 ─→ Ontology (模拟演练关联本体)
```

### 8.2 本体图谱与场景关联规则

- 本体图谱与场景有关，也和本体有关：一个本体有多个对象（实体/关系/事件）
- 图谱数据查询必须基于场景上下文：`场景 → 本体列表 → 图谱对象`
- 智能体问答检索范围 = 当前绑定场景的所有本体图谱数据
- 跨场景图谱数据隔离，禁止未授权跨场景查询

### 8.3 主要约束

1. **用户权限与资源管理**：JWT Payload 必须包含 `role` + `ws_id` + `ws_role`
2. **工作空间与场景层级**：工作空间作为顶级资源容器，场景继承基础配置
3. **场景与本体关联**：单个场景支持绑定多个本体（N:M），解绑需检查依赖
4. **本体版本管理**：版本记录含 `version_number`、`changelog`、`status`，支持回溯与对比
5. **业务资产关联**：语义地图、业务规则、逻辑模型等必须关联特定本体版本（非本体定义）
6. **本体定义不可变**：本体定义更新必须通过创建新本体实现，禁止直接修改
7. **智能体配置**：必须同时关联特定角色与工作空间
8. **Skill 管理**：创建/更新/删除必须关联特定本体定义
9. **模拟演练**：必须关联特定本体作为数据基础
10. **审计一致性**：所有变更通过 `unified_audit.py` 统一写入，`audit_api.py` 统一读取

---

## 9. 参考项目约定

### 9.1 参考项目列表

| 项目 | 用途 | 集成方式 |
|------|------|----------|
| **Graphiti** | 双时态知识图谱核心 | PyPI `graphiti-core>=0.28.0` |
| **OpenHarness** | Agent 编排与执行框架 | Git Submodule (`-e ./openharness`) |
| **Neo4j** | 图数据库存储 | 容器服务 / 本地安装 |
| **OPA** | 策略权限引擎 | 容器服务 (`openpolicyagent/opa:0.58.0`) |
| **Ant Design** | UI 组件库 | npm `antd` |
| **Zustand** | 状态管理 | npm `zustand` |
| **React Flow** | 流程/图谱编排 | npm `@xyflow/react` |
| **AntV G6** | 图谱可视化 | npm `@antv/g6` |

### 9.2 优先级规则

- **P0（阻塞）**：Graphiti、Neo4j、OpenHarness、FastAPI、React —— 核心功能依赖，必须先于业务代码就绪
- **P1（重要）**：OPA、Redis、Ant Design、Zustand —— 支撑功能，缺失会降级但可运行
- **P2（增强）**：Tavily、ECharts、React Flow —— 体验优化，缺失不影响核心流程

---

## 10. 文档导航

### 10.1 文档体系总览

```
docs/
├── 00-requirements/           # 需求文档（原始需求、 backlog）
├── 01-product-design/         # 产品设计（综合优化设计、WebUI 增强）
├── 02-architecture/           # 架构设计（四层架构、全链路、运维）
│   ├── ARCHITECTURE.md              # ⭐ 唯一权威架构
│   ├── ARCHITECTURE_FULL_CHAIN.md   # 全链路数据流概述
│   ├── ARCHITECTURE_FULL_CHAIN_DEEP.md  # 全链路深入实现
│   └── ARCHITECTURE_OPS.md          # 运维架构
├── 03-modules/               # 模块设计（17 个活跃模块）
│   ├── ontology/DESIGN.md
│   ├── swarm_orchestrator/DESIGN.md
│   ├── opa_policy/DESIGN.md
│   ├── hook_system/DESIGN.md
│   ├── mcp_protocol/DESIGN.md
│   ├── qa_engine/DESIGN.md
│   ├── event_simulator/DESIGN.md
│   ├── audit_log/DESIGN.md
│   ├── workspace/DESIGN.md
│   └── ...
├── 04-ui/                    # UI 设计（组件层级、规范、本体构建 UI）
├── 05-security/              # 安全设计
├── 06-dfx/                   # DFX 设计（可测试性、可维护性）
└── 07-adr/                   # 架构决策记录（ADR-001 ~ ADR-039）
```

### 10.2 详细文档索引表

| 主题 | 文档路径 | 说明 |
|------|----------|------|
| **架构总览** | [docs/02-architecture/ARCHITECTURE.md](docs/02-architecture/ARCHITECTURE.md) | 四层架构定义、Phase 演进 |
| **全链路实现** | [docs/02-architecture/ARCHITECTURE_FULL_CHAIN_DEEP.md](docs/02-architecture/ARCHITECTURE_FULL_CHAIN_DEEP.md) | 5-Phase 完整代码实现 |
| **模块设计总览** | [docs/03-modules/README.md](docs/03-modules/README.md) | 17 个活跃模块索引 |
| **本体管理** | [docs/03-modules/ontology/DESIGN.md](docs/03-modules/ontology/DESIGN.md) | 本体 CRUD、版本控制 |
| **Agent 编排** | [docs/03-modules/swarm_orchestrator/DESIGN.md](docs/03-modules/swarm_orchestrator/DESIGN.md) | Swarm 调度与协同 |
| **OPA 策略** | [docs/03-modules/opa_policy/DESIGN.md](docs/03-modules/opa_policy/DESIGN.md) | Rego 策略与权限 |
| **Hook 系统** | [docs/03-modules/hook_system/DESIGN.md](docs/03-modules/hook_system/DESIGN.md) | 事件订阅发布 |
| **MCP 协议** | [docs/03-modules/mcp_protocol/DESIGN.md](docs/03-modules/mcp_protocol/DESIGN.md) | Model Context Protocol |
| **问答引擎** | [docs/03-modules/qa_engine/DESIGN.md](docs/03-modules/qa_engine/DESIGN.md) | RAG 问答实现 |
| **审计日志** | [docs/03-modules/audit_log/DESIGN.md](docs/03-modules/audit_log/DESIGN.md) | 统一审计机制 |
| **Web 前端** | [docs/03-modules/web_frontend/DESIGN.md](docs/03-modules/web_frontend/DESIGN.md) | 前端模块设计 |
| **UI 组件规范** | [docs/04-ui/COMPONENT_SPEC.md](docs/04-ui/COMPONENT_SPEC.md) | 组件设计规范 |
| **安全设计** | [docs/05-security/SECURITY.md](docs/05-security/SECURITY.md) | JWT、OAuth2、审计 |
| **测试设计** | [docs/06-dfx/TEST_DESIGN.md](docs/06-dfx/TEST_DESIGN.md) | 测试策略与规范 |

---

## 附录

### A. 两个 Web 入口（极易混淆）

| 入口 | 文件 | 端口 | 何时使用 |
|------|------|------|---------|
| 生产 | `odap/web/app.py` | 8000 | Docker/Podman 部署，uvicorn 启动 |
| 本地开发 | `odap/web/api/app.py` | 8765 | `python main.py --web` |

### B. 核心编码规则速查

#### biz 模块内部结构

每个 biz 模块按以下分层组织:

```
module_name/
├── api/
│   ├── routes.py       # FastAPI 路由
│   └── schemas.py      # 请求/响应 Pydantic 模型（可选）
├── models/             # 领域模型 (Pydantic BaseModel)
├── interfaces/         # 抽象基类 (ABC)
├── impl/               # 接口实现（核心逻辑）
├── services/           # 编排层（连接路由和实现）
└── storage/            # SQLite 持久化
    ├── __init__.py     #   Storage = SQLiteXxxStorage（别名导出）
    └── sqlite_xxx_storage.py
```

**调用链**: `routes.py → services/ → impl/ → storage/`，禁止跨层调用。

#### 路由定义规则

```python
router = APIRouter(prefix="/api/xxx", tags=["xxx"])
xxx_service = XxxService()  # 模块级单例

@router.post("", response_model=XxxResponse)
async def create_xxx(request: CreateXxxRequest):
    try:
        result = xxx_service.create_xxx(...)
        return XxxResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**必须**:
- 前缀统一 `/api/{模块名}`
- `except HTTPException: raise` 透传，防止被 500 兜底吞掉
- 新路由必须在 `odap/web/app.py` 中 `include_router()`

#### 服务层返回值规则

**必须**返回 `Dict[str, Any]`，不直接返回 Pydantic 模型:

```python
def get_xxx(self, xxx_id: str) -> Dict[str, Any]:
    xxx = self.manager.get_xxx(xxx_id)
    if not xxx:
        return {"status": "error", "message": "Xxx not found"}  # 错误用此格式
    return {"xxx_id": xxx.id, "name": xxx.name, ...}             # 成功用扁平 dict
```

**类型转换在服务层完成**: Enum→`.value`, datetime→`.isoformat()`, BaseModel→扁平 dict

#### 错误处理规则

| 层 | 方式 | 示例 |
|---|------|------|
| impl/ | `raise ValueError("描述")` | 业务校验失败 |
| services/ | 返回 `{"status": "error", "message": "..."}` | 资源不存在等 |
| routes/ | `raise HTTPException(status_code=xxx, detail=...)` | 翻译为 HTTP 状态码 |
| 降级场景 | 不抛异常，返回 Mock/空数据 | 联网检索失败时降级 |

**禁止**: 在路由层直接写业务逻辑；在服务层抛 HTTPException。

#### SQLite 存储规则

```python
class SQLiteXxxStorage:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")), "xxx.db")
        self._init_db()

    def _init_db(self):
        # CREATE TABLE IF NOT EXISTS + 可选 _migrate_xxx()

    def save_xxx(self, xxx):       # INSERT OR REPLACE (upsert)
    def get_xxx(self, xxx_id):     # → Xxx | None
    def list_xxxs(self, filters, page, page_size):  # 带分页
```

**必须**:
- 每次操作 `sqlite3.connect()` → 用完 `conn.close()`（无连接池）
- 复杂字段 (Dict/List) → JSON TEXT 列
- Enum → `.value` 字符串存储
- datetime → ISO 字符串存储
- `storage/__init__.py` 别名导出: `Storage = SQLiteXxxStorage`

#### 领域模型规则

```python
class XxxStatus(str, Enum):       # 必须 (str, Enum) 双继承
    DRAFT = "draft"
    ACTIVE = "active"

class Xxx(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # uuid4 自动生成
    name: str
    status: XxxStatus = XxxStatus.DRAFT
    tags: List[str] = Field(default_factory=list)               # 容器字段必须 default_factory
    created_at: datetime = Field(default_factory=datetime.now)   # 统一用 datetime.now
```

#### 异步模式规则

- 关键路径: `await` 顺序执行
- 非阻塞广播: `asyncio.create_task(...)` (fire-and-forget，如 Hook 广播)
- 降级不回滚: Graphiti 写入失败时仅 log，版本记录保留
- 异步 HTTP: `aiohttp.ClientSession` + `ClientTimeout`
- 单例模式: `_instance` + `get_instance()` / `initialize()`

#### 认证鉴权规则

JWT 双 Token: Access 15min / Refresh 7d, HS256, Token Rotation

FastAPI 鉴权依赖:
- `Depends(get_current_user)` — 必须认证
- `Depends(optional_current_user)` — 可选认证
- `Depends(verify_admin)` — 必须 admin 角色

JWT Payload 含 `role` + `ws_id` + `ws_role`（工作空间隔离）。

### C. 测试规则

#### 必须遵守

- **新增模块必须同步新增测试文件** — 在 `tests/unit/` 下创建对应 `test_{module}.py`，不允许零测试提交
- **SQLite 存储层用真实临时 DB** — 使用 `tmp_path` fixture 创建 `.db` 文件，不用 MagicMock 模拟数据库
- **修改代码后必须运行 `pytest tests/unit/ -v`** — 全部通过后才算完成
- **测试文件命名** — `test_{模块名}.py`，与 `odap/biz/{领域}/{模块名}/` 对应

#### 测试编写模式

- **Fixture 级联**: `mock_storage → xxx_manager`，通过 `patch()` 替换 Storage 类
- **工厂函数**: `_make_xxx(**overrides)` 构造测试数据，默认值 + 覆盖
- **类组织**: `TestSQLiteXxxStorage`, `TestXxxService`, `TestXxxSchemas` 按层分组
- **异常断言**: `pytest.raises(ValueError, match="...")`
- **Mock SQLite**: 仅用于非存储层测试；存储层自身测试用 `tmp_path` 真实 DB
- **延迟导入**: fixture 内部 `from odap.xxx import` 避免模块级导入失败
- **外部依赖 skip**: 依赖 graphiti-core/openharness 等子模块的测试，模块级 `try/except` + `pytest.skip()`

#### 每个模块必须覆盖的测试点

| 层 | 必测场景 |
|---|---------|
| storage/ | CRUD 全流程、get 不存在返回 None、delete 不存在返回 False、JSON 字段序列化/反序列化、非法 JSON 容错 |
| models/ | 必填字段验证、默认值、容器字段 default_factory、Enum 值 |
| services/ | 成功返回扁平 dict、错误返回 `{"status": "error"}`、类型转换 (Enum→.value, datetime→.isoformat) |
| routes/ | HTTP 状态码映射、`except HTTPException: raise` 透传、404/400/500 场景 |

### D. 陷阱与禁忌

1. **Podman 非 Docker** — bootstep.py 全部使用 podman 命令，不要用 docker 命令
2. **两个 Web 入口** — 本地开发端口 8765，Docker 端口 8000，不要混淆
3. **服务层不抛 HTTPException** — 服务层返回 `{"status": "error"}` dict，由路由层翻译
4. **路由层必须 `except HTTPException: raise`** — 否则已构造的 HTTP 异常会被 500 兜底吞掉
5. **Enum 必须 `(str, Enum)`** — 便于 JSON 序列化，不要用纯 Enum
6. **容器字段必须 `Field(default_factory=...)`** — 不要用 `= []` 或 `= {}`
7. **OpenHarness 子模块** — clone 后必须 `git submodule update --init`
8. **集成测试** — 需要 Neo4j 运行，否则跳过
9. **SQLite 无连接池** — 每次 connect/close，不要保持长连接
10. **新增路由必须注册** — 在 `odap/web/app.py` 中 `include_router()`，否则不生效
11. **开发环境用 Podman 容器** — 不要在宿主机直接 `uvicorn` 或 `npm run dev`，用 `bootstep.py dev/restart`

### E. 端到端操作流程：创建领域智能体（以西游记为例）

以下流程演示如何利用平台现有能力，从零创建一个领域智能体：

```
Step 1: 登录获取 Token
  POST /api/auth/login  {"username":"admin","password":"admin123"}

Step 2: 创建工作空间
  POST /api/workspaces  {"name":"X","description":"西游记测试工作空间"}

Step 3: 创建场景
  POST /api/workspaces/{ws_id}/scenarios  {"name":"X-2","description":"Journey to the West scenario"}

Step 4: 创建本体
  POST /api/ontologies  {"name":"XiYouJi","workspace_id":"{ws_id}","scenario_id":"{scenario_id}"}

Step 5: 绑定本体到场景
  POST /api/workspaces/{ws_id}/scenarios/{scenario_id}/ontologies/{ontology_id}

Step 6: 构建本体类型定义
  - 对象类型: POST /api/ontologies/{oid}/object-types
  - 关系类型: POST /api/ontologies/{oid}/link-types
  - 动作类型: POST /api/ontologies/{oid}/action-types
  - 过程类型: POST /api/ontologies/{oid}/process-types
  - 规则类型: POST /api/ontologies/{oid}/rule-types
  - 逻辑函数: POST /api/ontologies/{oid}/function-types
  - 指标类型: POST /api/ontologies/{oid}/indicator-types

Step 7: 提交本体版本
  POST /api/ontologies/{oid}/commit  {"message":"Initial ontology"}

Step 8: 摄入知识数据
  POST /api/ingest/unified  {"source_type":"natural_language","text":"...","scenario_id":"...","workspace_id":"..."}

Step 9: 创建智能体
  POST /api/agent-management  {"name":"xiyouji-agent","display_name":"XiYouJi Agent","workspace_id":"{ws_id}",...}

Step 10: 智能问答
  - Agent Chat: POST /api/agent/chat  {"message":"...","workspace_id":"{ws_id}"}
  - QA 引擎:   POST /api/qa/ask  {"question":"...","workspace_id":"{ws_id}","scenario_id":"{scenario_id}"}
  - Agent 编排: POST /api/agent/orchestrate  {"query":"...","workspace_id":"{ws_id}","mode":"auto"}
```

**关键 API 路径速查**：

| 功能 | 路径 |
|------|------|
| 工作空间 CRUD | `/api/workspaces` |
| 场景 CRUD | `/api/workspaces/{ws_id}/scenarios` |
| 本体 CRUD | `/api/ontologies` |
| 对象类型 | `/api/ontologies/{oid}/object-types` |
| 关系类型 | `/api/ontologies/{oid}/link-types` |
| 动作类型 | `/api/ontologies/{oid}/action-types` |
| 过程类型 | `/api/ontologies/{oid}/process-types` |
| 规则类型 | `/api/ontologies/{oid}/rule-types` |
| 逻辑函数 | `/api/ontologies/{oid}/function-types` |
| 指标类型 | `/api/ontologies/{oid}/indicator-types` |
| 本体图谱 | `/api/ontologies/{oid}/graph` |
| 版本提交 | `/api/ontologies/{oid}/commit` |
| 统一摄入 | `/api/ingest/unified` |
| Agent 管理 | `/api/agent-management` |
| Agent 对话 | `/api/agent/chat` |
| Agent 编排 | `/api/agent/orchestrate` |
| QA 问答 | `/api/qa/ask` |
