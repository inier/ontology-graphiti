# Monorepo 重构设计文档

> **文档版本**：v1.0  
> **日期**：2026-07-16  
> **状态**：Draft（待用户审阅）  
> **对应 ADR**：ADR-066（待创建）  
> **前置条件**：所有活跃分支已合并到 main，工作区干净

---

## 目录

- [1. 背景与目标](#1-背景与目标)
- [2. 方案选型](#2-方案选型)
- [3. 目标目录结构](#3-目标目录结构)
- [4. Python Workspace 配置](#4-python-workspace-配置)
- [5. 前端 Workspace 配置](#5-前端-workspace-配置)
- [6. 子模块迁移与 Docker 适配](#6-子模块迁移与-docker-适配)
- [7. 测试组织](#7-测试组织)
- [8. 迁移执行步骤](#8-迁移执行步骤)
- [9. 验证清单](#9-验证清单)
- [10. 风险与回滚](#10-风险与回滚)
- [11. 文档同步清单](#11-文档同步清单)

---

## 1. 背景与目标

### 1.1 现状

当前 `ontology-graphiti` 是一个"伪 monorepo"形态，存在以下痛点：

- **3+ 套独立依赖文件**：根 `requirements.txt` + `openharness/pyproject.toml` + `hyper-extract/pyproject.toml` + `frontend/package.json`，无统一依赖图
- **子模块坑**：`openharness/` 和 `hyper-extract/` 是 git 子模块，clone 需 `--recursive`，CI 需 init，分支切换需同步
- **`odap/` 未声明为包**：无独立 `pyproject.toml`，靠 `pip install -r requirements.txt` 注入依赖
- **前端双锁冲突**：`package-lock.json` + `pnpm-lock.yaml` 并存
- **`pnpm-workspace.yaml` 形同虚设**：放在 `frontend/` 子目录而非仓库根
- **无统一构建/测试入口**：每个子项目各自为政

### 1.2 目标

1. **统一依赖与工具链**：Python 侧 uv workspace，前端侧 pnpm workspace，双锁文件统一管理
2. **目录布局重组**：采用 `apps/` + `packages/` 标准 monorepo 范式，明确"应用 vs 可复用包"边界
3. **子模块统一引用**：保留 git submodule 机制，但路径迁移到 `packages/` 目录，workspace 内通过 name-only 引用
4. **统一容器编排**：Dockerfile / docker-compose / bootstep.py 与新布局匹配，开发热更新 + 生产稳定部署
5. **零 import 改动**：`odap` 包名保留，Python import 路径不变

### 1.3 核心决策汇总

| 决策项 | 选择 |
|---|---|
| 目录布局范式 | `apps/` + `packages/` |
| Python 工具链 | uv workspace（hatchling 构建后端） |
| 前端工具链 | pnpm workspace |
| 子模块处理 | 保留 git submodule，路径迁至 `packages/` |
| 后端应用名 | `apps/api/`（包名仍为 `odap`） |
| 前端应用名 | `apps/web/`（包名 `@odap/web`） |
| 根 `requirements.txt` | 删除（由 `uv.lock` 替代） |
| 前端 `package-lock.json` | 删除（统一 pnpm） |
| 容器视角 | 开发 + 生产均为 workspace 视角（统一，不分裂） |

---

## 2. 方案选型

### 2.1 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|---|---|---|---|
| **A. 完整 apps/+packages/** | odap→apps/api/odap、frontend→apps/web、子模块→packages/ | 语义最清晰，符合主流范式，未来扩展无痛 | 一次性迁移量大，路径需全面更新 |
| B. 平铺 workspace | odap/frontend 留原位，仅加 workspace 配置 | 迁移最小，风险低 | 不符合选定范式，语义模糊，未来仍需重构 |
| C. 折中 | odap/frontend 留原位 + packages/ 放子模块 + 预留 apps/ | 为未来留位 | apps/ 当前为空，违背统一布局初衷 |

### 2.2 推荐：方案 A

**理由**：
- 用户明确选择 apps/packages 范式，方案 B/C 是妥协而非落实
- 一次性迁移避免"先平铺、半年后又迁"的二次成本
- `odap` 包名保留 → Python import 零改动
- `git mv` 保留历史，blame 友好
- uv workspace 原生支持子模块作为 workspace 成员

---

## 3. 目标目录结构

### 3.1 顶层布局

```
ontology-graphiti/                       # monorepo 根
├── apps/                                # 可部署应用
│   ├── api/                             #   后端 FastAPI 应用（原 odap/）
│   │   ├── pyproject.toml               #   新增：声明 odap 包
│   │   ├── odap/                        #   后端代码（包名不变，import 零改动）
│   │   ├── main.py                      #   CLI 入口（原根 main.py）
│   │   ├── bootstep.py                  #   容器编排入口（原根 bootstep.py）
│   │   └── tests/                       #   后端测试（原 tests/unit + tests/integration）
│   └── web/                             #   前端 Vite 应用（原 frontend/）
│       ├── package.json                 #   name: @odap/web
│       ├── tsconfig*.json
│       ├── vite.config.ts
│       ├── vitest.config.ts
│       ├── eslint.config.js
│       ├── index.html
│       ├── Dockerfile
│       ├── Dockerfile.dev
│       ├── public/
│       └── src/
├── packages/                            # 可复用包
│   ├── openharness/                     #   git 子模块（.gitmodules path 改此）
│   │   └── pyproject.toml
│   └── hyper-extract/                  #   git 子模块
│       └── pyproject.toml
├── docker/                              # 容器配置（保留原位）
│   ├── Dockerfile                       #   后端生产镜像
│   ├── Dockerfile.dev                   #   后端开发镜像
│   ├── Dockerfile.node-base
│   ├── Dockerfile.crawl4ai
│   ├── Dockerfile.browser-use
│   ├── docker-compose.yml               #   生产
│   ├── docker-compose.dev.yml           #   开发
│   ├── docker-compose.test.yml
│   └── podman-compose-win-fix.py
├── docs/                                # 文档（保留原位）
├── specs/                               # spec-kit 规格文件（保留原位）
├── scripts/                             # 顶层脚本（保留原位）
├── config/                              # 顶层配置（保留原位）
├── tests/                               # 仅保留跨包 e2e/perf/helpers
│   ├── e2e/
│   ├── perf/
│   └── helpers/
├── .github/workflows/                   # CI（路径适配）
├── .gitmodules                          # path = packages/openharness 等
├── pyproject.toml                       # 根 workspace + 共享工具配置
├── pnpm-workspace.yaml                  # 前端 workspace 根
├── uv.lock                              # Python 统一锁文件（新增）
├── pnpm-lock.yaml                       # 前端统一锁文件（迁自 frontend/）
├── .npmrc                               # 视内容决定迁根或留 apps/web/
├── .env.example
├── .dockerignore                        # 适配新结构
├── .gitignore
├── README.md
├── AGENTS.md                            # 所有路径同步更新
└── overview.md
```

### 3.2 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| `odap` 包名是否保留 | **保留** | `from odap.biz import ...` 所有 import 零改动，迁移风险骤降 |
| 后端应用目录名 | `apps/api/` | 通用命名，前端对齐 `apps/web/` |
| `bootstep.py` 位置 | `apps/api/` | 后端容器编排，跟后端绑定 |
| `main.py` 位置 | `apps/api/` | 本地 CLI 入口，跟后端绑定 |
| 测试组织 | 单元/集成跟代码走，e2e/perf 留根 | 职责清晰，避免跨包 fixture 混杂 |
| 子模块路径 | `packages/openharness` / `packages/hyper-extract` | 与目录布局一致 |
| `package-lock.json` | **删除** | 与 `pnpm-lock.yaml` 双锁冲突 |
| `requirements.txt` | **删除** | 由 `uv.lock` 替代，Dockerfile 改用 `uv sync` |
| `docker-compose.override.yml` | **删除** | AGENTS.md 已标注弃用 |

### 3.3 迁移路径概览

```bash
# 后端
git mv odap apps/api/odap
git mv main.py apps/api/main.py
git mv bootstep.py apps/api/bootstep.py
# 后端测试
git mv tests/__init__.py apps/api/tests/__init__.py
git mv tests/conftest.py apps/api/tests/conftest.py
git mv tests/run_tests.py apps/api/tests/run_tests.py
git mv tests/README.md apps/api/tests/README.md
git mv tests/TEST_PLAN.md apps/api/tests/TEST_PLAN.md
git mv tests/unit apps/api/tests/unit
git mv tests/integration apps/api/tests/integration
# 前端
git mv frontend apps/web
# 子模块
git mv openharness packages/openharness
git mv hyper-extract packages/hyper-extract
git submodule sync
git submodule update --init --recursive
# 锁文件
git mv frontend/pnpm-lock.yaml pnpm-lock.yaml
# 清理
git rm apps/web/package-lock.json
git rm apps/web/pnpm-workspace.yaml
git rm docker/docker-compose.override.yml
git rm requirements.txt
```

---

## 4. Python Workspace 配置

### 4.1 根 `pyproject.toml`

```toml
[project]
name = "odap-monorepo"
version = "0.1.0"
description = "ODAP Monorepo - Ontology-Driven Analysis & Decision Platform"
requires-python = ">=3.10"

[tool.uv.workspace]
members = [
    "apps/api",
    "packages/openharness",
    "packages/hyper-extract",
]

[tool.uv.sources]
openharness-ai = { workspace = true }
hyperextract   = { workspace = true }

[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
    "ruff>=0.5.0",
    "black>=23.0.0",
    "flake8>=6.1.0",
]

[tool.pytest.ini_options]
testpaths = ["apps/api/tests", "tests"]
asyncio_mode = "auto"
markers = [
    "unit: 单元测试",
    "integration: 集成测试（需要外部服务）",
    "slow: 慢速测试",
    "e2e: 端到端测试",
    "smoke: 冒烟测试（核心功能快速验证，<60s）",
    "regression: 回归测试",
    "perf: 性能基准测试",
    "docker: 需要 Docker/Podman 容器的测试",
]
addopts = "-v --tb=short --strict-markers"
filterwarnings = ["ignore::DeprecationWarning"]

[tool.pytest-asyncio]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py310"
```

### 4.2 `apps/api/pyproject.toml`（新增）

```toml
[project]
name = "odap"
version = "0.1.0"
description = "ODAP Backend API - FastAPI + Graphiti"
requires-python = ">=3.10"
dependencies = [
    # 图谱
    "neo4j>=5.0.0",
    "networkx>=2.8.0",
    "rank_bm25>=0.2.2",
    # 权限
    "opa-python",
    # Web 框架
    "flask",
    "fastapi",
    "uvicorn",
    # 数据处理
    "pandas", "numpy", "requests", "beautifulsoup4",
    "python-dateutil", "jsonpickle", "pyyaml>=6.0",
    # 任务队列
    "celery>=5.3.0",
    # Pydantic / HTTP / Auth
    "pydantic>=2.0.0", "httpx>=0.25.0", "redis>=5.0.0",
    "python-jose[cryptography]>=3.3.0",
    "pyjwt>=2.8.0", "bcrypt>=4.1.0", "python-multipart>=0.0.6",
    "openai>=1.0.0", "aiohttp>=3.9.0", "aiofiles>=23.0.0",
    "minio>=7.0.0",
    # DB drivers
    "sqlalchemy>=2.0.0", "psycopg2-binary>=2.9.0", "pymysql>=1.1.0",
    # 文档解析
    "PyPDF2>=3.0.0", "python-docx>=1.0.0", "openpyxl>=3.1.0",
    "pytesseract>=0.3.10", "Pillow>=10.0.0",
    # 可观测性
    "opentelemetry-api>=1.25.0",
    "opentelemetry-sdk>=1.25.0",
    "opentelemetry-exporter-otlp-proto-http>=1.25.0",
    "opentelemetry-instrumentation-fastapi>=0.46b0",
    "prometheus-client>=0.20.0",
    # workspace 依赖（name-only，由根 [tool.uv.sources] 解析）
    "openharness-ai",
    "hyperextract",
    "langchain>=0.1.0",
    "langchain-openai>=0.1.0",
    "langchain-community>=0.1.0",
    "faiss-cpu>=1.7.0",
]

[project.optional-dependencies]
graph = ["graphiti-core>=0.28.0"]
crawl4ai = ["crawl4ai>=0.6.0"]
embedder = ["sentence-transformers>=2.2.0"]

[project.scripts]
odap-api = "odap.web.app:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["odap"]
```

### 4.3 子模块 `pyproject.toml`

保持原内容不变。`packages/openharness/pyproject.toml` 和 `packages/hyper-extract/pyproject.toml` 均为合法 hatchling 包，uv workspace 通过 `members` 列表自动识别。

> 注意：`packages/openharness/pyproject.toml` 的 `[tool.hatch.build.targets.wheel.force-include]` 引用了 `frontend/terminal/...`，这是子模块内部事务，不影响 monorepo 结构。

### 4.4 常用工作流命令

| 操作 | 旧命令 | 新命令 |
|---|---|---|
| 安装所有依赖 | `pip install -r requirements.txt` | `uv sync` |
| 仅装生产依赖 | — | `uv sync --no-dev --extra graph` |
| 添加后端依赖 | 改 `requirements.txt` | `cd apps/api && uv add <pkg>` |
| 添加 dev 依赖 | 改 `requirements.txt` | `uv add --dev <pkg>`（在根） |
| 运行后端测试 | `pytest tests/unit/` | `uv run pytest apps/api/tests/unit/` |
| 运行后端 | `python main.py --web` | `uv run python apps/api/main.py --web` |
| 在子模块内开发 | `cd openharness && ...` | `cd packages/openharness && uv run ...` |

### 4.5 graphiti-core 容错机制

- **本地开发**：`uv sync --extra graph`（失败时降级到 Neo4j Driver 模式，GraphManager 内部已实现 fallback）
- **镜像构建**：Dockerfile 中保留 `pip install graphiti-core || echo WARNING` 的容错行

---

## 5. 前端 Workspace 配置

### 5.1 根 `pnpm-workspace.yaml`

```yaml
packages:
  - "apps/web"

allowBuilds:
  canvas: true
  esbuild: true
```

### 5.2 `apps/web/package.json` 改动

```jsonc
{
  "name": "@odap/web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "packageManager": "pnpm@9.15.0",
  "scripts": { /* 不变 */ },
  "dependencies": { /* 不变 */ },
  "devDependencies": { /* 不变 */ }
}
```

**改动汇总**：

| 字段 | 原值 | 新值 | 理由 |
|---|---|---|---|
| `name` | `"frontend"` | `"@odap/web"` | scope 命名，避免冲突，明确归属 |
| `version` | `"0.0.0"` | `"0.1.0"` | 起步版本对齐后端 |
| `packageManager` | 无 | `"pnpm@9.15.0"` | corepack 自动激活，避免环境差异 |

### 5.3 文件迁移表

| 文件 | 原位置 | 新位置/动作 |
|---|---|---|
| `pnpm-workspace.yaml` | `frontend/pnpm-workspace.yaml` | 迁到根（workspace 根必须在仓库根） |
| `pnpm-lock.yaml` | `frontend/pnpm-lock.yaml` | 迁到根（锁文件跟 workspace 根走） |
| `package-lock.json` | `frontend/package-lock.json` | **删除**（双锁冲突） |
| `.npmrc` | `frontend/.npmrc` | 判断标准：含 `registry=` / `shamefully-hoist=` 等全局配置则迁根；仅含 `save-exact` 等包级配置则留 `apps/web/.npmrc`。迁移前先 Read 内容决定 |
| `.utoo.toml` | `frontend/.utoo.toml` | 保留 `apps/web/.utoo.toml` |
| `tsconfig*.json` | `frontend/` | `apps/web/` |
| `vite.config.ts` / `vitest.config.ts` / `eslint.config.js` | `frontend/` | `apps/web/` |
| `index.html` | `frontend/` | `apps/web/` |
| `Dockerfile` / `Dockerfile.dev` | `frontend/` | `apps/web/` |
| `public/` / `src/` | `frontend/` | `apps/web/` |

### 5.4 常用工作流命令

| 操作 | 旧命令 | 新命令 |
|---|---|---|
| 安装前端依赖 | `cd frontend && pnpm install` | `pnpm install`（在根） |
| 添加前端依赖 | `cd frontend && pnpm add <pkg>` | `pnpm --filter @odap/web add <pkg>` |
| 启动 dev server | `cd frontend && pnpm dev` | `pnpm --filter @odap/web dev` |
| 类型检查 | `cd frontend && pnpm typecheck` | `pnpm --filter @odap/web typecheck` |
| 构建 | `cd frontend && pnpm build` | `pnpm --filter @odap/web build` |
| 测试 | `cd frontend && pnpm test` | `pnpm --filter @odap/web test` |

### 5.5 未来扩展位

本次不预创以下目录，遵循 YAGNI：
- `packages/shared-ui/`：从 `apps/web/src/modules/shared/` 抽出的通用组件
- `packages/api-client/`：由后端 OpenAPI 自动生成的 TypeScript 客户端

---

## 6. 子模块迁移与 Docker 适配

### 6.1 子模块迁移

```bash
git mv openharness packages/openharness
git mv hyper-extract packages/hyper-extract
git submodule sync
git submodule update --init --recursive
git submodule status
```

迁移后 `.gitmodules`：

```ini
[submodule "openharness"]
    path = packages/openharness
    url = https://github.com/HKUDS/OpenHarness.git
[submodule "hyper-extract"]
    path = packages/hyper-extract
    url = https://github.com/yifanfeng97/Hyper-Extract.git
```

### 6.2 后端生产 Dockerfile（`docker/Dockerfile`）

```dockerfile
FROM localhost/python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV ENVIRONMENT production
ENV UV_PROJECT_ENVIRONMENT=/usr/local
ENV UV_LINK_MODE=copy

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ tesseract-ocr tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# ─── 阶段 1：复制 workspace 元数据（层缓存友好） ───
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml ./apps/api/
COPY packages/openharness/pyproject.toml ./packages/openharness/
COPY packages/hyper-extract/pyproject.toml ./packages/hyper-extract/

# 子模块源码（editable install 需要）
COPY packages/openharness ./packages/openharness
COPY packages/hyper-extract ./packages/hyper-extract

# ─── 阶段 2：安装依赖 ───
RUN uv sync --frozen --no-dev --package odap

# graphiti-core 容错（保持原版降级行为）
RUN pip install --no-cache-dir graphiti-core \
    || echo "WARNING: graphiti-core install failed, fallback to Neo4j Driver mode (non-fatal)"

# ─── 阶段 3：复制后端源码（最常变，放最后） ───
COPY apps/api/odap ./apps/api/odap
COPY apps/api/main.py ./apps/api/main.py

RUN mkdir -p /app/data

EXPOSE 8000

WORKDIR /app/apps/api
CMD ["python", "-m", "uvicorn", "odap.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 6.3 后端开发 Dockerfile（`docker/Dockerfile.dev`）

```dockerfile
FROM localhost/python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV ENVIRONMENT development
ENV UV_PROJECT_ENVIRONMENT=/usr/local
ENV UV_LINK_MODE=copy

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ tesseract-ocr tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml ./apps/api/
COPY packages/openharness ./packages/openharness
COPY packages/hyper-extract ./packages/hyper-extract

RUN uv sync --frozen --package odap
RUN pip install --no-cache-dir graphiti-core \
    || echo "WARNING: graphiti-core install failed (non-fatal)"

EXPOSE 8000
WORKDIR /app/apps/api
CMD ["python", "-m", "uvicorn", "odap.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.4 前端生产 Dockerfile（`apps/web/Dockerfile`）

```dockerfile
FROM localhost/node-base:24 AS builder
WORKDIR /workspace

COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/
RUN pnpm install --frozen-lockfile --filter @odap/web

COPY apps/web/ ./apps/web/
WORKDIR /workspace/apps/web
RUN pnpm build

FROM localhost/nginx:alpine
COPY --from=builder /workspace/apps/web/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 6.5 前端开发 Dockerfile（`apps/web/Dockerfile.dev`）

```dockerfile
FROM localhost/node-base:24
WORKDIR /workspace

COPY pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/
RUN pnpm install --frozen-lockfile --filter @odap/web

WORKDIR /workspace/apps/web
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
```

### 6.6 `docker-compose.dev.yml`（开发，前后端热更新）

```yaml
services:
  app:
    image: localhost/docker_app:latest
    container_name: graphiti-dev-app
    ports:
      - "8000:8000"
    env_file:
      - ../.env.docker
    environment:
      - IN_DOCKER=true
      - ENVIRONMENT=development
      - NEO4J_URI=bolt://graphiti-neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=neo4j123456
      - OPA_URL=http://graphiti-policy-service:8181
      - REDIS_URL=redis://graphiti-cache:6379
      - MINIO_ENDPOINT=graphiti-minio:9000
      - MINIO_ACCESS_KEY=${MINIO_ROOT_USER:-minioadmin}
      - MINIO_SECRET_KEY=${MINIO_ROOT_PASSWORD:-minioadmin}
      - MINIO_SECURE=false
      - CORS_ORIGINS=http://localhost,http://localhost:5173,http://localhost:8000
    depends_on:
      - graphiti-neo4j
      - graphiti-policy-service
      - graphiti-cache
      - graphiti-minio
    volumes:
      - ../apps/api/odap:/app/apps/api/odap
      - ../apps/api/main.py:/app/apps/api/main.py
      - ../packages/openharness:/app/packages/openharness
      - ../packages/hyper-extract:/app/packages/hyper-extract
      - ../data:/app/data
    working_dir: /app/apps/api
    networks: [graphiti-network]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 30s
    command: ["python", "-m", "uvicorn", "odap.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/apps/api/odap"]

  frontend:
    build:
      context: ..
      dockerfile: apps/web/Dockerfile.dev
    image: localhost/docker_frontend:dev
    container_name: graphiti-dev-frontend
    ports:
      - "5173:5173"
    working_dir: /workspace/apps/web
    volumes:
      - ../pnpm-workspace.yaml:/workspace/pnpm-workspace.yaml
      - ../pnpm-lock.yaml:/workspace/pnpm-lock.yaml
      - ../apps/web/package.json:/workspace/apps/web/package.json
      - ../apps/web/src:/workspace/apps/web/src
      - ../apps/web/public:/workspace/apps/web/public
      - ../apps/web/index.html:/workspace/apps/web/index.html
      - ../apps/web/vite.config.ts:/workspace/apps/web/vite.config.ts
      - ../apps/web/vitest.config.ts:/workspace/apps/web/vitest.config.ts
      - ../apps/web/tsconfig.json:/workspace/apps/web/tsconfig.json
      - ../apps/web/tsconfig.app.json:/workspace/apps/web/tsconfig.app.json
      - ../apps/web/tsconfig.node.json:/workspace/apps/web/tsconfig.node.json
      - ../apps/web/eslint.config.js:/workspace/apps/web/eslint.config.js
      - ../apps/web/.env.development:/workspace/apps/web/.env.development
      - ../apps/web/.env.production:/workspace/apps/web/.env.production
    environment:
      - NODE_ENV=development
      - VITE_API_BASE=
      - PROXY_TARGET=http://graphiti-dev-app:8000
    networks: [graphiti-network]
    restart: unless-stopped
    command: ["sh", "-c", "cd /workspace && pnpm install --frozen-lockfile 2>&1 | tail -3; pnpm --filter @odap/web dev --host 0.0.0.0"]

  graphiti-neo4j:
    # 配置与原版完全相同（略）
  graphiti-policy-service:
    volumes:
      - ../apps/api/odap/infra/opa/policies:/policies
    # 其余配置与原版相同
  graphiti-minio:
    # 配置与原版完全相同（略）
  graphiti-cache:
    # 配置与原版完全相同（略）

volumes:
  neo4j-data:
  neo4j-logs:
  redis-data:
  minio_data:
networks:
  graphiti-network:
    driver: bridge
```

> 注：`graphiti-neo4j` / `graphiti-minio` / `graphiti-cache` 三个基础设施服务的配置与迁移前完全相同，不影响 monorepo 结构，故在此省略详细展开。完整配置参考原版 `docker-compose.dev.yml`。

### 6.7 `docker-compose.yml`（生产）

```yaml
services:
  app:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: graphiti-main-app
    ports: ["8000:8000"]
    env_file: [../.env.docker]
    environment: [/* 不变 */]
    depends_on: [/* 不变 */]
    volumes:
      - app-data:/app/data
    networks: [graphiti-network]
    restart: unless-stopped
    healthcheck: [/* 不变 */]

  frontend:
    build:
      context: ..
      dockerfile: apps/web/Dockerfile
    container_name: graphiti-frontend
    ports: ["8080:80"]
    depends_on: [app]
    networks: [graphiti-network]
    restart: unless-stopped

  graphiti-neo4j:
    # 配置与原版完全相同（略）
  graphiti-policy-service:
    volumes:
      - ../apps/api/odap/infra/opa/policies:/policies
    # 其余配置与原版相同
  graphiti-minio:
    # 配置与原版完全相同（略）
  graphiti-cache:
    # 配置与原版完全相同（略）

volumes:
  neo4j-data:
  neo4j-logs:
  redis-data:
  app-data:
  minio_data:

networks:
  graphiti-network:
    driver: bridge
```

> 注：`graphiti-neo4j` / `graphiti-minio` / `graphiti-cache` 三个基础设施服务配置不变，完整配置参考原版 `docker-compose.yml`。

### 6.8 `bootstep.py` 适配

`apps/api/bootstep.py` 路径常量更新：

```python
APP_DIR = os.path.dirname(os.path.abspath(__file__))
MONOREPO_ROOT = os.path.dirname(os.path.dirname(APP_DIR))  # apps/api/ → 根
DOCKER_DIR = os.path.join(MONOREPO_ROOT, "docker")
COMPOSE_FILE = os.path.join(DOCKER_DIR, "docker-compose.yml")
COMPOSE_DEV = os.path.join(DOCKER_DIR, "docker-compose.dev.yml")
# ... 其余常量
```

调用方式：`python apps/api/bootstep.py dev`

### 6.9 热更新与稳定部署保障矩阵

| 场景 | 保障机制 |
|---|---|
| 后端热更新（dev） | bind mount `apps/api/odap/` + `uvicorn --reload --reload-dir /app/apps/api/odap`，2-3s 自动重启 |
| 前端热更新（dev） | bind mount `apps/web/src/` + Vite HMR，<1s 无刷新更新 |
| 子模块热更新（dev） | bind mount `packages/*`，容器看到最新源码 |
| 生产稳定部署 | 多阶段构建（前端）+ 元数据/源码分层（后端）+ 健康检查 + `--frozen` 锁定依赖 + 无 bind mount |
| 依赖可重现 | `uv.lock` + `pnpm-lock.yaml` 双锁，CI 用 `--frozen-lockfile` |
| 降级容错 | `graphiti-core` 安装失败仅警告，GraphManager 内部 Neo4j Driver fallback |

---

## 7. 测试组织

### 7.1 测试目录重组

| 原位置 | 新位置 | 说明 |
|---|---|---|
| `tests/__init__.py` | `apps/api/tests/__init__.py` | git mv |
| `tests/conftest.py` | `apps/api/tests/conftest.py` | git mv（需 Read 内容确认无跨包 fixture） |
| `tests/run_tests.py` | `apps/api/tests/run_tests.py` | git mv |
| `tests/README.md` | `apps/api/tests/README.md` | git mv |
| `tests/TEST_PLAN.md` | `apps/api/tests/TEST_PLAN.md` | git mv |
| `tests/unit/` | `apps/api/tests/unit/` | git mv（全部后端单元测试） |
| `tests/integration/` | `apps/api/tests/integration/` | git mv（后端集成测试） |
| `tests/e2e/` | `tests/e2e/` | 保留根（跨包 e2e） |
| `tests/perf/` | `tests/perf/` | 保留根（跨包性能） |
| `tests/helpers/` | `tests/helpers/` | 保留根（跨包共享 fixture） |

### 7.2 `conftest.py` 拆分策略

1. 迁移前 Read `tests/conftest.py` 全文
2. 把"后端专属 fixture"留在 `apps/api/tests/conftest.py`
3. 把"跨包 fixture"（如 api_client、工厂函数等）保留/新建到根 `tests/conftest.py`
4. 若内容混合难以拆分，短期**复制**到两处；待 e2e 测试验证通过后，再按需清理重复 fixture

### 7.3 根 pytest 配置

```toml
[tool.pytest.ini_options]
testpaths = ["apps/api/tests", "tests"]
```

---

## 8. 迁移执行步骤

> **前置条件**：所有活跃分支已合并到 main，工作区干净，已 push 备份。

### Step 0：准备分支与备份

```bash
git checkout main
git pull origin main
git checkout -b refactor/monorepo-restructure
git tag pre-monorepo-backup
```

### Step 1：创建目录骨架

```bash
mkdir -p apps/api apps/web packages
mkdir -p apps/api/tests
```

### Step 2：git mv 主体文件（保留历史）

```bash
# 后端
git mv odap apps/api/odap
git mv main.py apps/api/main.py
git mv bootstep.py apps/api/bootstep.py

# 后端测试
git mv tests/__init__.py apps/api/tests/__init__.py
git mv tests/conftest.py apps/api/tests/conftest.py
git mv tests/run_tests.py apps/api/tests/run_tests.py
git mv tests/README.md apps/api/tests/README.md
git mv tests/TEST_PLAN.md apps/api/tests/TEST_PLAN.md
git mv tests/unit apps/api/tests/unit
git mv tests/integration apps/api/tests/integration

# 前端
git mv frontend apps/web

# 子模块
git mv openharness packages/openharness
git mv hyper-extract packages/hyper-extract
git submodule sync
git submodule update --init --recursive
```

### Step 3：清理旧文件

```bash
git rm apps/web/package-lock.json
git rm apps/web/pnpm-workspace.yaml
git rm docker/docker-compose.override.yml
git rm requirements.txt
```

### Step 4：创建新配置文件

- 根 `pyproject.toml`（覆盖原有 pytest 配置，新增 workspace 配置）
- 根 `pnpm-workspace.yaml`
- `apps/api/pyproject.toml`（新增）
- `pnpm-lock.yaml`（由 `apps/web/pnpm-lock.yaml` 迁到根）
- `.npmrc`：Read 内容后决定迁根或留 `apps/web/`

### Step 5：更新现有配置文件

- `apps/web/package.json`（改 name、加 packageManager）
- `apps/web/Dockerfile`（改为多阶段）
- `apps/web/Dockerfile.dev`（改写）
- `docker/Dockerfile`（改写）
- `docker/Dockerfile.dev`（改写）
- `docker/docker-compose.yml`（路径更新）
- `docker/docker-compose.dev.yml`（路径更新）
- `apps/api/bootstep.py`（路径常量更新）

### Step 6：生成 uv.lock 并验证

```bash
uv sync
ls uv.lock
```

### Step 7：更新 CI workflow

- `.github/workflows/ci.yml`
- `.github/workflows/quality-gate.yml`
- `.github/workflows/test.yml`

### Step 8：更新文档

见 [第 11 节：文档同步清单](#11-文档同步清单)

### Step 9：本地验证

```bash
# Python
uv sync
uv run pytest apps/api/tests/unit/ -x --tb=short -k "smoke"

# 前端
pnpm install
pnpm --filter @odap/web typecheck
pnpm --filter @odap/web lint
pnpm --filter @odap/web build
```

### Step 10：容器验证

```bash
python apps/api/bootstep.py rebuild main
python apps/api/bootstep.py rebuild frontend
python apps/api/bootstep.py dev
python apps/api/bootstep.py status
curl http://localhost:8000/health
curl http://localhost:5173
# 热更新验证（见验证清单）
python apps/api/bootstep.py down
```

### Step 11：提交

```bash
git add .
git status
git commit -m "refactor: restructure to monorepo with uv + pnpm workspace

- apps/api: backend FastAPI app (was odap/, main.py, bootstep.py)
- apps/web: frontend Vite app (was frontend/)
- packages/openharness, packages/hyper-extract: git submodules
- root pyproject.toml: uv workspace + shared dev deps
- root pnpm-workspace.yaml: pnpm workspace root
- docker/: build context → monorepo root, path constants updated
- bootstep.py: moved to apps/api/, MONOREPO_ROOT path resolution
- tests/: unit/integration moved to apps/api/tests/, e2e/perf stay at root
- AGENTS.md, docs/, CI workflows: path sync

Refs: ADR-066"
```

---

## 9. 验证清单

### 9.1 依赖验证

| # | 检查项 | 命令 | 期望 |
|---|---|---|---|
| 1 | uv.lock 存在且同步 | `uv lock --check` | exit 0 |
| 2 | pnpm-lock.yaml 存在且同步 | `pnpm install --frozen-lockfile` | exit 0 |
| 3 | import odap 成功 | `uv run python -c "import odap; print(odap.__file__)"` | 打印路径 |
| 4 | import openharness 成功 | `uv run python -c "import openharness; print('ok')"` | ok |
| 5 | import hyperextract 成功 | `uv run python -c "import hyperextract; print('ok')"` | ok |

### 9.2 测试验证

| # | 检查项 | 命令 |
|---|---|---|
| 6 | 后端单元测试通过 | `uv run pytest apps/api/tests/unit/ -x` |

### 9.3 前端验证

| # | 检查项 | 命令 |
|---|---|---|
| 7 | typecheck 通过 | `pnpm --filter @odap/web typecheck` |
| 8 | lint 通过 | `pnpm --filter @odap/web lint` |
| 9 | 构建通过 | `pnpm --filter @odap/web build` |

### 9.4 容器验证

| # | 检查项 | 命令 |
|---|---|---|
| 10 | 后端镜像构建成功 | `python apps/api/bootstep.py rebuild main` |
| 11 | 前端镜像构建成功 | `python apps/api/bootstep.py rebuild frontend` |
| 12 | dev 环境启动成功 | `python apps/api/bootstep.py dev` |
| 13 | 后端健康检查通过 | `curl http://localhost:8000/health` |
| 14 | 前端可访问 | `curl http://localhost:5173` |

### 9.5 热更新验证

| # | 检查项 | 操作 |
|---|---|---|
| 15 | 后端 .py 变更触发 reload | 修改 `apps/api/odap/web/app.py`，查看日志确认 uvicorn reload |
| 16 | 前端 .tsx 变更触发 HMR | 修改 `apps/web/src/App.tsx`，浏览器确认无刷新更新 |

### 9.6 其他验证

| # | 检查项 | 命令 |
|---|---|---|
| 17 | 子模块状态正常 | `git submodule status` |
| 18 | AGENTS.md 路径已同步 | `grep -r "odap/" docs/ AGENTS.md specs/` 确认无遗漏 |

---

## 10. 风险与回滚

### 10.1 风险点与缓解

| 风险 | 缓解措施 |
|---|---|
| `git mv` 后子模块状态异常 | Step 2 后立即 `git submodule sync && git submodule update --init --recursive` 验证 |
| `tests/conftest.py` 含跨包 fixture | Step 2 前 Read 内容，按需拆分到 `apps/api/tests/conftest.py` + 根 `tests/conftest.py` |
| `uv sync` 因网络失败 | 配置清华 PyPI 镜像：`pip config set global.index-url ...` |
| 镜像构建失败 | 先用 `--no-cache` 重建，定位是 COPY 路径还是依赖问题 |
| 文档路径遗漏 | `grep -r "odap/" docs/ AGENTS.md specs/` 全面扫描 |
| 006/007 后续 merge 冲突 | 重构前已合并到 main，重构 commit 后新分支基于 main |

### 10.2 回滚策略

```bash
git checkout main
git branch -D refactor/monorepo-restructure
git tag -d pre-monorepo-backup
git submodule update --init --recursive
```

---

## 11. 文档同步清单

### 11.1 必同步文档

| 文档 | 同步内容 |
|---|---|
| `AGENTS.md` | §2.2 启动命令路径、§3.1 包结构树、§4.2 路由方案、§6.1 验证流程、附录 A 两个 Web 入口、附录 E 端到端流程、附录 F Git 提交规范 |
| `docs/03-modules/README.md` | 后端模块路径前缀 `odap/biz/` → `apps/api/odap/biz/`，前端模块路径 `frontend/src/modules/` → `apps/web/src/modules/` |
| `docs/03-modules/web_frontend/DESIGN.md` | 前端路径更新 |
| `docs/03-modules/ontology/DESIGN.md` | 代码路径引用更新 |
| `docs/03-modules/audit_log/DESIGN.md` | 代码路径引用更新 |
| `docs/09-checklists/DOC_SYNC_CHECKLIST.md` | 新增 monorepo 路径检查项 |
| `docs/07-adr/ADR-066-monorepo-restructure.md` | **新增**：记录本次重构的架构决策 |
| `docs/07-adr/README.md` | 索引更新，加入 ADR-066 |

### 11.2 spec-kit 规格文档

| 文档 | 同步内容 |
|---|---|
| `specs/006-he-extraction-chain/*.md` | 代码路径引用同步 |
| `specs/007-semantic-admin-suite/*.md` | 代码路径引用同步 |

### 11.3 CI 配置

| 文件 | 同步内容 |
|---|---|
| `.github/workflows/ci.yml` | 工作目录、命令路径更新 |
| `.github/workflows/quality-gate.yml` | 同上 |
| `.github/workflows/test.yml` | 同上 |

---

*文档结束*
