# Swarm 编排模块设计文档

> **优先级**: P0 | **相关 ADR**: ADR-005, ADR-025

## 1. 模块概述

### 1.1 模块定位

`swarm_orchestrator` 是基于 OpenHarness Swarm 的多 Agent 协同编排器，实现领域三 Agent（Commander/Intelligence/Operations）的 OODA 循环协同。

### 1.2 核心职责

| 职责 | 描述 |
|------|------|
| Agent 注册 | 三 Agent 的注册和配置 |
| 任务分发 | OODA 各阶段任务的分发 |
| 结果聚合 | 多 Agent 结果的聚合和协调 |
| 状态管理 | Agent 状态的跟踪和管理 |

---

## 2. 接口设计

### 2.1 DomainSwarm 主接口

```python
# core/swarm_orchestrator/swarm.py
from typing import Dict, Any, List, Optional, AsyncGenerator
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class AgentType(str, Enum):
    """Agent 类型"""
    COMMANDER = "commander"
    INTELLIGENCE = "intelligence"
    OPERATIONS = "operations"

class OODAPhase(str, Enum):
    """OODA 阶段"""
    OBSERVE = "observe"
    ORIENT = "orient"
    DECIDE = "decide"
    ACT = "act"

class OODAProgress(BaseModel):
    """OODA 执行进度"""
    phase: OODAPhase
    status: str  # started/completed/waiting_confirmation/error
    agent: AgentType
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class MissionResult(BaseModel):
    """任务执行结果"""
    mission_id: str
    success: bool
    phases_completed: List[OODAPhase]
    final_decision: Optional[Dict[str, Any]] = None
    execution_time_ms: float
    graphiti_episodes: List[str] = Field(default_factory=list)

class DomainSwarm:
    """领域多 Agent Swarm"""

    def __init__(self, config: Dict[str, Any]): ...

    async def initialize(self) -> None: ...

    async def execute_mission(
        self,
        mission: str,
        context: Optional[Dict[str, Any]] = None
    ) -> MissionResult: ...

    async def execute_streaming(
        self,
        mission: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[OODAProgress, None]: ...

    async def shutdown(self) -> None: ...
```

### 2.2 Agent 配置

```python
# core/swarm_orchestrator/agent_config.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class AgentConfig(BaseModel):
    """Agent 配置"""
    name: str
    agent_type: AgentType
    model: str
    role: str
    tools: List[str]
    permission_level: str
    memory_backend: str = "graphiti"
    system_prompt_template: str
    requires_opa_approval: bool = False

class CommanderConfig(AgentConfig):
    """Commander Agent 配置"""
    agent_type: AgentType = AgentType.COMMANDER
    model: str = "claude-3-5-sonnet"
    permission_level: str = "commander"
    tools: List[str] = ["*"]  # 全工具权限

class IntelligenceConfig(AgentConfig):
    """Intelligence Agent 配置"""
    agent_type: AgentType = AgentType.INTELLIGENCE
    model: str = "deepseek-chat"
    permission_level: str = "intelligence"
    tools: List[str] = [
        "radar_*", "drone_*", "satellite_*",
        "threat_*", "pattern_*", "intelligence_*"
    ]
    memory_backend: str = "graphiti"

class OperationsConfig(AgentConfig):
    """Operations Agent 配置"""
    agent_type: AgentType = AgentType.OPERATIONS
    model: str = "qwen-plus"
    permission_level: str = "operations"
    tools: List[str] = [
        "attack_*", "command_*", "route_*", "weapon_*"
    ]
    requires_opa_approval: bool = True
```

---

## 3. OODA 循环实现

### 3.1 OODA 流程

```python
# core/swarm_orchestrator/ooda_loop.py
class OODALoop:
    """OODA 循环执行器"""

    async def execute(
        self,
        mission: str,
        context: Optional[Dict[str, Any]] = None
    ) -> MissionResult:
        """
        执行 OODA 循环

        流程: Observe → Orient → Decide → Act → (循环)
        """
        # 阶段 1: Observe
        observe_result = await self._observe(mission, context)

        # 阶段 2: Orient
        orient_result = await self._orient(observe_result, context)

        # 阶段 3: Decide
        decide_result = await self._decide(orient_result, context)

        # 阶段 4: Act
        act_result = await self._act(decide_result, context)

        # 回写 Graphiti
        await self._write_episodes({
            "observe": observe_result,
            "orient": orient_result,
            "decide": decide_result,
            "act": act_result
        })

        return MissionResult(...)

    async def _observe(
        self,
        mission: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Observe 阶段 - Intelligence 感知"""
        return await self.coordinator.delegate(
            agent=self.intelligence,
            task=f"感知领域: {mission}"
        )

    async def _orient(
        self,
        observe_result: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Orient 阶段 - Intelligence 理解"""
        return await self.coordinator.delegate(
            agent=self.intelligence,
            task=f"分析威胁: {observe_result}",
            context={"graphiti_episodes": await self.get_historical()}
        )

    async def _decide(
        self,
        orient_result: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Decide 阶段 - Commander 决策"""
        options = await self.operations.generate_options(
            orient_result["targets"]
        )
        return await self.coordinator.delegate(
            agent=self.commander,
            task=f"制定打击方案: {orient_result}",
            context={"options": options}
        )

    async def _act(
        self,
        decide_result: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Act 阶段 - Operations 执行"""
        if decide_result.get("requires_confirmation"):
            confirmed = await self._wait_confirmation(decide_result)
            if not confirmed:
                return {"status": "cancelled"}

        return await self.coordinator.delegate(
            agent=self.operations,
            task=f"执行命令: {decide_result['final_order']}"
        )
```

