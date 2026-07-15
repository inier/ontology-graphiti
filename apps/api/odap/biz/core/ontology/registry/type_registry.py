"""TypeRegistry — 统一类型定义读写入口

所有类型定义的写入必须经过 TypeRegistry，由其委托给 OntologyService 执行，
并通过 OMSSyncAdapter 自动同步到 OMS 只读缓存。

设计原则：
1. OntologyService 是唯一权威源（API Layer）
2. OMS 保留为只读缓存（Application Layer），下游 11 个消费者不变
3. TypeRegistry 是写入的唯一入口，确保数据一致性
4. 读取可直接走 OntologyService 或 OMS，视场景而定

调用链: routes → TypeRegistry → OntologyService (权威源)
                                 → OMSSyncAdapter → OMS (只读缓存同步)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .oms_sync import OMSSyncAdapter

logger = logging.getLogger(__name__)


class TypeRegistry:
    """统一类型定义读写入口

    所有类型定义的写入操作经此入口，委托给 OntologyService 执行，
    成功后自动触发 OMS 缓存同步。
    """

    def __init__(self, ontology_service=None, oms_sync: OMSSyncAdapter = None):
        self._ontology_service = ontology_service
        self._oms_sync = oms_sync or OMSSyncAdapter()

    @property
    def ontology_service(self):
        if self._ontology_service is None:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService
            self._ontology_service = OntologyService()
        return self._ontology_service

    # ==================================================================
    # Object Type
    # ==================================================================

    def create_object_type(self, ontology_id: str, type_data: Dict) -> Dict[str, Any]:
        """创建对象类型定义 → OntologyService + OMS 同步"""
        result = self.ontology_service.create_object_type(ontology_id, type_data)
        if result.get("status") != "error":
            self._oms_sync.sync_object_type_created(result)
        return result

    def get_object_type(self, type_id: str) -> Dict[str, Any]:
        """获取对象类型定义（从 OntologyService 权威源读取）"""
        return self.ontology_service.get_object_type(type_id)

    def list_object_types(self, ontology_id: str) -> Dict[str, Any]:
        """列出对象类型定义（从 OntologyService 权威源读取）"""
        return self.ontology_service.list_object_types(ontology_id)

    def update_object_type(self, type_id: str, updates: Dict) -> Dict[str, Any]:
        """更新对象类型定义 → OntologyService + OMS 同步"""
        result = self.ontology_service.update_object_type(type_id, updates)
        if result.get("status") != "error":
            self._oms_sync.sync_object_type_updated(result)
        return result

    def delete_object_type(self, type_id: str) -> Dict[str, Any]:
        """删除对象类型定义 → OntologyService + OMS 同步"""
        result = self.ontology_service.delete_object_type(type_id)
        if result.get("status") != "error":
            self._oms_sync.sync_object_type_deleted(type_id)
        return result

    # ==================================================================
    # Link Type
    # ==================================================================

    def create_link_type(self, ontology_id: str, link_data: Dict) -> Dict[str, Any]:
        """创建关系类型定义 → OntologyService"""
        return self.ontology_service.create_link_type(ontology_id, link_data)

    def list_link_types(self, ontology_id: str) -> Dict[str, Any]:
        """列出关系类型定义"""
        return self.ontology_service.list_link_types(ontology_id)

    def update_link_type(self, link_id: str, updates: Dict) -> Dict[str, Any]:
        """更新关系类型定义"""
        return self.ontology_service.update_link_type(link_id, updates)

    def delete_link_type(self, link_id: str) -> Dict[str, Any]:
        """删除关系类型定义"""
        return self.ontology_service.delete_link_type(link_id)

    # ==================================================================
    # Action Type
    # ==================================================================

    def create_action_type(self, ontology_id: str, action_data: Dict) -> Dict[str, Any]:
        """创建动作类型定义 → OntologyService + OMS 同步"""
        result = self.ontology_service.create_action_type(ontology_id, action_data)
        if result.get("status") != "error":
            self._oms_sync.sync_action_type_created(result)
        return result

    def list_action_types(self, ontology_id: str) -> Dict[str, Any]:
        """列出动作类型定义"""
        return self.ontology_service.list_action_types(ontology_id)

    def update_action_type(self, action_type_id: str, updates: Dict) -> Dict[str, Any]:
        """更新动作类型定义 → OntologyService + OMS 同步"""
        result = self.ontology_service.update_action_type(action_type_id, updates)
        if result.get("status") != "error":
            self._oms_sync.sync_action_type_updated(result)
        return result

    def delete_action_type(self, action_type_id: str) -> Dict[str, Any]:
        """删除动作类型定义 → OntologyService + OMS 同步"""
        result = self.ontology_service.delete_action_type(action_type_id)
        if result.get("status") != "error":
            self._oms_sync.sync_action_type_deleted(action_type_id)
        return result

    # ==================================================================
    # Process Type
    # ==================================================================

    def create_process_type(self, ontology_id: str, data: Dict) -> Dict[str, Any]:
        return self.ontology_service.create_process_type(ontology_id, data)

    def list_process_types(self, ontology_id: str) -> Dict[str, Any]:
        return self.ontology_service.list_process_types(ontology_id)

    def update_process_type(self, type_id: str, updates: Dict) -> Dict[str, Any]:
        return self.ontology_service.update_process_type(type_id, updates)

    def delete_process_type(self, type_id: str) -> Dict[str, Any]:
        return self.ontology_service.delete_process_type(type_id)

    # ==================================================================
    # Rule Type
    # ==================================================================

    def create_rule_type(self, ontology_id: str, data: Dict) -> Dict[str, Any]:
        return self.ontology_service.create_rule_type(ontology_id, data)

    def list_rule_types(self, ontology_id: str) -> Dict[str, Any]:
        return self.ontology_service.list_rule_types(ontology_id)

    def update_rule_type(self, type_id: str, updates: Dict) -> Dict[str, Any]:
        return self.ontology_service.update_rule_type(type_id, updates)

    def delete_rule_type(self, type_id: str) -> Dict[str, Any]:
        return self.ontology_service.delete_rule_type(type_id)

    # ==================================================================
    # Function Type
    # ==================================================================

    def create_function_type(self, ontology_id: str, data: Dict) -> Dict[str, Any]:
        return self.ontology_service.create_function_type(ontology_id, data)

    def list_function_types(self, ontology_id: str) -> Dict[str, Any]:
        return self.ontology_service.list_function_types(ontology_id)

    def update_function_type(self, type_id: str, updates: Dict) -> Dict[str, Any]:
        return self.ontology_service.update_function_type(type_id, updates)

    def delete_function_type(self, type_id: str) -> Dict[str, Any]:
        return self.ontology_service.delete_function_type(type_id)

    # ==================================================================
    # Indicator Type
    # ==================================================================

    def create_indicator_type(self, ontology_id: str, data: Dict) -> Dict[str, Any]:
        return self.ontology_service.create_indicator_type(ontology_id, data)

    def list_indicator_types(self, ontology_id: str) -> Dict[str, Any]:
        return self.ontology_service.list_indicator_types(ontology_id)

    def update_indicator_type(self, type_id: str, updates: Dict) -> Dict[str, Any]:
        return self.ontology_service.update_indicator_type(type_id, updates)

    def delete_indicator_type(self, type_id: str) -> Dict[str, Any]:
        return self.ontology_service.delete_indicator_type(type_id)

    # ==================================================================
    # Schema Version
    # ==================================================================

    def commit_schema_version(self, ontology_id: str, changelog: str = "") -> Dict[str, Any]:
        """提交 Schema 版本快照"""
        return self.ontology_service.commit_schema_version(ontology_id, changelog)

    # ==================================================================
    # OMS 只读代理（供下游消费者统一入口）
    # ==================================================================

    def list_oms_object_types(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """列出 OMS 缓存中的对象类型（只读，供下游消费者使用）"""
        from odap.biz.core.ontology.application.oms.services.oms_service import OMSService
        return OMSService.get_instance().list_object_types(active_only=active_only)

    def get_oms_object_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        """获取 OMS 缓存中的对象类型（只读）"""
        from odap.biz.core.ontology.application.oms.services.oms_service import OMSService
        return OMSService.get_instance().get_object_type(type_id)

    def list_oms_action_types(self, target_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出 OMS 缓存中的动作类型（只读）"""
        from odap.biz.core.ontology.application.oms.services.oms_service import OMSService
        return OMSService.get_instance().list_action_types(target_type=target_type)

    def get_oms_action_type(self, action_type_id: str) -> Optional[Dict[str, Any]]:
        """获取 OMS 缓存中的动作类型（只读）"""
        from odap.biz.core.ontology.application.oms.services.oms_service import OMSService
        return OMSService.get_instance().get_action_type(action_type_id)

    # ==================================================================
    # 语义层一致性验证
    # ==================================================================

    def validate_consistency(self, ontology_id: str) -> Dict[str, Any]:
        """验证语义层与本体类型定义的一致性

        检查维度：
        1. ontology_id 存在性
        2. 类型引用完整性（link_type 的 source_type/target_type 是否已定义）
        3. action_type 的 target_object_type 是否已定义
        4. OMS 缓存与 OntologyService 数据一致性

        Returns:
            {"status": "ok"/"warning"/"error", "checks": [...], "issues": [...]}
        """
        issues = []
        checks = []

        # 1. 本体存在性
        ontology = self.ontology_service.get_ontology(ontology_id)
        if ontology.get("status") == "error":
            return {"status": "error", "checks": [], "issues": [ontology.get("message", "本体不存在")]}

        checks.append({"name": "ontology_exists", "status": "ok"})

        # 2. 获取所有类型定义
        object_types = self.ontology_service.list_object_types(ontology_id)
        link_types = self.ontology_service.list_link_types(ontology_id)
        action_types = self.ontology_service.list_action_types(ontology_id)

        obj_type_names = {t.get("name") for t in object_types.get("object_types", [])}
        obj_type_ids = {t.get("type_id") for t in object_types.get("object_types", [])}

        # 3. 引用完整性检查：link_type
        for link in link_types.get("link_types", []):
            source = link.get("source_type", "")
            target = link.get("target_type", "")
            if source and source not in obj_type_names and source not in obj_type_ids:
                issues.append(f"link_type '{link.get('name')}' 引用了不存在的 source_type: {source}")
            if target and target not in obj_type_names and target not in obj_type_ids:
                issues.append(f"link_type '{link.get('name')}' 引用了不存在的 target_type: {target}")

        checks.append({
            "name": "link_type_reference_integrity",
            "status": "ok" if not any("link_type" in i for i in issues) else "warning",
            "link_count": link_types.get("count", 0),
        })

        # 4. 引用完整性检查：action_type
        for action in action_types.get("action_types", []):
            target = action.get("target_object_type", "")
            if target and target not in obj_type_names and target not in obj_type_ids:
                issues.append(f"action_type '{action.get('name')}' 引用了不存在的 target_object_type: {target}")

        checks.append({
            "name": "action_type_reference_integrity",
            "status": "ok" if not any("action_type" in i for i in issues) else "warning",
            "action_count": action_types.get("count", 0),
        })

        # 5. OMS 缓存一致性
        oms_types = self.list_oms_object_types(active_only=False)
        oms_type_ids = {t.get("type_id") for t in oms_types}
        missing_in_oms = obj_type_ids - oms_type_ids
        if missing_in_oms:
            issues.append(f"OMS 缓存缺少 {len(missing_in_oms)} 个类型定义: {list(missing_in_oms)[:5]}")

        checks.append({
            "name": "oms_cache_consistency",
            "status": "ok" if not missing_in_oms else "warning",
            "ontology_type_count": len(obj_type_ids),
            "oms_type_count": len(oms_type_ids),
        })

        overall_status = "ok" if not issues else "warning"
        return {
            "status": overall_status,
            "ontology_id": ontology_id,
            "checks": checks,
            "issues": issues,
        }


# ── 单例 ──

_registry_instance: Optional[TypeRegistry] = None


def get_type_registry() -> TypeRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = TypeRegistry()
    return _registry_instance
