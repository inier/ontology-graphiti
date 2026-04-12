# Ontology 本体管理层设计文档

> **优先级**: P1 | **相关 ADR**: ADR-021, ADR-024

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

---

## 7. 模拟推演本体增强

### 7.1 模拟推演实体定义

```python
# ontology/simulation_ontology.py

class SimulationEntityCategory(str, Enum):
    """模拟推演实体类别"""
    SIMULATION_SCENARIO = "simulation_scenario"           # 模拟场景
    SIMULATION_PARAMETERS = "simulation_parameters"       # 模拟参数
    SIMULATION_VERSION = "simulation_version"             # 模拟版本
    SIMULATION_EXECUTION = "simulation_execution"         # 模拟执行
    SIMULATION_RESULT = "simulation_result"               # 模拟结果
    WHAT_IF_ANALYSIS = "what_if_analysis"                 # What-if分析
    SENSITIVITY_ANALYSIS = "sensitivity_analysis"         # 敏感性分析
    COMPARISON_ANALYSIS = "comparison_analysis"           # 对比分析

class SimulationScenarioType(str, Enum):
    """模拟场景类型"""
    DECISION_ANALYSIS = "decision_analysis"               # 决策分析
    RESOURCE_ALLOCATION = "resource_allocation"           # 资源分配
    RISK_ASSESSMENT = "risk_assessment"                   # 风险评估
    WHAT_IF_EXPLORATION = "what_if_exploration"           # What-if探索
    PERFORMANCE_EVALUATION = "performance_evaluation"     # 性能评估
    TRAINING_SCENARIO = "training_scenario"               # 训练场景

class SimulationStatus(str, Enum):
    """模拟状态"""
    DRAFT = "draft"                 # 草稿
    READY = "ready"                 # 就绪
    RUNNING = "running"             # 运行中
    PAUSED = "paused"               # 已暂停
    COMPLETED = "completed"         # 已完成
    FAILED = "failed"               # 失败
    CANCELLED = "cancelled"         # 已取消

class SimulationScenario(BaseEntity):
    """模拟场景实体"""
    category: EntityCategory = EntityCategory.SIMULATION_SCENARIO
    
    scenario_type: SimulationScenarioType
    scenario_name: str
    description: str = ""
    
    # 基础配置
    base_scenario_id: Optional[str] = None     # 基于哪个场景创建
    base_version_id: Optional[str] = None      # 基于哪个版本创建
    
    # 参数配置
    parameter_schema: Dict[str, Any] = Field(default_factory=dict)  # 参数Schema定义
    default_parameters: Dict[str, Any] = Field(default_factory=dict)  # 默认参数
    
    # 执行配置
    max_duration_seconds: int = 3600           # 最大执行时长
    resource_limits: Dict[str, Any] = Field(default_factory=dict)    # 资源限制
    isolation_level: str = "strict"            # 隔离级别: strict/moderate/relaxed
    
    # 状态管理
    status: SimulationStatus = SimulationStatus.DRAFT
    created_by: str = ""                       # 创建者
    last_modified_by: str = ""                 # 最后修改者
    last_modified_at: datetime = Field(default_factory=datetime.now)
    
    # 统计信息
    execution_count: int = 0                    # 执行次数
    success_rate: float = 0.0                   # 成功率
    average_duration_seconds: float = 0.0       # 平均执行时长
    
    # 关联
    versions: List[str] = Field(default_factory=list)          # 版本列表
    current_version_id: Optional[str] = None    # 当前版本ID
    executions: List[str] = Field(default_factory=list)        # 执行记录
    recent_results: List[str] = Field(default_factory=list)    # 最近结果

class SimulationVersion(BaseEntity):
    """模拟版本实体"""
    category: EntityCategory = EntityCategory.SIMULATION_VERSION
    
    scenario_id: str                            # 所属场景
    version_number: str                         # 版本号 (v1.0.0, v1.0.1, etc.)
    parent_version_id: Optional[str] = None     # 父版本ID (用于分支)
    
    # 变更信息
    changes: Dict[str, Any] = Field(default_factory=dict)      # 变更内容
    change_summary: str = ""                    # 变更摘要
    change_author: str = ""                     # 变更作者
    
    # 参数快照
    parameter_snapshot: Dict[str, Any] = Field(default_factory=dict)  # 参数快照
    
    # 配置快照
    configuration_snapshot: Dict[str, Any] = Field(default_factory=dict)  # 配置快照
    
    # 状态
    is_current: bool = False                    # 是否为当前版本
    is_stable: bool = False                     # 是否为稳定版本
    
    # 执行记录
    execution_ids: List[str] = Field(default_factory=list)     # 使用该版本的执行
    success_count: int = 0                      # 成功次数
    failure_count: int = 0                      # 失败次数
    
    # 回滚信息
    rollback_target_id: Optional[str] = None    # 可回滚到的目标版本
    rollback_compatibility: bool = True         # 回滚兼容性

class SimulationExecution(BaseEntity):
    """模拟执行实体"""
    category: EntityCategory = EntityCategory.SIMULATION_EXECUTION
    
    scenario_id: str                            # 所属场景
    version_id: str                             # 使用的版本
    execution_number: int = 0                   # 执行编号
    
    # 执行配置
    parameters: Dict[str, Any] = Field(default_factory=dict)   # 执行参数
    configuration: Dict[str, Any] = Field(default_factory=dict)  # 执行配置
    
    # 状态追踪
    status: SimulationStatus = SimulationStatus.READY
    start_time: Optional[datetime] = None       # 开始时间
    end_time: Optional[datetime] = None         # 结束时间
    duration_seconds: Optional[float] = None    # 执行时长
    
    # 资源使用
    resource_usage: Dict[str, Any] = Field(default_factory=dict)  # 资源使用情况
    resource_limits_violated: bool = False      # 是否违反资源限制
    
    # 执行环境
    sandbox_id: Optional[str] = None            # 沙箱ID
    environment_id: Optional[str] = None        # 环境ID
    
    # 结果
    result_id: Optional[str] = None             # 结果实体ID
    result_status: Optional[str] = None         # 结果状态
    error_message: Optional[str] = None         # 错误信息
    stack_trace: Optional[str] = None           # 堆栈跟踪
    
    # 监控
    progress_percentage: float = 0.0            # 进度百分比
    checkpoints: List[Dict[str, Any]] = Field(default_factory=list)  # 检查点
    metrics_snapshots: List[Dict[str, Any]] = Field(default_factory=list)  # 指标快照
    
    # 实时数据
    realtime_data_url: Optional[str] = None     # 实时数据URL
    websocket_connections: int = 0              # WebSocket连接数

class SimulationResult(BaseEntity):
    """模拟结果实体"""
    category: EntityCategory = EntityCategory.SIMULATION_RESULT
    
    execution_id: str                           # 对应的执行
    scenario_id: str                            # 所属场景
    version_id: str                             # 使用的版本
    
    # 原始结果
    raw_data: Dict[str, Any] = Field(default_factory=dict)      # 原始数据
    processed_data: Dict[str, Any] = Field(default_factory=dict)  # 处理后的数据
    
    # 指标数据
    performance_metrics: Dict[str, float] = Field(default_factory=dict)  # 性能指标
    business_metrics: Dict[str, float] = Field(default_factory=dict)    # 业务指标
    quality_metrics: Dict[str, float] = Field(default_factory=dict)     # 质量指标
    
    # 详细结果
    detailed_results: List[Dict[str, Any]] = Field(default_factory=list)  # 详细结果
    events_log: List[Dict[str, Any]] = Field(default_factory=list)        # 事件日志
    state_changes: List[Dict[str, Any]] = Field(default_factory=list)     # 状态变更
    
    # 分析结果
    insights: List[str] = Field(default_factory=list)          # 洞察发现
    recommendations: List[str] = Field(default_factory=list)   # 建议推荐
    warnings: List[str] = Field(default_factory=list)          # 警告信息
    errors: List[str] = Field(default_factory=list)            # 错误信息
    
    # 可视化数据
    visualization_configs: Dict[str, Any] = Field(default_factory=dict)  # 可视化配置
    chart_data: Dict[str, Any] = Field(default_factory=dict)            # 图表数据
    report_data: Dict[str, Any] = Field(default_factory=dict)           # 报告数据
    
    # 版本管理
    result_version: str = "1.0.0"               # 结果版本
    is_baseline: bool = False                   # 是否为基线结果
    comparison_ids: List[str] = Field(default_factory=list)  # 对比结果ID
    
    # 存储信息
    storage_size_bytes: int = 0                 # 存储大小
    compression_ratio: float = 1.0              # 压缩比
    retention_period_days: int = 30             # 保留天数

class WhatIfAnalysis(BaseEntity):
    """What-if分析实体"""
    category: EntityCategory = EntityCategory.WHAT_IF_ANALYSIS
    
    base_scenario_id: str                       # 基础场景
    base_execution_id: str                      # 基础执行
    
    # 参数变化
    parameter_changes: Dict[str, Any] = Field(default_factory=dict)      # 参数变化
    change_description: str = ""                # 变化描述
    
    # 分析配置
    analysis_type: str = "sensitivity"          # 分析类型: sensitivity/impact/trend
    analysis_depth: str = "detailed"            # 分析深度: quick/detailed/comprehensive
    
    # 执行状态
    status: SimulationStatus = SimulationStatus.READY
    execution_ids: List[str] = Field(default_factory=list)      # 相关执行
    result_ids: List[str] = Field(default_factory=list)         # 相关结果
    
    # 分析结果
    impact_scores: Dict[str, float] = Field(default_factory=dict)        # 影响得分
    sensitivity_coefficients: Dict[str, float] = Field(default_factory=dict)  # 敏感性系数
    trend_analysis: Dict[str, Any] = Field(default_factory=dict)         # 趋势分析
    
    # 洞察发现
    key_insights: List[str] = Field(default_factory=list)       # 关键洞察
    risk_assessments: List[str] = Field(default_factory=list)   # 风险评估
    opportunity_areas: List[str] = Field(default_factory=list)  # 机会领域
    
    # 推荐
    parameter_recommendations: Dict[str, Any] = Field(default_factory=dict)  # 参数推荐
    strategy_recommendations: List[str] = Field(default_factory=list)        # 策略推荐
```