---

## 4. 配置示例

```yaml
# config/swarm_orchestrator.yaml
swarm_orchestrator:
  # OpenHarness Coordinator
  coordinator:
    max_parallel_agents: 3
    task_timeout_seconds: 300
    retry_attempts: 2

  # Agent 配置
  agents:
    commander:
      model: "claude-3-5-sonnet"
      permission_level: "commander"
      tools: ["*"]

    intelligence:
      model: "deepseek-chat"
      permission_level: "intelligence"
      tools:
        - "radar_*"
        - "drone_*"
        - "satellite_*"
        - "threat_*"

    operations:
      model: "qwen-plus"
      permission_level: "operations"
      tools:
        - "attack_*"
        - "command_*"
        - "route_*"

  # OODA 配置
  ooda:
    enable_streaming: true
    confirm_before_act: true
    write_to_graphiti: true
```

---

## 5. 故障恢复与状态管理

### 5.1 状态机与故障恢复管理器
```python
# core/swarm_orchestrator/fault_tolerance.py
from enum import Enum
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass

class AgentState(Enum):
    """Agent执行状态"""
    IDLE = "idle"
    RUNNING = "running"
    FAILED = "failed"
    DEGRADED = "degraded"  # 降级运行
    RECOVERING = "recovering"
    SUSPENDED = "suspended"  # 人工暂停

class FailureType(Enum):
    """故障类型"""
    AGENT_TIMEOUT = "agent_timeout"
    OPA_DENIAL = "opa_denial"
    GRAPHITI_UNAVAILABLE = "graphiti_unavailable"
    NETWORK_ERROR = "network_error"
    TOOL_EXECUTION_ERROR = "tool_execution_error"
    UNEXPECTED_EXCEPTION = "unexpected_exception"

@dataclass
class FailureRecord:
    """故障记录"""
    timestamp: datetime
    agent_id: str
    failure_type: FailureType
    error_message: str
    recovery_attempts: int = 0
    resolved: bool = False

class FaultRecoveryManager:
    """故障恢复管理器"""
    
    def __init__(self):
        self.agent_states: Dict[str, AgentState] = {}
        self.failure_history: List[FailureRecord] = []
        self.failure_count: Dict[str, int] = {}
        self.recovery_strategies: Dict[FailureType, str] = {
            FailureType.AGENT_TIMEOUT: "retry_with_backoff",
            FailureType.OPA_DENIAL: "escalate_to_commander",
            FailureType.GRAPHITI_UNAVAILABLE: "use_cache_fallback",
            FailureType.NETWORK_ERROR: "retry_with_backoff",
            FailureType.TOOL_EXECUTION_ERROR: "try_alternative_tool",
            FailureType.UNEXPECTED_EXCEPTION: "restart_agent"
        }
        
        # 配置参数
        self.max_retries = 3
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_reset_time = 300  # 5分钟
        self.circuit_breaker_state: Dict[str, Dict[str, Any]] = {}
    
    async def handle_failure(self, agent_id: str, error: Exception, 
                           failure_type: FailureType = None) -> Dict[str, Any]:
        """智能故障处理"""
        # 识别故障类型
        if failure_type is None:
            failure_type = self._classify_failure(error)
        
        # 记录故障
        record = FailureRecord(
            timestamp=datetime.now(),
            agent_id=agent_id,
            failure_type=failure_type,
            error_message=str(error)
        )
        self.failure_history.append(record)
        
        # 更新故障计数
        self.failure_count[agent_id] = self.failure_count.get(agent_id, 0) + 1
        
        # 检查断路器状态
        if self._is_circuit_breaker_open(agent_id):
            return await self._handle_circuit_breaker_open(agent_id)
        
        # 根据故障类型执行恢复策略
        recovery_action = self.recovery_strategies.get(failure_type, "retry_with_backoff")
        
        if recovery_action == "retry_with_backoff":
            return await self._retry_with_backoff(agent_id, error, record)
        elif recovery_action == "escalate_to_commander":
            return await self._escalate_to_commander(agent_id, error, record)
        elif recovery_action == "use_cache_fallback":
            return await self._use_cache_fallback(agent_id, error, record)
        elif recovery_action == "try_alternative_tool":
            return await self._try_alternative_tool(agent_id, error, record)
        elif recovery_action == "restart_agent":
            return await self._restart_agent(agent_id, error, record)
        
        # 默认降级
        return await self._activate_degraded_mode(agent_id, error, record)
    
    def _classify_failure(self, error: Exception) -> FailureType:
        """根据异常信息分类故障类型"""
        error_str = str(error).lower()
        
        if "timeout" in error_str or "timed out" in error_str:
            return FailureType.AGENT_TIMEOUT
        elif "permission denied" in error_str or "opa" in error_str:
            return FailureType.OPA_DENIAL
        elif "graphiti" in error_str or "neo4j" in error_str:
            return FailureType.GRAPHITI_UNAVAILABLE
        elif "connection" in error_str or "network" in error_str:
            return FailureType.NETWORK_ERROR
        elif "tool" in error_str or "skill" in error_str:
            return FailureType.TOOL_EXECUTION_ERROR
        else:
            return FailureType.UNEXPECTED_EXCEPTION
    
    async def _retry_with_backoff(self, agent_id: str, error: Exception, 
                                record: FailureRecord) -> Dict[str, Any]:
        """指数退避重试"""
        attempt = record.recovery_attempts + 1
        
        if attempt > self.max_retries:
            # 重试次数用尽，触发断路器
            self._trip_circuit_breaker(agent_id)
            return await self._activate_degraded_mode(agent_id, error, record)
        
        # 计算延迟时间（指数退避：1, 2, 4, 8秒...）
        delay = 2 ** (attempt - 1)
        print(f"Agent {agent_id} 重试尝试 {attempt}/{self.max_retries}，延迟 {delay}秒")
        
        await asyncio.sleep(delay)
        
        # 更新重试次数
        record.recovery_attempts = attempt
        
        return {
            "action": "retry",
            "attempt": attempt,
            "delay_seconds": delay,
            "circuit_breaker_state": "closed"
        }
    
    async def _escalate_to_commander(self, agent_id: str, error: Exception, 
                                   record: FailureRecord) -> Dict[str, Any]:
        """升级到指挥官决策"""
        print(f"Agent {agent_id} 权限被拒绝，升级到指挥官决策")
        
        # 记录升级事件
        from core.swarm_orchestrator.coordinator import Coordinator
        coordinator = Coordinator.get_instance()
        
        await coordinator.escalate_to_commander(
            agent_id=agent_id,
            reason=f"OPA权限拒绝: {error}",
            context={"failure_record": record}
        )
        
        return {
            "action": "escalate",
            "escalated_to": "commander",
            "reason": "opa_denial",
            "circuit_breaker_state": "closed"
        }
    
    async def _use_cache_fallback(self, agent_id: str, error: Exception, 
                                record: FailureRecord) -> Dict[str, Any]:
        """使用缓存回退"""
        print(f"Agent {agent_id} Graphiti不可用，使用缓存回退")
        
        # 切换到缓存模式
        self.agent_states[agent_id] = AgentState.DEGRADED
        
        from core.cache_manager import CacheManager
        cache = CacheManager.get_instance()
        
        # 尝试从缓存获取最近数据
        cached_data = await cache.get(f"agent_{agent_id}_last_state")
        
        return {
            "action": "fallback",
            "fallback_type": "cache",
            "cached_data_available": cached_data is not None,
            "agent_state": "degraded",
            "circuit_breaker_state": "half_open"
        }
    
    async def _try_alternative_tool(self, agent_id: str, error: Exception, 
                                  record: FailureRecord) -> Dict[str, Any]:
        """尝试替代工具"""
        print(f"Agent {agent_id} 工具执行失败，尝试替代工具")
        
        from core.skill_registry import SkillRegistry
        registry = SkillRegistry.get_instance()
        
        # 分析当前使用的工具
        error_tool = self._extract_tool_name(error)
        
        # 寻找替代工具
        alternatives = registry.find_alternative_tools(error_tool)
        
        if alternatives:
            return {
                "action": "alternative_tool",
                "failed_tool": error_tool,
                "alternative_tools": alternatives,
                "recommended_tool": alternatives[0],
                "circuit_breaker_state": "closed"
            }
        else:
            # 没有替代工具，降级运行
            return await self._activate_degraded_mode(agent_id, error, record)
    
    async def _restart_agent(self, agent_id: str, error: Exception, 
                           record: FailureRecord) -> Dict[str, Any]:
        """重启Agent"""
        print(f"Agent {agent_id} 发生意外异常，尝试重启")
        
        # 标记为恢复中
        self.agent_states[agent_id] = AgentState.RECOVERING
        
        from core.swarm_orchestrator.agent_manager import AgentManager
        agent_manager = AgentManager.get_instance()
        
        try:
            # 停止当前Agent
            await agent_manager.stop_agent(agent_id)
            
            # 重新启动
            await asyncio.sleep(2)  # 等待资源清理
            await agent_manager.start_agent(agent_id)
            
            self.agent_states[agent_id] = AgentState.IDLE
            record.resolved = True
            
            return {
                "action": "restart",
                "restart_successful": True,
                "agent_state": "idle",
                "circuit_breaker_state": "closed"
            }
        except Exception as restart_error:
            print(f"Agent {agent_id} 重启失败: {restart_error}")
            return await self._activate_degraded_mode(agent_id, error, record)
    
    async def _activate_degraded_mode(self, agent_id: str, error: Exception, 
                                    record: FailureRecord) -> Dict[str, Any]:
        """激活降级模式"""
        print(f"Agent {agent_id} 进入降级模式")
        
        self.agent_states[agent_id] = AgentState.DEGRADED
        
        # 根据Agent类型执行不同的降级策略
        if "intelligence" in agent_id:
            # Intelligence Agent降级：使用缓存数据，减少查询频率
            return {
                "action": "degraded",
                "degraded_mode": "cached_intelligence",
                "capabilities": ["read_only_cache", "basic_analysis"],
                "limitations": ["no_real_time_data", "no_direct_queries"],
                "circuit_breaker_state": "open"
            }
        elif "operations" in agent_id:
            # Operations Agent降级：切换到手动模式，只执行基本命令
            return {
                "action": "degraded",
                "degraded_mode": "manual_operations",
                "capabilities": ["basic_commands", "status_reporting"],
                "limitations": ["no_autonomous_actions", "no_complex_planning"],
                "circuit_breaker_state": "open"
            }
        elif "commander" in agent_id:
            # Commander Agent降级：使用预定义决策树
            return {
                "action": "degraded",
                "degraded_mode": "rule_based_commander",
                "capabilities": ["predefined_rules", "basic_decision_making"],
                "limitations": ["no_ai_analysis", "no_adaptive_strategies"],
                "circuit_breaker_state": "open"
            }
        else:
            return {
                "action": "degraded",
                "degraded_mode": "basic_functionality",
                "circuit_breaker_state": "open"
            }
    
    def _is_circuit_breaker_open(self, agent_id: str) -> bool:
        """检查断路器是否打开"""
        if agent_id not in self.circuit_breaker_state:
            return False
        
        state = self.circuit_breaker_state[agent_id]
        
        if state["state"] == "open":
            # 检查是否超过重置时间
            opened_at = state["opened_at"]
            reset_time = timedelta(seconds=self.circuit_breaker_reset_time)
            
            if datetime.now() - opened_at > reset_time:
                # 进入半开状态，允许一个测试请求
                state["state"] = "half_open"
                state["test_request_sent"] = False
                return False
            else:
                return True
        
        return False
    
    def _trip_circuit_breaker(self, agent_id: str):
        """触发断路器"""
        self.circuit_breaker_state[agent_id] = {
            "state": "open",
            "opened_at": datetime.now(),
            "failure_count": self.failure_count.get(agent_id, 0),
            "last_error": self.failure_history[-1].error_message if self.failure_history else ""
        }
        
        print(f"断路器已触发: {agent_id}，状态: open")
    
    async def _handle_circuit_breaker_open(self, agent_id: str) -> Dict[str, Any]:
        """处理断路器打开状态"""
        state = self.circuit_breaker_state[agent_id]
        time_remaining = self.circuit_breaker_reset_time - (datetime.now() - state["opened_at"]).total_seconds()
        
        return {
            "action": "circuit_breaker_open",
            "state": "open",
            "time_remaining_seconds": max(0, time_remaining),
            "failure_count": state["failure_count"],
            "recommendation": "等待断路器重置或切换到降级模式"
        }
    
    def _extract_tool_name(self, error: Exception) -> Optional[str]:
        """从异常中提取工具名称"""
        error_str = str(error)
        
        # 简单的模式匹配
        import re
        
        # 匹配 "tool 'xxx' failed" 模式
        tool_pattern = r"tool\s+['\"]([^'\"]+)['\"]"
        match = re.search(tool_pattern, error_str, re.IGNORECASE)
        
        if match:
            return match.group(1)
        
        # 匹配 "skill 'xxx' error" 模式
        skill_pattern = r"skill\s+['\"]([^'\"]+)['\"]"
        match = re.search(skill_pattern, error_str, re.IGNORECASE)
        
        if match:
            return match.group(1)
        
        return None
```

