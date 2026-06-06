# Ontology 本体管理层设计文档

> **优先级**: P1 | **相关 ADR**: ADR-036, ADR-024

## 1. 模块概述

### 1.1 模块定位

`ontology` 是领域的领域本体模型，定义领域中的实体类型、关系类型和约束规则。是 Graphiti 图谱的数据模式基础。

### 1.2 核心职责

| 职责 | 描述 |
|------|------|
| 本体模型定义 | 定义领域实体和关系的类型系统 |
| 模式管理 | 管理本体的版本和变更 |
| 验证规则 | 实体和关系的验证逻辑 |
| Graphiti 集成 | 与 Graphiti 的无缝集成 |

---

## 2. 本体模型设计

### 2.1 实体类型层次

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Domain Ontology                                │
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
│            │  (情报)    │ │ (决策指令)  │                                 │
│            └─────────────┘ └─────────────┘                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心实体定义

```python
# ontology/domain_ontology.py
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
    """决策指令实体"""
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
        """验证决策指令"""
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
├── domain_ontology.py    # 核心实体定义
├── relations.py               # 关系类型定义
├── validators.py              # 验证规则
├── ontology_manager.py        # 本体管理器
├── versions/                  # 版本管理
│   └── v1.0.0.py
└── schemas/                   # JSON Schema
    └── domain.json
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

## 8. Markdown 本体双向同步

> **对应需求**: FR-200 (本体设计器 - Markdown编辑)

本体定义支持 Markdown 格式编辑，用户可以直接编写 Markdown 文档来描述实体类型和关系，系统自动解析为结构化本体；反之，结构化本体也可导出为 Markdown 文档供人工审阅。

### 8.1 Markdown → 本体结构 (解析)

**Markdown 格式规范**:

```markdown
# 本体: 战争分析

## 实体类型

### Target (目标)
- **属性**:
  - name: string (必填)
  - type: enum[地面/海上/空中/地下/网络] (必填)
  - coordinates: [lat: float, lon: float]
  - threat_level: enum[低/中/高/极高]
  - description: text
- **约束**: name 不可为空, coordinates 格式校验
- **同义词**: 打击目标, 攻击对象

### Unit (部队)
- **属性**:
  - name: string (必填)
  - unit_type: enum[陆军/海军/空军/火箭军/网络部队]
  - strength: int (>= 0)
  - status: enum[待命/机动/交战中/休整]
- **同义词**: 作战单元, 部队单位

## 关系类型

### ATTACKS (攻击)
- 源: Unit → 目标: Target
- **属性**: time: datetime, weapon_type: string
- **反转**: ATTACKED_BY

### DETECTED_AT (探测)
- 源: Sensor → 目标: Target
- **属性**: time: datetime, confidence: float
```

**解析器实现**:

```python
# odap/ontology/markdown_parser.py
import re
from dataclasses import dataclass

@dataclass
class PropertyDef:
    name: str
    type: str
    required: bool = False

class OntologyMarkdownParser:
    """将 Markdown 本体定义解析为结构化数据"""

    def parse(self, md_content: str) -> dict:
        result = {"entity_types": [], "relation_types": []}
        current_section = None

        for line in md_content.split("\n"):
            line = line.strip()

            # 实体类型: ### TypeName (中文名)
            m = re.match(r"^### (\w+) \((.+)\)$", line)
            if m:
                entity = {"name": m.group(1), "display_name": m.group(2),
                          "properties": [], "constraints": [], "synonyms": []}
                result["entity_types"].append(entity)
                current_entity = entity
                continue

            # 属性: - name: type (必填/可选)
            m = re.match(r"^- (\w+): (.+?)(?: \((必填|可选)\))?$", line)
            if m and current_entity:
                prop = PropertyDef(name=m.group(1), type=m.group(2).strip(),
                                   required=m.group(3) == "必填")
                current_entity["properties"].append(prop)
                continue

            # 同义词: - keyword1, keyword2
            m = re.match(r"^- (.+)$", line)
            if m and isinstance(current_section, dict) and "synonyms" in current_section:
                current_entity["synonyms"] = [s.strip() for s in m.group(1).split(",")]

            # 关系类型: ### RELATION_NAME (中文名)
            m = re.match(r"^- 源: (\w+) → 目标: (\w+)$", line)
            if m and current_relation:
                current_relation["source_type"] = m.group(1)
                current_relation["target_type"] = m.group(2)

        return result
