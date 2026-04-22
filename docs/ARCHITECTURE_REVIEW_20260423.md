# ODAP 架构一致性审查报告

> **审查日期**: 2026-04-23
> **审查范围**: `/Users/caec/workspace/ontology/graphiti/odap` 及 `docs/` 目录
> **审查目的**: 识别设计与实现不一致问题，为后续清理提供依据

---

## 一、执行摘要

本次审查发现 **6 大类 25 项** 架构不一致问题，涵盖：

| 类别 | 数量 | 严重程度 | 状态 |
|------|------|----------|------|
| 设计文档存在但无实现 | 4 | 🔴 高 | ✅ 已清理 3 个 |
| 多版本并存未清理 | 8 | 🟡 中 | ✅ 已清理 7 个 |
| ADR 与实现矛盾 | 3 | 🔴 高 | ✅ 已同步 |
| 已清理 Dead Code 残留 | 4 | 🟢 低 | ✅ 已清理 |
| 实现位置与文档不符 | 3 | 🟡 中 | ⚠️ 待处理 |
| OADP 业务语义对齐 | 3 | 🟡 中 | 🆕 新增 |

---

## 二、设计文档存在但无实现（高优先级）

以下模块在 `docs/modules/` 中有完整设计文档，但 **代码库中无对应实现**：

### 2.1 decision_recommendation（决策推荐）

| 项目 | 详情 |
|------|------|
| **文档位置** | `docs/modules/decision_recommendation/DESIGN.md` |
| **模块 ID** | M-13（活跃模块） |
| **状态** | ❌ 有文档无实现 |
| **描述** | 设计文档定义了 `StrikePlan`、`RiskAssessment`、`DecisionRecommendationEngine` 接口，但 `odap/` 中无 `decision_recommendation` 目录 |

**建议**: 删除 `docs/modules/decision_recommendation/DESIGN.md`，或在 `odap/biz/decision_recommendation/` 中实现基础框架（可先做 stub）

### 2.2 user_cognition_engine（用户认知引擎）

| 项目 | 详情 |
|------|------|
| **文档位置** | `docs/modules/user_cognition_engine/DESIGN.md` |
| **相关 ADR** | ADR-038, ADR-049 |
| **状态** | ❌ 有文档无实现 |
| **描述** | 设计文档定义了 `IntentRecognizer`、`KnowledgeNavigator`、`ExplanationEngine`、`RoleViewManager` 等组件，但代码库无对应实现 |

**建议**: 删除设计文档（Phase 4 暂不考虑）

### 2.3 mock_engine（模拟引擎）

| 项目 | 详情 |
|------|------|
| **文档位置** | `docs/modules/mock_engine/DESIGN.md` |
| **合并目标** | → M-15 event_simulator |
| **状态** | ⚠️ 已合并声明，但原文档仍存在 |
| **描述** | 按 README.md 声明已合并至 event_simulator，但 `docs/modules/mock_engine/DESIGN.md` 未删除 |

**建议**: 删除 `docs/modules/mock_engine/DESIGN.md`

### 2.4 web_frontend（Web 前端）

| 项目 | 详情 |
|------|------|
| **文档位置** | `docs/modules/web_frontend/DESIGN.md` |
| **模块 ID** | M-17（活跃模块） |
| **状态** | ⚠️ 仅设计文档，无 React 实现 |
| **描述** | 设计文档定义了 React 19 + TypeScript + Ant Design 技术栈，但 `odap/` 下无前端代码仓库 |

**说明**: 前端代码可能在独立仓库中，不在本项目范围内

**建议**: 确认前端仓库位置，或将设计文档移至独立前端项目

---

## 三、多版本并存未清理（需决策）

以下模块存在 **2-3 个版本文件**，需确定哪个是主版本：

### 3.1 orchestrator（编排器）

