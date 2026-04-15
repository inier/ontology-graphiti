# ADR-035: Palantir AIP Ontology 参考架构

> **优先级**: P0 | **相关 ADR**: ADR-032, ADR-021, ADR-002

**版本**: 1.0.0 | **日期**: 2026-04-16

---

## 1. 概述

本文档参考 Palantir AIP Ontology 的设计理念，定义领域本体的标准结构。

**Palantir AIP Ontology 核心概念**:
- Object Types（对象类型）
- Properties（属性）
- Actions（行动）
- Rules（规则）

---

## 2. Palantir Ontology 架构

### 2.1 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                    Palantir AIP Ontology                         │
├─────────────────────────────────────────────────────────────┤
│  Object Types  │  Properties  │  Actions  │  Rules        │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Object Types (对象类型)

Object Type 是本体的核心实体类型，类似于面向对象编程中的类。

| 组件 | 说明 | 示例 |
|------|------|------|
| `name` | 类型名称 | `Unit`, `Location`, `Equipment` |
| `pluralName` | 复数名称 | `Units`, `Locations` |
| `description` | 描述 | |
| `properties` | 属性列表 | |
| `actions` | 可执行行动 | |
| `links` | 可关联的其他类型 | |

### 2.3 Properties (属性)

属性定义 Object Type 的特征。

| 属性类型 | 说明 | 示例 |
|---------|------|------|
| `StringProperty` | 字符串 | `name`, `status` |
| `IntegerProperty` | 整数 | `strength`, `count` |
| `FloatProperty` | 浮点数 | `coordinates`, `speed` |
| `BooleanProperty` | 布尔值 | `isActive`, `isEnemy` |
| `TimestampProperty` | 时间戳 | `createdAt`, `updatedAt` |
| `EnumProperty` | 枚举值 | `unit_type`, `side` |

### 2.4 Actions (行动)

Action 是 Object Type 可执行的操作。

```json
{
  "actionName": "attack",
  "description": "执行攻击行动",
  "parameters": [
    {
      "name": "target",
      "type": "ObjectTypeReference",
      "objectType": "Unit"
    },
    {
      "name": "weapon",
      "type": "Enum",
      "values": ["direct_fire", "indirect_fire"]
    }
  ],
  "resultType": "ActionResult",
  "requiresApproval": true
}
```

### 2.5 Rules (规则)

Rules 定义本体中的约束和推导逻辑。

```json
{
  "ruleName": "roe_check",
  "description": "交战规则检查",
  "condition": "actor.classification != 'civilian' AND target.classification != 'civilian'",
  "effect": "allow",
  "priority": 100
}
```

---

## 3. 本系统 Ontology 结构

### 3.1 Object Types 定义

#### 3.1.1 Unit (单元)

```json
{
  "name": "Unit",
  "pluralName": "Units",
  "description": "军事单元",
  "properties": [
    { "name": "unit_id", "type": "StringProperty", "required": true },
    { "name": "name", "type": "StringProperty", "required": true },
    { "name": "side", "type": "EnumProperty", "values": ["red", "blue", "neutral"], "required": true },
    { "name": "unit_type", "type": "EnumProperty", "values": ["infantry", "armor", "artillery", "air", "naval"], "required": true },
    { "name": "strength", "type": "IntegerProperty", "min": 0 },
    { "name": "status", "type": "EnumProperty", "values": ["idle", "moving", "engaged", "destroyed"] },
    { "name": "location", "type": "StringProperty" },
    { "name": "coordinates", "type": "FloatArrayProperty", "dimensions": 2 },
    { "name": "combat_power", "type": "FloatProperty", "min": 0.0, "max": 1.0 },
    { "name": "morale", "type": "FloatProperty", "min": 0.0, "max": 1.0 },
    { "name": "supply_level", "type": "FloatProperty", "min": 0.0, "max": 1.0 },
    { "name": "casualty_rate", "type": "FloatProperty", "min": 0.0, "max": 1.0 }
  ],
  "actions": ["move", "attack", "defend", "reinforce", "retreat"],
  "links": [
    { "targetType": "Location", "linkName": "located_at" },
    { "targetType": "Unit", "linkName": "attached_to" },
    { "targetType": "Unit", "linkName": "engaged_with" }
  ]
}
```

#### 3.1.2 Location (位置)

```json
{
  "name": "Location",
  "pluralName": "Locations",
  "description": "地理位置",
  "properties": [
    { "name": "location_id", "type": "StringProperty", "required": true },
    { "name": "name", "type": "StringProperty", "required": true },
    { "name": "location_type", "type": "EnumProperty", "values": ["zone", "sector", "point", "area"], "required": true },
    { "name": "coordinates", "type": "FloatArrayProperty", "dimensions": 2 },
    { "name": "parent_location", "type": "StringProperty" },
    { "name": "classification", "type": "EnumProperty", "values": ["civilian", "military", "mixed", "restricted"] }
  ],
  "actions": [],
  "links": [
    { "targetType": "Location", "linkName": "adjacent_to" },
    { "targetType": "Unit", "linkName": "contains" }
  ]
}
```

#### 3.1.3 Equipment (装备)