### 7.2 模拟推演关系定义

```python
# ontology/simulation_relations.py

class SimulationRelationType(str, Enum):
    """模拟推演关系类型"""
    # 场景管理关系
    HAS_VERSION = "HAS_VERSION"                 # 场景有版本
    IS_CURRENT_VERSION = "IS_CURRENT_VERSION"   # 是当前版本
    IS_BASED_ON = "IS_BASED_ON"                 # 基于
    
    # 执行关系
    EXECUTED_WITH = "EXECUTED_WITH"             # 使用执行
    PRODUCED_RESULT = "PRODUCED_RESULT"         # 产生结果
    USED_PARAMETERS = "USED_PARAMETERS"         # 使用参数
    
    # 分析关系
    COMPARES_WITH = "COMPARES_WITH"             # 与...对比
    ANALYZES_IMPACT = "ANALYZES_IMPACT"         # 分析影响
    SHOWS_SENSITIVITY = "SHOWS_SENSITIVITY"     # 显示敏感性
    
    # 版本管理
    BRANCHED_FROM = "BRANCHED_FROM"             # 从...分支
    MERGED_INTO = "MERGED_INTO"                 # 合并到
    ROLLBACK_TO = "ROLLBACK_TO"                 # 回滚到
    
    # 决策集成
    SIMULATES_DECISION = "SIMULATES_DECISION"   # 模拟决策
    EVALUATES_PLAN = "EVALUATES_PLAN"           # 评估方案
    OPTIMIZES_PARAMETERS = "OPTIMIZES_PARAMETERS"  # 优化参数

# 模拟推演关系约束
SIMULATION_RELATION_CONSTRAINTS = {
    SimulationRelationType.HAS_VERSION: RelationConstraints(
        source_categories=[SimulationEntityCategory.SIMULATION_SCENARIO],
        target_categories=[SimulationEntityCategory.SIMULATION_VERSION],
        valid_properties=["is_current", "stability"]
    ),
    SimulationRelationType.EXECUTED_WITH: RelationConstraints(
        source_categories=[SimulationEntityCategory.SIMULATION_SCENARIO],
        target_categories=[SimulationEntityCategory.SIMULATION_EXECUTION],
        valid_properties=["execution_number", "status"]
    ),
    SimulationRelationType.PRODUCED_RESULT: RelationConstraints(
        source_categories=[SimulationEntityCategory.SIMULATION_EXECUTION],
        target_categories=[SimulationEntityCategory.SIMULATION_RESULT],
        valid_properties=["result_type", "quality_score"]
    ),
    SimulationRelationType.COMPARES_WITH: RelationConstraints(
        source_categories=[SimulationEntityCategory.SIMULATION_RESULT],
        target_categories=[SimulationEntityCategory.SIMULATION_RESULT],
        valid_properties=["comparison_metric", "difference_score"]
    ),
    SimulationRelationType.SIMULATES_DECISION: RelationConstraints(
        source_categories=[SimulationEntityCategory.SIMULATION_SCENARIO],
        target_categories=[EntityCategory.STRIKE_ORDER],
        valid_properties=["decision_quality", "simulation_fidelity"]
    ),
}
```

