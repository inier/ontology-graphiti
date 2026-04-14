# 项目目录重构方案

**版本**: 1.0 | **日期**: 2026-04-15 | **作者**: 软件架构师

## 1. 现状问题分析

### 1.1 当前结构

```
graphiti/                      ← 52 个 .py 文件，架构层级混乱
├── core/                      ← 21 个 .py 文件，职责高度混杂
│   ├── graph_manager.py       ← 图谱基础设施
│   ├── llm_clients.py         ← LLM 适配层
│   ├── opa_manager.py         ← 权限基础设施
│   ├── hook_system.py         ← 事件基础设施
│   ├── simulation_engine.py   ← 模拟器业务逻辑
│   ├── simulator_web_service.py ← Web 服务层
│   ├── ontology_document.py   ← 本体模型定义
│   ├── ontology_hot_write_pipeline.py ← 本体管道
│   ├── ontology_version_manager.py   ← 本体版本管理
│   ├── data_ingestion.py      ← 模拟器数据采集
│   ├── intelligence_agent.py  ← Agent 业务逻辑
│   ├── swarm_orchestrator.py  ← Agent 编排业务逻辑
│   ├── orchestrator.py        ← Agent 业务逻辑（旧版）
│   ├── decision_recommender.py← Agent 业务逻辑
│   ├── intelligence_collector.py ← Agent 业务逻辑
│   ├── openharness_integration.py ← 适配层
│   ├── permission_checker.py  ← 权限业务逻辑
│   ├── fault_tolerance.py     ← 运维基础设施
│   ├── health_monitor.py      ← 运维基础设施
│   ├── state_persistence.py   ← 运维基础设施
│   └── opa_policy.rego        ← OPA 策略文件
├── ontology/                  ← 3 个 .py + 版本数据，职责混杂
│   ├── battlefield_ontology.py← 领域模型定义
│   ├── ontology_manager.py    ← 本体管理业务逻辑
│   └── versions/              ← 版本数据（应归 storage）
├── data/                      ← 2 个 .py，模拟数据
│   └── simulation_data.py     ← 领域数据生成
├── skills/                    ← 12 个 .py，工具层
├── visualization/             ← 3 个 .py，展示层（与 simulator_ui 重叠）
├── simulator_ui/              ← 1 个 HTML，前端
├── tests/                     ← 9 个 .py
├── docs/                      ← 文档
├── *.html                     ← 6 个散落的 HTML 文件在根目录
└── *.png                      ← 2 个散落的图片在根目录
```

### 1.2 核心问题

| # | 问题 | 影响 |
|---|------|------|
| P1 | `core/` 是个"大杂烩"，21 个文件横跨 5 个架构层次 | 任何修改都需要理解整个 core/ |
| P2 | 基础设施和业务逻辑无分离 | 无法独立测试/替换基础设施 |
| P3 | 本体相关分散在 `ontology/` + `core/ontology_*` 三个文件 | 本体管理模块不内聚 |
| P4 | 模拟器相关分散在 `core/simulation_engine.py` + `core/data_ingestion.py` + `core/simulator_web_service.py` + `simulator_ui/` | 模拟器模块不内聚 |
| P5 | 前端资源分散（`visualization/web_interface.py` + `simulator_ui/` + 根目录 HTML） | 前端入口不统一 |
| P6 | 不兼容 OpenHarness 的 `src/openharness/` 模块结构 | 后续 OpenHarness 集成困难 |
| P7 | `visualization/` 与 `simulator_ui/` 职责重叠 | 维护两套可视化 |
| P8 | 根目录散落 HTML/PNG 文件 | 项目根目录不整洁 |

## 2. 设计原则

### 2.1 分层原则（与四层架构对齐）

```
┌────────────────────────────────────────────────────┐
│  L4 业务领域层 (biz/)  — 战场分析、模拟器、Agent     │  ← 对外 API 暴露层
├────────────────────────────────────────────────────┤
│  L3 领域工具层 (tools/) — Skills、本体管理、决策推荐 │  ← 可插拔工具
├────────────────────────────────────────────────────┤
│  L2 基础服务层 (infra/) — 图谱、LLM、OPA、Hook      │  ← 可替换基础设施
├────────────────────────────────────────────────────┤
│  L1 适配层 (adapters/) — OpenHarness、MCP、外部API  │  ← 外部系统集成
└────────────────────────────────────────────────────┘
           ↕ API 边界（模块间通过对外 API 对接）
┌────────────────────────────────────────────────────┐
│  Web 服务层 (web/) — FastAPI 路由 + 前端 SPA        │  ← HTTP 入口
└────────────────────────────────────────────────────┘
```

