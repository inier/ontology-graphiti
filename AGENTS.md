# AGENTS.md - 代理工作指南

> 本文件记录在 ODAP (Ontology-Driven Analysis & Decision Platform) 代码库中工作的关键信息。

## 项目概述

ODAP 是一个通用的本体驱动分析决策平台，通过工作空间机制实现多场景隔离，支持任意领域的本体建模和分析决策。Graphiti 是本平台使用的双时态知识图谱组件。

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+, FastAPI, Neo4j (生产) / NetworkX (开发回退) |
| 前端 | React 19, TypeScript, Ant Design, G6, Leaflet |
| Agent 基础设施 | OpenHarness (子模块) |
| 知识图谱 | Graphiti (双时态知识图谱) |
| 策略治理 | OPA (开放策略代理) |
| LLM 支持 | OpenAI / Anthropic / DeepSeek |

---

## 核心命令

### 环境准备

```bash
# 安装后端依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend && npm install
```

### 本地开发（不依赖容器）

```bash
# 终端 1 - 启动后端
python main.py

# 终端 2 - 启动前端开发服务器
cd frontend && npm run dev
```

### Docker 部署（推荐）

项目提供 `bootstep.py` 一键管理脚本：

| 命令 | 说明 |
|------|------|
| `python bootstep.py pull` | 拉取基础镜像 |
| `python bootstep.py dev` | 开发模式（前端 HMR 热重载，访问 :5173） |
| `python bootstep.py up` | 生产模式（Nginx 静态服务，访问 :80） |
| `python bootstep.py status` | 查看服务状态 |
| `python bootstep.py logs` | 查看后端日志 |
| `python bootstep.py logs fe` | 查看前端生产日志 |
| `python bootstep.py logs fedev` | 查看前端开发日志 |
| `python bootstep.py down` | 停止所有服务 |
| `python bootstep.py rebuild` | 重新构建（生产模式） |
| `python bootstep.py clean` | 清理重复镜像和未使用资源 |

### 测试命令

```bash
# 后端单元测试（含覆盖率）
pytest tests/unit/ -v --cov=odap --cov-report=xml

# 后端集成测试（需要 MongoDB + Neo4j）
pytest tests/integration/ -v

# 后端所有测试
python -m pytest tests/ -v

# 前端测试
cd frontend && npm test

# 前端测试（监听模式）
cd frontend && npm run test:watch

# 前端测试（覆盖率）
cd frontend && npm run test:coverage

# 前端类型检查
cd frontend && npm run typecheck

# 前端 Lint 检查
cd frontend && npm run lint
```

### 构建命令

```bash
# 前端构建（生产）
cd frontend && npm run build

# Docker 镜像构建
docker build -t graphiti:latest -f docker/Dockerfile .
```

---

## 项目结构