### 7.3 模拟推验证证规则

```python
# ontology/simulation_validators.py

class SimulationOntologyValidator(OntologyValidator):
    """模拟推验证证器"""
    
    @staticmethod
    def validate_simulation_scenario(
        scenario: SimulationScenario
    ) -> List[str]:
        """验证模拟场景"""
        errors = []
        
        # 参数Schema验证
        if scenario.parameter_schema:
            errors.extend(
                SimulationOntologyValidator._validate_parameter_schema(
                    scenario.parameter_schema
                )
            )
        
        # 默认参数验证
        if scenario.default_parameters:
            errors.extend(
                SimulationOntologyValidator._validate_parameters(
                    scenario.default_parameters,
                    scenario.parameter_schema
                )
            )
        
        # 资源限制验证
        if scenario.resource_limits:
            errors.extend(
                SimulationOntologyValidator._validate_resource_limits(
                    scenario.resource_limits
                )
            )
        
        # 状态一致性验证
        if scenario.status == SimulationStatus.RUNNING:
            if not scenario.current_version_id:
                errors.append("Running scenario must have a current version")
        
        return errors
    
    @staticmethod
    def validate_simulation_version(
        version: SimulationVersion
    ) -> List[str]:
        """验证模拟版本"""
        errors = []
        
        # 版本号格式验证
        if not SimulationOntologyValidator._validate_version_number(
            version.version_number
        ):
            errors.append(f"Invalid version number format: {version.version_number}")
        
        # 参数快照验证
        if version.parameter_snapshot:
            errors.extend(
                SimulationOntologyValidator._validate_parameter_snapshot(
                    version.parameter_snapshot
                )
            )
        
        # 回滚兼容性验证
        if version.rollback_target_id and not version.rollback_compatibility:
            errors.append("Rollback target specified but compatibility is false")
        
        # 执行统计验证
        if version.success_count + version.failure_count != len(version.execution_ids):
            errors.append("Execution count mismatch with success+failure count")
        
        return errors
    
    @staticmethod
    def validate_simulation_execution(
        execution: SimulationExecution
    ) -> List[str]:
        """验证模拟执行"""
        errors = []
        
        # 状态机验证
        if not SimulationOntologyValidator._validate_state_transition(
            execution.status
        ):
            errors.append(f"Invalid state transition for {execution.status}")
        
        # 时间一致性验证
        if execution.end_time and execution.start_time:
            if execution.end_time < execution.start_time:
                errors.append("End time cannot be before start time")
            
            if execution.duration_seconds:
                expected_duration = (
                    execution.end_time - execution.start_time
                ).total_seconds()
                if abs(execution.duration_seconds - expected_duration) > 1:
                    errors.append("Duration does not match start/end times")
        
        # 进度验证
        if execution.progress_percentage < 0 or execution.progress_percentage > 100:
            errors.append("Progress percentage must be between 0 and 100")
        
        # 资源限制检查
        if execution.resource_limits_violated:
            if not execution.resource_usage:
                errors.append("Resource usage must be recorded when limits violated")
        
        return errors
    
    @staticmethod
    def validate_simulation_result(
        result: SimulationResult
    ) -> List[str]:
        """验证模拟结果"""
        errors = []
        
        # 结果完整性验证
        if not result.raw_data and not result.processed_data:
            errors.append("Result must have either raw or processed data")
        
        # 指标验证
        metrics = [
            result.performance_metrics,
            result.business_metrics,
            result.quality_metrics
        ]
        
        for metric_dict in metrics:
            for key, value in metric_dict.items():
                if not isinstance(value, (int, float)):
                    errors.append(f"Metric {key} must be a number, got {type(value)}")
        
        # 存储大小验证
        if result.storage_size_bytes < 0:
            errors.append("Storage size cannot be negative")
        
        # 压缩比验证
        if result.compression_ratio <= 0:
            errors.append("Compression ratio must be positive")
        
        # 版本格式验证
        if not SimulationOntologyValidator._validate_version_number(
            result.result_version
        ):
            errors.append(f"Invalid result version format: {result.result_version}")
        
        return errors
    
    @staticmethod
    def validate_what_if_analysis(
        analysis: WhatIfAnalysis
    ) -> List[str]:
        """验证What-if分析"""
        errors = []
        
        # 参数变化验证
        if not analysis.parameter_changes:
            errors.append("What-if analysis must have parameter changes")
        
        # 分析类型验证
        valid_analysis_types = ["sensitivity", "impact", "trend", "comprehensive"]
        if analysis.analysis_type not in valid_analysis_types:
            errors.append(f"Invalid analysis type: {analysis.analysis_type}")
        
        # 分析深度验证
        valid_depths = ["quick", "detailed", "comprehensive"]
        if analysis.analysis_depth not in valid_depths:
            errors.append(f"Invalid analysis depth: {analysis.analysis_depth}")
        
        # 结果一致性验证
        if analysis.status == SimulationStatus.COMPLETED:
            if not analysis.result_ids:
                errors.append("Completed analysis must have result IDs")
            if not analysis.key_insights:
                errors.append("Completed analysis must have key insights")
        
        # 相关性验证
        if analysis.execution_ids and not analysis.result_ids:
            errors.append("If executions exist, corresponding results should exist")
        
        return errors
```