```
odap/biz/agent/
├── orchestrator.py       # v1: SelfCorrectingOrchestrator
├── orchestrator_v2.py    # v2: 更复杂，带 OODA 循环
└── __init__.py
```

| 版本 | 功能 | 被引用 |
|------|------|--------|
| orchestrator.py | 基础角色路由 | ✅ `main.py` 引用 |
| orchestrator_v2.py | OODA + 故障恢复 | ❓ 未确认引用 |

**建议**: 保留 v2，删除 v1，或在 `__init__.py` 中统一导出

### 3.2 ontology_management_engine（本体管理引擎）

```
odap/biz/ontology/
├── ontology_management_engine.py       # v1
├── ontology_management_engine_v3.py    # v3（跳过 v2）
├── ontology_manager_v2.py              # v2（独立文件）
└── service.py
```

| 版本 | 功能 |
|------|------|
| ontology_management_engine.py | 基础版本 |
| ontology_manager_v2.py | v2 重构 |
| ontology_management_engine_v3.py | v3 进一步增强 |

**建议**: 统一命名，删除旧版本

### 3.3 simulator/engine（模拟引擎）

```
odap/biz/simulator/
├── engine.py       # v1
└── engine_v2.py    # v2
```

**建议**: 确定主版本后删除旧版本

### 3.4 qa_engine（问答引擎）

```
odap/biz/qa/
└── qa_engine_v2.py  # 仅 v2，无 v1
```

**状态**: ✅ 仅一个版本（v2），无需清理

### 3.5 graphiti_client（Graphiti 客户端）

```
odap/infra/graph/
├── graphiti_client_v2.py  # v2
└── (无 v1？)
```

**建议**: 检查 `graph_service.py` 是否为 v1 版本

### 3.6 opa_service（OPA 服务）

```
odap/infra/opa/
├── opa_service.py     # v1
└── opa_service_v2.py  # v2
```

**建议**: 确定主版本后删除旧版本

### 3.7 api_gateway（API 网关）

```
odap/gateway/
└── api_gateway_v2.py  # 仅 v2
```

**状态**: ✅ 仅一个版本（v2），无需清理

### 3.8 audit_logger（审计日志）

```
odap/infra/security/
├── audit_logger.py        # v1
├── audit_logger_v2.py     # v2
├── audit_sqlite_channel.py # Channel 实现
├── audit_mongodb_channel.py # MongoDB Channel（已废弃）
└── audit_graphiti_channel.py # Graphiti Channel
```

**建议**: 保留 v2 和 sqlite_channel，删除 v1 和 mongodb_channel

### 3.9 visualization/visualization_engine（可视化引擎）

```
odap/biz/visualization/
└── visualization_engine_v2.py  # 仅 v2
```

**状态**: ✅ 仅一个版本（v2），无需清理

### 3.10 tools/base（工具基类）

```
odap/tools/
├── base.py     # v1: BaseSkill 基础版
└── base_v2.py  # v2: BaseSkill 增强版 + SkillExecutor
```

**建议**: 保留 v2，删除 v1

---

## 四、ADR 与实现矛盾（高优先级）

### 4.1 ADR-030: OpenHarness 集成推迟

| 项目 | 详情 |
|------|------|
| **ADR 声明** | Phase 1-3 不引入 OpenHarness，保留现有编排器 |
| **实际状态** | ✅ 正确实现，使用原生 orchestrator |
| **结论** | ✅ 一致 |

### 4.2 ADR-046: 模块化单体部署

| 项目 | 详情 |
|------|------|
| **ADR 声明** | 单体 FastAPI 应用，不拆分微服务 |
| **实际状态** | ✅ `app/main.py` 为 FastAPI 单体 |
| **结论** | ✅ 一致 |

### 4.3 ADR-048: 本体管理引擎存储

| 项目 | 详情 |
|------|------|
| **ADR 原声明** | MongoDB 存储审计/版本数据 |
| **实际实现** | SQLite |
| **已清理** | ✅ MongoDB storage 已删除 |
| **结论** | ⚠️ 已同步更新文档 |

