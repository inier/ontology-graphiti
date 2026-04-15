# Skills 领域工具层设计文档

> **优先级**: P0 | **相关 ADR**: ADR-004, ADR-014

## 1. 模块概述

### 1.1 模块定位

`skills` 是领域领域特定工具集，通过 OpenHarness 原生 Tool 接口接入。分为四大类别：情报收集、作战执行、分析推理、可视化展示。

### 1.2 技能分类

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Skills 领域工具层                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐           │
│  │   Intelligence  │  │   Operations    │  │    Analysis     │           │
│  │   (情报)        │  │   (作战)        │  │    (分析)       │           │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤           │
│  │ radar_search    │  │ attack_target   │  │ threat_assess   │           │
│  │ drone_surveil   │  │ command_unit    │  │ pattern_match   │           │
│  │ satellite_imag  │  │ route_plan      │  │ anomaly_detect  │           │
│  │ signal_intercept│  │ weapon_select   │  │ trend_analysis  │           │
│  │ intel_collect   │  │ bda_assess     │  │ damage_estimate │           │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘           │
│                                                                              │
│  ┌─────────────────┐                                                       │
│  │ Visualization   │                                                       │
│  │ (可视化)        │                                                       │
│  ├─────────────────┤                                                       │
│  │ domain_map │                                                       │
│  │ timeline_gen    │                                                       │
│  │ graph_viz       │                                                       │
│  │ chart_render    │                                                       │
│  └─────────────────┘                                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 技能接口设计

### 2.1 基础接口

```python
# skills/base.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from abc import ABC, abstractmethod

class SkillInput(BaseModel):
    """所有 Skill 输入的基类"""
    request_id: str = Field(description="请求追踪ID")
    timestamp: datetime = Field(default_factory=datetime.now)

class SkillOutput(BaseModel):
    """所有 Skill 输出的基类"""
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float
    skill_name: str

class BaseSkill(ABC):
    """Skill 基类"""

    name: str = ""
    description: str = ""
    category: str = ""
    danger_level: str = "low"
    requires_opa_check: bool = False

    @abstractmethod
    async def execute(self, input_data: SkillInput) -> SkillOutput:
        """执行技能"""
        pass

    def validate_input(self, input_data: SkillInput) -> bool:
        """验证输入"""
        return True
```

### 2.2 情报类技能

```python
# skills/intelligence/radar_search.py
class RadarSearchInput(SkillInput):
    """雷达搜索输入"""
    region: str = Field(description="搜索区域")
    scan_depth: str = Field(default="normal", description="扫描深度")
    filters: Optional[Dict[str, Any]] = None

class RadarSearchOutput(SkillOutput):
    """雷达搜索输出"""
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "detected_targets": [],
        "scan_duration_seconds": 0,
        "confidence": 0.0
    })

class RadarSearchSkill(BaseSkill):
    """雷达搜索技能"""
    name = "radar_search"
    description = "搜索指定区域的雷达信号"
    category = "intelligence"
    danger_level = "low"
    requires_opa_check = False

    async def execute(self, input_data: RadarSearchInput) -> RadarSearchOutput:
        """执行雷达搜索"""
        start = datetime.now()

        # 调用雷达模拟
        targets = await self._scan_region(
            input_data.region,
            input_data.scan_depth
        )

        return RadarSearchOutput(
            success=True,
            data={
                "detected_targets": targets,
                "scan_duration_seconds": (datetime.now() - start).total_seconds(),
                "confidence": 0.92
            },
            skill_name=self.name,
            execution_time_ms=(datetime.now() - start).total_seconds() * 1000
        )
```

```python
# skills/intelligence/drone_surveillance.py
class DroneSurveillanceInput(SkillInput):
    """无人机侦察输入"""
    target_location: Dict[str, float] = Field(description="目标坐标")
    altitude: float = Field(default=500, description="飞行高度(米)")
    duration: int = Field(default=30, description="侦察时长(秒)")
    sensor_types: list[str] = Field(
        default=["visual", "infrared"],
        description="传感器类型"
    )

class DroneSurveillanceOutput(SkillOutput):
    """无人机侦察输出"""
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "imagery": [],
        "detections": [],
        "video_clips": []
    })
```