```
ontology-graphiti/
├── app/                      # 主应用入口
├── assets/                   # 静态资源（HTML、图片等）
├── config/                   # 配置文件
├── docker/                   # Docker 配置
│   ├── Dockerfile            # 后端镜像
│   ├── docker-compose.yml    # 生产编排
│   └── docker-compose.override.yml  # 开发覆盖（热更新）
├── docs/                     # 架构文档和 ADR
├── frontend/                 # 前端项目（React + TypeScript）
│   ├── src/
│   │   ├── modules/         # 按业务功能模块组织
│   │   │   ├── agent/       # Agent 协同
│   │   │   ├── ontology/    # 本体管理
│   │   │   ├── workspace/   # 工作空间
│   │   │   ├── skill_system/# 技能系统
│   │   │   └── ...
│   │   └── pages/           # 页面组件
├── odap/                     # 核心业务逻辑
│   ├── biz/                 # 业务模块
│   │   ├── agent/           # Agent 协同模块
│   │   ├── cognition/       # 认知模块（OADA理解）
│   │   ├── ontology/        # 本体管理模块
│   │   ├── skill_system/    # 技能系统模块
│   │   ├── tool_registry/   # 工具注册表模块
│   │   ├── workspace/       # 工作空间管理模块
│   │   └── ...
│   ├── infra/              # 基础设施
│   │   ├── config/          # 配置管理
│   │   ├── graph/           # 图谱服务（Graphiti）
│   │   ├── llm/             # LLM 服务
│   │   ├── opa/             # OPA 策略
│   │   └── ...
│   ├── tools/              # 领域工具（Python Skills）
│   │   ├── intelligence/   # 情报类工具
│   │   ├── operations/     # 操作类工具
│   │   ├── planning/       # 规划类工具
│   │   └── analysis/       # 分析类工具
│   └── web/                # Web 服务
├── openharness/            # OpenHarness 子模块（Git Submodule）
├── tests/                  # 测试目录
│   ├── unit/              # 单元测试
│   ├── integration/       # 集成测试
│   └── e2e/               # 端到端测试
├── scripts/               # 辅助脚本
├── bootstep.py            # Docker 一键管理脚本
├── main.py                # 主入口
└── pyproject.toml         # 项目配置
```

---

## 代码风格与规范

### Python

- **类型提示**：使用 Pydantic v2 进行数据验证和类型提示
- **异步处理**：使用 `async/await` 模式
- **导入顺序**：标准库 > 第三方库 > 本地模块（按字母排序）
- **代码格式化**：使用 Black（行长度 100）
- **导入排序**：使用 isort

### TypeScript/JavaScript

- **严格模式**：启用 TypeScript 严格模式
- **React Hooks**：使用函数组件 + Hooks 模式
- **状态管理**：使用 Zustand
- **UI 组件**：使用 Ant Design
- **图表库**：使用 G6、AntV、ECharts
- **ESLint**：项目配置了 ESLint 9

### 测试标记

在 `pyproject.toml` 中定义了以下 pytest 标记：

| 标记 | 说明 |
|------|------|
| `@pytest.mark.unit` | 单元测试 |
| `@pytest.mark.integration` | 集成测试（需要外部服务） |
| `@pytest.mark.slow` | 慢速测试 |
| `@pytest.mark.e2e` | 端到端测试 |

---

## 服务访问地址

| 服务 | 地址 |
|------|------|
| 前端界面（开发） | http://localhost:5173 |
| 前端界面（生产） | http://localhost:80 |
| 后端 API | http://localhost:8000 |
| API 文档 (Swagger) | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |
| Neo4j Browser | http://localhost:7474 |
| OPA 策略服务 | http://localhost:8181 |

---

## 重要配置

### 环境变量

复制 `.env.example` 为 `.env.docker` 并配置：

```bash
cp .env.example .env.docker
# 编辑填写 OPENAI_API_KEY 等配置
```

### Docker 开发模式原理

开发模式下，前端通过 Volume 挂载源码到容器：
- Vite Dev Server 监听文件变更，HMR 自动刷新
- `vite.config.ts` 配置了 `watch.usePolling: true` 确保跨平台兼容

---

## 常见注意事项

1. **子模块**：OpenHarness 是 Git Submodule，首次 clone 后需 `git submodule update --init`
2. **外部依赖**：集成测试需要 MongoDB 和 Neo4j 服务运行
3. **Windows 兼容性**：Windows 下使用 Podman 时，docker 目录提供了 `podman-compose-win-fix.py`
4. **代码清理**：项目有代码清理清单（`docs/CODE_CLEANUP_LIST.md`），定期执行清理
5. **CI/CD**：GitHub Actions 配置在 `.github/workflows/`，包括测试和构建

---

## 相关文档

- 完整架构设计：`docs/architecture/ARCHITECTURE.md`
- 业务模块文档：`docs/01-product-design/`
- ADR 记录：`docs/07-adr/`
- 测试说明：`tests/README.md`