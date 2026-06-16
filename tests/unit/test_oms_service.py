"""
OMS Service 单元测试

覆盖:
- PropertyDefinition / ActionTypeDefinition / ObjectTypeDefinition 模型验证
- SQLiteOMSStorage CRUD 操作（使用 tmp_path 真实 DB）
- OMSService 编排层（使用 mock storage）
- 种子数据加载
- JSON 字段序列化/反序列化
"""

import pytest
import json
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def oms_storage(tmp_path):
    """创建使用临时目录的 SQLiteOMSStorage 实例"""
    from odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
    db_path = str(tmp_path / "test_oms.db")
    return SQLiteOMSStorage(db_path=db_path)


@pytest.fixture
def oms_service(oms_storage):
    """创建使用临时 storage 的 OMSService 实例"""
    from odap.biz.core.ontology.application.oms.services.oms_service import OMSService
    OMSService._instance = None
    return OMSService(storage=oms_storage)


# ---------------------------------------------------------------------------
# TestPropertyDefinition — 模型验证
# ---------------------------------------------------------------------------

class TestPropertyDefinition:
    def test_basic_creation(self):
        """基本属性定义创建"""
        from odap.biz.core.ontology.application.oms.schemas import PropertyDefinition
        prop = PropertyDefinition(name="test_prop", display_name="Test Property")
        assert prop.name == "test_prop"
        assert prop.display_name == "Test Property"
        assert prop.property_type.value == "string"
        assert prop.required is False

    def test_required_property(self):
        """必填属性"""
        from odap.biz.core.ontology.application.oms.schemas import PropertyDefinition
        prop = PropertyDefinition(name="id", required=True)
        assert prop.required is True

    def test_enum_values(self):
        """enum_values 字段"""
        from odap.biz.core.ontology.application.oms.schemas import PropertyDefinition
        prop = PropertyDefinition(
            name="status",
            property_type="string",
            enum_values=["active", "inactive"],
        )
        assert len(prop.enum_values) == 2
        assert "active" in prop.enum_values

    def test_reference_type(self):
        """reference 类型属性"""
        from odap.biz.core.ontology.application.oms.schemas import PropertyDefinition, PropertyType
        prop = PropertyDefinition(
            name="workspace_ref",
            property_type=PropertyType.REFERENCE,
            reference_type="Workspace",
        )
        assert prop.property_type == PropertyType.REFERENCE
        assert prop.reference_type == "Workspace"

    def test_constraints_field(self):
        """constraints 字段"""
        from odap.biz.core.ontology.application.oms.schemas import PropertyDefinition
        prop = PropertyDefinition(
            name="age",
            constraints={"min": 0, "max": 150},
        )
        assert prop.constraints["min"] == 0
        assert prop.constraints["max"] == 150


# ---------------------------------------------------------------------------
# TestActionTypeDefinition — 模型验证
# ---------------------------------------------------------------------------

class TestActionTypeDefinition:
    def test_basic_creation(self):
        """基本动作类型创建"""
        from odap.biz.core.ontology.application.oms.schemas import ActionTypeDefinition
        action = ActionTypeDefinition(
            action_type_id="agent.dispatch",
            name="dispatch",
            target_object_type="Agent",
        )
        assert action.action_type_id == "agent.dispatch"
        assert action.name == "dispatch"
        assert action.target_object_type == "Agent"
        assert action.is_active is True
        assert action.confirmation_required is False

    def test_parameters_default_factory(self):
        """parameters 必须使用 default_factory"""
        from odap.biz.core.ontology.application.oms.schemas import ActionTypeDefinition
        a1 = ActionTypeDefinition(action_type_id="a1", name="a1", target_object_type="T")
        a2 = ActionTypeDefinition(action_type_id="a2", name="a2", target_object_type="T")
        assert a1.parameters is not a2.parameters

    def test_required_roles_default_factory(self):
        """required_roles 必须使用 default_factory"""
        from odap.biz.core.ontology.application.oms.schemas import ActionTypeDefinition
        a1 = ActionTypeDefinition(action_type_id="a1", name="a1", target_object_type="T")
        a2 = ActionTypeDefinition(action_type_id="a2", name="a2", target_object_type="T")
        assert a1.required_roles is not a2.required_roles

    def test_confirmation_required(self):
        """需要确认的动作"""
        from odap.biz.core.ontology.application.oms.schemas import ActionTypeDefinition
        action = ActionTypeDefinition(
            action_type_id="ws.delete",
            name="delete",
            target_object_type="Workspace",
            confirmation_required=True,
        )
        assert action.confirmation_required is True


