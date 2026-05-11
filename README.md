# ODAP - 本体驱动分析决策平台

**ODAP**（Ontology-Driven Analysis & Decision Platform）是一个通用的本体驱动分析决策平台，旨在通过工作空间机制实现多场景隔离，支持任意领域的本体建模和分析决策。

> **⚠️ 注意**: Graphiti 是本平台使用的双时态知识图谱组件，而非项目名称。

## 核心功能

- **本体管理**：领域本体设计、新增、更新维护
- **Skill 管理**：技能注册、配置、热插拔
- **多智能体调度**：意图识别、Agent 协同、OODA 闭环
- **问答链路**：自然语言问答、图表展示、过程解释
- **权限管控**：细粒度权限、OPA 策略、角色绑定
- **可视化配置**：本体、技能、策略、规则统一管理
- **事件模拟**：随机事件、自动/手动输入
- **工作空间**：场景隔离、导入导出、切换

## 技术栈

- **后端**: Python 3.11+, FastAPI, Neo4j (生产) / NetworkX (开发回退)
- **前端**: React, TypeScript, Ant Design, G6, Leaflet
- **Agent 基础设施**: OpenHarness (Agent Loop + Swarm + Tool 调度)
- **知识图谱**: Graphiti (双时态知识图谱 + 时序推理)
- **策略治理**: OPA (开放策略代理)
- **LLM 支持**: OpenAI / Anthropic / DeepSeek (多模型)
- **协议**: MCP (Model Context Protocol)

## 项目结构

```
graphiti/
├── app/                  # 主应用入口
├── assets/               # 静态资源（HTML、PNG等）
├── config/               # 配置文件
├── docker/               # Docker 配置
│   ├── Dockerfile                    # 后端镜像
│   ├── docker-compose.yml           # 生产编排
│   ├── docker-compose.override.yml  # 开发覆盖（热更新）
│   ├── docker-compose.test.yml      # 集成测试环境
│   └── podman-compose-win-fix.py    # Windows 路径兼容
├── docs/                 # 文档
│   ├── architecture/     # 架构设计文档（6个子文档）
│   ├── adr/             # 架构决策记录（48个ADR）
│   └── ...
├── frontend/             # 前端项目（React + TypeScript）
│   ├── src/              # 前端源码
│   ├── public/           # 前端静态资源
│   ├── Dockerfile                # 生产构建（Nginx 静态服务）
│   └── Dockerfile.dev            # 开发构建（Vite HMR 热更新）
├── odap/                 # 核心业务逻辑
│   ├── biz/              # 业务模块
│   │   ├── agent/                # Agent 协同模块
│   │   ├── cognition/            # 认知模块（OADA理解）
│   │   ├── decision_recommendation/ # 决策推荐模块
│   │   ├── event_simulator/      # 事件模拟模块
│   │   ├── frontend_compat/      # 前端兼容层
│   │   ├── hook_system/          # Hook 系统模块
│   │   ├── mcp_adapter/          # MCP 适配器模块
│   │   ├── ontology/             # 本体管理模块
│   │   ├── openharness_agent/    # OpenHarness Agent 集成
│   │   ├── qa/                   # 问答引擎模块
│   │   ├── roles/                # 角色权限模块
│   │   ├── skill_system/         # 技能系统模块
│   │   ├── tool_registry/        # 工具注册表模块
│   │   ├── visualization/        # 可视化模块
│   │   └── workspace/            # 工作空间管理模块
│   ├── infra/            # 基础设施
│   │   ├── config/               # 配置管理
│   │   ├── events/               # 事件系统
│   │   ├── graph/                # 图谱服务（Graphiti）
│   │   ├── llm/                  # LLM 服务
│   │   ├── monitoring/            # 性能监控
│   │   ├── opa/                  # OPA 策略
│   │   ├── openharness/          # OpenHarness 集成
│   │   ├── resilience/           # 韧性系统
│   │   └── security/             # 安全配置
│   ├── tools/            # 领域工具（Python Skills）
│   │   ├── intelligence/        # 情报类工具
│   │   ├── operations/           # 操作类工具
│   │   ├── planning/             # 规划类工具
│   │   ├── analysis/             # 分析类工具
│   │   ├── visualization/        # 可视化工具
│   │   └── ...
│   ├── web/              # Web 服务
│   ├── gateway/          # 网关模块
│   ├── storage/          # 存储目录
│   └── utils/           # 工具函数
├── openharness/          # OpenHarness 子模块
├── tests/                # 测试目录
├── scripts/              # 脚本目录
├── bootstep.py           # 一键管理脚本（生产/开发模式）
├── main.py               # 主入口
├── requirements.txt      # Python 依赖管理
├── pyproject.toml       # 项目配置
├── start.sh              # 启动脚本
└── stop.sh               # 停止脚本
```

> **📋 架构文档**: 完整的架构设计请查阅 `docs/architecture/ARCHITECTURE.md`（按层级拆分为6个子文档）

## 快速开始

### 环境准备

- **Podman** / Docker（容器运行时）
- **Python 3.11+**（仅运行管理脚本时需要）

### 配置环境变量

```bash
cp .env.example .env.docker
# 编辑 .env.docker，填写 OPENAI_API_KEY 等配置
```

### Docker 部署（推荐）

项目提供了 `bootstep.py` 一键管理脚本，支持**开发模式**和**生产模式**两种运行方式：

| 模式 | 命令 | 前端 | 特点 |
|------|------|------|------|
| **开发** | `python bootstep.py dev` | Vite HMR `:5173` | 代码修改即时热更新，无需重新构建 |
| **生产** | `python bootstep.py up` | Nginx `:80` | 静态文件服务，需要重新构建 |

