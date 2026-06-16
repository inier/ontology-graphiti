"""TypeRegistry 单元测试

测试统一类型定义读写入口和 OMS 同步适配器。
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch


# ── OMSSyncAdapter 测试 ──


class TestOMSSyncAdapter:
    """OMS 同步适配器测试"""

    def _make_adapter(self, oms_storage=None):
        from odap.biz.core.ontology.registry.oms_sync import OMSSyncAdapter
        return OMSSyncAdapter(oms_storage=oms_storage)

    def test_sync_object_type_created(self, tmp_path):
        """对象类型创建后同步到 OMS"""
        from odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
        storage = SQLiteOMSStorage(db_path=str(tmp_path / "test_oms.db"))
        adapter = self._make_adapter(oms_storage=storage)

        type_data = {
            "type_id": "test-type-001",
            "name": "TestType",
            "display_name": "测试类型",
            "description": "测试用",
            "properties": [{"name": "prop1", "property_type": "string"}],
            "links": [],
            "actions": [],
            "icon": "",
            "color": "",
            "is_active": True,
            "parent_type": None,
        }
        adapter.sync_object_type_created(type_data)

        result = storage.get_object_type("test-type-001")
        assert result is not None
        assert result["name"] == "TestType"

    def test_sync_object_type_updated(self, tmp_path):
        """对象类型更新后同步到 OMS"""
        from odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
        storage = SQLiteOMSStorage(db_path=str(tmp_path / "test_oms.db"))
        adapter = self._make_adapter(oms_storage=storage)

        # 先创建
        storage.create_object_type({
            "type_id": "test-type-002",
            "name": "OldName",
            "display_name": "旧名称",
        })

        # 同步更新
        type_data = {
            "type_id": "test-type-002",
            "name": "NewName",
            "display_name": "新名称",
            "description": "更新后",
            "properties": [],
            "links": [],
            "actions": [],
        }
        adapter.sync_object_type_updated(type_data)

        result = storage.get_object_type("test-type-002")
        assert result["name"] == "NewName"
        assert result["display_name"] == "新名称"

    def test_sync_object_type_deleted(self, tmp_path):
        """对象类型删除后从 OMS 移除"""
        from odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
        storage = SQLiteOMSStorage(db_path=str(tmp_path / "test_oms.db"))
        adapter = self._make_adapter(oms_storage=storage)

        storage.create_object_type({
            "type_id": "test-type-003",
            "name": "ToDelete",
        })
        assert storage.get_object_type("test-type-003") is not None

        adapter.sync_object_type_deleted("test-type-003")
        assert storage.get_object_type("test-type-003") is None

    def test_sync_skips_platform_seed_types(self, tmp_path):
        """平台核心实体（种子数据）不会被同步覆盖"""
        from odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
        storage = SQLiteOMSStorage(db_path=str(tmp_path / "test_oms.db"))
        adapter = self._make_adapter(oms_storage=storage)

        # Agent 是种子数据
        original = storage.get_object_type("Agent")
        assert original is not None

        type_data = {
            "type_id": "Agent",
            "name": "HackedAgent",
            "display_name": "被篡改",
        }
        adapter.sync_object_type_created(type_data)

        result = storage.get_object_type("Agent")
        assert result["name"] == "Agent"  # 未被覆盖

    def test_sync_action_type_created(self, tmp_path):
        """动作类型创建后同步到 OMS"""
        from odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
        storage = SQLiteOMSStorage(db_path=str(tmp_path / "test_oms.db"))
        adapter = self._make_adapter(oms_storage=storage)

        action_data = {
            "action_type_id": "act-test-001",
            "name": "TestAction",
            "display_name": "测试动作",
            "description": "测试",
            "target_object_type": "Agent",
            "parameters": [],
            "required_roles": [],
            "confirmation_required": False,
        }
        adapter.sync_action_type_created(action_data)

        result = storage.get_action_type("act-test-001")
        assert result is not None
        assert result["name"] == "TestAction"

    def test_convert_object_type_to_oms(self):
        """OntologyService 格式转 OMS 格式"""
        from odap.biz.core.ontology.registry.oms_sync import OMSSyncAdapter

        type_data = {
            "type_id": "test-001",
            "name": "TestType",
            "display_name": "测试",
            "description": "描述",
            "properties": [{"name": "p1", "property_type": "string"}],
            "links": [],
            "actions": [],
            "icon": "test-icon",
            "color": "#ff0000",
            "is_active": True,
            "parent_type": None,
        }
        result = OMSSyncAdapter._convert_object_type_to_oms(type_data)
        assert result["type_id"] == "test-001"
        assert result["name"] == "TestType"
        assert result["properties"] == [{"name": "p1", "property_type": "string"}]

    def test_convert_object_type_json_string_properties(self):
        """JSON 字符串属性正确解析"""
        from odap.biz.core.ontology.registry.oms_sync import OMSSyncAdapter

        type_data = {
            "type_id": "test-002",
            "name": "TestType",
            "properties": json.dumps([{"name": "p1"}]),
            "links": "[]",
            "actions": "[]",
        }
        result = OMSSyncAdapter._convert_object_type_to_oms(type_data)
        assert result["properties"] == [{"name": "p1"}]
        assert result["links"] == []
        assert result["actions"] == []

    def test_sync_failure_does_not_raise(self, tmp_path):
        """同步失败不抛异常（降级不回滚）"""
        adapter = self._make_adapter(oms_storage=None)
        # oms_storage 为 None，访问时会创建新实例，但 type_id 为空会失败
        type_data = {"type_id": "", "name": ""}
        # 不应抛异常
        adapter.sync_object_type_created(type_data)


# ── TypeRegistry 测试 ──


class TestTypeRegistry:
    """统一类型定义读写入口测试"""

    def _make_registry(self, ontology_service=None, oms_sync=None):
        from odap.biz.core.ontology.registry.type_registry import TypeRegistry
        return TypeRegistry(ontology_service=ontology_service, oms_sync=oms_sync)

    def test_create_object_type_delegates_and_syncs(self):
        """创建对象类型委托给 OntologyService 并触发 OMS 同步"""
        mock_service = MagicMock()
        mock_service.create_object_type.return_value = {
            "type_id": "new-type-001",
            "name": "NewType",
            "status": "active",
        }
        mock_sync = MagicMock()

        registry = self._make_registry(ontology_service=mock_service, oms_sync=mock_sync)
        result = registry.create_object_type("ont-001", {"name": "NewType"})

        mock_service.create_object_type.assert_called_once_with("ont-001", {"name": "NewType"})
        mock_sync.sync_object_type_created.assert_called_once()
        assert result["type_id"] == "new-type-001"

    def test_create_object_type_error_no_sync(self):
        """创建失败不触发 OMS 同步"""
        mock_service = MagicMock()
        mock_service.create_object_type.return_value = {
            "status": "error",
            "message": "name is required",
        }
        mock_sync = MagicMock()

        registry = self._make_registry(ontology_service=mock_service, oms_sync=mock_sync)
        result = registry.create_object_type("ont-001", {})

        mock_sync.sync_object_type_created.assert_not_called()
        assert result["status"] == "error"

    def test_update_object_type_delegates_and_syncs(self):
        """更新对象类型委托给 OntologyService 并触发 OMS 同步"""
        mock_service = MagicMock()
        mock_service.update_object_type.return_value = {
            "type_id": "type-001",
            "name": "UpdatedType",
        }
        mock_sync = MagicMock()

        registry = self._make_registry(ontology_service=mock_service, oms_sync=mock_sync)
        result = registry.update_object_type("type-001", {"name": "UpdatedType"})

        mock_service.update_object_type.assert_called_once_with("type-001", {"name": "UpdatedType"})
        mock_sync.sync_object_type_updated.assert_called_once()

    def test_delete_object_type_delegates_and_syncs(self):
        """删除对象类型委托给 OntologyService 并触发 OMS 同步"""
        mock_service = MagicMock()
        mock_service.delete_object_type.return_value = {"type_id": "type-001", "deleted": True}
        mock_sync = MagicMock()

        registry = self._make_registry(ontology_service=mock_service, oms_sync=mock_sync)
        result = registry.delete_object_type("type-001")

        mock_service.delete_object_type.assert_called_once_with("type-001")
        mock_sync.sync_object_type_deleted.assert_called_once_with("type-001")

    def test_create_action_type_delegates_and_syncs(self):
        """创建动作类型委托给 OntologyService 并触发 OMS 同步"""
        mock_service = MagicMock()
        mock_service.create_action_type.return_value = {
            "action_type_id": "act-001",
            "name": "NewAction",
        }
        mock_sync = MagicMock()

        registry = self._make_registry(ontology_service=mock_service, oms_sync=mock_sync)
        result = registry.create_action_type("ont-001", {"name": "NewAction"})

        mock_service.create_action_type.assert_called_once()
        mock_sync.sync_action_type_created.assert_called_once()

    def test_read_operations_delegate_without_sync(self):
        """读取操作只委托给 OntologyService，不触发 OMS 同步"""
        mock_service = MagicMock()
        mock_service.get_object_type.return_value = {"type_id": "type-001", "name": "Test"}
        mock_service.list_object_types.return_value = {"object_types": [], "count": 0}
        mock_sync = MagicMock()

        registry = self._make_registry(ontology_service=mock_service, oms_sync=mock_sync)

        registry.get_object_type("type-001")
        registry.list_object_types("ont-001")

        mock_sync.sync_object_type_created.assert_not_called()
        mock_sync.sync_object_type_updated.assert_not_called()
        mock_sync.sync_object_type_deleted.assert_not_called()

    def test_get_type_registry_singleton(self):
        """get_type_registry 返回单例"""
        from odap.biz.core.ontology.registry.type_registry import get_type_registry, _registry_instance
        # 重置单例
        import odap.biz.core.ontology.registry.type_registry as mod
        mod._registry_instance = None

        r1 = get_type_registry()
        r2 = get_type_registry()
        assert r1 is r2

        # 清理
        mod._registry_instance = None

    def test_link_type_operations_no_oms_sync(self):
        """关系类型操作不触发 OMS 同步（OMS 只有 object_type 和 action_type）"""
        mock_service = MagicMock()
        mock_service.create_link_type.return_value = {"link_id": "link-001"}
        mock_sync = MagicMock()

        registry = self._make_registry(ontology_service=mock_service, oms_sync=mock_sync)
        registry.create_link_type("ont-001", {"name": "TestLink", "source_type": "A", "target_type": "B"})

        mock_sync.sync_object_type_created.assert_not_called()
        mock_sync.sync_action_type_created.assert_not_called()

    def test_process_rule_function_indicator_no_oms_sync(self):
        """过程/规则/函数/指标类型操作不触发 OMS 同步"""
        mock_service = MagicMock()
        mock_service.create_process_type.return_value = {"type_id": "proc-001"}
        mock_service.create_rule_type.return_value = {"type_id": "rule-001"}
        mock_service.create_function_type.return_value = {"type_id": "func-001"}
        mock_service.create_indicator_type.return_value = {"type_id": "ind-001"}
        mock_sync = MagicMock()

        registry = self._make_registry(ontology_service=mock_service, oms_sync=mock_sync)
        registry.create_process_type("ont-001", {"name": "P"})
        registry.create_rule_type("ont-001", {"name": "R"})
        registry.create_function_type("ont-001", {"name": "F"})
        registry.create_indicator_type("ont-001", {"name": "I"})

        mock_sync.sync_object_type_created.assert_not_called()
        mock_sync.sync_action_type_created.assert_not_called()
