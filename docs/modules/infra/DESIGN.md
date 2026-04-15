# Infrastructure 基础设施模块 - 设计文档

> **优先级**: P0 | **相关 ADR**: ADR-002, ADR-003

**版本**: 1.1.0 | **日期**: 2026-04-16

---

## 1. 模块概述

基础设施模块包含系统运行所需的核心底层组件，为上层业务逻辑提供基础服务。

**核心组件**:

| 组件 | 位置 | 职责 |
|------|------|------|
| Graph | `odap/infra/graph/` | 知识图谱管理（Graphiti） |
| OPA | `odap/infra/opa/` | 策略引擎（权限控制） |
| Events | `odap/infra/events/` | 事件系统（Hook） |
| LLM | `odap/infra/llm/` | LLM 接口封装 |
| Resilience | `odap/infra/resilience/` | 容错机制 |
| Config | `odap/infra/config/` | 配置管理 |

---

## 2. 核心架构

```
odap/infra/
├── graph/                # 知识图谱基础设施
│   ├── graph_service.py  # GraphManager (核心类)
│   └── __init__.py
├── opa/                  # OPA 策略引擎
│   ├── opa_service.py    # OPAManager
│   └── opa_policy.rego   # 策略规则
├── events/              # 事件系统
│   └── hook_system.py    # Hook 管理
├── llm/                 # LLM 接口
│   └── llm_service.py    # ZhipuAIClient
├── resilience/          # 容错机制
│   ├── fault_tolerance.py    # 故障恢复
│   ├── health_monitor.py     # 健康监控
│   └── state_persistence.py  # 状态持久化
└── config/              # 配置管理
    └── __init__.py
```

---

## 3. Graph 模块

### 3.1 GraphManager

知识图谱核心管理类，基于 Graphiti 实现双时态知识图谱。

**类图**:

```python
class GraphManager:
    """知识图谱管理器 - 支持多层降级策略"""

    def __init__(
        self,
        name: str = "default",
        uri: str = "http://localhost:7474",
        auth: tuple = None,
        drop_all: bool = False
    ):
        """
        初始化 GraphManager

        降级策略:
        1. Neo4j + Graphiti: 完整功能
        2. Neo4j Only: 禁用 RAG 和时间旅行
        3. Mock Mode: 内存模拟（开发/测试）
        """

    def create_episode(
        self,
        content: str,
        summary: str = None,
        episode_type: str = "default",
        metadata: dict = None
    ) -> Optional[str]:
        """创建事件 episodes"""

    def search(
        self,
        query: str,
        mode: str = "auto",
        time_range: tuple = None,
        limit: int = 10
    ) -> list:
        """语义搜索实体"""

    def get_statistics(self) -> dict:
        """获取图谱统计信息"""
```

### 3.2 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `create_episode()` | 创建事件 episod | episode_id 或 None |
| `search()` | 语义搜索 | 实体列表 |
| `query_entities()` | 图查询 | 实体字典 |
| `update_entity()` | 更新实体属性 | bool |
| `get_statistics()` | 获取统计 | dict |
| `retrieve_rag_context()` | RAG 上下文检索 | str |

### 3.3 降级策略

```python
# 降级策略优先级
FALLBACK_PRIORITY = [
    "neo4j_graphiti",  # 完整功能
    "neo4j_only",       # 禁用 RAG
    "mock",            # 内存模拟
]

# 降级触发条件
FALLBACK_TRIGGERS = {
    "neo4j_graphiti": "Neo4j 可用且 Graphiti 可用",
    "neo4j_only": "Neo4j 可用但 Graphiti 不可用",
    "mock": "Neo4j 不可用",
}
```

---

## 4. OPA 模块

### 4.1 OPAManager

策略引擎管理类，基于 Open Policy Agent 实现权限控制。

**类图**:

```python
class OPAManager:
    """OPA 策略管理器"""

    def __init__(self, opa_url: str = "http://localhost:8181"):
        self.opa_url = opa_url
        self._client = httpx.Client(timeout=5.0)
        self.mock_mode = not self._check_opa_health()

    def check_permission(
        self,
        user_role: str,
        action: str,
        resource: str,
        context: dict = None
    ) -> bool:
        """
        检查权限

        参数:
        - user_role: 用户角色 (commander/analyst/observer)
        - action: 操作类型 (attack/defend/query/...)
        - resource: 资源类型 (entity/location/...)
        - context: 额外上下文
        """

    def _check_opa_health(self) -> bool:
        """检查 OPA Server 健康状态"""

    def _evaluate_mock(self, user_role, action, resource) -> bool:
        """Mock 模式评估"""
```

### 4.2 策略检查流程

```
┌─────────────────────────────────────────────────────────────┐
│                    check_permission()                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  OPA Server 可用?      │
              └───────────┬───────────┘
                    Yes   │   No
                    ┌─────┴─────┐
                    ▼           ▼
          ┌────────────┐  ┌────────────┐
          │ POST /v1/ │  │ Mock 模式   │
          │ data/...  │  │ 本地评估    │
          └─────┬──────┘  └─────┬──────┘
                │               │
                └───────┬───────┘
                        ▼
              ┌───────────────────────┐
              │     返回决策结果       │
              │   allow: true/false   │
              └───────────────────────┘
```

### 4.3 Rego 策略结构

