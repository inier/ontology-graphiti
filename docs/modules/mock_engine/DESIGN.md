# Mock 数据生成引擎 (Mock Data Engine) - 设计文档

> **优先级**: P1 | **相关 ADR**: ADR-018

**版本**: 1.0.0 | **日期**: 2026-04-16

---

## 1. 模块概述

Mock 数据生成引擎负责**为构建领域本体生成样本数据**（静态），是数据准备阶段的核心模块。

**核心职责**:
- 随机数据生成（基于概率分布）
- 样本数据构建
- 领域本体填充

**与模拟推演的区别**:

| 概念 | 职责 | 模块位置 |
|------|------|---------|
| **Mock 数据生成** | 为构建领域本体生成样本数据（静态） | `odap/biz/ontology/mock_data/` |
| **模拟推演** | 对选定方案进行沙盘验证（动态） | `odap/biz/simulator/` |

---

## 2. 核心架构

### 2.1 系统分层

```
┌─────────────────────────────────────────────────────────────┐
│                   Mock Data Engine                            │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: 数据生成 (Data Generation)                        │
│  - 实体生成 (Entity Generation)                            │
│  - 关系生成 (Relation Generation)                          │
│  - 事件生成 (Event Generation)                             │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: 数据格式化 (Data Formatting)                      │
│  - OntologyDocument 格式                                   │
│  - Schema 验证                                             │
│  - 导出管理                                                │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: 数据存储 (Data Storage)                          │
│  - 场景持久化                                              │
│  - 数据快照                                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 核心组件

### 3.1 DataGenerator

```python
class DataGenerator:
    """数据生成器"""

    def generate_simulation_data(self) -> dict:
        """
        生成模拟数据

        返回结构：
        {
            "locations": [...],
            "entities": [...],
            "relations": [...],
            "events": [...]
        }
        """
```

### 3.2 实体数据

实体数据遵循 OntologyDocument 格式：

```python
@dataclass
class MockEntity:
    entity_id: str
    entity_type: str  # Unit / Equipment / Location / Person / Organization
    name: str
    properties: dict  # 通用属性（位置、状态等）
    statistical_properties: dict  # 统计指标
    capabilities: dict  # 能力维度
    constraints: list  # 约束
    relationships: dict  # 关系（contains, adjacent_to, located_at 等）
```

### 3.3 关系类型

| 关系类型 | 说明 | 示例 |
|---------|------|------|
| `contains` | 包含关系 | LOC_A contains UNIT_1 |
| `adjacent_to` | 相邻关系 | LOC_A adjacent_to LOC_B |
| `located_at` | 位置关系 | UNIT_1 located_at LOC_A |
| `attached_to` | 隶属关系 | UNIT_1 attached_to UNIT_2 |
| `engaged_with` | 交战关系 | UNIT_1 engaged_with UNIT_2 |
| `communicates_with` | 通信关系 | UNIT_1 communicates_with UNIT_2 |
| `supports` | 支持关系 | UNIT_1 supports UNIT_2 |
| `opposes` | 对抗关系 | UNIT_1 opposes UNIT_2 |

---

## 4. 数据生成流程

```
┌─────────────────────────────────────────┐
│  1. 初始化参数                          │
│  - 生成器种子                           │
│  - 数量配置                             │
│  - 关系密度                             │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│  2. 实体生成                            │
│  - Locations                            │
│  - Entities (Units, Equipment, etc.)    │
│  - 生成唯一 ID                          │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│  3. 关系生成                            │
│  - 基于实体类型匹配                     │
│  - 关系密度控制                         │
│  - 避免孤立节点                         │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│  4. 事件生成                            │
│  - 时间线构建                           │
│  - 状态变更事件                         │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│  5. 格式验证 & 存储                     │
│  - OntologyDocument Schema              │
│  - 场景快照保存                         │
└─────────────────────────────────────────┘
```

---

## 5. 配置参数

```python
# 数据生成配置
DATA_GENERATION_CONFIG = {
    # 实体数量
    "entity_counts": {
        "locations": 10,
        "units": 20,
        "equipment": 30,
        "infrastructure": 15,
    },

    # 关系密度 (0-1)
    "relation_density": {
        "contains": 0.3,
        "adjacent_to": 0.5,
        "located_at": 0.8,
        "engaged_with": 0.2,
    },

    # 统计属性范围
    "statistical_ranges": {
        "combat_power": (0.0, 1.0),
        "morale": (0.0, 1.0),
        "supply_level": (0.0, 1.0),
        "casualty_rate": (0.0, 1.0),
    }
}
```

---

## 6. 与其他模块的集成

### 6.1 与 Simulator 的关系

```
mock_engine/ (数据准备)
    │
    │ 生成样本数据
    ▼
simulator/ (推演执行)
    │
    │ 加载预置数据
    ▼
SimulationEngine.run_simulation()
```

### 6.2 与 Web Service 的关系

```python
# Web Service 从 mock_engine 获取预置数据
from odap.biz.ontology.mock_data import DataGenerator

class MockDataWebService:
    def __init__(self):
        self.generator = DataGenerator()
        self._load_initial_data()

    def _load_initial_data(self):
        """加载初始模拟数据"""
        data = self.generator.generate_simulation_data()
        for doc in data.get("documents", []):
            self.scenario_store.add_document(self.default_scenario_id, doc)
```

---

## 7. 相关文档

- [ADR-018: 领域模拟推演引擎](../../adr/ADR-018_domain_simulator_engine.md)
- [Simulator 模拟推演引擎](../simulator/DESIGN.md)
- [Ontology 本体模块](../ontology/DESIGN.md)
