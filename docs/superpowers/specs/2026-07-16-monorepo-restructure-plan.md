# Monorepo 重构实施计划

> **对应设计文档**：[2026-07-16-monorepo-restructure-design.md](./2026-07-16-monorepo-restructure-design.md)  
> **日期**：2026-07-16  
> **前置条件**：所有活跃分支已合并到 main，工作区干净，已 push 备份  
> **目标分支**：`refactor/monorepo-restructure`

---

## Problem Statement

当前项目是"伪 monorepo"形态：3+ 套独立依赖文件、git 子模块管理复杂、`odap/` 未声明为包、前端双锁冲突、`pnpm-workspace.yaml` 位置错误。需要重构为标准 monorepo，统一依赖与构建工具链，明确应用与包的边界。

## Solution

采用 `apps/` + `packages/` 范式，Python 侧用 uv workspace、前端侧用 pnpm workspace。保留 `odap` 包名实现零 import 改动。保留 git submodule 机制，仅迁移路径到 `packages/`。开发与生产统一为 workspace 视角，支持热更新与稳定部署。

## Commits

将重构拆分为 **7 个提交**，每个提交后系统保持可工作状态。核心策略：**先移子模块 → 再移后端 → 最后移前端**，每步只动一个维度，过渡状态可工作。

---

### Commit 1: `docs: add monorepo restructure design and ADR-066`

**目的**：先落地设计文档和架构决策记录，不含任何代码变更。

**变更内容**：
- 新增 `docs/superpowers/specs/2026-07-16-monorepo-restructure-design.md`（设计文档）
- 新增 `docs/superpowers/specs/2026-07-16-monorepo-restructure-plan.md`（本计划）
- 新增 `docs/07-adr/ADR-066-monorepo-restructure.md`（架构决策记录）
- 更新 `docs/07-adr/README.md` 索引，加入 ADR-066

**验证**：文档可正常渲染，无代码影响。

---

### Commit 2: `refactor(submodules): move openharness and hyper-extract to packages/`

**目的**：先迁移 git 子模块到 `packages/` 目录，为后续 uv workspace 声明铺路。此步不引入 workspace 配置，仅改路径。

**变更内容**：
- `git mv openharness packages/openharness`
- `git mv hyper-extract packages/hyper-extract`
- `git submodule sync`
- `git submodule update --init --recursive`
- 更新 `.gitmodules`（`git mv` 自动完成）
- 更新 `requirements.txt` 中两个 `-e ./` 路径：
  - `-e ./openharness` → `-e ./packages/openharness`
  - `-e ./hyper-extract` → `-e ./packages/hyper-extract`

**过渡状态**：子模块在新位置，`requirements.txt` 路径已同步，`pip install -r requirements.txt` 仍可工作。其他代码/配置未动。

**验证**：
```bash
git submodule status                    # 两个子模块状态正常
pip install -r requirements.txt         # 依赖仍可安装
python -c "import openharness; print('ok')"  # import 正常
python -c "import hyperextract; print('ok')"
```

---

### Commit 3: `refactor(backend): move odap to apps/api/ and create uv workspace`

**目的**：迁移后端代码到 `apps/api/`，创建 uv workspace，删除 `requirements.txt`。前端仍在 `frontend/`（过渡状态）。

**变更内容**：

*目录迁移*：
- `git mv odap apps/api/odap`
- `git mv main.py apps/api/main.py`
- `git mv bootstep.py apps/api/bootstep.py`
- `mkdir -p apps/api/tests`
- `git mv tests/__init__.py apps/api/tests/__init__.py`
- `git mv tests/conftest.py apps/api/tests/conftest.py`
- `git mv tests/run_tests.py apps/api/tests/run_tests.py`
- `git mv tests/README.md apps/api/tests/README.md`
- `git mv tests/TEST_PLAN.md apps/api/tests/TEST_PLAN.md`
- `git mv tests/unit apps/api/tests/unit`
- `git mv tests/integration apps/api/tests/integration`
- 根 `tests/` 仅保留 `e2e/`、`perf/`、`helpers/`