```json
{
  "name": "Equipment",
  "pluralName": "Equipment",
  "description": "军事装备",
  "properties": [
    { "name": "equipment_id", "type": "StringProperty", "required": true },
    { "name": "name", "type": "StringProperty", "required": true },
    { "name": "equipment_type", "type": "EnumProperty", "values": ["vehicle", "weapon", "sensor", "communication", "protection"], "required": true },
    { "name": "operational_status", "type": "EnumProperty", "values": ["operational", "damaged", "destroyed", "maintenance"] },
    { "name": "capabilities", "type": "ObjectProperty" },
    { "name": "assigned_to", "type": "StringProperty" }
  ],
  "actions": [],
  "links": [
    { "targetType": "Unit", "linkName": "assigned_to" }
  ]
}
```

#### 3.1.4 Event (事件)

```json
{
  "name": "Event",
  "pluralName": "Events",
  "description": "领域事件",
  "properties": [
    { "name": "event_id", "type": "StringProperty", "required": true },
    { "name": "event_type", "type": "EnumProperty", "values": ["contact", "attack", "movement", "communication", "observation"], "required": true },
    { "name": "timestamp", "type": "TimestampProperty", "required": true },
    { "name": "location", "type": "StringProperty" },
    { "name": "coordinates", "type": "FloatArrayProperty", "dimensions": 2 },
    { "name": "description", "type": "StringProperty" },
    { "name": "phase", "type": "EnumProperty", "values": ["initial_contact", "engagement", "resolution", "aftermath"] }
  ],
  "actions": [],
  "links": [
    { "targetType": "Unit", "linkName": "participants" }
  ]
}
```

### 3.2 Relations (关系)

| 关系类型 | 源类型 | 目标类型 | 说明 |
|---------|--------|---------|------|
| `located_at` | Unit | Location | 单元位于 |
| `contains` | Location | Unit | 位置包含单元 |
| `adjacent_to` | Location | Location | 位置相邻 |
| `engaged_with` | Unit | Unit | 单元交战 |
| `attached_to` | Unit | Unit | 单元隶属 |
| `communicates_with` | Unit | Unit | 单元通信 |
| `supports` | Unit | Unit | 单元支援 |
| `opposes` | Unit | Unit | 单元对抗 |
| `assigned_to` | Equipment | Unit | 装备配属 |

### 3.3 Actions (行动)

| 行动 | 适用类型 | 参数 | 说明 |
|------|---------|------|------|
| `move` | Unit | destination, speed | 移动 |
| `attack` | Unit | target, weapon, mode | 攻击 |
| `defend` | Unit | position, duration | 防御 |
| `reinforce` | Unit | source, strength | 增援 |
| `retreat` | Unit | destination | 撤退 |
| `observe` | Unit | target, sensor | 侦察 |
| `communicate` | Unit | recipient, message | 通信 |

---

## 4. 与 ADR-032 OntologyDocument 的映射

### 4.1 映射关系

| Palantir 概念 | ADR-032 OntologyDocument |
|--------------|-------------------------|
| Object Type | `entities[].entity_type` |
| Property | `entities[].basic_properties`, `statistical_properties`, `capabilities` |
| Action | `actions[]` |
| Rule | `rules[]` |
| Link | `relations[]` |

### 4.2 转换示例

```json
// ADR-032 OntologyDocument
{
  "entities": [
    {
      "entity_id": "unit-red-001",
      "entity_type": "Unit",
      "basic_properties": {
        "side": "red",
        "unit_type": "armor"
      },
      "statistical_properties": {
        "combat_power": 0.78
      }
    }
  ]
}

// 转换为 Palantir Object
// ObjectType: Unit
// Properties: side=red, unit_type=armor, combat_power=0.78
```

---

## 5. 实现参考

### 5.1 Ontology 定义文件

```
odap/biz/ontology/
├── definitions/           # 本体定义
│   ├── unit.json         # Unit 类型定义
│   ├── location.json     # Location 类型定义
│   ├── equipment.json    # Equipment 类型定义
│   └── event.json        # Event 类型定义
├── schema/
│   └── ontology.schema.json   # JSON Schema
└── validator.py         # 本体验证器
```

### 5.2 核心接口

```python
class OntologyDefinition:
    """本体定义"""

    def get_object_type(self, type_name: str) -> dict:
        """获取对象类型定义"""

    def list_object_types(self) -> list[str]:
        """列出所有对象类型"""

    def get_property_definition(self, object_type: str, property_name: str) -> dict:
        """获取属性定义"""

    def get_actions(self, object_type: str) -> list[dict]:
        """获取对象类型的可用行动"""

    def get_links(self, object_type: str) -> list[dict]:
        """获取对象类型的关联关系"""

class OntologyValidator:
    """本体验证器"""

    def validate_object(self, obj: dict) -> ValidationResult:
        """验证对象是否符合本体定义"""

    def validate_relation(self, source: str, relation: str, target: str) -> bool:
        """验证关系是否符合本体定义"""
```

---

## 6. 相关文档

- [ADR-032: 标准化本体文档格式](ADR-032_standard_ontology_document_format.md)
- [ADR-021: 领域实体标准本体库](ADR-021_领域实体标准本体库.md)
- [Ontology 模块](../modules/ontology/DESIGN.md)