### 2.2 模块化原则

| 原则 | 规则 |
|------|------|
| **单一职责** | 每个子包只做一件事，对外暴露清晰的 `__init__.py` API |
| **依赖方向** | 只允许上层依赖下层，禁止反向依赖 |
| **内聚性** | 同一业务能力的代码必须在同一目录 |
| **兼容 OpenHarness** | 目录结构参照 OpenHarness 的 `src/openharness/` 模式 |
| **渐进式迁移** | 旧路径通过 `__init__.py` re-export 保持向后兼容 |

### 2.3 依赖方向矩阵

```
web/          → biz/, tools/, infra/      （Web 层调用业务层和基础设施）
biz/          → tools/, infra/            （业务逻辑调用工具和基础设施）
tools/        → infra/                    （工具调用基础设施）
infra/        → (无外部依赖，纯技术实现)    （基础设施层自包含）
adapters/     → infra/, biz/              （适配层桥接外部系统和内部）
tests/        → 所有层                     （测试依赖全部）
```

## 3. 新目录结构

```
odap/                                  # 项目根目录（建议从 graphiti 更名）
│
├── pyproject.toml                      # Python 项目配置（替代 requirements.txt）
├── README.md                           # 项目说明
├── .env.example                        # 环境变量模板
├── .gitignore
│
# ═══════════════════════════════════════
# L2 基础设施层 (infra/) — 技术组件，无业务逻辑
# ═══════════════════════════════════════
├── odap/
│   ├── __init__.py                     # 包根
│   │
│   ├── infra/                          # 【基础设施层】
│   │   ├── __init__.py                 # 暴露: GraphService, LLMService, OPAService, EventBus
│   │   │
│   │   ├── graph/                      # 图谱基础设施
│   │   │   ├── __init__.py             # 暴露: GraphService
│   │   │   ├── graph_service.py        # ← core/graph_manager.py 重构
│   │   │   ├── graphiti_client.py      # ← 新增: Graphiti 客户端封装
│   │   │   └── config.py               # Neo4j/Graphiti 连接配置
│   │   │
│   │   ├── llm/                        # LLM 基础设施
│   │   │   ├── __init__.py             # 暴露: LLMService, ZhipuAIClient
│   │   │   ├── llm_service.py          # ← core/llm_clients.py 重构（统一接口）
│   │   │   ├── zhipu_client.py         # ← core/llm_clients.py 拆分（智谱适配器）
│   │   │   └── config.py               # 模型配置、Provider 管理
│   │   │
│   │   ├── opa/                        # OPA 策略基础设施
│   │   │   ├── __init__.py             # 暴露: OPAService
│   │   │   ├── opa_service.py          # ← core/opa_manager.py 重命名
│   │   │   ├── opa_policy.rego         # ← core/opa_policy.rego 迁移
│   │   │   └── config.py               # OPA Server 配置
│   │   │
│   │   ├── events/                     # 事件/Hook 基础设施
│   │   │   ├── __init__.py             # 暴露: EventBus, HookRegistry
│   │   │   └── hook_system.py          # ← core/hook_system.py
│   │   │
│   │   ├── resilience/                 # 韧性基础设施
│   │   │   ├── __init__.py             # 暴露: FaultTolerancer, HealthMonitor, StateStore
│   │   │   ├── fault_tolerance.py      # ← core/fault_tolerance.py
│   │   │   ├── health_monitor.py       # ← core/health_monitor.py
│   │   │   └── state_persistence.py    # ← core/state_persistence.py
│   │   │
│   │   └── config/                     # 全局配置
│   │       ├── __init__.py             # 暴露: Settings
│   │       └── settings.py             # ← 新增: 集中配置管理（pydantic-settings）
│   │
│   # ═══════════════════════════════════════
│   # L3 领域工具层 (tools/) — 可插拔业务工具
│   # ═══════════════════════════════════════
│   ├── tools/                          # 【领域工具层】
│   │   ├── __init__.py                 # 暴露: SkillRegistry, register_skill, SKILL_CATALOG
│   │   ├── base.py                     # ← skills/base.py（BaseSkill / SkillInput / SkillOutput）
│   │   ├── registry.py                 # ← skills/__init__.py 提取注册逻辑
│   │   │
│   │   ├── intelligence/               # 情报工具
│   │   │   ├── __init__.py
│   │   │   └── intelligence.py         # ← skills/intelligence.py
│   │   │
│   │   ├── operations/                 # 作战工具
│   │   │   ├── __init__.py
│   │   │   └── operations.py           # ← skills/operations.py
│   │   │
│   │   ├── analysis/                   # 分析工具
│   │   │   ├── __init__.py
│   │   │   └── analysis.py             # ← skills/analysis.py
│   │   │
│   │   ├── planning/                   # 规划工具
│   │   │   ├── __init__.py
│   │   │   └── planning.py             # ← skills/planning.py
│   │   │
│   │   ├── recommendation/             # 决策推荐工具
│   │   │   ├── __init__.py
│   │   │   └── recommendation.py       # ← skills/recommendation.py
│   │   │
│   │   ├── policy/                     # 策略工具
│   │   │   ├── __init__.py
│   │   │   └── policy.py               # ← skills/policy.py
│   │   │
│   │   ├── computation/                # 计算工具
│   │   │   ├── __init__.py
│   │   │   └── computation.py          # ← skills/computation.py
│   │   │
│   │   ├── task_management/            # 任务管理工具
│   │   │   ├── __init__.py
│   │   │   └── task_management.py      # ← skills/task_management.py
│   │   │
│   │   └── visualization/              # 可视化工具（Python 生成图表）
│   │       ├── __init__.py
│   │       └── visualization_skill.py  # ← skills/visualization_skill.py
│   │
│   # ═══════════════════════════════════════
│   # L4 业务领域层 (biz/) — 核心业务模块
│   # ═══════════════════════════════════════
│   ├── biz/                            # 【业务领域层】
│   │   ├── __init__.py
│   │   │
│   │   ├── ontology/                   # 【本体管理模块】
│   │   │   ├── __init__.py             # 暴露: OntologyManager（对外 API）
│   │   │   │
│   │   │   ├── schema/                 # 本体 Schema 定义
│   │   │   │   ├── __init__.py
│   │   │   │   ├── document.py         # ← core/ontology_document.py
│   │   │   │   ├── battlefield.py      # ← ontology/battlefield_ontology.py
│   │   │   │   └── validators.py       # ← 新增: Schema 验证器集合
│   │   │   │
│   │   │   ├── service.py              # ← ontology/ontology_manager.py + core/ontology_* 整合
│   │   │   │                           # 对外 API:
│   │   │   │                           #   create_workspace(), update(), reset(), switch_version()
│   │   │   │                           #   hot_write(), query(), export(), import_doc()
│   │   │   │
│   │   │   ├── hot_write.py            # ← core/ontology_hot_write_pipeline.py
│   │   │   ├── version_manager.py      # ← core/ontology_version_manager.py
│   │   │   └── ingestion.py            # ← core/data_ingestion.py（数据采集归入本体管理）
│   │   │
│   │   ├── workspace/                  # 【工作空间管理模块】
│   │   │   ├── __init__.py             # 暴露: WorkspaceManager
│   │   │   └── manager.py              # ← 新增: 工作空间 CRUD + 隔离
│   │   │                               # 对外 API:
│   │   │                               #   create(), delete(), list(), switch(), get_config()
│   │   │
│   │   ├── agent/                      # 【Agent 协同模块】
│   │   │   ├── __init__.py             # 暴露: SwarmOrchestrator, IntelligenceAgent
│   │   │   │
│   │   │   ├── intelligence_agent.py   # ← core/intelligence_agent.py
│   │   │   ├── commander.py            # ← core/swarm_orchestrator.py 拆分: Commander 逻辑
│   │   │   ├── operations_agent.py     # ← core/swarm_orchestrator.py 拆分: Operations 逻辑
│   │   │   ├── swarm_orchestrator.py   # ← core/swarm_orchestrator.py（保留编排核心）
│   │   │   ├── orchestrator.py         # ← core/orchestrator.py（旧版，后续废弃）
│   │   │   ├── collector.py            # ← core/intelligence_collector.py
│   │   │   └── recommender.py          # ← core/decision_recommender.py
│   │   │
│   │   ├── permission/                 # 【权限管理模块】
│   │   │   ├── __init__.py             # 暴露: PermissionService
│   │   │   └── checker.py              # ← core/permission_checker.py
│   │   │
│   │   └── simulator/                  # 【模拟推演模块】
│   │       ├── __init__.py             # 暴露: SimulatorEngine
│   │       │
│   │       ├── engine.py               # ← core/simulation_engine.py
│   │       ├── data_generator.py       # ← data/simulation_data.py
│   │       └── models.py               # ← 新增: 模拟器领域模型（Scenario, Event 等）
│   │
│   # ═══════════════════════════════════════
│   # L1 适配层 (adapters/) — 外部系统集成
│   # ═══════════════════════════════════════
│   ├── adapters/                       # 【适配层】
│   │   ├── __init__.py
│   │   │
│   │   ├── openharness/                # OpenHarness 适配
│   │   │   ├── __init__.py
│   │   │   ├── tool_adapter.py         # ← core/openharness_integration.py
│   │   │   └── harness.py              # ← core/openharness_integration.py 拆分
│   │   │
│   │   └── mcp/                        # MCP 协议适配（预留）
│   │       ├── __init__.py
│   │       └── server.py               # 预留: MCP Server 实现
│   │
│   # ═══════════════════════════════════════
│   # Web 服务层 (web/) — HTTP 入口 + 前端
│   # ═══════════════════════════════════════
│   ├── web/                            # 【Web 服务层】
│   │   ├── __init__.py
│   │   │
│   │   ├── api/                        # REST API 路由
│   │   │   ├── __init__.py
│   │   │   ├── app.py                  # ← core/simulator_web_service.py 重构: FastAPI app
│   │   │   ├── router_ontology.py      # 本体管理 API（/api/v1/ontology/...）
│   │   │   ├── router_simulator.py     # 模拟器 API（/api/v1/simulator/...）
│   │   │   ├── router_agent.py         # Agent API（/api/v1/agent/...）
│   │   │   ├── router_workspace.py     # 工作空间 API（/api/v1/workspace/...）
│   │   │   └── router_system.py        # 系统 API（健康检查、审计等）
│   │   │
│   │   ├── ws/                         # WebSocket 处理
│   │   │   ├── __init__.py
│   │   │   └── event_stream.py         # ← core/simulator_web_service.py 拆分: WS
│   │   │
│   │   ├── static/                     # 前端 SPA
│   │   │   ├── index.html              # ← simulator_ui/index.html
│   │   │   ├── css/
│   │   │   │   └── app.css             # ← 从 index.html 提取
│   │   │   └── js/
│   │   │       ├── app.js              # ← 从 index.html 提取
│   │   │       ├── timeline.js         # ← 从 index.html 提取
│   │   │       ├── graph.js            # ← 从 index.html 提取
│   │   │       └── map.js              # ← 从 index.html 提取
│   │   │
│   │   └── legacy/                     # 旧版 Web 界面（保留但不推荐）
│   │       ├── __init__.py
│   │       ├── dialog_interface.py     # ← visualization/dialog_interface.py
│   │       └── web_interface.py        # ← visualization/web_interface.py
│   │
│   # ═══════════════════════════════════════
│   # 数据存储 (storage/) — 运行时数据
│   # ═══════════════════════════════════════
│   └── storage/                        # 【数据存储层】
│       ├── __init__.py
│       ├── scenarios/                  # ← ontology/versions/scenarios/ 迁移
│       ├── versions/                   # ← ontology/versions/*.json 迁移
│       ├── states/                     # Agent 状态持久化
│       └── exports/                    # 导出文件
│
# ═══════════════════════════════════════
# 入口 & 配置
# ═══════════════════════════════════════
├── src/                                # 入口脚本
│   ├── __init__.py
│   ├── cli.py                          # ← main.py 重构: CLI 入口
│   └── web_server.py                   # ← main.py 拆分: Web 服务启动器
│
# ═══════════════════════════════════════
# 测试
# ═══════════════════════════════════════
├── tests/
│   ├── __init__.py
│   ├── conftest.py                     # 新增: pytest fixtures（共享测试基础设施）
│   ├── unit/                           # 单元测试
│   │   ├── test_hook_system.py         # ← tests/test_hook_system.py
│   │   ├── test_permission.py          # ← tests/test_permission_checker.py
│   │   ├── test_simulation.py          # ← tests/test_simulation_engine.py
│   │   ├── test_orchestrator.py        # ← tests/test_swarm.py
│   │   └── test_system.py              # ← tests/test_system.py
│   ├── integration/                    # 集成测试
│   │   └── test_graphiti.py            # ← tests/test_graphiti_integration.py
│   └── manual/                         # 手动测试脚本
│       ├── graphiti_bulk.py            # ← tests/manual_graphiti_bulk.py
│       ├── graphiti_retry.py           # ← tests/manual_graphiti_retry.py
│       └── graphiti_test.py            # ← tests/manual_graphiti_test.py
│
# ═══════════════════════════════════════
# 文档
# ═══════════════════════════════════════
├── docs/
│   ├── ARCHITECTURE.md                 # 架构文档
│   ├── TASK_BREAKDOWN.md               # 任务分解
│   ├── RESTRUCTURE_PLAN.md             # 本文档
│   ├── adr/                            # 架构决策记录
│   │   ├── README.md
│   │   ├── ADR-001_*.md
│   │   └── ...
│   └── modules/                        # 模块设计文档
│       ├── README.md
│       ├── ontology/
│       ├── agent/
│       ├── simulator/
│       ├── infra/
│       └── web/
│
# ═══════════════════════════════════════
# 资源 & 配置
# ═══════════════════════════════════════
├── assets/                             # 静态资源
│   ├── images/                         # ← 根目录 *.png 迁移
│   └── templates/                      # 模板文件
│
├── docker/                             # 容器化配置（预留）
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── neo4j/
│   └── opa/
│
├── scripts/                            # 运维脚本
│   ├── migrate.py                      # 数据迁移脚本
│   └── setup_dev.py                    # 开发环境搭建
│
├── .openharness/                       # OpenHarness 配置（预留）
│   └── config.yaml
│
└── pyproject.toml                      # 项目配置
```

