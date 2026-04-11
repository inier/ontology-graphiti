"""
OpenHarness 桥接适配器
将现有 Skill 系统桥接到 OpenHarness 的 Tool 接口

核心思路：
- 现有 56 个 Python Skills 封装为 OpenHarness Tools
- Graphiti 作为 OpenHarness Memory 的底层存储
- OPA 作为 OpenHarness Permission Hook
- OpenHarness Swarm Coordinator 管理三 Agent 协同
"""

import asyncio
import sys
import os
from typing import Dict, Any, List, Optional
from enum import Enum

# 确保项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================================
# 第一层：Skill → OpenHarness Tool 桥接
# ============================================================================

try:
    from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
    from pydantic import BaseModel, Field
    OH_AVAILABLE = True
except ImportError:
    OH_AVAILABLE = False
    # 回退：定义简化版 Tool 接口
    class BaseTool:
        pass
    class ToolExecutionContext:
        pass
    class ToolResult:
        pass
    def Field(*args, **kwargs):
        return None
    class BaseModel:
        pass


class BattleFieldToolInput(BaseModel):
    """战场工具通用输入模型"""
    area: Optional[str] = Field(None, description="区域代号 (A/B/C/D/E)")
    entity_id: Optional[str] = Field(None, description="实体ID")
    user_role: str = Field("pilot", description="用户角色 (pilot/commander/observer)")


# ============================================================================
# 第二层：Graphiti → OpenHarness Memory 桥接
# ============================================================================

