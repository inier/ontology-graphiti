# 战场情报分析与打击决策系统 - 架构设计文档

**版本**: 2.0 | **日期**: 2026-04-11 | **架构师**: 软件架构师

> **设计原则**: 从零开始，基于 OpenHarness + Graphiti + Skill + OPA 四大核心组件，构建可扩展的多智能体协同系统，实现感知-理解-决策-行动（OODA）闭环。

---

## 目录

1. [愿景与目标](#1-愿景与目标)
2. [核心架构：四层组件定位](#2-核心架构四层组件定位)
3. [OpenHarness Agent 基础设施层](#3-openharness-agent-基础设施层)
4. [Graphiti 双时态知识图谱层](#4-graphiti-双时态知识图谱层)
5. [Python Skill 领域工具层](#5-python-skill-领域工具层)
6. [OPA 策略治理层](#6-opa-策略治理层)
7. [三 Agent 协同编排设计](#7-三-agent-协同编排设计)
8. [OODA 闭环实现](#8-ooda-闭环实现)
9. [数据架构](#9-数据架构)
10. [技术选型与权衡](#10-技术选型与权衡)
11. [前端界面架构](#11-前端界面架构)
12. [管理后台架构](#12-管理后台架构)
13. [本体管理层](#13-本体管理层)
14. [角色与权限管理](#14-角色与权限管理)
15. [审计日志系统](#15-审计日志系统)
16. [配置中心](#16-配置中心)
17. [架构决策记录（ADR）](#17-架构决策记录adr)
18. [演进路线图](#18-演进路线图)
19. [文档体系](#19-文档体系)

---

## 1. 愿景与目标

### 1.1 系统定位

构建一个类似 Palantir AIP 的**战场情报分析与打击决策系统**，核心能力：

- **感知（Observe）**: 多源情报采集与融合
- **理解（Orient）**: 威胁模式识别与态势评估
- **决策（Decide）**: 多方案评估与最优选择
- **行动（Act）**: 打击命令下发与执行监控

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **OpenHarness First** | 基于 OpenHarness 作为 Agent 基础设施，减少重复造轮子 |
| **Graphiti as Memory** | Graphiti 作为双时态记忆，支撑时序推理和历史回溯 |
| **Skill as Tool** | Python Skills 作为领域工具，通过桥接层接入 OpenHarness |
| **OPA for Governance** | OPA 作为策略治理，所有高危操作必须通过 OPA 校验 |
| **Fail-Safe by Default** | 默认拒绝不了解的操作，fail-close 策略 |
| **Observable Everything** | 全链路可观测：Logs + Traces + Metrics |

### 1.3 技术约束

| 维度 | 约束 |
|------|------|
| **团队规模** | 小团队（3-5人），无需微服务拆分 |
| **部署环境** | 本地开发 + Docker Compose 生产 |
| **图数据库** | Neo4j（生产）/ NetworkX（开发回退） |
| **策略引擎** | OPA（外部服务，Docker 部署） |
| **LLM API** | 支持 OpenAI / Anthropic / DeepSeek 多模型 |
| **协议标准** | MCP（Model Context Protocol） |

---

## 2. 核心架构：四层组件定位

### 2.1 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           用户交互层 (User Interface)                          │
│                    战场态势可视化 / 命令下发 / 结果展示                          │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    OpenHarness Agent 基础设施层                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ Commander Agent │  │Intelligence Agent│  │Operations Agent │             │
│  │   (决策中枢)     │◄─┤    (情报中心)   │◄─┤    (执行中心)    │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
│           │                    │                    │                      │
│           └────────────────────┼────────────────────┘                      │
│                                ▼                                            │
│                    ┌─────────────────────┐                                  │
│                    │  Swarm Coordinator  │                                  │
│                    │    (OpenHarness)    │                                  │
│                    └──────────┬──────────┘                                  │
│                               │                                              │
│         ┌─────────────────────┼─────────────────────┐                       │
│         ▼                     ▼                     ▼                       │
│  ┌─────────────┐      ┌─────────────┐       ┌─────────────┐                │
│  │Tool Registry│      │Hook System │       │Permission   │                │
│  │  (43+工具)  │      │(Pre/Post)  │       │  Checker    │                │
│  └─────────────┘      └─────────────┘       └─────────────┘                │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Python Skills  │    │   Graphiti      │    │     OPA         │
│  (领域工具层)    │    │ (双时态图谱层)   │    │  (策略治理层)    │
│                 │    │                 │    │                 │
│ • radar_search  │    │ • 实体存储       │    │ • 权限校验       │
│ • threat_assess │    │ • 时序推理      │    │ • 规则执行       │
│ • attack_target │    │ • 关系图谱       │    │ • 合规检查       │
│ • unit_command  │    │ • 历史回溯       │    │ • Fail-Close    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │    MCP Protocol         │
                    │ (外部系统集成)          │
                    │ • 战场仿真器             │
                    │ • 雷达模拟器             │
                    │ • 气象数据源             │
                    └─────────────────────────┘
```

### 2.2 四层职责定位

| 层次 | 组件 | 职责 | 核心价值 |
|------|------|------|---------|
| **L1** | OpenHarness | Agent Loop + Swarm + 工具调度 | 减少 90% Agent 基础设施代码 |
| **L2** | Graphiti | 双时态知识图谱 + 时序推理 | 支撑"当时发生了什么"的历史回溯 |
| **L3** | Python Skills | 领域特定工具（战场情报、打击决策） | 可插拔的领域能力 |
| **L4** | OPA | 策略治理 + 权限校验 | fail-close 安全边界 |

### 2.3 数据流总览

```
用户输入
    │
    ▼
┌────────────────────────────────────────────────────────────┐
│                    OpenHarness Agent Loop                    │
│  Query → LLM推理 → Tool选择 → Permission检查 → 执行 → 响应  │
└────────────────────────────┬───────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────────┐   ┌─────────────┐
│ Graphiti    │    │  Python Skills  │   │    OPA      │
│ 记忆写入     │    │  执行结果        │   │  策略校验    │
└──────┬──────┘    └────────┬────────┘   └──────┬──────┘
       │                    │                   │
       └────────────────────┴───────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   执行结果       │
                    │ (用户可见响应)   │
                    └─────────────────┘
```

---

## 3. OpenHarness Agent 基础设施层

### 3.1 为什么选择 OpenHarness

| 维度 | 自研 | OpenHarness | 结论 |
|------|------|-------------|------|
| Agent Loop | 500+ 行代码 | 内置 | 节省 500+ 行 |
| Tool 系统 | 需从零实现 | 43+ 内置工具 | 复用成熟实现 |
| Swarm 协调 | 无 | 内置 | 多 Agent 协同开箱即用 |
| Permission | 需自研 | 内置多级权限 | 安全边界现成 |
| Memory | 需对接 | 可扩展接口 | Graphiti 完美对接 |
| **总代码量** | ~5000 行 | ~300 行桥接 | **节省 90%** |

### 3.2 OpenHarness 核心子系统使用矩阵

| 子系统 | 使用方式 | 本项目集成点 |
|--------|---------|------------|
| `engine/` | Agent Loop | 接管 Query → Tool 循环 |
| `tools/` | 通用工具 | WebSearch, FileIO, Bash |
| `skills/` | 按需加载 | Markdown Skills 生态 |
| `plugins/` | 扩展点 | 自定义 Hook 插件 |
| `permissions/` | 权限检查 | OPA 桥接作为 Backend |
| `hooks/` | 生命周期 | PreTool/PostTool 事件 |
| `mcp/` | 外部集成 | 战场仿真器、雷达模拟器 |
| `memory/` | 记忆管理 | Graphiti 替换内置 Memory |
| `coordinator/` | Swarm | 三 Agent 协同编排 |

### 3.3 OpenHarness 安装与配置

```yaml
# pyproject.toml
[project]
dependencies = [
    "openharness>=0.1.6",
    "graphiti-core>=0.3.0",
    "opa-python-sdk>=0.5.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
]

# .openharness/config.yaml
permission:
  mode: default  # Default | Auto | Plan
  backend: opa   # 使用 OPA 作为权限检查后端
  opa_url: http://localhost:8181

memory:
  backend: graphiti  # 替换内置 Memory，使用 Graphiti
  graphiti_url: http://localhost:7474

model:
  provider: openai  # OpenAI | Anthropic | DeepSeek
  model: gpt-4o
  api_key: ${OPENAI_API_KEY}

tools:
  enabled:
    - web_search
    - web_fetch
    - bash
    - file_read
    - file_write
  disabled:
    - dangerous_commands
```

---

## 4. Graphiti 双时态知识图谱层

### 4.1 Graphiti 在架构中的定位

```
Graphiti = 双时态知识图谱 = 时间维度的事实存储

传统知识图谱:    实体 ──关系──► 实体
双时态图谱:   [时间区间.valid_from, valid_to] + [recorded_at]
                    │
                    ├──► 支持"当时是什么状态"的快照查询
                    ├──► 支持"何时发生变化"的事件溯源
                    └──► 支持"历史版本对比"的差异分析
```

### 4.2 节点类型设计

```python
from graphiti_core.nodes import EpisodeNode, EntityNode
from datetime import datetime

# 战场实体节点
class Target(EntityNode):
    """打击目标实体"""
    name: str                    # 目标名称
    target_type: str            # radar | command_center | supply_depot
    location: dict              # 地理坐标
    threat_level: str            # critical | high | medium | low
    status: str                  # active | destroyed | unknown

class Unit(EntityNode):
    """作战单元"""
    unit_id: str
    unit_type: str               # infantry | armor | aviation
    position: dict
    combat_capability: float     # 作战能力指数 0-100

class IntelligenceReport(EpisodeNode):
    """情报报告（时间区间事实）"""
    report_id: str
    source: str                  # satellite | drone | human
    confidence: float            # 置信度 0-1
    detected_at: datetime        # 发现时间
    content: str                  # 报告内容摘要

class StrikeOrder(EpisodeNode):
    """打击命令（带执行状态）"""
    order_id: str
    target_id: str
    weapon_type: str
    issued_by: str               # Commander Agent ID
    status: str                   # pending | approved | executed | failed
    executed_at: datetime | None
```

### 4.3 关系类型设计

```python
# 实体间关系（带时序）
rel_detected = {
    "source": IntelligenceReport,
    "target": Target,
    "type": "DETECTED_AT",
    "valid_from": datetime(2026, 4, 11, 14, 30),
    "valid_to": datetime(2026, 4, 11, 15, 45),  # 目标在此时被摧毁
    "recorded_at": datetime(2026, 4, 11, 14, 35),  # 情报记录时间
}

# 事实间关系（证据链）
rel_evidence = {
    "source": IntelligenceReport,
    "target": StrikeOrder,
    "type": "EVIDENCE_FOR",
    "confidence": 0.95,
}
```

### 4.4 Graphiti 查询能力

| 查询模式 | 示例 | 用途 |
|---------|------|------|
| **时序查询** | "14:00-15:00 B区有哪些威胁？" | 态势回放 |
| **状态快照** | "15:30时打击效果如何？" | 效果评估 |
| **证据链追溯** | "这个打击命令的依据是什么？" | 决策解释 |
| **变化检测** | "过去1小时有哪些变化？" | 异常告警 |
| **RAG 增强** | "基于历史情报推荐打击方案" | 决策支持 |

---

## 5. Python Skill 领域工具层

### 5.1 Skill 定位

Python Skills = 领域特定工具，通过 `openharness_bridge.py` 接入 OpenHarness Tool 系统

```
OpenHarness Tool 接口 (Pydantic)
         │
         ▼
┌─────────────────────────────┐
│   openharness_bridge.py    │  ← 桥接适配器
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
│  │ • battlefield│ │ • weapon_       │   │
│  │   analyze   │  │   selection      │   │
│  └─────────────┘  └─────────────────────┘   │
│                                             │
│  ┌─────────────┐  ┌─────────────────────┐   │
│  │ Analysis    │  │   Visualization    │   │
│  │ Skills      │  │   Skills           │   │
│  │             │  │                    │   │
│  │ • pattern_  │  │ • battlefield_   │   │
│  │   match     │  │   render         │   │
│  │ • anomaly_  │  │ • timeline_      │   │
│  │   detect    │  │   generate       │   │
│  │ • trend_    │  │ • graph_        │   │
│  │   analysis  │  │   visualize     │   │
│  └─────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────┘
```

### 5.2 Skill 接口定义

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

## 6. OPA 策略治理层

### 6.1 OPA 在架构中的定位

```
OPA = Open Policy Agent = 策略引擎

职责：
1. 权限校验 - 谁可以执行什么操作
2. 规则执行 - 操作是否符合业务规则
3. 合规检查 - 是否满足法规要求
4. Fail-Close - 不了解的操作默认拒绝
```

### 6.2 策略包设计

```
policies/
├── attack/
│   ├──.rego              # 包声明
│   ├── allow.rego         # 允许规则
│   ├── deny.rego          # 拒绝规则
│   └── test.rego          # 测试用例
├── intelligence/
│   ├── allow.rego
│   └── classify.rego      # 情报分级规则
├── agent/
│   ├── commander.rego     # Commander Agent 权限
│   ├── intelligence.rego  # Intelligence Agent 权限
│   └── operations.rego    # Operations Agent 权限
└── common/
    ├── default.rego       # 默认策略（fail-close）
    └── input.rego         # 输入验证
```

### 6.3 核心策略示例

```rego
# policies/attack/allow.rego
package policies.attack

import future.keywords.if

# 打击目标允许规则
allow if {
    input.action == "attack_target"
    input.commander_id != ""
    input.target.confirmation_level == "acknowledged"
    not is_protected_target(input.target)
    weapon_within_params(input.weapon_type, input.target)
}

# 保护目标检查
is_protected_target(target) if {
    target.category == "civilian"
} if {
    target.category == "medical"
} if {
    target.category == "historical"
}

# 武器参数检查
weapon_within_params(weapon, target) if {
    weapon.effective_range >= target.distance
    weapon.yield <= target.max_tolerable_yield
}
```

```rego
# policies/common/default.rego
package policies.common

import future.keywords.if

# 默认拒绝（fail-close）
default allow = false

# 管理员旁路
allow if {
    input.user.role == "admin"
}
```

### 6.4 OPA 集成方式

```python
# core/opa_client.py
from opa importOPAClient

class OPAManager:
    def __init__(self, opa_url: str = "http://localhost:8181"):
        self.client = OPAClient(base_url=opa_url)

    async def check(self, policy_package: str, input_data: dict) -> bool:
        """
        策略检查

        Args:
            policy_package: 策略包路径，如 "policies/attack/allow"
            input_data: 输入数据

        Returns:
            True if allowed, False if denied
        """
        result = await self.client.check(policy_package, input_data)

        if not result.allow:
            logger.warning(
                f"OPA denied: {policy_package}",
                extra={"reason": result.reason, "input": input_data}
            )

        return result.allow

    async def check_and_raise(self, policy_package: str, input_data: dict):
        """检查失败时抛出异常"""
        if not await self.check(policy_package, input_data):
            raise OPAPolicyDenied(
                policy=policy_package,
                input=input_data,
            )
```

### 6.5 OpenHarness Permission 桥接

```python
# core/openharness_bridge.py

from openharness.permissions.base import PermissionBackend

class OPAPermissionBackend(PermissionBackend):
    """OpenHarness 权限后端 - 使用 OPA"""

    def __init__(self, opa_manager: OPAManager):
        self.opa = opa_manager

    async def check(self, tool_name: str, tool_input: dict, context: dict) -> bool:
        # 映射 Tool 名称到 OPA 策略包
        policy_map = {
            "attack_target": "policies/attack/allow",
            "command_unit": "policies/operations/allow",
            "radar_search": "policies/intelligence/allow",
        }

        policy = policy_map.get(tool_name, "policies/common/default")

        input_data = {
            "action": tool_name,
            "tool_input": tool_input,
            "agent_id": context.get("agent_id"),
            "user": context.get("user"),
        }

        return await self.opa.check(policy, input_data)
```

---

## 7. 三 Agent 协同编排设计

### 7.1 Agent 角色定义

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Commander Agent                            │
│                                                                      │
│  定位: 战术决策中枢，最终决策者                                        │
│  模型: 强推理模型（Claude-3.5 Sonnet / GPT-4 / DeepSeek-R1）         │
│  权限: 最高（commander），唯一可批准高危操作的 Agent                  │
│                                                                      │
│  职责:                                                               │
│  • 接收 Intelligence 的威胁评估                                       │
│  • 接收 Operations 的可行性报告                                       │
│  • 多方案排序与风险权衡                                               │
│  • 高危操作 OPA 规则复核                                              │
│  • 最终打击命令签发                                                   │
│                                                                      │
│  System Prompt:                                                      │
│  "你是战场指挥官，负责在不确定情况下做出最优决策。                    │
│   你的决策必须：                                                      │
│   1. 基于 Intelligence 提供的情报                                    │
│   2. 考虑 Operations 的执行可行性                                    │
│   3. 通过 OPA 策略校验                                               │
│   4. 记录决策理由，供后续复盘"                                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
           ┌────────────────────┴────────────────────┐
           │              Swarm 协调                  │
           │         (OpenHarness Coordinator)       │
           ▼                                        ▼
┌───────────────────────────────┐    ┌───────────────────────────────┐
│     Intelligence Agent        │    │      Operations Agent          │
│                               │    │                               │
│  定位: 战场感知 + 态势理解     │    │  定位: 行动计划生成 + 执行     │
│  模型: 快速分析模型            │    │  模型: 规划模型                │
│         (Kimi / DeepSeek-v3)  │    │         (Qwen / GPT-4o-mini)  │
│                               │    │                               │
│  记忆: Graphiti (持久化)       │    │  工具: 作战执行工具集          │
│                               │    │                               │
│  职责:                        │    │  职责:                        │
│  • 传感器数据采集              │    │  • 生成行动计划                │
│  • 威胁模式识别                │    │  • 命令下发与执行               │
│  • 置信度计算                  │    │  • 执行状态监控                │
│  • 时序关联分析                │    │  • 失败回滚机制                 │
│  • RAG 增强推理                │    │  • 结果回写 Graphiti           │
│                               │    │                               │
│  工具:                        │    │  工具:                        │
│  • radar_search               │    │  • attack_target (需OPA)      │
│  • drone_surveillance         │    │  • command_unit               │
│  • satellite_imagery          │    │  • route_planning             │
│  • threat_assessment          │    │  • weapon_selection           │
│  • pattern_match              │    │  • battle_damage_assessment  │
└───────────────────────────────┘    └───────────────────────────────┘
```

### 7.2 Swarm 协作模式

```python
# core/swarm_orchestrator.py
from openharness.coordinator import SwarmCoordinator
from openharness.agents import AgentConfig

class BattlefieldSwarm:
    """战场多 Agent 协同"""

    def __init__(self):
        self.coordinator = SwarmCoordinator()

        # 初始化三 Agent
        self.commander = AgentConfig(
            name="commander",
            model="claude-3-5-sonnet",
            role="decision_maker",
            tools=["*"],  # 全工具权限（需 OPA 校验）
            permission_level="commander",
        )

        self.intelligence = AgentConfig(
            name="intelligence",
            model="deepseek-chat",
            role="sensor_and_analyzer",
            tools=["radar_*", "drone_*", "satellite_*", "threat_*", "pattern_*"],
            permission_level="intelligence",
            memory_backend="graphiti",  # 使用 Graphiti 作为记忆
        )

        self.operations = AgentConfig(
            name="operations",
            model="qwen-plus",
            role="action_executor",
            tools=["attack_*", "command_*", "route_*", "weapon_*"],
            permission_level="operations",
            requires_opa_approval=True,  # 所有操作需 OPA 确认
        )

    async def execute_mission(self, mission: str):
        """
        OODA 循环执行任务

        流程:
        Observe → Orient → Decide → Act → (循环)
        """
        # 阶段 1: Observe - Intelligence 感知
        observe_result = await self.coordinator.delegate(
            agent=self.intelligence,
            task=f"感知战场: {mission}",
        )

        # 阶段 2: Orient - Intelligence 理解
        orient_result = await self.coordinator.delegate(
            agent=self.intelligence,
            task=f"分析威胁: {observe_result.raw_data}",
            context={"graphiti_episodes": await self.get_historical_context()},
        )

        # 阶段 3: Decide - Commander 决策
        decide_result = await self.coordinator.delegate(
            agent=self.commander,
            task=f"制定打击方案: {orient_result.threat_report}",
            context={
                "options": await self.operations.generate_options(
                    orient_result.targets
                ),
            },
        )

        # 阶段 4: Act - Operations 执行
        act_result = await self.coordinator.delegate(
            agent=self.operations,
            task=f"执行命令: {decide_result.final_order}",
        )

        # 回写 Graphiti
        await self.graphiti.write_episode(
            type="mission_completed",
            data={
                "mission": mission,
                "observe": observe_result,
                "orient": orient_result,
                "decide": decide_result,
                "act": act_result,
            },
        )

        # 触发新一轮 Observe（如果需要持续监控）
        if decide_result.requires_monitoring:
            await self.execute_mission_loop(mission)

        return act_result
```

---

## 8. OODA 闭环实现

### 8.1 闭环流程图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           OODA 闭环执行流程                                   │
└──────────────────────────────────────────────────────────────────────────────┘

   用户: "评估 B 区威胁并打击高价值雷达"
         │
         │ Observe (感知)
         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        Intelligence Agent                                  │
│                                                                            │
│  输入: 用户查询 + 实时传感器                                                │
│  处理:                                                                      │
│    1. radar_search → 扫描 B 区                                             │
│    2. drone_surveillance → 无人机抵近侦察                                   │
│    3. pattern_match → 历史模式匹配                                          │
│  输出:                                                                      │
│    • 威胁清单: [{target_id, location, threat_level, confidence}]            │
│    • 情报置信度: 0.92                                                      │
│    • 历史关联: "该雷达3天前曾暴露位置"                                       │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                                     │ Orient (理解)
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        Intelligence Agent                                  │
│                                                                            │
│  处理:                                                                      │
│    1. threat_assessment → 计算综合威胁指数                                 │
│    2. RAG查询Graphiti → 历史打击效果对比                                    │
│    3. anomaly_detection → 异常模式识别                                      │
│  输出:                                                                      │
│    • 威胁排序: [radar_A(critical), radar_B(high), depot_C(medium)]         │
│    • 打击建议: "优先打击 radar_A，作战窗口15分钟"                            │
│    • 风险提示: "radar_A 有伴随防空力量"                                     │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                                     │ Decide (决策)
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        Commander Agent                                      │
│                                                                            │
│  输入: 威胁评估 + 可行性报告                                                │
│  处理:                                                                      │
│    1. 多方案生成: 方案A(精确打击) / 方案B(电子压制+打击)                     │
│    2. OPA 策略校验:                                                        │
│       • policies/attack/allow → 检查目标类别、武器参数                     │
│       • policies/common/escalation → 检查授权级别                          │
│    3. 风险权衡: 方案A风险高但收益高，方案B更稳妥                           │
│  输出:                                                                      │
│    • 最终命令: 方案A，带 OPA 签章                                           │
│    • 决策理由: "优先摧毁核心节点，符合打击优先原则"                           │
│    • 人工确认: [高危] 需要操作员确认                                        │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                                     │ Act (行动)
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                        Operations Agent                                    │
│                                                                            │
│  输入: 打击命令（已OPA批准）                                                │
│  处理:                                                                      │
│    1. weapon_selection → 选择最优武器                                       │
│    2. route_planning → 规划打击航线                                         │
│    3. attack_target (Tool) → 执行打击                                       │
│       └── OPA Hook: 再次校验 + 记录审计日志                                 │
│    4. battle_damage_assessment → 打击效果评估                               │
│  输出:                                                                      │
│    • 执行状态: SUCCESS                                                      │
│    • 打击效果: radar_A 已摧毁                                               │
│    • 次生损失: 无                                                          │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │
                                     │ 结果回写
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                          Graphiti 图谱                                     │
│                                                                            │
│  写入:                                                                      │
│    • 新 Episode: StrikeExecuted (打击执行)                                 │
│    • 更新 Target 状态: radar_A.status = "destroyed"                         │
│    • 关联证据: Intelligence → Strike → BDA                                │
│                                                                            │
│  触发: 新一轮 Observe（持续监控）                                           │
└────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 实时反馈机制

```python
# core/ooda_loop.py
from typing import AsyncGenerator
import json

class OODALoop:
    """OODA 循环执行器，支持流式输出"""

    async def execute_streaming(
        self,
        mission: str,
    ) -> AsyncGenerator[dict, None]:
        """流式执行 OODA，返回每一步的实时状态"""

        yield {
            "phase": "observe",
            "status": "started",
            "agent": "intelligence",
            "message": "开始感知 B 区战场态势...",
        }

        # Observe
        observe_result = await self.intelligence.observe(mission)
        yield {
            "phase": "observe",
            "status": "completed",
            "agent": "intelligence",
            "data": observe_result,
        }

        # Orient
        yield {"phase": "orient", "status": "started", "agent": "intelligence"}
        orient_result = await self.intelligence.orient(observe_result)
        yield {"phase": "orient", "status": "completed", "data": orient_result}

        # Decide
        yield {"phase": "decide", "status": "started", "agent": "commander"}
        decide_result = await self.commander.decide(orient_result)
        yield {"phase": "decide", "status": "completed", "data": decide_result}

        # Act
        if decide_result.requires_human_confirmation:
            yield {
                "phase": "act",
                "status": "waiting_confirmation",
                "data": decide_result.pending_order,
            }
            # 等待用户确认...
            confirmed = await self.wait_for_confirmation()
            if not confirmed:
                yield {"phase": "act", "status": "cancelled"}
                return

        yield {"phase": "act", "status": "executing", "agent": "operations"}
        act_result = await self.operations.act(decide_result.final_order)

        # 回写 Graphiti
        await self.graphiti.write_episode(act_result)
        yield {"phase": "act", "status": "completed", "data": act_result}
```

---

## 9. 数据架构

### 9.1 数据流总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              数据流                                          │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────┐     ┌──────────────┐     ┌─────────────┐     ┌────────────┐
  │ 传感器    │────►│ Intelligence │────►│   Graphiti  │◄────│  外部数据源 │
  │ Radar    │     │    Agent     │     │   (持久化)   │     │  气象/地形  │
  │ Drone    │     └──────────────┘     └──────┬──────┘     └────────────┘
  │ Satellite│              ▲                   │
  └──────────┘              │                   ▼
                             │            ┌─────────────┐
                             └────────────│   RAG       │
                                          │  增强推理    │
                                          └─────────────┘

  ┌──────────┐     ┌──────────────┐     ┌─────────────┐
  │ Commander│────►│    OPA       │────►│  Operations │
  │  Agent   │     │  (策略校验)   │     │    Agent    │
  └──────────┘     └──────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │  执行结果    │
                                        │  回写Graphiti│
                                        └─────────────┘
```

### 9.2 存储层次

| 存储层 | 技术 | 用途 | 数据示例 |
|--------|------|------|---------|
| **向量存储** | Neo4j Vector | RAG 语义搜索 | 情报文本嵌入 |
| **图存储** | Neo4j | 实体关系 | Target-THREATENED_BY→Intelligence |
| **时序存储** | Graphiti Episode | 双时态事实 | [valid_from, valid_to, recorded_at] |
| **结构化存储** | PostgreSQL | 业务主数据 | 打击命令、授权配置 |
| **对象存储** | S3/MinIO | 文件资产 | 战场图像、雷达回波 |

---

## 10. 技术选型与权衡

### 10.1 核心组件选型

| 组件 | 选项A | 选项B | 选项C | 决策 | 权衡 |
|------|-------|-------|-------|------|------|
| **Agent 框架** | LangGraph | OpenHarness | AutoGen | **OpenHarness** | 开源+生产级+多Agent内置，节省90%代码 |
| **知识图谱** | Neo4j | Amazon Neptune | Graphiti | **Graphiti** | 双时态原生支持，支撑历史回溯 |
| **策略引擎** | OPA | Cedar | Casbin | **OPA** | Rego语言灵活+生态丰富+生产验证 |
| **图数据库** | Neo4j | NetworkX | Memgraph | **Neo4j** | 向量检索+时序+ACID，成熟稳定 |
| **Agent LLM** | Claude | GPT-4 | DeepSeek | **混合** | Commander用强推理，Intelligence用快速 |

### 10.2 权衡矩阵

#### 10.2.1 LLM 模型分配

| Agent | 推荐模型 | 理由 |
|-------|---------|------|
| Commander | Claude-3.5 Sonnet / GPT-4 | 复杂推理+风险权衡 |
| Intelligence | DeepSeek-v3 / Kimi | 快速分析+长上下文 |
| Operations | GPT-4o-mini / Qwen | 规划+执行，速度优先 |

#### 10.2.2 Skill 体系策略

| 策略 | 优点 | 缺点 | 决策 |
|------|------|------|------|
| 统一 OpenHarness Markdown | 生态统一 | 迁移成本高 | 过渡期双层并行 |
| 双层并行 (Markdown + Python) | 快速验证+灵活 | 两套维护 | **采用** |
| 统一 Python | 现有积累 | 脱离生态 | 不采用 |

---

## 17. 架构决策记录（ADR）

### ADR-001: 采用 OpenHarness 作为 Agent 基础设施

**状态**: 已接受

**上下文**: 需要构建多 Agent 协同系统，面临自研 vs 复用选择

**决策**: 采用 OpenHarness 作为 Agent 基础设施，通过 `openharness_bridge.py` 桥接现有组件

**后果**:
- ✅ 节省 ~5000 行基础设施代码
- ✅ 内置 Swarm 多 Agent 协调、Tool 系统、Permission 检查
- ✅ 社区活跃（8.7k stars），持续更新
- ❌ 引入外部依赖，需跟进版本更新
- ❌ 部分定制受限，需通过 Plugin 机制扩展

**可逆性**: 高。OpenHarness 通过 HTTP API 交互，可替换为其他框架。

---

### ADR-002: Graphiti 作为双时态知识图谱

**状态**: 已接受

**上下文**: 需要支撑"当时发生了什么"的历史回溯和时间区间查询

**决策**: Graphiti 作为 Memory 层，Neo4j 作为底层图数据库

**后果**:
- ✅ 原生支持双时态（valid_time + transaction_time）
- ✅ Episode 设计天然匹配战场事件流
- ✅ 支持时序推理和 RAG 增强
- ❌ Graphiti 相对新兴，社区较小
- ❌ 需适配 OpenHarness Memory 接口

**可逆性**: 中。替换为纯 Neo4j 或其他图数据库需重写记忆层。

---

### ADR-003: OPA 作为策略治理引擎

**状态**: 已接受

**上下文**: 高危操作（打击命令）需要策略校验

**决策**: OPA 作为独立的策略服务，集成到 OpenHarness Permission 系统

**后果**:
- ✅ Rego 语言表达力强，策略可版本化
- ✅ 与 OpenHarness Permission 系统无缝集成
- ✅ Fail-close 默认策略，安全性高
- ❌ 引入额外服务（OPA Docker 容器）
- ❌ Rego 学习曲线

**可逆性**: 中。替换为 Cedar/Casbin 需重写策略代码。

---

### ADR-004: Skill 双层并行策略

**状态**: 已接受

**上下文**: 现有 Python Skills 积累 vs OpenHarness Markdown Skills 生态

**决策**: 过渡期采用双层并行，长期统一到 OpenHarness Markdown

**后果**:
- ✅ 快速验证：Python Skills 可直接使用
- ✅ 生态接轨：新 Skills 采用 Markdown 格式
- ❌ 两套维护：过渡期增加工作量
- ❌ 桥接层复杂度

**可逆性**: 高。统一格式后删除桥接层即可。

---

### ADR-005: 三 Agent 角色分工

**状态**: 已接受

**上下文**: 需要明确 Intelligence/Commander/Operations 职责边界

**决策**:

- Intelligence: 感知 + 理解（Observe + Orient）
- Commander: 决策（Decide）
- Operations: 执行（Act）

**后果**:
- ✅ 单一职责：每个 Agent 专注一个阶段
- ✅ 易于扩展：新增 Agent 类型不影响现有逻辑
- ✅ 审计友好：每步操作可追溯到具体 Agent
- ❌ Agent 间通信开销
- ❌ 状态同步挑战

**可逆性**: 高。OpenHarness Swarm 支持动态调整 Agent 角色。

---

### ADR-006: 前端采用 React + Ant Design 技术栈

**状态**: 已接受

**上下文**: 需要构建战场前端和管理后台，面临技术选型决策

**决策**: 采用 React 18 + TypeScript + Ant Design 5 作为前端技术栈

**后果**:
- ✅ 企业级组件库，开发效率高
- ✅ TypeScript 类型安全
- ✅ AntV G6 + ECharts 支持图谱可视化
- ✅ CesiumJS 支持地理空间展示
- ❌ 包体积较大
- ❌ 学习曲线（对于新加入的团队成员）

**可逆性**: 中。前端框架切换成本较高，但组件层可抽象。

---

### ADR-007: 审计日志完整记录

**状态**: 已接受

**上下文**: 战场决策系统需要完整的操作审计追溯

**决策**: 所有用户操作、Agent 操作、系统事件均记录审计日志

**后果**:
- ✅ 合规要求满足
- ✅ 事后复盘有据可查
- ✅ 异常行为可追溯
- ❌ 存储成本增加
- ❌ 需要注意敏感信息脱敏

**可逆性**: 低。审计日志是合规要求，不易移除。

---

### ADR-008: Markdown 编写 OPA 策略

**状态**: 已接受

**上下文**: 运维人员不熟悉 Rego 语言

**决策**: 提供 Markdown 格式的策略编辑器，自动转换为 Rego

**后果**:
- ✅ 降低策略编写门槛
- ✅ 提供语法高亮和预览
- ✅ 可版本化管理
- ❌ 转换层复杂度
- ❌ 某些复杂 Rego 特性可能无法表达

**可逆性**: 高。保留直接编辑 Rego 的能力作为备选。

---

### ADR-009: 多模态文档处理可配置

**状态**: 提议中

**上下文**: 需要支持上传外部情报文档（图像、PDF、语音）

**决策**: 多模态处理采用可插拔架构，支持配置不同模型

**后果**:
- ✅ 灵活适配不同场景
- ✅ 可根据数据敏感度选择本地/云端模型
- ❌ 配置复杂度增加
- ❌ 多模型集成测试工作量大

**可逆性**: 中。模型可替换，但接口需要统一。

---

### ADR-010: 角色配置热生效

**状态**: 已接受

**上下文**: 需要快速调整角色权限而不重启服务

**决策**: 角色配置支持手动或自动热生效

**后果**:
- ✅ 运营灵活性高
- ✅ 可快速响应安全事件
- ❌ 需要考虑缓存失效
- ❌ 并发修改需要锁机制

**可逆性**: 高。可降级为重启生效模式。

---

### ADR-011: 配置组合引擎

**状态**: 已接受

**上下文**: 需要支持角色、技能、策略的灵活配置组合

**决策**: 引入 ConfigurationProfile 概念，实现配置模板化和组合化

**后果**:
- ✅ 角色定义与技能/策略解耦
- ✅ 支持配置模板复用
- ✅ 可快速创建新角色
- ❌ 配置复杂度增加
- ❌ 需要配置验证机制

**可逆性**: 高。可降级为硬编码配置。

---

### ADR-012: 多数据源统一接入

**状态**: 已接受

**上下文**: 需要支持结构化和非结构化数据源的统一接入

**决策**: 采用适配器模式，每种数据源有专门适配器，统一输出 DataEntity

**后果**:
- ✅ 数据源类型可扩展
- ✅ 接入新数据源成本低
- ✅ 统一本体映射
- ❌ 适配器维护成本
- ❌ 需要处理数据质量差异

**可逆性**: 中。替换适配器需要修改映射规则。

---

### ADR-013: 技能热插拔架构

**状态**: 已接受

**上下文**: 需要支持技能的动态注册、启用、禁用，无需重启

**决策**: SkillRegistry 作为技能生命周期管理器，支持热加载

**后果**:
- ✅ 技能更新无需重启服务
- ✅ 可灰度发布新技能
- ✅ 故障技能可快速禁用
- ❌ 运行时状态管理复杂
- ❌ 需要考虑技能间依赖

**可逆性**: 高。可降级为启动时加载。

---

### ADR-014: 可扩展图表系统

**状态**: 已接受

**上下文**: 问答需要展示多种类型的图表，且类型需可扩展

**决策**: ChartRegistry 模式，支持注册新图表类型和渲染器

**后果**:
- ✅ 新图表类型无需修改核心代码
- ✅ 支持自定义图表
- ✅ 渲染器可独立演进
- ❌ 图表配置复杂度
- ❌ 需要统一的渲染接口

**可逆性**: 高。移除图表类型不影响核心功能。

---

### ADR-015: 完备文档体系

**状态**: 已接受

**上下文**: 需要从设计、开发、测试到运维的完整文档支撑

**决策**: 文档即代码，与代码同版本管理，自动化生成部分文档

**后果**:
- ✅ 文档与代码同步
- ✅ 可追溯文档历史
- ✅ 降低维护成本
- ❌ 初始建立成本高
- ❌ 需要持续维护

**可逆性**: 低。文档体系一旦建立，移除影响知识传承。

---

### ADR-016: 原子提交规范

**状态**: 已接受

**上下文**: 需要规范代码提交，每步原子功能修改都有清晰记录

**决策**: 采用 Conventional Commits 规范，commitizen 工具辅助

**后果**:
- ✅ 提交历史清晰可追溯
- ✅ 自动生成 CHANGELOG
- ✅ 便于代码审查
- ❌ 需要团队培训
- ❌ 初期可能降低提交速度

**可逆性**: 高。可调整为宽松规范。

---

### ADR-017: 模拟战场数据生成引擎

**状态**: 提议中

**上下文**: 管理人员需要模拟战场数据功能，自动生成模拟战场变化事件，支持手工选择采用。

**决策**: 设计战场模拟器（BattlefieldSimulator），基于事件驱动架构，支持：
- 预定义事件模板（遭遇战、增援、撤退等）
- 随机事件生成（基于概率分布）
- 事件时间线控制（加速/减速/暂停）
- 事件采用审核队列

**后果**:
- ✅ 支持无外部数据源的演示和培训
- ✅ 可控的测试场景生成
- ✅ 支持边界条件和异常场景测试
- ❌ 需要维护事件模板库
- ❌ 模拟数据与真实数据的边界需明确区分

**可逆性**: 高。模拟器可独立部署或禁用。

---

### ADR-018: 多模态文档处理流水线

**状态**: 提议中

**上下文**: 需要上传外部情报文档（PDF、Word、图片等），并基于此更新本体。

**决策**: 构建多模态文档处理流水线（DocumentPipeline）：
- **文档解析层**: PDF 解析、OCR、文本提取
- **内容理解层**: LLM 摘要、实体识别、关系抽取
- **本体更新层**: Graphiti 节点/边创建、Neo4j 写入
- **独立配置**: 每个环节可配置不同模型

**后果**:
- ✅ 支持多种文档格式
- ✅ 可独立配置各层模型
- ✅ 流水线可监控和回滚
- ❌ 处理延迟较高（多模态 LLM 调用）
- ❌ 需要处理文档解析错误

**可逆性**: 中。可简化处理流程或降级为纯文本处理。

---

### ADR-019: 管理员控制台统一界面

**状态**: 提议中

**上下文**: 管理人员需要单独的管理界面，涵盖模拟数据管理、本体管理、配置管理等。

**决策**: 设计统一管理员控制台（AdminConsole），包含：
- **模拟数据管理**: 生成、审核、采用/拒绝
- **本体图谱可视化**: D3.js 动态图谱、节点/边属性查看
- **日志溯源面板**: 实时日志流、可跳转至原始事件
- **本体编辑区**: 手动新增规则、OPA 策略、处理逻辑

**后果**:
- ✅ 集中管理，降低学习成本
- ✅ 实时反馈，减少操作失误
- ✅ 审计追溯能力强
- ❌ 界面复杂度增加
- ❌ 需要细粒度权限控制

**可逆性**: 中。管理功能可分散到独立页面。

---

### ADR-020: 战争实体标准本体库

**状态**: 提议中

**上下文**: 需要基础的战争实体本体，包括各实体的属性，提供中英文说明。

**决策**: 构建战争实体标准本体库（WarEntityOntology）：
- **基础实体**: 部队(Unit)、装备(Equipment)、地形(Terrain)、气象(Weather)等
- **实体属性**: 数量、位置、状态、能力等（中英文双语）
- **关系类型**: 指挥(commands)、部署(deploys)、位于(located_at)等
- **本体加载器**: 支持初始化加载和增量更新

**后果**:
- ✅ 快速启动，无需从零构建本体
- ✅ 术语统一，便于多系统集成
- ✅ 中英文支持，便于国际协作
- ❌ 领域特定，可能需要扩展
- ❌ 需要持续维护实体库

**可逆性**: 低。本体是系统核心，变更成本高。

---

### ADR-021: 模拟数仓与统一查询服务

**状态**: 提议中

**上下文**: 需要模拟数仓的基础数据，为本体提供指标属性，本体作为统一语义层对外提供查询服务。

**决策**: 构建模拟数仓与统一查询服务（DataWarehouse + QueryService）：
- **模拟数仓**: 预计算指标数据（打击效能、生存概率等）
- **本体映射**: 数仓字段 → Graphiti 节点属性
- **统一查询**: GraphQL API，支持跨数据源联合查询
- **缓存层**: Redis 缓存热点查询结果

**后果**:
- ✅ 结构化数据与本体统一访问
- ✅ 查询性能优化（预计算 + 缓存）
- ✅ 支持复杂分析查询
- ❌ 数据一致性挑战
- ❌ 需要额外存储资源

**可逆性**: 中。查询服务可独立部署。

---

## 19. 需求追溯矩阵

### 19.1 硬性需求覆盖表

| # | 硬性需求 | 功能编号 | ADR 决策 | 优先级 |
|---|----------|----------|----------|--------|
| 1 | 角色前端了解战场情况，询问战场信息，skill 可扩展 | F-001, F-030 | ADR-001, ADR-004 | P0 |
| 2 | **模拟战场数据生成功能** | F-060 | **ADR-017** | P0 |
| 3 | **上传外部情报文档（多模态处理）** | F-061 | **ADR-018** | P0 |
| 4 | **管理员管理界面（模拟数据、本体图谱、日志溯源）** | F-070, F-071, F-072, F-073 | **ADR-019** | P0 |
| 5 | 配置界面分组和可视化配置 | F-080 | ADR-010, ADR-011 | P0 |
| 6 | **战争实体本体库（中英文说明）** | F-090 | **ADR-020** | P0 |
| 7 | **模拟数仓与统一查询服务** | F-091 | **ADR-021** | P1 |
| 8 | OPA 策略 Markdown 自动转化 | F-012 | ADR-008 | P0 |
| 9 | 角色管理界面（skill、OPA 策略绑定） | F-010, F-011 | ADR-010, ADR-013 | P0 |
| 10 | Web 前端实时查看战场变化 | F-031 | ADR-006 | P0 |
| 11 | 快速添加信息到问答 | F-033 | ADR-004 | P1 |
| 12 | 审计日志功能（所有操作记录） | F-007, F-072 | ADR-007 | P0 |

### 19.2 功能需求与 ADR 对照

| 功能需求 | 功能编号 | 对应章节 | ADR |
|----------|----------|----------|-----|
| 多 Agent 调度系统 | F-001 | 第8章 | ADR-005 |
| Graphiti 知识图谱 | F-002 | 第5章 | ADR-002 |
| OPA 策略治理 | F-003 | 第7章 | ADR-003 |
| Skill 体系 | F-004 | 第6章 | ADR-004 |
| 角色配置组合 | F-010 | 第14章 | ADR-010, ADR-011 |
| 技能热插拔 | F-011 | 第14章 | ADR-013 |
| 策略 Markdown 编写 | F-012 | 第7章 | ADR-008 |
| 规则引擎 | F-013 | 第14章 | ADR-011 |
| 多数据源接入 | F-020 | 第13章 | ADR-012 |
| 本体构建 | F-021 | 第13章 | ADR-020 |
| 技能绑定 | F-022 | 第13章 | ADR-013 |
| 多 Agent 问答 | F-030 | 第11章 | ADR-005 |
| 图表展示 | F-031 | 第11章 | ADR-014 |
| 图表扩展 | F-032 | 第11章 | ADR-014 |
| 过程可视化 | F-033 | 第11章 | ADR-006 |
| 完备文档体系 | F-040 | 第19章 | ADR-015 |
| 原子提交规范 | F-050 | 第16章 | ADR-016 |
| 模拟战场数据 | F-060 | 第12章 | ADR-017 |
| 多模态文档处理 | F-061 | 第13章 | ADR-018 |
| 管理员控制台 | F-070 | 第12章 | ADR-019 |
| 本体图谱可视化 | F-071 | 第13章 | ADR-019 |
| 日志溯源 | F-072 | 第15章 | ADR-007 |
| 本体手动编辑 | F-073 | 第13章 | ADR-019 |
| 平台配置中心 | F-080 | 第16章 | ADR-011 |
| 战争实体本体库 | F-090 | 第13章 | ADR-020 |
| 模拟数仓 | F-091 | 第13章 | ADR-021 |

### 19.3 ADR 与功能需求反向追溯

| ADR | 决策标题 | 支持的功能需求 |
|-----|----------|----------------|
| ADR-001 | OpenHarness 作为 Agent 基础设施 | F-001 |
| ADR-002 | Graphiti 作为双时态知识图谱 | F-002, F-021 |
| ADR-003 | OPA 作为策略治理引擎 | F-003, F-012 |
| ADR-004 | Skill 双层并行策略 | F-004, F-011, F-033 |
| ADR-005 | 三 Agent 角色分工 | F-001, F-030 |
| ADR-006 | 前端 React + Ant Design | F-033 |
| ADR-007 | 审计日志完整记录 | F-007, F-072 |
| ADR-008 | Markdown 编写 OPA 策略 | F-012 |
| ADR-009 | 多模态文档处理可配置 | F-061 |
| ADR-010 | 角色配置热生效 | F-010 |
| ADR-011 | 配置组合引擎 | F-010, F-013, F-080 |
| ADR-012 | 多数据源统一接入 | F-020 |
| ADR-013 | 技能热插拔架构 | F-011, F-022 |
| ADR-014 | 可扩展图表系统 | F-031, F-032 |
| ADR-015 | 完备文档体系 | F-040 |
| ADR-016 | 原子提交规范 | F-050 |
| ADR-017 | 模拟战场数据生成引擎 | F-060 |
| ADR-018 | 多模态文档处理流水线 | F-061 |
| ADR-019 | 管理员控制台统一界面 | F-070, F-071, F-073 |
| ADR-020 | 战争实体标准本体库 | F-021, F-090 |
| ADR-021 | 模拟数仓与统一查询服务 | F-091 |

### 19.4 优先级矩阵

```
                    高业务价值
                         │
     ┌───────────────────┼───────────────────┐
     │                   │                   │
     │   紧急且重要       │   重要不紧急       │
     │   (P0)           │   (P1)           │
     │                   │                   │
低───┼───────────────────┼───────────────────┼────高
技───┤                   │                   │    术
术───┤   应急补丁         │   技术债务         │    风
复───┤   (临时方案)       │   (规划解决)       │    险
杂────┴───────────────────┴───────────────────┘
度
                         │
                    低业务价值
```

| 象限 | 需求 | 策略 |
|------|------|------|
| P0 (紧急+重要) | F-001~F-005, F-007, F-010~F-012, F-030~F-031, F-060~F-061, F-070~F-073, F-090 | 立即实施 |
| P1 (重要不紧急) | F-013, F-020~F-022, F-032~F-033, F-091 | 规划迭代 |
| P2 (技术债务) | F-040, F-050, F-080 | 持续改进 |

### 19.5 需求状态跟踪

| 功能编号 | 需求描述 | 状态 | 迭代 |
|----------|----------|------|------|
| F-001 | 多 Agent 调度系统 | ⏳ 待开发 | Phase 1 |
| F-002 | Graphiti 知识图谱 | 🔄 开发中 | Phase 0 |
| F-003 | OPA 策略治理 | ⏳ 待开发 | Phase 0 |
| F-004 | Skill 体系 | 🔄 开发中 | Phase 1 |
| F-007 | 审计日志功能 | ⏳ 待开发 | Phase 1 |
| F-010 | 角色配置组合 | ⏳ 待开发 | Phase 2 |
| F-011 | 技能热插拔 | ⏳ 待开发 | Phase 2 |
| F-012 | 策略 Markdown 编写 | ⏳ 待开发 | Phase 1 |
| F-013 | 规则引擎 | ⏳ 待开发 | Phase 2 |
| F-020 | 多数据源接入 | ⏳ 待开发 | Phase 2 |
| F-021 | 本体构建 | 🔄 开发中 | Phase 0 |
| F-022 | 技能绑定 | ⏳ 待开发 | Phase 2 |
| F-030 | 多 Agent 问答 | ⏳ 待开发 | Phase 1 |
| F-031 | 图表展示 | 🔄 开发中 | Phase 1 |
| F-032 | 图表扩展 | ⏳ 待开发 | Phase 2 |
| F-033 | 过程可视化 | ⏳ 待开发 | Phase 2 |
| F-040 | 完备文档体系 | ⏳ 待开发 | Phase 3 |
| F-050 | 原子提交规范 | ✅ 已建立 | Phase 0 |
| F-060 | 模拟战场数据 | ⏳ 待开发 | Phase 1 |
| F-061 | 多模态文档处理 | ⏳ 待开发 | Phase 2 |
| F-070 | 管理员控制台 | ⏳ 待开发 | Phase 2 |
| F-071 | 本体图谱可视化 | ⏳ 待开发 | Phase 2 |
| F-072 | 日志溯源 | ⏳ 待开发 | Phase 2 |
| F-073 | 本体手动编辑 | ⏳ 待开发 | Phase 2 |
| F-080 | 平台配置中心 | ⏳ 待开发 | Phase 1 |
| F-090 | 战争实体本体库 | ⏳ 待开发 | Phase 0 |
| F-091 | 模拟数仓 | ⏳ 待开发 | Phase 2 |

---

## 20. 演进路线图

### Phase 0: 基础设施搭建（2-4 周）

```
目标: 搭建开发环境，验证核心组件集成
```

| 任务 | 时间 | 负责人 |
|------|------|--------|
| OpenHarness 安装配置 | Week 1 | 架构师 |
| Graphiti + Neo4j 集成 | Week 1 | 开发者A |
| OPA 服务部署 + 基础策略 | Week 2 | 开发者B |
| openharness_bridge.py 桥接 | Week 2 | 开发者A |
| Python Skills → Tool 桥接 | Week 3 | 开发者B |
| 单元测试覆盖 (>80%) | Week 4 | 全员 |

**验收标准**:
- `oh` CLI 可正常运行
- Graphiti 可写入/查询 Episode
- OPA 可执行基础策略检查
- 至少 3 个 Python Skill 可通过 OpenHarness 调用

---

### Phase 1: 单 Agent 闭环（1-2 月）

```
目标: Intelligence Agent 独立完成 Observe + Orient
```

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Phase 1: 单 Agent 闭环                             │
└────────────────────────────────────────────────────────────────────────┘

Week 5-6   Intelligence Agent 开发
            ├─ radar_search Skill
            ├─ drone_surveillance Skill
            ├─ threat_assessment Skill
            └─ 单 Agent 测试

Week 7-8   Graphiti RAG 增强
            ├─ 情报文本向量化
            ├─ 历史模式匹配
            └─ RAG 增强推理

Week 9-10  工具链完善
            ├─ MCP 接入战场仿真器
            ├─ 可视化组件
            └─ 日志/追踪集成

Week 11-12 Demo: "分析 B 区威胁"
            └─ Intelligence Agent 独立输出威胁报告
```

**验收标准**:
- 用户输入 "分析 B 区威胁" → Intelligence Agent 输出结构化威胁报告
- 响应时间 < 10 秒
- 威胁识别准确率 > 85%（基于测试集）

---

### Phase 2: 三 Agent 协同（2-3 月）

```
目标: Commander + Operations Agent 加入，完成 OODA 闭环
```

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Phase 2: 三 Agent 协同                             │
└────────────────────────────────────────────────────────────────────────┘

Week 13-14 Commander Agent 开发
            ├─ 方案生成 + 排序
            ├─ OPA 集成
            └─ 人工确认机制

Week 15-16 Operations Agent 开发
            ├─ attack_target Skill
            ├─ command_unit Skill
            └─ 执行状态监控

Week 17-18 Swarm 协调集成
            ├─ OpenHarness Swarm 配置
            ├─ Agent 间通信协议
            └─ 错误处理 + 回滚

Week 19-20 完整 OODA 闭环测试
            ├─ 感知→理解→决策→行动
            ├─ Graphiti 回写验证
            └─ 人工介入点测试

Week 21-24 性能优化 + 文档
            ├─ 并发优化
            ├─ 可观测性完善
            └─ 用户文档 + API 文档
```

**验收标准**:
- 完整 OODA 流程端到端 < 30 秒
- OPA 策略覆盖率 > 90%
- 三 Agent 协作成功率 > 95%

---

### Phase 3: 生产化（3-6 月）

```
目标: 生产级部署，高可用，可观测
```

| 里程碑 | 内容 |
|--------|------|
| M1 (Month 3) | Docker Compose 部署，监控告警 |
| M2 (Month 4) | 多租户支持，权限细化 |
| M3 (Month 5) | 高可用架构（主备切换） |
| M4-M6 (Month 6) | 性能调优，容量规划 |

---

### Phase 4: 高级特性（6-12 月）

```
目标: 地理空间层、多模态情报、战场数字孪生
```

| 功能 | 描述 | 时间 |
|------|------|------|
| 地理空间层 | 战场态势地图，实时位置追踪 | Month 6-8 |
| 多模态情报 | 图像识别、语音指令 | Month 8-10 |
| 战场数字孪生 | 3D 战场仿真 | Month 10-12 |

---

## 21. 文档体系

### 19.1 文档架构概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           完备文档体系 (Complete Documentation)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   设计文档      │  │   开发文档      │  │   测试文档      │             │
│  │  Design Docs    │  │  Dev Docs       │  │  Test Docs      │             │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤             │
│  │ • 架构设计      │  │ • 开发指南      │  │ • 测试策略      │             │
│  │ • 接口设计      │  │ • API 参考      │  │ • 测试用例      │             │
│  │ • 数据字典      │  │ • 代码规范      │  │ • 测试报告      │             │
│  │ • 模块设计      │  │ • 部署手册      │  │ • 自动化测试    │             │
│  │ • 安全设计      │  │ • 运维手册      │  │ • 性能测试      │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   使用手册      │  │   运营文档      │  │   质量保证      │             │
│  │  User Docs      │  │  Ops Docs       │  │  QA Docs        │             │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤             │
│  │ • 用户指南      │  │ • 运维手册      │  │ • 验收标准      │             │
│  │ • 管理员指南    │  │ • 故障排查      │  │ • 发布检查单    │             │
│  │ • 快速入门      │  │ • 监控告警      │  │ • 质量报告      │             │
│  │ • FAQ           │  │ • 备份恢复      │  │ • 合规文档      │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 19.2 文档清单

#### 19.2.1 设计文档

| 文档名称 | 路径 | 描述 | 更新频率 |
|----------|------|------|----------|
| **架构设计文档** | `docs/ARCHITECTURE.md` | 整体架构、组件设计、ADR | 每季度审查 |
| **接口设计文档** | `docs/API.md` | REST API、WebSocket 协议定义 | 与 API 同版本 |
| **数据字典** | `docs/DATA_DICTIONARY.md` | 数据库表结构、字段说明 | 数据库变更时 |
| **模块设计文档** | `docs/modules/{module}/DESIGN.md` | 各模块详细设计 | 模块重构时 |
| **安全设计文档** | `docs/SECURITY.md` | 安全架构、威胁建模 | 每半年审查 |

#### 19.2.2 开发文档

| 文档名称 | 路径 | 描述 | 更新频率 |
|----------|------|------|----------|
| **开发指南** | `docs/DEVELOPER_GUIDE.md` | 环境搭建、开发流程 | 按需更新 |
| **API 参考** | `docs/openapi.yaml` | OpenAPI 3.0 规范 | API 变更时自动生成 |
| **代码规范** | `docs/CODE_STYLE.md` | 编码规范、命名约定 | 按需更新 |
| **部署手册** | `docs/DEPLOYMENT.md` | Docker、K8s 部署 | 部署变更时 |
| **技能开发指南** | `docs/SKILL_DEVELOPMENT.md` | 如何开发新 Skill | 按需更新 |
| **OPA 策略编写指南** | `docs/OPA_POLICY_GUIDE.md` | Rego 策略编写规范 | 按需更新 |

#### 19.2.3 测试文档

| 文档名称 | 路径 | 描述 | 更新频率 |
|----------|------|------|----------|
| **测试策略** | `docs/TEST_STRATEGY.md` | 测试方法论、覆盖率目标 | 每季度 |
| **单元测试用例** | `tests/unit/` | pytest 用例 | 与代码同步 |
| **集成测试用例** | `tests/integration/` | API、组件集成测试 | 按需更新 |
| **E2E 测试用例** | `tests/e2e/` | Playwright 端到端测试 | 按需更新 |
| **性能测试报告** | `docs/reports/PERF_TEST_{date}.md` | 性能基准测试 | 每次发布前 |
| **安全测试报告** | `docs/reports/SECURITY_TEST_{date}.md` | 安全扫描报告 | 按需更新 |

#### 19.2.4 使用手册

| 文档名称 | 路径 | 描述 | 受众 |
|----------|------|------|------|
| **用户手册** | `docs/user/MANUAL.md` | 功能使用说明 | 指挥官、分析员 |
| **管理员手册** | `docs/admin/ADMIN_GUIDE.md` | 系统配置说明 | 系统管理员 |
| **快速入门** | `docs/user/QUICK_START.md` | 5 分钟上手指南 | 新用户 |
| **常见问题** | `docs/user/FAQ.md` | FAQ 汇总 | 所有用户 |

#### 19.2.5 运营文档

| 文档名称 | 路径 | 描述 |
|----------|------|------|
| **运维手册** | `docs/ops/OPS_MANUAL.md` | 日常运维操作 |
| **故障排查指南** | `docs/ops/TROUBLESHOOTING.md` | 常见问题处理 |
| **监控告警配置** | `docs/ops/MONITORING.md` | Prometheus/Grafana 配置 |
| **备份恢复手册** | `docs/ops/BACKUP_RECOVERY.md` | 数据备份与恢复 |
| **发布检查单** | `docs/ops/RELEASE_CHECKLIST.md` | 发布前检查项 |

### 19.3 文档维护流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          文档生命周期 (Documentation Lifecycle)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│  │  编写   │───▶│  评审   │───▶│  发布   │───▶│  维护   │───▶│  归档   │ │
│  │ Author  │    │ Review  │    │ Publish │    │ Maintain │    │ Archive  │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│       │              │              │              │                    │      │
│       ▼              ▼              ▼              ▼                    ▼      │
│  • 功能开发时    • PR 评审       • 版本发布      • 版本更新时      • 版本 EOL  │
│  • 代码变更时    • Tech Lead     • 自动生成      • 用户反馈时      • 归档存储  │
│  • 需求文档化    • 文档审查      • GitHub Pages  • 错误更正时      • 版本保留  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 19.4 代码提交规范（原子功能提交）

```bash
# 提交格式
<type>(<scope>): <subject>

# type 类型
feat:     新功能
fix:      缺陷修复
docs:     文档更新
style:    代码格式（不影响功能）
refactor: 重构（既不修复也不添加功能）
perf:     性能优化
test:     测试相关
chore:    构建/工具变更

# scope 影响范围
core:       核心模块
skills:     技能模块
ontology:   本体模块
visualization: 可视化模块
admin:      管理后台
docs:       文档

# 示例
feat(skills): 添加威胁评估技能
fix(core): 修复 Graphiti 连接池泄漏
docs(ontology): 更新数据字典
refactor(admin): 重构角色配置模块
test(skills): 添加技能测试用例
```

### 19.5 自动化文档生成

```yaml
# .github/workflows/docs.yml
name: Documentation

on:
  push:
    branches: [main]
    paths: ['docs/**', '**.md']
  release:
    types: [published]

jobs:
  generate-api-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Generate OpenAPI docs
        run: |
          npm run docs:api

      - name: Upload API docs
        uses: actions/upload-artifact@v4
        with:
          name: api-docs
          path: docs/api/

  build-site:
    runs-on: ubuntu-latest
    needs: generate-api-docs
    steps:
      - uses: actions/checkout@v4

      - name: Build documentation
        run: |
          npm run docs:build

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./docs/_site
```

---

## 11. 前端界面架构

### 11.1 前端定位

前端界面是用户与系统的交互窗口，分为两大类：
- **战场前端**: 供不同角色（指挥官、情报分析员、操作员）使用
- **管理后台**: 供管理员配置系统、管理本体、审计日志

### 11.2 技术选型

| 组件 | 技术选型 | 理由 |
|------|---------|------|
| **框架** | React 18 + TypeScript | 组件化、类型安全、生态丰富 |
| **UI 库** | Ant Design 5 | 企业级组件、主题定制 |
| **状态管理** | Zustand | 轻量、支持持久化 |
| **图表** | ECharts + AntV G6 | 态势图 + 知识图谱可视化 |
| **地图** | CesiumJS | 3D 地理空间可视化 |
| **实时通信** | WebSocket + SSE | 实时推送战场变化 |
| **构建工具** | Vite | 快速启动、HMR |

### 11.3 战场前端（C4 Level 4 - 用户视角）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           战场前端 (Battlefield Frontend)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐               │
│  │   态势概览      │  │   情报分析      │  │   指挥控制      │               │
│  │   (Dashboard)   │  │   (Analysis)    │  │   (Command)    │               │
│  │                 │  │                 │  │                 │               │
│  │ • 实时地图      │  │ • 威胁报告      │  │ • 命令下发      │               │
│  │ • 单位位置      │  │ • 目标分析      │  │ • 执行监控      │               │
│  │ • 友军/敌军     │  │ • 模式识别      │  │ • 结果反馈      │               │
│  │ • 变更高亮      │  │ • 证据链查看    │  │ • 历史回放      │               │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                      智能助手 (AI Assistant)                      │        │
│  │                                                                   │        │
│  │  ┌─────────────────────────────────────────────────────────┐    │        │
│  │  │  指挥官: 帮我分析 B 区的威胁情况                          │    │        │
│  │  └─────────────────────────────────────────────────────────┘    │        │
│  │                          │                                      │        │
│  │                          ▼                                      │        │
│  │  ┌─────────────────────────────────────────────────────────┐    │        │
│  │  │  🤖 Intelligence Agent: 发现 3 个雷达，威胁等级 High     │    │        │
│  │  │  推荐优先打击 RADAR_01，作战窗口 15 分钟                 │    │        │
│  │  │  [添加到问答] [查看详情] [立即打击]                       │    │        │
│  │  └─────────────────────────────────────────────────────────┘    │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                      实时事件流 (Event Stream)                     │        │
│  │  🔴 [14:30] RADAR_01 状态变更: ACTIVE → DESTROYED              │        │
│  │  🟡 [14:28] 发现新目标: Mobile_SAM_02 (C区)                     │        │
│  │  🟢 [14:25] 打击命令执行成功: LAUNCHER_01                      │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.4 实时战场同步机制

```typescript
// frontend/services/websocket.ts
import { io, Socket } from 'socket.io-client';

class BattlefieldSocket {
  private socket: Socket;

  constructor() {
    this.socket = io(BATTLEFIELD_WS_URL, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
    });
  }

  // 订阅战场实体变化
  onEntityChange(callback: (entity: EntityChange) => void) {
    this.socket.on('entity:changed', callback);
  }

  // 订阅情报更新
  onIntelUpdate(callback: (intel: IntelUpdate) => void) {
    this.socket.on('intel:updated', callback);
  }

  // 订阅打击结果
  onStrikeResult(callback: (result: StrikeResult) => void) {
    this.socket.on('strike:result', callback);
  }

  // 订阅 OODA 阶段
  onOODAProgress(callback: (progress: OODAProgress) => void) {
    this.socket.on('ooda:progress', callback);
  }
}

// 前端状态管理
interface BattlefieldStore {
  entities: Map<string, Entity>;
  highlights: EntityChange[];  // 变更高亮
  pendingOrders: Order[];

  // 添加变更到高亮队列
  addHighlight(change: EntityChange) {
    this.highlights.push(change);
    // 3秒后自动移除高亮
    setTimeout(() => {
      this.highlights = this.highlights.filter(h => h.id !== change.id);
    }, 3000);
  }
}
```

### 10.5 一键引用功能

```typescript
// 前端：快速将图谱信息添加到问答
const QuickQuoteButton = ({ entityId, entityName }) => {
  const addToContext = () => {
    // 将选中的实体信息添加到 AI 助手的上下文
    const entityContext = {
      id: entityId,
      name: entityName,
      timestamp: Date.now(),
      source: 'graphiti'
    };

    // 发送到 AI 助手组件
    eventBus.emit('ai:addContext', entityContext);

    // Toast 提示
    message.success(`已添加 "${entityName}" 到问答上下文`);
  };

  return (
    <Button
      icon={<PlusCircleOutlined />}
      onClick={addToContext}
      size="small"
    >
      添加到问答
    </Button>
  );
};
```

### 11.5 问答图表系统（可扩展）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          问答图表系统 (Q&A Chart System)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   图表渲染器    │  │   图表注册表    │  │   图表编辑器    │             │
│  │  ChartRenderer  │  │  ChartRegistry  │  │  ChartEditor    │             │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤             │
│  │ • ECharts      │  │ • 柱状图       │  │ • 配置生成     │             │
│  │ • AntV G6      │  │ • 折线图       │  │ • 实时预览     │             │
│  │ • Plotly       │  │ • 饼图         │  │ • 代码导出     │             │
│  │ • 自定义渲染   │  │ • 散点图       │  │ • 模板库      │             │
│  │                │  │ • 雷达图       │  │               │             │
│  │                │  │ • 桑基图       │  │               │             │
│  │                │  │ • 力导向图     │  │               │             │
│  │                │  │ • 热力图       │  │               │             │
│  │                │  │ • 地图         │  │               │             │
│  │                │  │ • 关系图谱     │  │               │             │
│  │                │  │ • 自定义图表   │  │               │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 11.5.1 图表类型注册

```typescript
// charts/chart-registry.ts

interface ChartDefinition {
  type: string;                      // 图表类型标识
  name: string;                       // 显示名称
  description: string;               // 描述
  icon: string;                      // 图标
  renderer: ChartRenderer;           // 渲染器类型
  defaultConfig: ChartConfig;       // 默认配置
  dataSchema: DataSchema;            // 数据模式
  capabilities: ChartCapability[];   // 能力列表
}

interface ChartCapability {
  type: 'animation' | 'export' | 'interactive' | 'realtime';
  enabled: boolean;
}

class ChartRegistry {
  private charts: Map<string, ChartDefinition> = new Map();

  register(definition: ChartDefinition): void {
    // 1. 验证定义
    this.validateDefinition(definition);

    // 2. 注册图表
    this.charts.set(definition.type, definition);

    // 3. 发布事件
    eventBus.publish(new ChartRegisteredEvent(definition.type));
  }

  getChart(type: string): ChartDefinition | undefined {
    return this.charts.get(type);
  }

  getAllCharts(): ChartDefinition[] {
    return Array.from(this.charts.values());
  }
}

// 注册内置图表
const registry = new ChartRegistry();

// 内置图表：柱状图
registry.register({
  type: 'bar',
  name: '柱状图',
  description: '用于对比分类数据',
  icon: 'bar-chart',
  renderer: 'echarts',
  defaultConfig: {
    xAxis: { type: 'category' },
    yAxis: { type: 'value' },
    series: [{ type: 'bar' }]
  },
  dataSchema: {
    required: ['categories', 'values'],
    optional: ['series', 'labels']
  },
  capabilities: [
    { type: 'animation', enabled: true },
    { type: 'export', enabled: true },
    { type: 'interactive', enabled: true }
  ]
});

// 内置图表：知识图谱
registry.register({
  type: 'knowledge-graph',
  name: '知识图谱',
  description: '展示实体关系网络',
  icon: 'apartment',
  renderer: 'antv-g6',
  defaultConfig: {
    layout: { type: 'force-directed' },
    nodeSize: 20,
    edgeWidth: 1
  },
  dataSchema: {
    required: ['nodes', 'edges'],
    optional: ['categories', 'weights']
  },
  capabilities: [
    { type: 'animation', enabled: true },
    { type: 'export', enabled: true },
    { type: 'interactive', enabled: true }
  ]
});
```

#### 11.5.2 图表渲染器

```typescript
// charts/chart-renderer.ts

interface ChartRenderer {
  type: string;
  render(container: HTMLElement, config: ChartConfig, data: ChartData): void;
  update(config: ChartConfig, data: ChartData): void;
  resize(): void;
  export(format: 'png' | 'svg' | 'pdf'): Promise<Blob>;
  destroy(): void;
}

class EChartsRenderer implements ChartRenderer {
  type = 'echarts';
  private chart: ECharts.EChartsOption | null = null;

  render(container: HTMLElement, config: ChartConfig, data: ChartData): void {
    this.chart = echarts.init(container);
    this.update(config, data);
  }

  update(config: ChartConfig, data: ChartData): void {
    if (!this.chart) return;

    const option = this.buildOption(config, data);
    this.chart.setOption(option, { notMerge: true });
  }

  private buildOption(config: ChartConfig, data: ChartData): ECharts.EChartsOption {
    // 动态构建 ECharts 配置
    return {
      ...config,
      series: data.series.map(s => ({
        ...config.series?.[0],
        data: s.data
      })),
      xAxis: {
        ...config.xAxis,
        data: data.categories
      }
    };
  }

  export(format: 'png' | 'svg' | 'pdf'): Promise<Blob> {
    return this.chart!.getConnectedDataURL({
      type: format === 'pdf' ? 'png' : format,
      pixelRatio: 2,
      backgroundColor: '#fff'
    });
  }
}

// 自定义图表渲染器注册
ChartRendererFactory.register('echarts', new EChartsRenderer());
ChartRendererFactory.register('antv-g6', new AntVG6Renderer());
ChartRendererFactory.register('plotly', new PlotlyRenderer());
```

#### 11.5.3 会话问答图表展示

```typescript
// components/ChatChart.tsx

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  charts?: ChartRenderRequest[];
  timestamp: Date;
}

const ChatChart: React.FC<{ message: ChatMessage }> = ({ message }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [renderer, setRenderer] = useState<ChartRenderer | null>(null);

  // 加载图表渲染器
  useEffect(() => {
    if (message.charts && message.charts.length > 0) {
      const chartType = message.charts[0].type;
      const definition = chartRegistry.getChart(chartType);

      if (definition) {
        const rendererInstance = ChartRendererFactory.create(definition.renderer);
        setRenderer(rendererInstance);
      }
    }
  }, [message.charts]);

  // 渲染图表
  useEffect(() => {
    if (renderer && chartContainerRef.current && message.charts) {
      renderer.render(
        chartContainerRef.current,
        message.charts[0].config,
        message.charts[0].data
      );
    }

    return () => renderer?.destroy();
  }, [renderer, message.charts]);

  return (
    <Card className="chat-chart-card">
      {message.charts?.map((chart, index) => (
        <div key={index} className="chart-container">
          <div className="chart-header">
            <span className="chart-type">{chart.type}</span>
            <Space>
              <Button size="small" icon={<FullscreenOutlined />}>全屏</Button>
              <Button size="small" icon={<DownloadOutlined />}>导出</Button>
            </Space>
          </div>
          <div ref={chartContainerRef} className="chart-canvas" />
        </div>
      ))}
    </Card>
  );
};
```

---

## 12. 管理后台架构

### 12.1 管理后台定位

管理后台供系统管理员使用，实现**可配置、可扩展、可维护**的管理能力：

| 模块 | 功能 | 核心特性 |
|------|------|----------|
| **角色配置** | 自定义角色、技能绑定、策略关联 | 热生效、版本管理 |
| **本体管理** | 图谱可视化、节点/边编辑、数据导入 | 实时预览、多数据源 |
| **策略管理** | OPA 策略编辑（Markdown → Rego） | 版本历史、差异对比 |
| **规则管理** | 业务规则 CRUD、规则组合、条件链 | 规则测试沙箱 |
| **技能管理** | 技能注册、启用/禁用、依赖管理 | 自动热加载 |
| **数据源管理** | 结构化/非结构化数据源接入 | 数据预览、脱敏配置 |
| **审计日志** | 全链路日志查询、导出、分析 | 多维度筛选 |
| **系统配置** | 分组配置、配置版本、灰度发布 | 变更追踪 |

### 12.2 配置组合架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           配置中心 (Configuration Hub)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        角色 (Role) 配置层                             │   │
│  │                                                                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │   │
│  │  │ 指挥官     │  │ 情报分析员  │  │ 操作员      │  │ 自定义角色  │  │   │
│  │  │ Commander   │  │ Intelligence│  │ Operations  │  │ Custom      │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  │   │
│  │         │                │                │                │         │   │
│  │         ▼                ▼                ▼                ▼         │   │
│  │  ┌─────────────────────────────────────────────────────────────┐       │   │
│  │  │                   技能 (Skill) 绑定                          │       │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │       │   │
│  │  │  │打击技能 │ │分析技能 │ │查询技能 │ │可视化技能│  ...     │       │   │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │       │   │
│  │  └─────────────────────────────────────────────────────────────┘       │   │
│  │                              │                                          │   │
│  │                              ▼                                          │   │
│  │  ┌─────────────────────────────────────────────────────────────┐       │   │
│  │  │                   策略 (Policy) 绑定                         │       │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │       │   │
│  │  │  │授权策略 │ │执行策略 │ │数据策略 │ │审计策略 │  ...     │       │   │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │       │   │
│  │  └─────────────────────────────────────────────────────────────┘       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.3 配置组合数据结构

```python
# models/config_models.py

@dataclass
class Role:
    id: str
    name: str                          # 角色名称
    description: str                   # 角色描述
    base_type: str                     # 基类型: commander/intelligence/operations
    skills: List[str]                 # 绑定技能列表
    policies: List[str]                # 绑定策略列表
    data_sources: List[str]            # 可访问数据源
    priority: int                      # 优先级
    status: str                       # enabled/disabled
    version: str                      # 配置版本
    created_at: datetime
    updated_at: datetime
    created_by: str
    metadata: Dict[str, Any]           # 扩展元数据

@dataclass
class SkillBinding:
    role_id: str
    skill_id: str
    priority: int                      # 同角色内技能优先级
    params: Dict[str, Any]            # 技能参数覆盖
    enabled: bool
    conditions: List[Condition]       # 触发条件

@dataclass
class PolicyBinding:
    role_id: str
    policy_id: str
    effect: str                       # allow/deny
    conditions: List[Condition]       # 生效条件
    priority: int                      # 冲突时优先级

@dataclass
class ConfigurationProfile:
    id: str
    name: str                          # 配置集名称
    description: str
    roles: List[Role]                  # 角色列表
    global_skills: List[str]           # 全局技能
    global_policies: List[str]          # 全局策略
    data_sources: List[DataSource]      # 数据源配置
    is_active: bool                    # 是否激活
    is_default: bool                   # 是否默认配置
    validation_status: str             # 验证状态
```

### 12.4 配置热生效机制

```python
# services/config_hot_reload.py

class ConfigurationHotReload:
    """配置热生效服务"""

    def __init__(self, event_bus: EventBus, cache: Cache):
        self.event_bus = event_bus
        self.cache = cache
        self.subscribers = []

    async def apply_changes(self, change: ConfigChange) -> ApplyResult:
        # 1. 验证配置合法性
        validation = await self.validate_config(change)
        if not validation.is_valid:
            return ApplyResult(success=False, errors=validation.errors)

        # 2. 预览变更影响
        impact = await self.analyze_impact(change)
        if impact.has_critical_changes:
            # 需要审批流程
            await self.request_approval(impact)

        # 3. 生成变更批次
        batch = ChangeBatch.create(change)

        # 4. 原子性应用变更
        async with self.transaction():
            await self.apply_to_database(batch)
            await self.sync_to_cache(batch)
            await self.notify_subscribers(batch)

        # 5. 记录审计日志
        await self.audit_log.record(change)

        return ApplyResult(success=True, batch_id=batch.id)

    async def notify_subscribers(self, batch: ChangeBatch):
        """通知订阅者配置变更"""
        for subscriber in self.subscribers:
            await subscriber.on_config_changed(batch)


class ConfigChangeSubscriber(ABC):
    """配置变更订阅者接口"""

    @abstractmethod
    async def on_config_changed(self, batch: ChangeBatch):
        pass


class SkillHotReload(ConfigChangeSubscriber):
    """技能热加载"""

    async def on_config_changed(self, batch: ChangeBatch):
        for change in batch.changes:
            if change.type == 'skill':
                if change.action == 'enable':
                    await self.skill_registry.enable(change.target_id)
                elif change.action == 'disable':
                    await self.skill_registry.disable(change.target_id)
                elif change.action == 'create':
                    await self.skill_registry.register(
                        change.target_id,
                        change.payload
                    )


class PolicyHotReload(ConfigChangeSubscriber):
    """策略热加载"""

    async def on_config_changed(self, batch: ChangeBatch):
        for change in batch.changes:
            if change.type == 'policy':
                await self.opa_client.reload_policy(change.target_id)
```

### 11.2 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           管理后台 (Admin Dashboard)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   模拟数据      │  │   本体管理      │  │   策略管理      │             │
│  │   管理         │  │                 │  │                 │             │
│  │                 │  │                 │  │                 │             │
│  │ • 事件生成器   │  │ • 节点浏览      │  │ • Markdown 编辑 │             │
│  │ • 事件队列     │  │ • 属性查看      │  │ • Rego 预览     │             │
│  │ • 手工采用     │  │ • 边关系查看    │  │ • 策略启停      │             │
│  │ • 批量导入     │  │ • 溯源日志      │  │ • 版本历史      │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   角色管理      │  │   审计日志      │  │   系统配置      │             │
│  │                 │  │                 │  │                 │             │
│  │ • 角色 CRUD    │  │ • 日志查询      │  │ • 配置分组      │             │
│  │ • Skill 分配   │  │ • 高级筛选      │  │ • 可视化编辑    │             │
│  │ • OPA 策略绑定 │  │ • 导出报表      │  │ • 说明文档      │             │
│  │ • 生效控制     │  │ • 溯源分析      │  │ • 版本对比      │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.3 模拟数据管理

```typescript
// 后端: simulation_controller.py
class SimulationController {
  // 生成模拟事件
  async generateEvents(config: SimulationConfig): Promise<SimulationResult> {
    const events = await this.eventGenerator.generate({
      region: config.region,
      density: config.density,
      types: config.eventTypes,
      timeRange: config.timeRange,
    });

    return {
      eventCount: events.length,
      events: events.map(e => ({
        id: e.id,
        type: e.type,
        description: e.description,
        source: 'simulation',
        timestamp: e.timestamp,
        status: 'pending',  // pending | adopted | rejected
      })),
    };
  }

  // 手工采用模拟事件
  async adoptEvent(eventId: string): Promise<void> {
    const event = await this.getEvent(eventId);

    // 将事件写入 Graphiti
    await this.graphiti.addEpisode({
      name: `Adopted_Simulation_${eventId}`,
      episode_body: event.description,
      source: 'simulation_adopted',
      time_stamp: event.timestamp,
    });

    // 更新事件状态
    event.status = 'adopted';
    await this.eventStore.save(event);
  }
}

// 前端: SimulationDashboard
const SimulationDashboard: React.FC = () => {
  const [events, setEvents] = useState<SimulationEvent[]>([]);
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);

  return (
    <Card title="模拟战场事件">
      <Space direction="vertical" style={{ width: '100%' }}>
        <Row gutter={16}>
          <Col span={8}>
            <Button type="primary" onClick={generateEvents}>
              生成模拟事件
            </Button>
          </Col>
          <Col span={8}>
            <Button
              type="primary"
              disabled={selectedEvents.length === 0}
              onClick={adoptSelected}
            >
              批量采用 ({selectedEvents.length})
            </Button>
          </Col>
        </Row>

        <Table
          dataSource={events}
          rowSelection={{
            selectedRowKeys: selectedEvents,
            onChange: (keys) => setSelectedEvents(keys as string[]),
          }}
          columns={[
            { title: '类型', dataIndex: 'type' },
            { title: '描述', dataIndex: 'description' },
            { title: '时间', dataIndex: 'timestamp' },
            { title: '状态', dataIndex: 'status', render: (s) => <StatusTag>{s}</StatusTag> },
            {
              title: '操作',
              render: (_, record) => (
                <Space>
                  <Button size="small" onClick={() => adoptEvent(record.id)}>采用</Button>
                  <Button size="small" onClick={() => viewDetail(record.id)}>详情</Button>
                </Space>
              ),
            },
          ]}
        />
      </Space>
    </Card>
  );
};
```

### 11.4 本体图谱管理

```typescript
// 前端: OntologyGraphViewer
const OntologyGraphViewer: React.FC = () => {
  const [selectedNode, setSelectedNode] = useState<EntityNode | null>(null);
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });

  // 加载图谱数据
  useEffect(() => {
    loadGraphData().then(setGraphData);
  }, []);

  return (
    <Split horizontal defaultSizes={[300, 700]}>
      {/* 左侧：节点列表 */}
      <div>
        <Tree
          treeData={buildEntityTree(graphData.nodes)}
          onSelect={(keys) => {
            const node = graphData.nodes.find(n => n.id === keys[0]);
            setSelectedNode(node);
          }}
        />
      </div>

      {/* 中间：图谱可视化 */}
      <div>
        <AntVGraph
          data={graphData}
          onNodeClick={(node) => setSelectedNode(node.data)}
          layout="force"
          animate
        />
      </div>

      {/* 右侧：属性面板 */}
      <div>
        {selectedNode ? (
          <EntityDetailPanel
            entity={selectedNode}
            onUpdate={handleEntityUpdate}
          />
        ) : (
          <Empty description="请选择节点查看详情" />
        )}
      </div>
    </Split>
  );
};

// 本体溯源日志展示
const TraceLogPanel: React.FC<{ entityId: string }> = ({ entityId }) => {
  const [logs, setLogs] = useState<TraceLog[]>([]);

  useEffect(() => {
    loadTraceLogs(entityId).then(setLogs);
  }, [entityId]);

  return (
    <Timeline mode="left">
      {logs.map((log) => (
        <Timeline.Item
          key={log.id}
          color={log.type === 'external' ? 'blue' : 'green'}
          label={formatTime(log.timestamp)}
        >
          <Card size="small">
            <Space>
              <Tag>{log.type}</Tag>
              <Text strong>{log.description}</Text>
            </Space>
            {log.source && (
              <div>
                <Text type="secondary">来源: {log.source}</Text>
              </div>
            )}
          </Card>
        </Timeline.Item>
      ))}
    </Timeline>
  );
};
```

### 11.5 OPA 策略管理（Markdown → Rego）

```typescript
// 后端: policy_controller.py
class PolicyController {
  // Markdown 转 Rego
  async markdownToRego(markdown: string): Promise<string> {
    return this.markdownConverter.convert(markdown);
  }

  // 保存策略
  async savePolicy(policy: Policy): Promise<void> {
    // 1. Markdown 转 Rego
    const rego = await this.markdownToRego(policy.markdown);

    // 2. 语法验证
    const validation = await this.opa.validate(rego);
    if (!validation.valid) {
      throw new PolicyValidationError(validation.errors);
    }

    // 3. 保存到文件系统
    await this.policyStore.save(policy.name, {
      markdown: policy.markdown,
      rego: rego,
      version: Date.now(),
      status: policy.status,  // draft | enabled | disabled
    });

    // 4. 如果启用，热更新 OPA
    if (policy.status === 'enabled') {
      await this.opa.reloadPolicies();
    }
  }

  // 手动/自动生效控制
  async setPolicyStatus(policyId: string, status: 'enabled' | 'disabled'): Promise<void> {
    await this.policyStore.updateStatus(policyId, status);

    if (status === 'enabled') {
      await this.opa.reloadPolicies();
    }
  }
}

// Markdown 策略示例
const markdownPolicy = `
# 打击权限策略

## 基本规则

允许条件：
1. 操作用户具有 commander 角色
2. 目标不在保护名单中（民用、医疗、历史遗迹）
3. 武器参数满足要求

## Rego 转换输出

\`\`\`rego
package policies.attack

allow if {
    input.action == "attack_target"
    input.commander_id != ""
    not is_protected_target(input.target)
}

is_protected_target(target) if {
    target.category == "civilian"
}
\`\`\`
`;
```

---

## 13. 本体管理层

### 12.1 本体定位

本体（Ontology）是系统的"词汇表"，定义了战场上所有实体、关系和属性。本体作为统一的语义层，支撑 Graphiti 图谱和前端展示。

### 12.2 战争实体定义（中英文）

```typescript
// ontology/entities.ts

export const BATTLEFIELD_ONTOLOGY = {
  // ===== 作战单位 =====
  Unit: {
    name: { zh: '作战单位', en: 'Unit' },
    description: '执行作战任务的军事单位',
    attributes: {
      unit_id: { zh: '单位ID', en: 'Unit ID', type: 'string', required: true },
      unit_type: {
        zh: '单位类型',
        en: 'Unit Type',
        type: 'enum',
        values: ['infantry', 'armor', 'aviation', 'naval', 'electronic_warfare'],
        required: true
      },
      affiliation: {
        zh: '所属方',
        en: 'Affiliation',
        type: 'enum',
        values: ['friendly', 'enemy', 'neutral', 'unknown'],
        required: true
      },
      status: {
        zh: '状态',
        en: 'Status',
        type: 'enum',
        values: ['active', 'deployed', 'damaged', 'destroyed', 'retreating'],
        required: true
      },
      position: {
        zh: '位置坐标',
        en: 'Position',
        type: 'object',
        properties: { lat: 'number', lon: 'number', altitude: 'number' }
      },
      combat_capability: {
        zh: '作战能力指数',
        en: 'Combat Capability',
        type: 'number',
        range: [0, 100]
      },
    },
  },

  // ===== 打击目标 =====
  Target: {
    name: { zh: '打击目标', en: 'Target' },
    description: '需要监视或打击的目标实体',
    attributes: {
      target_id: { zh: '目标ID', en: 'Target ID', type: 'string', required: true },
      target_type: {
        zh: '目标类型',
        en: 'Target Type',
        type: 'enum',
        values: ['radar', 'command_center', 'supply_depot', 'missile_launcher', 'air_defense', 'communications'],
        required: true
      },
      threat_level: {
        zh: '威胁等级',
        en: 'Threat Level',
        type: 'enum',
        values: ['critical', 'high', 'medium', 'low']
      },
      location: { zh: '位置坐标', en: 'Location', type: 'object' },
      status: { zh: '状态', en: 'Status', type: 'enum', values: ['active', 'destroyed', 'unknown'] },
      protected: { zh: '受保护', en: 'Protected', type: 'boolean', default: false },
    },
  },

  // ===== 情报报告 =====
  IntelligenceReport: {
    name: { zh: '情报报告', en: 'Intelligence Report' },
    description: '来自各种传感器的情报数据',
    attributes: {
      report_id: { zh: '报告ID', en: 'Report ID', type: 'string' },
      source: {
        zh: '来源',
        en: 'Source',
        type: 'enum',
        values: ['satellite', 'drone', 'radar', 'human', 'sigint', 'document']
      },
      confidence: { zh: '置信度', en: 'Confidence', type: 'number', range: [0, 1] },
      detected_at: { zh: '发现时间', en: 'Detected At', type: 'datetime' },
      content: { zh: '内容摘要', en: 'Content', type: 'string' },
      attached_files: { zh: '附件', en: 'Attached Files', type: 'array' },
    },
  },

  // ===== 打击命令 =====
  StrikeOrder: {
    name: { zh: '打击命令', en: 'Strike Order' },
    description: '下达的打击执行命令',
    attributes: {
      order_id: { zh: '命令ID', en: 'Order ID', type: 'string' },
      target_id: { zh: '目标ID', en: 'Target ID', type: 'string' },
      weapon_type: { zh: '武器类型', en: 'Weapon Type', type: 'enum' },
      issued_by: { zh: '签发人', en: 'Issued By', type: 'string' },
      status: {
        zh: '执行状态',
        en: 'Status',
        type: 'enum',
        values: ['pending', 'approved', 'executed', 'failed', 'cancelled']
      },
      executed_at: { zh: '执行时间', en: 'Executed At', type: 'datetime' },
      result: { zh: '执行结果', en: 'Result', type: 'string' },
    },
  },

  // ===== 武器装备 =====
  Weapon: {
    name: { zh: '武器装备', en: 'Weapon' },
    description: '可用于打击的武器系统',
    attributes: {
      weapon_id: { zh: '装备ID', en: 'Weapon ID', type: 'string' },
      weapon_type: { zh: '武器类型', en: 'Type', type: 'enum' },
      effective_range: { zh: '有效射程(km)', en: 'Effective Range', type: 'number' },
      yield: { zh: '当量', en: 'Yield', type: 'number' },
      status: { zh: '状态', en: 'Status', type: 'enum' },
      carrier_unit: { zh: '搭载单位', en: 'Carrier Unit', type: 'string' },
    },
  },

  // ===== 保护区域 =====
  ProtectedZone: {
    name: { zh: '保护区域', en: 'Protected Zone' },
    description: '禁止攻击的保护性区域或目标',
    attributes: {
      zone_id: { zh: '区域ID', en: 'Zone ID', type: 'string' },
      zone_type: {
        zh: '区域类型',
        en: 'Zone Type',
        type: 'enum',
        values: ['civilian', 'medical', 'historical', 'diplomatic', 'neutral']
      },
      boundary: { zh: '边界坐标', en: 'Boundary', type: 'array' },
      description: { zh: '描述', en: 'Description', type: 'string' },
    },
  },
};
```

### 12.3 关系类型定义

```typescript
export const BATTLEFIELD_RELATIONS = {
  // 单位间关系
  'Unit - [:DEPLOYED_TO]-> Target': {
    zh: '单位部署到目标区域',
    en: 'Unit deployed to target area',
  },
  'Unit - [:BELONGS_TO]-> Unit': {
    zh: '单位隶属关系',
    en: 'Unit affiliation',
  },
  'Unit - [:COMMANDED_BY]-> Unit': {
    zh: '指挥关系',
    en: 'Command relationship',
  },

  // 情报关系
  'IntelligenceReport - [:DETECTED]-> Target': {
    zh: '情报发现目标',
    en: 'Intelligence detected target',
  },
  'IntelligenceReport - [:EVIDENCE_FOR]-> StrikeOrder': {
    zh: '情报为打击命令提供依据',
    en: 'Intelligence provides evidence for strike order',
  },

  // 打击关系
  'StrikeOrder - [:TARGETS]-> Target': {
    zh: '打击命令指向目标',
    en: 'Strike order targets',
  },
  'Weapon - [:MOUNTED_ON]-> Unit': {
    zh: '武器挂载在单位上',
    en: 'Weapon mounted on unit',
  },

  // 保护关系
  'Target - [:LOCATED_IN]-> ProtectedZone': {
    zh: '目标位于保护区域内',
    en: 'Target located in protected zone',
  },
};
```

### 12.3 多数据源接入架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          多数据源接入层 (Multi-Source Adapter)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   结构化数据源   │  │  非结构化数据源   │  │   实时数据源     │             │
│  │  Structured     │  │  Unstructured    │  │  Real-time      │             │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤             │
│  │ • PostgreSQL    │  │ • PDF 文档      │  │ • WebSocket     │             │
│  │ • MySQL         │  │ • 图像/视频     │  │ • Kafka         │             │
│  │ • MongoDB       │  │ • 语音转文本    │  │ • MQTT          │             │
│  │ • Elasticsearch │  │ • 网页爬虫     │  │ • Redis PubSub  │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
│           │                      │                      │                       │
│           ▼                      ▼                      ▼                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      统一数据抽象层 (Data Abstraction)                 │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │   │
│  │  │  DataEntity  │  │ DataDocument │  │ DataStream   │            │   │
│  │  │  结构化实体  │  │ 非结构化文档 │  │ 实时数据流   │            │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘            │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      本体映射层 (Ontology Mapping)                    │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │   │
│  │  │  FieldMapper  │  │ ParserMapper │  │ StreamMapper │            │   │
│  │  │  字段映射     │  │ 解析器映射   │  │ 流映射       │            │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘            │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Graphiti 图谱 (知识融合)                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.4 数据源配置模型

```python
# models/data_source.py

@dataclass
class DataSource:
    id: str
    name: str                          # 数据源名称
    source_type: DataSourceType        # 数据源类型
    connection_config: Dict[str, Any]  # 连接配置
    ontology_mapping: OntologyMapping  # 本体映射规则
    status: str                       # active/inactive/error
    refresh_interval: int             # 刷新间隔(秒)
    credential_id: str               # 凭证ID(加密存储)
    created_at: datetime
    updated_at: datetime


class DataSourceType(Enum):
    # 结构化数据源
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    ELASTICSEARCH = "elasticsearch"

    # 非结构化数据源
    PDF_DOCUMENT = "pdf_document"
    IMAGE_ARCHIVE = "image_archive"
    VIDEO_ARCHIVE = "video_archive"
    WEB_CRAWLER = "web_crawler"
    VOICE_TRANSCRIPT = "voice_transcript"

    # 实时数据源
    WEBSOCKET = "websocket"
    KAFKA = "kafka"
    MQTT = "mqtt"
    REDIS_PUBSUB = "redis_pubsub"


@dataclass
class OntologyMapping:
    """本体映射配置"""
    source_entity_type: str           # 源数据类型
    target_ontology_class: str        # 目标本体类
    field_mappings: List[FieldMapping]  # 字段映射
    transformation_rules: List[str]    # 转换规则
    filter_conditions: List[str]      # 过滤条件


@dataclass
class FieldMapping:
    source_field: str                 # 源字段
    target_field: str                 # 目标字段
    transform_type: TransformType     # 转换类型
    transform_params: Dict[str, Any]  # 转换参数
```

### 12.5 数据接入处理器

```python
# services/data_ingestion.py

class DataIngestionService:
    """数据接入服务"""

    def __init__(
        self,
        source_adapters: Dict[DataSourceType, DataSourceAdapter],
        ontology_mapper: OntologyMapper,
        graphiti_client: GraphitiClient,
    ):
        self.source_adapters = source_adapters
        self.ontology_mapper = ontology_mapper
        self.graphiti_client = graphiti_client

    async def ingest(self, data_source: DataSource, data: Any) -> IngestionResult:
        # 1. 数据解析 - 适配器统一化
        adapter = self.source_adapters[data_source.source_type]
        parsed_data = await adapter.parse(data)

        # 2. 本体映射 - 转换为图谱实体
        entities = await self.ontology_mapper.map(
            parsed_data,
            data_source.ontology_mapping
        )

        # 3. 图谱写入
        for entity in entities:
            await self.graphiti_client.add_entity(entity)

        # 4. 审计记录
        await self.audit_log.record_ingestion(
            source=data_source.id,
            record_count=len(entities)
        )

        return IngestionResult(success=True, count=len(entities))


class DataSourceAdapter(ABC):
    """数据源适配器基类"""

    @abstractmethod
    async def parse(self, raw_data: Any) -> ParsedData:
        """解析原始数据为统一格式"""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """测试数据源连接"""
        pass


class StructuredDataAdapter(DataSourceAdapter):
    """结构化数据适配器"""

    async def parse(self, raw_data: Any) -> ParsedData:
        # 保持原始结构
        return ParsedData(
            data_type=DataType.STRUCTURED,
            records=raw_data if isinstance(raw_data, list) else [raw_data],
            schema=self.extract_schema(raw_data)
        )


class PDFDocumentAdapter(DataSourceAdapter):
    """PDF 文档适配器"""

    def __init__(self, ocr_service: OCRService, llm_extractor: LLMExtractor):
        self.ocr_service = ocr_service
        self.llm_extractor = llm_extractor

    async def parse(self, raw_data: bytes) -> ParsedData:
        # 1. OCR 提取文本
        text = await self.ocr_service.extract(raw_data)

        # 2. LLM 抽取结构化信息
        structured = await self.llm_extractor.extract(
            text,
            extraction_schema=self.get_schema()
        )

        return ParsedData(
            data_type=DataType.DOCUMENT,
            raw_text=text,
            entities=structured,
            metadata={'source': 'pdf', 'page_count': self.get_page_count(raw_data)}
        )


class KafkaStreamAdapter(DataSourceAdapter):
    """Kafka 流数据适配器"""

    def __init__(self, kafka_config: KafkaConfig):
        self.consumer = AIOKafkaConsumer(**kafka_config)

    async def parse(self, raw_data: ConsumerRecord) -> ParsedData:
        return ParsedData(
            data_type=DataType.STREAM,
            records=[{
                'topic': raw_data.topic,
                'partition': raw_data.partition,
                'offset': raw_data.offset,
                'timestamp': raw_data.timestamp,
                'value': json.loads(raw_data.value)
            }],
            metadata={'kafka_topic': raw_data.topic}
        )
```

### 12.6 技能自动注册机制

```python
# services/skill_registry.py

class SkillRegistry:
    """技能注册表 - 支持热插拔"""

    def __init__(self, config_store: ConfigStore):
        self.config_store = config_store
        self.skills: Dict[str, SkillMetadata] = {}
        self.enabled_skills: Set[str] = set()

    async def register(self, skill_id: str, skill_config: SkillConfig):
        """注册新技能 - 立即生效"""
        # 1. 验证技能配置
        await self.validate_skill(skill_config)

        # 2. 加载技能模块
        module = await self.load_skill_module(skill_config)

        # 3. 注册到运行时
        self.skills[skill_id] = SkillMetadata(
            id=skill_id,
            module=module,
            config=skill_config,
            registered_at=datetime.now(),
            status='registered'
        )

        # 4. 如果启用则激活
        if skill_config.enabled:
            await self.enable(skill_id)

        # 5. 持久化注册信息
        await self.config_store.save_skill_registration(skill_id, skill_config)

        # 6. 发布注册事件
        await self.event_bus.publish(SkillRegisteredEvent(skill_id))

    async def enable(self, skill_id: str):
        """启用技能 - 立即生效"""
        if skill_id not in self.skills:
            raise SkillNotFoundError(skill_id)

        skill = self.skills[skill_id]

        # 重新加载模块
        await self.reload_skill_module(skill_id)

        self.enabled_skills.add(skill_id)
        skill.status = 'enabled'

        # 通知 Agent 系统
        await self.notify_agent_system(skill_id, enabled=True)

        await self.event_bus.publish(SkillEnabledEvent(skill_id))

    async def disable(self, skill_id: str):
        """禁用技能 - 立即生效"""
        if skill_id in self.enabled_skills:
            self.enabled_skills.remove(skill_id)

        self.skills[skill_id].status = 'disabled'

        # 通知 Agent 系统
        await self.notify_agent_system(skill_id, enabled=False)

        await self.event_bus.publish(SkillDisabledEvent(skill_id))

    def get_enabled_skills(self) -> List[SkillMetadata]:
        """获取所有启用的技能"""
        return [self.skills[sid] for sid in self.enabled_skills]
```

### 12.7 规则引擎集成

```python
# services/rule_engine.py

class RuleEngine:
    """规则引擎 - 支持规则组合"""

    def __init__(
        self,
        rule_repository: RuleRepository,
        condition_evaluator: ConditionEvaluator,
    ):
        self.rule_repository = rule_repository
        self.condition_evaluator = condition_evaluator

    async def evaluate(
        self,
        context: EvaluationContext,
        rule_group_id: str
    ) -> EvaluationResult:
        """评估规则组"""
        rules = await self.rule_repository.get_by_group(rule_group_id)
        results = []

        for rule in sorted(rules, key=lambda r: r.priority):
            # 评估条件
            if await self.condition_evaluator.evaluate(rule.conditions, context):
                # 执行动作
                action_result = await self.execute_action(rule.action, context)
                results.append(RuleResult(rule_id=rule.id, executed=True, result=action_result))

                # 如果规则指定为独占执行，则跳出
                if rule.exclusive:
                    break
            else:
                results.append(RuleResult(rule_id=rule.id, executed=False))

        return EvaluationResult(results=results)

    async def create_rule(self, rule_config: RuleConfig) -> Rule:
        """创建规则"""
        # 1. 验证规则语法
        await self.validate_rule_syntax(rule_config)

        # 2. 编译条件表达式
        compiled_conditions = await self.compile_conditions(rule_config.conditions)

        # 3. 保存规则
        rule = Rule(
            id=self.generate_id(),
            name=rule_config.name,
            group_id=rule_config.group_id,
            conditions=compiled_conditions,
            action=rule_config.action,
            priority=rule_config.priority,
            enabled=True,
        )
        await self.rule_repository.save(rule)

        # 4. 通知规则引擎重载
        await self.reload_rules()

        return rule


@dataclass
class Rule:
    id: str
    name: str
    group_id: str                    # 规则组
    conditions: CompiledConditions    # 编译后的条件
    action: RuleAction               # 执行动作
    priority: int                     # 优先级(越小越先)
    exclusive: bool                  # 独占执行
    enabled: bool
    version: str
    created_at: datetime


### 13.1 角色定义

```typescript
// roles/definitions.ts

export const SYSTEM_ROLES = {
  // ===== 操作角色 =====
  commander: {
    name: { zh: '指挥官', en: 'Commander' },
    description: '战场最高决策者，有权下达打击命令',
    permissions: {
      skills: ['*'],  // 所有技能权限
      targets: ['*'],  // 可操作所有目标
      strike_approval: true,  // 可批准打击
      ooda_phases: ['observe', 'orient', 'decide', 'act'],
    },
    required_conditions: {
      min_rank: 'colonel',
      security_clearance: 4,
    },
  },

  intelligence_officer: {
    name: { zh: '情报分析员', en: 'Intelligence Officer' },
    description: '负责情报收集、分析和威胁评估',
    permissions: {
      skills: ['radar_search', 'drone_surveillance', 'threat_assessment', 'pattern_match'],
      targets: ['*'],
      strike_approval: false,
      ooda_phases: ['observe', 'orient'],
    },
  },

  operator: {
    name: { zh: '操作员', en: 'Operator' },
    description: '执行具体操作命令',
    permissions: {
      skills: ['command_unit', 'route_planning'],
      targets: ['unrestricted'],
      strike_approval: false,
      ooda_phases: ['act'],
    },
  },

  // ===== 管理角色 =====
  admin: {
    name: { zh: '系统管理员', en: 'Administrator' },
    description: '系统配置和本体管理',
    permissions: {
      simulation_control: true,
      ontology_edit: true,
      policy_edit: true,
      role_manage: true,
      audit_view: true,
    },
  },

  auditor: {
    name: { zh: '审计员', en: 'Auditor' },
    description: '查看审计日志，但不能操作',
    permissions: {
      simulation_control: false,
      ontology_edit: false,
      policy_edit: false,
      role_manage: false,
      audit_view: true,
    },
  },
};
```

### 13.2 角色管理接口

```typescript
// 后端: role_controller.py
class RoleController {
  // 角色 CRUD
  async createRole(role: RoleCreate): Promise<Role>;
  async getRole(roleId: string): Promise<Role>;
  async updateRole(roleId: string, updates: RoleUpdate): Promise<Role>;
  async deleteRole(roleId: string): Promise<void>;

  // 角色 Skill 分配
  async assignSkills(roleId: string, skillIds: string[]): Promise<void>;
  async getRoleSkills(roleId: string): Promise<Skill[]>;

  // 角色 OPA 策略绑定
  async bindPolicies(roleId: string, policyIds: string[]): Promise<void>;
  async getRolePolicies(roleId: string): Promise<Policy[]>;

  // 修改生效控制
  async applyRoleChanges(roleId: string): Promise<void>;
  // 或设置为自动应用
  async setAutoApply(roleId: string, enabled: boolean): Promise<void>;
}

// 前端: RoleManagement
const RoleManagement: React.FC = () => {
  const [roles, setRoles] = useState<Role[]>([]);
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);

  return (
    <Card>
      <Table dataSource={roles} rowKey="id">
        <Column title="角色名" dataIndex={['name', 'zh']} />
        <Column title="描述" dataIndex={['description']} />
        <Column
          title="操作"
          render={(_, record) => (
            <Space>
              <Button onClick={() => setSelectedRole(record)}>编辑</Button>
              <Button onClick={() => applyChanges(record.id)}>应用修改</Button>
              <Switch
                checked={record.auto_apply}
                onChange={(checked) => setAutoApply(record.id, checked)}
              />
              <Text type="secondary">自动应用</Text>
            </Space>
          )}
        />
      </Table>

      {selectedRole && (
        <RoleEditDrawer
          role={selectedRole}
          onSave={handleSave}
          onClose={() => setSelectedRole(null)}
        />
      )}
    </Card>
  );
};
```

---

## 15. 审计日志系统

### 14.1 审计日志定位

审计日志是系统的"执法记录仪"，记录所有操作和事件，为合规、追溯和复盘提供依据。

### 14.2 审计事件类型

```typescript
// audit/event_types.ts

export const AUDIT_EVENT_TYPES = {
  // ===== 用户操作 =====
  USER_LOGIN: { zh: '用户登录', en: 'User Login', category: 'auth' },
  USER_LOGOUT: { zh: '用户登出', en: 'User Logout', category: 'auth' },
  USER_ACTION: { zh: '用户操作', en: 'User Action', category: 'user' },

  // ===== Agent 操作 =====
  AGENT_INVOKE: { zh: 'Agent 调用', en: 'Agent Invoke', category: 'agent' },
  AGENT_DECISION: { zh: 'Agent 决策', en: 'Agent Decision', category: 'agent' },
  AGENT_TOOL_CALL: { zh: 'Agent 工具调用', en: 'Agent Tool Call', category: 'agent' },

  // ===== 系统自动 =====
  SYSTEM_EVENT: { zh: '系统事件', en: 'System Event', category: 'system' },
  SIMULATION_ADOPT: { zh: '模拟数据采用', en: 'Simulation Adopted', category: 'system' },
  GRAPHITI_UPDATE: { zh: '图谱更新', en: 'Graphiti Update', category: 'system' },

  // ===== OPA 操作 =====
  OPA_CHECK_PASS: { zh: 'OPA 校验通过', en: 'OPA Check Passed', category: 'security' },
  OPA_CHECK_DENY: { zh: 'OPA 校验拒绝', en: 'OPA Check Denied', category: 'security' },
  POLICY_UPDATE: { zh: '策略更新', en: 'Policy Updated', category: 'security' },

  // ===== 高危操作 =====
  STRIKE_ORDER_ISSUED: { zh: '打击命令下达', en: 'Strike Order Issued', category: 'critical' },
  STRIKE_ORDER_EXECUTED: { zh: '打击命令执行', en: 'Strike Order Executed', category: 'critical' },
  STRIKE_ORDER_CANCELLED: { zh: '打击命令取消', en: 'Strike Order Cancelled', category: 'critical' },
};

// 审计日志数据结构
interface AuditLog {
  id: string;
  timestamp: Date;
  event_type: AuditEventType;
  actor: {
    type: 'user' | 'agent' | 'system';
    id: string;
    name: string;
    role?: string;
  };
  action: string;
  target?: {
    type: string;
    id: string;
    name?: string;
  };
  context: {
    ip?: string;
    user_agent?: string;
    session_id?: string;
  };
  result: 'success' | 'failure';
  details: Record<string, any>;
  ooda_phase?: 'observe' | 'orient' | 'decide' | 'act';
}
```

### 14.3 审计日志后端实现

```typescript
// backend/audit_service.py
class AuditService {
  constructor(
    private db: Database,
    private eventEmitter: EventEmitter,
  ) {
    // 监听所有关键事件
    this.setupEventListeners();
  }

  private setupEventListeners() {
    // Agent 调用
    this.eventEmitter.on('agent:invoke', (data) => {
      this.log({
        event_type: 'AGENT_INVOKE',
        actor: { type: 'agent', ...data.agent },
        action: data.task,
        details: { input: data.input },
      });
    });

    // OPA 校验
    this.eventEmitter.on('opa:check', (data) => {
      this.log({
        event_type: data.allowed ? 'OPA_CHECK_PASS' : 'OPA_CHECK_DENY',
        actor: data.actor,
        action: data.action,
        result: data.allowed ? 'success' : 'failure',
        details: { reason: data.reason },
      });
    });

    // 打击命令
    this.eventEmitter.on('strike:issued', (data) => {
      this.log({
        event_type: 'STRIKE_ORDER_ISSUED',
        actor: data.commander,
        action: '下达打击命令',
        target: data.target,
        ooda_phase: 'act',
        details: { order_id: data.order_id },
      });
    });
  }

  async log(event: AuditLogInput): Promise<void> {
    // 写入数据库
    await this.db.audit_logs.insert(event);

    // 实时推送（可选）
    this.eventEmitter.emit('audit:new', event);
  }

  // 查询接口
  async query(filters: AuditQueryFilters): Promise<AuditLog[]> {
    return this.db.audit_logs.find({
      where: filters,
      order_by: [{ timestamp: 'DESC' }],
      limit: filters.limit || 100,
    });
  }
}
```

### 14.4 前端审计日志展示

```typescript
// frontend: AuditLogViewer
const AuditLogViewer: React.FC = () => {
  const [filters, setFilters] = useState<AuditFilters>({
    dateRange: [dayjs().subtract(7, 'day'), dayjs()],
    eventTypes: [],
    actorType: undefined,
  });
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);

  const loadLogs = async () => {
    setLoading(true);
    const result = await auditService.query(filters);
    setLogs(result);
    setLoading(false);
  };

  return (
    <Card>
      <FilterPanel filters={filters} onChange={setFilters} />

      <Table
        dataSource={logs}
        loading={loading}
        pagination={{ pageSize: 50 }}
      >
        <Column title="时间" dataIndex="timestamp" render={(t) => formatTime(t)} />
        <Column
          title="类型"
          dataIndex={['event_type', 'zh']}
          render={(t, record) => (
            <Tag color={getCategoryColor(record.event_type.category)}>{t}</Tag>
          )}
        />
        <Column
          title="执行者"
          render={(_, record) => (
            <Space>
              <Avatar size="small" type={record.actor.type} />
              <Text>{record.actor.name}</Text>
              {record.actor.role && <Tag>{record.actor.role}</Tag>}
            </Space>
          )}
        />
        <Column title="操作" dataIndex="action" />
        <Column
          title="结果"
          dataIndex="result"
          render={(r) => <Badge status={r === 'success' ? 'success' : 'error'} />}
        />
        <Column
          title="操作"
          render={(_, record) => (
            <Button size="small" onClick={() => viewDetail(record)}>
              详情
            </Button>
          )}
        />
      </Table>

      {/* 导出功能 */}
      <ExportMenu onExport={(format) => exportLogs(filters, format)} />
    </Card>
  );
};
```

---

## 16. 配置中心

### 16.1 配置分层

```
配置中心
├── 系统配置
│   ├── 数据库配置
│   ├── 缓存配置
│   └── 日志配置
├── LLM 配置
│   ├── 模型选择
│   ├── API 密钥
│   └── 温度参数
├── Graphiti 配置
│   ├── Neo4j 连接
│   └── 向量索引
├── OPA 配置
│   ├── 服务地址
│   └── Bundle URL
├── Skill 配置
│   ├── 启用列表
│   └── 参数配置
├── 前端配置
│   ├── 主题
│   └── WebSocket URL
└── 多模态配置
    ├── OCR 模型
    ├── 图像识别模型
    └── 文档解析配置
```

### 16.2 配置模型

```typescript
// config/config_model.ts

export interface ConfigGroup {
  id: string;
  name: { zh: string; en: string };
  description: { zh: string; en: string };
  icon: string;
  configs: ConfigItem[];
}

export interface ConfigItem {
  key: string;              // 配置键
  name: { zh: string; en: string };
  description: { zh: string; en: string };
  type: 'string' | 'number' | 'boolean' | 'select' | 'json' | 'secret';
  default?: any;
  value?: any;
  options?: { label: string; value: any }[];  // for select type
  validation?: {
    pattern?: string;
    min?: number;
    max?: number;
    required?: boolean;
  };
  secret?: boolean;  // 是否加密存储
}

export const CONFIG_GROUPS: ConfigGroup[] = [
  {
    id: 'llm',
    name: { zh: '大模型配置', en: 'LLM Configuration' },
    description: { zh: '配置 LLM 模型和 API', en: 'Configure LLM models and APIs' },
    icon: 'robot',
    configs: [
      {
        key: 'llm.provider',
        name: { zh: '模型提供商', en: 'Provider' },
        description: { zh: '选择 LLM 提供商', en: 'Select LLM provider' },
        type: 'select',
        options: [
          { label: 'OpenAI', value: 'openai' },
          { label: 'Anthropic', value: 'anthropic' },
          { label: 'DeepSeek', value: 'deepseek' },
        ],
      },
      {
        key: 'llm.commander_model',
        name: { zh: 'Commander 模型', en: 'Commander Model' },
        description: { zh: 'Commander Agent 使用的模型', en: 'Model for Commander Agent' },
        type: 'select',
        options: [
          { label: 'GPT-4', value: 'gpt-4' },
          { label: 'Claude-3.5 Sonnet', value: 'claude-3-5-sonnet' },
        ],
      },
      {
        key: 'llm.api_key',
        name: { zh: 'API 密钥', en: 'API Key' },
        description: { zh: 'LLM 提供商的 API 密钥', en: 'LLM provider API key' },
        type: 'secret',
        secret: true,
      },
    ],
  },
  {
    id: 'multimodal',
    name: { zh: '多模态配置', en: 'Multimodal Configuration' },
    description: { zh: '配置多模态处理模型', en: 'Configure multimodal processing models' },
    icon: 'scan',
    configs: [
      {
        key: 'multimodal.ocr_enabled',
        name: { zh: '启用 OCR', en: 'Enable OCR' },
        description: { zh: '是否启用文档 OCR 识别', en: 'Enable document OCR' },
        type: 'boolean',
        default: true,
      },
      {
        key: 'multimodal.ocr_model',
        name: { zh: 'OCR 模型', en: 'OCR Model' },
        description: { zh: 'OCR 使用的模型', en: 'Model for OCR' },
        type: 'select',
        options: [
          { label: 'EasyOCR', value: 'easyocr' },
          { label: 'PaddleOCR', value: 'paddleocr' },
        ],
      },
      {
        key: 'multimodal.vision_model',
        name: { zh: '图像识别模型', en: 'Vision Model' },
        description: { zh: '图像分析的模型', en: 'Model for image analysis' },
        type: 'select',
        options: [
          { label: 'GPT-4V', value: 'gpt-4v' },
          { label: 'Claude Vision', value: 'claude-vision' },
        ],
      },
    ],
  },
];
```

### 16.3 前端配置界面

```typescript
// frontend: ConfigCenter
const ConfigCenter: React.FC = () => {
  const [activeGroup, setActiveGroup] = useState('llm');
  const [configs, setConfigs] = useState<Record<string, any>>({});
  const [saving, setSaving] = useState(false);

  const activeGroupData = CONFIG_GROUPS.find((g) => g.id === activeGroup);

  return (
    <Split horizontal defaultSizes={[200, '1fr']}>
      {/* 左侧：分组列表 */}
      <Menu
        mode="vertical"
        selectedKeys={[activeGroup]}
        onClick={({ key }) => setActiveGroup(key)}
        items={CONFIG_GROUPS.map((g) => ({
          key: g.id,
          icon: <Icon name={g.icon} />,
          label: g.name.zh,
        }))}
      />

      {/* 右侧：配置项 */}
      <Card title={activeGroupData?.name.zh}>
        <Descriptions column={1} bordered>
          {activeGroupData?.configs.map((config) => (
            <Descriptions.Item
              key={config.key}
              label={
                <Space direction="vertical" size={0}>
                  <Text strong>{config.name.zh}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {config.description.zh}
                  </Text>
                </Space>
              }
            >
              <ConfigInput config={config} value={configs[config.key]} />
            </Descriptions.Item>
          ))}
        </Descriptions>

        <Space style={{ marginTop: 16 }}>
          <Button type="primary" loading={saving} onClick={handleSave}>
            保存配置
          </Button>
          <Button onClick={handleReset}>重置</Button>
        </Space>
      </Card>
    </Split>
  );
};
```

---



### A. 文件结构

```
graphiti-battlefield/
├── core/
│   ├── openharness_bridge.py      # OpenHarness 桥接适配器
│   ├── opa_client.py              # OPA 客户端
│   ├── graphiti_client.py         # Graphiti 客户端
│   └── swarm_orchestrator.py     # Swarm 编排器
├── skills/                        # Python Skills（领域工具）
│   ├── intelligence/              # 情报类 Skills
│   ├── operations/               # 作战类 Skills
│   ├── analysis/                 # 分析类 Skills
│   └── visualization/            # 可视化类 Skills
├── policies/                      # OPA 策略
│   ├── attack/
│   ├── intelligence/
│   └── common/
├── graphiti/                      # Graphiti 配置
│   ├── nodes/                    # 节点类型定义
│   └── edges/                    # 边类型定义
├── ui/                           # 前端界面
│   └── battlefield_dashboard/
├── docker/
│   ├── opa/
│   └── neo4j/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/
│   ├── ARCHITECTURE.md
│   └── adr/
├── pyproject.toml
├── .openharness/
│   └── config.yaml
└── README.md
```

### B. 环境变量

```bash
# OpenAI / Anthropic
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...

# OPA
OPA_URL=http://localhost:8181

# OpenHarness
OH_MODEL=claude-3-5-sonnet
OH_PERMISSION_MODE=default
```

### C. API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/mission` | POST | 创建任务（触发 OODA） |
| `/api/v1/mission/{id}` | GET | 获取任务状态 |
| `/api/v1/mission/{id}/stream` | GET | SSE 流式响应 |
| `/api/v1/confirm` | POST | 人工确认接口 |
| `/api/v1/graphiti/query` | POST | Graphiti 查询 |
| `/api/v1/opa/check` | POST | OPA 策略检查 |

---

*文档版本: 2.0 | 最后更新: 2026-04-11 | 作者: 软件架构师*
