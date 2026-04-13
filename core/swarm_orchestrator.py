"""
Swarm 编排器核心模块
基于 OpenHarness Swarm 的多 Agent 协同编排器，实现战场三 Agent（Commander/Intelligence/Operations）的 OODA 循环协同。

Phase 2: 三 Agent 协同 OODA
- Slice 2.1: Commander Agent
- Slice 2.2: Operations Agent
- Slice 2.3: Swarm 编排器
- Slice 2.4: OODA 闭环测试
"""

import json
import uuid
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, AsyncGenerator, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger("swarm_orchestrator")


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


class OODAStatus(str, Enum):
    """OODA 执行状态"""
    STARTED = "started"
    COMPLETED = "completed"
    WAITING_CONFIRMATION = "waiting_confirmation"
    ERROR = "error"


class AgentState(str, Enum):
    """Agent 执行状态"""
    IDLE = "idle"
    RUNNING = "running"
    FAILED = "failed"
    DEGRADED = "degraded"
    RECOVERING = "recovering"


@dataclass
class OODAProgress:
    """OODA 执行进度"""
    phase: OODAPhase
    status: OODAStatus
    agent: AgentType
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "status": self.status.value,
            "agent": self.agent.value,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MissionResult:
    """任务执行结果"""
    mission_id: str
    success: bool
    phases_completed: List[OODAPhase]
    final_decision: Optional[Dict[str, Any]] = None
    execution_time_ms: float = 0.0
    graphiti_episodes: List[str] = field(default_factory=list)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "success": self.success,
            "phases_completed": [p.value for p in self.phases_completed],
            "final_decision": self.final_decision,
            "execution_time_ms": self.execution_time_ms,
            "graphiti_episodes": self.graphiti_episodes,
            "error_message": self.error_message,
        }


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str
    agent_type: AgentType
    model: str
    role: str
    tools: List[str]
    permission_level: str
    memory_backend: str = "graphiti"
    requires_opa_approval: bool = False