## 4. 模块映射表（旧 → 新）

| 旧路径 | 新路径 | 说明 |
|--------|--------|------|
| `core/graph_manager.py` | `odap/infra/graph/graph_service.py` | 基础设施层 |
| `core/llm_clients.py` | `odap/infra/llm/llm_service.py` + `zhipu_client.py` | 拆分为统一接口 + 适配器 |
| `core/opa_manager.py` | `odap/infra/opa/opa_service.py` | 基础设施层 |
| `core/opa_policy.rego` | `odap/infra/opa/opa_policy.rego` | 随 OPA 服务走 |
| `core/hook_system.py` | `odap/infra/events/hook_system.py` | 事件基础设施 |
| `core/fault_tolerance.py` | `odap/infra/resilience/fault_tolerance.py` | 韧性基础设施 |
| `core/health_monitor.py` | `odap/infra/resilience/health_monitor.py` | 韧性基础设施 |
| `core/state_persistence.py` | `odap/infra/resilience/state_persistence.py` | 韧性基础设施 |
| `skills/base.py` | `odap/tools/base.py` | 工具层基类 |
| `skills/__init__.py`（注册逻辑） | `odap/tools/registry.py` | 工具层注册 |
| `skills/intelligence.py` | `odap/tools/intelligence/intelligence.py` | 工具层 |
| `skills/operations.py` | `odap/tools/operations/operations.py` | 工具层 |
| `skills/analysis.py` | `odap/tools/analysis/analysis.py` | 工具层 |
| `skills/planning.py` | `odap/tools/planning/planning.py` | 工具层 |
| `skills/recommendation.py` | `odap/tools/recommendation/recommendation.py` | 工具层 |
| `skills/policy.py` | `odap/tools/policy/policy.py` | 工具层 |
| `skills/computation.py` | `odap/tools/computation/computation.py` | 工具层 |
| `skills/task_management.py` | `odap/tools/task_management/task_management.py` | 工具层 |
| `skills/visualization_skill.py` | `odap/tools/visualization/visualization_skill.py` | 工具层 |
| `skills/ontology_management.py` | `odap/biz/ontology/` (合并到 service.py) | 业务层 |
| `ontology/battlefield_ontology.py` | `odap/biz/ontology/schema/battlefield.py` | 领域 Schema |
| `ontology/ontology_manager.py` | `odap/biz/ontology/service.py` | 业务层 |
| `core/ontology_document.py` | `odap/biz/ontology/schema/document.py` | 领域 Schema |
| `core/ontology_hot_write_pipeline.py` | `odap/biz/ontology/hot_write.py` | 业务层 |
| `core/ontology_version_manager.py` | `odap/biz/ontology/version_manager.py` | 业务层 |
| `core/data_ingestion.py` | `odap/biz/ontology/ingestion.py` | 业务层（数据采集归本体管理） |
| `ontology/versions/` | `odap/storage/versions/` | 数据存储 |
| `ontology/versions/scenarios/` | `odap/storage/scenarios/` | 数据存储 |
| `core/intelligence_agent.py` | `odap/biz/agent/intelligence_agent.py` | 业务层 |
| `core/swarm_orchestrator.py` | `odap/biz/agent/swarm_orchestrator.py` | 业务层 |
| `core/orchestrator.py` | `odap/biz/agent/orchestrator.py` | 业务层（旧版，标记 @deprecated） |
| `core/decision_recommender.py` | `odap/biz/agent/recommender.py` | 业务层 |
| `core/intelligence_collector.py` | `odap/biz/agent/collector.py` | 业务层 |
| `core/permission_checker.py` | `odap/biz/permission/checker.py` | 业务层 |
| `core/simulation_engine.py` | `odap/biz/simulator/engine.py` | 业务层 |
| `data/simulation_data.py` | `odap/biz/simulator/data_generator.py` | 业务层 |
| `core/simulator_web_service.py` | `odap/web/api/app.py` + `routers/` | Web 层（拆分） |
| `simulator_ui/index.html` | `odap/web/static/index.html` | Web 前端 |
| `visualization/dialog_interface.py` | `odap/web/legacy/dialog_interface.py` | 旧版保留 |
| `visualization/web_interface.py` | `odap/web/legacy/web_interface.py` | 旧版保留 |
| `visualization/visualization.py` | `odap/tools/visualization/plotting.py` | 工具层（Python 绘图） |
| `core/openharness_integration.py` | `odap/adapters/openharness/tool_adapter.py` | 适配层 |
| `main.py` | `src/cli.py` + `src/web_server.py` | 入口拆分 |
| `requirements.txt` | `pyproject.toml` | 现代化依赖管理 |
| `*.html`（根目录） | `assets/templates/` 或删除 | 清理根目录 |
| `*.png`（根目录） | `assets/images/` | 清理根目录 |

