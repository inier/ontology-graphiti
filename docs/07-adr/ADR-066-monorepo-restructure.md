# ADR-066：Monorepo 重构（uv workspace + pnpm workspace）

> **状态**：已接受  
> **日期**：2026-07-16  
> **优先级**：P1  
> **关联文档**：[设计文档](../superpowers/specs/2026-07-16-monorepo-restructure-design.md)、[实施计划](../superpowers/specs/2026-07-16-monorepo-restructure-plan.md)

## 上下文

当前项目 `ontology-graphiti` 是"伪 monorepo"形态，存在以下痛点：

1. **3+ 套独立依赖文件**：根 `requirements.txt` + `openharness/pyproject.toml` + `hyper-extract/pyproject.toml` + `frontend/package.json`，无统一依赖图
2. **子模块路径不规范**：`openharness/` 和 `hyper-extract/` 直接放在仓库根，与业务代码混杂
3. **`odap/` 未声明为包**：无独立 `pyproject.toml`，靠 `pip install -r requirements.txt` 注入依赖
4. **前端双锁冲突**：`package-lock.json` + `pnpm-lock.yaml` 并存
5. **`pnpm-workspace.yaml` 位置错误**：放在 `frontend/` 子目录而非仓库根
6. **无统一构建/测试入口**：每个子项目各自为政

## 决策

采用标准 `apps/` + `packages/` monorepo 范式，统一依赖与构建工具链：

### 目录布局

```
ontology-graphiti/
├── apps/
│   ├── api/          # 后端 FastAPI 应用（原 odap/）
│   └── web/          # 前端 Vite 应用（原 frontend/）
├── packages/
│   ├── openharness/  # git 子模块
│   └── hyper-extract/  # git 子模块
├── docker/           # 容器配置
├── docs/             # 文档
├── tests/            # 跨包 e2e/perf
├── pyproject.toml    # uv workspace 根
├── pnpm-workspace.yaml  # pnpm workspace 根
├── uv.lock           # Python 统一锁文件
└── pnpm-lock.yaml    # 前端统一锁文件
```

### 工具链选择

| 维度 | 选择 | 理由 |
|---|---|---|
| Python 依赖管理 | uv workspace | 统一锁文件，原生 workspace 支持，性能优于 pip |
| 前端依赖管理 | pnpm workspace | 已有 pnpm 基础，锁文件统一到根 |
| 构建后端 | hatchling | 与子模块 pyproject.toml 一致 |
| 容器编排 | Podman + bootstep.py | 保持现有机制，仅更新路径 |

### 关键设计

1. **保留 `odap` 包名**：Python import 零改动，迁移风险骤降
2. **保留 git submodule**：维持上游同步能力，仅迁移路径到 `packages/`
3. **统一 workspace 视角**：开发与生产均为 workspace 视角，不分裂（避免 dev/prod 不一致）
4. **`UV_PROJECT_ENVIRONMENT=/usr/local`**：容器内 uv 装到系统 Python，与原版 uvicorn 启动方式兼容
5. **删除 `requirements.txt`**：由 `uv.lock` 替代，Dockerfile 改用 `uv sync`
6. **删除 `package-lock.json`**：统一 pnpm，避免双锁冲突

### 迁移策略

分 7 个提交，每个提交后系统保持可工作状态：
1. docs：设计文档 + ADR
2. refactor(submodules)：子模块迁到 packages/
3. refactor(backend)：后端迁到 apps/api/ + uv workspace
4. refactor(frontend)：前端迁到 apps/web/ + pnpm workspace
5. ci：CI 适配
6. docs：文档路径同步
7. test：验证并修复

## 影响

### 正面

- 统一依赖管理，消除多套锁文件不一致风险
- 目录语义清晰，应用 vs 可复用包边界明确
- 未来扩展（新增包/应用）无痛
- 开发与生产环境一致，测试可信度提升

### 负面

- 一次性迁移量大（但 git mv 保留历史）
- 需要学习 uv 工具链（团队已有 pip 经验）
- Dockerfile 改用 uv，镜像层需重新缓存

## 关联

- 替代：ADR-033（项目目录结构重构，本次为其演进版）
- 参考：[uv workspace 文档](https://docs.astral.sh/uv/concepts/projects/workspaces/)
- 参考：[pnpm workspace 文档](https://pnpm.io/workspaces)
