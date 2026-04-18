# OpenHarness 桥接模块设计文档

> ⏸️ **DEFERRED — 推迟至 Phase 4** (ADR-030, 2026-04-19)
>
> 本模块依赖 OpenHarness 框架集成，根据 ADR-030 决策，OpenHarness 实现延期至 Phase 4。
> 当前阶段（Phase 0-3）通过原生扩展点实现必要功能，无需本桥接层。
> 本文档保留供 Phase 4 参考，当前不再维护。

> **优先级**: P0 | **相关 ADR**: ADR-001, ADR-005, ADR-006

## 1. 模块概述

### 1.1 模块定位

`openharness_bridge` 是基于 **OpenHarness 原生扩展点**（Plugin/Memory Plugin/Permission Plugin/Skill）的领域适配层。它通过 ADR-005 定义的分层 Agent 架构，将 OpenHarness 的通用 Agent 框架、Tool 调度、记忆管理和权限控制适配到领域情报分析与打击决策系统的特定需求。

> **注意**: 本模块定位为"适配层"而非"桥接中间件"。所有集成通过 OpenHarness 原生扩展点实现（参见 ADR-005），不引入独立中间件。

### 1.2 核心职责

| 职责 | 描述 |
|------|------|
| Agent 适配 | 将 OpenHarness 原生 Agent 配置适配到三 Agent 角色（Commander/Intelligence/Operations），通过 Skill 封装领域能力（ADR-005 Layer 2） |
| Memory 适配 | 通过 OpenHarness Memory Plugin 扩展点，将 Graphiti 双时态知识图谱注册为 OpenHarness 记忆后端 |
| Permission 适配 | 通过 OpenHarness Permission Plugin 扩展点，将 OPA 策略引擎注册为权限后端 |
| Tool 标准化 | 将领域领域 Skills 转换为 OpenHarness 原生 Tool 接口 |
| Hooks 管理 | 注册和管理 OpenHarness 生命周期钩子 |

### 1.3 架构位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OpenHarness 领域适配层                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      BridgeManager (总入口)                         │    │
│  │  • 统一配置管理                                                     │    │
│  │  • 组件生命周期管理                                                  │    │
│  │  • 健康检查                                                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│         ┌──────────────────────────┼──────────────────────────┐             │
│         ▼                          ▼                          ▼             │
│  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐        │
│  │MemoryBridge │          │PermissionBrg│          │ SkillBridge │        │
│  │ (→Graphiti) │          │   (→OPA)    │          │  (Skills)   │        │
│  └─────────────┘          └─────────────┘          └─────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OpenHarness Core                                     │
│  Agent Loop | Tool Framework | Plugin System | Provider Management          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 接口设计

### 2.1 BridgeManager 主接口

```python
# core/openharness_bridge/__init__.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum

class BridgeStatus(str, Enum):
    """适配模块状态"""
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"
    ERROR = "error"

class BridgeConfig(BaseModel):
    """适配层配置"""
    opa_url: str = Field(default="http://localhost:8181")
    graphiti_url: str = Field(default="http://localhost:7474")
    neo4j_url: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(...)
    enable_memory_bridge: bool = Field(default=True)
    enable_permission_bridge: bool = Field(default=True)
    skill_scan_paths: List[str] = Field(default=["skills/"])
    auto_reload_skills: bool = Field(default=True)

class BridgeHealth(BaseModel):
    """健康检查结果"""
    status: BridgeStatus
    memory_bridge: bool
    permission_bridge: bool
    skills_loaded: int
    uptime_seconds: float
    errors: List[str] = Field(default_factory=list)

class BridgeManager:
    """OpenHarness 领域适配层管理器（基于原生扩展点）"""

    def __init__(self, config: BridgeConfig):
        self.config = config
        self._memory_bridge: Optional[GraphitiMemoryAdapter] = None
        self._permission_bridge: Optional[OPAPermissionAdapter] = None
        self._skill_registry: Optional[SkillRegistry] = None
        self._hooks: List[Hook] = []
        self._start_time: Optional[datetime] = None

    async def initialize(self) -> None:
        """初始化所有桥接组件"""
        pass

    async def shutdown(self) -> None:
        """优雅关闭所有组件"""
        pass

    async def health_check(self) -> BridgeHealth:
        """健康检查"""
        pass

    def get_memory_bridge(self) -> GraphitiMemoryAdapter:
        """获取记忆桥接器"""
        pass

    def get_permission_bridge(self) -> OPAPermissionAdapter:
        """获取权限桥接器"""
        pass

    def get_skill_registry(self) -> SkillRegistry:
        """获取技能注册表"""
        pass
```

