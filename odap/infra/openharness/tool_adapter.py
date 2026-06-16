"""
OpenHarness 集成适配模块
将 OpenHarness 的 Tool/Harness 嵌入领域情报系统

架构：
- GraphitiToolAdapter (别名 OpenHarnessToolAdapter): 统一 Skill → OH Tool 适配层
  （定义在 engine_adapter.py，此处通过别名导出以保持向后兼容）
- DomainHarness: 基于 OHQueryEngineFactory 的领域 Harness
  提供 reset/step/run_episode 等 RL 风格接口

集成模式：OpenHarness 作为 LLM Agent Loop 引擎，
我们通过 GraphitiToolAdapter 将 Skill 暴露为 OpenHarness 可调用的工具。
"""

import asyncio
import json
import os
import sys
import time
import warnings
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)

# 首先处理项目根目录
ODAP_INFRA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ODAP_INFRA_DIR)

# 然后尝试找到 openharness 包的位置
OPENHARNESS_POSSIBLE_PATHS = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'openharness', 'src'),
    '/app/openharness/src',  # Docker 容器路径
]

for possible_path in OPENHARNESS_POSSIBLE_PATHS:
    if os.path.exists(possible_path) and possible_path not in sys.path:
        sys.path.insert(0, possible_path)
        logger.info(f'Added openharness source path: {possible_path}')

# OpenHarness（可选）
try:
    # 尝试导入 OpenHarness v2 版本 (engine + tools)
    try:
        from openharness.tools.base import BaseTool as Tool
        from openharness.engine.query_engine import QueryEngine as Harness
        from openharness.api.client import AnthropicApiClient
        Observation = None
        logger.info('✓ OpenHarness v2 导入成功 (engine + tools)')
        OPENHARNESS_AVAILABLE = True
        OPENHARNESS_VERSION = 2
    except ImportError:
        # 尝试导入 OpenHarness v1 版本 (core.harness)
        try:
            from openharness.tools.base import BaseTool as Tool
            from openharness.core.harness import Harness, Observation
            logger.info('✓ OpenHarness v1 (core.harness) 导入成功')
            OPENHARNESS_AVAILABLE = True
            OPENHARNESS_VERSION = 1
        except ImportError:
            try:
                from openharness_ai.tools.tool import Tool
                from openharness_ai.core.harness import Harness, Observation
                logger.info('✓ OpenHarness v1 (openharness_ai) 导入成功')
                OPENHARNESS_AVAILABLE = True
                OPENHARNESS_VERSION = 1
            except ImportError:
                logger.info('OpenHarness 未安装，使用模拟模式')
                OPENHARNESS_AVAILABLE = False
                OPENHARNESS_VERSION = 0
                Tool = object  # type: ignore
                Harness = object  # type: ignore
                Observation = None  # type: ignore
except Exception as e:
    logger.info(f'⚠ OpenHarness 导入失败: {e}')
    OPENHARNESS_AVAILABLE = False
    OPENHARNESS_VERSION = 0
    Tool = object  # type: ignore
    Harness = object  # type: ignore
    Observation = None  # type: ignore


# ============================================================
# 统一适配器：从 engine_adapter 导入 GraphitiToolAdapter
# ============================================================

try:
    from odap.infra.openharness.engine_adapter import GraphitiToolAdapter
    # 向后兼容别名：OpenHarnessToolAdapter → GraphitiToolAdapter
    OpenHarnessToolAdapter = GraphitiToolAdapter
except ImportError:
    logger.warning("无法从 engine_adapter 导入 GraphitiToolAdapter，使用本地 fallback")
    # fallback: 如果 engine_adapter 不可用，定义一个最小适配器
    class _FallbackToolAdapter:
        """GraphitiToolAdapter 不可用时的最小 fallback"""
        def __init__(self, name: str, description: str, handler,
                     opa_manager=None, category: str = "general"):
            self.name = name
            self.description = description
            self.handler = handler
            self.opa_manager = opa_manager
            self.category = category
            self.call_count = 0

        async def execute(self, arguments, context) -> Any:
            self.call_count += 1
            try:
                params = arguments.model_dump() if hasattr(arguments, 'model_dump') else dict(arguments)
                if asyncio.iscoroutinefunction(self.handler):
                    result = await self.handler(**params)
                else:
                    result = self.handler(**params)
                return {"status": "success", "data": result, "tool": self.name}
            except Exception as e:
                return {"status": "error", "error": str(e), "tool": self.name}

        def run(self, action: Dict[str, Any]) -> str:
            self.call_count += 1
            try:
                params = {k: v for k, v in action.items()
                          if k not in ("name", "type", "thought", "tool_name")}
                result = self.handler(**params)
                output = result if isinstance(result, (dict, list)) else {"result": str(result)}
                return json.dumps({"status": "success", "data": output, "tool": self.name},
                                  ensure_ascii=False, default=str)
            except Exception as e:
                return json.dumps({"status": "error", "error": str(e), "tool": self.name},
                                  ensure_ascii=False)

        def to_openai_tool_schema(self) -> Dict:
            return {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description,
                    "parameters": {"type": "object", "properties": {}, "required": []},
                }
            }

        to_openai_schema = to_openai_tool_schema

    GraphitiToolAdapter = _FallbackToolAdapter  # type: ignore
    OpenHarnessToolAdapter = _FallbackToolAdapter  # type: ignore