## 5. 各模块对外 API 设计

### 5.1 本体管理模块 (`odap/biz/ontology/`)

```python
# odap/biz/ontology/__init__.py — 对外 API
from .service import OntologyManager

# OntologyManager 对外方法:
class OntologyManager:
    # 工作空间管理
    async def create_workspace(workspace_id, config) -> Workspace
    async def delete_workspace(workspace_id) -> None
    async def list_workspaces() -> List[Workspace]
    async def switch_workspace(workspace_id) -> None

    # 图谱 CRUD
    async def create_graph(schema, entities, relations) -> GraphSnapshot
    async def update_graph(doc: OntologyDocument) -> GraphSnapshot
    async def reset_graph(workspace_id) -> None
    async def query_graph(query, workspace_id) -> QueryResult

    # 版本管理
    async def list_versions(workspace_id) -> List[OntologyVersion]
    async def switch_version(workspace_id, version_id) -> None
    async def rollback(workspace_id, version_id) -> None
    async def diff(version_a, version_b) -> VersionDiff

    # 热写入
    async def hot_write(doc: OntologyDocument) -> WriteResult

    # 导入/导出
    async def export(workspace_id, format="odoc") -> bytes
    async def import_doc(data, format="odoc") -> ImportResult
```

### 5.2 工作空间管理模块 (`odap/biz/workspace/`)

