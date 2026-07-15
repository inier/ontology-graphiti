"""
工具注册表 - Tool Registry
ODAP 核心模块 M-11

功能：
- Step1(P0): 核心接口 register/discover/execute + SkillExecutor + OPA桥接
- Step2(P1): 语义发现 + 健康监控 + 工具链 + MCP + REST

设计原则：
- 统一注册表管理所有工具（Skill、MCP Tool Server、REST API）
- 支持运行时发现和健康监控
- OPA 权限桥接
"""

import sys
import os
import json
import time
import threading
import hashlib
import re
from typing import Dict, Any, List, Optional, Type, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from odap.tools.base import (
    SkillRegistryV2,
    SkillExecutorV2,
    get_registry_v2,
    SkillStatus,
    HealthStatus,
    SkillHealthInfo,
    BaseSkill,
    SkillInput,
    SkillOutput,
    SkillMetadata,
)

try:
    from infra.opa.opa_service_v2 import OPAManagerV2
except ImportError:
    OPAManagerV2 = None

import logging
_logger = logging.getLogger(__name__)

# ── 审计工具（懒加载 + 容错） ──
def _tool_audit(action: str, *, result_status: str = "success",
                result_message: str = "", resource: str = None,
                details: Dict[str, Any] = None) -> None:
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service="platform_tool",
        )
    except Exception as e:
        _logger.warning(f"audit failed: {e}")


class ToolType(str, Enum):
    SKILL = "skill"
    MCP = "mcp"
    REST = "rest"
    FUNCTION = "function"


class ToolCapability(str, Enum):
    QUERY = "query"
    ACTION = "action"
    TRANSFORM = "transform"
    MONITOR = "monitor"
    ANALYZE = "analyze"


@dataclass
class ToolMetadata:
    """统一工具元数据"""
    name: str
    description: str
    tool_type: str
    category: str
    version: str = "1.0.0"
    danger_level: str = "low"
    capabilities: List[str] = field(default_factory=list)
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    semantic_tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    opa_action: str = ""
    requires_opa_check: bool = False
    rate_limit: int = 100
    timeout_ms: int = 30000
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolRegistration:
    """工具注册信息"""
    tool_id: str
    metadata: ToolMetadata
    tool_type: ToolType
    handler: Any
    status: str = "registered"
    health_info: Optional[SkillHealthInfo] = None
    registered_at: str = ""
    last_modified: str = ""
    call_count: int = 0
    success_count: int = 0
    failed_count: int = 0

    def __post_init__(self):
        if not self.registered_at:
            self.registered_at = datetime.now(timezone.utc).isoformat()
        if not self.last_modified:
            self.last_modified = self.registered_at


@dataclass
class ToolChainStep:
    """工具链步骤"""
    tool_name: str
    input_mapping: Dict[str, str]
    output_mapping: Dict[str, str]
    condition: Optional[str] = None


