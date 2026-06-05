# 本体子系统隔离架构

## 概述

ODAP 平台将本体业务拆分为两个隔离子系统，通过契约层和统一查询服务进行通信，禁止直接跨边界导入。

```
┌────────────────────────────────────────────────────────────┐
│                   odap.biz.core.ontology                   │
│                                                            │
│  ┌──────────────────────────┐   ┌────────────────────────┐ │
│  │  本体设计 (Design)       │   │ 本体应用 (Application) │ │
│  │  ─ 定义、版本、构建      │   │ ─ 运行、编排、服务化   │ │
│  │  ─ 摄入、Schema          │   │ ─ OMS、Harness、Runtime│ │
│  │                          │   │                        │ │
│  │  design/                 │   │  application/          │ │
│  │   ├─ model/              │   │   ├─ runtime/          │ │
│  │   ├─ engine/             │   │   ├─ servitization/    │ │
│  │   ├─ version/            │   │   ├─ team_agent/       │ │
│  │   ├─ ingestion/          │   │   ├─ oms/              │ │
│  │   ├─ schema/             │   │   ├─ abution_graph/    │ │
│  │   ├─ ingestion_split/    │   │   ├─ harness/          │ │
│  │   ├─ mock_data/          │   │   ├─ abution_graph/    │ │
│  │   ├─ interfaces/         │   │   └─ query_api/        │ │
│  │   ├─ impl/               │   │                        │ │
│  │   ├─ services/           │   │                        │ │
│  │   ├─ storage/            │   │                        │ │
│  │   ├─ models/             │   │                        │ │
│  │   └─ contract/  ◄── 公共 │   │                        │ │
│  └────────┬─────────────────┘   └─────────▲──────────────┘ │
│           │                              │                │
└───────────┼──────────────────────────────┼────────────────┘
            │                              │
            │   ┌──────────────────────┐   │
            └──►│ 统一查询服务         │◄──┘
                │ odap.infra.query     │
                │  - QueryService      │
                │  - OntologyDesignSource
                │  - 多种数据源协议     │
                └──────────────────────┘
```

## 边界规则

### 1. 设计 → 应用（下行）
**禁止**。设计层定义本体结构和生命周期，**不得**依赖应用层。

```python
# ❌ 错误: 设计层导入应用层
# 在 design/ 下任何文件中
from odap.biz.core.ontology.application import ...
from ..runtime import ...  # ❌
```

### 2. 应用 → 设计（上行）
**只允许通过 contract**。应用层只能通过 `design/contract/` 读取设计数据。

```python
# ✅ 正确: 通过契约层
from odap.biz.core.ontology.design.contract import get_design_contract

contract = get_design_contract()
entity = contract.get_entity_type("et-001")  # 返回 EntityTypeView (frozen)
schema = contract.get_entity_type_schema_json("et-001")

# ❌ 错误: 直接导入设计层内部
from odap.biz.core.ontology.design.model import ModelService  # ❌
from odap.biz.core.ontology.design.schema.document import ...  # ❌
```

### 3. 任何 → infra/query
**允许**。统一查询服务是查询本体数据的标准方式，应用层和设计层都通过它查询。

```python
# ✅ 正确: 使用统一查询服务
from odap.infra.query import get_ontology_design_source

source = get_ontology_design_source()
entities = source.query_object_types({"workspace_id": "ws-001"})
schema = source.get_entity_schema_json("et-001")
```

### 4. 视图对象 (View Objects)
Contract 返回的所有视图都是 `@dataclass(frozen=True)`，**不可变**。这防止应用层意外修改设计层状态。

```python
entity: EntityTypeView = contract.get_entity_type("et-001")
entity.name = "new"  # ❌ FrozenInstanceError
```

## 文件组织

### 设计层 (design/)
| 子目录 | 职责 |
|--------|------|
| `model/` | 实体类型、关系类型的数据模型 |
| `engine/` | 版本、审计、验证引擎 |
| `version/` | 本体版本管理 |
| `ingestion/` | 数据摄入管道（结构化/非结构化） |
| `schema/` | 本体 schema 定义 |
| `ingestion_split/` | 拆分式摄入器（新闻、手工、生成器） |
| `mock_data/` | Mock 数据生成器 |
| `interfaces/` | 内部接口 |
| `impl/` | 内部实现 |
| `services/` | 业务服务 |
| `storage/` | SQLite 存储层 |
| `models/` | Pydantic 数据模型 |
| **`contract/`** | **公共契约（唯一跨边界出口）** |

### 应用层 (application/)
| 子目录 | 职责 |
|--------|------|
| `runtime/` | 本体运行时引擎（函数/动作/状态机） |
| `servitization/` | 知识服务化（技能生成、API 部署） |
| `team_agent/` | 多智能体协调 |
| `oms/` | 对象管理服务（运行时对象生命周期） |
| `abution_graph/` | Abution 推理图谱 |
| `harness/` | 蓝图管理、测试 Harness |
| `query_api/` | 查询/分析 API（应用层 API 入口） |

## 自动化测试

[test_architecture_boundary.py](../../../tests/unit/test_architecture_boundary.py) 强制执行以下规则：

1. `test_application_does_not_import_design_internals` — 应用层不得导入设计层内部
2. `test_design_does_not_import_application` — 设计层不得依赖应用层
3. `test_contract_layer_exposes_factory` — 契约层必须暴露 `get_design_contract()` 工厂
4. `test_contract_interface_defines_immutable_views` — 视图对象必须 `@dataclass(frozen=True)`

## 统一查询服务

[odap/infra/query/](../../../odap/infra/query/) 作为语义查询的统一入口，提供：

- `QueryService` — 单一查询服务门面
- `SchemaSource` / `EntitySource` / `TopoSource` / `TemporalSource` — 数据源协议
- `OntologyDesignSource` — 桥接设计契约到查询服务

`OntologyDesignSource` 是 **唯一** 允许从 `odap.infra.query` 导入 `odap.biz.core.ontology.design.*` 的地方，且只能导入 `design.contract`。

## 迁移历史

| 时间 | 变更 |
|------|------|
| 2026-06-02 | 重构: 将 16 个本体子模块拆分为 `design/` 和 `application/` 两个隔离子系统 |
| 2026-06-02 | 新增: `design/contract/` 公共契约层 |
| 2026-06-02 | 新增: `odap.infra.query.ontology_source` 统一查询桥接 |
| 2026-06-02 | 新增: `test_architecture_boundary.py` 强制执行隔离规则 |