```bash
# 首次使用先拉取基础镜像
python bootstep.py pull

# 开发模式（推荐日常开发）
python bootstep.py dev

# 生产模式
python bootstep.py up

# 查看状态
python bootstep.py status

# 查看日志
python bootstep.py logs          # 后端日志
python bootstep.py logs fe       # 生产前端日志
python bootstep.py logs fedev    # 开发前端日志

# 停止所有服务
python bootstep.py down

# 重新构建（生产模式）
python bootstep.py rebuild

# 清理资源
python bootstep.py clean
```

### 开发模式热更新原理

开发模式下，前端使用 `Dockerfile.dev` + `docker-compose.override.yml`：

- 源码通过 **Volume 挂载** 到容器内，修改即时生效
- Vite Dev Server 监听文件变更，**HMR (Hot Module Replacement)** 自动刷新浏览器
- `vite.config.ts` 已配置 `watch.usePolling: true` 确保跨平台兼容

### 服务访问地址

| 服务 | 地址 |
|------|------|
| 前端界面（开发） | http://localhost:5173 |
| 前端界面（生产） | http://localhost:80 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |
| Neo4j Browser | http://localhost:7474 |
| OPA | http://localhost:8181 |

### 本地开发（不依赖容器）

```bash
pip install -r requirements.txt
cd frontend && npm install

# 启动后端（终端 1）
python main.py

# 启动前端开发服务器（终端 2）
cd frontend && npm run dev
```

## 核心模块

### 1. 本体管理（Ontology）

- **功能**：领域本体设计、新增、更新维护、可视化配置
- **API**：`/api/ontology-management`
- **模块路径**：`odap/biz/ontology/`
- **架构文档**：[ARCHITECTURE_BIZ.md](docs/architecture/ARCHITECTURE_BIZ.md) 第13章

### 2. 工作空间管理（Workspace）

- **功能**：场景隔离、导入导出、切换、资源分类管理
- **API**：`/api/workspace`
- **模块路径**：`odap/biz/workspace/`
- **架构文档**：[ARCHITECTURE_BIZ.md](docs/architecture/ARCHITECTURE_BIZ.md) 第16章

### 3. Agent 协同（Swarm）

- **功能**：三Agent协同（Commander + Intelligence + Operations）、OADP闭环
- **API**：`/api/agent`
- **模块路径**：`odap/biz/agent/`（协同编排）+ `odap/biz/openharness_agent/`（OpenHarness集成）
- **架构文档**：[ARCHITECTURE_BIZ.md](docs/architecture/ARCHITECTURE_BIZ.md) 第7-9章

### 4. 技能系统（Skill System）

- **功能**：技能注册、配置、热插拔、工具注册表
- **API**：`/api/skill`
- **模块路径**：`odap/biz/skill_system/`（技能系统）+ `odap/biz/tool_registry/`（工具注册表）+ `odap/tools/`（领域工具）
- **架构文档**：[ARCHITECTURE_BIZ.md](docs/architecture/ARCHITECTURE_BIZ.md) 第14章、[ARCHITECTURE_TOOLS.md](docs/architecture/ARCHITECTURE_TOOLS.md)

### 5. 审计日志（Audit）

- **功能**：操作审计、日志记录、SQLite存储+文件哈希链锚点
- **API**：`/api/audit`
- **模块路径**：`odap/infra/opa/`（策略校验）+ 审计日志模块
- **架构文档**：[ARCHITECTURE_INFRA.md](docs/architecture/ARCHITECTURE_INFRA.md) 第6章

### 6. 问答引擎（QA）

- **功能**：自然语言问答、图表展示、过程解释
- **API**：`/api/qa`
- **模块路径**：`odap/biz/qa/`
- **架构文档**：[ARCHITECTURE_WEB.md](docs/architecture/ARCHITECTURE_WEB.md) 第11章

### 7. 角色权限（Roles）

- **功能**：细粒度权限、OPA策略、角色绑定
- **API**：`/api/roles`
- **模块路径**：`odap/biz/roles/`
- **架构文档**：[ARCHITECTURE_BIZ.md](docs/architecture/ARCHITECTURE_BIZ.md) 第20章

### 8. 事件模拟（Event Simulator）

- **功能**：随机事件、自动/手动输入、Web可视化
- **API**：`/api/simulator`
- **模块路径**：`odap/biz/event_simulator/`
- **架构文档**：[ARCHITECTURE_BIZ.md](docs/architecture/ARCHITECTURE_BIZ.md) 第9章

## 安全配置

- **API 密钥管理**：通过 `.env` 文件配置，避免硬编码
- **权限控制**：基于 OPA 策略的细粒度权限控制
- **CORS 配置**：通过环境变量配置允许的来源
- **JWT 认证**：支持基于 JWT 的 API 认证

## 性能监控

- **API 端点**：`/api/v1/monitoring/performance`
- **监控指标**：LLM 调用、数据库操作、API 请求、工具执行
- **统计信息**：平均值、中位数、最小值、最大值、P95、P99

## 测试

运行所有测试：

```bash
python -m pytest tests/ -v
```

## CI/CD

项目配置了 GitHub Actions CI/CD 流程，包括：
- **测试**：运行所有单元测试和集成测试
- **代码质量**：使用 flake8、black 和 isort 检查代码质量
- **覆盖率**：上传测试覆盖率报告到 Codecov

## 贡献

1. **Fork 仓库**
2. **创建分支**：`git checkout -b feature/your-feature`
3. **提交更改**：`git commit -m "Add your feature"`
4. **推送分支**：`git push origin feature/your-feature`
5. **创建 PR**

## 许可证

本项目许可证尚未确定。请根据实际需求选择合适的开源许可证（如 MIT、Apache 2.0 等）。