class GraphitiMemoryAdapter:
    """
    Graphiti 双时态图谱作为 OpenHarness 的长期记忆存储
    遵循 OpenHarness Memory 接口规范
    """

    def __init__(self):
        # 延迟导入，避免 graphiti 未安装时崩溃
        self._graph_manager = None
        self._initialized = False

    def _ensure_init(self):
        if not self._initialized:
            from core.graph_manager import BattlefieldGraphManager
            self._graph_manager = BattlefieldGraphManager()
            self._initialized = True

    async def read(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        读取记忆（对应 OpenHarness memory.read）
        使用 Graphiti 的语义搜索能力
        """
        self._ensure_init()
        results = self._graph_manager.search(query, limit)
        return results

    async def write(self, event_type: str, content: str, metadata: Dict = None) -> bool:
        """
        写入记忆（对应 OpenHarness memory.write）
        将事件写入 Graphiti 时序图谱
        """
        self._ensure_init()
        from datetime import datetime
        from data.simulation_data import load_simulation_data

        # 构建实体数据
        entity_data = {
            "id": f"memory_{event_type}_{int(datetime.now().timestamp())}",
            "type": "MemoryEvent",
            "properties": {
                "event_type": event_type,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                **(metadata or {})
            }
        }

        # 写入 Graphiti（异步）
        self._graph_manager.update_entity(entity_data["id"], entity_data["properties"])
        return True

    async def search_by_time_window(
        self, start_time: str, end_time: str, entity_type: str = None
    ) -> List[Dict]:
        """
        时序窗口查询（Graphiti 独特能力，OpenHarness 原生 Memory 不支持）
        """
        self._ensure_init()
        return self._graph_manager.query_entities(entity_type=entity_type)


# ============================================================================
# 第三层：OPA → OpenHarness Permission Hook 桥接
# ============================================================================

class OPAPermissionHook:
    """
    OPA 策略引擎作为 OpenHarness 的权限控制 Hook
    遵循 OpenHarness hooks.permission 接口规范
    """

    def __init__(self):
        from core.opa_manager import OPAManager
        self.opa_manager = OPAManager()

    def check(self, action: str, resource: str, context: Dict) -> bool:
        """
        权限检查（对应 OpenHarness permission hook）
        返回 True = 允许，False = 拒绝
        """
        # 将 OpenHarness 上下文映射为 OPA 输入格式
        opa_input = {
            "action": action,
            "resource": resource,
            "subject": context.get("user_role", "pilot"),
            "object_id": context.get("entity_id"),
            "timestamp": context.get("timestamp"),
        }

        return self.opa_manager.evaluate(opa_input)

    def enforce_attack(self, target_id: str, user_role: str) -> Dict[str, Any]:
        """
        攻击操作的专项 OPA 校验（封装通用 check）
        """
        allowed = self.check(
            action="attack",
            resource="battlefield.target",
            context={"entity_id": target_id, "user_role": user_role}
        )
        return {
            "allowed": allowed,
            "target_id": target_id,
            "actor": user_role,
            "policy": "attack_target_policy"
        }


# ============================================================================
# 第四层：现有 Skill → OpenHarness Tool 封装
# ============================================================================

class SearchRadarTool(BaseTool):
    """
    雷达搜索工具
    封装 skills/intelligence.search_radar
    """

    name = "search_radar"
    description = "在指定区域搜索敌方雷达系统，返回雷达位置和状态"
    input_model = type("SearchRadarInput", (BaseModel,), {
        "area": Optional[str] = Field(None, description="区域代号 (A/B/C/D/E)"),
    })

    async def execute(self, arguments, context: ToolExecutionContext) -> ToolResult:
        from skills.intelligence import search_radar
        area = arguments.get("area") if isinstance(arguments, dict) else getattr(arguments, "area", None)
        result = search_radar(area=area)
        return ToolResult(output={"radars": result, "count": len(result)})


class AnalyzeBattlefieldTool(BaseTool):
    """
    战场态势分析工具
    封装 skills/intelligence.analyze_battlefield
    """

    name = "analyze_battlefield"
    description = "分析当前战场整体态势，返回威胁评估和行动建议"
    input_model = type("AnalyzeBattlefieldInput", (BaseModel,), {})

    async def execute(self, arguments, context: ToolExecutionContext) -> ToolResult:
        from skills.intelligence import analyze_battlefield
        result = analyze_battlefield()
        return ToolResult(output=result)


class AttackTargetTool(BaseTool):
    """
    打击目标工具
    封装 skills/operations.attack_target（含 OPA 权限校验）
    """

    name = "attack_target"
    description = "对指定目标执行打击命令（需指挥官权限）"
    input_model = type("AttackTargetInput", (BaseModel,), {
        "target_id": str = Field(..., description="目标实体ID"),
        "user_role": str = Field("pilot", description="用户角色"),
    })

    async def execute(self, arguments, context: ToolExecutionContext) -> ToolResult:
        from skills.operations import attack_target

        if isinstance(arguments, dict):
            target_id = arguments.get("target_id")
            user_role = arguments.get("user_role", "pilot")
        else:
            target_id = getattr(arguments, "target_id", None)
            user_role = getattr(arguments, "user_role", "pilot")

        # 权限预检（fail-fast）
        opa_hook = OPAPermissionHook()
        decision = opa_hook.enforce_attack(target_id, user_role)

        if not decision["allowed"]:
            return ToolResult(output={
                "status": "denied",
                "reason": "OPA policy rejected",
                "decision": decision
            })

        result = attack_target(target_id=target_id, user_role=user_role)
        return ToolResult(output=result)


# ============================================================================
# 第五层：OpenHarness Skill 生态系统桥接
# ============================================================================

class OpenHarnessSkillLoader:
    """
    加载 OpenHarness 官方 Skills（Markdown 格式）
    与现有 Python Skills 并存，形成双层 Skill 生态

    OpenHarness Skills 路径: ~/.openharness/skills/
    项目 Skills 路径: ./skills/
    """

    @staticmethod
    def get_openharness_skills_dir() -> str:
        """OpenHarness 官方 Skills 目录"""
        home = os.path.expanduser("~")
        return os.path.join(home, ".openharness", "skills")

    @staticmethod
    def get_project_skills_dir() -> str:
        """项目自建 Skills 目录"""
        return os.path.join(os.path.dirname(__file__), "..", "skills")

    @classmethod
    def discover_skills(cls) -> Dict[str, List[str]]:
        """发现两层 Skill 系统中的所有可用 Skills"""
        oh_dir = cls.get_openharness_skills_dir()
        proj_dir = cls.get_project_skills_dir()

        return {
            "openharness_official": os.listdir(oh_dir) if os.path.exists(oh_dir) else [],
            "project_custom": cls._discover_project_skills(proj_dir),
        }

    @staticmethod
    def _discover_project_skills(skills_dir: str) -> List[str]:
        """扫描项目 skills 目录下的 Python 模块"""
        if not os.path.exists(skills_dir):
            return []
        return [
            f.replace(".py", "")
            for f in os.listdir(skills_dir)
            if f.endswith(".py") and not f.startswith("_")
        ]


# ============================================================================
# 第六层：三 Agent 协同编排（Swarm Pattern）
# ============================================================================

class AgentRole(Enum):
    """三 Agent 角色枚举"""
    COMMANDER = "commander"   # 决策者：高权限，全局视角
    INTELLIGENCE = "intelligence"  # 感知者：情报收集，态势分析
    OPERATIONS = "operations"     # 执行者：命令下发，结果回写


class MultiAgentCoordinator:
    """
    多智能体协调器
    基于 OpenHarness Swarm 模式，实现 OODA 闭环

    协作流程：
    1. 用户输入 → Intelligence（感知 + 理解）
    2. Intelligence → Commander（威胁报告）
    3. Commander → Operations（打击命令）
    4. Operations → Intelligence（执行反馈，触发新一轮感知）
    """

    def __init__(self):
        self.memory = GraphitiMemoryAdapter()
        self.permission = OPAPermissionHook()
        self.tools = self._register_tools()

    def _register_tools(self) -> Dict[str, BaseTool]:
        """注册所有可用工具"""
        if not OH_AVAILABLE:
            return {}
        return {
            "search_radar": SearchRadarTool(),
            "analyze_battlefield": AnalyzeBattlefieldTool(),
            "attack_target": AttackTargetTool(),
        }

    async def run_ooda_loop(self, user_query: str, user_role: str = "pilot") -> Dict[str, Any]:
        """
        执行 OODA 循环（Observe → Orient → Decide → Act）

        Returns:
            包含四个阶段结果的字典
        """

        loop_results = {
            "query": user_query,
            "actor": user_role,
            "stages": {}
        }

        # ─────────────────────────────────────────────────────────────
        # Stage 1: Observe（感知）
        # Intelligence Agent 从 Graphiti + 外部传感器获取战场数据
        # ─────────────────────────────────────────────────────────────
        obs_result = await self._observe(user_query)
        loop_results["stages"]["observe"] = obs_result

        # 写入感知结果到记忆（用于后续 Orient）
        await self.memory.write(
            event_type="intelligence_observation",
            content=str(obs_result),
            metadata={"query": user_query, "stage": "observe"}
        )

        # ─────────────────────────────────────────────────────────────
        # Stage 2: Orient（理解）
        # Intelligence Agent 分析感知数据，生成威胁评估
        # ─────────────────────────────────────────────────────────────
        orient_result = await self._orient(obs_result)
        loop_results["stages"]["orient"] = orient_result

        await self.memory.write(
            event_type="intelligence_analysis",
            content=str(orient_result),
            metadata={"stage": "orient"}
        )

        # ─────────────────────────────────────────────────────────────
        # Stage 3: Decide（决策）
        # Commander Agent 根据情报做出决策（需 OPA 校验）
        # ─────────────────────────────────────────────────────────────
        decide_result = await self._decide(orient_result, user_role)
        loop_results["stages"]["decide"] = decide_result

        # 如果是高危决策，记录到审计日志
        if decide_result.get("requires_confirmation"):
            await self.memory.write(
                event_type="pending_confirmation",
                content=f"等待确认: {decide_result.get('command')}",
                metadata={"stage": "decide", "risk": "high"}
            )

        # ─────────────────────────────────────────────────────────────
        # Stage 4: Act（行动）
        # Operations Agent 执行决策并回写结果
        # ─────────────────────────────────────────────────────────────
        if decide_result.get("approved") and not decide_result.get("requires_confirmation"):
            act_result = await self._act(decide_result)
            loop_results["stages"]["act"] = act_result

            await self.memory.write(
                event_type="operation_executed",
                content=str(act_result),
                metadata={"stage": "act", "success": act_result.get("status") == "success"}
            )
        else:
            loop_results["stages"]["act"] = {"status": "pending", "reason": "awaiting_confirmation"}

        return loop_results

    async def _observe(self, query: str) -> Dict[str, Any]:
        """
        Observe: Intelligence Agent 感知战场
        """
        # 使用 Graphiti 进行语义搜索
        graph_results = await self.memory.read(query, limit=10)

        # 并行执行多个感知工具
        if OH_AVAILABLE:
            radar_tool = self.tools.get("search_radar")
            if radar_tool:
                radar_result = await radar_tool.execute({"area": None}, None)

                return {
                    "data_sources": ["graphiti_memory", "radar_search"],
                    "graphiti_results": graph_results,
                    "radar_data": radar_result.output if hasattr(radar_result, "output") else {},
                    "raw_intel": self._parse_query_to_intel(query)
                }

        return {
            "data_sources": ["graphiti_memory"],
            "graphiti_results": graph_results,
            "raw_intel": self._parse_query_to_intel(query)
        }

    async def _orient(self, obs_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orient: Intelligence Agent 理解数据，评估威胁
        """
        # 简单的规则推理（后续可接入 LLM）
        graphiti_data = obs_data.get("graphiti_results", [])
        threat_level = "unknown"

        if len(graphiti_data) > 5:
            threat_level = "high"
        elif len(graphiti_data) > 2:
            threat_level = "medium"
        else:
            threat_level = "low"

        return {
            "threat_level": threat_level,
            "entities_of_interest": [r.get("id") for r in graphiti_data[:5]],
            "recommended_action": self._recommend_action(threat_level),
            "confidence": 0.75,  # 当前规则推理置信度
        }

    async def _decide(self, orient_data: Dict[str, Any], user_role: str) -> Dict[str, Any]:
        """
        Decide: Commander Agent 做出决策（含 OPA 校验）
        """
        threat_level = orient_data.get("threat_level", "low")
        recommended = orient_data.get("recommended_action", "monitor")

        # OPA 校验
        requires_confirmation = False
        if threat_level == "high" and recommended == "attack":
            requires_confirmation = True
            if user_role != "commander":
                return {
                    "approved": False,
                    "requires_confirmation": True,
                    "reason": "高危打击需要指挥官授权",
                    "decision": "blocked_by_policy"
                }

        return {
            "approved": True,
            "requires_confirmation": requires_confirmation,
            "command": recommended,
            "threat_level": threat_level,
            "actor": user_role,
            "decision": "approved"
        }

    async def _act(self, decide_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Act: Operations Agent 执行命令
        """
        if not self.tools:
            return {"status": "no_tools_available"}

        attack_tool = self.tools.get("attack_target")
        if not attack_tool:
            return {"status": "attack_tool_not_available"}

        # 从决策中提取目标（简化：取第一个实体）
        target_id = decide_data.get("entities_of_interest", ["UNKNOWN"])[0]

        result = await attack_tool.execute(
            {"target_id": target_id, "user_role": decide_data.get("actor", "pilot")},
            None
        )
        return result.output if hasattr(result, "output") else {"status": "unknown"}

    def _parse_query_to_intel(self, query: str) -> Dict[str, Any]:
        """将用户查询解析为情报格式"""
        q = query.lower()
        return {
            "intent": "attack" if "攻击" in q else "analyze",
            "target_type": "radar" if "雷达" in q else "unknown",
            "area": next((c for c in "ABCDE" if c in q.upper()), None),
        }

    def _recommend_action(self, threat_level: str) -> str:
        """基于威胁等级推荐行动"""
        mapping = {
            "high": "attack",
            "medium": "reinforce",
            "low": "monitor",
            "unknown": "investigate"
        }
        return mapping.get(threat_level, "monitor")


# ============================================================================
# 导出接口
# ============================================================================

if __name__ == "__main__":
    # 演示 OODA 循环
    async def demo():
        coordinator = MultiAgentCoordinator()
        result = await coordinator.run_ooda_loop(
            "评估 B 区威胁并打击雷达",
            user_role="commander"
        )
        print("=== OODA 循环结果 ===")
        for stage, data in result["stages"].items():
            print(f"\n[{stage.upper()}]")
            print(data)

    if OH_AVAILABLE:
        asyncio.run(demo())
    else:
        print("OpenHarness 未安装，跳过演示")
        print("安装命令: uv add openharness")