*新建配置*：
- 新建 `apps/api/pyproject.toml`（声明 `odap` 包，含全部后端依赖，workspace 依赖 `openharness-ai` + `hyperextract`）
- 覆盖根 `pyproject.toml`（`[tool.uv.workspace]` 三个成员 + `[tool.uv.sources]` + 共享 dev 依赖 + pytest/ruff 配置，`testpaths = ["apps/api/tests", "tests"]`）

*删除旧文件*：
- `git rm requirements.txt`

*更新 `apps/api/tests/conftest.py`*：
- `project_root` 路径计算从 2 级 dirname 改为 3 级（`apps/api/tests/` → root）
  ```python
  # 旧: project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  # 新: project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
  ```

*更新 `apps/api/bootstep.py`*：
- 路径常量：
  ```python
  APP_DIR = os.path.dirname(os.path.abspath(__file__))           # apps/api/
  MONOREPO_ROOT = os.path.dirname(os.path.dirname(APP_DIR))      # 根
  DOCKER_DIR = os.path.join(MONOREPO_ROOT, "docker")
  ```
- `IMAGES_BUILD` 字典中 frontend 相关条目**暂不改动**（过渡期前端仍在 `frontend/`）

*更新 `docker/Dockerfile`*：
- 改用 `uv sync --frozen --no-dev --package odap`（见设计文档 §6.2）
- `COPY` 路径适配：`apps/api/pyproject.toml`、`packages/openharness`、`packages/hyper-extract`、`apps/api/odap`
- `WORKDIR /app/apps/api`

*更新 `docker/Dockerfile.dev`*：
- 同上，用 `uv sync --frozen --package odap`（见设计文档 §6.3）

*更新 `docker/docker-compose.yml`*：
- `app` 服务 build context 改为 `..`（monorepo 根）
- `graphiti-policy-service` 挂载路径改为 `../apps/api/odap/infra/opa/policies:/policies`
- `frontend` 服务**暂不改动**（仍在 `../frontend`）

*更新 `docker/docker-compose.dev.yml`*：
- `app` 服务 volumes 改为 `../apps/api/odap:/app/apps/api/odap` 等
- `app` 服务 `working_dir: /app/apps/api`
- `app` 服务 command 加 `--reload --reload-dir /app/apps/api/odap`
- `graphiti-policy-service` 挂载路径改为 `../apps/api/odap/infra/opa/policies:/policies`
- `frontend` 服务**暂不改动**（仍在 `../frontend`）

*删除 `docker/docker-compose.override.yml`*（已弃用）

*生成 `uv.lock`*：
- 运行 `uv sync` 生成锁文件

**过渡状态**：后端在 `apps/api/`，uv workspace 激活（3 个成员），前端仍在 `frontend/`。`bootstep.py` 和 `docker-compose` 的 frontend 路径暂指向旧位置。系统可工作但 frontend 路径不一致。

**验证**：
```bash
uv sync                                                    # 依赖安装成功
uv run python -c "import odap; print(odap.__file__)"       # import 成功
uv run python -c "import openharness; print('ok')"         # 子模块 import 成功
uv run pytest apps/api/tests/unit/ -x -k smoke             # 冒烟测试通过
python apps/api/bootstep.py status                         # bootstep 可运行
```

---

### Commit 4: `refactor(frontend): move frontend to apps/web/ and create pnpm workspace`

**目的**：迁移前端到 `apps/web/`，创建 pnpm workspace，完成目录重组最后一步。

**变更内容**：

*目录迁移*：
- `git mv frontend apps/web`
- `git mv apps/web/pnpm-lock.yaml pnpm-lock.yaml`（锁文件迁根）
- `git mv apps/web/.npmrc .npmrc`（含 `registry=` 全局配置，迁根）

*删除旧文件*：
- `git rm apps/web/package-lock.json`（双锁冲突）
- `git rm apps/web/pnpm-workspace.yaml`（旧的，迁根后删除）

*新建配置*：
- 新建根 `pnpm-workspace.yaml`（`packages: ["apps/web"]` + `allowBuilds`）

*更新 `apps/web/package.json`*：
- `name`: `"frontend"` → `"@odap/web"`
- `version`: `"0.0.0"` → `"0.1.0"`
- 新增 `"packageManager": "pnpm@9.15.0"`

*更新 `apps/web/Dockerfile`*（生产）：
- 多阶段构建，workspace 视角（见设计文档 §6.4）