```

### 8.2 本体结构 → Markdown (导出)

```python
class OntologyMarkdownExporter:
    def export(self, ontology: dict) -> str:
        lines = [f"# 本体: {ontology.get('name', '未命名')}\n"]
        lines.append("## 实体类型\n")

        for et in ontology.get("entity_types", []):
            lines.append(f"### {et['name']} ({et.get('display_name', '')})\n")
            lines.append("- **属性**:")
            for prop in et.get("properties", []):
                req = "必填" if prop.get("required") else "可选"
                lines.append(f"  - {prop['name']}: {prop['type']} ({req})")
            if et.get("synonyms"):
                lines.append(f"- **同义词**: {', '.join(et['synonyms'])}")
            lines.append("")

        lines.append("## 关系类型\n")
        for rt in ontology.get("relation_types", []):
            lines.append(f"### {rt['name']} ({rt.get('display_name', '')})\n")
            lines.append(f"- 源: {rt['source_type']} → 目标: {rt['target_type']}")
            rt_props = rt.get("properties", [])
            if rt_props:
                lines.append(f"- **属性**: {', '.join(p['name'] for p in rt_props)}")
            lines.append("")

        return "\n".join(lines)
```

### 8.3 前端双向编辑器

```typescript
const OntologyDesigner: React.FC = () => {
  const [mode, setMode] = useState<'visual' | 'markdown'>('visual')
  const [markdown, setMarkdown] = useState("")
  const [parseErrors, setParseErrors] = useState<string[]>([])

  const handleMarkdownChange = (newMd: string) => {
    setMarkdown(newMd)
    // 实时解析反馈
    try {
      const parsed = parseOntologyMarkdown(newMd)
      setParseErrors([])
      updateOntologyModel(parsed)      // 同步到可视化模型
    } catch (e) {
      setParseErrors([e.message])
    }
  }

  const handleVisualChange = (ontology: OntologyModel) => {
    const md = exportToMarkdown(ontology)
    setMarkdown(md)                    // 反向同步 Markdown
    updateOntologyModel(ontology)
  }

  return (
    <div className="ontology-designer">
      <Button.Group>
        <Button type={mode === 'visual' ? 'primary' : 'default'}
          onClick={() => setMode('visual')}>可视化编辑</Button>
        <Button type={mode === 'markdown' ? 'primary' : 'default'}
          onClick={() => setMode('markdown')}>Markdown 编辑</Button>
      </Button.Group>

      {mode === 'markdown' ? (
        <div>
          <CodeEditor value={markdown} onChange={handleMarkdownChange} language="markdown" />
          {parseErrors.map((e, i) => <Alert key={i} type="error" message={e} />)}
        </div>
      ) : (
        <VisualOntologyEditor onChange={handleVisualChange} />
      )}
    </div>
  )
}
```

---

---

## 9. Data Health 数据健康（FR-031）

Data Health 模块是 Palantir/OntoFlow 范式下"写入后验证"的执行者，与 OPA 的"写入前权限"形成严格分工。Data Health 关注的是**数据本身是否符合业务规则**，例如"装备必须有 currentLocation"、"邮箱必须符合正则"等可量化的数据质量标准。

### 9.1 5 类核心规则

| 规则 | 表达式示例 | 检查目标 |
|------|-----------|----------|
| `not_null` | `{"properties": ["name", "currentLocation"]}` | 必填字段不能为空 |
| `unique` | `{"properties": ["serialNumber"]}` | 字段值在目标类型所有实例中唯一 |
| `regex` | `{"properties": ["email"], "pattern": "^[^@]+@[^@]+$"}` | 字段值匹配正则表达式 |
| `range` | `{"properties": ["score"], "min": 0, "max": 100}` | 数值字段在指定闭区间内 |
| `referential_integrity` | `{"property": "unitId", "ref_type": "Unit"}` | 外键引用指向已存在的实例 |

### 9.2 定时扫描调度（cron）

每个 `HealthRule` 携带一个 `schedule` 字段（标准 5 段 cron 表达式，例如 `0 */6 * * *` 表示每 6 小时一次）。后台调度器基于 `croniter` 库计算下次执行时间，扫描完成后通过 `NotificationDispatcher` 推送失败告警。

### 9.3 多通道通知

支持三种通知通道，按规则配置可多选：
- **webhook**：HTTP POST 推送 JSON 报告
- **email**：SMTP 发送 HTML 邮件（含失败详情 + 链接）
- **im**：企业 IM（飞书/钉钉/Slack）卡片消息

通知发送使用 `asyncio.create_task` 异步执行，避免阻塞主扫描流程；失败时降级为日志告警，不影响扫描结果。

### 9.4 模型与存储

```
odap/biz/core/ontology/health/
├── api/                  # FastAPI 路由（35+ 端点）
├── models/
│   ├── rule.py           # HealthRule（target_type_id, rule_type, severity, schedule）
│   └── report.py         # HealthReport（instance_id, status: pass/warn/fail）
├── interfaces/           # ABC: HealthRuleRepository, HealthScanner
├── impl/
│   ├── health_rule_repository_impl.py
│   ├── health_scanner_impl.py        # 5 种规则实现
│   └── notification_dispatcher.py    # 3 通道分发
├── services/             # HealthService 编排层（返回 Dict[str, Any]）
└── storage/
    └── sqlite_health_storage.py      # health_rules / health_reports 表