```rego
package domain.authz

default allow = false

# 指挥官可以执行攻击操作
allow {
    input.user_role == "commander"
    input.action == "attack"
    input.resource == "entity"
}

# 情报分析员可以查询
allow {
    input.user_role == "analyst"
    input.action == "query"
}

# 观察员只读
allow {
    input.user_role == "observer"
    input.action == "query"
}
```

---

## 5. LLM 模块

### 5.1 ZhipuAIClient

智谱 AI API 客户端，兼容 OpenAI Client 接口。

**类图**:

```python
class ZhipuAIClient:
    """智谱 AI 客户端"""

    def __init__(
        self,
        api_key: str = None,
        model: str = "glm-4",
        base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    ):
        self.api_key = api_key or os.getenv('ZHIPU_API_KEY', '')
        self.model = model
        self.base_url = base_url

    def chat completions(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> dict:
        """发送聊天请求"""
```

### 5.2 配置

```python
# 环境变量
ZHIPU_API_KEY = os.getenv('ZHIPU_API_KEY', '')
LLM_API_BASE = os.getenv('LLM_API_BASE', 'https://open.bigmodel.cn/api/paas/v4')
LLM_MODEL = os.getenv('LLM_MODEL', 'glm-4')
```

---

## 6. Resilience 模块

### 6.1 FaultRecoveryManager

故障恢复与断路器模式实现。

**类图**:

```python
class FaultRecoveryManager:
    """故障恢复管理器"""

    def __init__(self):
        self._circuit_breakers: dict = {}
        self._retry_policies: dict = {}
        self._fallback_handlers: dict = {}

    def execute_with_circuit_breaker(
        self,
        func: callable,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60
    ) -> Any:
        """带断路器的执行"""

    def execute_with_retry(
        self,
        func: callable,
        max_retries: int = 3,
        backoff_factor: float = 2.0
    ) -> Any:
        """带重试的执行"""
```

### 6.2 HealthMonitor

系统健康状态监控。

**类图**:

```python
class HealthMonitor:
    """健康监控器"""

    def __init__(self):
        self._health_checks: dict = {}
        self._metrics: dict = defaultdict(list)

    async def check_service_health(self, service_name: str) -> dict:
        """检查服务健康状态"""

    def record_metric(self, metric_name: str, value: float):
        """记录指标"""

    def get_system_health(self) -> dict:
        """获取系统整体健康状态"""
```

### 6.3 StatePersistenceManager

Agent 状态和任务检查点持久化。

**类图**:

```python
class StatePersistenceManager:
    """状态持久化管理器"""

    def __init__(self, storage_path: str = "./data/states"):
        self.storage_path = storage_path

    def save_checkpoint(
        self,
        agent_id: str,
        state: dict,
        task_id: str = None
    ) -> str:
        """保存检查点"""

    def load_checkpoint(self, checkpoint_id: str) -> dict:
        """加载检查点"""

    def list_checkpoints(self, agent_id: str) -> list:
        """列出检查点"""
```

---

## 7. Events 模块

### 7.1 Hook 系统

事件钩子管理，支持插件化扩展。

**类图**:

```python
class HookManager:
    """Hook 管理器"""

    def __init__(self):
        self._hooks: dict = defaultdict(list)

    def register_hook(
        self,
        event_type: str,
        handler: callable,
        priority: int = 0
    ):
        """注册钩子"""

    def trigger_event(
        self,
        event_type: str,
        context: dict = None
    ):
        """触发事件"""

    def unregister_hook(self, event_type: str, handler: callable):
        """注销钩子"""
```

---

## 8. Config 模块

### 8.1 配置结构

```python
# 配置优先级
CONFIG_PRIORITY = [
    "环境变量",
    "config.yaml",
    "config.default.yaml",
]

# 核心配置项
CORE_CONFIG = {
    # Neo4j 配置
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USER": "neo4j",
    "NEO4J_PASSWORD": "",

    # OPA 配置
    "OPA_URL": "http://localhost:8181",

    # LLM 配置
    "LLM_API_KEY": "",
    "LLM_API_BASE": "",
    "LLM_MODEL": "glm-4",

    # 存储配置
    "STORAGE_PATH": "./odap/storage",
}
```

---

## 9. 模块依赖

```
┌─────────────────────────────────────────────────────────────┐
│                       业务层 (biz/)                          │
├─────────────────────────────────────────────────────────────┤
│  Agent  │  Ontology  │  Simulator  │  Skills  │  Visualization │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    基础设施层 (infra/)                        │
├─────────────────────────────────────────────────────────────┤
│ Graph │  OPA  │  Events  │  LLM  │  Resilience  │  Config │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       外部服务                                │
├─────────────────────────────────────────────────────────────┤
│  Neo4j  │  Graphiti  │  OPA Server  │  LLM API  │  Redis  │
└─────────────────────────────────────────────────────────────┘
```

---

## 10. 相关文档

- [ADR-002: Graphiti 作为双时态知识图谱](../../adr/ADR-002_graphiti_作为双时态知识图谱.md)
- [ADR-003: OPA 策略治理引擎](../../adr/ADR-003_opa_策略治理引擎mvp_生产化.md)
- [Graphiti Client 模块](../graphiti_client/DESIGN.md)
- [OPA Policy 模块](../opa_policy/DESIGN.md)
- [Hook System 模块](../hook_system/DESIGN.md)