### 2.2 Memory Bridge 接口

```python
# core/openharness_bridge/memory_bridge.py
from openharness.memory.base import BaseMemoryStore
from typing import List, Dict, Any, Optional
from datetime import datetime

class GraphitiMemoryAdapter(BaseMemoryStore):
    """Graphiti 双时态图谱作为 OpenHarness 的长期记忆"""

    async def read(
        self,
        query: str,
        limit: int = 10,
        time_window: Optional[tuple[datetime, datetime]] = None,
        agent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        读取记忆（支持语义搜索和时序过滤）

        Args:
            query: 语义查询字符串
            limit: 返回结果数量限制
            time_window: 可选的时序窗口 (start, end)
            agent_id: 可选的 Agent ID 过滤

        Returns:
            匹配的 Episode 列表
        """
        pass

    async def write(
        self,
        event_type: str,
        content: str,
        metadata: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        写入记忆（写入 Graphiti Episode）

        Args:
            event_type: 事件类型（用于分类）
            content: 内容摘要
            metadata: 元数据（包含 timestamp, agent_id 等）
            ttl: 可选的生存时间（秒）

        Returns:
            写入是否成功
        """
        pass

    async def search_by_time_window(
        self,
        start: datetime,
        end: datetime,
        entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        时序窗口查询（OpenHarness 原生 Memory 没有的能力）

        Args:
            start: 开始时间
            end: 结束时间
            entity_type: 可选的实体类型过滤

        Returns:
            时间窗口内的 Episode 列表
        """
        pass

    async def search_by_entity(
        self,
        entity_id: str,
        depth: int = 1,
        time_window: Optional[tuple[datetime, datetime]] = None
    ) -> Dict[str, Any]:
        """
        按实体 ID 查询关联记忆

        Args:
            entity_id: 实体 ID
            depth: 关系深度
            time_window: 可选的时序窗口

        Returns:
            实体及其关联 Episode
        """
        pass

    async def get_context_for_agent(
        self,
        agent_id: str,
        current_task: str,
        limit: int = 20
    ) -> str:
        """
        为特定 Agent 生成上下文摘要

        Args:
            agent_id: Agent ID
            current_task: 当前任务描述
            limit: 上下文长度限制

        Returns:
            格式化的上下文字符串
        """
        pass

    async def compact(self, older_than: datetime) -> int:
        """
        压缩旧记忆（合并相似 Episode）

        Args:
            older_than: 压缩此时间之前的记忆

        Returns:
            删除的记忆数量
        """
        pass
```

### 2.3 Permission Bridge 接口

```python
# core/openharness_bridge/permission_bridge.py
from openharness.permissions.base import PermissionBackend

class OPAPermissionAdapter(PermissionBackend):
    """OPA 策略引擎替代 OpenHarness 原生权限系统"""

    def __init__(
        self,
        opa_url: str,
        default_package: str = "policies/common/default",
        cache_ttl: int = 60
    ):
        self.opa_url = opa_url
        self.default_package = default_package
        self.cache_ttl = cache_ttl
        self._cache: LRUCache = LRUCache(maxsize=1000)
        self._opa_client: Optional[OPAClient] = None

    async def check(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        权限检查

        Args:
            tool_name: Tool 名称
            tool_input: Tool 输入参数
            context: 执行上下文（agent_id, user, domain_state 等）

        Returns:
            是否允许执行
        """
        pass

    async def check_with_reason(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        权限检查（返回原因）

        Args:
            tool_name: Tool 名称
            tool_input: Tool 输入参数
            context: 执行上下文

        Returns:
            (是否允许, 拒绝原因)
        """
        pass

    async def bulk_check(
        self,
        requests: List[PermissionRequest]
    ) -> List[PermissionResult]:
        """
        批量权限检查（优化性能）

        Args:
            requests: 权限请求列表

        Returns:
            权限结果列表
        """
        pass

    async def reload_policies(self) -> bool:
        """重新加载 OPA 策略（热更新）"""
        pass

    async def get_allowed_tools(
        self,
        agent_id: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """
        获取 Agent 允许执行的 Tool 列表

        Args:
            agent_id: Agent ID
            context: 执行上下文

        Returns:
            允许的 Tool 名称列表
        """
        pass

    def get_policy_package(self, tool_name: str) -> str:
        """Tool 名称到策略包的映射"""
        pass

    def set_policy_mapping(self, mapping: Dict[str, str]) -> None:
        """设置自定义策略映射"""
        pass
```

### 2.4 Skill Bridge 接口

