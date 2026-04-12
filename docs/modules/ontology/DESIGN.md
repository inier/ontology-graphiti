# Ontology 本体管理层设计文档

## 1. 模块概述

### 1.1 模块定位

`ontology` 是战场的领域本体模型，定义战场中的实体类型、关系类型和约束规则。是 Graphiti 图谱的数据模式基础。

### 1.2 核心职责

| 职责 | 描述 |
|------|------|
| 本体模型定义 | 定义战场实体和关系的类型系统 |
| 模式管理 | 管理本体的版本和变更 |
| 验证规则 | 实体和关系的验证逻辑 |
| Graphiti 集成 | 与 Graphiti 的无缝集成 |

---

## 2. 本体模型设计

### 2.1 实体类型层次

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Battlefield Ontology                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                            ┌─────────────┐                                 │
│                            │   Entity    │                                 │
│                            │  (基类)     │                                 │
│                            └──────┬──────┘                                 │
│                    ┌──────────────┼──────────────┐                         │
│                    ▼              ▼              ▼                          │
│            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                 │
│            │   Target   │ │    Unit     │ │   Weapon   │                 │
│            │  (目标)    │ │  (单元)    │ │  (武器)   │                 │
│            └──────┬──────┘ └──────┬──────┘ └─────────────┘                 │
│                   │             │                                           │
│     ┌─────────────┼─────────────┼─────────────┐                           │
│     ▼             ▼             ▼             ▼                             │
│ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐                       │
│ │ Radar │ │Command│ │Supply │ │Launcher│ │SAM    │                       │
│ │ 雷达  │ │Center │ │Depot  │ │发射架  │ │防空   │                       │
│ └───────┘ └───────┘ └───────┘ └───────┘ └───────┘                       │
│                                                                              │
│            ┌─────────────┐ ┌─────────────┐                                 │
│            │ Intelligence│ │ StrikeOrder │                                 │
│            │  (情报)    │ │ (打击命令)  │                                 │
│            └─────────────┘ └─────────────┘                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心实体定义