```

### 9.5 与 OPA 的职责边界

| 维度 | OPA | Data Health |
|------|-----|-------------|
| 执行时机 | 写入**前**（preconditions） | 写入**后**（post-write scan） |
| 关注点 | "用户 X 能否写入数据" | "数据本身是否符合业务规则" |
| 失败处理 | 拒绝写入，返回 403 | 写入成功，扫描产出 fail 报告 + 通知 |
| 责任主体 | 权限/安全 | 数据质量/业务正确性 |

---

## 10. Branch & Merge 本体分支（FR-032）

本体分支借鉴 Git 的分支与合并思想，支持多人/多团队并行修改同一本体，通过 3-way merge 自动合并不冲突字段，冲突字段则交给人工解决。

### 10.1 3-way merge 基于 RFC 6902

每个分支保存 `base_snapshot`（fork 时的版本）+ `ours_snapshot`（源分支当前 head）+ `theirs_snapshot`（目标分支当前 head）三份 JSON。合并引擎使用 RFC 6902 JSON Patch 计算差异，对每个 JSON Pointer 路径独立判断：

- 仅 base/theirs 变化 → 取 theirs
- 仅 base/ours 变化 → 取 ours
- ours 和 theirs 都未变 → 保持 base
- ours 和 theirs **冲突**（同一路径不同值） → 标记为 Conflict，阻塞合并

### 10.2 Conflict 检测 / 解决流程

```
1. POST /api/ontology/merge-requests/{mr_id}/detect-conflicts
   → 返回 conflicts 列表 [{path, base_value, ours_value, theirs_value}]

2. 用户逐条解决：
   POST /api/ontology/merge-requests/{mr_id}/resolve
   body: { conflict_id, resolution: "theirs|ours|manual", resolved_value, resolved_by }

3. 全部解决后执行合并：
   POST /api/ontology/merge-requests/{mr_id}/execute
   → 自动生成新版本号（基于目标分支 head），写入版本管理
```

### 10.3 分支保护机制

`Branch.protected: bool` 字段控制分支是否可被直接 push 或 force-merge。受保护的分支（如 `main`）必须通过 PR/MR 流程才能修改，且至少 1 名 reviewer 批准。

### 10.4 模型与存储

```
odap/biz/core/ontology/branch/
├── api/                       # FastAPI 路由
├── models/
│   ├── branch.py              # Branch（name, ontology_id, base_version_id, head_version_id）
│   ├── merge_request.py       # MergeRequest（source/target, status: open/approved/merged/conflict）
│   └── conflict.py            # Conflict（path, base/ours/theirs value, resolution）
├── interfaces/                # ABC: BranchRepository, MergeEngine
├── impl/
│   ├── branch_repository_impl.py
│   └── merge_engine.py        # ThreeWayMergeEngine (RFC 6902)
├── services/                  # BranchService 编排
└── storage/
    └── sqlite_branch_storage.py   # branches / merge_requests / conflicts 三表