```python
# skills/intelligence/threat_assessment.py
class ThreatAssessmentInput(SkillInput):
    """威胁评估输入"""
    target_ids: list[str] = Field(description="目标ID列表")
    assessment_type: str = Field(
        default="comprehensive",
        description="评估类型"
    )
    include_recommendations: bool = Field(default=True)

class ThreatAssessmentOutput(SkillOutput):
    """威胁评估输出"""
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "assessments": [],
        "priority_order": [],
        "recommendations": []
    })
```

### 2.3 作战类技能

```python
# skills/operations/attack_target.py
class AttackTargetInput(SkillInput):
    """打击目标输入"""
    target_id: str = Field(description="目标ID")
    weapon_type: str = Field(description="武器类型")
    commander_id: str = Field(description="指挥官ID")
    priority: int = Field(default=1, description="优先级")
    justification: Optional[str] = None

class AttackTargetOutput(SkillOutput):
    """打击目标输出"""
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "order_id": None,
        "status": "pending",
        "opa_check_passed": False,
        "requires_confirmation": False
    })

class AttackTargetSkill(BaseSkill):
    """打击目标技能"""
    name = "attack_target"
    description = "向指定目标发起打击"
    category = "operations"
    danger_level = "critical"
    requires_opa_check = True

    async def execute(self, input_data: AttackTargetInput) -> AttackTargetOutput:
        """执行打击（需 OPA 批准）"""
        start = datetime.now()

        # OPA 策略检查
        opa_result = await self.opa_manager.check_attack(
            commander_id=input_data.commander_id,
            target=await self._get_target(input_data.target_id),
            weapon_type=input_data.weapon_type,
            context={}
        )

        if not opa_result.allowed:
            return AttackTargetOutput(
                success=False,
                error=f"OPA denied: {opa_result.reason}",
                skill_name=self.name,
                execution_time_ms=(datetime.now() - start).total_seconds() * 1000
            )

        # 创建决策指令
        order = await self._create_strike_order(input_data)

        return AttackTargetOutput(
            success=True,
            data={
                "order_id": order["id"],
                "status": "pending",
                "opa_check_passed": True,
                "requires_confirmation": order.get("requires_confirmation", False)
            },
            skill_name=self.name,
            execution_time_ms=(datetime.now() - start).total_seconds() * 1000
        )
```

```python
# skills/operations/command_unit.py
class CommandUnitInput(SkillInput):
    """指挥单元输入"""
    unit_id: str
    command_type: str  # move/attack/defend/halt
    parameters: Dict[str, Any] = Field(default_factory=dict)

class CommandUnitOutput(SkillOutput):
    """指挥单元输出"""
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "command_id": None,
        "status": "pending"
    })

class CommandUnitSkill(BaseSkill):
    """指挥单元技能"""
    name = "command_unit"
    description = "向作战单元下达命令"
    category = "operations"
    danger_level = "high"
    requires_opa_check = True
```

```python
# skills/operations/weapon_selection.py
class WeaponSelectionInput(SkillInput):
    """武器选择输入"""
    target_id: str
    target_type: str
    distance: float
    terrain: str = "flat"
    constraints: Optional[Dict[str, Any]] = None

class WeaponSelectionOutput(SkillOutput):
    """武器选择输出"""
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "recommended_weapons": [],
        "rationale": ""
    })

class WeaponSelectionSkill(BaseSkill):
    """武器选择技能"""
    name = "weapon_selection"
    description = "为打击目标选择最优武器"
    category = "operations"
    danger_level = "medium"
```

### 2.4 分析类技能

```python
# skills/analysis/pattern_match.py
class PatternMatchInput(SkillInput):
    """模式匹配输入"""
    pattern_type: str  # movement/attack/communication
    region: str
    time_window_hours: int = 24

class PatternMatchOutput(SkillOutput):
    """模式匹配输出"""
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "matches": [],
        "confidence": 0.0
    })

class PatternMatchSkill(BaseSkill):
    """模式匹配技能"""
    name = "pattern_match"
    description = "识别领域行为模式"
    category = "analysis"
```