```python
# odap/biz/workspace/__init__.py — 对外 API
from .manager import WorkspaceManager

class WorkspaceManager:
    async def create(name, description, ontology_config) -> Workspace
    async def delete(workspace_id) -> None
    async def list_all() -> List[Workspace]
    async def get(workspace_id) -> Workspace
    async def switch(workspace_id) -> Workspace
    async def update_config(workspace_id, config) -> Workspace
```

### 5.3 Agent 协同模块 (`odap/biz/agent/`)

```python
# odap/biz/agent/__init__.py — 对外 API
from .swarm_orchestrator import BattlefieldSwarm
from .intelligence_agent import IntelligenceAgent

class BattlefieldSwarm:
    async def initialize(config=None) -> None
    async def execute_mission(mission: str) -> MissionResult
    async def shutdown() -> None

class IntelligenceAgent:
    def analyze(query: str, context=None) -> AnalysisReport
```

### 5.4 模拟推演模块 (`odap/biz/simulator/`)

```python
# odap/biz/simulator/__init__.py — 对外 API
from .engine import SimulatorEngine

class SimulatorEngine:
    def create_scenario(config) -> Scenario
    def run_simulation(scenario_id, parameters) -> SimulationResult
    def pause_simulation(scenario_id) -> None
    def resume_simulation(scenario_id) -> None
    def get_result(scenario_id) -> SimulationResult
```