# ============================================================
# DomainHarness: 领域情报系统 Harness
# ============================================================

class DomainHarness:
    """
    领域情报分析 Harness

    基于 OHQueryEngineFactory 构建，提供 RL 风格的 step 接口：
    1. 所有已注册的 Skill（通过 GraphitiToolAdapter）
    2. OPA 权限管理
    3. Graphiti 图谱管理

    v1/v2 统一策略：
    - 工具列表优先从 OHQueryEngineFactory._tool_registry 获取（避免与 engine_adapter 双重注册）
    - step(message) 委托给 GraphitiAgentLoop.run()（复用 OH QueryEngine 的完整 Agent Loop）
    - step(tool_name) 保留本地工具执行作为 v1 兼容 fallback

    使用示例::

        harness = DomainHarness()
        obs = harness.reset()
        while not harness.is_done():
            action = llm.decide(obs)
            obs, reward, done, info = harness.step(action)
    """

    def __init__(self, user_role: str = "intelligence_analyst",
                 opa_manager=None, graph_manager=None):
        self.user_role = user_role
        self.opa_manager = opa_manager
        self.graph_manager = graph_manager
        self._episode_history: List[Dict] = []
        self._task_queue: List[Dict] = []
        self._done = False

        # Phase 1: 不再在 __init__ 中立即构建工具列表
        # 工具列表将在 _init_engine() 之后从 factory 的 ToolRegistry 获取
        self._tool_list: List = []
        self._factory = None
        self._query_engine = None
        self._agent_loop = None

        # 优先使用 OHQueryEngineFactory 初始化 QueryEngine
        self._init_engine()

        # Phase 1: 引擎初始化后，从 factory 的 ToolRegistry 获取工具列表
        self._resolve_tool_list()

        # Phase 2: 创建 GraphitiAgentLoop 实例，用于 step(message) 委托
        self._init_agent_loop()

    def _init_engine(self):
        """通过 OHQueryEngineFactory 初始化 QueryEngine"""
        try:
            from odap.infra.openharness.engine_adapter import OHQueryEngineFactory

            factory = OHQueryEngineFactory.get_instance()
            if not factory.is_available:
                api_key = os.environ.get("OPENAI_API_KEY", "")
                base_url = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
                model = os.environ.get("OPENAI_MODEL", "gpt-4")
                factory.configure(
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    opa_manager=self.opa_manager,
                )

            if factory.is_available:
                self._factory = factory
                self._query_engine = factory.create_engine(
                    system_prompt=f"你是领域情报分析助手，当前角色: {self.user_role}",
                    workspace_id="",
                    scenario_id="",
                )
                if self._query_engine:
                    logger.info('✓ DomainHarness QueryEngine 初始化成功')
                else:
                    logger.info('⚠ DomainHarness QueryEngine 创建失败')
            else:
                logger.info('⚠ OHQueryEngineFactory 不可用，DomainHarness 使用 fallback 模式')
        except Exception as e:
            logger.info(f'⚠ DomainHarness 引擎初始化失败: {e}')
            self._query_engine = None

    def _resolve_tool_list(self):
        """Phase 1: 从 factory 的 ToolRegistry 获取工具列表，避免与 engine_adapter 双重注册

        优先级：
        1. factory._tool_registry 中的工具（由 OHQueryEngineFactory._register_skills() 注册）
        2. 本地 _build_tools() 作为 fallback（factory 不可用时）
        """
        if self._factory and self._factory._tool_registry:
            try:
                registry = self._factory._tool_registry
                # ToolRegistry 内部用 _tools dict 存储已注册工具
                if hasattr(registry, '_tools'):
                    self._tool_list = list(registry._tools.values())
                    logger.info(f'✓ DomainHarness 从 factory ToolRegistry 获取 {len(self._tool_list)} 个工具（避免双重注册）')
                    return
            except Exception as e:
                logger.debug(f'从 factory ToolRegistry 获取工具失败: {e}')

        # Fallback: 本地构建工具列表
        self._tool_list = self._build_tools(self.opa_manager)
        logger.info(f'DomainHarness 使用本地 fallback 工具列表: {len(self._tool_list)} 个工具')

    def _init_agent_loop(self):
        """Phase 2: 创建 GraphitiAgentLoop 实例，用于 step(message) 委托"""
        try:
            from odap.infra.openharness.engine_adapter import GraphitiAgentLoop
            self._agent_loop = GraphitiAgentLoop(
                user_role=self.user_role,
                opa_manager=self.opa_manager,
                graph_manager=self.graph_manager,
            )
            logger.info('✓ DomainHarness GraphitiAgentLoop 初始化成功')
        except Exception as e:
            logger.debug(f'GraphitiAgentLoop 初始化失败: {e}')
            self._agent_loop = None

    @property
    def tools(self):
        return self._tool_list

    def _build_tools(self, opa_manager=None) -> List:
        """从 SKILL_CATALOG 构建工具列表（使用统一适配器 GraphitiToolAdapter）"""
        tools = []
        try:
            from odap.tools import SKILL_CATALOG
            for name, entry in SKILL_CATALOG.items():
                adapter = GraphitiToolAdapter(
                    name=name,
                    description=entry["description"],
                    handler=entry["handler"],
                    opa_manager=opa_manager,
                    category=entry.get("category", "general"),
                )
                tools.append(adapter)
        except Exception as e:
            logger.info(f'构建 OpenHarness 工具列表失败: {e}')

        return tools

    def _get_observation(self) -> Dict:
        """构建当前 Observation"""
        return {
            "state": "active",
            "tools_available": [t.name for t in self._tool_list],
            "user_role": self.user_role,
        }

    def reset(self):
        """重置 Harness，开始新 episode"""
        self._episode_history.clear()
        self._done = False
        return self._get_observation()

    def step(self, action: Dict[str, Any]):
        """
        执行一步

        v1/v2 统一策略：
        - 当 action 包含 message 字段时，委托给 GraphitiAgentLoop.run()
          （复用 OH QueryEngine 的完整 Agent Loop，包括 LLM 调用、工具选择、执行、循环）
        - 当 action 包含 tool_name 字段时（v1 风格），走本地工具执行路径（向后兼容）

        Args:
            action: {"tool_name": str, "action": {params}} 或 {"message": str}

        Returns:
            (observation, reward, done, info)
        """
        # Phase 2: 当 action 包含 message 字段，委托给 GraphitiAgentLoop
        message = action.get("message")
        if message:
            if self._agent_loop:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            result = pool.submit(
                                asyncio.run,
                                self._agent_loop.run(message)
                            ).result()
                    else:
                        result = loop.run_until_complete(self._agent_loop.run(message))

                    obs = self._get_observation()
                    # GraphitiAgentLoop.run() 返回 Dict[str, Any]
                    success = result.get("success", False) if isinstance(result, dict) else True
                    reward = 1.0 if success else 0.0
                    info = {
                        "engine": result.get("engine", "agent_loop") if isinstance(result, dict) else "agent_loop",
                        "result": result,
                    }
                    return obs, reward, True, info
                except Exception as e:
                    logger.debug(f"GraphitiAgentLoop.run() failed, fallback to QueryEngine: {e}")

            # Fallback: 如果 agent_loop 不可用，尝试直接使用 QueryEngine
            if self._query_engine:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            result = pool.submit(
                                asyncio.run,
                                self._submit_via_engine(message)
                            ).result()
                    else:
                        result = loop.run_until_complete(self._submit_via_engine(message))
                    obs = self._get_observation()
                    return obs, 1.0, True, {"engine": "openharness_query_engine", "result": result}
                except Exception as e:
                    logger.debug(f"QueryEngine step failed, fallback to tool execution: {e}")

        # v1 兼容路径：自建工具执行（fallback）
        tool_name = action.get("tool_name", action.get("name", ""))
        params = action.get("action", action.get("params", {}))

        tool = None
        for t in self._tool_list:
            if t.name == tool_name:
                tool = t
                break

        if not tool:
            obs = self._get_observation()
            return obs, -1.0, False, {"error": f"工具不存在: {tool_name}"}

        result_str = tool.run(params)

        step_record = {
            "tool": tool_name,
            "params": params,
            "result": result_str,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._episode_history.append(step_record)

        reward = 1.0 if '"status": "success"' in result_str else 0.0
        done = tool_name == "end_mission" if isinstance(tool_name, str) else False

        return self._get_observation(), reward, done, step_record

    async def _submit_via_engine(self, message: str) -> str:
        """通过 OH QueryEngine 提交消息并收集结果"""
        text_parts = []
        async for event in self._query_engine.submit_message(message):
            if hasattr(event, 'text'):
                text_parts.append(event.text)
        return "".join(text_parts)

    async def submit_message(self, message: str):
        """向 v2 QueryEngine 提交消息（异步）"""
        if self._query_engine:
            return await self._query_engine.submit_message(message)
        return {"error": "QueryEngine not initialized"}

    def run_episode(self, actions: List[Dict[str, Any]]) -> List[Dict]:
        """
        运行完整 episode（批量执行）

        Args:
            actions: 步骤列表 [{"tool_name": ..., "action": {...}}, ...]

        Returns:
            步骤结果列表
        """
        self.reset()
        results = []

        for action in actions:
            obs, reward, done, info = self.step(action)
            results.append({
                "observation": obs,
                "reward": reward,
                "done": done,
                "info": info,
            })
            if done:
                break

        return results

    def list_available_tools(self) -> List[Dict[str, str]]:
        """列出所有可用工具"""
        tools = []
        for t in self._tool_list:
            if hasattr(t, 'name'):
                tools.append({"name": t.name, "description": t.description, "category": t.category})
        return tools

    def get_episode_history(self) -> List[Dict]:
        """获取当前 episode 历史"""
        return list(self._episode_history)


# ============================================================
# 便捷函数
# ============================================================

def create_harness(user_role: str = "intelligence_analyst") -> Optional['DomainHarness']:
    """
    创建领域 Harness 实例

    Args:
        user_role: 用户角色

    Returns:
        DomainHarness 或 None（OpenHarness 不可用时）
    """
    try:
        harness = DomainHarness(user_role=user_role)
        logger.info(f'DomainHarness 初始化成功: {len(harness.tools)} 个工具')
        return harness
    except Exception as e:
        logger.info(f'DomainHarness 初始化失败: {e}')
        return None


_domain_harness_instance: Optional['DomainHarness'] = None


def get_domain_harness(user_role: str = "intelligence_analyst") -> Optional['DomainHarness']:
    """获取 DomainHarness 单例实例"""
    global _domain_harness_instance
    if _domain_harness_instance is None:
        _domain_harness_instance = create_harness(user_role)
    return _domain_harness_instance


def export_tool_schemas() -> List[Dict]:
    """
    导出所有 Skill 为 OpenAI function calling 格式

    用于 LLM Agent 集成。
    """
    try:
        from odap.tools import SKILL_CATALOG
        return [
            GraphitiToolAdapter(
                name=name,
                description=entry["description"],
                handler=entry["handler"],
            ).to_openai_schema()
            for name, entry in SKILL_CATALOG.items()
        ]
    except Exception as e:
        logger.info(f'导出工具 schema 失败: {e}')
        return []


if __name__ == "__main__":
    logger.info(f'OpenHarness 可用: {OPENHARNESS_AVAILABLE}')

    # 创建 Harness
    harness = create_harness(user_role="commander")
    if harness:
        logger.info(f'\n可用工具 ({len(harness.list_available_tools())}):')
        for t in harness.list_available_tools()[:5]:
            logger.info(f"  - [{t['category']}] {t['name']}: {t['description']}")
        logger.info(f'  ... 共 {len(harness.list_available_tools())} 个')

        # 导出 OpenAI schemas
        schemas = export_tool_schemas()
        logger.info(f'\n导出 {len(schemas)} 个 OpenAI function schemas')
    else:
        logger.info('使用 fallback 模式，尝试直接列出 skills:')
        try:
            from odap.tools import SKILL_CATALOG
            logger.info(f'共 {len(SKILL_CATALOG)} 个 skill 注册')
        except Exception as e:
            logger.info(f'Skill 加载失败: {e}')
