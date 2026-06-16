"""
Agent 统一编排器

提供单一入口，根据请求类型自动分派到正确的 Agent Loop 实现：
- DomainSwarm (OODA): 复杂多 Agent 协同任务
- IntelligenceAgent (ReAct): 简单事实性问答 + RAG
- GraphitiAgentLoop (Harness): 工具密集型任务

使用方式：
    orchestrator = AgentOrchestrator()
    result = await orchestrator.dispatch(
        query="分析态势",
        user_id="user1",
        workspace_id="ws1",
        scenario_id="sc1",
        mode="auto",
    )
"""

import uuid
import time
import logging
from typing import Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger("agent_orchestrator")


class AgentMode(str, Enum):
    """Agent 编排模式"""
    AUTO = "auto"
    SWARM = "swarm"
    REACT = "react"
    HARNESS = "harness"


# ── 关键词分类规则 ──────────────────────────────────────────────

_SWARM_KEYWORDS: List[str] = [
    "协同", "分析态势", "制定方案", "多Agent", "联合行动",
    "决策", "调度", "运营方案", "综合分析", "协同运营",
]

_REACT_KEYWORDS: List[str] = [
    "是什么", "什么是", "查询", "解释", "定义",
    "有多少", "列出", "描述", "说明", "比较",
    "如何", "为什么", "原因", "历史",
]

_HARNESS_KEYWORDS: List[str] = [
    "执行", "调用", "运行", "部署", "启动",
    "停止", "创建", "删除", "更新", "操作",
]


def _classify_query(query: str) -> AgentMode:
    """
    基于关键词的查询分类器。

    优先级: swarm > harness > react（react 作为默认兜底）
    """
    scores: Dict[AgentMode, int] = {
        AgentMode.SWARM: 0,
        AgentMode.REACT: 0,
        AgentMode.HARNESS: 0,
    }

    for kw in _SWARM_KEYWORDS:
        if kw in query:
            scores[AgentMode.SWARM] += 1

    for kw in _REACT_KEYWORDS:
        if kw in query:
            scores[AgentMode.REACT] += 1

    for kw in _HARNESS_KEYWORDS:
        if kw in query:
            scores[AgentMode.HARNESS] += 1

    max_score = max(scores.values())
    if max_score == 0:
        return AgentMode.REACT

    # 优先级: swarm > harness > react
    for mode in (AgentMode.SWARM, AgentMode.HARNESS, AgentMode.REACT):
        if scores[mode] == max_score:
            return mode

    return AgentMode.REACT