### 5.5 Web 服务层 (`odap/web/api/`)

```
API 路由规划:
├── /api/v1/ontology/           ← router_ontology.py
│   ├── POST   /workspace               创建工作空间
│   ├── GET    /workspaces              列出工作空间
│   ├── DELETE /workspace/{id}          删除工作空间
│   ├── POST   /write                   热写入 OntologyDocument
│   ├── GET    /query                   图谱查询
│   ├── GET    /versions/{workspace_id} 版本列表
│   ├── POST   /version/switch          切换版本
│   ├── POST   /version/rollback        回退版本
│   ├── POST   /export                  导出
│   └── POST   /import                  导入
│
├── /api/v1/simulator/          ← router_simulator.py
│   ├── POST   /scenario               创建场景
│   ├── POST   /run                     启动推演
│   ├── POST   /pause/{id}              暂停
│   ├── POST   /resume/{id}             恢复
│   └── GET    /result/{id}             获取结果
│
├── /api/v1/agent/              ← router_agent.py
│   ├── POST   /mission                创建任务（触发 OODA）
│   ├── GET    /mission/{id}            获取任务状态
│   └── GET    /mission/{id}/stream     SSE 流式响应
│
├── /api/v1/workspace/          ← router_workspace.py
│   ├── POST   /                        创建工作空间
│   ├── GET    /                        列出工作空间
│   ├── GET    /{id}                    工作空间详情
│   └── POST   /{id}/switch             切换工作空间
│
├── /api/v1/system/             ← router_system.py
│   ├── GET    /health                  健康检查
│   └── GET    /metrics                 系统指标
│
└── /ws/events                    ← WebSocket 事件流
```

