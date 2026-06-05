"""撤销/重做服务"""

import logging
from typing import Dict, Any

from .operation_history_service import OperationHistoryService

logger = logging.getLogger(__name__)


class UndoService:
    """撤销/重做服务"""

    def __init__(self, history_service: OperationHistoryService = None):
        self.history = history_service or OperationHistoryService()

    def undo(self, operation_id: str) -> Dict[str, Any]:
        """撤销操作

        恢复 before_state，标记操作为已撤销

        Args:
            operation_id: 操作ID

        Returns:
            撤销结果
        """
        operation = self.history.get_operation(operation_id)
        if not operation:
            return {"status": "error", "message": "Operation not found"}

        if operation.get("undone"):
            return {"status": "error", "message": "Operation already undone"}

        before_state = operation.get("before_state")
        if before_state is None:
            return {"status": "error", "message": "Cannot undo: no before_state available"}

        # 尝试恢复 before_state
        restore_result = self._restore_state(
            operation["resource_type"],
            operation["resource_id"],
            before_state,
        )

        if restore_result.get("status") == "error":
            logger.warning(f"撤销恢复失败: {restore_result.get('message')}")

        # 标记为已撤销
        self.history.mark_undone(operation_id)

        return {
            "status": "success",
            "message": "Operation undone",
            "operation_id": operation_id,
            "resource_type": operation["resource_type"],
            "resource_id": operation["resource_id"],
            "restored_state": before_state,
        }

    def redo(self, operation_id: str) -> Dict[str, Any]:
        """重做操作

        恢复 after_state，取消撤销标记

        Args:
            operation_id: 操作ID

        Returns:
            重做结果
        """
        operation = self.history.get_operation(operation_id)
        if not operation:
            return {"status": "error", "message": "Operation not found"}

        if not operation.get("undone"):
            return {"status": "error", "message": "Operation is not undone, cannot redo"}

        after_state = operation.get("after_state")
        if after_state is None:
            return {"status": "error", "message": "Cannot redo: no after_state available"}

        # 尝试恢复 after_state
        restore_result = self._restore_state(
            operation["resource_type"],
            operation["resource_id"],
            after_state,
        )

        if restore_result.get("status") == "error":
            logger.warning(f"重做恢复失败: {restore_result.get('message')}")

        # 取消撤销标记
        self.history.mark_redone(operation_id)

        return {
            "status": "success",
            "message": "Operation redone",
            "operation_id": operation_id,
            "resource_type": operation["resource_type"],
            "resource_id": operation["resource_id"],
            "restored_state": after_state,
        }

    def get_undoable_operations(self, workspace_id: str) -> Dict[str, Any]:
        """获取可撤销的操作列表

        Args:
            workspace_id: 工作空间ID

        Returns:
            可撤销操作列表
        """
        operations = self.history.get_undoable_operations(workspace_id)
        return {
            "status": "success",
            "operations": operations,
            "count": len(operations),
        }

    def get_redoable_operations(self, workspace_id: str) -> Dict[str, Any]:
        """获取可重做的操作列表

        Args:
            workspace_id: 工作空间ID

        Returns:
            可重做操作列表
        """
        operations = self.history.get_redoable_operations(workspace_id)
        return {
            "status": "success",
            "operations": operations,
            "count": len(operations),
        }

    def _restore_state(
        self,
        resource_type: str,
        resource_id: str,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """恢复资源状态

        根据资源类型调用对应的存储层恢复数据

        Args:
            resource_type: 资源类型
            resource_id: 资源ID
            state: 要恢复的状态

        Returns:
            恢复结果
        """
        try:
            if resource_type == "workspace":
                from odap.biz.platform.workspace.storage import Storage
                from odap.biz.platform.workspace.models.workspace import Workspace, WorkspaceStatus, WorkspaceType, WorkspaceConfig
                storage = Storage()
                # 重建 Workspace 对象
                ws_data = dict(state)
                if "type" in ws_data and isinstance(ws_data["type"], str):
                    ws_data["type"] = WorkspaceType(ws_data["type"])
                if "status" in ws_data and isinstance(ws_data["status"], str):
                    ws_data["status"] = WorkspaceStatus(ws_data["status"])
                if "config" in ws_data and isinstance(ws_data["config"], dict):
                    ws_data["config"] = WorkspaceConfig(**ws_data["config"])
                workspace = Workspace(**ws_data)
                storage.save_workspace(workspace)
                return {"status": "success"}

            elif resource_type == "scenario":
                from odap.biz.platform.workspace.storage import Storage
                storage = Storage()
                storage.save_scenario(state)
                return {"status": "success"}

            elif resource_type == "agent":
                from odap.biz.management.agent_management.storage import SQLiteAgentStorage
                storage = SQLiteAgentStorage()
                storage.save_agent(state)
                return {"status": "success"}

            elif resource_type == "ontology_version":
                # Restore ontology to the before_state version
                from odap.biz.core.ontology.design.services.pipeline_service import get_pipeline_service
                pipeline = get_pipeline_service()
                before = state  # contains ontology_id and version_id
                ontology_id = before.get("ontology_id")
                version_id = before.get("version_id")
                if not ontology_id or not version_id:
                    return {"status": "error", "message": "ontology_version restore requires ontology_id and version_id in before_state"}
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(asyncio.run, pipeline.rollback(version_id))
                            future.result(timeout=30)
                    else:
                        asyncio.run(pipeline.rollback(version_id))
                except RuntimeError:
                    asyncio.run(pipeline.rollback(version_id))
                return {"status": "success"}

            else:
                logger.warning(f"不支持撤销的资源类型: {resource_type}")
                return {"status": "error", "message": f"Unsupported resource type: {resource_type}"}

        except Exception as e:
            logger.error(f"恢复状态失败: {e}")
            return {"status": "error", "message": str(e)}