def _build_agent_result(
    *,
    mode: str,
    answer: str,
    reasoning_chain: Optional[List[Dict[str, Any]]] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """构造统一的 AgentResult 字典"""
    return {
        "result_id": str(uuid.uuid4()),
        "mode": mode,
        "answer": answer,
        "reasoning_chain": reasoning_chain or [],
        "sources": sources or [],
        "metadata": metadata or {},
        "error": error,
    }


class AgentOrchestrator:
    """
    Agent 统一编排器（单例模式）

    提供单一 dispatch 方法，根据 mode 参数选择对应的 Agent Loop：
    - auto: 自动分类
    - swarm: DomainSwarm (OODA)
    - react: IntelligenceAgent (ReAct + RAG)
    - harness: GraphitiAgentLoop (OpenHarness v2)
    """

    _instance: Optional["AgentOrchestrator"] = None

    def __new__(cls) -> "AgentOrchestrator":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        # 延迟加载的实例
        self._swarm = None
        self._intelligence_agent = None
        self._harness_loop = None

        # 可用性标记
        self._swarm_available: Optional[bool] = None
        self._react_available: Optional[bool] = None
        self._harness_available: Optional[bool] = None

        logger.info("AgentOrchestrator 初始化完成")

    # ── 延迟加载各 Agent Loop ──────────────────────────────────

    def _get_swarm(self):
        """延迟加载 DomainSwarm"""
        if self._swarm is not None:
            return self._swarm
        try:
            from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
            self._swarm = DomainSwarm()
            self._swarm_available = True
            logger.info("DomainSwarm 加载成功")
        except Exception as e:
            self._swarm_available = False
            logger.warning(f"DomainSwarm 加载失败: {e}")
            self._swarm = None
        return self._swarm

    def _get_intelligence_agent(self):
        """延迟加载 IntelligenceAgent"""
        if self._intelligence_agent is not None:
            return self._intelligence_agent
        try:
            from odap.biz.core.agent.intelligence_agent import IntelligenceAgent
            self._intelligence_agent = IntelligenceAgent()
            self._react_available = True
            logger.info("IntelligenceAgent 加载成功")
        except Exception as e:
            self._react_available = False
            logger.warning(f"IntelligenceAgent 加载失败: {e}")
            self._intelligence_agent = None
        return self._intelligence_agent

    def _get_harness_loop(self):
        """延迟加载 GraphitiAgentLoop"""
        if self._harness_loop is not None:
            return self._harness_loop
        try:
            from odap.infra.openharness.engine_adapter import GraphitiAgentLoop
            self._harness_loop = GraphitiAgentLoop()
            self._harness_available = True
            logger.info("GraphitiAgentLoop 加载成功")
        except Exception as e:
            self._harness_available = False
            logger.warning(f"GraphitiAgentLoop 加载失败: {e}")
            self._harness_loop = None
        return self._harness_loop

    # ── 核心分派方法 ────────────────────────────────────────────

    async def dispatch(
        self,
        query: str,
        user_id: str,
        workspace_id: str,
        scenario_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        mode: str = "auto",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        统一分派入口。

        Args:
            query: 用户查询
            user_id: 用户 ID
            workspace_id: 工作空间 ID
            scenario_id: 场景 ID（可选）
            agent_id: 指定 Agent ID（可选）
            mode: 编排模式 "auto" | "swarm" | "react" | "harness"
            session_id: 会话 ID（可选），用于持久化聊天历史

        Returns:
            统一的 AgentResult 字典
        """
        start_time = time.perf_counter()

        # 解析 mode
        try:
            resolved_mode = AgentMode(mode)
        except ValueError:
            logger.warning(f"无效的 mode 参数: {mode}，回退到 auto")
            resolved_mode = AgentMode.AUTO

        # auto 模式下自动分类
        if resolved_mode == AgentMode.AUTO:
            resolved_mode = _classify_query(query)
            logger.info(f"auto 模式分类结果: {resolved_mode.value} (query: {query[:50]})")

        logger.info(
            f"AgentOrchestrator.dispatch: mode={resolved_mode.value}, "
            f"user={user_id}, ws={workspace_id}, query={query[:80]}"
        )

        # 分派到对应 Loop
        try:
            if resolved_mode == AgentMode.SWARM:
                result = await self._dispatch_swarm(query, workspace_id, scenario_id)
            elif resolved_mode == AgentMode.REACT:
                result = await self._dispatch_react(query, workspace_id, scenario_id)
            elif resolved_mode == AgentMode.HARNESS:
                result = await self._dispatch_harness(query, workspace_id, scenario_id, session_id)
            else:
                result = _build_agent_result(
                    mode="unknown",
                    answer="",
                    error=f"未知的编排模式: {resolved_mode}",
                )
        except Exception as e:
            logger.error(f"Agent Loop 执行失败 (mode={resolved_mode.value}): {e}")
            result = _build_agent_result(
                mode=resolved_mode.value,
                answer="",
                error=f"执行失败: {str(e)}",
            )

        # 补充元数据
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        result["metadata"].update({
            "user_id": user_id,
            "workspace_id": workspace_id,
            "scenario_id": scenario_id,
            "agent_id": agent_id,
            "requested_mode": mode,
            "resolved_mode": resolved_mode.value,
            "orchestration_time_ms": elapsed_ms,
        })

        logger.info(
            f"AgentOrchestrator.dispatch 完成: mode={resolved_mode.value}, "
            f"time={elapsed_ms}ms, error={result.get('error')}"
        )

        return result

    # ── 各 Loop 分派实现 ────────────────────────────────────────

    async def _dispatch_swarm(
        self,
        query: str,
        workspace_id: str,
        scenario_id: Optional[str],
    ) -> Dict[str, Any]:
        """分派到 DomainSwarm (OODA)"""
        swarm = self._get_swarm()
        if swarm is None:
            # 降级到 ReAct
            logger.warning("DomainSwarm 不可用，降级到 IntelligenceAgent (ReAct)")
            return await self._dispatch_react(query, workspace_id, scenario_id)

        # 先尝试 execute_mission（完整 OODA 循环）
        try:
            mission_result = await swarm.execute_mission(
                mission=query,
                context={"workspace_id": workspace_id, "scenario_id": scenario_id},
            )

            # 将 MissionResult 转换为统一格式
            reasoning_chain = []
            for phase in mission_result.phases_completed:
                reasoning_chain.append({
                    "phase": phase.value,
                    "description": f"OODA {phase.value} 阶段完成",
                })

            answer = ""
            if mission_result.final_decision:
                recommended = mission_result.final_decision.get("recommended_action", {})
                answer = recommended.get("description", "") if recommended else ""
                if not answer:
                    answer = mission_result.final_decision.get("situation_summary", "")

            return _build_agent_result(
                mode=AgentMode.SWARM.value,
                answer=answer or "OODA 循环已完成",
                reasoning_chain=reasoning_chain,
                sources=[],
                metadata={
                    "mission_id": mission_result.mission_id,
                    "success": mission_result.success,
                    "execution_time_ms": mission_result.execution_time_ms,
                    "graphiti_episodes": mission_result.graphiti_episodes,
                    "error_message": mission_result.error_message,
                },
                error=mission_result.error_message,
            )
        except Exception as e:
            logger.warning(f"DomainSwarm execute_mission 失败: {e}，尝试 dispatch_intent")

        # 降级到 dispatch_intent
        try:
            dispatch_result = await swarm.dispatch_intent(
                intent=query,
                context={"workspace_id": workspace_id, "scenario_id": scenario_id},
                workspace_id=workspace_id,
            )

            reasoning_chain = []
            for step in dispatch_result.get("plan", []):
                reasoning_chain.append({
                    "sub_agent": step.get("sub_agent", ""),
                    "action": step.get("action", ""),
                })

            return _build_agent_result(
                mode=AgentMode.SWARM.value,
                answer=f"任务已分派到 {dispatch_result.get('assigned_agent', 'unknown')} Agent",
                reasoning_chain=reasoning_chain,
                sources=[],
                metadata={
                    "task_id": dispatch_result.get("task_id"),
                    "assigned_agent": dispatch_result.get("assigned_agent"),
                    "confidence": dispatch_result.get("confidence"),
                    "routing_source": dispatch_result.get("routing_source"),
                },
            )
        except Exception as e:
            logger.error(f"DomainSwarm dispatch_intent 也失败: {e}")
            return _build_agent_result(
                mode=AgentMode.SWARM.value,
                answer="",
                error=f"DomainSwarm 执行失败: {str(e)}",
            )

    async def _dispatch_react(
        self,
        query: str,
        workspace_id: str,
        scenario_id: Optional[str],
    ) -> Dict[str, Any]:
        """分派到 IntelligenceAgent (ReAct + RAG)"""
        agent = self._get_intelligence_agent()
        if agent is None:
            logger.warning("IntelligenceAgent 不可用，返回错误")
            return _build_agent_result(
                mode=AgentMode.REACT.value,
                answer="",
                error="IntelligenceAgent 不可用，请检查 LLM 配置",
            )

        report = await agent.analyze(query)

        # 从 IntelligenceAgent 报告中提取统一格式
        answer = report.get("summary", "")
        if not answer and "raw_response" in report:
            answer = report.get("raw_response", "")[:500]

        # 构建推理链
        reasoning_chain = []
        metadata = report.get("_metadata", {})
        for tc in metadata.get("tool_calls", []):
            reasoning_chain.append({
                "tool": tc.get("tool", ""),
                "args": tc.get("args", {}),
                "result_preview": tc.get("result_preview", ""),
            })

        # 构建来源列表
        sources = []
        for key in ("opponent_units", "own_status", "public_risk"):
            items = report.get(key, [])
            if items:
                sources.append({"type": key, "count": len(items)})

        # 提取 trace 信息
        trace = report.get("_trace", {})

        return _build_agent_result(
            mode=AgentMode.REACT.value,
            answer=answer,
            reasoning_chain=reasoning_chain,
            sources=sources,
            metadata={
                "threat_level": report.get("threat_level", "unknown"),
                "iterations": metadata.get("iterations", 0),
                "execution_time_ms": metadata.get("execution_time_ms", 0),
                "rag_context_provided": metadata.get("rag_context_provided", False),
                "trace_id": trace.get("trace_id"),
                "parsing": report.get("parsing"),
            },
            error=report.get("error"),
        )

    async def _dispatch_harness(
        self,
        query: str,
        workspace_id: str,
        scenario_id: Optional[str],
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """分派到 GraphitiAgentLoop (OpenHarness v2)"""
        loop = self._get_harness_loop()
        if loop is None:
            logger.warning("GraphitiAgentLoop 不可用，降级到 IntelligenceAgent (ReAct)")
            return await self._dispatch_react(query, workspace_id, scenario_id)

        context = {
            "workspace_id": workspace_id,
            "scenario_id": scenario_id,
            "session_id": session_id or "",
        }
        harness_result = await loop.run(user_input=query, context=context)

        # 从 GraphitiAgentLoop 结果中提取统一格式
        success = harness_result.get("success", False)
        steps = harness_result.get("steps", [])
        final_obs = harness_result.get("final_observation", {})

        # 构建推理链
        reasoning_chain = []
        for step in steps:
            action = step.get("action", {})
            reasoning_chain.append({
                "step": step.get("step", 0),
                "tool_name": action.get("tool_name", ""),
                "thought": action.get("thought", ""),
                "timestamp": step.get("timestamp", ""),
            })

        # 构建答案
        answer = ""
        if steps:
            last_step = steps[-1]
            last_result = last_step.get("result", {})
            if isinstance(last_result, dict) and last_result.get("status") == "success":
                data = last_result.get("data", {})
                if isinstance(data, dict):
                    answer = data.get("summary", "") or data.get("result", str(data))
                elif isinstance(data, list):
                    answer = f"获取到 {len(data)} 条结果"
                else:
                    answer = str(data)

        if not answer:
            answer = "工具执行完成" if success else "工具执行失败"

        return _build_agent_result(
            mode=AgentMode.HARNESS.value,
            answer=answer,
            reasoning_chain=reasoning_chain,
            sources=[],
            metadata={
                "success": success,
                "total_steps": harness_result.get("total_steps", 0),
                "final_state": final_obs.get("state", ""),
                "tools_available": final_obs.get("tools_available", []),
            },
            error=None if success else "Harness 执行未成功",
        )

    # ── 状态查询 ────────────────────────────────────────────────

    def get_availability(self) -> Dict[str, bool]:
        """获取各 Agent Loop 的可用状态"""
        # 触发延迟加载以确定可用性
        self._get_swarm()
        self._get_intelligence_agent()
        self._get_harness_loop()

        return {
            "swarm": self._swarm_available is True,
            "react": self._react_available is True,
            "harness": self._harness_available is True,
        }