```python
# ontology/battlefield_ontology.py
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import uuid

class EntityCategory(str, Enum):
    """实体类别"""
    TARGET = "target"
    UNIT = "unit"
    WEAPON = "weapon"
    INTELLIGENCE = "intelligence"
    STRIKE_ORDER = "strike_order"
    THREAT = "threat"
    LOCATION = "location"

class TargetType(str, Enum):
    """目标类型"""
    RADAR = "radar"
    COMMAND_CENTER = "command_center"
    SUPPLY_DEPOT = "supply_depot"
    LAUNCHER = "launcher"
    AIR_DEFENSE = "air_defense"
    COMMUNICATION = "communication"
    BUILDING = "building"
    VEHICLE = "vehicle"

class UnitType(str, Enum):
    """单元类型"""
    INFANTRY = "infantry"
    ARMOR = "armor"
    AVIATION = "aviation"
    NAVAL = "naval"
    ARTILLERY = "artillery"

class ThreatLevel(str, Enum):
    """威胁等级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class BaseEntity(BaseModel):
    """基础实体"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: EntityCategory
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        use_enum_values = True

class Target(BaseEntity):
    """打击目标实体"""
    category: EntityCategory = EntityCategory.TARGET

    # 目标特定属性
    target_type: TargetType
    location: Dict[str, float]  # {"lat": xx, "lon": xx, "alt": xx}
    region: str = "unknown"  # A区/B区/C区
    threat_level: ThreatLevel = ThreatLevel.MEDIUM
    status: str = "active"  # active/damaged/destroyed/unknown
    confirmation_level: str = "unconfirmed"  # unconfirmed/pending/confirmed/verified
    classification: str = "military"  # military/civilian/protected

    # 发现信息
    discovered_at: Optional[datetime] = None
    discovered_by: Optional[str] = None
    first_detected_location: Optional[Dict[str, float]] = None

    # 打击信息
    destroyed_at: Optional[datetime] = None
    destroyed_by: Optional[str] = None

    # 关联
    associated_targets: List[str] = Field(default_factory=list)
    supporting_targets: List[str] = Field(default_factory=list)

    @field_validator('classification')
    @classmethod
    def validate_classification(cls, v):
        if v not in ['military', 'civilian', 'protected']:
            raise ValueError("classification must be military/civilian/protected")
        return v

    @property
    def is_protected(self) -> bool:
        """是否受保护目标"""
        return self.classification in ['civilian', 'protected']

class Unit(BaseEntity):
    """作战单元实体"""
    category: EntityCategory = EntityCategory.UNIT

    unit_type: UnitType
    unit_id: str  # 单元标识
    location: Dict[str, float]
    affiliation: str = "friendly"  # friendly/hostile/neutral
    status: str = "ready"  # ready/deployed/damaged/destroyed
    combat_capability: float = Field(default=50.0, ge=0, le=100)
    morale: float = Field(default=75.0, ge=0, le=100)

    # 任务
    current_mission: Optional[str] = None
    assigned_targets: List[str] = Field(default_factory=list)

class Weapon(BaseEntity):
    """武器实体"""
    category: EntityCategory = EntityCategory.WEAPON

    weapon_id: str
    weapon_type: str
    platform: str = "ground"  # aircraft/ship/ground
    effective_range: float  # 公里
    payload: float  # kg
    status: str = "available"  # available/deployed/expended
    accuracy: float = Field(default=0.8, ge=0, le=1)

    # 成本
    unit_cost: float = 0.0
    ammunition_remaining: int = 0

class IntelligenceReport(BaseEntity):
    """情报报告实体"""
    category: EntityCategory = EntityCategory.INTELLIGENCE

    report_id: str
    source: str  # satellite/drone/radar/human
    confidence: float = Field(ge=0, le=1)
    content: str

    # 发现的目标
    detected_targets: List[str] = Field(default_factory=list)
    detected_locations: List[Dict[str, float]] = Field(default_factory=list)

    # 时间信息
    detected_at: datetime
    reported_at: datetime = Field(default_factory=datetime.now)
    valid_from: datetime = Field(default_factory=datetime.now)
    valid_to: Optional[datetime] = None

    # 分类
    intel_type: str = "tactical"  # strategic/tactical/technical
    classification: str = "secret"  # top_secret/secret/confidential/unclassified

class StrikeOrder(BaseEntity):
    """打击命令实体"""
    category: EntityCategory = EntityCategory.STRIKE_ORDER

    order_id: str
    target_id: str
    weapon_type: str
    weapon_id: Optional[str] = None

    # 状态
    status: str = "pending"  # pending/approved/executing/executed/failed/cancelled
    priority: int = Field(default=1, ge=1, le=5)

    # 授权
    issued_by: str  # Commander Agent ID
    approved_by: Optional[str] = None
    executed_by: Optional[str] = None

    # 时间
    issued_at: datetime = Field(default_factory=datetime.now)
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None

    # 结果
    result: Optional[Dict[str, Any]] = None
    target_destroyed: bool = False

    # 证据链
    supporting_intel: List[str] = Field(default_factory=list)
```

---

## 3. 关系类型定义

### 3.1 关系类型枚举

```python
# ontology/relations.py
from enum import Enum

class RelationType(str, Enum):
    """关系类型"""
    # 目标关系
    DETECTED_AT = "DETECTED_AT"           # 情报发现目标
    LOCATED_AT = "LOCATED_AT"             # 位于
    THREATENED_BY = "THREATENED_BY"       # 被威胁
    THREATENS = "THREATENS"               # 威胁
    SUPPORTS = "SUPPORTS"                # 支援
    PART_OF = "PART_OF"                   # 组成
    COMMANDED_BY = "COMMANDED_BY"         # 被指挥

    # 打击关系
    ATTACKED_BY = "ATTACKED_BY"           # 被攻击
    ATTACKS = "ATTACKS"                   # 攻击
    EVIDENCE_FOR = "EVIDENCE_FOR"         # 证据
    DESTROYED_BY = "DESTROYED_BY"         # 被摧毁

    # 情报关系
    REPORTED_IN = "REPORTED_IN"          # 包含在报告中
    CORROBORATES = "CORROBORATES"        # 证实
    CONTRADICTS = "CONTRADICTS"          # 矛盾

    # 指挥关系
    ORDERS = "ORDERS"                    # 下令
    EXECUTES = "EXECUTES"                # 执行

class RelationConstraints(BaseModel):
    """关系约束"""
    source_categories: List[EntityCategory]
    target_categories: List[EntityCategory]
    required_source_props: Dict[str, Any] = {}
    required_target_props: Dict[str, Any] = {}
    valid_properties: List[str] = []

RELATION_CONSTRAINTS = {
    RelationType.DETECTED_AT: RelationConstraints(
        source_categories=[EntityCategory.INTELLIGENCE],
        target_categories=[EntityCategory.TARGET],
        required_source_props={"confidence": ">0.5"},
        valid_properties=["confidence", "location_accuracy"]
    ),
    RelationType.ATTACKED_BY: RelationConstraints(
        source_categories=[EntityCategory.TARGET],
        target_categories=[EntityCategory.STRIKE_ORDER],
        valid_properties=["damage_assessment", "result"]
    ),
    RelationType.EVIDENCE_FOR: RelationConstraints(
        source_categories=[EntityCategory.INTELLIGENCE],
        target_categories=[EntityCategory.STRIKE_ORDER],
        valid_properties=["confidence"]
    ),
}
```