*更新 `apps/web/Dockerfile.dev`*（开发）：
- workspace 视角，`WORKDIR /workspace/apps/web`（见设计文档 §6.5）

*更新 `docker/docker-compose.yml`*：
- `frontend` 服务 build context 改为 `..`，dockerfile 改为 `apps/web/Dockerfile`

*更新 `docker/docker-compose.dev.yml`*：
- `frontend` 服务完全重写（见设计文档 §6.6）：
  - build context `..`，dockerfile `apps/web/Dockerfile.dev`
  - `working_dir: /workspace/apps/web`
  - volumes 挂载 `pnpm-workspace.yaml`、`pnpm-lock.yaml`、`apps/web/*`
  - command 用 `pnpm --filter @odap/web dev --host 0.0.0.0`

*更新 `apps/api/bootstep.py`*：
- `IMAGES_BUILD` 字典中 frontend 条目：
  - `"dockerfile": "frontend/Dockerfile.dev"` → `"apps/web/Dockerfile.dev"`
  - `"context": "frontend"` → `"."`（monorepo 根）
  - `"dockerfile": "frontend/Dockerfile"` → `"apps/web/Dockerfile"`
  - `"context": "frontend"` → `"."`（monorepo 根）

*更新 `pnpm-lock.yaml`*：
- 运行 `pnpm install` 重新生成锁文件（包名从 `frontend` 变为 `@odap/web`）

**验证**：
```bash
pnpm install --frozen-lockfile                              # 锁文件同步
pnpm --filter @odap/web typecheck                           # 类型检查通过
pnpm --filter @odap/web lint                                # lint 通过
pnpm --filter @odap/web build                               # 构建通过
python apps/api/bootstep.py rebuild frontend                # 前端镜像构建成功
python apps/api/bootstep.py dev                             # dev 环境启动
curl http://localhost:5173                                  # 前端可访问
curl http://localhost:8000/health                           # 后端健康
# 热更新验证
python apps/api/bootstep.py down
```

---

### Commit 5: `ci: update workflows for monorepo structure`

**目的**：更新 GitHub Actions CI 适配新路径和工具链。

**变更内容**：

*`.github/workflows/ci.yml`*：
- `backend-test` job：
  - `pip install -r requirements.txt` → `pip install uv && uv sync`
  - `pytest tests/unit/` → `uv run pytest apps/api/tests/unit/`
  - `pytest tests/integration/` → `uv run pytest apps/api/tests/integration/`
  - checkout 需加 `submodules: recursive`
- `frontend-test` job：
  - `cd frontend && npm install` → `pnpm install`（在根）
  - `cd frontend && npm run typecheck` → `pnpm --filter @odap/web typecheck`
  - `cd frontend && npm run lint` → `pnpm --filter @odap/web lint`
  - `cd frontend && npm test` → `pnpm --filter @odap/web test`
  - Setup Node 改为 Setup pnpm（`pnpm/action-setup` + corepack）
- `build` job：
  - `docker build -t graphiti:latest -f docker/Dockerfile .` 不变（context 已是根）
  - `docker compose -f docker/docker-compose.yml up -d` 不变

*`.github/workflows/quality-gate.yml`*：
- 路径替换：`odap/` → `apps/api/odap/`、`frontend/` → `apps/web/`
- 命令替换：`pytest` → `uv run pytest`、`npm` → `pnpm --filter @odap/web`

*`.github/workflows/test.yml`*：
- 同 ci.yml 的路径和命令替换

**验证**：
```bash
# 本地模拟 CI 步骤
uv sync
uv run pytest apps/api/tests/unit/ -v --cov=odap --cov-report=xml
pnpm install
pnpm --filter @odap/web typecheck
pnpm --filter @odap/web lint
pnpm --filter @odap/web test
```

---

### Commit 6: `docs: sync all documentation paths for monorepo`

**目的**：同步所有文档中的路径引用，确保文档与代码一致（规则 12）。

**变更内容**：

