"""ISessionMemory — 会话记忆服务抽象接口

ADR-065: 舱壁先行。agent 通过此接口依赖 platform 层的会话记忆服务，
而非直接导入具体实现类。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class ISessionMemory(ABC):
    """会话管理与记忆持久化抽象接口

    定义 agent 对会话存储能力的需求。
    当前实现: odap.biz.platform.session_memory.services.session_memory_service.SessionMemoryService
    """

    @abstractmethod
    def create_session(
        self, workspace_id: str, title: str = "", max_tokens: int = 8000
    ) -> Dict[str, Any]:
        """创建新会话

        Args:
            workspace_id: 工作空间 ID
            title: 会话标题
            max_tokens: 最大 token 数

        Returns:
            包含 session_id 的字典
        """
        ...

    @abstractmethod
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens: int = 0,
        entities: List[Any] = None,
    ) -> Dict[str, Any]:
        """添加消息到会话

        Args:
            session_id: 会话 ID
            role: 角色 (user / assistant)
            content: 消息内容
            tokens: token 数量
            entities: 关联实体列表

        Returns:
            操作结果
        """
        ...

    @abstractmethod
    def get_context(self, session_id: str) -> Dict[str, Any]:
        """获取会话上下文（含消息历史）

        Args:
            session_id: 会话 ID

        Returns:
            包含 messages 列表的上下文字典。未找到时返回空字典。
        """
        ...