```python
# skills/analysis/anomaly_detection.py
class AnomalyDetectionInput(SkillInput):
    """异常检测输入"""
    entity_ids: list[str]
    detection_threshold: float = 0.8

class AnomalyDetectionOutput(SkillOutput):
    """异常检测输出"""
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "anomalies": [],
        "alert_level": "normal"
    })

class AnomalyDetectionSkill(BaseSkill):
    """异常检测技能"""
    name = "anomaly_detection"
    description = "检测领域异常行为"
    category = "analysis"
```

### 2.5 可视化类技能

```python
# skills/visualization/domain_map.py
class DomainMapInput(SkillInput):
    """领域地图输入"""
    region: str
    show_targets: bool = True
    show_units: bool = True
    show_threat_zones: bool = False
    time_range: Optional[Dict[str, str]] = None

class DomainMapOutput(SkillOutput):
    """领域地图输出"""
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "map_url": None,
        "legend": {}
    })

class DomainMapSkill(BaseSkill):
    """领域地图技能"""
    name = "domain_map"
    description = "生成领域态势地图"
    category = "visualization"
```

---

## 3. 技能注册机制

```python
# skills/registry.py
from dataclasses import dataclass
from typing import Type

@dataclass
class SkillMetadata:
    """技能元数据"""
    name: str
    description: str
    category: str
    input_model: Type
    output_model: Type
    requires_opa_check: bool = False
    danger_level: str = "low"

SKILL_REGISTRY: Dict[str, SkillMetadata] = {}

def register_skill(
    name: str,
    description: str,
    category: str,
    input_model: Type,
    output_model: Type,
    requires_opa_check: bool = False,
    danger_level: str = "low"
):
    """装饰器：自动注册 Skill"""
    def decorator(cls):
        SKILL_REGISTRY[name] = SkillMetadata(
            name=name,
            description=description,
            category=category,
            input_model=input_model,
            output_model=output_model,
            requires_opa_check=requires_opa_check,
            danger_level=danger_level,
        )
        return cls
    return decorator

# 使用示例
@register_skill(
    name="attack_target",
    description="向指定目标发起打击",
    category="operations",
    input_model=AttackTargetInput,
    output_model=AttackTargetOutput,
    requires_opa_check=True,
    danger_level="critical"
)
class AttackTargetSkill(BaseSkill):
    ...
```

---

## 4. 目录结构

```
skills/
├── __init__.py
├── base.py                      # 基础接口
├── registry.py                  # 注册机制
│
├── intelligence/               # 情报类技能
│   ├── __init__.py
│   ├── radar_search.py
│   ├── drone_surveillance.py
│   ├── satellite_imagery.py
│   ├── signal_intercept.py
│   ├── intel_collect.py
│   └── threat_assessment.py
│
├── operations/                 # 作战类技能
│   ├── __init__.py
│   ├── attack_target.py
│   ├── command_unit.py
│   ├── route_planning.py
│   ├── weapon_selection.py
│   └── bda_assessment.py
│
├── analysis/                  # 分析类技能
│   ├── __init__.py
│   ├── pattern_match.py
│   ├── anomaly_detection.py
│   ├── trend_analysis.py
│   └── damage_estimate.py
│
└── visualization/              # 可视化类技能
    ├── __init__.py
    ├── domain_map.py
    ├── timeline_gen.py
    ├── graph_viz.py
    └── chart_render.py
```

---

## 5. 技能清单

### 5.1 情报类技能

| 技能名称 | 描述 | 危险等级 | OPA 检查 |
|---------|------|---------|---------|
| radar_search | 雷达搜索目标 | Low | 否 |
| drone_surveillance | 无人机侦察 | Medium | 否 |
| satellite_imagery | 卫星图像获取 | Low | 否 |
| signal_intercept | 信号截获 | Medium | 否 |
| intel_collect | 综合情报收集 | Medium | 否 |
| threat_assessment | 威胁评估 | Low | 否 |

### 5.2 作战类技能

| 技能名称 | 描述 | 危险等级 | OPA 检查 |
|---------|------|---------|---------|
| attack_target | 打击目标 | Critical | 是 |
| command_unit | 指挥单元 | High | 是 |
| route_planning | 航线规划 | Medium | 否 |
| weapon_selection | 武器选择 | Medium | 否 |
| bda_assessment | 打击效果评估 | Low | 否 |