## 6. 向后兼容策略

迁移过程中，旧路径通过 re-export 保持兼容，并打印 DeprecationWarning：

```python
# core/__init__.py — 向后兼容 shim（迁移后保留 2 个版本）
import warnings
warnings.warn(
    "导入 'core' 已废弃，请使用 'odap.infra' / 'odap.biz' / 'odap.tools'",
    DeprecationWarning, stacklevel=2
)

# 逐一 re-export
from odap.infra.graph.graph_service import BattlefieldGraphManager
from odap.infra.opa.opa_service import OPAClient, OPAManager
from odap.infra.events.hook_system import HookRegistry
# ... 等等
```

```python
# skills/__init__.py — 向后兼容 shim
import warnings
warnings.warn(
    "导入 'skills' 已废弃，请使用 'odap.tools'",
    DeprecationWarning, stacklevel=2
)

from odap.tools.registry import SkillRegistry, register_skill, SKILL_CATALOG
```

## 7. 迁移执行计划

### Phase R-1: 准备阶段（1-2 天）
1. 创建新目录结构（空 `__init__.py`）
2. 编写 `pyproject.toml`（替代 `requirements.txt`）
3. 编写 `conftest.py`（共享测试 fixtures）
4. 编写 `odap/__init__.py` 和各子包 `__init__.py`
5. 创建向后兼容 shim