# ---------------------------------------------------------------------------
# TestObjectTypeDefinition — 模型验证
# ---------------------------------------------------------------------------

class TestObjectTypeDefinition:
    def test_basic_creation(self):
        """基本对象类型创建"""
        from odap.biz.core.ontology.application.oms.schemas import ObjectTypeDefinition
        obj = ObjectTypeDefinition(type_id="Agent", name="Agent")
        assert obj.type_id == "Agent"
        assert obj.name == "Agent"
        assert obj.is_active is True
        assert obj.properties == []
        assert obj.links == []
        assert obj.actions == []

    def test_container_fields_default_factory(self):
        """容器字段必须使用 default_factory"""
        from odap.biz.core.ontology.application.oms.schemas import ObjectTypeDefinition
        o1 = ObjectTypeDefinition(type_id="T1", name="T1")
        o2 = ObjectTypeDefinition(type_id="T2", name="T2")
        assert o1.properties is not o2.properties
        assert o1.links is not o2.links
        assert o1.actions is not o2.actions

    def test_with_properties_and_links(self):
        """带属性和链接的对象类型"""
        from odap.biz.core.ontology.application.oms.schemas import (
            ObjectTypeDefinition, PropertyDefinition, LinkDefinition,
        )
        obj = ObjectTypeDefinition(
            type_id="Scenario",
            name="Scenario",
            properties=[
                PropertyDefinition(name="scenario_id", required=True),
                PropertyDefinition(name="name", required=True),
            ],
            links=[
                LinkDefinition(
                    name="belongs_to_workspace",
                    source_type="Scenario",
                    target_type="Workspace",
                ),
            ],
        )
        assert len(obj.properties) == 2
        assert len(obj.links) == 1
        assert obj.links[0].target_type == "Workspace"


# ---------------------------------------------------------------------------
# TestSQLiteOMSStorage — CRUD 操作（真实 DB）
# ---------------------------------------------------------------------------