### 5.3 分析类技能

| 技能名称 | 描述 | 危险等级 | OPA 检查 |
|---------|------|---------|---------|
| pattern_match | 模式匹配 | Low | 否 |
| anomaly_detection | 异常检测 | Low | 否 |
| trend_analysis | 趋势分析 | Low | 否 |
| damage_estimate | 毁伤评估 | Low | 否 |

### 5.4 可视化类技能

| 技能名称 | 描述 | 危险等级 | OPA 检查 |
|---------|------|---------|---------|
| domain_map | 领域地图 | Low | 否 |
| timeline_gen | 时间线生成 | Low | 否 |
| graph_viz | 图谱可视化 | Low | 否 |
| chart_render | 图表渲染 | Low | 否 |

---

## 6. 技能编排与协调机制

### 6.1 技能编排器设计
```python
# skills/orchestrator.py
from typing import List, Dict, Any, AsyncGenerator
from dataclasses import dataclass
import asyncio
from enum import Enum

@dataclass
class SkillDependency:
    """技能依赖关系"""
    skill_name: str
    depends_on: List[str]  # 依赖的技能名
    timeout_seconds: int = 30
    required: bool = True  # 是否必须成功
    retry_count: int = 1

class SkillStatus(Enum):
    """技能执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class SkillOrchestrator:
    """技能编排器"""
    
    def __init__(self):
        self.skill_registry: Dict[str, Any] = {}
        self.dependency_graph: Dict[str, SkillDependency] = {}
        self.execution_history: List[Dict[str, Any]] = []
        
    async def execute_workflow(self, workflow_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行技能工作流"""
        workflow = self.define_domain_workflows().get(workflow_name)
        if not workflow:
            raise ValueError(f"工作流 {workflow_name} 未定义")
        
        # 1. 解析依赖图，拓扑排序
        execution_order = self._topological_sort(workflow)
        
        # 2. 并行执行无依赖技能
        results = {}
        for skill_group in execution_order:
            tasks = []
            for skill_name in skill_group:
                if self._can_execute(skill_name, results):
                    task = asyncio.create_task(
                        self._execute_skill(skill_name, context, results)
                    )
                    tasks.append((skill_name, task))
            
            # 等待当前组所有技能完成
            if tasks:
                completed = await asyncio.gather(*[t for _, t in tasks], return_exceptions=True)
                for (skill_name, _), result in zip(tasks, completed):
                    if isinstance(result, Exception):
                        results[skill_name] = {"status": SkillStatus.FAILED, "error": str(result)}
                    else:
                        results[skill_name] = {"status": SkillStatus.SUCCESS, "data": result}
        
        # 3. 聚合结果
        return self._aggregate_results(results)
    
    def _topological_sort(self, workflow: Dict[str, List[str]]) -> List[List[str]]:
        """拓扑排序技能依赖"""
        # 构建邻接表和入度表
        adjacency = {}
        in_degree = {}
        
        for skill, deps in workflow.items():
            adjacency[skill] = deps
            in_degree[skill] = in_degree.get(skill, 0)
            for dep in deps:
                in_degree[dep] = in_degree.get(dep, 0) + 1
        
        # Kahn算法拓扑排序
        result = []
        zero_in_degree = [skill for skill, degree in in_degree.items() if degree == 0]
        
        while zero_in_degree:
            result.append(zero_in_degree)
            next_zero = []
            
            for skill in zero_in_degree:
                for neighbor in adjacency.get(skill, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_zero.append(neighbor)
            
            zero_in_degree = next_zero
        
        return result
    
    def _can_execute(self, skill_name: str, results: Dict[str, Any]) -> bool:
        """检查技能是否可以执行"""
        if skill_name not in self.dependency_graph:
            return True
        
        deps = self.dependency_graph[skill_name].depends_on
        for dep in deps:
            if dep not in results:
                return False
            if results[dep]["status"] != SkillStatus.SUCCESS:
                if self.dependency_graph[skill_name].required:
                    return False
        return True
    
    async def _execute_skill(self, skill_name: str, context: Dict[str, Any], 
                           previous_results: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个技能"""
        skill = self.skill_registry.get(skill_name)
        if not skill:
            raise ValueError(f"技能 {skill_name} 未注册")
        
        # 合并上下文和之前的结果
        execution_context = {**context}
        for prev_skill, result in previous_results.items():
            if result["status"] == SkillStatus.SUCCESS:
                execution_context[f"_{prev_skill}_result"] = result["data"]
        
        try:
            result = await skill.execute(execution_context)
            return result
        except Exception as e:
            # 重试逻辑
            max_retries = self.dependency_graph.get(skill_name, SkillDependency(skill_name, [])).retry_count
            for attempt in range(max_retries):
                await asyncio.sleep(2 ** attempt)  # 指数退避
                try:
                    result = await skill.execute(execution_context)
                    return result
                except Exception:
                    continue
            raise
    
    def _aggregate_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """聚合技能执行结果"""
        aggregated = {
            "overall_status": SkillStatus.SUCCESS,
            "successful_skills": [],
            "failed_skills": [],
            "execution_summary": {},
            "final_output": None
        }
        
        for skill_name, result in results.items():
            if result["status"] == SkillStatus.SUCCESS:
                aggregated["successful_skills"].append(skill_name)
                aggregated["execution_summary"][skill_name] = {
                    "status": "success",
                    "data_summary": str(result["data"])[:100] if result.get("data") else None
                }
            else:
                aggregated["failed_skills"].append(skill_name)
                aggregated["execution_summary"][skill_name] = {
                    "status": "failed",
                    "error": result.get("error", "unknown")
                }
                aggregated["overall_status"] = SkillStatus.FAILED
        
        return aggregated
    
    def define_domain_workflows(self) -> Dict[str, Dict[str, List[str]]]:
        """预定义领域工作流"""
        return {
            "target_identification": {
                "satellite_imagery": [],
                "radar_search": [],
                "signal_intercept": [],
                "threat_assessment": ["satellite_imagery", "radar_search", "signal_intercept"]
            },
            "strike_planning": {
                "target_identification": [],  # 子工作流
                "weapon_selection": ["target_identification"],
                "route_planning": ["target_identification"],
                "risk_assessment": ["weapon_selection", "route_planning"]
            },
            "intelligence_cycle": {
                "intel_collect": [],
                "pattern_match": ["intel_collect"],
                "anomaly_detection": ["intel_collect"],
                "trend_analysis": ["pattern_match", "anomaly_detection"]
            }
        }
```