```

### 10.5 与 OntoFlow Goal 的联动

每个 MergeRequest 可关联一个 `goal_id`（来自 FR-037），将"本体变更"与"业务目标"绑定。当 ChangeProposal 审批通过后，自动化引擎会创建对应的分支并发起 MR，业务目标与本体演化形成闭环。

---

## 11. Object Type Inheritance 继承 + Mixin（FR-033）

Object Type 继承模拟 OOP 中"类继承 + 多接口实现"的能力，允许定义一个 ObjectType 继承父类属性，并可叠加多个 Mixin（横切关注点）。继承解析是 OntoFlow 的核心能力之一，关系到 Health 规则、Computed Property、View 脱敏等下游能力是否能在继承层级上正确工作。

### 11.1 DFS 循环检测，深度上限 5

InheritanceValidator 使用**迭代 DFS**（避免栈溢出）检测循环继承（如 A→B→A），同时计算每个 ObjectType 的继承深度，超过 5 层则拒绝添加。深度上限的选择基于"业务可读性"权衡：太深会破坏人类对类型层次的可理解性。

### 11.2 父类与 Mixin 共同参与属性解析

InheritanceResolver 给定 ObjectType ID，返回完整属性链：
1. 沿继承链向上收集父类属性（去重 + 后定义优先）
2. 应用所有 Mixin 提供的属性（同名时 Mixin 属性覆盖父类）
3. 子类自身属性优先级最高

```
[Vehicle] (parent)        [AuditableMixin]
  | props: speed           | props: created_at, updated_at
  ↓                         ↓
[Truck] (child)            ↓
  | inherits: [Vehicle]    ↓
  | mixins: [Auditable] ←──┘
  | props: payload_kg
  
→ Effective properties: payload_kg, speed, created_at, updated_at
```

### 11.3 解决链示例

对于多继承（A→B、A→C、B→D、C→D）这种"菱形继承"，Resolver 使用 **C3 线性化**算法确定属性解析顺序，避免同一属性被多个祖先声明时的歧义。

### 11.4 模型与存储

```
odap/biz/core/ontology/inheritance/
├── api/                   # FastAPI 路由（12 端点）
├── models/
│   ├── inheritance.py     # InheritanceEdge（child_type_id, parent_type_id, depth）
│   └── mixin.py           # Mixin（name, properties, target_type_ids）
├── interfaces/            # ABC: InheritanceRepository
├── impl/
│   ├── inheritance_repository_impl.py
│   ├── validator.py       # InheritanceValidator (DFS + 深度 5)
│   └── resolver.py        # InheritanceResolver (C3 线性化)
├── services/              # InheritanceService
└── storage/
    └── sqlite_inheritance_storage.py   # inheritance_edges / mixins 表
```

### 11.5 与下游模块的集成

- **Health 规则**：在子类实例上跑 not_null 规则时，自动检查从父类继承的必填字段
- **Computed Property**：基于继承属性做计算，无需为每个子类重复定义表达式
- **View 脱敏**：父类上的脱敏规则自动应用到所有子类实例

---

## 12. Action Type 动作类型（FR-034）

Action Type 是本体的"一等公民"，将"可执行动作"提升为本体层级的概念。详见 [ADR-055 2026-06-06 状态修正](../07-adr/ADR-055-统一查询服务.md#2026-06-06-状态修正action-type-与-skill-分层原则) 中 ActionType（业务接口）↔ Skill（工程实现）的分层原则。

### 12.1 业务接口（Action Type）与工程实现（Skill）分离

- **ActionType** 面向业务用户/Agent，定义参数 schema、返回类型、副作用
- **Skill** 是 ActionType 的实现细节（位于 `odap/tools/` 现有技能包），可被多个 ActionType 绑定复用
- `ActionType.linked_skill_id` 字段强制非空，强制"业务逻辑只能通过 ActionType 暴露"

### 12.2 OPA 写入权限校验

`execute_action()` 流程：
```
1. 加载 ActionType
2. OPA check_permission(action_type, user_context) → bool
3. DENY → 写"denied"执行记录 + 审计 + 返回
4. ALLOW → 调用 SkillBackedExecutor → 落库 execution
```

OPA 拒绝时**仍**创建一条 DENIED 状态的执行记录，便于审计追溯"哪些用户被拒绝了什么操作"。

### 12.3 执行历史 + 审计

- 执行历史：`action_executions` 表记录 `action_type_id / parameters / result / status / audit_record_id`
- 审计日志：通过 `unified_audit.py` 写入 `event_type=action_execution`，含 `actor / action_type / result / duration_ms`

### 12.4 模型与存储

```
odap/biz/core/ontology/action/
├── api/                # FastAPI 路由（7 端点）
├── models/
│   ├── action_type.py  # ActionType（name, parameters, linked_skill_id, opa_policy_ref）
│   └── execution.py    # ActionExecution（status: success/failed/denied）
├── interfaces/         # ABC: ActionTypeRepository, ActionExecutor
├── impl/
│   ├── action_type_repository_impl.py
│   └── skill_executor.py    # SkillBackedExecutor (ActionType → Skill 委托)
├── services/           # ActionService（OPA write-time check + audit）
└── storage/
    └── sqlite_action_storage.py   # action_types / action_executions 表
