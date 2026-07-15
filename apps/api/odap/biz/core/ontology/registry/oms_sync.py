"""OMSSyncAdapter — OntologyService → OMS 只读缓存同步

当 TypeRegistry 通过 OntologyService 完成写入后，
OMSSyncAdapter 将变更同步到 OMS 缓存，确保下游 11 个消费者无需改动。

同步策略：
- create: upsert 到 OMS（INSERT OR REPLACE）
- update: upsert 到 OMS
- delete: 从 OMS 删除
- 平台核心实体（种子数据）不会被覆盖或删除
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 平台核心实体 type_id 前缀（种子数据），禁止同步覆盖
_PLATFORM_SEED_TYPE_IDS = {"Agent", "Workspace", "Scenario", "Ontology", "Simulation"}


class OMSSyncAdapter:
    """OntologyService → OMS 缓存同步适配器"""

    def __init__(self, oms_storage=None):
        self._oms_storage = oms_storage

    @property
    def oms_storage(self):
        if self._oms_storage is None:
            from odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
            self._oms_storage = SQLiteOMSStorage()
        return self._oms_storage

    def sync_object_type_created(self, type_data: Dict[str, Any]) -> None:
        """对象类型创建后同步到 OMS 缓存"""
        type_id = type_data.get("type_id", "")
        if type_id in _PLATFORM_SEED_TYPE_IDS:
            logger.debug("OMSSyncAdapter: skip platform seed type %s", type_id)
            return
        try:
            oms_data = self._convert_object_type_to_oms(type_data)
            existing = self.oms_storage.get_object_type(type_id)
            if existing:
                self.oms_storage.update_object_type(type_id, oms_data)
            else:
                self.oms_storage.create_object_type(oms_data)
            logger.info("OMSSyncAdapter: synced object_type %s to OMS", type_id)
        except Exception as exc:
            logger.warning("OMSSyncAdapter: sync object_type created failed for %s: %s", type_id, exc)

    def sync_object_type_updated(self, type_data: Dict[str, Any]) -> None:
        """对象类型更新后同步到 OMS 缓存"""
        type_id = type_data.get("type_id", "")
        if type_id in _PLATFORM_SEED_TYPE_IDS:
            return
        try:
            oms_data = self._convert_object_type_to_oms(type_data)
            existing = self.oms_storage.get_object_type(type_id)
            if existing:
                self.oms_storage.update_object_type(type_id, oms_data)
            else:
                self.oms_storage.create_object_type(oms_data)
            logger.info("OMSSyncAdapter: synced object_type update %s to OMS", type_id)
        except Exception as exc:
            logger.warning("OMSSyncAdapter: sync object_type updated failed for %s: %s", type_id, exc)

    def sync_object_type_deleted(self, type_id: str) -> None:
        """对象类型删除后从 OMS 缓存移除"""
        if type_id in _PLATFORM_SEED_TYPE_IDS:
            return
        try:
            self.oms_storage.delete_object_type(type_id)
            logger.info("OMSSyncAdapter: removed object_type %s from OMS", type_id)
        except Exception as exc:
            logger.warning("OMSSyncAdapter: sync object_type deleted failed for %s: %s", type_id, exc)

    def sync_action_type_created(self, action_data: Dict[str, Any]) -> None:
        """动作类型创建后同步到 OMS 缓存"""
        action_type_id = action_data.get("action_type_id", "")
        try:
            oms_data = self._convert_action_type_to_oms(action_data)
            existing = self.oms_storage.get_action_type(action_type_id)
            if existing:
                self.oms_storage.update_action_type(action_type_id, oms_data)
            else:
                self.oms_storage.create_action_type(oms_data)
            logger.info("OMSSyncAdapter: synced action_type %s to OMS", action_type_id)
        except Exception as exc:
            logger.warning("OMSSyncAdapter: sync action_type created failed for %s: %s", action_type_id, exc)

    def sync_action_type_updated(self, action_data: Dict[str, Any]) -> None:
        """动作类型更新后同步到 OMS 缓存"""
        action_type_id = action_data.get("action_type_id", "")
        try:
            oms_data = self._convert_action_type_to_oms(action_data)
            existing = self.oms_storage.get_action_type(action_type_id)
            if existing:
                self.oms_storage.update_action_type(action_type_id, oms_data)
            else:
                self.oms_storage.create_action_type(oms_data)
            logger.info("OMSSyncAdapter: synced action_type update %s to OMS", action_type_id)
        except Exception as exc:
            logger.warning("OMSSyncAdapter: sync action_type updated failed for %s: %s", action_type_id, exc)

    def sync_action_type_deleted(self, action_type_id: str) -> None:
        """动作类型删除后从 OMS 缓存移除"""
        try:
            self.oms_storage.delete_action_type(action_type_id)
            logger.info("OMSSyncAdapter: removed action_type %s from OMS", action_type_id)
        except Exception as exc:
            logger.warning("OMSSyncAdapter: sync action_type deleted failed for %s: %s", action_type_id, exc)

    # ── 类型转换: OntologyService 格式 → OMS 格式 ──

    @staticmethod
    def _convert_object_type_to_oms(type_data: Dict[str, Any]) -> Dict[str, Any]:
        """将 OntologyService 的 object_type 转换为 OMS 存储格式

        OntologyService 字段: type_id, name, display_name, description, properties, links, actions, ...
        OMS 字段: type_id, name, display_name, description, properties, links, actions, icon, color, is_active, parent_type
        """
        properties = type_data.get("properties", [])
        # OntologyService properties 是 list[dict]，OMS 也是 list[dict]，直接传递
        if isinstance(properties, str):
            import json
            try:
                properties = json.loads(properties)
            except (json.JSONDecodeError, TypeError):
                properties = []

        links = type_data.get("links", [])
        if isinstance(links, str):
            import json
            try:
                links = json.loads(links)
            except (json.JSONDecodeError, TypeError):
                links = []

        actions = type_data.get("actions", [])
        if isinstance(actions, str):
            import json
            try:
                actions = json.loads(actions)
            except (json.JSONDecodeError, TypeError):
                actions = []

        return {
            "type_id": type_data.get("type_id", ""),
            "name": type_data.get("name", ""),
            "display_name": type_data.get("display_name", type_data.get("name", "")),
            "description": type_data.get("description", ""),
            "properties": properties,
            "links": links,
            "actions": actions,
            "icon": type_data.get("icon", ""),
            "color": type_data.get("color", ""),
            "is_active": type_data.get("is_active", True),
            "parent_type": type_data.get("parent_type"),
        }

    @staticmethod
    def _convert_action_type_to_oms(action_data: Dict[str, Any]) -> Dict[str, Any]:
        """将 OntologyService 的 action_type 转换为 OMS 存储格式

        OntologyService 字段: action_type_id, name, target_object_type, description, parameters, required_roles, ...
        OMS 字段: action_type_id, name, display_name, description, target_object_type, parameters, opa_policy, required_roles, ...
        """
        parameters = action_data.get("parameters", [])
        if isinstance(parameters, str):
            import json
            try:
                parameters = json.loads(parameters)
            except (json.JSONDecodeError, TypeError):
                parameters = []

        required_roles = action_data.get("required_roles", [])
        if isinstance(required_roles, str):
            import json
            try:
                required_roles = json.loads(required_roles)
            except (json.JSONDecodeError, TypeError):
                required_roles = []

        return {
            "action_type_id": action_data.get("action_type_id", ""),
            "name": action_data.get("name", ""),
            "display_name": action_data.get("display_name", action_data.get("name", "")),
            "description": action_data.get("description", ""),
            "target_object_type": action_data.get("target_object_type", ""),
            "parameters": parameters,
            "opa_policy": action_data.get("opa_policy"),
            "required_roles": required_roles,
            "writeback_config": action_data.get("writeback_config"),
            "confirmation_required": action_data.get("confirmation_required", False),
        }