### 5.2 状态持久化与恢复
```python
# core/swarm_orchestrator/state_persistence.py
import json
import pickle
from typing import Dict, Any, Optional
from datetime import datetime
import os

class StatePersistenceManager:
    """状态持久化管理器"""
    
    def __init__(self, persistence_path: str = "/var/lib/graphiti/swarm_state"):
        self.persistence_path = persistence_path
        os.makedirs(persistence_path, exist_ok=True)
    
    async def save_state(self, agent_id: str, state: Dict[str, Any]) -> bool:
        """保存Agent状态"""
        try:
            state_file = os.path.join(self.persistence_path, f"{agent_id}_state.json")
            
            # 添加元数据
            state_with_meta = {
                "agent_id": agent_id,
                "timestamp": datetime.now().isoformat(),
                "data": state
            }
            
            # 写入文件
            with open(state_file, 'w') as f:
                json.dump(state_with_meta, f, indent=2, default=str)
            
            # 创建备份
            backup_file = os.path.join(self.persistence_path, f"{agent_id}_state_backup.pkl")
            with open(backup_file, 'wb') as f:
                pickle.dump(state_with_meta, f)
            
            return True
        except Exception as e:
            print(f"状态保存失败: {e}")
            return False
    
    async def load_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """加载Agent状态"""
        try:
            # 首先尝试JSON文件
            state_file = os.path.join(self.persistence_path, f"{agent_id}_state.json")
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    state_data = json.load(f)
                    return state_data.get("data")
            
            # 如果JSON文件不存在，尝试备份文件
            backup_file = os.path.join(self.persistence_path, f"{agent_id}_state_backup.pkl")
            if os.path.exists(backup_file):
                with open(backup_file, 'rb') as f:
                    state_data = pickle.load(f)
                    return state_data.get("data")
            
            return None
        except Exception as e:
            print(f"状态加载失败: {e}")
            return None
    
    async def save_checkpoint(self, mission_id: str, checkpoint_data: Dict[str, Any]) -> bool:
        """保存任务检查点"""
        try:
            checkpoint_file = os.path.join(self.persistence_path, f"checkpoint_{mission_id}.json")
            
            checkpoint = {
                "mission_id": mission_id,
                "timestamp": datetime.now().isoformat(),
                "data": checkpoint_data,
                "version": "1.0"
            }
            
            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint, f, indent=2, default=str)
            
            return True
        except Exception as e:
            print(f"检查点保存失败: {e}")
            return False
    
    async def load_checkpoint(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """加载任务检查点"""
        try:
            checkpoint_file = os.path.join(self.persistence_path, f"checkpoint_{mission_id}.json")
            
            if os.path.exists(checkpoint_file):
                with open(checkpoint_file, 'r') as f:
                    checkpoint = json.load(f)
                    return checkpoint.get("data")
            
            return None
        except Exception as e:
            print(f"检查点加载失败: {e}")
            return None
    
    async def resume_from_checkpoint(self, mission_id: str) -> Dict[str, Any]:
        """从检查点恢复任务"""
        checkpoint_data = await self.load_checkpoint(mission_id)
        
        if not checkpoint_data:
            return {"status": "no_checkpoint", "message": "没有找到检查点"}
        
        # 恢复Agent状态
        recovered_agents = []
        for agent_state in checkpoint_data.get("agent_states", []):
            agent_id = agent_state["agent_id"]
            
            # 恢复Agent状态
            await self._restore_agent_state(agent_id, agent_state)
            recovered_agents.append(agent_id)
        
        # 恢复OODA阶段
        current_phase = checkpoint_data.get("current_phase")
        phase_data = checkpoint_data.get("phase_data", {})
        
        return {
            "status": "resumed",
            "mission_id": mission_id,
            "recovered_agents": recovered_agents,
            "current_phase": current_phase,
            "phase_data": phase_data,
            "checkpoint_timestamp": checkpoint_data.get("timestamp")
        }
    
    async def _restore_agent_state(self, agent_id: str, agent_state: Dict[str, Any]):
        """恢复Agent状态"""
        from core.swarm_orchestrator.agent_manager import AgentManager
        
        agent_manager = AgentManager.get_instance()
        
        # 如果Agent不存在，重新创建
        if not agent_manager.agent_exists(agent_id):
            await agent_manager.create_agent(
                agent_id=agent_id,
                config=agent_state.get("config", {})
            )
        
        # 恢复内存状态
        memory_state = agent_state.get("memory_state")
        if memory_state:
            await agent_manager.restore_agent_memory(agent_id, memory_state)
```