```

### 12.5 ODAP 实际例子

- `assign-mission` ActionType 绑定到 `validate-mission` + `persist-mission-log` 两个 Skill
- `decommission-equipment` ActionType 绑定到 `validate-state` + `update-status` 两个 Skill

具体 schema 与执行流程参考 ADR-055 状态修正章节。

---

## 13. Computed Property + Materialized View（FR-035）

Computed Property 让本体具备"派生属性"能力，例如根据 `birthdate` 自动计算 `age`、根据 `price * quantity` 计算 `totalAmount`。物化视图则将计算结果持久化，避免每次查询时重复计算。

### 13.1 安全表达式求值（AST 白名单 + 受限 builtins）

`SafeExpressionEvaluator` 不直接 `eval()` 用户表达式，而是先解析为 AST，仅允许以下节点类型：
- 字面量（数字、字符串、布尔、null）
- 二元/一元算术运算（`+ - * / %`）
- 比较运算（`== != < > <= >=`）
- 三元表达式（`a if cond else b`）
- 受限的内置函数（`abs / min / max / round / len / str / int / float / bool / ifnull`）

任何 `import`、属性访问（`obj.attr`）或下标访问（`arr[0]`）都被拒绝，确保表达式无法逃逸沙箱。

### 13.2 依赖追踪 + 增量重算（DAG 传播）

`DependencyTracker` 在创建 ComputedProperty 时通过 AST 遍历提取所有引用的"源属性名"，构建全局依赖图（DAG）。当某个源属性值变化时：
1. 反向查找所有"依赖此属性"的 ComputedProperty
2. 重新评估这些 Property
3. 若 ComputedProperty 也是其他 Property 的依赖，递归传播
4. 物化视图根据 `materialization` 字段（none/full/incremental）选择更新策略

### 13.3 物化视图 vs 实时计算的权衡

| 策略 | 适用场景 | 优缺点 |
|------|----------|--------|
| **实时计算** | 低频访问、表达式简单、源数据频繁变化 | 始终最新；查询慢；占用 CPU |
| **物化（full）** | 高频访问、源数据稳定 | 查询快；占用存储；需定时刷新 |
| **物化（incremental）** | 高频访问、源数据增量变化 | 查询快 + 存储省；DAG 传播复杂度高 |

`ComputedProperty.materialization` 字段显式选择策略。增量重算时采用批量提交（每 1000 条一批），单次任务超时自动降级为全量重算（避免"雪崩"）。

### 13.4 模型与存储

```
odap/biz/core/ontology/computed/
├── api/                  # FastAPI 路由
├── models/
│   ├── property.py       # ComputedProperty（name, expression, dependencies, materialization）
│   └── job.py            # MaterializationJob（status: pending/running/done/failed）
├── interfaces/           # ABC: ComputedRepository, ExpressionEvaluator
├── impl/
│   ├── computed_repository_impl.py
│   ├── evaluator.py      # SafeExpressionEvaluator (AST 白名单)
│   ├── dependency_tracker.py   # DAG 构建 + 反向传播
│   └── incremental.py    # IncrementalComputer
├── services/             # ComputedService
└── storage/
    └── sqlite_computed_storage.py  # computed_properties / materialization_jobs / materialized_values
