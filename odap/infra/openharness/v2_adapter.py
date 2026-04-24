"""
OpenHarness v2 深度整合适配器

基于 OpenHarness v2 的 BaseTool 架构，构建完整的 Agent Loop 系统。
"""

import json
import os
import sys
import time
import asyncio
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

# 配置 OpenHarness 路径
OPENHARNESS_SRC = os.environ.get(
    'OPENHARNESS_PATH',
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'openharness', 'src')
)
if os.path.exists(OPENHARNESS_SRC) and OPENHARNESS_SRC not in sys.path:
    sys.path.insert(0, OPENHARNESS_SRC)

# 尝试导入 OpenHarness v2
try:
    from openharness.tools.base import BaseTool, ToolRegistry
    from openharness.engine.query_engine import QueryEngine
    from openharness.config.settings import Settings
    from openharness.api.client import AnthropicApiClient
    OPENHARNESS_V2_AVAILABLE = True
    print("✓ OpenHarness v2 导入成功")
except ImportError as e:
    print(f"⚠ OpenHarness v2 导入失败: {e}")
    OPENHARNESS_V2_AVAILABLE = False
    BaseTool = object
    ToolRegistry = object


@dataclass
class AgentAction:
    """Agent 动作"""
    tool_name: str
    params: Dict[str, Any] = field(default_factory=dict)
    thought: str = ""

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "tool_name": self.tool_name,
            "params": self.params,
            "thought": self.thought,
        }


@dataclass
class AgentObservation:
    """Agent 观察结果"""
    state: str
    tools_available: List[str]
    last_result: Optional[Dict] = None
    episode_history: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "state": self.state,
            "tools_available": self.tools_available,
            "last_result": self.last_result,
            "episode_history": self.episode_history,
        }