```python
# core/openharness_bridge/skill_bridge.py
from pydantic import BaseModel
from typing import Dict, Type, List, Optional, Any

class SkillMetadata(BaseModel):
    """技能元数据"""
    name: str
    description: str
    category: str  # intelligence | operations | analysis | visualization
    input_model: str  # 类名字符串
    output_model: str  # 类名字符串
    requires_opa_check: bool = False
    danger_level: str = "low"  # low | medium | high | critical
    tags: List[str] = []
    version: str = "1.0.0"
    dependencies: List[str] = []

class SkillRegistry:
    """技能注册表（OpenHarness Skill → Tool 适配）"""

    def __init__(self):
        self._skills: Dict[str, Type] = {}
        self._metadata: Dict[str, SkillMetadata] = {}
        self._tools: Dict[str, ToolConfig] = {}
        self._category_index: Dict[str, List[str]] = {
            "intelligence": [],
            "operations": [],
            "analysis": [],
            "visualization": [],
        }

    def register(
        self,
        name: str,
        skill_class: Type,
        metadata: SkillMetadata
    ) -> None:
        """注册技能"""
        pass

    def unregister(self, name: str) -> bool:
        """取消注册技能"""
        pass

    def get_skill(self, name: str) -> Optional[Type]:
        """获取技能类"""
        pass

    def get_metadata(self, name: str) -> Optional[SkillMetadata]:
        """获取技能元数据"""
        pass

    def get_tools_for_agent(
        self,
        agent_type: str,
        context: Dict[str, Any]
    ) -> List[ToolConfig]:
        """
        获取 Agent 可用的 Tool 列表

        Args:
            agent_type: Agent 类型 (commander/intelligence/operations)
            context: 执行上下文

        Returns:
            可用的 Tool 配置列表
        """
        pass

    def get_by_category(self, category: str) -> List[SkillMetadata]:
        """按类别获取技能"""
        pass

    def search(self, query: str) -> List[SkillMetadata]:
        """语义搜索技能"""
        pass

    async def reload(self) -> ReloadResult:
        """重新加载技能（热更新）"""
        pass

    def to_openharness_tools(self) -> List[ToolConfig]:
        """转换为 OpenHarness Tool 配置"""
        pass

class SkillToToolAdapter:
    """Skill 到 OpenHarness Tool 的适配器"""

    def __init__(self, skill_registry: SkillRegistry):
        self.skill_registry = skill_registry
        self.opensearch_adapter = OpenSearchAdapter()

    def adapt_skill(self, skill_name: str) -> ToolConfig:
        """将 Skill 适配为 OpenHarness Tool"""
        pass

    def adapt_all(self) -> List[ToolConfig]:
        """适配所有注册的 Skill"""
        pass

    def create_tool_executor(self, skill_name: str) -> Callable:
        """创建 Tool 执行器"""
        pass
```

---

## 3. 数据结构

### 3.1 配置模型

```python
# core/openharness_bridge/models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class AgentRoleConfig(BaseModel):
    """Agent 角色配置"""
    role: str  # commander | intelligence | operations
    model: str
    tools: List[str]
    permission_level: str
    memory_backend: str = "graphiti"
    system_prompt_template: str
    requires_opa_approval: bool = False

class ToolPolicyMapping(BaseModel):
    """Tool 到策略包的映射"""
    tool_name: str
    policy_package: str
    conditions: Optional[Dict[str, Any]] = None

class BridgeMetrics(BaseModel):
    """桥接层指标"""
    timestamp: datetime
    memory_queries_total: int = 0
    memory_writes_total: int = 0
    permission_checks_total: int = 0
    permission_denials_total: int = 0
    skills_executed_total: int = 0
    average_response_time_ms: float = 0.0
```

---

## 4. 核心实现

### 4.1 BridgeManager 实现

