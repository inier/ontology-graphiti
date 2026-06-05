"""
OpenHarness 集成适配模块
将 OpenHarness 的 Tool/Harness 嵌入领域情报系统

架构：
- OpenHarnessToolAdapter: 将 BaseSkill 适配为 OpenHarness Tool
- DomainHarness: 继承 OpenHarness Harness，注入领域 Tool + OPA 权限
- 提供 reset/step/run_episode 等 Agent Loop 接口

集成模式：OpenHarness 作为 LLM Agent Loop 引擎，
我们通过 Tool 适配层将 51 个 Skill 暴露为 OpenHarness 可调用的工具。
"""

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional


import logging

logger = logging.getLogger(__name__)
# 首先处理项目根目录
ODAP_INFRA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ODAP_INFRA_DIR)

# 然后尝试找到 openharness 包的位置
# 1. 先检查本地开发路径 (可能是 git submodule)
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
# OpenHarnessToolAdapter: Skill → Tool 适配
# ============================================================

class OpenHarnessToolAdapter(Tool):
    """
    将 BaseSkill / 裸函数 Skill 适配为 OpenHarness Tool

    兼容 OpenHarness v2 BaseTool 接口：
    - name: str
    - description: str
    - input_model: type[BaseModel]
    - execute(arguments, context) -> ToolResult
    """

    def __init__(self, name: str, description: str, handler,
                 opa_manager=None, category: str = "general"):
        if OPENHARNESS_AVAILABLE and OPENHARNESS_VERSION == 2:
            from pydantic import BaseModel, Field

            class DynamicInput(BaseModel):
                query: str = Field(default="", description="查询参数")
                params: Dict[str, Any] = Field(default_factory=dict, description="额外参数")

            super().__init__()
            self.name = name
            self.description = description
            self.input_model = DynamicInput
        else:
            super().__init__(name=name)

        self.handler = handler
        self.opa_manager = opa_manager
        self.category = category
        self.call_count = 0

    async def execute(self, arguments, context) -> Any:
        """执行工具调用（OpenHarness v2 接口）"""
        from openharness.tools.base import ToolResult

        self.call_count += 1
        start = time.perf_counter()

        try:
            params = arguments.model_dump() if hasattr(arguments, 'model_dump') else dict(arguments)
            query = params.pop("query", "")
            extra = params.pop("params", {})

            merged = {"query": query, **extra} if query else extra

            if asyncio.iscoroutinefunction(self.handler):
                result = await self.handler(**merged)
            else:
                result = self.handler(**merged)

            elapsed_ms = (time.perf_counter() - start) * 1000

            if isinstance(result, (dict, list)):
                output = json.dumps(result, ensure_ascii=False, default=str)
            else:
                output = str(result)

            return ToolResult(
                output=output,
                is_error=False,
                metadata={"tool": self.name, "execution_time_ms": round(elapsed_ms, 2), "call_count": self.call_count},
            )

        except Exception as e:
            return ToolResult(
                output=str(e),
                is_error=True,
                metadata={"tool": self.name, "call_count": self.call_count},
            )

    def run(self, action: Dict[str, Any]) -> str:
        """执行工具调用（兼容 v1 接口）"""
        self.call_count += 1
        start = time.perf_counter()

        try:
            params = {k: v for k, v in action.items()
                      if k not in ("name", "type", "thought", "tool_name")}

            result = self.handler(**params)

            elapsed_ms = (time.perf_counter() - start) * 1000

            if isinstance(result, (dict, list)):
                output = result
            else:
                output = {"result": str(result)}

            return json.dumps({
                "status": "success",
                "data": output,
                "tool": self.name,
                "execution_time_ms": round(elapsed_ms, 2),
                "call_count": self.call_count,
            }, ensure_ascii=False, default=str)

        except TypeError as e:
            return json.dumps({
                "status": "error",
                "error": f"参数错误: {e}",
                "tool": self.name,
                "call_count": self.call_count,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": str(e),
                "tool": self.name,
                "call_count": self.call_count,
            }, ensure_ascii=False)

    def to_openai_tool_schema(self) -> Dict:
        """生成 OpenAI function calling 格式的 tool schema"""
        if OPENHARNESS_AVAILABLE and OPENHARNESS_VERSION == 2:
            return self.to_api_schema()
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


# ============================================================
# DomainHarness: 领域情报系统 Harness
# ============================================================

class DomainHarness:
    """
    领域情报分析 Harness

    兼容 OpenHarness v1 (core.harness) 和 v2 (engine.query_engine)：
    1. 所有已注册的 Skill（通过 OpenHarnessToolAdapter）
    2. OPA 权限管理
    3. Graphiti 图谱管理

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

        self._tool_list = self._build_tools(opa_manager)
        self._query_engine = None

        if OPENHARNESS_AVAILABLE and OPENHARNESS_VERSION == 2:
            self._init_v2_engine()

    def _init_v2_engine(self):
        """初始化 v2 QueryEngine"""
        try:
            from openharness.engine.query_engine import QueryEngine
            from openharness.tools.base import ToolRegistry
            from openharness.api.client import AnthropicApiClient
            from openharness.permissions.checker import PermissionChecker
            from openharness.config.settings import Settings, PermissionSettings

            registry = ToolRegistry()
            for tool in self._tool_list:
                registry.register(tool)

            settings = Settings()
            perm_checker = PermissionChecker(PermissionSettings())

            api_key = os.getenv("OPENAI_API_KEY", "")
            base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
            model = os.getenv("OPENAI_MODEL", "gpt-4")

            api_client = AnthropicApiClient(
                api_key=api_key,
                base_url=base_url,
            )

            self._query_engine = QueryEngine(
                api_client=api_client,
                tool_registry=registry,
                permission_checker=perm_checker,
                cwd=os.getcwd(),
                model=model,
                system_prompt=f"你是领域情报分析助手，当前角色: {self.user_role}",
            )
            logger.info(f'✓ OpenHarness v2 QueryEngine 初始化成功, {len(self._tool_list)} 个工具')
        except Exception as e:
            logger.info(f'⚠ OpenHarness v2 QueryEngine 初始化失败: {e}')
            self._query_engine = None

    @property
    def tools(self):
        return self._tool_list

    def _build_tools(self, opa_manager=None) -> List:
        """从 SKILL_CATALOG 构建工具列表"""
        tools = []
        try:
            from odap.tools import SKILL_CATALOG
            for name, entry in SKILL_CATALOG.items():
                adapter = OpenHarnessToolAdapter(
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

        Args:
            action: {"tool_name": str, "action": {params}}

        Returns:
            (observation, reward, done, info)
        """
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
    if not OPENHARNESS_AVAILABLE:
        logger.info('OpenHarness 未安装，使用模拟模式')
        return None

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
            OpenHarnessToolAdapter(
                name=name,
                description=entry["description"],
                handler=entry["handler"],
            ).to_openai_tool_schema()
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