### 5.3 健康检查与监控
```python
# core/swarm_orchestrator/health_monitor.py
import asyncio
from typing import Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass

@dataclass
class HealthMetric:
    """健康指标"""
    name: str
    value: float
    unit: str
    threshold_warning: float
    threshold_critical: float
    timestamp: datetime

class HealthMonitor:
    """健康监控器"""
    
    def __init__(self, check_interval: int = 60):  # 60秒检查间隔
        self.check_interval = check_interval
        self.metrics_history: Dict[str, List[HealthMetric]] = {}
        self.alerts: List[Dict[str, Any]] = []
        self.monitoring_tasks = []
    
    async def start_monitoring(self):
        """启动健康监控"""
        print("启动Swarm健康监控...")
        
        # 创建监控任务
        tasks = [
            self._monitor_agent_health(),
            self._monitor_system_resources(),
            self._monitor_external_dependencies(),
            self._monitor_performance_metrics()
        ]
        
        self.monitoring_tasks = [asyncio.create_task(task) for task in tasks]
    
    async def stop_monitoring(self):
        """停止健康监控"""
        for task in self.monitoring_tasks:
            task.cancel()
        
        try:
            await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        
        print("Swarm健康监控已停止")
    
    async def _monitor_agent_health(self):
        """监控Agent健康状态"""
        while True:
            try:
                from core.swarm_orchestrator.agent_manager import AgentManager
                agent_manager = AgentManager.get_instance()
                
                agents = agent_manager.get_all_agents()
                
                for agent_id, agent in agents.items():
                    # 检查Agent响应时间
                    response_time = await self._measure_response_time(agent)
                    
                    metric = HealthMetric(
                        name=f"agent_{agent_id}_response_time",
                        value=response_time,
                        unit="ms",
                        threshold_warning=1000,  # 1秒警告
                        threshold_critical=5000,  # 5秒严重
                        timestamp=datetime.now()
                    )
                    
                    await self._record_metric(metric)
                    
                    # 检查故障次数
                    from core.swarm_orchestrator.fault_tolerance import FaultRecoveryManager
                    fault_manager = FaultRecoveryManager.get_instance()
                    
                    failure_count = fault_manager.failure_count.get(agent_id, 0)
                    
                    metric = HealthMetric(
                        name=f"agent_{agent_id}_failure_count",
                        value=failure_count,
                        unit="count",
                        threshold_warning=3,  # 3次警告
                        threshold_critical=10,  # 10次严重
                        timestamp=datetime.now()
                    )
                    
                    await self._record_metric(metric)
                    
                    # 生成警报
                    if failure_count >= 10:
                        await self._generate_alert(
                            level="critical",
                            agent_id=agent_id,
                            metric="failure_count",
                            value=failure_count,
                            message=f"Agent {agent_id} 故障次数过多"
                        )
                
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                print(f"Agent健康监控异常: {e}")
                await asyncio.sleep(10)  # 发生异常时缩短等待时间
    
    async def _monitor_system_resources(self):
        """监控系统资源"""
        while True:
            try:
                import psutil
                
                # CPU使用率
                cpu_percent = psutil.cpu_percent(interval=1)
                metric = HealthMetric(
                    name="system_cpu_usage",
                    value=cpu_percent,
                    unit="percent",
                    threshold_warning=80,  # 80%警告
                    threshold_critical=95,  # 95%严重
                    timestamp=datetime.now()
                )
                await self._record_metric(metric)
                
                # 内存使用率
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                metric = HealthMetric(
                    name="system_memory_usage",
                    value=memory_percent,
                    unit="percent",
                    threshold_warning=85,  # 85%警告
                    threshold_critical=95,  # 95%严重
                    timestamp=datetime.now()
                )
                await self._record_metric(metric)
                
                # 磁盘使用率
                disk = psutil.disk_usage('/')
                disk_percent = disk.percent
                metric = HealthMetric(
                    name="system_disk_usage",
                    value=disk_percent,
                    unit="percent",
                    threshold_warning=90,  # 90%警告
                    threshold_critical=95,  # 95%严重
                    timestamp=datetime.now()
                )
                await self._record_metric(metric)
                
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                print(f"系统资源监控异常: {e}")
                await asyncio.sleep(10)
    
    async def _monitor_external_dependencies(self):
        """监控外部依赖"""
        while True:
            try:
                # 检查Graphiti连接
                from core.graphiti_client import GraphitiClient
                graphiti_client = GraphitiClient.get_instance()
                
                graphiti_healthy = await graphiti_client.health_check()
                metric = HealthMetric(
                    name="graphiti_health",
                    value=1 if graphiti_healthy else 0,
                    unit="boolean",
                    threshold_warning=0.5,
                    threshold_critical=0,
                    timestamp=datetime.now()
                )
                await self._record_metric(metric)
                
                # 检查OPA连接
                from core.opa_client import OPAClient
                opa_client = OPAClient.get_instance()
                
                opa_healthy = await opa_client.health_check()
                metric = HealthMetric(
                    name="opa_health",
                    value=1 if opa_healthy else 0,
                    unit="boolean",
                    threshold_warning=0.5,
                    threshold_critical=0,
                    timestamp=datetime.now()
                )
                await self._record_metric(metric)
                
                # 检查模型API连接
                model_healthy = await self._check_model_api()
                metric = HealthMetric(
                    name="model_api_health",
                    value=1 if model_healthy else 0,
                    unit="boolean",
                    threshold_warning=0.5,
                    threshold_critical=0,
                    timestamp=datetime.now()
                )
                await self._record_metric(metric)
                
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                print(f"外部依赖监控异常: {e}")
                await asyncio.sleep(10)
    
    async def _monitor_performance_metrics(self):
        """监控性能指标"""
        while True:
            try:
                from core.swarm_orchestrator.coordinator import Coordinator
                coordinator = Coordinator.get_instance()
                
                # 任务执行时间
                avg_execution_time = coordinator.get_average_execution_time()
                metric = HealthMetric(
                    name="average_task_execution_time",
                    value=avg_execution_time,
                    unit="ms",
                    threshold_warning=30000,  # 30秒警告
                    threshold_critical=60000,  # 60秒严重
                    timestamp=datetime.now()
                )
                await self._record_metric(metric)
                
                # 任务成功率
                success_rate = coordinator.get_task_success_rate()
                metric = HealthMetric(
                    name="task_success_rate",
                    value=success_rate * 100,
                    unit="percent",
                    threshold_warning=90,  # 90%警告
                    threshold_critical=80,  # 80%严重
                    timestamp=datetime.now()
                )
                await self._record_metric(metric)
                
                # OODA循环完成时间
                ooda_cycle_time = coordinator.get_average_ooda_cycle_time()
                metric = HealthMetric(
                    name="average_ooda_cycle_time",
                    value=ooda_cycle_time,
                    unit="ms",
                    threshold_warning=120000,  # 2分钟警告
                    threshold_critical=300000,  # 5分钟严重
                    timestamp=datetime.now()
                )
                await self._record_metric(metric)
                
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                print(f"性能指标监控异常: {e}")
                await asyncio.sleep(10)
    
    async def _measure_response_time(self, agent) -> float:
        """测量Agent响应时间"""
        import time
        
        start_time = time.time()
        
        try:
            # 发送一个简单的ping请求
            response = await agent.ping()
            if response:
                return (time.time() - start_time) * 1000  # 转换为毫秒
            else:
                return float('inf')
        except Exception:
            return float('inf')
    
    async def _check_model_api(self) -> bool:
        """检查模型API连接"""
        try:
            import aiohttp
            
            # 这里需要根据实际使用的模型API进行调整
            test_prompt = {"prompt": "test", "max_tokens": 1}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:8000/v1/completions",
                    json=test_prompt,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False
    
    async def _record_metric(self, metric: HealthMetric):
        """记录指标"""
        if metric.name not in self.metrics_history:
            self.metrics_history[metric.name] = []
        
        self.metrics_history[metric.name].append(metric)
        
        # 保持最近1000个记录
        if len(self.metrics_history[metric.name]) > 1000:
            self.metrics_history[metric.name] = self.metrics_history[metric.name][-1000:]
        
        # 检查阈值
        if metric.value >= metric.threshold_critical:
            await self._generate_alert(
                level="critical",
                metric_name=metric.name,
                value=metric.value,
                threshold=metric.threshold_critical,
                message=f"指标 {metric.name} 达到严重阈值: {metric.value}{metric.unit}"
            )
        elif metric.value >= metric.threshold_warning:
            await self._generate_alert(
                level="warning",
                metric_name=metric.name,
                value=metric.value,
                threshold=metric.threshold_warning,
                message=f"指标 {metric.name} 达到警告阈值: {metric.value}{metric.unit}"
            )
    
    async def _generate_alert(self, level: str, **kwargs):
        """生成警报"""
        alert = {
            "level": level,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        self.alerts.append(alert)
        
        # 发送警报通知
        await self._send_alert_notification(alert)
        
        print(f"警报生成: {alert}")
    
    async def _send_alert_notification(self, alert: Dict[str, Any]):
        """发送警报通知"""
        # 这里可以实现发送到监控系统、Slack、邮件等
        # 例如: send_to_slack(f"[{alert['level'].upper()}] {alert['message']}")
        pass
    
    async def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "components": {},
            "alerts": self.alerts[-100:],  # 最近100个警报
            "recommendations": []
        }
        
        # 评估各组件状态
        components = [
            ("agent_health", "Agent健康"),
            ("system_resources", "系统资源"),
            ("external_dependencies", "外部依赖"),
            ("performance", "性能指标")
        ]
        
        for component_key, component_name in components:
            component_status = await self._evaluate_component_status(component_key)
            report["components"][component_key] = {
                "name": component_name,
                "status": component_status["status"],
                "metrics": component_status["metrics"],
                "issues": component_status["issues"]
            }
            
            if component_status["status"] != "healthy":
                report["overall_status"] = "degraded"
                report["recommendations"].extend(component_status["recommendations"])
        
        return report
    
    async def _evaluate_component_status(self, component_key: str) -> Dict[str, Any]:
        """评估组件状态"""
        if component_key == "agent_health":
            return await self._evaluate_agent_health()
        elif component_key == "system_resources":
            return await self._evaluate_system_resources()
        elif component_key == "external_dependencies":
            return await self._evaluate_external_dependencies()
        elif component_key == "performance":
            return await self._evaluate_performance()
        else:
            return {
                "status": "unknown",
                "metrics": [],
                "issues": [],
                "recommendations": []
            }
    
    async def _evaluate_agent_health(self) -> Dict[str, Any]:
        """评估Agent健康状态"""
        from core.swarm_orchestrator.fault_tolerance import FaultRecoveryManager
        
        fault_manager = FaultRecoveryManager.get_instance()
        issues = []
        recommendations = []
        
        # 检查是否有Agent处于降级模式
        degraded_agents = [
            agent_id for agent_id, state in fault_manager.agent_states.items()
            if state in [AgentState.DEGRADED, AgentState.FAILED]
        ]
        
        if degraded_agents:
            issues.append(f"有{len(degraded_agents)}个Agent处于降级/失败状态")
            recommendations.append("检查故障恢复管理器日志，确定故障原因并尝试恢复")
        
        # 检查断路器状态
        open_circuit_breakers = [
            agent_id for agent_id, state in fault_manager.circuit_breaker_state.items()
            if state.get("state") == "open"
        ]
        
        if open_circuit_breakers:
            issues.append(f"有{len(open_circuit_breakers)}个断路器处于打开状态")
            recommendations.append("等待断路器重置或手动重置受影响的Agent")
        
        return {
            "status": "healthy" if not issues else "degraded",
            "metrics": [],
            "issues": issues,
            "recommendations": recommendations
        }
    
    async def _evaluate_system_resources(self) -> Dict[str, Any]:
        """评估系统资源状态"""
        import psutil
        
        issues = []
        recommendations = []
        
        # 检查CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 95:
            issues.append(f"CPU使用率过高: {cpu_percent}%")
            recommendations.append("减少并发任务或优化资源密集型操作")
        elif cpu_percent > 80:
            issues.append(f"CPU使用率警告: {cpu_percent}%")
            recommendations.append("监控CPU使用率，考虑优化或扩容")
        
        # 检查内存
        memory = psutil.virtual_memory()
        if memory.percent > 95:
            issues.append(f"内存使用率过高: {memory.percent}%")
            recommendations.append("减少内存使用或增加系统内存")
        elif memory.percent > 85:
            issues.append(f"内存使用率警告: {memory.percent}%")
            recommendations.append("优化内存使用，考虑增加swap或扩容")
        
        # 检查磁盘
        disk = psutil.disk_usage('/')
        if disk.percent > 95:
            issues.append(f"磁盘使用率过高: {disk.percent}%")
            recommendations.append("清理磁盘空间或扩容存储")
        elif disk.percent > 90:
            issues.append(f"磁盘使用率警告: {disk.percent}%")
            recommendations.append("监控磁盘使用，计划清理或扩容")
        
        return {
            "status": "healthy" if not issues else "degraded",
            "metrics": [
                {"name": "cpu_usage", "value": cpu_percent, "unit": "percent"},
                {"name": "memory_usage", "value": memory.percent, "unit": "percent"},
                {"name": "disk_usage", "value": disk.percent, "unit": "percent"}
            ],
            "issues": issues,
            "recommendations": recommendations
        }
    
    async def _evaluate_external_dependencies(self) -> Dict[str, Any]:
        """评估外部依赖状态"""
        issues = []
        recommendations = []
        metrics = []
        
        # 检查Graphiti
        from core.graphiti_client import GraphitiClient
        try:
            graphiti_client = GraphitiClient.get_instance()
            graphiti_healthy = await graphiti_client.health_check()
            
            metrics.append({
                "name": "graphiti_health",
                "value": 1 if graphiti_healthy else 0,
                "unit": "boolean"
            })
            
            if not graphiti_healthy:
                issues.append("Graphiti连接异常")
                recommendations.append("检查Graphiti服务和网络连接")
        except Exception as e:
            issues.append(f"Graphiti检查失败: {str(e)}")
            recommendations.append("检查Graphiti客户端配置和连接")
        
        # 检查OPA
        from core.opa_client import OPAClient
        try:
            opa_client = OPAClient.get_instance()
            opa_healthy = await opa_client.health_check()
            
            metrics.append({
                "name": "opa_health",
                "value": 1 if opa_healthy else 0,
                "unit": "boolean"
            })
            
            if not opa_healthy:
                issues.append("OPA连接异常")
                recommendations.append("检查OPA服务和网络连接")
        except Exception as e:
            issues.append(f"OPA检查失败: {str(e)}")
            recommendations.append("检查OPA客户端配置和连接")
        
        return {
            "status": "healthy" if not issues else "degraded",
            "metrics": metrics,
            "issues": issues,
            "recommendations": recommendations
        }
    
    async def _evaluate_performance(self) -> Dict[str, Any]:
        """评估性能状态"""
        from core.swarm_orchestrator.coordinator import Coordinator
        
        issues = []
        recommendations = []
        metrics = []
        
        try:
            coordinator = Coordinator.get_instance()
            
            # 任务成功率
            success_rate = coordinator.get_task_success_rate()
            metrics.append({
                "name": "task_success_rate",
                "value": success_rate * 100,
                "unit": "percent"
            })
            
            if success_rate < 0.8:
                issues.append(f"任务成功率过低: {success_rate*100:.1f}%")
                recommendations.append("检查任务失败原因，优化错误处理")
            elif success_rate < 0.9:
                issues.append(f"任务成功率警告: {success_rate*100:.1f}%")
                recommendations.append("监控任务执行，识别并解决常见失败模式")
            
            # 平均执行时间
            avg_execution_time = coordinator.get_average_execution_time()
            metrics.append({
                "name": "average_task_execution_time",
                "value": avg_execution_time,
                "unit": "ms"
            })
            
            if avg_execution_time > 60000:  # 60秒
                issues.append(f"任务执行时间过长: {avg_execution_time/1000:.1f}秒")
                recommendations.append("优化任务分解或增加并发处理")
            elif avg_execution_time > 30000:  # 30秒
                issues.append(f"任务执行时间警告: {avg_execution_time/1000:.1f}秒")
                recommendations.append("监控任务性能，识别瓶颈")
            
        except Exception as e:
            issues.append(f"性能评估失败: {str(e)}")
            recommendations.append("检查Coordinator服务和数据收集")
        
        return {
            "status": "healthy" if not issues else "degraded",
            "metrics": metrics,
            "issues": issues,
            "recommendations": recommendations
        }
```