---

## 4. 本体验证规则

### 4.1 实体验证

```python
# ontology/validators.py
from pydantic import validator, ValidationError

class OntologyValidator:
    """本体验证器"""

    @staticmethod
    def validate_target(target: Target) -> List[str]:
        """验证目标实体"""
        errors = []

        # 保护目标检查
        if target.is_protected and target.classification != "military":
            if target.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]:
                errors.append(
                    f"Protected target {target.name} cannot have critical/high threat level"
                )

        # 位置验证
        if target.location:
            lat = target.location.get("lat", 0)
            lon = target.location.get("lon", 0)
            if not (-90 <= lat <= 90):
                errors.append(f"Invalid latitude: {lat}")
            if not (-180 <= lon <= 180):
                errors.append(f"Invalid longitude: {lon}")

        return errors

    @staticmethod
    def validate_strike_order(order: StrikeOrder) -> List[str]:
        """验证打击命令"""
        errors = []

        # 状态流转验证
        valid_status_flow = {
            "pending": ["approved", "cancelled"],
            "approved": ["executing", "cancelled"],
            "executing": ["executed", "failed"],
            "executed": [],
            "failed": [],
            "cancelled": []
        }

        # 检查打击目标是否存在
        if order.status in ["approved", "executing", "executed"]:
            if not order.target_id:
                errors.append("Target ID required for approved orders")

        return errors

    @staticmethod
    def validate_relation(
        source: BaseEntity,
        target: BaseEntity,
        relation_type: RelationType
    ) -> List[str]:
        """验证关系合法性"""
        errors = []

        # 检查关系约束
        constraints = RELATION_CONSTRAINTS.get(relation_type)
        if constraints:
            if source.category not in constraints.source_categories:
                errors.append(
                    f"Source category {source.category} not allowed for {relation_type}"
                )
            if target.category not in constraints.target_categories:
                errors.append(
                    f"Target category {target.category} not allowed for {relation_type}"
                )

        return errors
```

---

## 5. OntologyManager

```python
# ontology/ontology_manager.py
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

class OntologyManager:
    """本体管理器"""

    def __init__(self, graphiti_client):
        self.graphiti = graphiti_client

    async def register_entity(self, entity: BaseEntity) -> str:
        """注册实体到图谱"""
        entity_id = await self.graphiti.add_entity(
            name=entity.name,
            entity_type=entity.category.value,
            properties=entity.model_dump(exclude={"id"}),
            categories=[entity.category.value]
        )
        return entity_id

    async def register_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        properties: Dict[str, Any] = None
    ) -> str:
        """注册关系到图谱"""
        return await self.graphiti.add_relation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type.value,
            properties=properties or {}
        )

    async def query_by_type(
        self,
        entity_category: EntityCategory,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """按类型查询实体"""
        return await self.graphiti.search_episodes(
            query=f"type:{entity_category.value}",
            categories=[entity_category.value]
        )

    async def export_ontology(self) -> Dict[str, Any]:
        """导出本体定义"""
        return {
            "entities": {
                "Target": Target.model_json_schema(),
                "Unit": Unit.model_json_schema(),
                "Weapon": Weapon.model_json_schema(),
                "IntelligenceReport": IntelligenceReport.model_json_schema(),
                "StrikeOrder": StrikeOrder.model_json_schema()
            },
            "relations": {
                rt.value: {
                    "source": constraints.source_categories,
                    "target": constraints.target_categories
                }
                for rt, constraints in RELATION_CONSTRAINTS.items()
            },
            "exported_at": datetime.now().isoformat()
        }
```

---

## 6. 目录结构

```
ontology/
├── __init__.py
├── battlefield_ontology.py    # 核心实体定义
├── relations.py               # 关系类型定义
├── validators.py              # 验证规则
├── ontology_manager.py        # 本体管理器
├── versions/                  # 版本管理
│   └── v1.0.0.py
└── schemas/                   # JSON Schema
    └── battlefield.json
```

---

## 7. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-11 | 初始版本 |