class TestSQLiteOMSStorage:
    def test_seed_data_loaded(self, oms_storage):
        """初始化时应加载种子数据"""
        types = oms_storage.list_object_types(active_only=False)
        assert len(types) > 0
        type_names = [t["name"] for t in types]
        assert "Agent" in type_names
        assert "Workspace" in type_names

    def test_seed_action_types_loaded(self, oms_storage):
        """初始化时应加载种子动作类型"""
        actions = oms_storage.list_action_types()
        assert len(actions) > 0

    def test_create_object_type(self, oms_storage):
        """创建对象类型"""
        result = oms_storage.create_object_type({
            "type_id": "TestType",
            "name": "TestType",
            "display_name": "测试类型",
            "description": "A test type",
        })
        assert result is not None
        assert result["type_id"] == "TestType"
        assert result["name"] == "TestType"

    def test_get_object_type(self, oms_storage):
        """获取已存在的对象类型"""
        oms_storage.create_object_type({
            "type_id": "GetType",
            "name": "GetType",
        })
        result = oms_storage.get_object_type("GetType")
        assert result is not None
        assert result["type_id"] == "GetType"

    def test_get_object_type_not_found(self, oms_storage):
        """获取不存在的对象类型返回 None"""
        result = oms_storage.get_object_type("NonExistent")
        assert result is None

    def test_update_object_type(self, oms_storage):
        """更新对象类型"""
        oms_storage.create_object_type({
            "type_id": "UpdateType",
            "name": "UpdateType",
        })
        result = oms_storage.update_object_type("UpdateType", {
            "display_name": "Updated Display",
            "description": "Updated desc",
        })
        assert result is not None
        assert result["display_name"] == "Updated Display"
        assert result["description"] == "Updated desc"

    def test_update_object_type_not_found(self, oms_storage):
        """更新不存在的对象类型返回 None"""
        result = oms_storage.update_object_type("NonExistent", {"name": "x"})
        assert result is None

    def test_delete_object_type(self, oms_storage):
        """删除对象类型"""
        oms_storage.create_object_type({
            "type_id": "DeleteType",
            "name": "DeleteType",
        })
        assert oms_storage.delete_object_type("DeleteType") is True
        assert oms_storage.get_object_type("DeleteType") is None

    def test_delete_object_type_not_found(self, oms_storage):
        """删除不存在的对象类型返回 False"""
        assert oms_storage.delete_object_type("NonExistent") is False

    def test_list_object_types_active_only(self, oms_storage):
        """active_only 过滤"""
        oms_storage.create_object_type({
            "type_id": "ActiveType",
            "name": "ActiveType",
        })
        oms_storage.create_object_type({
            "type_id": "InactiveType",
            "name": "InactiveType",
        })
        # 手动设为 inactive
        oms_storage.update_object_type("InactiveType", {"is_active": 0})

        active = oms_storage.list_object_types(active_only=True)
        active_ids = [t["type_id"] for t in active]
        assert "ActiveType" in active_ids
        assert "InactiveType" not in active_ids

    def test_json_fields_serialization(self, oms_storage):
        """JSON 字段（properties/links/actions）正确序列化"""
        oms_storage.create_object_type({
            "type_id": "JsonType",
            "name": "JsonType",
            "properties": [{"name": "prop1", "data_type": "string"}],
            "links": [{"name": "link1", "target_type": "Other"}],
            "actions": ["act1", "act2"],
        })
        result = oms_storage.get_object_type("JsonType")
        assert isinstance(result["properties"], list)
        assert len(result["properties"]) == 1
        assert isinstance(result["links"], list)
        assert isinstance(result["actions"], list)
        assert "act1" in result["actions"]

    def test_create_action_type(self, oms_storage):
        """创建动作类型"""
        result = oms_storage.create_action_type({
            "action_type_id": "test.run",
            "name": "run",
            "target_object_type": "TestType",
            "parameters": [{"name": "param1", "data_type": "string"}],
            "required_roles": ["admin"],
        })
        assert result is not None
        assert result["action_type_id"] == "test.run"
        assert isinstance(result["parameters"], list)
        assert isinstance(result["required_roles"], list)

    def test_get_action_type_not_found(self, oms_storage):
        """获取不存在的动作类型返回 None"""
        result = oms_storage.get_action_type("nonexistent.action")
        assert result is None

    def test_delete_action_type(self, oms_storage):
        """删除动作类型"""
        oms_storage.create_action_type({
            "action_type_id": "test.del",
            "name": "del",
            "target_object_type": "TestType",
        })
        assert oms_storage.delete_action_type("test.del") is True
        assert oms_storage.get_action_type("test.del") is None

    def test_delete_action_type_not_found(self, oms_storage):
        """删除不存在的动作类型返回 False"""
        assert oms_storage.delete_action_type("nonexistent.action") is False

    def test_list_action_types_by_target(self, oms_storage):
        """按 target_object_type 过滤动作类型"""
        oms_storage.create_action_type({
            "action_type_id": "test.filter1",
            "name": "filter1",
            "target_object_type": "FilterTarget",
        })
        oms_storage.create_action_type({
            "action_type_id": "test.filter2",
            "name": "filter2",
            "target_object_type": "OtherTarget",
        })
        results = oms_storage.list_action_types(target_type="FilterTarget")
        assert all(a["target_object_type"] == "FilterTarget" for a in results)

    def test_bind_unbind_action(self, oms_storage):
        """绑定/解绑动作到对象类型"""
        oms_storage.create_object_type({
            "type_id": "BindTarget",
            "name": "BindTarget",
        })
        oms_storage.create_action_type({
            "action_type_id": "bind.action",
            "name": "bind_action",
            "target_object_type": "BindTarget",
        })
        # 绑定
        assert oms_storage.bind_action_to_object_type("BindTarget", "bind.action") is True
        obj = oms_storage.get_object_type("BindTarget")
        assert "bind.action" in obj["actions"]

        # 解绑
        assert oms_storage.unbind_action_from_object_type("BindTarget", "bind.action") is True
        obj = oms_storage.get_object_type("BindTarget")
        assert "bind.action" not in obj["actions"]

    def test_bind_action_object_not_found(self, oms_storage):
        """绑定到不存在的对象类型返回 False"""
        result = oms_storage.bind_action_to_object_type("NonExistent", "some.action")
        assert result is False

    def test_bind_action_action_not_found(self, oms_storage):
        """绑定不存在的动作返回 False"""
        oms_storage.create_object_type({"type_id": "ObjForBind", "name": "ObjForBind"})
        result = oms_storage.bind_action_to_object_type("ObjForBind", "nonexistent.action")
        assert result is False

    def test_map_property_type(self, oms_storage):
        """_map_property_type 静态方法"""
        from odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
        assert SQLiteOMSStorage._map_property_type("string") == "string"
        assert SQLiteOMSStorage._map_property_type("int") == "integer"
        assert SQLiteOMSStorage._map_property_type("float") == "float"
        assert SQLiteOMSStorage._map_property_type("bool") == "boolean"
        assert SQLiteOMSStorage._map_property_type("datetime") == "datetime"
        assert SQLiteOMSStorage._map_property_type("tuple") == "geopoint"
        assert SQLiteOMSStorage._map_property_type("list") == "json"
        assert SQLiteOMSStorage._map_property_type("dict") == "json"
        assert SQLiteOMSStorage._map_property_type("unknown") == "string"


