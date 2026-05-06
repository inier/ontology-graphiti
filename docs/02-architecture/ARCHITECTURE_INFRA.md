# 本体驱动分析决策平台 (ODAP) - L1 基础设施层
> **部分**: OpenHarness + Graphiti + OPA + 审计日志
> **版本**: 4.1.0 | **日期**: 2026-05-04
> **上级文档**: [ARCHITECTURE.md](ARCHITECTURE.md)
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
| `mcp/` | 外部集成 | 领域仿真器、雷达模拟器 |
| `memory/` | 记忆管理 | Graphiti 替换内置 Memory |
| `coordinator/` | Swarm | 三 Agent 协同编排 |

### 3.3 OpenHarness 复用策略详解

#### 3.3.1 复用分类总览

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           OpenHarness HKUDS v0.1.6 能力分布                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ✅ 完全复用 (8个)  │ Agent Loop、43+ Tools、40+ Skills、Memory、Permissions、    │
│                     │ Plugin、Provider、Token 计量                                │
│  ⚠️ 适配复用 (7个)  │ Swarm(承载三Agent)、hooks、prompts、commands、mcp、tasks、  │
│                     │ config                                                    │
│  🔴 独立扩展 (6个)  │ Graphiti本体图谱、OPA业务策略、领域本体、56 Skills、       │
│                     │ 态势可视化、仿真数据生成                                    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

> **⚠️ 重要声明 1**: OpenHarness Memory 与 Graphiti 是**两种不同机制**，职责分明，**不能混用**：
> - **OpenHarness Memory**: Agent 运行时的**会话状态管理**（CLAUDE.md 发现、Auto-Compaction）
> - **Graphiti**: **本体知识图谱**（实体关系、时序推理、历史回溯）
>
> **⚠️ 重要声明 2**: OpenHarness Permissions 与 OPA 是**职责互补，而非替代**：
> - **OpenHarness Permissions**: **操作系统层安全**（文件路径、Shell 命令、工作目录）
> - **OPA**: **业务层策略**（角色权限、工作空间隔离、业务规则校验）
> - 两者串联执行：Permissions → OPA

#### 3.3.2 完全复用（开箱即用）

| 组件 | 说明 | 项目中的价值 |
|------|------|-------------|
| **Agent Loop Engine** | 流式推理 + 工具调用循环 | 底层推理引擎，无需自研 |
| **Tool 生态 (43+)** | Bash/Read/Write/Grep/Search/Web/Task | 情报分析可直接调用 |
| **Skill 格式** | 兼容 anthropics/skills | 可复用官方 40+ Skills |
| **Memory 会话管理** | CLAUDE.md 发现、Auto-Compaction | 多天会话自动压缩，CLAUDE.md 自动注入 |
| **Permissions 系统** | 路径规则、命令过滤、工作目录隔离 | 操作系统层安全防护 |
| **Plugin 系统** | Claude-code 兼容 | 代码审查、安全扫描插件 |
| **多 Provider** | Claude/GPT/DeepSeek/本地 | `oh provider add` 配置 |
| **Token 计量** | 内置成本跟踪 | 无需自建计量系统 |

#### 3.3.3 适配复用（需要桥接）

> **核心思路**：OpenHarness 提供**通用智能**，业务层提供**领域知识**，两者通过桥接层组合。

##### 框架层：OpenHarness 提供的智能能力