```

### 13.5 与 View 的集成

Materialized View 的本质是一种特殊的 ComputedProperty：`materialization=full` + 持久化到 `materialized_values` 表。View 解析时直接查询物化值，避免运行时计算。详见 §14。

---

## 14. Object View 对象视图（FR-036）

Object View 为不同角色（Commander/Intelligence/Operations）提供"看到的就是该看的"的数据视图，集成 OPA 读权限校验 + 字段脱敏 + 过滤 + 排序 + 行数限制。

### 14.1 基于角色的字段投影

每个 `ObjectView` 绑定一个 `role`，定义该角色可见的字段白名单（`projected_properties`）。查询时仅返回白名单内的字段，其他字段从结果中剔除。这与"列级权限"等价。

### 14.2 脱敏规则（REMOVE / 邮箱掩码 / 身份证掩码 / 自定义模式）

`redaction_rules` 是字段→脱敏策略的映射，支持 4 种内置策略：

| 策略 | 示例 | 适用 |
|------|------|------|
| `REMOVE` | 字段从结果中删除 | 高度敏感（薪资、医疗记录） |
| `EMAIL_MASK` | `alice@example.com` → `a***@example.com` | 邮箱 |
| `ID_CARD_MASK` | `110101199003078888` → `1101********8888` | 身份证 |
| `CUSTOM_REGEX` | `{"pattern": "\\d{4}$", "replace": "****"}` | 任意自定义模式 |

### 14.3 过滤 + 排序 + 行数限制

- `filters`：JSON 表达式树（`{property, op, value}` 三元组）
- `sort_order`：字段名 + 方向（asc/desc）
- `row_limit`：硬性行数限制（防止单次查询返回过多数据）

### 14.4 View 解析流程

```
GET /api/ontology/views/{view_id}/resolve?instance_id=X&user_id=Y
→ ViewResolver:
  1. 加载 View (含 projected_properties / redaction_rules / filters)
  2. OPA 二次校验 (用户 Y 是否有权读取此 View)
  3. 从数据源加载实例
  4. 应用 filters → sort_order → row_limit
  5. 应用 redaction_rules
  6. 投影 projected_properties
  7. 写 view_resolution_cache (Redis TTL 5min)
  8. 返回最终可见属性
```

### 14.5 模型与存储

```
odap/biz/core/ontology/view/
├── api/                  # FastAPI 路由
├── models/
│   ├── view.py           # ObjectView（base_type_id, role, projected_properties, filters, row_limit）
│   └── permission.py     # ViewPermission（view_id, role, can_export, can_share, redaction_rules）
├── interfaces/           # ABC: ViewRepository, ViewQueryEngine
├── impl/
│   ├── view_repository_impl.py
│   └── view_query_engine_impl.py   # OPA 集成 + 脱敏 + 投影
├── services/             # ViewService
└── storage/
    └── sqlite_view_storage.py  # object_views / view_permissions 表
```

### 14.6 与其他模块的集成

- **Inheritance**：父类上的 View 脱敏规则自动应用到所有子类实例
- **Computed Property**：View 解析时直接读取 materialized_values，不重新计算
- **OPA**：View 是"读时权限"的最后一道闸门（FR-007 + FR-008 写时权限的补充）

---

## 15. OntoFlow Goal 目标驱动（FR-037）

OntoFlow 范式的核心是"业务目标驱动本体演化"。Goal 不仅是"待办事项"，而是连接"业务意图"与"本体变更"的第一类实体。详见 [spec §FR-037](../../specs/001-odap-platform/spec.md#fr-037-ontoflow-goal-目标驱动演化)。

### 15.1 Goal 状态机

```
proposed ──→ approved ──→ in-progress ──→ achieved
   │            │              │
   ↓            ↓              ↓
