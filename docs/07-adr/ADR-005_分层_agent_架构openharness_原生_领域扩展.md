# ADR-005: 分层 Agent 架构（OpenHarness 原生 + 领域扩展）

> **来源**: `docs/ARCHITECTURE.md` 第 17 章

---


**状态**: 已接受

**上下文**: 系统定位为通用本体驱动平台，Agent 需要：
1. 复用 OpenHarness 原生能力，保持框架可升级
2. 支持其他业务 Agent 的集成管理
3. 区分平台级通用 Agent 和领域特定 Agent

**决策**: 采用分层 Agent 架构，深度集成 OpenHarness

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         Agent 分层架构 (OpenHarness Native)                │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  Layer 1: OpenHarness 原生 Agent（平台通用）                         │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │                                                                     │  │
│  │   OpenHarness Engine                                               │  │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐              │  │
│  │   │  Tool   │  │ Memory  │  │Permiss- │  │  Hook   │              │  │
│  │   │Registry │  │Manager  │  │   ion   │  │Manager  │              │  │
│  │   └─────────┘  └─────────┘  └─────────┘  └─────────┘              │  │
│  │                                                                     │  │
│  │   ┌─────────────────────────────────────────────────────────────┐  │  │
│  │   │  Swarm Orchestrator (OpenHarness)                           │  │  │
│  │   │  • 多 Agent 协同    • 任务分发    • 结果聚合                 │  │  │
│  │   └─────────────────────────────────────────────────────────────┘  │  │
│  │                                                                     │  │
│  │   OpenHarness Plugins (可扩展)                                     │  │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐              │  │
│  │   │ Router  │  │Coordin- │  │Observer │  │ Memory  │              │  │
│  │   │ Plugin  │  │ator     │  │ Plugin  │  │ Plugin  │              │  │
│  │   │(内置)   │  │Plugin   │  │(内置)   │  │(内置)   │              │  │
│  │   └─────────┘  └─────────┘  └─────────┘  └─────────┘              │  │
│  │                                                                     │  │
│  │   MCP Integration (外部系统集成)                                    │  │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────┐                           │  │
│  │   │   MCP   │  │   MCP   │  │   MCP   │    ...                    │  │
│  │   │ Server1 │  │ Server2 │  │ ServerN  │                           │  │
│  │   └─────────┘  └─────────┘  └─────────┘                           │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                              ↓                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  Layer 2: 领域特定 Agent（工作空间实例化）                          │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │                                                                     │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │  │
│  │  │    战争分析  │  │    金融分析  │  │    医疗诊断  │  ...          │  │
│  │  │   Workspace │  │   Workspace │  │   Workspace │                │  │
│  │  ├─────────────┤  ├─────────────┤  ├─────────────┤                │  │
│  │  │ Intelligence│  │ Analyzer   │  │ Diagnostian │                │  │
│  │  │ Commander   │  │ Advisor    │  │ Specialist  │                │  │
│  │  │ Operations  │  │ Executor   │  │ Nurse       │                │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │  │
│  │                                                                     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │  Layer 3: 外部业务 Agent 集成（第三方系统）                          │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐                      │  │
│  │  │ External  │  │ External  │  │ External  │                      │  │
│  │  │ Agent API │  │ Agent SDK │  │ MCP Bridge│                      │  │
│  │  └───────────┘  └───────────┘  └───────────┘                      │  │
│  │  • REST/WebSocket 接口  • Python/JS SDK  • MCP 协议兼容             │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

**Layer 1: OpenHarness 原生 Agent（平台通用）**

| 组件 | 类型 | 说明 | 可升级性 |
|------|------|------|----------|
| **Engine** | 核心 | Agent Loop + Tool 调度 | ✅ 原生支持 |
| **Swarm** | 核心 | 多 Agent 协同编排 | ✅ 原生支持 |
| **Memory Manager** | 内置 Plugin | 记忆管理（桥接 Graphiti） | ✅ 热插拔 |
| **Permission** | 内置 Plugin | 权限检查（桥接 OPA） | ✅ 热插拔 |
| **Router Plugin** | 扩展 Plugin | 意图识别 + 会话路由 | ✅ 可扩展 |
| **Coordinator Plugin** | 扩展 Plugin | 多 Agent 协调 | ✅ 可扩展 |
| **MCP Integration** | 扩展 | 外部系统集成 | ✅ 标准协议 |