class CommanderAgent:
    """Commander Agent - 决策中枢"""

    def __init__(self, config: AgentConfig, opa_manager, graph_manager):
        self.config = config
        self.opa_manager = opa_manager
        self.graph_manager = graph_manager
        self.state = AgentState.IDLE

    async def analyze_situation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """分析当前态势，制定决策方案"""
        self.state = AgentState.RUNNING
        try:
            intel_data = context.get("intel_data", {})
            threat_level = intel_data.get("threat_level", "unknown")

            options = self._generate_options(intel_data)

            decision = {
                "situation_summary": intel_data.get("summary", "未知态势"),
                "threat_level": threat_level,
                "recommended_action": self._select_best_option(options),
                "options": options,
                "requires_confirmation": threat_level == "critical",
                "decision_time": datetime.now(timezone.utc).isoformat(),
            }

            self.state = AgentState.IDLE
            return decision
        except Exception as e:
            self.state = AgentState.FAILED
            logger.error(f"Commander 分析失败: {e}")
            raise

    def _generate_options(self, intel_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成多个决策选项"""
        options = []

        enemy_units = intel_data.get("enemy_units", [])
        if enemy_units:
            options.append({
                "id": "option_1",
                "type": "strike",
                "description": "对敌方单位实施精确打击",
                "targets": [u.get("id") for u in enemy_units[:3]],
                "risk_level": "high",
            })

        civilian_risk = intel_data.get("civilian_risk", [])
        if not civilian_risk:
            options.append({
                "id": "option_2",
                "type": "observe",
                "description": "保持监控，持续收集情报",
                "targets": [],
                "risk_level": "low",
            })

        recommendations = intel_data.get("recommendations", [])
        if recommendations:
            options.append({
                "id": "option_3",
                "type": "coordinate",
                "description": recommendations[0] if recommendations else "协调友军",
                "targets": [],
                "risk_level": "medium",
            })

        return options

    def _select_best_option(self, options: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """选择最佳决策选项"""
        if not options:
            return None
        for opt in options:
            if opt.get("risk_level") == "medium":
                return opt
        return options[0] if options else None


class OperationsAgent:
    """Operations Agent - 执行中枢"""

    def __init__(self, config: AgentConfig, opa_manager, graph_manager):
        self.config = config
        self.opa_manager = opa_manager
        self.graph_manager = graph_manager
        self.state = AgentState.IDLE
        self.pending_confirmations: Dict[str, Dict[str, Any]] = {}

    async def execute_order(self, order: Dict[str, Any], confirmation_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """执行指挥官下达的命令"""
        self.state = AgentState.RUNNING

        order_type = order.get("type")
        targets = order.get("targets", [])

        if order.get("requires_confirmation"):
            order_id = str(uuid.uuid4())
            self.pending_confirmations[order_id] = order

            if confirmation_callback:
                confirmed = await confirmation_callback(order)
                if not confirmed:
                    self.state = AgentState.IDLE
                    return {"status": "cancelled", "order_id": order_id}

        results = []
        for target_id in targets:
            result = await self._execute_action(order_type, target_id, order)
            results.append(result)

        self.state = AgentState.IDLE
        return {
            "status": "completed",
            "order_type": order_type,
            "results": results,
            "execution_time": datetime.now(timezone.utc).isoformat(),
        }

    async def _execute_action(self, action_type: str, target_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个行动"""
        try:
            if action_type == "strike":
                from skills import SKILL_CATALOG
                if "attack_target" in SKILL_CATALOG:
                    result = SKILL_CATALOG["attack_target"]["handler"](
                        target_id=target_id,
                        user_role=self.config.permission_level
                    )
                    return {"target_id": target_id, "status": "success", "result": result}
            return {"target_id": target_id, "status": "skipped", "reason": "no_handler"}
        except Exception as e:
            logger.error(f"执行行动失败 {action_type}/{target_id}: {e}")
            return {"target_id": target_id, "status": "failed", "error": str(e)}


class IntelligenceAgentSwarm:
    """Intelligence Agent Swarm 版本 - 用于多 Agent 协同"""

    def __init__(self, config: AgentConfig, graph_manager, opa_manager=None):
        self.config = config
        self.graph_manager = graph_manager
        self.opa_manager = opa_manager
        self.state = AgentState.IDLE

    async def gather_intelligence(self, mission: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """收集情报"""
        self.state = AgentState.RUNNING

        from skills import SKILL_CATALOG

        results = {}

        if "analyze_battlefield" in SKILL_CATALOG:
            try:
                results["battlefield"] = SKILL_CATALOG["analyze_battlefield"]["handler"]()
            except Exception as e:
                logger.warning(f"analyze_battlefield 失败: {e}")

        if "analyze_force_comparison" in SKILL_CATALOG:
            try:
                results["force_comparison"] = SKILL_CATALOG["analyze_force_comparison"]["handler"]()
            except Exception as e:
                logger.warning(f"analyze_force_comparison 失败: {e}")

        threat_level = "medium"
        if results.get("battlefield"):
            summary = str(results["battlefield"])
            if "high" in summary.lower() or "critical" in summary.lower():
                threat_level = "high"
            elif "low" in summary.lower():
                threat_level = "low"

        self.state = AgentState.IDLE
        return {
            "summary": results.get("battlefield", {}).get("summary", "情报收集完成"),
            "threat_level": threat_level,
            "enemy_units": results.get("force_comparison", {}).get("enemy_units", []),
            "friendly_status": results.get("force_comparison", {}).get("friendly_units", []),
            "civilian_risk": [],
            "recommendations": results.get("battlefield", {}).get("recommendations", []),
            "raw_data": results,
        }


class BattlefieldSwarm:
    """战场多 Agent Swarm 编排器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()

        from core.opa_manager import OPAManager
        from core.graph_manager import BattlefieldGraphManager

        self.opa_manager = OPAManager()
        self.graph_manager = BattlefieldGraphManager()

        self.agents = self._initialize_agents()
        self.active_missions: Dict[str, Dict[str, Any]] = {}
        self.mission_history: List[MissionResult] = []

    def _default_config(self) -> Dict[str, Any]:
        return {
            "coordinator": {
                "max_parallel_agents": 3,
                "task_timeout_seconds": 300,
                "retry_attempts": 2,
            },
            "ooda": {
                "confirm_before_act": True,
                "write_to_graphiti": True,
            },
        }

    def _initialize_agents(self) -> Dict[AgentType, Any]:
        """初始化三个 Agent"""
        intel_config = AgentConfig(
            name="Intelligence",
            agent_type=AgentType.INTELLIGENCE,
            model="deepseek-chat",
            role="intelligence_analyst",
            tools=["*"],
            permission_level="intelligence",
        )

        commander_config = AgentConfig(
            name="Commander",
            agent_type=AgentType.COMMANDER,
            model="claude-3-5-sonnet",
            role="commander",
            tools=["*"],
            permission_level="commander",
        )

        operations_config = AgentConfig(
            name="Operations",
            agent_type=AgentType.OPERATIONS,
            model="qwen-plus",
            role="operations_officer",
            tools=["*"],
            permission_level="operations",
            requires_opa_approval=True,
        )

        return {
            AgentType.INTELLIGENCE: IntelligenceAgentSwarm(intel_config, self.graph_manager, self.opa_manager),
            AgentType.COMMANDER: CommanderAgent(commander_config, self.opa_manager, self.graph_manager),
            AgentType.OPERATIONS: OperationsAgent(operations_config, self.opa_manager, self.graph_manager),
        }

    async def initialize(self) -> None:
        """初始化 Swarm"""
        logger.info("BattlefieldSwarm 初始化中...")

        try:
            self.graph_manager.initialize_graph()
            logger.info("Graphiti 连接正常")
        except Exception as e:
            logger.warning(f"Graphiti 初始化失败: {e}")
            logger.warning("将使用 fallback 模式")

        logger.info(f"已初始化 {len(self.agents)} 个 Agent")
        for agent_type, agent in self.agents.items():
            logger.info(f"  - {agent_type.value}: {type(agent).__name__}")

    async def execute_mission(self, mission: str, context: Optional[Dict[str, Any]] = None) -> MissionResult:
        """执行完整 OODA 循环"""
        mission_id = str(uuid.uuid4())[:16]
        start_time = time.perf_counter()

        logger.info(f"[{mission_id}] 开始执行任务: {mission}")

        mission_ctx = {
            "mission": mission,
            "context": context or {},
            "phases_completed": [],
            "graphiti_episodes": [],
            "error": None,
        }

        self.active_missions[mission_id] = mission_ctx

        try:
            observe_result = await self._observe(mission, context)
            mission_ctx["phases_completed"].append(OODAPhase.OBSERVE)
            logger.info(f"[{mission_id}] Observe 阶段完成")

            orient_result = await self._orient(observe_result, context)
            mission_ctx["phases_completed"].append(OODAPhase.ORIENT)
            logger.info(f"[{mission_id}] Orient 阶段完成")

            decide_result = await self._decide(orient_result, context)
            mission_ctx["phases_completed"].append(OODAPhase.DECIDE)
            logger.info(f"[{mission_id}] Decide 阶段完成")

            act_result = await self._act(decide_result, context)
            mission_ctx["phases_completed"].append(OODAPhase.ACT)
            logger.info(f"[{mission_id}] Act 阶段完成")

            if self.config.get("ooda", {}).get("write_to_graphiti", True):
                await self._write_episodes(mission_ctx)

            execution_time_ms = (time.perf_counter() - start_time) * 1000

            result = MissionResult(
                mission_id=mission_id,
                success=True,
                phases_completed=mission_ctx["phases_completed"],
                final_decision=decide_result,
                execution_time_ms=round(execution_time_ms, 2),
                graphiti_episodes=mission_ctx["graphiti_episodes"],
            )

            logger.info(f"[{mission_id}] 任务完成，耗时: {execution_time_ms:.2f}ms")

        except Exception as e:
            import traceback
            logger.error(f"[{mission_id}] 任务执行失败: {e}")
            logger.error(f"[{mission_id}] 详细错误: {traceback.format_exc()}")
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            result = MissionResult(
                mission_id=mission_id,
                success=False,
                phases_completed=mission_ctx["phases_completed"],
                execution_time_ms=round(execution_time_ms, 2),
                error_message=str(e),
            )

        self.mission_history.append(result)
        if mission_id in self.active_missions:
            del self.active_missions[mission_id]

        return result

    async def execute_streaming(self, mission: str, context: Optional[Dict[str, Any]] = None) -> AsyncGenerator[OODAProgress, None]:
        """流式执行 OODA 循环，逐步返回进度"""
        mission_id = str(uuid.uuid4())[:16]

        yield OODAProgress(
            phase=OODAPhase.OBSERVE,
            status=OODAStatus.STARTED,
            agent=AgentType.INTELLIGENCE,
            message="开始感知阶段",
        )

        try:
            observe_result = await self._observe(mission, context)
            yield OODAProgress(
                phase=OODAPhase.OBSERVE,
                status=OODAStatus.COMPLETED,
                agent=AgentType.INTELLIGENCE,
                data=observe_result,
            )
        except Exception as e:
            yield OODAProgress(
                phase=OODAPhase.OBSERVE,
                status=OODAStatus.ERROR,
                agent=AgentType.INTELLIGENCE,
                message=str(e),
            )
            return

        yield OODAProgress(
            phase=OODAPhase.ORIENT,
            status=OODAStatus.STARTED,
            agent=AgentType.INTELLIGENCE,
            message="开始理解阶段",
        )

        try:
            orient_result = await self._orient(observe_result, context)
            yield OODAProgress(
                phase=OODAPhase.ORIENT,
                status=OODAStatus.COMPLETED,
                agent=AgentType.INTELLIGENCE,
                data=orient_result,
            )
        except Exception as e:
            yield OODAProgress(
                phase=OODAPhase.ORIENT,
                status=OODAStatus.ERROR,
                agent=AgentType.INTELLIGENCE,
                message=str(e),
            )
            return

        yield OODAProgress(
            phase=OODAPhase.DECIDE,
            status=OODAStatus.STARTED,
            agent=AgentType.COMMANDER,
            message="开始决策阶段",
        )

        try:
            decide_result = await self._decide(orient_result, context)

            if decide_result.get("requires_confirmation"):
                yield OODAProgress(
                    phase=OODAPhase.DECIDE,
                    status=OODAStatus.WAITING_CONFIRMATION,
                    agent=AgentType.COMMANDER,
                    message="等待人工确认",
                    data=decide_result,
                )
                return

            yield OODAProgress(
                phase=OODAPhase.DECIDE,
                status=OODAStatus.COMPLETED,
                agent=AgentType.COMMANDER,
                data=decide_result,
            )
        except Exception as e:
            yield OODAProgress(
                phase=OODAPhase.DECIDE,
                status=OODAStatus.ERROR,
                agent=AgentType.COMMANDER,
                message=str(e),
            )
            return

        yield OODAProgress(
            phase=OODAPhase.ACT,
            status=OODAStatus.STARTED,
            agent=AgentType.OPERATIONS,
            message="开始行动阶段",
        )

        try:
            act_result = await self._act(decide_result, context)
            yield OODAProgress(
                phase=OODAPhase.ACT,
                status=OODAStatus.COMPLETED,
                agent=AgentType.OPERATIONS,
                data=act_result,
            )
        except Exception as e:
            yield OODAProgress(
                phase=OODAPhase.ACT,
                status=OODAStatus.ERROR,
                agent=AgentType.OPERATIONS,
                message=str(e),
            )

    async def _observe(self, mission: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Observe 阶段 - Intelligence 感知"""
        logger.info(f"[Observe] 收集情报: {mission}")
        agent = self.agents[AgentType.INTELLIGENCE]
        return await agent.gather_intelligence(mission, context)

    async def _orient(self, observe_result: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Orient 阶段 - Intelligence 理解分析"""
        logger.info("[Orient] 分析威胁模式")

        rag_context = self.graph_manager.retrieve_rag_context(
            observe_result.get("summary", ""),
            top_k=3
        )

        oriented = {
            **observe_result,
            "historical_context": rag_context,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return oriented

    async def _decide(self, orient_result: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Decide 阶段 - Commander 决策"""
        logger.info("[Decide] 制定行动方案")
        agent = self.agents[AgentType.COMMANDER]
        return await agent.analyze_situation(orient_result)

    async def _act(self, decide_result: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Act 阶段 - Operations 执行"""
        logger.info(f"[Act] 执行命令: {decide_result.get('recommended_action')}")

        recommended = decide_result.get("recommended_action", {})
        order = {
            "type": recommended.get("type", "observe"),
            "targets": recommended.get("targets", []),
            "requires_confirmation": decide_result.get("requires_confirmation", False),
            "description": recommended.get("description", ""),
        }

        agent = self.agents[AgentType.OPERATIONS]
        return await agent.execute_order(order)

    async def _write_episodes(self, mission_ctx: Dict[str, Any]) -> None:
        """写 Graphiti Episode"""
        try:
            episode_text = f"任务: {mission_ctx['mission']}\n"
            episode_text += f"完成阶段: {[p.value for p in mission_ctx['phases_completed']]}\n"
            episode_text += f"最终决策: {json.dumps(mission_ctx.get('final_decision', {}), ensure_ascii=False, default=str)}"

            success = self.graph_manager.add_episode(
                name=f"mission_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                content=episode_text,
                source_description="BattlefieldSwarm/OODA",
            )

            if success:
                mission_ctx["graphiti_episodes"].append("ooda_mission_episode")
        except Exception as e:
            logger.warning(f"Graphiti 写入失败: {e}")

    async def shutdown(self) -> None:
        """关闭 Swarm"""
        logger.info("BattlefieldSwarm 关闭中...")
        self.active_missions.clear()
        logger.info("BattlefieldSwarm 已关闭")

    def get_mission_history(self) -> List[Dict[str, Any]]:
        """获取任务历史"""
        return [r.to_dict() for r in self.mission_history]


if __name__ == "__main__":
    import asyncio

    async def main():
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(message)s",
        )

        swarm = BattlefieldSwarm()
        await swarm.initialize()

        print("\n" + "=" * 60)
        print("BattlefieldSwarm OODA 循环测试")
        print("=" * 60)

        result = await swarm.execute_mission("分析B区威胁并采取行动")

        print("\n任务结果:")
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

        print("\n历史记录:")
        for r in swarm.get_mission_history():
            print(f"  - {r['mission_id']}: {'✅' if r['success'] else '❌'} {r['execution_time_ms']:.2f}ms")

        await swarm.shutdown()

    asyncio.run(main())