```python
# core/openharness_bridge/manager.py
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class BridgeManagerImpl(BridgeManager):
    """BridgeManager 具体实现"""

    async def initialize(self) -> None:
        """初始化所有桥接组件"""
        self._start_time = datetime.now()
        logger.info("Initializing OpenHarness Adapter...")

        # 1. 初始化 Memory Adapter (Graphiti Memory Plugin)
        if self.config.enable_memory_bridge:
            self._memory_bridge = GraphitiMemoryAdapter(
                graphiti_url=self.config.graphiti_url,
                neo4j_config={
                    "uri": self.config.neo4j_url,
                    "auth": (self.config.neo4j_user, self.config.neo4j_password)
                }
            )
            await self._memory_bridge.connect()
            logger.info("Graphiti Memory Plugin initialized")

        # 2. 初始化 Permission Adapter (OPA Permission Plugin)
        if self.config.enable_permission_bridge:
            self._permission_bridge = OPAPermissionAdapter(
                opa_url=self.config.opa_url
            )
            await self._permission_bridge.health_check()
            logger.info("OPA Permission Plugin initialized")

        # 3. 初始化 Skill Registry
        self._skill_registry = SkillRegistry()
        await self._load_skills()

        # 4. 注册 Hooks
        await self._register_hooks()

        logger.info("OpenHarness Bridge ready")

    async def _load_skills(self) -> None:
        """加载技能模块"""
        skill_adapter = SkillToToolAdapter(self._skill_registry)

        for scan_path in self.config.skill_scan_paths:
            await self._skill_registry.load_from_path(scan_path)

        if self.config.auto_reload_skills:
            asyncio.create_task(self._watch_skills())

    async def _register_hooks(self) -> None:
        """注册 OpenHarness Hooks"""
        # 注册 pre_tool_use Hook (OPA 权限检查)
        if self._permission_bridge:
            self._hooks.append(OPAPermissionHook(self._permission_bridge))

        # 注册 post_tool_use Hook (结果写入 Graphiti)
        if self._memory_bridge:
            self._hooks.append(MemoryWriteHook(self._memory_bridge))

    async def health_check(self) -> BridgeHealth:
        """健康检查"""
        status = BridgeStatus.READY
        errors = []

        memory_ok = False
        permission_ok = False

        if self._memory_bridge:
            memory_ok = await self._memory_bridge.ping()
            if not memory_ok:
                status = BridgeStatus.DEGRADED
                errors.append("Graphiti Memory Bridge unreachable")

        if self._permission_bridge:
            permission_ok = await self._permission_bridge.health_check()
            if not permission_ok:
                status = BridgeStatus.DEGRADED
                errors.append("OPA Permission Bridge unreachable")

        if not memory_ok and not permission_ok:
            status = BridgeStatus.ERROR

        return BridgeHealth(
            status=status,
            memory_bridge=memory_ok,
            permission_bridge=permission_ok,
            skills_loaded=len(self._skill_registry._skills),
            uptime_seconds=(datetime.now() - self._start_time).total_seconds(),
            errors=errors
        )
```

### 4.2 OPA 权限检查 Hook

```python
# core/openharness_bridge/hooks/opa_hook.py
from openharness.hooks import register_hook

@register_hook("pre_tool_use")
class OPAPermissionHook:
    """OPA 权限检查 Hook"""

    def __init__(self, permission_bridge: OPAPermissionAdapter):
        self.permission_bridge = permission_bridge

    async def execute(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> HookResult:
        """
        在 Tool 执行前进行 OPA 权限检查

        Args:
            tool_name: Tool 名称
            tool_input: Tool 输入参数
            context: 执行上下文

        Returns:
            HookResult (允许或拒绝)
        """
        # 1. 获取 Tool 对应的策略包
        policy_package = self.permission_bridge.get_policy_package(tool_name)

        # 2. 构建 OPA 输入
        opa_input = {
            "action": tool_name,
            "tool_input": tool_input,
            "agent_id": context.get("agent_id"),
            "user": context.get("user"),
            "role": context.get("role"),
            "environment": context.get("domain_state", {}),
            "timestamp": datetime.now().isoformat(),
        }

        # 3. OPA 检查
        allowed, reason = await self.permission_bridge.check_with_reason(
            tool_name, tool_input, context
        )

        if not allowed:
            logger.warning(
                f"OPA denied: {tool_name}",
                extra={"reason": reason, "agent": context.get("agent_id")}
            )
            return HookResult(
                allowed=False,
                message=f"Permission denied: {reason}",
                metadata={"policy": policy_package, "reason": reason}
            )

        return HookResult(allowed=True)
```

### 4.3 记忆写入 Hook

```python
# core/openharness_bridge/hooks/memory_hook.py

@register_hook("post_tool_use")
class MemoryWriteHook:
    """Tool 执行后写入 Graphiti"""

    def __init__(self, memory_bridge: GraphitiMemoryAdapter):
        self.memory_bridge = memory_bridge

    async def execute(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
        context: Dict[str, Any]
    ) -> None:
        """写入执行结果到 Graphiti"""
        await self.memory_bridge.write(
            event_type=f"tool_executed_{tool_name}",
            content=f"{tool_name} executed: {str(tool_output)[:500]}",
            metadata={
                "tool_name": tool_name,
                "tool_input": tool_input,
                "agent_id": context.get("agent_id"),
                "timestamp": datetime.now(),
                "success": tool_output.get("success", True),
            }
        )
```

---

## 5. 配置文件

### 5.1 YAML 配置示例