@dataclass
class ToolChain:
    """工具链定义"""
    chain_id: str
    name: str
    description: str
    steps: List[ToolChainStep]
    version: str = "1.0.0"
    created_at: str = ""
    enabled: bool = True

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class ToolExecutionResult:
    """工具执行结果"""
    tool_id: str
    tool_name: str
    success: bool
    data: Any
    error: Optional[str] = None
    execution_time_ms: float = 0
    timestamp: str = ""
    trace_id: Optional[str] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class MCPToolBridge:
    """MCP Tool Server 桥接器"""

    def __init__(self, mcp_service=None):
        self.mcp_service = mcp_service
        self._tool_cache: Dict[str, ToolMetadata] = {}

    def register_mcp_tools(self, server_name: str, tools: List[Dict]) -> int:
        """注册 MCP 工具到统一注册表"""
        registered = 0
        for tool in tools:
            tool_meta = ToolMetadata(
                name=f"{server_name}:{tool['name']}",
                description=tool.get("description", ""),
                tool_type=ToolType.MCP.value,
                category="mcp",
                capabilities=tool.get("capabilities", []),
                input_schema=tool.get("inputSchema"),
                output_schema=tool.get("outputSchema"),
                semantic_tags=tool.get("tags", []),
                metadata={"server": server_name, "original_name": tool['name']}
            )
            self._tool_cache[tool_meta.name] = tool_meta
            registered += 1
        return registered

    def discover_mcp_tools(self, pattern: str = None) -> List[ToolMetadata]:
        """发现 MCP 工具"""
        tools = list(self._tool_cache.values())
        if pattern:
            pattern_lower = pattern.lower()
            tools = [t for t in tools if pattern_lower in t.name.lower()
                    or pattern_lower in t.description.lower()]
        return tools

    def get_mcp_tool(self, name: str) -> Optional[ToolMetadata]:
        """获取 MCP 工具元数据"""
        return self._tool_cache.get(name)

    async def execute_mcp_tool(self, tool_name: str, input_data: Dict,
                              mcp_service=None) -> ToolExecutionResult:
        """执行 MCP 工具"""
        start_time = time.perf_counter()
        try:
            if mcp_service:
                result = await mcp_service.execute_tool(tool_name, input_data)
            else:
                result = {"error": "MCP service not available"}
            return ToolExecutionResult(
                tool_id=tool_name,
                tool_name=tool_name,
                success=result.get("success", False),
                data=result.get("data", result),
                error=result.get("error"),
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )
        except Exception as e:
            logger.warning("silent except caught in {exc} (line 205)", exc_info=True)
            return ToolExecutionResult(
                tool_id=tool_name,
                tool_name=tool_name,
                success=False,
                data=None,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )


