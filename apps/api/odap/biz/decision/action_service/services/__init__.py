"""动作服务 - 查询服务层"""

from typing import Dict, Any, List, Optional

from ..storage.sqlite_action_storage import SQLiteActionStorage


class ActionQueryService:
    """动作查询服务，封装存储层调用，提供业务语义接口"""

    def __init__(self):
        self.storage = SQLiteActionStorage()

    def list_records(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """列出动作记录"""
        return self.storage.list_records(status=status, limit=limit, offset=offset)

    def get_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """获取单条动作记录"""
        return self.storage.get_record(record_id)

    def list_by_target(
        self,
        target_object_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """按目标对象列出动作记录"""
        return self.storage.list_by_target(target_object_id, limit=limit)


# 模块级单例
_action_query_service: Optional[ActionQueryService] = None


def get_action_query_service() -> ActionQueryService:
    """获取动作查询服务实例（单例）"""
    global _action_query_service
    if _action_query_service is None:
        _action_query_service = ActionQueryService()
    return _action_query_service