### 6.2 工作流执行引擎
```python
# skills/workflow_engine.py
from typing import Dict, Any, Optional
from datetime import datetime
import json

class WorkflowEngine:
    """工作流执行引擎"""
    
    def __init__(self, orchestrator: SkillOrchestrator):
        self.orchestrator = orchestrator
        self.workflow_instances: Dict[str, Dict[str, Any]] = {}
        
    async def start_workflow(self, workflow_name: str, 
                           initial_context: Dict[str, Any]) -> str:
        """启动工作流"""
        workflow_id = f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        self.workflow_instances[workflow_id] = {
            "workflow_name": workflow_name,
            "status": "running",
            "start_time": datetime.now(),
            "context": initial_context,
            "results": {},
            "current_step": 0,
            "total_steps": self._count_steps(workflow_name)
        }
        
        # 异步执行工作流
        asyncio.create_task(self._execute_workflow(workflow_id))
        
        return workflow_id
    
    async def _execute_workflow(self, workflow_id: str):
        """异步执行工作流"""
        instance = self.workflow_instances[workflow_id]
        
        try:
            result = await self.orchestrator.execute_workflow(
                instance["workflow_name"],
                instance["context"]
            )
            
            instance["results"] = result
            instance["status"] = "completed" if result["overall_status"] == SkillStatus.SUCCESS else "failed"
            instance["end_time"] = datetime.now()
            instance["duration_seconds"] = (instance["end_time"] - instance["start_time"]).total_seconds()
            
        except Exception as e:
            instance["status"] = "error"
            instance["error"] = str(e)
            instance["end_time"] = datetime.now()
    
    def _count_steps(self, workflow_name: str) -> int:
        """计算工作流步骤数"""
        workflow = self.orchestrator.define_domain_workflows().get(workflow_name, {})
        return len(workflow)
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """获取工作流状态"""
        instance = self.workflow_instances.get(workflow_id)
        if not instance:
            return None
        
        status = {
            "workflow_id": workflow_id,
            "workflow_name": instance["workflow_name"],
            "status": instance["status"],
            "progress": f"{instance['current_step']}/{instance['total_steps']}",
            "start_time": instance["start_time"].isoformat() if "start_time" in instance else None,
            "duration_seconds": instance.get("duration_seconds")
        }
        
        if "error" in instance:
            status["error"] = instance["error"]
        
        if "results" in instance:
            status["summary"] = {
                "successful_skills": len(instance["results"].get("successful_skills", [])),
                "failed_skills": len(instance["results"].get("failed_skills", []))
            }
        
        return status
```