rejected    (rejected)     abandoned
```

- `proposed → approved | rejected`：评审阶段
- `approved → in-progress`：进入实施阶段（需至少 1 个 ChangeProposal）
- `in-progress → achieved | abandoned`：终态

非法转换（如 `proposed → achieved`）被 `is_valid_goal_transition()` 拒绝，API 返回 400。

### 15.2 ChangeProposal + ImpactAnalysis 联动

每个 Goal 可关联多个 `ChangeProposal`，每个 Proposal 携带 RFC 6902 JSON Patch 描述的具体变更。创建 Proposal 时自动运行 `ImpactAnalyzer`：

- 静态分析 JSON Patch 的 path 字段，识别受影响的 ObjectType / ActionType
- 估算 `affected_instances_count`（基于 type_id 扫描）
- 计算 `breaking_changes`（如删除属性、修改必填约束）
- 输出 `estimated_migration_cost`（low/medium/high）与 `risk_level`（low/medium/high/critical）

Proposal 状态机：`draft → submitted → under-review → approved/rejected → implemented`。

### 15.3 多轮 LLM Rationale 生成

`RationaleGenerator` 调用 LLM 为 Goal 生成 `business_rationale`：
1. 第一轮：基于 `title + business_objective` 生成初版 rationale
2. 第二轮：LLM 提出澄清问题（"目标受众是谁？"、"时间窗口？"、"成功度量？"）
3. 第三轮：用户提供补充信息后，LLM 生成完整 rationale
4. 失败降级：LLM 不可用时，rationale 留空，Goal 仍可创建（仅警告）

### 15.4 父子 Goal lineage

`Goal.parent_goal_id` 字段支持父子嵌套，构成 Goal Lineage 树：
- 父 Goal 可拆解为多个子 Goal（"提升装备完好率" 拆解为 "3 个月内完成 X 装备大修" + "采购 Y 备件"）
- 子 Goal 全部 `achieved` 时，父 Goal 可标记 `achieved`
- `get_goal_lineage(goal_id)` 返回完整 lineage（祖先链 + 子 + 关联 Proposal）

### 15.5 模型与存储

```
odap/biz/core/ontology/goal/
├── api/                  # FastAPI 路由（11 端点）
├── models/
│   ├── goal.py           # Goal（title, business_objective, status, parent_goal_id, rationale）
│   ├── proposal.py       # ChangeProposal（goal_id, changes, impact_analysis_id, status）
│   └── impact.py         # ImpactAnalysis（affected_types, breaking_changes, risk_level）
├── interfaces/           # ABC: GoalRepository, ImpactAnalyzer
├── impl/
│   ├── goal_repository_impl.py
│   ├── impact_analyzer_impl.py    # 静态分析 JSON Patch path
│   └── rationale_generator.py     # LLM 多轮追问
├── services/             # GoalService
└── storage/
    └── sqlite_goal_storage.py   # goals / change_proposals / impact_analyses 三表
```

### 15.6 与 Branch & Merge 的闭环

Goal → ChangeProposal 审批通过后，自动化引擎（未来实现）会：
1. 创建一个新 Branch（`feature/goal-{goal_id}`）
2. 应用 ChangeProposal 的 JSON Patch 到分支
3. 发起 MergeRequest 回到主分支
4. 合并后 Goal 状态自动推进为 `achieved`

此闭环在 Phase 11 M4 中实现，Phase 12 持续完善自动化部分。

---

## 16. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-11 | 初始版本 |
| 1.1.0 | 2026-04-12 | 新增模拟推演本体支持，包括场景、版本、执行、结果等实体定义，以及与决策推荐的深度集成 |
| 1.2.0 | 2026-05-07 | 新增 §8 Markdown 本体双向同步（解析器+导出器+前端双向编辑器），交叉引用全链路文档 |
| 2.0.0 | 2026-06-06 | Phase 11 Palantir/OntoFlow 增强：新增 §9 Data Health（FR-031）、§10 Branch & Merge（FR-032）、§11 Inheritance + Mixin（FR-033）、§12 Action Type（FR-034）、§13 Computed Property（FR-035）、§14 Object View（FR-036）、§15 OntoFlow Goal（FR-037）；交叉引用 ADR-055 状态修正章节 |

---

**相关文档**:
- [全链路架构设计](../../02-architecture/ARCHITECTURE_FULL_CHAIN.md) — Phase 2 本体构建架构
- [全链路深入实现设计 v2.0](../../02-architecture/ARCHITECTURE_FULL_CHAIN_DEEP.md) — Phase 2 完整代码实现
- [Graphiti 客户端模块设计](../graphiti_client/DESIGN.md)
- [Decision Recommendation 决策推荐模块设计](../decision_recommendation/DESIGN.md)
- [Visualization 可视化模块设计](../visualization/DESIGN.md)
- [本体管理引擎模块设计](../ontology_management_engine/DESIGN.md)
- [安全策略文档](../../05-security/SECURITY.md)