**层级关系说明**：

| 层级 | 定位 | 来源 | 接入方式 | 管理 |
|------|------|------|----------|------|
| **Layer 2** | 平台内部扩展 | 自研 Python Skills | OpenHarness Skill 机制 | 平台内管理 |
| **Layer 3** | 平台外部集成 | 第三方 Agent | MCP/REST/WebSocket | 外部管理 |

> **关系**：Layer 2 是平台可控的内部能力，Layer 3 是平台需要对接的外部能力。两者通过不同协议接入，统一由 Layer 1 调度。

**Layer 2: 领域特定 Agent（OpenHarness Skill 封装）**

```python
# 领域 Agent 通过 Skill 封装，集成到 OpenHarness
class DomainIntelligenceAgent:
    """战争分析 - Intelligence Agent"""
    
    def __init__(self, openharness_client):
        self.client = openharness_client
        # 挂载领域 Skill
        self.skills = [
            "intelligence/situation_analysis",
            "intelligence/threat_detection",
            "ontology/query",
        ]
    
    async def observe(self, context: Context) -> Observation:
        """Observe: 情报采集"""
        result = await self.client.execute(
            skills=self.skills,
            input={"query": context.query, "workspace": context.workspace}
        )
        return Observation(data=result)
    
    async def orient(self, observation: Observation) -> Understanding:
        """Orient: 态势理解"""
        # 调用 Graphiti 进行时序推理
        graphiti_result = await self._query_graphiti(observation)
        return Understanding(situation=graphiti_result)
```

**Layer 3: 外部业务 Agent 集成**

```python
# core/external_agent_bridge.py
class ExternalAgentBridge:
    """外部 Agent 集成桥接器"""
    
    def __init__(self, openharness_client):
        self.client = openharness_client
        self.registries = {}  # agent_type -> registry
    
    async def register_agent(self, agent_config: ExternalAgentConfig):
        """注册外部 Agent"""
        if agent_config.protocol == "mcp":
            await self._register_mcp_agent(agent_config)
        elif agent_config.protocol == "rest":
            await self._register_rest_agent(agent_config)
        elif agent_config.protocol == "websocket":
            await self._register_ws_agent(agent_config)
        else:
            raise UnsupportedProtocolError(agent_config.protocol)
    
    async def invoke_agent(self, agent_id: str, input_data: dict) -> dict:
        """调用外部 Agent"""
        registry = self.registries.get(agent_id)
        if not registry:
            raise AgentNotFoundError(agent_id)
        return await registry.invoke(input_data)
```

**OpenHarness 升级兼容性设计**：

```python
# core/openharness_compatibility.py
class OpenHarnessCompatibilityLayer:
    """
    OpenHarness 兼容性抽象层
    目标：解耦业务逻辑与框架细节，支持框架平滑升级
    """
    
    # 抽象接口（业务层使用）
    ABSTRACT_METHODS = [
        "create_agent",
        "invoke_agent",
        "register_tool",
        "attach_memory",
        "check_permission",
    ]
    
    # 版本兼容性映射
    VERSION_COMPATIBILITY = {
        "1.x": {"breaking": ["ToolRegistry"], "additions": ["MCP"]},
        "2.x": {"breaking": [], "additions": ["Swarm", "Hook"]},
        # 未来版本兼容...
    }
    
    def check_upgrade_compatibility(self, target_version: str) -> UpgradeReport:
        """检查升级兼容性"""
        breaking_changes = self._get_breaking_changes(target_version)
        return UpgradeReport(
            compatible=len(breaking_changes) == 0,
            breaking_changes=breaking_changes,
            migration_guide=self._generate_guide(breaking_changes)
        )
```

**后果**:
- ✅ **框架原生**：深度集成 OpenHarness，复用成熟能力
- ✅ **可升级**：兼容性抽象层支持框架平滑升级
- ✅ **可扩展**：Plugin 机制支持新增通用 Agent
- ✅ **第三方集成**：Layer 3 支持外部业务 Agent 接入
- ✅ **平台无关**：通用 Agent 不绑定领域逻辑
- ❌ 架构复杂度增加
- ❌ 需要管理三层 Agent 的生命周期

**可逆性**: 高。业务 Agent 通过 Skill 封装，解耦框架依赖。

---