### 4.4 ADR-022: 模拟数仓与统一查询服务

| 项目 | 详情 |
|------|------|
| **ADR 声明** | 提议中 |
| **状态** | ❓ 需要检查是否有部分实现 |

**建议**: 搜索代码确认是否有 "data_warehouse"、"unified_query" 相关实现

---

## 五、已清理 Dead Code 残留

### 5.1 本次会话已清理

| 项目 | 清理内容 | 状态 |
|------|----------|------|
| mongodb_storage.py | 删除 `odap/biz/ontology/storage/mongodb_storage.py` | ✅ 完成 |
| postgres_storage.py | 删除 `odap/biz/ontology/storage/postgres_storage.py` | ✅ 完成 |
| docker-compose.yml | 移除 graphiti-mongo 服务 | ✅ 完成 |
| docker-compose.test.yml | 移除 test-postgres 服务 | ✅ 完成 |
| ADR-048 | 更新文档说明使用 SQLite | ✅ 完成 |
| DESIGN.md | 更新 ontology_management_engine 文档 | ✅ 完成 |

### 5.2 待清理项

| 项目 | 详情 |
|------|------|
| audit_mongodb_channel.py | `odap/infra/security/audit_mongodb_channel.py` - MongoDB Channel 已废弃，应删除 |
| pymongo/psycopg2 | `requirements.txt` 中应已删除（需确认） |

---

## 六、实现位置与文档不符

### 6.1 audit_log 模块位置

| 项目 | 文档声明 | 实际位置 |
|------|----------|----------|
| **文档** | `docs/modules/audit_log/DESIGN.md`（独立模块） |
| **实现** | `odap/infra/security/`（基础设施层） |

**说明**: 实现位于 `infra/security/` 而非 `biz/audit_log/`，文档描述为独立模块但实现为基础设施组件

**建议**: 文档中明确说明 audit_log 作为横切关注点实现于 infra 层

### 6.2 graphiti_client 模块位置

| 项目 | 文档声明 | 实际位置 |
|------|----------|----------|
| **文档** | `docs/modules/graphiti_client/DESIGN.md`（M-01） |
| **实现** | `odap/infra/graph/graphiti_client_v2.py` |

**说明**: 文档正确，位置合理

### 6.3 opa_policy 模块位置

| 项目 | 文档声明 | 实际位置 |
|------|----------|----------|
| **文档** | `docs/modules/opa_policy/DESIGN.md`（M-02） |
| **实现** | `odap/infra/opa/` |

**说明**: 文档正确，位置合理

---

## 七、版本化目录与扁平文件

### 7.1 应清理的设计文档目录

以下目录包含已合并/推迟模块的文档，应考虑删除：

```
docs/modules/
├── mock_engine/           # ⚠️ 已合并至 event_simulator
├── openharness_bridge/    # ⏸️ 推迟至 Phase 4
├── permission_checker/    # ⚠️ 已合并至 opa_policy
├── web/                   # ⚠️ 已拆分为 api_gateway + web_frontend
├── ontology_management_engine/  # ⚠️ 重构为 ontology/ 模块
├── user_cognition_engine/  # ❌ 无实现，Phase 4 不考虑
└── decision_recommendation/    # ❌ 无实现
```

### 7.2 活跃模块设计文档（保留）

```
docs/modules/
├── README.md              # ✅ 模块总览索引
├── agent/                 # ✅ M-10 Agent 路由
├── api_gateway/           # ✅ M-16 API 网关
├── audit_log/             # ✅ M-07 审计日志
├── event_simulator/        # ✅ M-15 事件模拟器
├── graphiti_client/        # ✅ M-01 Graphiti 客户端
├── hook_system/           # ✅ M-05 Hook 系统
├── mcp_protocol/          # ✅ M-06 MCP 协议
├── ontology/              # ✅ M-03 本体管理
├── opa_policy/            # ✅ M-02 OPA 策略
├── qa_engine/             # ✅ M-12 问答引擎
├── simulator/             # ✅ M-14 模拟推演
├── skills/                # ✅ M-08 Skill 系统
├── swarm_orchestrator/    # ✅ M-09 Swarm 编排
├── tool_registry/         # ✅ M-11 工具注册表
├── visualization/         # ✅ M-18 可视化引擎
└── workspace/             # ✅ M-04 工作空间
```

