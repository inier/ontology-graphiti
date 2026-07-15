"""Swarm 适配器 — 基于 OpenHarness Swarm 模块实现

复用 OH 的 TeammateExecutor + InProcessBackend + TeamLifecycleManager，
提供进程内多 Agent 协同执行能力。

OH Swarm 架构：
  TeammateExecutor (Protocol) → spawn() / send_message() / shutdown()
  InProcessBackend → asyncio.Task + ContextVar 隔离
  TeamLifecycleManager → 团队 CRUD + team.json 持久化
  TeammateMailbox → 文件邮箱消息队列
"""

import logging
import os
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 延迟导入标记
_OH_SWARM_AVAILABLE = False
try:
    from openharness.swarm.types import (
        TeammateSpawnConfig,
        TeammateMessage,
        SpawnResult,
    )
    _OH_SWARM_AVAILABLE = True
except ImportError:
    pass


class SwarmAdapter:
    """基于 OpenHarness Swarm 的多 Agent 协同适配器

    核心方法委托给 OH 的 InProcessBackend 和 TeamLifecycleManager，
    不自建任何 Agent 执行逻辑。
    """

    def __init__(self):
        self._backend = None  # InProcessBackend 实例
        self._lifecycle = None  # TeamLifecycleManager 实例
        self._available = False
        self._teams: Dict[str, Dict[str, Any]] = {}  # team_name → team info
        self._init_swarm()

    def _init_swarm(self):
        """初始化 OH Swarm 组件"""
        if not _OH_SWARM_AVAILABLE:
            logger.debug("SwarmAdapter: OpenHarness Swarm 不可用")
            return

        try:
            from openharness.swarm.in_process import InProcessBackend
            from openharness.swarm.team_lifecycle import TeamLifecycleManager

            self._backend = InProcessBackend()
            self._lifecycle = TeamLifecycleManager()
            self._available = True
            logger.info("SwarmAdapter: OpenHarness Swarm 初始化成功 (InProcessBackend)")
        except Exception as e:
            logger.warning("SwarmAdapter: 初始化失败: %s", e)
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    async def create_swarm(self, agents: List[Dict[str, Any]],
                           config: Dict[str, Any] = None) -> Dict[str, Any]:
        """创建 Swarm 团队

        委托给 OH TeamLifecycleManager.create_team() 创建团队，
        然后通过 InProcessBackend.spawn() 生成每个 Agent。

        Args:
            agents: Agent 配置列表，每项含 name, prompt, system_prompt 等
            config: 可选配置，含 team_name 等
        """
        if not self._available:
            return {"status": "error", "message": "OpenHarness Swarm not available"}

        team_name = (config or {}).get("team_name", f"team-{uuid.uuid4().hex[:8]}")
        parent_session_id = (config or {}).get("session_id", uuid.uuid4().hex[:12])

        try:
            # 1. 通过 TeamLifecycleManager 创建团队
            if self._lifecycle:
                team = self._lifecycle.create_team(
                    name=team_name,
                    description=f"ODAP swarm team with {len(agents)} agents",
                )
                team_id = team.name if hasattr(team, 'name') else team_name
            else:
                team_id = team_name

            # 2. 通过 InProcessBackend spawn 每个 Agent
            spawned_agents = []
            for agent_cfg in agents:
                agent_name = agent_cfg.get("name", f"agent-{uuid.uuid4().hex[:6]}")
                spawn_config = TeammateSpawnConfig(
                    name=agent_name,
                    team=team_name,
                    prompt=agent_cfg.get("prompt", ""),
                    cwd=agent_cfg.get("cwd", os.getcwd()),
                    parent_session_id=parent_session_id,
                    model=agent_cfg.get("model"),
                    system_prompt=agent_cfg.get("system_prompt"),
                    color=agent_cfg.get("color"),
                )

                result: SpawnResult = await self._backend.spawn(spawn_config)
                if result.success:
                    spawned_agents.append({
                        "agent_id": result.agent_id,
                        "task_id": result.task_id,
                        "name": agent_name,
                        "backend_type": result.backend_type,
                    })
                else:
                    logger.warning("SwarmAdapter: spawn %s 失败: %s",
                                   agent_name, result.error)

            # 3. 记录团队信息
            self._teams[team_name] = {
                "team_id": team_id,
                "parent_session_id": parent_session_id,
                "agents": spawned_agents,
            }

            return {
                "status": "success",
                "team_name": team_name,
                "swarm_id": team_id,
                "agents_count": len(spawned_agents),
                "agents": spawned_agents,
            }
        except Exception as e:
            logger.error("SwarmAdapter: create_swarm 失败: %s", e)
            return {"status": "error", "message": str(e)}

    async def run_swarm(self, swarm_id: str, task: str,
                        context: Dict[str, Any] = None) -> Dict[str, Any]:
        """向 Swarm 团队中的 Agent 发送任务消息

        委托给 OH InProcessBackend.send_message() 发送消息到指定 Agent。

        Args:
            swarm_id: 团队名称（create_swarm 返回的 team_name）
            task: 任务描述
            context: 可选上下文
        """
        if not self._available:
            return {"status": "error", "message": "OpenHarness Swarm not available"}

        team_info = self._teams.get(str(swarm_id))
        if not team_info:
            return {"status": "error", "message": f"Swarm team '{swarm_id}' not found"}

        try:
            agents = team_info.get("agents", [])
            steps = []

            # 向团队中所有 Agent 广播任务
            for agent_info in agents:
                agent_id = agent_info.get("agent_id", "")
                if not agent_id:
                    continue

                message = TeammateMessage(
                    text=task,
                    from_agent="leader",
                    summary=task[:80],
                )
                await self._backend.send_message(agent_id, message)
                steps.append({
                    "agent_id": agent_id,
                    "agent_name": agent_info.get("name", ""),
                    "action": "message_sent",
                    "task": task[:100],
                })

            return {
                "status": "success",
                "task": task,
                "steps": steps,
                "agents_contacted": len(steps),
            }
        except Exception as e:
            logger.error("SwarmAdapter: run_swarm 失败: %s", e)
            return {"status": "error", "message": str(e)}

    async def list_agents(self, swarm_id: str = None) -> Dict[str, Any]:
        """列出团队中的 Agent

        委托给 OH InProcessBackend.list_teammates() 获取活跃 Agent 列表。
        """
        if not self._available:
            return {"status": "error", "message": "OpenHarness Swarm not available"}

        try:
            # 从 InProcessBackend 获取活跃 Agent
            teammates = self._backend.list_teammates()
            agents = []
            for agent_id, is_running, duration_s in teammates:
                agents.append({
                    "agent_id": agent_id,
                    "is_running": is_running,
                    "duration_s": duration_s,
                })

            # 如果指定了 swarm_id，过滤到该团队
            if swarm_id:
                team_info = self._teams.get(str(swarm_id))
                if team_info:
                    team_agent_ids = {
                        a["agent_id"] for a in team_info.get("agents", [])
                    }
                    agents = [a for a in agents if a["agent_id"] in team_agent_ids]

            return {"status": "success", "agents": agents}
        except Exception as e:
            logger.error("SwarmAdapter: list_agents 失败: %s", e)
            return {"status": "error", "message": str(e)}

    async def add_agent(self, swarm_id: str,
                        agent_config: Dict[str, Any]) -> Dict[str, Any]:
        """向团队添加新 Agent

        委托给 OH InProcessBackend.spawn() 生成新 Agent。
        """
        if not self._available:
            return {"status": "error", "message": "OpenHarness Swarm not available"}

        team_info = self._teams.get(str(swarm_id))
        if not team_info:
            return {"status": "error", "message": f"Swarm team '{swarm_id}' not found"}

        try:
            agent_name = agent_config.get("name", f"agent-{uuid.uuid4().hex[:6]}")
            spawn_config = TeammateSpawnConfig(
                name=agent_name,
                team=str(swarm_id),
                prompt=agent_config.get("prompt", ""),
                cwd=agent_config.get("cwd", os.getcwd()),
                parent_session_id=team_info.get("parent_session_id", ""),
                model=agent_config.get("model"),
                system_prompt=agent_config.get("system_prompt"),
                color=agent_config.get("color"),
            )

            result: SpawnResult = await self._backend.spawn(spawn_config)
            if result.success:
                agent_info = {
                    "agent_id": result.agent_id,
                    "task_id": result.task_id,
                    "name": agent_name,
                    "backend_type": result.backend_type,
                }
                team_info.setdefault("agents", []).append(agent_info)
                return {"status": "success", "agent_added": True, "agent": agent_info}
            else:
                return {"status": "error", "message": result.error or "spawn failed"}
        except Exception as e:
            logger.error("SwarmAdapter: add_agent 失败: %s", e)
            return {"status": "error", "message": str(e)}

    async def remove_agent(self, swarm_id: str,
                           agent_id: str) -> Dict[str, Any]:
        """从团队中移除 Agent

        委托给 OH InProcessBackend.shutdown() 优雅终止 Agent。
        """
        if not self._available:
            return {"status": "error", "message": "OpenHarness Swarm not available"}

        try:
            success = await self._backend.shutdown(agent_id, force=False)
            if success:
                # 从团队记录中移除
                team_info = self._teams.get(str(swarm_id))
                if team_info:
                    team_info["agents"] = [
                        a for a in team_info.get("agents", [])
                        if a.get("agent_id") != agent_id
                    ]
                return {"status": "success", "agent_removed": True}
            else:
                return {"status": "error", "message": f"Failed to shutdown agent {agent_id}"}
        except Exception as e:
            logger.error("SwarmAdapter: remove_agent 失败: %s", e)
            return {"status": "error", "message": str(e)}

    async def shutdown_all(self) -> Dict[str, Any]:
        """关闭所有活跃 Agent"""
        if not self._available or not self._backend:
            return {"status": "error", "message": "Swarm not available"}

        try:
            teammates = self._backend.list_teammates()
            shutdown_count = 0
            for agent_id, _, _ in teammates:
                success = await self._backend.shutdown(agent_id, force=True)
                if success:
                    shutdown_count += 1

            self._teams.clear()
            return {"status": "success", "agents_shutdown": shutdown_count}
        except Exception as e:
            return {"status": "error", "message": str(e)}


_swarm_adapter: Optional[SwarmAdapter] = None


def get_swarm_adapter() -> SwarmAdapter:
    global _swarm_adapter
    if _swarm_adapter is None:
        _swarm_adapter = SwarmAdapter()
    return _swarm_adapter