*`AGENTS.md`*（全文路径同步）：
- §2.2 启动命令：`python bootstep.py dev` → `python apps/api/bootstep.py dev`
- §2.2.5 标准启动流程：所有 `bootstep.py` 调用加 `apps/api/` 前缀
- §2.2.6 关键文件速查：路径更新
- §3.1 包结构树：`odap/` → `apps/api/odap/`、`frontend/` → `apps/web/`
- §4.2 路由方案：`frontend/src/` → `apps/web/src/`
- §6.1 验证流程：`pytest tests/unit/` → `uv run pytest apps/api/tests/unit/`、`cd frontend && npm` → `pnpm --filter @odap/web`
- §7.1 命令矩阵：`pytest tests/unit/` → `uv run pytest apps/api/tests/unit/`、`cd frontend && npm` → `pnpm --filter @odap/web`
- 附录 A 两个 Web 入口：`odap/web/app.py` → `apps/api/odap/web/app.py`
- 附录 B 核心编码规则：路径示例更新
- 附录 E 端到端流程：无 API 路径变化，仅代码路径引用更新

*`docs/03-modules/README.md`*：
- 后端模块路径：`odap/biz/` → `apps/api/odap/biz/`
- 前端模块路径：`frontend/src/modules/` → `apps/web/src/modules/`

*`docs/03-modules/web_frontend/DESIGN.md`*：
- 所有 `frontend/` 路径引用 → `apps/web/`

*`docs/03-modules/ontology/DESIGN.md`*：
- 代码路径引用 `odap/` → `apps/api/odap/`

*`docs/03-modules/audit_log/DESIGN.md`*：
- 代码路径引用 `odap/` → `apps/api/odap/`

*`docs/09-checklists/DOC_SYNC_CHECKLIST.md`*：
- 新增 monorepo 路径检查项

*`specs/006-he-extraction-chain/*.md`*：
- 代码路径引用同步

*`specs/007-semantic-admin-suite/*.md`*：
- 代码路径引用同步

**验证**：
```bash
# 扫描遗漏的旧路径
grep -rn "[^/]odap/" docs/ AGENTS.md specs/ --include="*.md" | grep -v "apps/api/odap/" | grep -v "node_modules"
# 期望：无输出（或仅设计文档中的历史引用）
grep -rn "frontend/" docs/ AGENTS.md specs/ --include="*.md" | grep -v "apps/web/" | grep -v "node_modules"
# 期望：无输出（或仅设计文档中的历史引用）
```

---

### Commit 7: `test: verify monorepo structure and fix conftest paths`

**目的**：最终验证测试组织正确，修复可能的 fixture 路径问题。

**变更内容**：
- 检查 `apps/api/tests/conftest.py` 的 `project_root` 路径计算是否正确（Commit 3 已改，此步复查）
- 若根 `tests/e2e/` 或 `tests/perf/` 缺少 conftest 且需要后端 fixture，创建根 `tests/conftest.py` 导入必要 fixture
- 运行全量测试验证

**验证**：
```bash
# 后端单元测试
uv run pytest apps/api/tests/unit/ -x --tb=short

# 后端集成测试（需 Neo4j）
uv run pytest apps/api/tests/integration/ -x -v

# 跨包 e2e 测试
uv run pytest tests/e2e/ -x -v

# 子模块状态
git submodule status

# 容器最终验证
python apps/api/bootstep.py rebuild main
python apps/api/bootstep.py rebuild frontend
python apps/api/bootstep.py dev
python apps/api/bootstep.py status
curl http://localhost:8000/health
curl http://localhost:5173
# 后端热更新：修改 apps/api/odap/web/app.py，看日志
# 前端热更新：修改 apps/web/src/App.tsx，看浏览器
python apps/api/bootstep.py down
```

---

## Decision Document

### 模块变更

| 模块 | 变更类型 | 说明 |
|---|---|---|
| `apps/api/` | 新增 | 后端应用，原 `odap/` + `main.py` + `bootstep.py` + 后端测试 |
| `apps/web/` | 新增 | 前端应用，原 `frontend/` |
| `packages/openharness/` | 迁移 | git 子模块，原 `openharness/` |
| `packages/hyper-extract/` | 迁移 | git 子模块，原 `hyper-extract/` |
| 根 `pyproject.toml` | 重写 | uv workspace 入口 + 共享工具配置 |
| 根 `pnpm-workspace.yaml` | 新增 | pnpm workspace 根 |
| `uv.lock` | 新增 | Python 统一锁文件 |
| `pnpm-lock.yaml` | 迁移 | 从 `frontend/` 迁到根 |
| `.npmrc` | 迁移 | 从 `frontend/` 迁到根（含全局配置） |
| `requirements.txt` | 删除 | 由 `uv.lock` 替代 |
| `docker-compose.override.yml` | 删除 | 已弃用 |
| `package-lock.json` | 删除 | 双锁冲突 |