### Phase R-2: 基础设施层迁移（2-3 天）
1. `core/graph_manager.py` → `odap/infra/graph/`
2. `core/llm_clients.py` → `odap/infra/llm/`
3. `core/opa_manager.py` → `odap/infra/opa/`
4. `core/hook_system.py` → `odap/infra/events/`
5. `core/fault_tolerance.py` + `health_monitor.py` + `state_persistence.py` → `odap/infra/resilience/`
6. 更新 shim re-export
7. 运行测试验证

### Phase R-3: 领域工具层迁移（1-2 天）
1. `skills/base.py` → `odap/tools/base.py`
2. 提取 `skills/__init__.py` 注册逻辑 → `odap/tools/registry.py`
3. 各 Skill 模块迁移到 `odap/tools/{category}/`
4. `visualization/visualization.py` → `odap/tools/visualization/plotting.py`
5. 运行测试验证

### Phase R-4: 业务领域层迁移（3-4 天）
1. 本体模块: `ontology/` + `core/ontology_*` + `core/data_ingestion.py` → `odap/biz/ontology/`
2. Agent 模块: `core/intelligence_agent.py` + `core/swarm_orchestrator.py` + ... → `odap/biz/agent/`
3. 模拟器模块: `core/simulation_engine.py` + `data/simulation_data.py` → `odap/biz/simulator/`
4. 权限模块: `core/permission_checker.py` → `odap/biz/permission/`
5. 创建 `odap/biz/workspace/manager.py`（新模块）
6. 更新各模块 `__init__.py` 对外 API
7. 运行测试验证

### Phase R-5: Web 服务层迁移（2-3 天）
1. `core/simulator_web_service.py` 拆分为 `odap/web/api/` 路由模块
2. 前端 HTML 拆分为 `odap/web/static/`（CSS/JS 分离）
3. `visualization/dialog_interface.py` + `web_interface.py` → `odap/web/legacy/`
4. `main.py` 拆分为 `src/cli.py` + `src/web_server.py`
5. 运行测试 + 手动验证 Web 服务

### Phase R-6: 适配层 + 清理（1-2 天）
1. `core/openharness_integration.py` → `odap/adapters/openharness/`
2. 根目录散落文件清理（HTML → `assets/templates/`，PNG → `assets/images/`）
3. 数据文件迁移（`ontology/versions/` → `odap/storage/`）
4. 更新文档（ARCHITECTURE.md、ADR-033）
5. 删除向后兼容 shim（v1.0 正式版）

### 总计: 10-16 天

## 8. 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 迁移过程中测试大面积失败 | Phase 分步迁移，每步后运行全量测试 |
| import 路径变更导致外部引用断裂 | 向后兼容 shim（re-export + DeprecationWarning） |
| 循环依赖 | 严格遵循依赖方向矩阵，通过 import 检查工具验证 |
| 前端引用后端静态文件路径 | FastAPI StaticFiles 配置统一入口 |
| Git 历史丢失 | 使用 `git mv` 保持文件历史 |

## 9. 成功标准

1. ✅ 每个 `odap/` 子包的 `__init__.py` 清晰暴露对外 API
2. ✅ 模块间零循环依赖（通过 `import-linter` 或 `pydeps` 验证）
3. ✅ 所有测试通过（60+ passed）
4. ✅ `python src/web_server.py --web` 正常启动 Web 服务
5. ✅ `python src/cli.py` 正常运行 CLI Demo
6. ✅ 旧 `from core.xxx import yyy` 路径仍然可用（带 DeprecationWarning）
7. ✅ 根目录整洁（无散落 HTML/PNG）