class GraphitiToolAdapter(BaseTool if OPENHARNESS_V2_AVAILABLE else object):
    """
    将 Graphiti Skill 适配为 OpenHarness v2 BaseTool
    
    OpenHarness v2 BaseTool 接口：
    - name: str
    - description: str  
    - input_model: type[BaseModel]
    - execute(arguments, context) -> ToolResult
    """

    def __init__(self, name: str, description: str, handler: Callable,
                 category: str = "general", opa_manager=None):
        if OPENHARNESS_V2_AVAILABLE:
            super().__init__()
        self.name = name
        self.description = description
        self.handler = handler
        self.category = category
        self.opa_manager = opa_manager
        self.call_count = 0
        self._success_count = 0
        self._error_count = 0

    async def execute(self, arguments, context) -> Any:
        """执行工具调用（OpenHarness v2 接口）"""
        self.call_count += 1
        start = time.perf_counter()

        try:
            # 提取参数
            params = arguments.model_dump() if hasattr(arguments, 'model_dump') else dict(arguments)
            
            # 调用 handler
            if asyncio.iscoroutinefunction(self.handler):
                result = await self.handler(**params)
            else:
                result = self.handler(**params)

            elapsed_ms = (time.perf_counter() - start) * 1000
            self._success_count += 1

            # 标准化输出
            if isinstance(result, (dict, list)):
                output = result
            else:
                output = {"result": str(result)}

            return {
                "status": "success",
                "data": output,
                "tool": self.name,
                "execution_time_ms": round(elapsed_ms, 2),
                "call_count": self.call_count,
            }

        except Exception as e:
            self._error_count += 1
            return {
                "status": "error",
                "error": str(e),
                "tool": self.name,
                "call_count": self.call_count,
            }

    def to_openai_schema(self) -> Dict:
        """生成 OpenAI function calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                }
            }
        }


class GraphitiAgentLoop:
    """
    Graphiti Agent Loop 实现
    
    基于 OpenHarness v2 架构的完整 Agent 循环系统：
    1. 接收用户输入
    2. 使用 LLM 决策下一步行动
    3. 执行工具调用
    4. 观察结果并循环
    """

    def __init__(self, 
                 user_role: str = "intelligence_analyst",
                 opa_manager=None,
                 graph_manager=None,
                 llm_client=None):
        self.user_role = user_role
        self.opa_manager = opa_manager
        self.graph_manager = graph_manager
        self.llm_client = llm_client
        self.tools: Dict[str, GraphitiToolAdapter] = {}
        self._episode_history: List[Dict] = []
        self._max_steps = 50
        self._current_step = 0
        self._build_tools()

    def _build_tools(self):
        """从 SKILL_CATALOG 构建工具列表"""
        try:
            from odap.tools import SKILL_CATALOG
            for name, entry in SKILL_CATALOG.items():
                tool = GraphitiToolAdapter(
                    name=name,
                    description=entry["description"],
                    handler=entry["handler"],
                    category=entry.get("category", "general"),
                    opa_manager=self.opa_manager,
                )
                self.tools[name] = tool
            print(f"✓ Agent Loop 初始化完成: {len(self.tools)} 个工具")
        except Exception as e:
            print(f"⚠ 构建工具列表失败: {e}")

    async def run(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        运行完整的 Agent Loop
        
        Args:
            user_input: 用户输入
            context: 额外上下文
            
        Returns:
            执行结果
        """
        self._episode_history.clear()
        self._current_step = 0
        
        # 初始化观察
        observation = self._get_observation()
        
        # Agent Loop
        while self._current_step < self._max_steps:
            self._current_step += 1
            
            # 1. LLM 决策
            action = await self._decide_action(user_input, observation, context)
            
            if not action or action.tool_name == "end_mission":
                break
                
            # 2. 执行工具
            result = await self._execute_action(action)
            
            # 3. 更新观察
            observation = self._get_observation(result)
            
            # 4. 记录历史（使用 to_dict 转换）
            self._episode_history.append({
                "step": self._current_step,
                "action": action.to_dict(),
                "result": result,
                "timestamp": datetime.now().isoformat(),
            })
            
            # 检查是否完成
            if result.get("status") == "success" and self._is_task_complete(result):
                break
        
        return {
            "success": True,
            "steps": self._episode_history,
            "total_steps": self._current_step,
            "final_observation": observation.to_dict(),
        }

    async def _decide_action(self, user_input: str, 
                            observation: AgentObservation,
                            context: Dict[str, Any] = None) -> Optional[AgentAction]:
        """使用 LLM 决策下一步行动"""
        if not self.llm_client:
            # Fallback: 简单关键词匹配
            return self._fallback_decide(user_input)
        
        # 构建 prompt
        tools_schema = [tool.to_openai_schema() for tool in self.tools.values()]
        
        prompt = f"""基于用户输入和当前状态，选择最合适的工具执行。

用户输入: {user_input}
可用工具: {[t.name for t in self.tools.values()]}
当前观察: {observation.state}
历史步骤: {len(self._episode_history)}

请决定下一步行动，格式为 JSON:
{{
    "tool_name": "工具名称",
    "params": {{参数}},
    "thought": "思考过程"
}}
"""
        
        try:
            response = await self.llm_client.complete(prompt)
            action_data = json.loads(response)
            return AgentAction(**action_data)
        except Exception as e:
            print(f"LLM 决策失败: {e}")
            return self._fallback_decide(user_input)

    def _fallback_decide(self, user_input: str) -> Optional[AgentAction]:
        """Fallback 决策逻辑"""
        # 简单的关键词匹配
        keywords = {
            "查询": "query_graph",
            "搜索": "search_entities",
            "创建": "create_entity",
            "删除": "delete_entity",
            "更新": "update_entity",
        }
        
        for keyword, tool_name in keywords.items():
            if keyword in user_input:
                return AgentAction(tool_name=tool_name, params={"query": user_input})
        
        return AgentAction(tool_name="end_mission", params={})

    async def _execute_action(self, action: AgentAction) -> Dict[str, Any]:
        """执行 Agent 行动"""
        tool = self.tools.get(action.tool_name)
        if not tool:
            return {"status": "error", "error": f"工具不存在: {action.tool_name}"}
        
        # 创建模拟的 context
        class MockContext:
            cwd = "/app"
            metadata = {}
        
        result = await tool.execute(action.params, MockContext())
        return result

    def _get_observation(self, last_result: Dict = None) -> AgentObservation:
        """获取当前观察"""
        return AgentObservation(
            state="active" if self._current_step < self._max_steps else "completed",
            tools_available=list(self.tools.keys()),
            last_result=last_result,
            episode_history=self._episode_history,
        )

    def _is_task_complete(self, result: Dict) -> bool:
        """判断任务是否完成"""
        # 可以根据具体业务逻辑判断
        return False

    def list_tools(self) -> List[Dict]:
        """列出所有可用工具"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "call_count": tool.call_count,
            }
            for tool in self.tools.values()
        ]


class OpenHarnessIntegration:
    """
    OpenHarness 集成管理器
    
    统一管理 OpenHarness 的初始化、配置和使用。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self.agent_loop: Optional[GraphitiAgentLoop] = None
        self.settings: Optional[Any] = None
        self.llm_client: Optional[Any] = None
        self._initialized = True

    async def initialize(self, 
                        user_role: str = "intelligence_analyst",
                        provider_config: Dict[str, Any] = None):
        """
        初始化 OpenHarness 集成
        
        Args:
            user_role: 用户角色
            provider_config: LLM Provider 配置
        """
        try:
            # 初始化 LLM Client
            if provider_config and OPENHARNESS_V2_AVAILABLE:
                self.settings = Settings()
                # 配置 provider
                self.llm_client = AnthropicApiClient(self.settings)
            
            # 初始化 Agent Loop
            self.agent_loop = GraphitiAgentLoop(
                user_role=user_role,
                llm_client=self.llm_client,
            )
            
            print(f"✓ OpenHarness 集成初始化完成")
            return True
            
        except Exception as e:
            print(f"⚠ OpenHarness 集成初始化失败: {e}")
            return False

    async def run_agent(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        运行 Agent
        
        Args:
            user_input: 用户输入
            context: 上下文
            
        Returns:
            执行结果
        """
        if not self.agent_loop:
            return {
                "success": False,
                "error": "Agent Loop 未初始化",
            }
        
        return await self.agent_loop.run(user_input, context)

    def get_status(self) -> Dict[str, Any]:
        """获取集成状态"""
        return {
            "openharness_available": OPENHARNESS_V2_AVAILABLE,
            "agent_loop_initialized": self.agent_loop is not None,
            "llm_client_initialized": self.llm_client is not None,
            "tools_count": len(self.agent_loop.tools) if self.agent_loop else 0,
            "tools": self.agent_loop.list_tools() if self.agent_loop else [],
        }


# 全局集成实例
_integration_instance = None


def get_openharness_integration() -> OpenHarnessIntegration:
    """获取 OpenHarness 集成实例"""
    global _integration_instance
    if _integration_instance is None:
        _integration_instance = OpenHarnessIntegration()
    return _integration_instance


async def initialize_openharness(user_role: str = "intelligence_analyst",
                                 provider_config: Dict[str, Any] = None) -> bool:
    """
    初始化 OpenHarness
    
    Args:
        user_role: 用户角色
        provider_config: Provider 配置
        
    Returns:
        是否成功
    """
    integration = get_openharness_integration()
    return await integration.initialize(user_role, provider_config)


async def run_agent(user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    运行 Agent
    
    Args:
        user_input: 用户输入
        context: 上下文
        
    Returns:
        执行结果
    """
    integration = get_openharness_integration()
    return await integration.run_agent(user_input, context)