class SemanticToolDiscovery:
    """语义工具发现引擎"""

    def __init__(self):
        self._semantic_index: Dict[str, List[str]] = {}
        self._keyword_index: Dict[str, List[str]] = {}
        self._capability_index: Dict[str, List[str]] = {}
        self._tool_metadata_store: Dict[str, ToolMetadata] = {}

    def index_tool(self, metadata: ToolMetadata):
        """索引工具元数据"""
        self._tool_metadata_store[metadata.name] = metadata
        name_parts = re.split(r'[_\-]', metadata.name.lower())
        for part in name_parts:
            if part not in self._keyword_index:
                self._keyword_index[part] = []
            self._keyword_index[part].append(metadata.name)

        for tag in metadata.semantic_tags:
            if tag not in self._semantic_index:
                self._semantic_index[tag] = []
            self._semantic_index[tag].append(metadata.name)

        for cap in metadata.capabilities:
            if cap not in self._capability_index:
                self._capability_index[cap] = []
            self._capability_index[cap].append(metadata.name)

    def discover_by_semantics(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        基于语义的工具发现

        Args:
            query: 自然语言查询
            top_k: 返回前 k 个结果

        Returns:
            排序后的工具列表（包含相似度分数）
        """
        query_lower = query.lower()
        query_words = re.split(r'[_\-\s]+', query_lower)
        scores: Dict[str, float] = {}

        for tool_name, metadata in self._get_all_indexed_tools():
            score = 0.0

            for word in query_words:
                if word in tool_name.lower():
                    score += 2.0
                if word in metadata.description.lower():
                    score += 1.0
                for tag in metadata.semantic_tags:
                    if word in tag.lower():
                        score += 1.5

            for cap in metadata.capabilities:
                if cap.lower() in query_lower:
                    score += 1.0

            if score > 0:
                scores[tool_name] = score

        sorted_tools = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for tool_name, score in sorted_tools[:top_k]:
            metadata = self._get_tool_metadata(tool_name)
            results.append({
                "tool_name": tool_name,
                "score": score,
                "metadata": metadata
            })
        return results

    def discover_by_capability(self, capability: str) -> List[str]:
        """按能力发现工具"""
        return self._capability_index.get(capability, [])

    def _get_all_indexed_tools(self) -> List[tuple]:
        """获取所有已索引的工具"""
        tools = []
        for name, metadata in self._tool_metadata_store.items():
            tools.append((name, metadata))
        return tools

    def _get_tool_metadata(self, name: str) -> Optional[ToolMetadata]:
        return None


class ToolHealthMonitor:
    """工具健康监控器"""

    def __init__(self):
        self._health_data: Dict[str, SkillHealthInfo] = {}
        self._lock = threading.RLock()
        self._alerts: List[Dict] = []
        self._alert_thresholds = {
            "error_rate_warning": 0.1,
            "error_rate_critical": 0.3,
            "avg_latency_warning_ms": 5000,
            "avg_latency_critical_ms": 10000,
        }

    def record_call(self, tool_name: str, success: bool, latency_ms: float, error: str = None):
        """记录工具调用"""
        with self._lock:
            if tool_name not in self._health_data:
                self._health_data[tool_name] = SkillHealthInfo(
                    name=tool_name,
                    status="registered",
                    health="healthy",
                    registered_at=datetime.now(timezone.utc).isoformat(),
                    last_modified=datetime.now(timezone.utc).isoformat()
                )

            health = self._health_data[tool_name]
            health.total_calls += 1
            if success:
                health.success_calls += 1
            else:
                health.failed_calls += 1
                if error:
                    health.last_error = error

            error_rate = health.failed_calls / health.total_calls if health.total_calls > 0 else 0
            health.avg_execution_time_ms = (
                (health.avg_execution_time_ms * (health.total_calls - 1) + latency_ms) / health.total_calls
            )

            health.health = self._calculate_health(error_rate, health.avg_execution_time_ms)
            health.last_execution_time = datetime.now(timezone.utc).isoformat()
            health.last_modified = datetime.now(timezone.utc).isoformat()

            self._check_alerts(tool_name, health, error_rate)

    def _calculate_health(self, error_rate: float, avg_latency_ms: float) -> str:
        """计算健康状态"""
        if error_rate >= self._alert_thresholds["error_rate_critical"]:
            return HealthStatus.UNHEALTHY.value
        elif error_rate >= self._alert_thresholds["error_rate_warning"]:
            return HealthStatus.DEGRADED.value
        elif avg_latency_ms >= self._alert_thresholds["avg_latency_critical_ms"]:
            return HealthStatus.UNHEALTHY.value
        elif avg_latency_ms >= self._alert_thresholds["avg_latency_warning_ms"]:
            return HealthStatus.DEGRADED.value
        return HealthStatus.HEALTHY.value

    def _check_alerts(self, tool_name: str, health: SkillHealthInfo, error_rate: float):
        """检查告警条件"""
        if health.health == HealthStatus.UNHEALTHY.value:
            self._alerts.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool_name": tool_name,
                "level": "critical",
                "message": f"Tool {tool_name} is unhealthy: error_rate={error_rate:.2%}",
                "health": health
            })
        elif health.health == HealthStatus.DEGRADED.value:
            self._alerts.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool_name": tool_name,
                "level": "warning",
                "message": f"Tool {tool_name} is degraded",
                "health": health
            })

    def get_health(self, tool_name: str) -> Optional[SkillHealthInfo]:
        """获取工具健康信息"""
        return self._health_data.get(tool_name)

    def get_all_health(self) -> List[SkillHealthInfo]:
        """获取所有工具健康状态"""
        return list(self._health_data.values())

    def get_alerts(self, level: str = None) -> List[Dict]:
        """获取告警列表"""
        if level:
            return [a for a in self._alerts if a["level"] == level]
        return self._alerts

    def clear_alerts(self, tool_name: str = None):
        """清除告警"""
        if tool_name:
            self._alerts = [a for a in self._alerts if a["tool_name"] != tool_name]
        else:
            self._alerts = []


class ToolRegistry:
    """
    统一工具注册表

    管理所有类型的工具：
    - Skill (BaseSkill)
    - MCP (MCP Tool Server)
    - REST (外部 REST API)
    - Function (原生函数)
    """

    def __init__(self, opa_manager: OPAManagerV2 = None):
        self._tools: Dict[str, ToolRegistration] = {}
        self._skill_registry = get_registry_v2()
        self._mcp_bridge = MCPToolBridge()
        self._semantic_discovery = SemanticToolDiscovery()
        self._health_monitor = ToolHealthMonitor()
        self._opa_manager = opa_manager
        self._tool_chains: Dict[str, ToolChain] = {}
        self._lock = threading.RLock()
        self._execution_history: List[ToolExecutionResult] = []
        self._max_history_size = 1000

    def register_skill(self, skill: BaseSkill, version: str = "1.0.0",
                      changelog: str = "") -> bool:
        """
        注册 Skill 工具

        Args:
            skill: BaseSkill 实例
            version: 版本号
            changelog: 变更日志

        Returns:
            是否注册成功
        """
        with self._lock:
            tool_id = f"skill:{skill.metadata.name}"

            metadata = ToolMetadata(
                name=skill.metadata.name,
                description=skill.metadata.description,
                tool_type=ToolType.SKILL.value,
                category=skill.metadata.category,
                version=version,
                danger_level=skill.metadata.danger_level,
                capabilities=self._category_to_capabilities(skill.metadata.category),
                input_schema=self._get_skill_input_schema(skill),
                semantic_tags=self._extract_semantic_tags(skill),
                opa_action=skill.metadata.opa_action,
                requires_opa_check=skill.metadata.requires_opa_check
            )

            registration = ToolRegistration(
                tool_id=tool_id,
                metadata=metadata,
                tool_type=ToolType.SKILL,
                handler=skill
            )

            self._tools[tool_id] = registration
            self._skill_registry.register(skill, version, changelog)
            self._semantic_discovery.index_tool(metadata)

            _tool_audit(
                action="tool_register_skill",
                result_status="success",
                resource=tool_id,
                details={
                    "tool_id": tool_id,
                    "tool_name": skill.metadata.name,
                    "category": skill.metadata.category,
                    "version": version,
                    "danger_level": skill.metadata.danger_level,
                },
            )

            return True

    def register_mcp_server(self, server_name: str, tools: List[Dict]) -> int:
        """注册 MCP Tool Server"""
        count = self._mcp_bridge.register_mcp_tools(server_name, tools)
        for tool in self._mcp_bridge.discover_mcp_tools():
            tool_id = f"mcp:{tool.name}"
            registration = ToolRegistration(
                tool_id=tool_id,
                metadata=tool,
                tool_type=ToolType.MCP,
                handler=None
            )
            self._tools[tool_id] = registration
            self._semantic_discovery.index_tool(tool)
        _tool_audit(
            action="tool_register_mcp_server",
            result_status="success",
            resource=server_name,
            details={
                "server_name": server_name,
                "tools_count": count,
                "item_count": count,
            },
        )
        return count

    def register_rest_api(self, name: str, description: str, endpoint: str,
                          method: str = "POST", category: str = "api",
                          input_schema: Dict = None, output_schema: Dict = None) -> bool:
        """注册 REST API 工具"""
        with self._lock:
            tool_id = f"rest:{name}"

            metadata = ToolMetadata(
                name=name,
                description=description,
                tool_type=ToolType.REST.value,
                category=category,
                input_schema=input_schema,
                output_schema=output_schema,
                metadata={"endpoint": endpoint, "method": method}
            )

            registration = ToolRegistration(
                tool_id=tool_id,
                metadata=metadata,
                tool_type=ToolType.REST,
                handler=None
            )

            self._tools[tool_id] = registration
            self._semantic_discovery.index_tool(metadata)

            return True

    def register_function(self, name: str, description: str, func: Callable,
                         category: str = "function") -> bool:
        """注册原生函数工具"""
        with self._lock:
            tool_id = f"func:{name}"

            metadata = ToolMetadata(
                name=name,
                description=description,
                tool_type=ToolType.FUNCTION.value,
                category=category,
                metadata={"is_native": True}
            )

            registration = ToolRegistration(
                tool_id=tool_id,
                metadata=metadata,
                tool_type=ToolType.FUNCTION,
                handler=func
            )

            self._tools[tool_id] = registration
            self._semantic_discovery.index_tool(metadata)

            _tool_audit(
                action="tool_register_function",
                result_status="success",
                resource=tool_id,
                details={
                    "tool_id": tool_id,
                    "tool_name": name,
                    "category": category,
                },
            )

            return True

    def discover(self, pattern: str = None, tool_type: str = None,
                category: str = None, capability: str = None,
                semantic_query: str = None) -> List[Dict[str, Any]]:
        """
        发现工具

        支持多种发现方式：
        - pattern: 名称模式匹配
        - tool_type: 按类型过滤
        - category: 按分类过滤
        - capability: 按能力过滤
        - semantic_query: 语义查询

        Returns:
            工具列表（包含健康信息）
        """
        if semantic_query:
            semantic_results = self._semantic_discovery.discover_by_semantics(semantic_query)
            tool_ids = [f"{r['metadata'].tool_type}:{r['tool_name']}" for r in semantic_results]
            results = []
            for tool_id in tool_ids:
                if tool_id in self._tools:
                    results.append(self._format_tool_info(self._tools[tool_id]))
            return results

        tools = []
        for tool_id, reg in self._tools.items():
            if pattern and pattern.lower() not in reg.metadata.name.lower():
                continue
            if tool_type and reg.metadata.tool_type != tool_type:
                continue
            if category and reg.metadata.category != category:
                continue
            if capability and capability not in reg.metadata.capabilities:
                continue

            tools.append(self._format_tool_info(reg))

        return tools

    def execute(self, tool_name: str, input_data: Dict,
               user: Dict = None, trace_id: str = None) -> ToolExecutionResult:
        """
        执行工具

        Args:
            tool_name: 工具名称
            input_data: 输入数据
            user: 用户信息（用于 OPA 权限检查）
            trace_id: 追踪 ID

        Returns:
            ToolExecutionResult
        """
        start_time = time.perf_counter()

        tool_id = self._resolve_tool_id(tool_name)
        if not tool_id or tool_id not in self._tools:
            _tool_audit(
                action="tool_execute",
                result_status="failure",
                result_message=f"Tool not found: {tool_name}"[:200],
                resource=tool_name,
                details={"tool_name": tool_name},
            )
            return ToolExecutionResult(
                tool_id=tool_name,
                tool_name=tool_name,
                success=False,
                data=None,
                error=f"Tool not found: {tool_name}",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                trace_id=trace_id
            )

        reg = self._tools[tool_id]

        if user and reg.metadata.requires_opa_check and self._opa_manager:
            if not self._check_permission(user, reg):
                _tool_audit(
                    action="tool_execute",
                    result_status="failure",
                    result_message="Permission denied",
                    resource=tool_id,
                    details={
                        "tool_id": tool_id,
                        "tool_name": tool_name,
                    },
                )
                return ToolExecutionResult(
                    tool_id=tool_id,
                    tool_name=tool_name,
                    success=False,
                    data=None,
                    error="Permission denied",
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                    trace_id=trace_id
                )

        try:
            if reg.tool_type == ToolType.SKILL:
                result = self._execute_skill(reg, input_data)
            elif reg.tool_type == ToolType.FUNCTION:
                result = self._execute_function(reg, input_data)
            elif reg.tool_type == ToolType.MCP:
                result = self._execute_mcp(reg, input_data)
            elif reg.tool_type == ToolType.REST:
                result = self._execute_rest(reg, input_data)
            else:
                result = ToolExecutionResult(
                    tool_id=tool_id,
                    tool_name=tool_name,
                    success=False,
                    data=None,
                    error=f"Unknown tool type: {reg.tool_type}",
                    trace_id=trace_id
                )

            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            self._update_execution_stats(reg, result.success)
            self._health_monitor.record_call(
                tool_name, result.success, result.execution_time_ms, result.error
            )
            self._add_to_history(result)

            _tool_audit(
                action="tool_execute",
                result_status="success" if result.success else "failure",
                result_message="" if result.success else (result.error or "")[:200],
                resource=tool_id,
                details={
                    "tool_id": tool_id,
                    "tool_name": tool_name,
                    "tool_type": reg.tool_type.value if hasattr(reg.tool_type, 'value') else str(reg.tool_type),
                    "execution_time_ms": round(result.execution_time_ms, 1),
                    "item_count": 1,
                },
            )

            return result

        except Exception as e:
            logger.warning("silent except caught in {exc} (line 650)", exc_info=True)
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            self._update_execution_stats(reg, False)
            self._health_monitor.record_call(tool_name, False, execution_time_ms, str(e))

            _tool_audit(
                action="tool_execute",
                result_status="failure",
                result_message=str(e)[:200],
                resource=tool_id,
                details={
                    "tool_id": tool_id,
                    "tool_name": tool_name,
                    "execution_time_ms": round(execution_time_ms, 1),
                },
            )

            return ToolExecutionResult(
                tool_id=tool_id,
                tool_name=tool_name,
                success=False,
                data=None,
                error=str(e),
                execution_time_ms=execution_time_ms,
                trace_id=trace_id
            )

    async def execute_async(self, tool_name: str, input_data: Dict,
                           user: Dict = None, trace_id: str = None) -> ToolExecutionResult:
        """异步执行工具"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute, tool_name, input_data, user, trace_id)

    def execute_chain(self, chain_id: str, initial_input: Dict,
                     user: Dict = None) -> List[ToolExecutionResult]:
        """
        执行工具链

        Args:
            chain_id: 工具链 ID
            initial_input: 初始输入
            user: 用户信息

        Returns:
            执行结果列表
        """
        if chain_id not in self._tool_chains:
            raise ValueError(f"Tool chain not found: {chain_id}")

        chain = self._tool_chains[chain_id]
        results = []
        context = initial_input.copy()

        for step in chain.steps:
            if step.condition and not self._evaluate_condition(step.condition, context):
                continue

            step_input = self._map_input(step.input_mapping, context)
            result = self.execute(step.tool_name, step_input, user)
            results.append(result)

            if result.success:
                context.update(self._map_output(step.output_mapping, result.data))
            else:
                break

        return results

    def register_tool_chain(self, chain: ToolChain) -> bool:
        """注册工具链"""
        with self._lock:
            self._tool_chains[chain.chain_id] = chain
            return True

    def get_tool_chain(self, chain_id: str) -> Optional[ToolChain]:
        """获取工具链"""
        return self._tool_chains.get(chain_id)

    def list_tool_chains(self) -> List[ToolChain]:
        """列出所有工具链"""
        return list(self._tool_chains.values())

    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        health_list = self._health_monitor.get_all_health()

        healthy = sum(1 for h in health_list if h.health == HealthStatus.HEALTHY.value)
        degraded = sum(1 for h in health_list if h.health == HealthStatus.DEGRADED.value)
        unhealthy = sum(1 for h in health_list if h.health == HealthStatus.UNHEALTHY.value)

        total_calls = sum(h.total_calls for h in health_list)
        total_success = sum(h.success_calls for h in health_list)

        return {
            "total_tools": len(self._tools),
            "healthy_count": healthy,
            "degraded_count": degraded,
            "unhealthy_count": unhealthy,
            "total_calls": total_calls,
            "total_success": total_success,
            "overall_success_rate": (total_success / total_calls * 100) if total_calls > 0 else 0,
            "alerts": self._health_monitor.get_alerts(),
            "tools": health_list
        }

    def get_execution_history(self, limit: int = 100) -> List[ToolExecutionResult]:
        """获取执行历史"""
        return self._execution_history[-limit:]

    def _resolve_tool_id(self, tool_name: str) -> Optional[str]:
        """解析工具 ID"""
        if tool_name in self._tools:
            return tool_name

        for tool_id, reg in self._tools.items():
            if reg.metadata.name == tool_name:
                return tool_id

        for tool_id, reg in self._tools.items():
            if tool_id.endswith(f":{tool_name}"):
                return tool_id

        return None

    def _check_permission(self, user: Dict, reg: ToolRegistration) -> bool:
        """检查 OPA 权限"""
        if not self._opa_manager:
            return True

        user_role = user.get("role", "guest")
        action = reg.metadata.opa_action or f"{reg.metadata.tool_type}:{reg.metadata.name}"

        return self._opa_manager.check_permission(
            user_role, action, {"type": reg.metadata.tool_type, "id": reg.metadata.name}
        )

    def _execute_skill(self, reg: ToolRegistration, input_data: Dict) -> ToolExecutionResult:
        """执行 Skill"""
        executor = self._skill_registry.get_executor()
        output = executor.execute(reg.metadata.name, input_data)

        return ToolExecutionResult(
            tool_id=reg.tool_id,
            tool_name=reg.metadata.name,
            success=output.success,
            data=output.data,
            error=output.error
        )

    def _execute_function(self, reg: ToolRegistration, input_data: Dict) -> ToolExecutionResult:
        """执行原生函数"""
        try:
            result = reg.handler(**input_data)
            return ToolExecutionResult(
                tool_id=reg.tool_id,
                tool_name=reg.metadata.name,
                success=True,
                data=result
            )
        except Exception as e:
            logger.warning("silent except caught in {exc} (line 798)", exc_info=True)
            return ToolExecutionResult(
                tool_id=reg.tool_id,
                tool_name=reg.metadata.name,
                success=False,
                data=None,
                error=str(e)
            )

    def _execute_mcp(self, reg: ToolRegistration, input_data: Dict) -> ToolExecutionResult:
        """执行 MCP 工具"""
        return ToolExecutionResult(
            tool_id=reg.tool_id,
            tool_name=reg.metadata.name,
            success=False,
            data=None,
            error="MCP execution requires async call"
        )

    def _execute_rest(self, reg: ToolRegistration, input_data: Dict) -> ToolExecutionResult:
        """执行 REST API"""
        return ToolExecutionResult(
            tool_id=reg.tool_id,
            tool_name=reg.metadata.name,
            success=False,
            data=None,
            error="REST execution not implemented"
        )

    def _update_execution_stats(self, reg: ToolRegistration, success: bool):
        """更新执行统计"""
        reg.call_count += 1
        if success:
            reg.success_count += 1
        else:
            reg.failed_count += 1
        reg.last_modified = datetime.now(timezone.utc).isoformat()

    def _add_to_history(self, result: ToolExecutionResult):
        """添加执行历史"""
        self._execution_history.append(result)
        if len(self._execution_history) > self._max_history_size:
            self._execution_history = self._execution_history[-self._max_history_size:]

    def _format_tool_info(self, reg: ToolRegistration) -> Dict[str, Any]:
        """格式化工具信息"""
        health = self._health_monitor.get_health(reg.metadata.name)
        return {
            "tool_id": reg.tool_id,
            "name": reg.metadata.name,
            "description": reg.metadata.description,
            "tool_type": reg.metadata.tool_type,
            "category": reg.metadata.category,
            "version": reg.metadata.version,
            "danger_level": reg.metadata.danger_level,
            "capabilities": reg.metadata.capabilities,
            "status": reg.status,
            "call_count": reg.call_count,
            "success_count": reg.success_count,
            "failed_count": reg.failed_count,
            "health": health.health if health else "unknown",
            "registered_at": reg.registered_at,
            "last_modified": reg.last_modified
        }

    def _category_to_capabilities(self, category: str) -> List[str]:
        """将分类映射为能力列表"""
        mapping = {
            "intelligence": ["query", "analyze"],
            "operations": ["action", "monitor"],
            "analysis": ["analyze", "transform"],
            "recommendation": ["query", "analyze"],
            "visualization": ["transform"],
            "planning": ["analyze", "query"],
            "policy": ["query", "action"],
            "computation": ["transform"],
            "ontology": ["query", "analyze"],
            "task_management": ["action", "monitor"],
        }
        return mapping.get(category.lower(), ["query"])

    def _get_skill_input_schema(self, skill: BaseSkill) -> Optional[Dict[str, Any]]:
        """获取 Skill 输入 Schema"""
        if skill.input_schema:
            return skill.input_schema.model_json_schema() if hasattr(skill.input_schema, 'model_json_schema') else {}
        return None

    def _extract_semantic_tags(self, skill: BaseSkill) -> List[str]:
        """提取语义标签"""
        tags = []
        tags.extend(skill.metadata.category.split('_'))
        desc_words = re.findall(r'\w+', skill.metadata.description.lower())
        tags.extend([w for w in desc_words if len(w) > 3])
        return list(set(tags))

    def _map_input(self, mapping: Dict[str, str], context: Dict) -> Dict:
        """映射输入"""
        result = {}
        for target_key, source_key in mapping.items():
            if '.' in source_key:
                parts = source_key.split('.')
                value = context
                for part in parts:
                    value = value.get(part, {}) if isinstance(value, dict) else {}
                result[target_key] = value
            else:
                result[target_key] = context.get(source_key, None)
        return result

    def _map_output(self, mapping: Dict[str, str], data: Any) -> Dict:
        """映射输出"""
        if not isinstance(data, dict):
            return {}
        result = {}
        for target_key, source_key in mapping.items():
            if '.' in source_key:
                parts = source_key.split('.')
                value = data
                for part in parts:
                    value = value.get(part, {}) if isinstance(value, dict) else {}
                result[target_key] = value
            else:
                result[target_key] = data.get(source_key, None)
        return result

    def _evaluate_condition(self, condition: str, context: Dict) -> bool:
        """评估条件表达式（使用 AST 安全求值器替代 eval）"""
        try:
            from odap.biz.core.ontology.application.runtime.state_machine.impl.expression_evaluator import safe_eval

            return safe_eval(condition, {"context": context})
        except Exception:
            logger.warning("silent except caught in {exc} (line 930)", exc_info=True)
            return False


_global_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry(opa_manager: OPAManagerV2 = None) -> ToolRegistry:
    """获取全局工具注册表"""
    global _global_tool_registry
    if _global_tool_registry is None:
        _global_tool_registry = ToolRegistry(opa_manager)
    return _global_tool_registry


if __name__ == "__main__":
    registry = get_tool_registry()

    logger.info('=' * 60)
    logger.info('工具注册表初始化测试')
    logger.info('=' * 60)

    class TestSkillInput(SkillInput):
        value: int = 0

    class TestSkill(BaseSkill):
        metadata = SkillMetadata(
            name="test_skill",
            description="测试技能，用于验证工具注册表",
            category="analysis",
        )
        input_schema = TestSkillInput

        def execute(self, input_data: SkillInput) -> SkillOutput:
            return SkillOutput(
                success=True,
                data={"result": input_data.value * 2},
                execution_time_ms=0,
                skill_name=self.metadata.name,
                request_id=input_data.request_id
            )

    logger.info('\n1. 注册 Skill 工具:')
    registry.register_skill(TestSkill(), version="1.0.0", changelog="初始版本")
    logger.info('   ✓ Skill 注册成功')

    logger.info('\n2. 注册原生函数:')
    def calculate(x: int, y: int) -> int:
        return x + y

    registry.register_function("add", "加法运算", calculate, category="computation")
    logger.info('   ✓ 函数注册成功')

    logger.info('\n3. 工具发现:')
    tools = registry.discover()
    logger.info(f'   发现 {len(tools)} 个工具')

    logger.info('\n4. 执行 Skill:')
    result = registry.execute("test_skill", {"value": 21})
    logger.info(f'   执行结果: {result.success}')
    logger.info(f'   输出数据: {result.data}')

    logger.info('\n5. 执行原生函数:')
    result = registry.execute("add", {"x": 10, "y": 20})
    logger.info(f'   执行结果: {result.success}')
    logger.info(f'   输出数据: {result.data}')

    logger.info('\n6. 健康报告:')
    report = registry.get_health_report()
    logger.info(f"   总工具数: {report['total_tools']}")
    logger.info(f"   健康数: {report['healthy_count']}")
    logger.info(f"   总调用数: {report['total_calls']}")

    logger.info('\n' + '=' * 60)
    logger.info('工具注册表测试完成')
    logger.info('=' * 60)