```yaml
# config/openharness_bridge.yaml
openharness_bridge:
  # OPA 配置
  opa:
    url: "http://localhost:8181"
    default_package: "policies/common/default"
    cache_ttl: 60

  # Graphiti 配置
  graphiti:
    url: "http://localhost:7474"
    neo4j:
      uri: "bolt://localhost:7687"
      user: "neo4j"
      # password 从环境变量或密钥库获取

  # 技能配置
  skills:
    scan_paths:
      - "skills/intelligence/"
      - "skills/operations/"
      - "skills/analysis/"
      - "skills/visualization/"
    auto_reload: true
    hot_reload_interval: 30

  # 策略映射
  policy_mappings:
    attack_target: "policies/attack/allow"
    command_unit: "policies/operations/allow"
    radar_search: "policies/intelligence/allow"
    threat_assess: "policies/intelligence/allow"

  # Hook 配置
  hooks:
    pre_tool_use:
      - type: "opa_permission"
        enabled: true
    post_tool_use:
      - type: "memory_write"
        enabled: true
```

---

## 6. 错误处理

### 6.1 错误类型定义

```python
# core/openharness_bridge/exceptions.py

class BridgeError(Exception):
    """桥接模块基础异常"""
    pass

class MemoryBridgeError(BridgeError):
    """记忆桥接错误"""
    pass

class PermissionBridgeError(BridgeError):
    """权限桥接错误"""
    pass

class SkillBridgeError(BridgeError):
    """技能桥接错误"""
    pass

class OPAPolicyDenied(BridgeError):
    """OPA 策略拒绝"""
    def __init__(self, policy: str, input_data: dict, reason: str = None):
        self.policy = policy
        self.input_data = input_data
        self.reason = reason
        super().__init__(f"OPA policy denied: {policy} - {reason}")

class GraphitiConnectionError(MemoryBridgeError):
    """Graphiti 连接错误"""
    pass

class SkillNotFoundError(SkillBridgeError):
    """技能未找到"""
    pass
```

### 6.2 降级策略

| 组件 | 失败策略 | 降级行为 |
|------|---------|---------|
| Graphiti Memory | Warning + Local Cache | 使用内存缓存，回退只读模式 |
| OPA Permission | Fail-Close | 拒绝所有需要检查的操作 |
| Skill Registry | Warning | 使用已加载的技能，禁用热更新 |

---

## 7. 测试策略

### 7.1 单元测试

```python
# tests/unit/test_openharness_bridge/
# ├── test_manager.py
# ├── test_memory_bridge.py
# ├── test_permission_bridge.py
# └── test_skill_bridge.py
```

### 7.2 集成测试

```python
# tests/integration/test_bridge_integration.py
async def test_full_agent_loop_with_bridges():
    """测试完整的 Agent Loop 与桥接组件集成"""
    # 1. 启动 Mock OPA Server
    # 2. 启动 Mock Graphiti
    # 3. 初始化 BridgeManager
    # 4. 执行 Agent Loop
    # 5. 验证记忆写入和权限检查
```

---

## 8. 性能指标

| 指标 | 目标值 | 告警阈值 |
|------|--------|---------|
| 权限检查延迟 (P99) | < 50ms | > 100ms |
| 记忆查询延迟 (P99) | < 100ms | > 200ms |
| 技能执行吞吐量 | > 100 TPS | < 50 TPS |
| 桥接模块可用性 | > 99.9% | < 99% |

---

## 9. 依赖关系

```
# 依赖外部服务
- graphiti-core >= 0.3.0
- neo4j >= 5.0
- opa-python-sdk >= 0.5.0
- openharness >= 0.1.6

# 内部依赖
- ontology.domain_ontology
- skills.* (所有领域 Skills)
- core.opa_client
- core.graphiti_client
```

---

## 10. 框架抽象层与解耦设计

### 10.1 框架抽象接口层
```python
# core/framework_abstraction/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from dataclasses import dataclass

class FrameworkType(Enum):
    """支持的框架类型"""
    OPENHARNESS = "openharness"
    LANGGRAPH = "langgraph"
    CREWAI = "crewai"
    AUTOGEN = "autogen"

@dataclass
class AgentConfig:
    """Agent配置抽象"""
    name: str
    role: str
    model: str
    tools: List[str]
    system_prompt: str
    max_tokens: int = 4000
    temperature: float = 0.7

@dataclass
class ToolConfig:
    """Tool配置抽象"""
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    execute_func: Callable

class FrameworkAdapter(ABC):
    """框架适配器抽象接口"""
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """初始化框架"""
        pass
    
    @abstractmethod
    async def create_agent(self, config: AgentConfig) -> Any:
        """创建Agent实例"""
        pass
    
    @abstractmethod
    async def register_tool(self, tool_config: ToolConfig) -> bool:
        """注册Tool"""
        pass
    
    @abstractmethod
    async def execute_task(self, agent_id: str, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """关闭框架"""
        pass
```