### 6.3 技能注册与发现
```python
# skills/registry.py
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import inspect

@dataclass
class SkillMetadata:
    """技能元数据"""
    name: str
    description: str
    category: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    danger_level: str
    requires_opa_check: bool
    version: str = "1.0.0"
    tags: List[str] = None

class SkillRegistry:
    """技能注册表"""
    
    def __init__(self):
        self.skills: Dict[str, Any] = {}
        self.metadata: Dict[str, SkillMetadata] = {}
        
    def register(self, skill_class) -> None:
        """注册技能"""
        skill = skill_class()
        self.skills[skill.name] = skill
        
        # 提取元数据
        metadata = SkillMetadata(
            name=skill.name,
            description=skill.description,
            category=skill.category,
            input_schema=self._extract_schema(skill.input_model),
            output_schema=self._extract_schema(skill.output_model),
            danger_level=skill.danger_level,
            requires_opa_check=skill.requires_opa_check,
            tags=getattr(skill, 'tags', [])
        )
        
        self.metadata[skill.name] = metadata
    
    def _extract_schema(self, model_class) -> Dict[str, Any]:
        """从Pydantic模型提取JSON Schema"""
        if hasattr(model_class, 'schema'):
            return model_class.schema()
        return {}
    
    def discover_skills(self, category: Optional[str] = None) -> List[SkillMetadata]:
        """发现技能"""
        skills = list(self.metadata.values())
        
        if category:
            skills = [s for s in skills if s.category == category]
        
        return skills
    
    def get_skill(self, name: str) -> Optional[Any]:
        """获取技能实例"""
        return self.skills.get(name)
    
    def get_metadata(self, name: str) -> Optional[SkillMetadata]:
        """获取技能元数据"""
        return self.metadata.get(name)
```

### 6.4 技能编排API
```python
# skills/api.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List

router = APIRouter(prefix="/skills", tags=["skills"])

class WorkflowRequest(BaseModel):
    workflow_name: str
    context: Dict[str, Any]

class WorkflowResponse(BaseModel):
    workflow_id: str
    status: str
    estimated_completion_time: str

@router.post("/workflow/start")
async def start_workflow(request: WorkflowRequest) -> WorkflowResponse:
    """启动技能工作流"""
    try:
        from skills.orchestrator import SkillOrchestrator
        from skills.workflow_engine import WorkflowEngine
        
        orchestrator = SkillOrchestrator()
        engine = WorkflowEngine(orchestrator)
        
        workflow_id = await engine.start_workflow(
            request.workflow_name,
            request.context
        )
        
        return WorkflowResponse(
            workflow_id=workflow_id,
            status="started",
            estimated_completion_time="5分钟"  # 根据工作流复杂度动态计算
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflow/{workflow_id}")
async def get_workflow_status(workflow_id: str) -> Dict[str, Any]:
    """获取工作流状态"""
    from skills.workflow_engine import WorkflowEngine
    
    engine = WorkflowEngine(SkillOrchestrator())
    status = engine.get_workflow_status(workflow_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="工作流不存在")
    
    return status
```

## 7. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-11 | 初始版本 |
| 1.1.0 | 2026-04-12 | 新增技能编排器、工作流引擎、协调机制和API接口 |

---

**相关文档**:
- [OpenHarness 桥接模块设计](../openharness_bridge/DESIGN.md)
- [Swarm 编排模块设计](../swarm_orchestrator/DESIGN.md)
- [安全策略文档](../../security/SECURITY.md)
