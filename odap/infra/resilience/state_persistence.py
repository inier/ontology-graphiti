"""
状态持久化管理器模块
实现 Agent 状态和任务检查点的持久化与恢复

Phase 2 扩展: 故障恢复与状态管理
"""

import json
import pickle
import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger("state_persistence")


class StatePersistenceManager:
    """状态持久化管理器"""

    _instance: Optional['StatePersistenceManager'] = None

    def __init__(self, persistence_path: str = "/tmp/graphiti_swarm_state"):
        self.persistence_path = persistence_path
        os.makedirs(persistence_path, exist_ok=True)

    @classmethod
    def get_instance(cls, persistence_path: str = "/tmp/graphiti_swarm_state") -> 'StatePersistenceManager':
        if cls._instance is None:
            cls._instance = StatePersistenceManager(persistence_path)
        return cls._instance

    async def save_state(self, agent_id: str, state: Dict[str, Any]) -> bool:
        """保存 Agent 状态"""
        try:
            state_file = os.path.join(self.persistence_path, f"{agent_id}_state.json")

            state_with_meta = {
                "agent_id": agent_id,
                "timestamp": datetime.now().isoformat(),
                "data": state
            }

            with open(state_file, 'w') as f:
                json.dump(state_with_meta, f, indent=2, default=str)

            backup_file = os.path.join(self.persistence_path, f"{agent_id}_state_backup.pkl")
            with open(backup_file, 'wb') as f:
                pickle.dump(state_with_meta, f)

            logger.info(f"Agent {agent_id} 状态已保存")
            return True
        except Exception as e:
            logger.error(f"状态保存失败: {e}")
            return False

    async def load_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """加载 Agent 状态"""
        try:
            state_file = os.path.join(self.persistence_path, f"{agent_id}_state.json")
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    state_data = json.load(f)
                    logger.info(f"Agent {agent_id} 状态已加载")
                    return state_data.get("data")

            backup_file = os.path.join(self.persistence_path, f"{agent_id}_state_backup.pkl")
            if os.path.exists(backup_file):
                with open(backup_file, 'rb') as f:
                    state_data = pickle.load(f)
                    logger.info(f"Agent {agent_id} 状态已从备份加载")
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

            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint, f, indent=2, default=str)

            logger.info(f"Mission {mission_id} 检查点已保存")
            return True
        except Exception as e:
            logger.error(f"检查点保存失败: {e}")
            return False

    async def load_checkpoint(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """加载任务检查点"""
        try:
            checkpoint_file = os.path.join(self.persistence_path, f"checkpoint_{mission_id}.json")

            if os.path.exists(checkpoint_file):
                with open(checkpoint_file, 'r') as f:
                    checkpoint = json.load(f)
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