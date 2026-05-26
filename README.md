# ODAP - 本体驱动分析决策平台

**ODAP**（Ontology-Driven Analysis & Decision Platform）是一个通用的本体驱动分析决策平台，通过工作空间机制实现多场景隔离，支持任意领域的本体建模和分析决策。

> Graphiti 是本平台使用的双时态知识图谱组件，而非项目名称。

## 核心特性

- **本体驱动**：OMS 元模型框架 + 四层本体结构 + 版本链管理
- **统一查询服务**：QueryService 四源查询（Schema/Entity/Topo/Temporal），Agent Safe 默认只读
- **多智能体协同**：OpenHarness Agent Loop + Swarm 三 Agent OODA 闭环
- **双时态知识图谱**：Graphiti 支持 valid_time + transaction_time 时序推理
- **策略治理**：OPA fail-close 安全边界 + Agent 写操作守卫
- **工作空间隔离**：4 级隔离（low/standard/high/strict）+ 资源配额

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+, FastAPI, Neo4j / NetworkX |
| 前端 | React 19, TypeScript, Ant Design, G6, Leaflet |
| Agent | OpenHarness (Agent Loop + Swarm + MCP) |
| 知识图谱 | Graphiti (双时态知识图谱) |
| 策略治理 | OPA (开放策略代理) |
| LLM | OpenAI / Anthropic / DeepSeek |

## 项目结构

```
ontology-graphiti/
├── odap/                          # 核心平台
│   ├── biz/                       # 业务模块（按领域分层）
│   │   ├── core/                  #   核心领域
│   │   │   ├── ontology/          #     本体管理（OMS + Schema + 摄入管道）
│   │   │   ├── cognition/         #     认知引擎（OADA 理解）
│   │   │   └── agent/             #     Agent 协同（Swarm + OODA）
│   │   ├── decision/              #   决策领域
│   │   │   ├── decision_recommendation/  # 决策推荐
│   │   │   ├── decision_pipeline/        # 决策管道
│   │   │   └── action_service/           # 动作执行
│   │   ├── integration/           #   集成领域
│   │   │   ├── openharness_agent/ #     OpenHarness Agent 集成
│   │   │   ├── mcp_adapter/       #     MCP 协议适配
│   │   │   ├── hook_system/       #     Hook 系统
│   │   │   └── frontend_compat/   #     前端兼容层
│   │   ├── platform/              #   平台领域
│   │   │   ├── workspace/         #     工作空间管理
│   │   │   ├── roles/             #     角色权限
│   │   │   ├── skill_system/      #     技能系统
│   │   │   ├── tool_registry/     #     工具注册表
│   │   │   └── session_memory/    #     会话记忆
│   │   ├── data/                  #   数据领域
│   │   │   ├── perception/        #     感知模块
│   │   │   ├── data_warehouse/    #     数据仓库
│   │   │   ├── qa/                #     问答引擎
│   │   │   └── knowledge_base/    #     知识库
│   │   ├── simulation/            #   仿真领域
│   │   │   ├── event_simulator/   #     事件模拟
│   │   │   ├── simulation_sandbox/ #    仿真沙箱
│   │   │   ├── feedback/          #     反馈闭环
│   │   │   └── visualization/     #     可视化
│   │   └── management/            #   管理领域
│   │       ├── agent_management/  #     Agent 管理
│   │       └── business/          #     业务管理
│   ├── infra/                     # 基础设施
│   │   ├── query/                 #   统一查询服务（QueryService）
│   │   │   ├── service.py         #     查询服务核心
│   │   │   ├── parser.py          #     查询语法解析器
│   │   │   ├── protocols.py       #     接口定义
│   │   │   ├── routes.py          #     FastAPI 路由
│   │   │   └── sources/           #     数据源适配
│   │   │       ├── schema_source.py   # OMS 类型查询 + 校验
│   │   │       ├── entity_source.py   # 实体查询
│   │   │       └── topo_source.py     # 拓扑查询
│   │   ├── graph/                 #   图谱服务（GraphManager）
│   │   ├── openharness/           #   OpenHarness 适配层
│   │   │   ├── v2_adapter.py      #     Agent Loop 适配
│   │   │   ├── query_guard_hook.py #    Agent 写操作守卫
│   │   │   └── ...                #     Tool/Memory/Permission 适配
│   │   ├── opa/                   #   OPA 策略引擎
│   │   ├── security/              #   安全（JWT + 审计）
│   │   ├── storage/               #   数据存储（场景 + 版本）
│   │   ├── data_pipeline/         #   数据管道
│   │   ├── utils/                 #   工具函数（数据生成 + 爬虫）
│   │   ├── llm/                   #   LLM 服务
│   │   ├── monitoring/            #   性能监控
│   │   └── resilience/            #   韧性系统
│   ├── tools/                     # 领域工具（Python Skills）
│   │   ├── intelligence/          #   情报类
│   │   ├── operations/            #   操作类
│   │   ├── planning/              #   规划类
│   │   ├── analysis/              #   分析类
│   │   └── ...
│   └── web/                       # Web 服务
│       ├── app.py                 #   FastAPI 应用入口
│       ├── api/app.py             #   MockDataWebService
│       ├── gateway/               #   API 网关
│       ├── ws/                    #   WebSocket 事件总线
│       └── static/                #   静态资源
├── frontend/                      # 前端项目
│   └── src/modules/               #   按业务模块组织
│       ├── ontology/              #     本体管理
│       ├── agent/                 #     Agent 聊天
│       ├── workspace/             #     工作空间
│       ├── ingest/                #     数据摄入
│       └── ...
├── openharness/                   # OpenHarness 子模块（Git Submodule）
├── tests/                         # 测试
│   ├── unit/                      #   单元测试
│   ├── integration/               #   集成测试
│   └── e2e/                       #   端到端测试
├── docs/                          # 文档（12 个分类目录）
│   ├── 02-architecture/           #   架构设计（6 个子文档）
│   ├── 07-adr/                    #   架构决策记录（56 个 ADR）
│   └── ...
├── docker/                        # Docker 配置
├── scripts/                       # 辅助脚本
├── main.py                        # CLI 入口
├── bootstep.py                    # Docker 一键管理脚本
├── pyproject.toml                 # 项目配置
└── requirements.txt               # Python 依赖
```