### 10.2 OpenHarness 适配器实现
```python
# core/framework_abstraction/adapters/openharness_adapter.py
from typing import Dict, Any, List, Optional
from openharness import Agent, Tool, ToolRegistry

class OpenHarnessAdapter(FrameworkAdapter):
    """OpenHarness适配器（主选）"""
    
    def __init__(self):
        self.framework_type = FrameworkType.OPENHARNESS
        self.agents: Dict[str, Agent] = {}
        self.tool_registry = ToolRegistry()
        
    async def initialize(self, config: Dict[str, Any]) -> None:
        """初始化OpenHarness"""
        from openharness import initialize
        
        await initialize({
            "model_provider": config.get("model_provider", "openai"),
            "model_name": config.get("model_name", "gpt-4-turbo"),
            "memory_backend": config.get("memory_backend", "graphiti"),
            "permission_backend": config.get("permission_backend", "opa")
        })
        
        print(f"OpenHarness适配器已初始化 (v{self._get_version()})")
    
    async def create_agent(self, config: AgentConfig) -> Any:
        """创建OpenHarness Agent"""
        from openharness import create_agent
        
        # 获取Agent可用的Tools
        available_tools = []
        for tool_name in config.tools:
            tool = self.tool_registry.get(tool_name)
            if tool:
                available_tools.append(tool)
        
        # 创建Agent
        agent = create_agent(
            name=config.name,
            role=config.role,
            model=config.model,
            tools=available_tools,
            system_prompt=config.system_prompt,
            max_tokens=config.max_tokens,
            temperature=config.temperature
        )
        
        self.agents[config.name] = agent
        return agent
    
    async def register_tool(self, tool_config: ToolConfig) -> bool:
        """注册OpenHarness Tool"""
        tool = Tool(
            name=tool_config.name,
            description=tool_config.description,
            parameters=tool_config.parameters_schema,
            execute=tool_config.execute_func
        )
        
        self.tool_registry.register(tool)
        return True
    
    async def execute_task(self, agent_id: str, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        agent = self.agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} 未找到")
        
        result = await agent.run(task, context=context)
        return {
            "success": True,
            "result": result.content,
            "usage": result.usage,
            "execution_time_ms": result.execution_time_ms
        }
    
    async def health_check(self) -> bool:
        """OpenHarness健康检查"""
        try:
            # 检查核心组件
            components = [
                "model_provider",
                "memory_backend",
                "permission_backend"
            ]
            
            for component in components:
                status = await self._check_component(component)
                if not status:
                    return False
            
            return True
        except Exception:
            return False
    
    async def shutdown(self) -> None:
        """关闭OpenHarness"""
        for agent in self.agents.values():
            await agent.close()
        
        self.agents.clear()
        self.tool_registry.clear()
```

### 10.3 LangGraph 适配器实现（备选方案）
```python
# core/framework_abstraction/adapters/langgraph_adapter.py
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph

class LangGraphAdapter(FrameworkAdapter):
    """LangGraph适配器（第一备选）"""
    
    def __init__(self):
        self.framework_type = FrameworkType.LANGGRAPH
        self.agents: Dict[str, Any] = {}
        self.tools: Dict[str, Any] = {}
        self.graphs: Dict[str, StateGraph] = {}
        
    async def initialize(self, config: Dict[str, Any]) -> None:
        """初始化LangGraph"""
        import langgraph
        
        # LangGraph不需要特殊初始化
        print("LangGraph适配器已初始化")
    
    async def create_agent(self, config: AgentConfig) -> Any:
        """创建LangGraph Agent"""
        from langgraph.agent import Agent as LangGraphAgent
        
        # 创建Agent
        agent = LangGraphAgent(
            name=config.name,
            role=config.role,
            model=config.model,
            system_prompt=config.system_prompt
        )
        
        # 绑定Tools
        for tool_name in config.tools:
            tool = self.tools.get(tool_name)
            if tool:
                agent.bind_tool(tool)
        
        self.agents[config.name] = agent
        return agent
    
    async def register_tool(self, tool_config: ToolConfig) -> bool:
        """注册LangGraph Tool"""
        from langgraph.tool import tool
        
        # 创建装饰器Tool
        @tool(name=tool_config.name, description=tool_config.description)
        def execute_tool(**kwargs):
            return tool_config.execute_func(**kwargs)
        
        self.tools[tool_config.name] = execute_tool
        return True
    
    async def execute_task(self, agent_id: str, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        agent = self.agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} 未找到")
        
        # LangGraph执行
        result = await agent.invoke({"task": task, "context": context})
        
        return {
            "success": True,
            "result": result.get("content", ""),
            "usage": result.get("usage", {}),
            "execution_time_ms": result.get("execution_time_ms", 0)
        }
```

