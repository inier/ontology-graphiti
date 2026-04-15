"""
OpenHarness 集成适配模块
将 OpenHarness 的 Tool/Harness 嵌入战场情报系统

架构：
- OpenHarnessToolAdapter: 将 BaseSkill 适配为 OpenHarness Tool
- BattlefieldHarness: 继承 OpenHarness Harness，注入战场 Tool + OPA 权限
- 提供 reset/step/run_episode 等 Agent Loop 接口

集成模式：OpenHarness 作为 LLM Agent Loop 引擎，
我们通过 Tool 适配层将 51 个 Skill 暴露为 OpenHarness 可调用的工具。
"""

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# OpenHarness（可选）
try:
    from openharness.tools.tool import Tool
    from openharness.core.harness import Harness, Observation
    OPENHARNESS_AVAILABLE = True
except ImportError:
    OPENHARNESS_AVAILABLE = False
    Tool = object  # type: ignore
    Harness = object  # type: ignore
    Observation = None  # type: ignore


# ============================================================
# OpenHarnessToolAdapter: Skill → Tool 适配
# ============================================================

class OpenHarnessToolAdapter(Tool):
    """
    将 BaseSkill / 裸函数 Skill 适配为 OpenHarness Tool

    OpenHarness Tool 接口：
    - __init__(name, ...) 
    - run(action: Dict) -> str  (返回字符串结果)

    我们的 Skill 接口：
    - register_skill(name, description, handler)
    - handler(**kwargs) -> dict/list
    """

    def __init__(self, name: str, description: str, handler,
                 opa_manager=None, category: str = "general"):
        super().__init__(name=name)
        self.description = description
        self.handler = handler
        self.opa_manager = opa_manager
        self.category = category
        self.call_count = 0

    def run(self, action: Dict[str, Any]) -> str:
        """
        执行工具调用

        Args:
            action: 包含参数的字典

        Returns:
            str: JSON 格式的执行结果
        """
        self.call_count += 1
        start = time.perf_counter()

        try:
            # 提取参数（排除 OpenHarness 内部字段）
            params = {k: v for k, v in action.items()
                      if k not in ("name", "type", "thought", "tool_name")}

            # 调用底层 handler
            result = self.handler(**params)

            elapsed_ms = (time.perf_counter() - start) * 1000

            # 标准化输出
            if isinstance(result, (dict, list)):
                output = result
            else:
                output = {"result": str(result)}

            # 包装为标准响应
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
# BattlefieldHarness: 战场情报系统 Harness
# ============================================================

class BattlefieldHarness(Harness if OPENHARNESS_AVAILABLE else object):
    """
    战场情报分析 Harness

    继承 OpenHarness Harness，注入：
    1. 所有已注册的 Skill（通过 OpenHarnessToolAdapter）
    2. OPA 权限管理
    3. Graphiti 图谱管理

    使用示例::

        harness = BattlefieldHarness()
        obs = harness.reset()
        while not harness.is_done():
            action = llm.decide(obs)
            obs, reward, done, info = harness.step(action)
    """

    def __init__(self, user_role: str = "intelligence_analyst",
                 opa_manager=None, graph_manager=None):
        if OPENHARNESS_AVAILABLE:
            # OpenHarness Harness 需要传入 tools 列表
            tools = self._build_tools(opa_manager)
            super().__init__(tools=tools)
        else:
            self.tools = self._build_tools(opa_manager) if opa_manager else []

        self.user_role = user_role
        self.opa_manager = opa_manager
        self.graph_manager = graph_manager
        self._episode_history: List[Dict] = []
        self._task_queue: List[Dict] = []
        self._done = False

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
            print(f"构建 OpenHarness 工具列表失败: {e}")

        return tools

    def _get_observation(self) -> 'Observation':
        """构建当前 Observation"""
        if not OPENHARNESS_AVAILABLE or Observation is None:
            return {"state": "fallback", "tools": len(self.tools) if hasattr(self, 'tools') else 0}

        return Observation(
            state="active",
            tools_available=[t.name for t in (self.tools if hasattr(self, 'tools') else [])],
            user_role=self.user_role,
        )

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

        # 查找工具
        tool = None
        for t in (self.tools if hasattr(self, 'tools') else []):
            if t.name == tool_name:
                tool = t
                break

        if not tool:
            obs = self._get_observation()
            return obs, -1.0, False, {"error": f"工具不存在: {tool_name}"}

        # 执行
        result_str = tool.run(params)

        # 记录历史
        step_record = {
            "tool": tool_name,
            "params": params,
            "result": result_str,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._episode_history.append(step_record)

        # 判断是否结束
        reward = 1.0 if '"status": "success"' in result_str else 0.0
        done = tool_name == "end_mission" if isinstance(tool_name, str) else False

        return self._get_observation(), reward, done, step_record

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
        return [
            {"name": t.name, "description": t.description, "category": t.category}
            for t in (self.tools if hasattr(self, 'tools') else [])
        ]

    def get_episode_history(self) -> List[Dict]:
        """获取当前 episode 历史"""
        return list(self._episode_history)


# ============================================================
# 便捷函数
# ============================================================

def create_harness(user_role: str = "intelligence_analyst") -> Optional['BattlefieldHarness']:
    """
    创建战场 Harness 实例

    Args:
        user_role: 用户角色

    Returns:
        BattlefieldHarness 或 None（OpenHarness 不可用时）
    """
    if not OPENHARNESS_AVAILABLE:
        print("OpenHarness 未安装，使用模拟模式")
        return None

    try:
        harness = BattlefieldHarness(user_role=user_role)
        print(f"BattlefieldHarness 初始化成功: {len(harness.tools)} 个工具")
        return harness
    except Exception as e:
        print(f"BattlefieldHarness 初始化失败: {e}")
        return None


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
        print(f"导出工具 schema 失败: {e}")
        return []


if __name__ == "__main__":
    print(f"OpenHarness 可用: {OPENHARNESS_AVAILABLE}")

    # 创建 Harness
    harness = create_harness(user_role="commander")
    if harness:
        print(f"\n可用工具 ({len(harness.list_available_tools())}):")
        for t in harness.list_available_tools()[:5]:
            print(f"  - [{t['category']}] {t['name']}: {t['description']}")
        print(f"  ... 共 {len(harness.list_available_tools())} 个")

        # 导出 OpenAI schemas
        schemas = export_tool_schemas()
        print(f"\n导出 {len(schemas)} 个 OpenAI function schemas")
    else:
        print("使用 fallback 模式，尝试直接列出 skills:")
        try:
            from odap.tools import SKILL_CATALOG
            print(f"共 {len(SKILL_CATALOG)} 个 skill 注册")
        except Exception as e:
            print(f"Skill 加载失败: {e}")