## 6. 配置示例增强

```yaml
# config/swarm_orchestrator.yaml
swarm_orchestrator:
  # OpenHarness Coordinator
  coordinator:
    max_parallel_agents: 3
    task_timeout_seconds: 300
    retry_attempts: 2
  
  # Agent 配置
  agents:
    commander:
      model: "claude-3-5-sonnet"
      permission_level: "commander"
      tools: ["*"]
    
    intelligence:
      model: "deepseek-chat"
      permission_level: "intelligence"
      tools:
        - "radar_*"
        - "drone_*"
        - "satellite_*"
        - "threat_*"
    
    operations:
      model: "qwen-plus"
      permission_level: "operations"
      tools:
        - "attack_*"
        - "command_*"
        - "route_*"
  
  # OODA 配置
  ooda:
    enable_streaming: true
    confirm_before_act: true
    write_to_graphiti: true
  
  # 故障恢复配置
  fault_tolerance:
    max_retries: 3
    circuit_breaker_threshold: 5
    circuit_breaker_reset_seconds: 300
    degraded_mode_enabled: true
    fallback_strategies:
      - "retry_with_backoff"
      - "use_cache_fallback"
      - "try_alternative_tool"
      - "escalate_to_commander"
      - "activate_degraded_mode"
  
  # 状态持久化配置
  state_persistence:
    enabled: true
    persistence_path: "/var/lib/graphiti/swarm_state"
    checkpoint_interval_seconds: 60
    max_checkpoints_per_mission: 10
  
  # 健康监控配置
  health_monitoring:
    enabled: true
    check_interval_seconds: 60
    alert_channels:
      - "log"
      - "slack"
      # - "email"  # 可选
      # - "webhook"  # 可选
    thresholds:
      cpu_warning_percent: 80
      cpu_critical_percent: 95
      memory_warning_percent: 85
      memory_critical_percent: 95
      disk_warning_percent: 90
      disk_critical_percent: 95
      task_success_warning_percent: 90
      task_success_critical_percent: 80
```

## 7. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-11 | 初始版本 |
| 1.1.0 | 2026-04-12 | 新增故障恢复机制、状态持久化、健康监控和断路器模式 |

---

**相关文档**:
- [OpenHarness 桥接模块设计](../openharness_bridge/DESIGN.md)
- [Skills 领域工具层设计](../skills/DESIGN.md)
- [Decision Recommendation 决策推荐模块设计](../decision_recommendation/DESIGN.md)
- [安全策略文档](../../security/SECURITY.md)
