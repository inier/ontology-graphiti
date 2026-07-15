"""
GraphWriteProxy — 图谱写入操作的统一代理

业务模块禁止直接导入 GraphManager 进行写操作，必须通过本代理。
读操作应使用 QueryService。

设计原则:
- 单例模式，与 QueryService 对齐
- 惰性导入 GraphManager，避免循环依赖
- 每次写操作记录审计日志（workspace_id + 操作类型）
- 返回 Dict[str, Any]，遵循 AGENTS.md 服务层规则
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GraphWriteProxy:
    """图谱写入操作的统一代理，业务模块通过此类执行所有图谱写入。"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._graph_manager = None
        self._initialized = True

    # ------------------------------------------------------------------
    # 内部：惰性获取 GraphManager
    # ------------------------------------------------------------------
    def _get_graph_manager(self):
        """惰性导入并缓存 GraphManager 单例。"""
        if self._graph_manager is None:
            try:
                from odap.infra.graph import GraphManager
                self._graph_manager = GraphManager()
            except Exception as e:
                logger.warning("GraphWriteProxy: GraphManager init failed: %s", e)
                self._graph_manager = None
        return self._graph_manager

    # ------------------------------------------------------------------
    # 审计日志
    # ------------------------------------------------------------------
    def _log_write(self, operation: str, workspace_id: str = "", **detail):
        """记录写操作审计日志。"""
        logger.info(
            "GraphWrite op=%s workspace=%s detail=%s",
            operation,
            workspace_id,
            detail,
        )

    # ------------------------------------------------------------------
    # 公开写方法
    # ------------------------------------------------------------------
    def add_entity(
        self,
        entity_id: str,
        entity_type: str,
        properties: Dict[str, Any],
        workspace_id: str = "",
    ) -> Dict[str, Any]:
        """添加实体到图谱。

        Returns:
            {"status": "success"/"error", ...}
        """
        gm = self._get_graph_manager()
        if gm is None:
            return {"status": "error", "message": "GraphManager unavailable"}

        try:
            success = gm.add_entity(entity_id, entity_type, properties)
            self._log_write(
                "add_entity",
                workspace_id=workspace_id or properties.get("workspace_id", ""),
                entity_id=entity_id,
                entity_type=entity_type,
                success=success,
            )
            if success:
                return {"status": "success", "entity_id": entity_id, "entity_type": entity_type}
            return {"status": "error", "message": "add_entity returned False"}
        except Exception as e:
            logger.warning("GraphWriteProxy.add_entity failed: %s", e)
            return {"status": "error", "message": str(e)}

    def update_entity(
        self,
        entity_id: str,
        properties: Dict[str, Any],
        workspace_id: str = "",
    ) -> Dict[str, Any]:
        """更新实体属性。

        Returns:
            {"status": "success"/"error", ...}
        """
        gm = self._get_graph_manager()
        if gm is None:
            return {"status": "error", "message": "GraphManager unavailable"}

        try:
            success = gm.update_entity(entity_id, properties)
            self._log_write(
                "update_entity",
                workspace_id=workspace_id,
                entity_id=entity_id,
                keys=list(properties.keys()),
                success=success,
            )
            if success:
                return {"status": "success", "entity_id": entity_id, "updated_keys": list(properties.keys())}
            return {"status": "error", "message": "update_entity returned False"}
        except Exception as e:
            logger.warning("GraphWriteProxy.update_entity failed: %s", e)
            return {"status": "error", "message": str(e)}

    def delete_entity(
        self,
        entity_id: str,
        workspace_id: str = "",
    ) -> Dict[str, Any]:
        """删除实体。

        Returns:
            {"status": "success"/"error", ...}
        """
        gm = self._get_graph_manager()
        if gm is None:
            return {"status": "error", "message": "GraphManager unavailable"}

        try:
            success = gm.delete_entity(entity_id)
            self._log_write(
                "delete_entity",
                workspace_id=workspace_id,
                entity_id=entity_id,
                success=success,
            )
            if success:
                return {"status": "success", "entity_id": entity_id}
            return {"status": "error", "message": "delete_entity returned False"}
        except Exception as e:
            logger.warning("GraphWriteProxy.delete_entity failed: %s", e)
            return {"status": "error", "message": str(e)}

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship: str,
        properties: Optional[Dict[str, Any]] = None,
        workspace_id: str = "",
    ) -> Dict[str, Any]:
        """添加关系。

        Returns:
            {"status": "success"/"error", ...}
        """
        gm = self._get_graph_manager()
        if gm is None:
            return {"status": "error", "message": "GraphManager unavailable"}

        try:
            success = gm.add_relationship(source_id, target_id, relationship, properties or {})
            self._log_write(
                "add_relationship",
                workspace_id=workspace_id,
                source_id=source_id,
                target_id=target_id,
                relationship=relationship,
                success=success,
            )
            if success:
                return {
                    "status": "success",
                    "source_id": source_id,
                    "target_id": target_id,
                    "relationship": relationship,
                }
            return {"status": "error", "message": "add_relationship returned False"}
        except Exception as e:
            logger.warning("GraphWriteProxy.add_relationship failed: %s", e)
            return {"status": "error", "message": str(e)}

    async def add_episode(
        self,
        name: str,
        content: str,
        source_description: str = "",
        reference_time=None,
        workspace_id: str = "",
    ) -> Dict[str, Any]:
        """添加 Episode 到 Graphiti。

        Returns:
            {"status": "success"/"error", ...}
        """
        gm = self._get_graph_manager()
        if gm is None:
            return {"status": "error", "message": "GraphManager unavailable"}

        try:
            success = await gm.add_episode(
                name=name,
                content=content,
                source_description=source_description,
                reference_time=reference_time,
            )
            self._log_write(
                "add_episode",
                workspace_id=workspace_id,
                name=name,
                success=success,
            )
            if success:
                return {"status": "success", "name": name}
            return {"status": "error", "message": "add_episode returned False"}
        except Exception as e:
            logger.warning("GraphWriteProxy.add_episode failed: %s", e)
            return {"status": "error", "message": str(e)}

    def add_episodes_batch(
        self,
        episodes: List[Dict[str, Any]],
        batch_size: int = 10,
        workspace_id: str = "",
    ) -> Dict[str, Any]:
        """批量添加 Episode。

        Returns:
            {"status": "success"/"error", ...}
        """
        gm = self._get_graph_manager()
        if gm is None:
            return {"status": "error", "message": "GraphManager unavailable"}

        try:
            result = gm.add_episodes_batch(episodes, batch_size=batch_size)
            self._log_write(
                "add_episodes_batch",
                workspace_id=workspace_id,
                total=len(episodes),
                success=result.get("success", 0),
                failed=result.get("failed", 0),
            )
            return {"status": "success", **result}
        except Exception as e:
            logger.warning("GraphWriteProxy.add_episodes_batch failed: %s", e)
            return {"status": "error", "message": str(e)}

    def initialize_graph(self, workspace_id: str = "") -> Dict[str, Any]:
        """初始化图谱连接。

        Returns:
            {"status": "success"/"error", ...}
        """
        gm = self._get_graph_manager()
        if gm is None:
            return {"status": "error", "message": "GraphManager unavailable"}

        try:
            gm.initialize_graph()
            self._log_write("initialize_graph", workspace_id=workspace_id)
            return {"status": "success"}
        except Exception as e:
            logger.warning("GraphWriteProxy.initialize_graph failed: %s", e)
            return {"status": "error", "message": str(e)}

    def clear_graph(self, workspace_id: str = "") -> Dict[str, Any]:
        """清空图谱数据。

        Returns:
            {"status": "success"/"error", ...}
        """
        gm = self._get_graph_manager()
        if gm is None:
            return {"status": "error", "message": "GraphManager unavailable"}

        try:
            result = gm.clear_graph()
            self._log_write("clear_graph", workspace_id=workspace_id, result=result)
            return {"status": "success", **result}
        except Exception as e:
            logger.warning("GraphWriteProxy.clear_graph failed: %s", e)
            return {"status": "error", "message": str(e)}

    def is_connected(self) -> bool:
        """检查 GraphManager 是否可用且已连接。"""
        gm = self._get_graph_manager()
        if gm is None:
            return False
        return getattr(gm, "_connected", False) and not getattr(gm, "_use_fallback", True)

    # ------------------------------------------------------------------
    # 诊断属性
    # ------------------------------------------------------------------
    @property
    def mode(self) -> str:
        """Get the current graph manager mode (for debug/diagnostic purposes).

        Returns the internal _mode string of the underlying GraphManager,
        e.g. 'neo4j_driver', 'graphiti', 'networkx', or 'unknown'.
        """
        gm = self._get_graph_manager()
        if gm is not None:
            return getattr(gm, "_mode", "unknown")
        return "unavailable"


# ------------------------------------------------------------------
# 模块级单例获取函数
# ------------------------------------------------------------------
_write_proxy_instance = None


def get_graph_write_proxy() -> GraphWriteProxy:
    """获取全局 GraphWriteProxy 单例。"""
    global _write_proxy_instance
    if _write_proxy_instance is None:
        _write_proxy_instance = GraphWriteProxy()
    return _write_proxy_instance