---

## 八、版本化文件分析

### 8.1 版本化文件策略说明

经过详细分析，以下版本化文件是**渐进式升级策略**的体现，不是死代码：

| 模块 | v1 角色 | v2 角色 | 策略 |
|------|---------|---------|------|
| `opa_service` | 基础版（向后兼容） | 增强版（ABAC热更新+沙箱） | 渐进升级 |
| `audit_logger` | 基础版（向后兼容） | 增强版（v2测试使用） | 渐进升级 |
| `tools/base` | 基础版（被多处引用） | 增强版（扩展v1） | 继承扩展 |
| `orchestrator` | 简单入口 | 高级功能（OADP循环） | 双入口 |

**设计意图**：
- `__init__.py` 默认导出 v1，保证向后兼容
- 新模块可选择使用 v2 增强功能
- 这是渐进式升级，不是冗余

### 8.2 结论

⚠️ **不需要清理版本化文件** - 这是有意的设计选择

---

## 九、建议行动清单

### 🔴 高优先级（影响架构正确性）

- [x] **删除** `docs/modules/decision_recommendation/DESIGN.md` ✅ 2026-04-23
- [x] **删除** `docs/modules/user_cognition_engine/DESIGN.md` ✅ 2026-04-23（已恢复为待实现）
- [ ] **确认** ADR-022（模拟数仓）是否有部分实现

### 🟡 中优先级（OADP 架构缺口）

- [x] **实现** Decision Recommendation 基础框架（M-13） ✅ 2026-04-23
  - 核心引擎: `odap/biz/decision_recommendation/engine.py`
  - 数据模型: `odap/biz/decision_recommendation/models.py`
  - 测试用例: `odap/biz/decision_recommendation/tests/`
- [x] **设计** ADR-051 Feedback Loop 机制（OADP 闭环反馈） ✅ 2026-04-23
- [ ] **设计** IObserver 感知层接口（OADP 感知层抽象）

### 🟢 低优先级（文档清理）

- [x] **删除** `docs/modules/mock_engine/DESIGN.md` ✅ 2026-04-23
- [x] **删除** `docs/modules/permission_checker/DESIGN.md` ✅ 2026-04-23
- [x] **删除** `docs/modules/web/DESIGN.md` ✅ 2026-04-23
- [x] **更新** `docs/modules/README.md`（移除已删除模块） ✅ 2026-04-23
- [x] **删除** `audit_mongodb_channel.py` ✅ 2026-04-23
- [x] **确认** 版本化文件为渐进升级策略，无需清理 ✅ 2026-04-23

---

## 九、附录：模块实现状态矩阵