### 10.4 CrewAI 适配器实现（第二备选方案）
```python
# core/framework_abstraction/adapters/crewai_adapter.py
class CrewAIAdapter(FrameworkAdapter):
    """CrewAI适配器（第二备选）"""
    
    def __init__(self):
        self.framework_type = FrameworkType.CREWAI
        self.crew = None
        self.tasks: Dict[str, Any] = {}
        
    async def initialize(self, config: Dict[str, Any]) -> None:
        """初始化CrewAI"""
        from crewai import Crew
        
        # CrewAI通过任务和代理配置，不需要全局初始化
        print("CrewAI适配器已初始化")
    
    async def create_agent(self, config: AgentConfig) -> Any:
        """创建CrewAI Agent"""
        from crewai import Agent
        
        agent = Agent(
            role=config.role,
            goal=f"作为{config.role}执行任务",
            backstory=config.system_prompt,
            allow_delegation=False,
            verbose=True
        )
        
        return agent
    
    async def register_tool(self, tool_config: ToolConfig) -> bool:
        """CrewAI Tool注册（通过函数装饰器）"""
        # CrewAI使用函数工具
        def tool_wrapper(**kwargs):
            return tool_config.execute_func(**kwargs)
        
        tool_wrapper.__name__ = tool_config.name
        tool_wrapper.__doc__ = tool_config.description
        
        self.tools[tool_config.name] = tool_wrapper
        return True
    
    async def execute_task(self, agent_id: str, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """CrewAI执行任务"""
        from crewai import Task
        
        agent = self.agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} 未找到")
        
        # 创建任务
        crew_task = Task(
            description=task,
            agent=agent,
            expected_output="任务执行结果"
        )
        
        # 执行任务
        result = self.crew.kickoff(inputs={"task": task, "context": context})
        
        return {
            "success": True,
            "result": result.raw,
            "execution_time_ms": 0  # CrewAI不提供执行时间
        }
```