# ---------------------------------------------------------------------------
# TestOMSService — 编排层
# ---------------------------------------------------------------------------

class TestOMSService:
    def test_list_object_types(self, oms_service):
        """列出对象类型"""
        result = oms_service.list_object_types()
        assert isinstance(result, list)

    def test_get_object_type(self, oms_service):
        """获取对象类型"""
        result = oms_service.get_object_type("Agent")
        assert result is not None
        assert result["type_id"] == "Agent"

    def test_get_object_type_not_found(self, oms_service):
        """获取不存在的对象类型"""
        result = oms_service.get_object_type("NonExistent")
        assert result is None

    def test_create_and_delete_object_type(self, oms_service):
        """创建和删除对象类型"""
        created = oms_service.create_object_type({
            "type_id": "SvcTest",
            "name": "SvcTest",
        })
        assert created is not None
        assert oms_service.delete_object_type("SvcTest") is True

    def test_list_action_types(self, oms_service):
        """列出动作类型"""
        result = oms_service.list_action_types()
        assert isinstance(result, list)

    def test_singleton_pattern(self):
        """OMSService 单例模式"""
        from odap.biz.core.ontology.application.oms.services.oms_service import OMSService
        OMSService._instance = None
        s1 = OMSService.get_instance()
        s2 = OMSService.get_instance()
        assert s1 is s2
        OMSService._instance = None


# ---------------------------------------------------------------------------
# TestSeedData — 种子数据
# ---------------------------------------------------------------------------

class TestSeedData:
    def test_generate_oms_seed_data_structure(self):
        """种子数据应包含 object_types 和 action_types"""
        from odap.biz.core.ontology.application.oms.seed_data import generate_oms_seed_data
        data = generate_oms_seed_data()
        assert "object_types" in data
        assert "action_types" in data

    def test_seed_data_object_types(self):
        """种子数据应包含核心对象类型"""
        from odap.biz.core.ontology.application.oms.seed_data import generate_oms_seed_data
        data = generate_oms_seed_data()
        obj_types = data["object_types"]
        assert "Agent" in obj_types
        assert "Workspace" in obj_types
        assert "Scenario" in obj_types
        assert "Ontology" in obj_types
        assert "Simulation" in obj_types

    def test_seed_data_action_types(self):
        """种子数据应包含核心动作类型"""
        from odap.biz.core.ontology.application.oms.seed_data import generate_oms_seed_data
        data = generate_oms_seed_data()
        actions = data["action_types"]
        assert len(actions) > 0
        action_ids = [a["action_type_id"] for a in actions]
        assert "agent.dispatch" in action_ids
        assert "workspace.create" in action_ids

    def test_seed_data_object_type_has_properties(self):
        """种子数据对象类型应包含 basic_properties"""
        from odap.biz.core.ontology.application.oms.seed_data import generate_oms_seed_data
        data = generate_oms_seed_data()
        agent = data["object_types"]["Agent"]
        assert "basic_properties" in agent
        assert len(agent["basic_properties"]) > 0