| OpenHarness 组件 | 框架能力 | 我们利用什么 |
|:-----------------|---------|-------------|
| **coordinator/** | Swarm 多 Agent 协调、注册、任务分发、结果聚合 | Swarm 作为三 Agent 的运行容器 |
| **hooks/** | PreToolUse/PostToolUse 生命周期钩子 | 作为策略注入点，在执行前调用 OPA 校验 |
| **prompts/** | System Prompt 模板化管理 | 领域化改造，注入领域上下文、角色定义 |
| **mcp/** | MCP 协议支持，多 Server 管理 | 扩展 Server，接入领域传感器数据源 |
| **tasks/** | 任务状态管理、持久化接口 | 复用接口，任务数据存入 Graphiti |
| **config/** | 多环境配置、动态加载 | 保留层级，新增 domain_config.yaml |

##### 业务层：需要桥接的部分

| 业务需求 | 框架能力 | 桥接实现 |
|:---------|---------|---------|
| 三 Agent 协同 | Swarm 支持多 Agent 注册 | 定义 Commander/Intelligence/Operations 三个业务角色 |
| 领域策略校验 | hooks 机制 | 创建 DomainPolicyHook，调用 OPA 检查攻击目标 |
| 领域化指令 | commands 系统 | 新增 /strike /intel /threat 等领域命令 |
| 知识持久化 | tasks 持久化 | 执行任务写入 Graphiti，形成决策历史 |

> **关系说明**: Swarm Coordinator **承载** 三 Agent，而非被三 Agent 替代。
> - Coordinator = 调度引擎（注册、分发、聚合）
> - 三 Agent = 业务角色（决策、感知、执行）

#### 3.3.4 独立扩展（OpenHarness 没有的能力）

##### 存储层：持久化知识

| 能力 | 技术实现 | 优先级 | 职责边界 |
|------|---------|--------|----------|
| **Graphiti 图谱** | graphiti-core + Neo4j | P0 | 持久化存储、时序推理、RAG 检索、历史追溯 |
| **OPA 策略引擎** | opa-python | P0 | 角色权限、业务规则、决策校验 |

##### 模型层：类型定义

| 能力 | 技术实现 | 优先级 | 职责边界 |
|------|---------|--------|----------|
| **本体模型** | Pydantic | P0 | 实体类型定义、属性校验、API Schema |
| **拓扑计算** | NetworkX | P1 | 图算法（路径规划、影响力传播、聚类分析）|

> **Graphiti vs NetworkX 分工**：
> - **Graphiti (Neo4j)**：持久化存储，答"What happened"（发生了什么）
> - **NetworkX**：图算法计算，答"What does it mean"（意味着什么）
> - **协作模式**：Graphiti 导出 → NetworkX 计算 → 结果回写 Graphiti

##### 应用层：业务 Skills

| 能力 | 技术实现 | 优先级 | 说明 |
|------|---------|--------|------|
| **56 个领域 Skills** | Python 模块 | P1 | 情报/作战/分析专用 |
| **态势可视化** | Plotly + Matplotlib + ECharts | P1 | 前端动态可视化（地图、图表、动画） |
| **仿真数据生成** | 模拟事件生成器 | P2 | 工作空间级模拟事件、匹配本体图谱更新 |

#### 3.3.5 双层安全架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    双层安全架构：Permissions + OPA 串联                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    Layer 1: OpenHarness Permissions                    │  │
│  │                         (操作系统层防护)                               │  │
│  │                                                                      │  │
│  │  职责:                                                              │  │
│  │    • 防止 Agent 执行危险命令 (rm -rf /, DROP TABLE)                │  │
│  │    • 限制文件系统访问范围 (~/.workspace/*)                         │  │
│  │    • Shell 命令白名单/黑名单                                         │  │
│  │    • 工作目录隔离                                                   │  │
│  │                                                                      │  │
│  │  特点: 快速（本地配置）| 粗粒度 | 无业务上下文                      │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼ 执行前检查                              │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                         Layer 2: OPA                                   │  │
│  │                        (业务层策略引擎)                                │  │
│  │                                                                      │  │
│  │  职责:                                                              │  │
│  │    • 角色权限管控（pilot/commander/analyst）                        │  │
│  │    • 业务规则校验（禁止攻击民用设施）                                │  │
│  │    • 工作空间隔离（空间 A 规则不适用 B）                             │  │
│  │    • 决策审计追溯                                                   │  │
│  │                                                                      │  │
│  │  特点: 稍慢（HTTP）| 细粒度 | 丰富上下文                            │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼ 全部通过                              │
│                           ┌─────────────────┐                              │
│                           │   业务操作执行   │                              │
│                           └─────────────────┘                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

| 对比维度 | OpenHarness Permissions | OPA |
|----------|------------------------|-----|
| 防护对象 | 文件/命令/Shell | 业务操作（攻击/查看/审批） |
| 决策依据 | 路径模式/命令白名单 | 角色+资源+上下文 |
| 上下文感知 | 无 | 丰富（时间/空间/状态） |
| 适用场景 | 开发安全、沙箱 | 业务合规、权限管控 |
| 更新方式 | 配置重启 | 热更新（Bundle） |
|------|---------|--------|
| **Graphiti 本体图谱** | graphiti-core | P0 | 实体关系、时序推理、历史回溯 |
| **本体模型** | Pydantic | P0 | 实体类型体系 |
| **决策审计** | Graphiti 时序记录 | P0 | 完整决策链追溯 |
| **56 个领域 Skills** | Python 模块 | P1 | 情报/作战/分析专用 |
| **态势可视化** | Plotly + Matplotlib + ECharts | P1 | 前端动态可视化（地图、图表、动画） |
| **仿真数据生成** | 模拟事件生成器 | P2 | 工作空间级模拟事件、匹配本体图谱更新 |

#### 3.3.6 记忆系统分工说明

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         记忆系统：职责分明，协同工作                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐  │
│  │    OpenHarness Memory           │   │         Graphiti                 │  │
│  │     (会话状态管理层)              │   │        (本体知识图谱层)            │  │
│  ├─────────────────────────────────┤   ├─────────────────────────────────┤  │
│  │  • CLAUDE.md 自动发现           │   │  • 实体节点存储                  │  │
│  │  • Auto-Compaction             │   │  • 关系边管理                    │  │
│  │  • 多天会话压缩                 │   │  • 双时态记录 (valid/observed)   │  │
│  │  • 任务状态保持                 │   │  • 图遍历查询                   │  │
│  │  • 频道日志                     │   │  • 时序窗口查询                 │  │
│  │  • 上下文注入到 Prompt           │   │  • 语义向量检索                 │  │
│  └─────────────────────────────────┘   └─────────────────────────────────┘  │
│                  │                                    │                     │
│                  ▼                                    ▼                     │
│  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐  │
│  │  用途：Agent 运行时状态           │   │  用途：领域知识推理               │  │
│  │  • "上次任务执行到哪了"          │   │  • "雷达A和雷达B是什么关系"      │  │
│  │  • "用户之前要求了什么"          │   │  • "过去72小时威胁等级变化"      │  │
│  │  • "当前会话压缩状态"            │   │  • "目标X的毁伤评估"             │  │
│  └─────────────────────────────────┘   └─────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3.3.7 桥接层核心代码

```python
# Memory 桥接：Graphiti → OpenHarness Memory
from openharness.memory.base import BaseMemoryStore

class GraphitiMemoryAdapter(BaseMemoryStore):
    """Graphiti 双时态图谱作为 OpenHarness 的长期记忆"""

    async def read(self, query: str, limit: int = 10) -> List[Dict]:
        return self.graphiti.search(query, limit)  # 语义搜索

    async def write(self, event_type: str, content: str, metadata: Dict) -> bool:
        # 写入时序图谱（OpenHarness 原生 Memory 没有的能力）
        self.graphiti.add_fact(
            subject=event_type,
            predicate="occurred_at",
            object=content,
            episode_time=metadata.get("timestamp")
        )

    async def search_by_time_window(self, start: datetime, end: datetime):
        """增强能力：时序窗口查询（OpenHarness 没有）"""
        return self.graphiti.get_facts(start_time=start, end_time=end)
```

```python
# Permission 桥接：OPA → OpenHarness Permission Hook
@register_hook("pre_tool_use")
class OPAPermissionHook:
    """OPA 策略引擎替代 OpenHarness 原生权限系统"""

    async def execute(self, tool_name: str, arguments: Dict, context: Dict) -> bool:
        opa_input = {
            "action": tool_name,
            "resource": arguments.get("target_id"),
            "subject": context.get("user_role"),
            "environment": context.get("domain_state")
        }
        return self.opa.evaluate("domain.allow", opa_input)
```

#### 3.3.8 复用收益与权衡

| 指标 | 自研 | 复用 OpenHarness | 变化 |
|------|------|------------------|------|
| 基础设施代码 | ~5000 行 | ~200 行集成 | **-96%** |
| Agent Loop | 需自研 | 开箱即用 | **消除** |
| 工具开发 | 43 个需自研 | 原生 Tool 接口 | **节省 6+ 月** |
| Swarm 编排 | 需自研 | 内置支持 | **消除** |
| 版本维护 | 独立更新 | 需同步上游 | **新增成本** |
| 定制能力 | 完全可控 | 原生扩展点 | **可扩展** |

**收益总结**：
- ✅ **94%+ 基础设施代码节省**：复用 OpenHarness 成熟组件
- ✅ **消除核心技术风险**：Agent Loop、Swarm、Tool 调度经过生产验证
- ✅ **Python Skills 原生接入**：无需桥接层，直接 Tool 接口
- ⚠️ **上游依赖**：需关注 OpenHarness 版本更新
- ⚠️ **定制边界**：平台差异化能力需在 Skill 层实现

---

### 3.4 OpenHarness 安装与配置

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

# 领域实体节点
class Target(EntityNode):
    """目标实体"""
    name: str                    # 目标名称
    target_type: str            # radar | command_center | supply_depot
    location: dict              # 地理坐标
    threat_level: str            # critical | high | medium | low
    status: str                  # active | destroyed | unknown

class Unit(EntityNode):
    """执行单元"""
    unit_id: str
    unit_type: str               # infantry | armor | aviation
    position: dict
    combat_capability: float     # 执行能力指数 0-100

class IntelligenceReport(EpisodeNode):
    """情报报告（时间区间事实）"""
    report_id: str
    source: str                  # satellite | drone | human
    confidence: float            # 置信度 0-1
    detected_at: datetime        # 发现时间
    content: str                  # 报告内容摘要

class StrikeOrder(EpisodeNode):
    """决策指令（带执行状态）"""
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
| **证据链追溯** | "这个决策指令的依据是什么？" | 决策解释 |
| **变化检测** | "过去1小时有哪些变化？" | 异常告警 |
| **RAG 增强** | "基于历史情报推荐方案" | 决策支持 |

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

# 目标允许规则
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
# core/skills/

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


## 15. 审计日志系统


### 15.1 审计日志定位

审计日志是系统的"执法记录仪"，记录所有操作和事件，为合规、追溯和复盘提供依据。

### 15.2 审计事件类型

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
  STRIKE_ORDER_ISSUED: { zh: '决策指令下达', en: 'Strike Order Issued', category: 'critical' },
  STRIKE_ORDER_EXECUTED: { zh: '决策指令执行', en: 'Strike Order Executed', category: 'critical' },
  STRIKE_ORDER_CANCELLED: { zh: '决策指令取消', en: 'Strike Order Cancelled', category: 'critical' },
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



### 15.3 审计日志后端实现

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

    // 决策指令
    this.eventEmitter.on('strike:issued', (data) => {
      this.log({
        event_type: 'STRIKE_ORDER_ISSUED',
        actor: data.commander,
        action: '下达决策指令',
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

### 15.4 前端审计日志展示

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