### 7.4 模拟推演本体管理器（简化版本）

```python
# ontology/simulation_ontology_manager.py

class SimulationOntologyManager(OntologyManager):
    """模拟推演本体管理器"""
    
    async def create_simulation_scenario(
        self,
        scenario_data: Dict[str, Any],
        created_by: str
    ) -> Tuple[str, str]:
        """
        创建模拟场景
        返回: (scenario_id, scenario_version_id)
        """
        # 创建场景实体
        scenario = SimulationScenario(
            **scenario_data,
            created_by=created_by,
            last_modified_by=created_by
        )
        
        # 验证场景
        errors = SimulationOntologyValidator.validate_simulation_scenario(scenario)
        if errors:
            raise ValidationError(f"Scenario validation failed: {errors}")
        
        # 注册场景
        scenario_id = await self.register_entity(scenario)
        
        # 创建初始版本
        version = SimulationVersion(
            scenario_id=scenario_id,
            version_number="v1.0.0",
            change_summary="Initial version",
            change_author=created_by,
            parameter_snapshot=scenario.default_parameters,
            configuration_snapshot=scenario.model_dump(),
            is_current=True,
            is_stable=True
        )
        
        # 注册版本
        version_id = await self.register_entity(version)
        
        # 建立场景-版本关系
        await self.register_relation(
            source_id=scenario_id,
            target_id=version_id,
            relation_type=SimulationRelationType.HAS_VERSION,
            properties={"is_current": True}
        )
        
        return scenario_id, version_id
    
    async def execute_simulation(
        self,
        scenario_id: str,
        version_id: str,
        parameters: Dict[str, Any],
        execution_config: Dict[str, Any],
        executed_by: str
    ) -> Tuple[str, str]:
        """
        执行模拟
        返回: (execution_id, result_id)
        """
        # 创建执行实体
        execution = SimulationExecution(
            scenario_id=scenario_id,
            version_id=version_id,
            parameters=parameters,
            configuration=execution_config,
            status=SimulationStatus.READY
        )
        
        # 注册执行
        execution_id = await self.register_entity(execution)
        
        # 创建结果占位符
        result = SimulationResult(
            execution_id=execution_id,
            scenario_id=scenario_id,
            version_id=version_id
        )
        
        result_id = await self.register_entity(result)
        
        # 建立执行-结果关系
        await self.register_relation(
            source_id=execution_id,
            target_id=result_id,
            relation_type=SimulationRelationType.PRODUCED_RESULT
        )
        
        return execution_id, result_id
```

---

## 8. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-11 | 初始版本 |
| 1.1.0 | 2026-04-12 | 新增模拟推演本体支持，包括场景、版本、执行、结果等实体定义，以及与决策推荐的深度集成 |

---

**相关文档**:
- [Graphiti 客户端模块设计](../graphiti_client/DESIGN.md)
- [Decision Recommendation 决策推荐模块设计](../decision_recommendation/DESIGN.md)
- [Visualization 可视化模块设计](../visualization/DESIGN.md)
- [安全策略文档](../../security/SECURITY.md)