### 10.5 框架工厂与热切换
```python
# core/framework_abstraction/factory.py
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class FrameworkFactoryConfig:
    """框架工厂配置"""
    primary_framework: str = "openharness"
    fallback_order: List[str] = None
    health_check_interval: int = 30  # 秒
    auto_failover: bool = True

class FrameworkFactory:
    """框架工厂，支持热切换和故障转移"""
    
    def __init__(self, config: FrameworkFactoryConfig = None):
        self.config = config or FrameworkFactoryConfig()
        
        # 初始化适配器
        self.adapters: Dict[str, FrameworkAdapter] = {}
        self.current_adapter: Optional[FrameworkAdapter] = None
        
        # 故障转移状态
        self.failover_history: List[Dict[str, Any]] = []
        self.last_health_check: Dict[str, bool] = {}
        
    def initialize_adapters(self) -> None:
        """初始化所有适配器"""
        adapter_configs = {
            "openharness": {
                "class": "OpenHarnessAdapter",
                "module": "core.framework_abstraction.adapters.openharness_adapter"
            },
            "langgraph": {
                "class": "LangGraphAdapter",
                "module": "core.framework_abstraction.adapters.langgraph_adapter"
            },
            "crewai": {
                "class": "CrewAIAdapter",
                "module": "core.framework_abstraction.adapters.crewai_adapter"
            }
        }
        
        for name, config in adapter_configs.items():
            try:
                module = __import__(config["module"], fromlist=[config["class"]])
                adapter_class = getattr(module, config["class"])
                self.adapters[name] = adapter_class()
                print(f"框架适配器 {name} 已加载")
            except ImportError as e:
                print(f"警告: 无法加载适配器 {name}: {e}")
    
    async def start(self, framework_config: Dict[str, Any]) -> bool:
        """启动框架工厂"""
        self.initialize_adapters()
        
        # 尝试启动主框架
        success = await self._try_start_framework(
            self.config.primary_framework,
            framework_config
        )
        
        if success:
            print(f"主框架 {self.config.primary_framework} 启动成功")
            return True
        
        # 尝试备选框架
        for fallback in self.config.fallback_order or ["langgraph", "crewai"]:
            if fallback in self.adapters:
                success = await self._try_start_framework(fallback, framework_config)
                if success:
                    print(f"备选框架 {fallback} 启动成功")
                    return True
        
        print("错误: 所有框架启动失败")
        return False
    
    async def _try_start_framework(self, framework_name: str, config: Dict[str, Any]) -> bool:
        """尝试启动指定框架"""
        adapter = self.adapters.get(framework_name)
        if not adapter:
            return False
        
        try:
            await adapter.initialize(config)
            self.current_adapter = adapter
            
            # 启动健康检查监控
            if self.config.auto_failover:
                asyncio.create_task(self._monitor_health())
            
            return True
        except Exception as e:
            print(f"框架 {framework_name} 启动失败: {e}")
            return False
    
    async def _monitor_health(self) -> None:
        """监控框架健康状态"""
        while True:
            await asyncio.sleep(self.config.health_check_interval)
            
            if not self.current_adapter:
                continue
            
            try:
                healthy = await self.current_adapter.health_check()
                self.last_health_check[self.current_adapter.framework_type.value] = healthy
                
                if not healthy and self.config.auto_failover:
                    print(f"框架 {self.current_adapter.framework_type.value} 健康检查失败，尝试故障转移")
                    await self._perform_failover()
            except Exception as e:
                print(f"健康检查异常: {e}")
                if self.config.auto_failover:
                    await self._perform_failover()
    
    async def _perform_failover(self) -> None:
        """执行故障转移"""
        current_name = self.current_adapter.framework_type.value
        
        for framework_name, adapter in self.adapters.items():
            if framework_name != current_name:
                try:
                    # 检查备选框架是否健康
                    if await adapter.health_check():
                        print(f"故障转移到 {framework_name}")
                        
                        # 记录故障转移
                        self.failover_history.append({
                            "timestamp": datetime.now(),
                            "from": current_name,
                            "to": framework_name,
                            "reason": "health_check_failed"
                        })
                        
                        self.current_adapter = adapter
                        return
                except Exception:
                    continue
        
        print("警告: 所有备选框架均不可用，保持当前状态")
    
    async def execute_with_framework(self, agent_id: str, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """使用当前框架执行任务"""
        if not self.current_adapter:
            raise RuntimeError("没有可用的框架适配器")
        
        try:
            return await self.current_adapter.execute_task(agent_id, task, context)
        except Exception as e:
            if self.config.auto_failover:
                print(f"任务执行失败，尝试故障转移: {e}")
                await self._perform_failover()
                
                # 使用新的框架重试
                if self.current_adapter:
                    return await self.current_adapter.execute_task(agent_id, task, context)
            
            raise
```

### 10.6 配置文件示例
```yaml
# config/framework_factory.yaml
framework_factory:
  primary_framework: "openharness"
  fallback_order:
    - "langgraph"
    - "crewai"
  
  health_check:
    enabled: true
    interval_seconds: 30
    auto_failover: true
  
  adapters:
    openharness:
      model_provider: "openai"
      model_name: "gpt-4-turbo"
      memory_backend: "graphiti"
      permission_backend: "opa"
    
    langgraph:
      model_provider: "openai"
      model_name: "gpt-4-turbo"
    
    crewai:
      model_provider: "openai"
      model_name: "gpt-4-turbo"
  
  logging:
    level: "INFO"
    failover_log_path: "/var/log/graphiti/failover.log"
```

### 10.7 集成测试
```python
# tests/integration/test_framework_abstraction.py
async def test_framework_failover():
    """测试框架故障转移"""
    # 1. 启动主框架（OpenHarness）
    factory = FrameworkFactory()
    await factory.start({"model_provider": "openai"})
    
    # 2. 模拟主框架故障
    await simulate_framework_failure("openharness")
    
    # 3. 验证故障转移
    await asyncio.sleep(35)  # 等待健康检查
    
    # 4. 执行任务，应自动使用备选框架
    result = await factory.execute_with_framework(
        "commander_agent",
        "分析领域态势",
        {"domain_state": "active"}
    )
    
    assert result["success"] == True
    assert factory.current_adapter.framework_type != FrameworkType.OPENHARNESS
```

## 11. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-11 | 初始版本 |
| 1.1.0 | 2026-04-12 | 新增框架抽象层，支持OpenHarness/LangGraph/CrewAI热切换和故障转移 |

---

**相关文档**:
- [Graphiti 客户端模块设计](../graphiti_client/DESIGN.md)
- [OPA 策略管理模块设计](../opa_policy/DESIGN.md)
- [Skills 领域工具层设计](../skills/DESIGN.md)
- [Swarm 编排模块设计](../swarm_orchestrator/DESIGN.md)
- [安全策略文档](../../security/SECURITY.md)
