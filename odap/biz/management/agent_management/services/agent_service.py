"""智能体管理 - 服务层"""

from typing import Dict, Any, List, Optional

from ..storage.sqlite_agent_storage import SQLiteAgentStorage


class AgentService:
    """智能体服务，封装存储层调用"""

    def __init__(self):
        self.storage = SQLiteAgentStorage()

    def list_agents(
        self,
        role_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self.storage.list_agents(role_id=role_id, workspace_id=workspace_id)

    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        agent = self.storage.get_agent(agent_id)
        if not agent:
            return {"status": "error", "message": "智能体不存在"}
        return agent

    def create_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.storage.create_agent(data)

    def update_agent(self, agent_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        updated = self.storage.update_agent(agent_id, data)
        if not updated:
            return {"status": "error", "message": "智能体不存在"}
        return updated

    def delete_agent(self, agent_id: str) -> Dict[str, Any]:
        success = self.storage.delete_agent(agent_id)
        if not success:
            return {"status": "error", "message": "智能体不存在"}
        return {"status": "success", "message": "智能体删除成功"}


# 模块级单例
_agent_service_instance: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """获取智能体服务实例（单例）"""
    global _agent_service_instance
    if _agent_service_instance is None:
        _agent_service_instance = AgentService()
    return _agent_service_instance
