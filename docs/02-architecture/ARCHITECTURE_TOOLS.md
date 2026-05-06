# 本体驱动分析决策平台 (ODAP) - L2 领域工具层
> **部分**: Python Skills
> **版本**: 4.1.0 | **日期**: 2026-05-04
> **上级文档**: [ARCHITECTURE.md](ARCHITECTURE.md)
---
## 5. Python Skills 领域工具层

### 5.1 Skills 定位

Python Skills = 领域特定工具（Skills），通过 OpenHarness 原生 Tool 接口直接接入

```
OpenHarness Tool 接口 (Pydantic)
         │
         ▼
┌─────────────────────────────┐
│   OpenHarness Tool 接口    │  ← 原生接入
│   • Skill → Tool 转换      │
│   • 参数验证                │
│   • 结果标准化               │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│           Python Skills (领域工具)           │
│                                             │
│  ┌─────────────┐  ┌─────────────────────┐   │
│  │ Intelligence│  │    Operations       │   │
│  │  Skills     │  │    Skills          │   │
│  │             │  │                    │   │
│  │ • radar_    │  │ • attack_target   │   │
│  │   search    │  │ • command_unit   │   │
│  │ • threat_   │  │ • route_         │   │
│  │   assess    │  │   planning       │   │
│  │ • domain│ │ • weapon_       │   │
│  │   analyze   │  │   selection      │   │
│  └─────────────┘  └─────────────────────┘   │
│                                             │
│  ┌─────────────┐  ┌─────────────────────┐   │
│  │ Analysis    │  │   Visualization    │   │
│  │ Skills      │  │   Skills           │   │
│  │             │  │                    │   │
│  │ • pattern_  │  │ • domain_   │   │
│  │   match     │  │   render         │   │
│  │ • anomaly_  │  │ • timeline_      │   │
│  │   detect    │  │   generate       │   │
│  │ • trend_    │  │ • graph_        │   │
│  │   analysis  │  │   visualize     │   │
│  └─────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────┘
```

### 5.2 Skills 接口定义

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class SkillInput(BaseModel):
    """所有 Skill 输入的基类"""
    request_id: str = Field(description="请求追踪ID")
    timestamp: datetime = Field(default_factory=datetime.now)

class SkillOutput(BaseModel):
    """所有 Skill 输出的基类"""
    success: bool
    data: dict = Field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float

# ============================================
# Intelligence Skills
# ============================================

class RadarSearchInput(SkillInput):
    region: str = Field(description="搜索区域，如 'B区'")
    scan_depth: str = Field(default="normal", description="扫描深度")

class RadarSearchOutput(SkillOutput):
    detected_targets: list[dict] = Field(default_factory=list)

# ============================================
# Operations Skills
# ============================================

class AttackTargetInput(SkillInput):
    target_id: str
    weapon_type: str
    commander_id: str  # 指挥官 Agent ID，用于 OPA 校验
    confirmation_required: bool = True  # 高危操作需确认

class AttackTargetOutput(SkillOutput):
    order_id: Optional[str] = None
    status: str  # pending | approved | executed | rejected
    opa_check_passed: bool = False
```

### 5.3 Skill 注册机制

```python
# skills/registry.py
from dataclasses import dataclass
from typing import Type

@dataclass
class SkillMetadata:
    name: str
    description: str
    category: str  # intelligence | operations | analysis | visualization
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]
    requires_opa_check: bool = False  # 是否需要 OPA 校验
    danger_level: str = "low"  # low | medium | high | critical

SKILL_REGISTRY: dict[str, SkillMetadata] = {}

def register_skill(
    name: str,
    description: str,
    category: str,
    input_model: Type[BaseModel],
    output_model: Type[BaseModel],
    requires_opa_check: bool = False,
    danger_level: str = "low",
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
    danger_level="critical",
)
class AttackTargetSkill:
    async def execute(self, input_data: AttackTargetInput) -> AttackTargetOutput:
        # 实现...
        pass
```

---