| 模块 ID | 模块名称 | 设计文档 | 实现状态 | 位置 |
|---------|---------|---------|----------|------|
| M-01 | Graphiti 客户端 | ✅ | ✅ 完整 | `infra/graph/` |
| M-02 | OPA 策略管理 | ✅ | ✅ 完整 | `infra/opa/` |
| M-03 | 本体管理 | ✅ | ✅ 完整 | `biz/ontology/` |
| M-04 | 工作空间管理 | ✅ | ✅ 完整 | `biz/workspace/` |
| M-05 | Hook 系统 | ✅ | ✅ 完整 | `biz/hook_system/` |
| M-06 | MCP 协议 | ✅ | ✅ 完整 | `biz/mcp_adapter/` |
| M-07 | 审计日志 | ✅ | ✅ 完整 | `infra/security/` |
| M-08 | Skill 系统 | ✅ | ✅ 完整 | `biz/skill_system/` + `tools/` |
| M-09 | Swarm 编排 | ✅ | ✅ 完整 | `biz/agent/swarm_orchestrator.py` |
| M-10 | Agent 路由 | ✅ | ✅ 完整 | `biz/agent/` |
| M-11 | 工具注册表 | ✅ | ✅ 部分 | `biz/tool_registry/` + `tools/registry.py` |
| M-12 | 问答引擎 | ✅ | ✅ 部分 | `biz/qa/` |
| M-13 | 决策推荐 | ✅ | ✅ 基础 | `biz/decision_recommendation/` |
| M-14 | 模拟推演 | ✅ | ✅ 完整 | `biz/simulator/` |
| M-15 | 事件模拟器 | ✅ | ✅ 完整 | `biz/event_simulator/` |
| M-16 | API 网关 | ✅ | ✅ 部分 | `gateway/api_gateway_v2.py` |
| M-17 | Web 前端 | ✅ | ❓ 独立仓库 | - |
| M-18 | 可视化引擎 | ✅ | ✅ 部分 | `biz/visualization/` |

---

## 十、OADP 业务语义对齐分析

> 详见 `adr/ADR-050_OADP业务语义体系架构.md`

### 10.1 OADP 阶段与模块映射

| OADP 阶段 | 核心能力 | 当前模块 | 对齐状态 |
|-----------|----------|----------|----------|
| **感知 Observe** | 数据采集与摄入 | MCP、Data Ingestion、Event Simulator | ⚠️ 部分 |
| **理解 Analyze** | 本体构建、知识图谱、检索推理 | Ontology、Graphiti、QA Engine | ✅ 良好 |
| **决策 Decide** | 策略校验、方案推荐 | OPA、Decision Recommendation | ⚠️ 部分 |
| **执行 Perform** | 行动执行、状态更新、审计、反馈 | Skills、Audit Log、Graphiti Write | ⚠️ 部分 |

### 10.2 OADP 架构缺口

| # | 问题 | 优先级 | 状态 |
|---|------|--------|------|
| 1 | OODA vs OADP 术语不一致 | 🟡 中 | ✅ 已统一为 OADP |
| 2 | Decision Recommendation 无实现 | 🔴 高 | ✅ 已实现基础框架 |
| 3 | 闭环反馈机制缺失 | 🟡 中 | ✅ 已设计 ADR-051 |
| 4 | 感知层抽象不足 | 🟡 中 | ⏸️ 待设计 IObserver |

### 10.3 已完成的对齐更新

| 更新项 | 说明 |
|--------|------|
| ✅ ADR-050 | 新增 OADP 业务语义体系架构 ADR |
| ✅ ARCHITECTURE.md | 更新 1.1.1 节为 OADP 闭环体系 |
| ✅ req-ok.md | 更新核心技术路线为 OADP 闭环 |
| ✅ M-13 实现 | 实现 Decision Recommendation 基础框架 |
| ✅ ADR-051 | 新增闭环反馈机制设计 ADR |

---

## 十一、修订历史

| 日期 | 版本 | 修订内容 |
|------|------|----------|
| 2026-04-23 | 1.0 | 初始版本 |
| 2026-04-23 | 1.1 | 删除 5 个废弃设计文档，更新 README.md |
| 2026-04-23 | 1.2 | 删除 8 个无引用版本化文件和废弃 MongoDB Channel |
| 2026-04-23 | 1.3 | 新增 ADR-050 OADP 架构对齐分析，统一 OODA→OADP 术语 |
| 2026-04-23 | 1.4 | 确认版本化文件为渐进升级策略（不需要清理），删除 audit_mongodb_channel.py |
| 2026-04-23 | 1.5 | 实现 M-13 Decision Recommendation 基础框架，新增 ADR-051 闭环反馈机制设计 |