## 快速开始

### 环境准备

- **Podman** / Docker（容器运行时）
- **Python 3.11+**
- **Node.js 18+**（前端开发）

### 配置环境变量

```bash
cp .env.example .env.docker
# 编辑 .env.docker，填写 OPENAI_API_KEY 等配置
```

### Docker 部署（推荐）

```bash
# 拉取基础镜像
python bootstep.py pull

# 开发模式（前端 HMR 热更新，访问 :5173）
python bootstep.py dev

# 生产模式（Nginx 静态服务，访问 :80）
python bootstep.py up

# 常用命令
python bootstep.py status    # 查看状态
python bootstep.py logs      # 查看后端日志
python bootstep.py down      # 停止服务
python bootstep.py rebuild   # 重新构建
python bootstep.py clean     # 清理资源
```

### 本地开发

```bash
# 安装后端依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend && npm install

# 终端 1 - 启动后端
python main.py --web

# 终端 2 - 启动前端
cd frontend && npm run dev
```

## 服务访问

| 服务 | 地址 |
|------|------|
| 前端（开发） | http://localhost:5173 |
| 前端（生产） | http://localhost:80 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |
| Neo4j Browser | http://localhost:7474 |
| OPA | http://localhost:8181 |

## 统一查询服务

ODAP 提供统一的 QueryService，支持四种查询源：

| 查询源 | 语法 | 说明 |
|--------|------|------|
| Schema | `.schema with(type='Unit')` | 查询 OMS 类型定义 |
| Entity | `.entity with(type='MilitaryUnit')` | 查询运行时实体 |
| Topo | `.topo neighbors(id='xxx', depth=2)` | 查询拓扑关系 |
| Temporal | `.temporal at('2025-01-01')` | 查询双时态数据 |

API 端点：`POST /api/query/execute`

## 测试

```bash
# 单元测试
pytest tests/unit/ -v

# 集成测试（需要 Neo4j + MongoDB）
pytest tests/integration/ -v

# 全部测试
python -m pytest tests/ -v

# 前端测试
cd frontend && npm test

# 前端类型检查
cd frontend && npm run typecheck
```

## 架构文档

| 文档 | 说明 |
|------|------|
| [ARCHITECTURE.md](docs/02-architecture/ARCHITECTURE.md) | 架构总览 + 语义层架构 |
| [ARCHITECTURE_INFRA.md](docs/02-architecture/ARCHITECTURE_INFRA.md) | 基础设施层 + QueryService |
| [ARCHITECTURE_BIZ.md](docs/02-architecture/ARCHITECTURE_BIZ.md) | 业务层 + Agent 查询统一化 |
| [ARCHITECTURE_TOOLS.md](docs/02-architecture/ARCHITECTURE_TOOLS.md) | 领域工具层 |
| [ARCHITECTURE_WEB.md](docs/02-architecture/ARCHITECTURE_WEB.md) | 接口层 |
| [ARCHITECTURE_EVOLVE.md](docs/02-architecture/ARCHITECTURE_EVOLVE.md) | 演进与决策 |

## 贡献

1. Fork 仓库
2. 创建分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m "Add your feature"`
4. 推送分支：`git push origin feature/your-feature`
5. 创建 PR

## 许可证

待定
