"""会话记忆 - 服务层"""

import logging
from typing import Dict, Any, List, Optional

from ..session_store import SessionStore, Session
from ..context_window import ContextWindow, ChatMessage, MessageRole
from ..memory_compactor import MemoryCompactor
from ..memory_tiers import get_session_memory_manager

logger = logging.getLogger(__name__)

# ── 审计工具（懒加载 + 容错） ──
def _session_audit(action: str, *, result_status: str = "success",
                   result_message: str = "", resource: str = None,
                   details: Dict[str, Any] = None) -> None:
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service="platform_session",
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


class SessionMemoryService:
    """会话记忆服务，封装存储层调用，提供业务语义接口"""

    def __init__(self):
        self.store = SessionStore()
        self.compactor = MemoryCompactor()

    def create_session(self, workspace_id: str, title: str, max_tokens: int) -> Dict[str, Any]:
        """创建会话"""
        session = Session(
            workspace_id=workspace_id,
            title=title or "New Session",
            context_window=ContextWindow(max_tokens=max_tokens),
        )
        session_id = self.store.save_session(session)
        _session_audit(
            action="session_create",
            result_status="success",
            resource=session_id,
            details={
                "workspace_id": workspace_id,
                "session_id": session_id,
                "max_tokens": max_tokens,
                "title_len": len(title or ""),
            },
        )
        return {"session_id": session_id, "title": session.title}

    def list_sessions(self, workspace_id: str, limit: int) -> Dict[str, Any]:
        """列出会话"""
        summaries = self.store.list_sessions(workspace_id, limit)
        return {"sessions": [s.model_dump() for s in summaries]}

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        session = self.store.load_session(session_id)
        if not session:
            return None
        return {
            "id": session.id,
            "workspace_id": session.workspace_id,
            "title": session.title,
            "message_count": len(session.messages),
            "context_window": session.context_window.to_dict(),
            "is_active": session.is_active,
        }

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens: int,
        entities: List[str],
    ) -> Optional[Dict[str, Any]]:
        """添加消息到会话"""
        session = self.store.load_session(session_id)
        if not session:
            return None

        try:
            msg_role = MessageRole(role)
        except ValueError:
            msg_role = MessageRole.USER

        message = ChatMessage(role=msg_role, content=content, tokens=tokens, entities=entities)
        session.messages.append(message)
        session.context_window.add_message(message)

        if self.compactor.should_compact(session.context_window):
            session.needs_compaction = True
            logger.info(f"Session {session_id} needs compaction (usage_ratio={session.context_window.usage_ratio:.2f})")

        self.store.save_session(session)
        _session_audit(
            action="session_add_message",
            result_status="success",
            resource=session_id,
            details={
                "session_id": session_id,
                "role": role,
                "tokens": tokens,
                "message_count": len(session.messages),
                "needs_compaction": session.needs_compaction,
                "item_count": tokens,
            },
        )
        return {"message_id": message.id, "context_window": session.context_window.to_dict(), "needs_compaction": session.needs_compaction}

    async def compact_if_needed(self, session_id: str) -> Dict[str, Any]:
        """检查 needs_compaction 标记，若需要则执行压缩

        此方法应在路由层（async 上下文）中调用。

        Args:
            session_id: 会话 ID

        Returns:
            压缩结果，包含是否执行了压缩及压缩后的上下文窗口信息
        """
        session = self.store.load_session(session_id)
        if not session:
            return {"status": "error", "message": "Session not found"}

        if not session.needs_compaction:
            return {"status": "skipped", "message": "No compaction needed"}

        try:
            session.context_window = await self.compactor.compact(session.context_window)
            session.needs_compaction = False
            self.store.save_session(session)
            logger.info(f"Session {session_id} compacted successfully")
            return {"status": "success", "context_window": session.context_window.to_dict()}
        except Exception as e:
            logger.error(f"Session {session_id} compaction failed: {e}")
            return {"status": "error", "message": str(e)}

    def get_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话上下文"""
        session = self.store.load_session(session_id)
        if not session:
            return None
        return {
            "context_window": session.context_window.to_dict(),
            "messages": [m.model_dump() for m in session.context_window.messages],
            "summary": session.context_window.summary,
        }

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        result = self.store.delete_session(session_id)
        _session_audit(
            action="session_delete",
            result_status="success" if result else "failure",
            result_message="" if result else "Session not found",
            resource=session_id,
            details={"session_id": session_id},
        )
        return result

    def get_session_memory(self, session_id: str) -> Dict[str, Any]:
        """获取会话记忆"""
        manager = get_session_memory_manager()
        return manager.get_session_memory(session_id)

    def store_short_term_memory(self, session_id: str, key: str, value: Any) -> Dict[str, Any]:
        """存储短期记忆"""
        manager = get_session_memory_manager()
        return manager.store_short_term(session_id, key, value)

    def store_working_memory(self, session_id: str, key: str, value: Any) -> Dict[str, Any]:
        """存储工作记忆"""
        manager = get_session_memory_manager()
        return manager.store_working(session_id, key, value)

    def clear_short_term_memory(self, session_id: str) -> Dict[str, Any]:
        """清除短期记忆"""
        manager = get_session_memory_manager()
        result = manager.clear_short_term(session_id)
        _session_audit(
            action="session_clear_short_term_memory",
            result_status="success",
            resource=session_id,
            details={"session_id": session_id},
        )
        return result

    def retrieve_long_term_memory(self, query: str, limit: int) -> Dict[str, Any]:
        """检索长期记忆"""
        manager = get_session_memory_manager()
        return manager.retrieve_long_term(query, limit)

    def store_long_term_memory(self, key: str, value: Any) -> Dict[str, Any]:
        """存储长期记忆"""
        manager = get_session_memory_manager()
        return manager.store_long_term(key, value)

    def load_session_raw(self, session_id: str) -> Optional[Session]:
        """加载原始 Session 对象（用于需要异步操作的场景）"""
        return self.store.load_session(session_id)

    def save_session_raw(self, session: Session) -> str:
        """保存原始 Session 对象"""
        return self.store.save_session(session)


# 模块级单例
_service_instance: Optional[SessionMemoryService] = None


def get_session_memory_service() -> SessionMemoryService:
    """获取会话记忆服务实例（单例）"""
    global _service_instance
    if _service_instance is None:
        _service_instance = SessionMemoryService()
    return _service_instance
