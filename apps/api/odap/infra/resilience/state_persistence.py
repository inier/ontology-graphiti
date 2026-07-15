"""
状态持久化管理器模块
实现 Agent 状态和任务检查点的持久化与恢复

Phase 2 扩展: 故障恢复与状态管理

安全改进：移除 pickle 反序列化（防止任意代码执行），仅使用 JSON。
性能改进：async 方法使用 run_in_executor 避免阻塞事件循环。
"""

import asyncio
import json
import os
import logging
import functools
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger("state_persistence")

DEFAULT_PERSISTENCE_DIR = os.path.join(os.getenv("DATA_DIR", os.path.join(os.getcwd(), "data")), "graphiti_swarm_state")


class StatePersistenceManager:
    """状态持久化管理器"""

    _instance: Optional['StatePersistenceManager'] = None

    def __init__(self, persistence_path: str = None):
        if persistence_path is None:
            persistence_path = DEFAULT_PERSISTENCE_DIR
        self.persistence_path = persistence_path
        os.makedirs(persistence_path, exist_ok=True)

    @classmethod
    def get_instance(cls, persistence_path: str = None) -> 'StatePersistenceManager':
        if cls._instance is None:
            cls._instance = StatePersistenceManager(persistence_path)
        return cls._instance

    @staticmethod
    def _json_dump(data: Any, filepath: str) -> None:
        """同步 JSON 写入（供 run_in_executor 调用）"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)

    @staticmethod
    def _json_load(filepath: str) -> Optional[Dict[str, Any]]:
        """同步 JSON 读取（供 run_in_executor 调用）"""
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def save_state(self, agent_id: str, state: Dict[str, Any]) -> bool:
        """保存 Agent 状态（仅 JSON，无 pickle）"""
        try:
            state_file = os.path.join(self.persistence_path, f"{agent_id}_state.json")

            state_with_meta = {
                "agent_id": agent_id,
                "timestamp": datetime.now().isoformat(),
                "data": state
            }

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, functools.partial(self._json_dump, state_with_meta, state_file))

            logger.info(f"Agent {agent_id} 状态已保存")
            return True
        except Exception as e:
            logger.error(f"状态保存失败: {e}")
            return False

    async def load_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """加载 Agent 状态（仅 JSON，无 pickle 回退）"""
        try:
            state_file = os.path.join(self.persistence_path, f"{agent_id}_state.json")

            loop = asyncio.get_event_loop()
            state_data = await loop.run_in_executor(None, functools.partial(self._json_load, state_file))

            if state_data:
                logger.info(f"Agent {agent_id} 状态已加载")
                return state_data.get("data")

            return None
        except Exception as e:
            logger.error(f"状态加载失败: {e}")
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

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, functools.partial(self._json_dump, checkpoint, checkpoint_file))

            logger.info(f"Mission {mission_id} 检查点已保存")
            return True
        except Exception as e:
            logger.error(f"检查点保存失败: {e}")
            return False

    async def load_checkpoint(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """加载任务检查点"""
        try:
            checkpoint_file = os.path.join(self.persistence_path, f"checkpoint_{mission_id}.json")

            loop = asyncio.get_event_loop()
            checkpoint = await loop.run_in_executor(None, functools.partial(self._json_load, checkpoint_file))

            if checkpoint:
                logger.info(f"Mission {mission_id} 检查点已加载")
                return checkpoint.get("data")

            return None
        except Exception as e:
            logger.error(f"检查点加载失败: {e}")
            return None

    async def resume_from_checkpoint(self, mission_id: str) -> Dict[str, Any]:
        """从检查点恢复任务"""
        checkpoint_data = await self.load_checkpoint(mission_id)

        if not checkpoint_data:
            return {"status": "no_checkpoint", "message": "没有找到检查点"}

        return {
            "status": "resumed",
            "mission_id": mission_id,
            "recovered_agents": checkpoint_data.get("agent_ids", []),
            "current_phase": checkpoint_data.get("current_phase"),
            "phase_data": checkpoint_data.get("phase_data", {}),
            "checkpoint_timestamp": datetime.now().isoformat()
        }

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """列出所有检查点"""
        checkpoints = []
        try:
            for filename in os.listdir(self.persistence_path):
                if filename.startswith("checkpoint_") and filename.endswith(".json"):
                    mission_id = filename[len("checkpoint_"):-len(".json")]
                    file_path = os.path.join(self.persistence_path, filename)
                    stat = os.stat(file_path)
                    checkpoints.append({
                        "mission_id": mission_id,
                        "file": filename,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "size_bytes": stat.st_size
                    })
        except Exception as e:
            logger.error(f"列出检查点失败: {e}")

        return sorted(checkpoints, key=lambda x: x["modified"], reverse=True)

    def delete_checkpoint(self, mission_id: str) -> bool:
        """删除检查点"""
        try:
            checkpoint_file = os.path.join(self.persistence_path, f"checkpoint_{mission_id}.json")
            if os.path.exists(checkpoint_file):
                os.remove(checkpoint_file)
                logger.info(f"Mission {mission_id} 检查点已删除")
                return True
            return False
        except Exception as e:
            logger.error(f"删除检查点失败: {e}")
            return False

    def get_persistence_stats(self) -> Dict[str, Any]:
        """获取持久化统计信息"""
        try:
            files = os.listdir(self.persistence_path)
            total_size = sum(
                os.path.getsize(os.path.join(self.persistence_path, f))
                for f in files
            )
            return {
                "total_files": len(files),
                "total_size_bytes": total_size,
                "checkpoints": len([f for f in files if f.startswith("checkpoint_")]),
                "agent_states": len([f for f in files if f.endswith("_state.json")]),
                "persistence_path": self.persistence_path
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}