### 架构决策

- **uv workspace**：Python 侧统一依赖管理，`UV_PROJECT_ENVIRONMENT=/usr/local` 让容器内装到系统 Python
- **pnpm workspace**：前端侧统一依赖管理，锁文件在仓库根
- **保留 git submodule**：维持上游同步能力，仅迁移路径
- **保留 `odap` 包名**：零 import 改动，降低迁移风险
- **统一 workspace 视角**：开发与生产均为 workspace 视角，不分裂
- **Docker build context 统一为 monorepo 根**：让 Dockerfile 能访问 workspace 元数据

### 拆分策略

- **Commit 2 先移子模块**：因为 uv workspace 要求成员路径存在，子模块必须先就位
- **Commit 3 移后端**：引入 uv workspace，前端路径暂不改动（过渡状态可工作）
- **Commit 4 移前端**：引入 pnpm workspace，完成目录重组
- **每步后系统可工作**：bootstep.py 和 docker-compose 在过渡期容忍混合路径

## Testing Decisions

### 测试原则

- 只测外部行为，不测实现细节
- 每个提交后运行冒烟测试验证系统可工作
- 最终提交后运行全量测试

### 测试模块

| 测试范围 | 位置 | 验证内容 |
|---|---|---|
| 后端单元测试 | `apps/api/tests/unit/` | import 路径、CRUD、服务层逻辑 |
| 后端集成测试 | `apps/api/tests/integration/` | Neo4j 连接、API 端到端 |
| 跨包 e2e | `tests/e2e/` | 前后端联调 |
| 前端测试 | `apps/web/src/test/` | 组件渲染、交互 |
| 容器验证 | 手动 | 镜像构建、dev 启动、热更新 |

### 测试参考

- `tests/unit/conftest.py`：fixture 级联模式（mock_storage → manager）
- `tests/helpers/`：跨包共享 fixture（api_client、factories）

## Out of Scope

- **业务逻辑改动**：不修改任何业务代码，仅改目录结构和配置
- **Python import 路径改动**：`odap` 包名保留，所有 `from odap.xxx import yyy` 不变
- **API 路径改动**：所有 `/api/xxx` 路由不变
- **数据库 schema 改动**：无
- **新功能**：不引入 `packages/shared-ui/` 或 `packages/api-client/`（YAGNI）
- **根 `bootstep.py` shim**：不创建根目录代理脚本，直接用 `python apps/api/bootstep.py dev`

## Further Notes

### 回滚策略

```bash
git checkout main
git branch -D refactor/monorepo-restructure
git tag -d pre-monorepo-backup
git submodule update --init --recursive
```

### Commit 2-4 过渡状态说明

| Commit | 后端位置 | 前端位置 | 子模块位置 | uv workspace | pnpm workspace |
|---|---|---|---|---|---|
| 1 | `odap/` | `frontend/` | `openharness/` | ❌ | ❌ |
| 2 | `odap/` | `frontend/` | `packages/openharness/` | ❌ | ❌ |
| 3 | `apps/api/odap/` | `frontend/` | `packages/openharness/` | ✅ | ❌ |
| 4 | `apps/api/odap/` | `apps/web/` | `packages/openharness/` | ✅ | ✅ |

Commit 3 的过渡状态中，`bootstep.py` 和 `docker-compose` 的前端路径仍指向 `frontend/`，这是刻意的过渡设计，在 Commit 4 中统一修正。

### 风险点

| 风险 | 缓解 |
|---|---|
| `git mv` 子模块后状态异常 | Commit 2 后立即 `git submodule sync && git submodule update --init --recursive` |
| `uv sync` 网络失败 | 配置清华 PyPI 镜像 |
| `conftest.py` 路径计算错误 | Commit 3 中改为 3 级 dirname，Commit 7 复查 |
| `bootstep.py` IMAGES_BUILD 字典遗漏 | Commit 4 中统一更新 frontend 条目 |
| 文档路径遗漏 | Commit 6 中用 `grep -rn` 全面扫描 |

---

*计划结束*
