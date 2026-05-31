import pytest
import os
import json
from datetime import datetime


def _make_storage(tmp_path, storage_cls):
    db_path = str(tmp_path / "test_blueprint.db")
    return storage_cls(db_path=db_path)


class TestBlueprintStorage:
    def test_init_db(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        assert os.path.exists(storage.db_path)

    def test_save_and_get(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        now = datetime.now().isoformat()
        bp = {
            "blueprint_id": "bp-test001", "name": "TestBP", "description": "A test blueprint",
            "scenario_id": "sc-001", "version": 1,
            "nodes": [{"node_id": "n1", "node_type": "data_source", "name": "Source"}],
            "edges": [{"edge_id": "e1", "source": "n1", "target": "n2"}],
            "layout": {"zoom": 1.0}, "is_published": False, "parent_version_id": None,
            "created_at": now, "updated_at": now, "metadata": {"author": "test"},
        }
        storage.save(bp)
        fetched = storage.get("bp-test001")
        assert fetched is not None
        assert fetched["name"] == "TestBP"
        assert len(fetched["nodes"]) == 1
        assert fetched["nodes"][0]["node_type"] == "data_source"
        assert len(fetched["edges"]) == 1
        assert fetched["layout"] == {"zoom": 1.0}
        assert fetched["metadata"] == {"author": "test"}
        assert fetched["is_published"] is False

    def test_list_blueprints(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        now = datetime.now().isoformat()
        storage.save({"blueprint_id": "bp-1", "name": "BP1", "description": "",
                       "scenario_id": "sc-1", "version": 1, "nodes": [], "edges": [],
                       "layout": {}, "is_published": False, "parent_version_id": None,
                       "created_at": now, "updated_at": now, "metadata": {}})
        storage.save({"blueprint_id": "bp-2", "name": "BP2", "description": "",
                       "scenario_id": "sc-1", "version": 1, "nodes": [], "edges": [],
                       "layout": {}, "is_published": True, "parent_version_id": None,
                       "created_at": now, "updated_at": now, "metadata": {}})
        all_bps = storage.list_blueprints()
        assert len(all_bps) == 2
        by_scenario = storage.list_blueprints(scenario_id="sc-1")
        assert len(by_scenario) == 2
        published = storage.list_blueprints(is_published=True)
        assert len(published) == 1
        assert published[0]["name"] == "BP2"

    def test_delete(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        now = datetime.now().isoformat()
        storage.save({"blueprint_id": "bp-del", "name": "Del", "description": "",
                       "scenario_id": None, "version": 1, "nodes": [], "edges": [],
                       "layout": {}, "is_published": False, "parent_version_id": None,
                       "created_at": now, "updated_at": now, "metadata": {}})
        assert storage.delete("bp-del") is True
        assert storage.get("bp-del") is None
        assert storage.delete("bp-del") is False

    def test_get_nonexistent(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        assert storage.get("nonexistent") is None

    def test_json_fields_serialization(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        now = datetime.now().isoformat()
        bp = {
            "blueprint_id": "bp-json", "name": "JsonBP", "description": "",
            "scenario_id": None, "version": 1,
            "nodes": [{"node_id": "n1"}, {"node_id": "n2"}],
            "edges": [{"edge_id": "e1"}],
            "layout": {"x": 100, "y": 200},
            "is_published": False, "parent_version_id": None,
            "created_at": now, "updated_at": now,
            "metadata": {"tags": ["a", "b"]},
        }
        storage.save(bp)
        fetched = storage.get("bp-json")
        assert len(fetched["nodes"]) == 2
        assert len(fetched["edges"]) == 1
        assert fetched["layout"]["x"] == 100
        assert fetched["metadata"]["tags"] == ["a", "b"]


class TestBlueprintDesignerService:
    def test_create_blueprint(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        result = service.create_blueprint(name="MyBP", description="Test")
        assert result["status"] == "success"
        assert result["blueprint_id"].startswith("bp-")
        assert result["version"] == 1

    def test_get_blueprint(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="GetBP")
        result = service.get_blueprint(created["blueprint_id"])
        assert result["status"] == "success"
        assert result["name"] == "GetBP"

    def test_get_blueprint_not_found(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        result = service.get_blueprint("nonexistent")
        assert result["status"] == "error"

    def test_list_blueprints(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        service.create_blueprint(name="BP1")
        service.create_blueprint(name="BP2")
        result = service.list_blueprints()
        assert result["count"] == 2

    def test_update_blueprint(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="UpdateBP")
        result = service.update_blueprint(created["blueprint_id"], name="UpdatedBP", description="Updated")
        assert result["status"] == "success"
        fetched = service.get_blueprint(created["blueprint_id"])
        assert fetched["name"] == "UpdatedBP"

    def test_update_blueprint_not_found(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        result = service.update_blueprint("nonexistent", name="X")
        assert result["status"] == "error"

    def test_delete_blueprint(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="DelBP")
        result = service.delete_blueprint(created["blueprint_id"])
        assert result["status"] == "success"
        result = service.delete_blueprint(created["blueprint_id"])
        assert result["status"] == "error"

    def test_add_node(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="NodeBP")
        result = service.add_node(created["blueprint_id"], "data_source", "Source",
                                  position={"x": 10, "y": 20}, config={"source_type": "api"})
        assert result["status"] == "success"
        assert result["node_id"].startswith("node-")
        fetched = service.get_blueprint(created["blueprint_id"])
        assert len(fetched["nodes"]) == 1
        assert fetched["nodes"][0]["name"] == "Source"

    def test_add_node_blueprint_not_found(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        result = service.add_node("nonexistent", "data_source", "Source")
        assert result["status"] == "error"

    def test_update_node(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="UpdNodeBP")
        node = service.add_node(created["blueprint_id"], "data_source", "Source")
        result = service.update_node(created["blueprint_id"], node["node_id"], name="UpdatedSource")
        assert result["status"] == "success"
        fetched = service.get_blueprint(created["blueprint_id"])
        assert fetched["nodes"][0]["name"] == "UpdatedSource"

    def test_update_node_not_found(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="UpdNodeNF")
        result = service.update_node(created["blueprint_id"], "nonexistent", name="X")
        assert result["status"] == "error"

    def test_remove_node(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="RemNodeBP")
        n1 = service.add_node(created["blueprint_id"], "data_source", "S1")
        n2 = service.add_node(created["blueprint_id"], "transform", "T1")
        service.add_edge(created["blueprint_id"], n1["node_id"], n2["node_id"])
        result = service.remove_node(created["blueprint_id"], n1["node_id"])
        assert result["status"] == "success"
        fetched = service.get_blueprint(created["blueprint_id"])
        assert len(fetched["nodes"]) == 1
        assert len(fetched["edges"]) == 0

    def test_add_edge(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="EdgeBP")
        n1 = service.add_node(created["blueprint_id"], "data_source", "S1")
        n2 = service.add_node(created["blueprint_id"], "transform", "T1")
        result = service.add_edge(created["blueprint_id"], n1["node_id"], n2["node_id"],
                                  edge_type="data_flow", label="data")
        assert result["status"] == "success"
        assert result["edge_id"].startswith("edge-")
        fetched = service.get_blueprint(created["blueprint_id"])
        assert len(fetched["edges"]) == 1

    def test_add_edge_invalid_nodes(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="EdgeInvBP")
        result = service.add_edge(created["blueprint_id"], "fake-source", "fake-target")
        assert result["status"] == "error"

    def test_remove_edge(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="RemEdgeBP")
        n1 = service.add_node(created["blueprint_id"], "data_source", "S1")
        n2 = service.add_node(created["blueprint_id"], "transform", "T1")
        edge = service.add_edge(created["blueprint_id"], n1["node_id"], n2["node_id"])
        result = service.remove_edge(created["blueprint_id"], edge["edge_id"])
        assert result["status"] == "success"
        fetched = service.get_blueprint(created["blueprint_id"])
        assert len(fetched["edges"]) == 0

    def test_validate_blueprint_valid(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="ValidBP")
        n1 = service.add_node(created["blueprint_id"], "data_source", "S1")
        n2 = service.add_node(created["blueprint_id"], "transform", "T1")
        service.add_edge(created["blueprint_id"], n1["node_id"], n2["node_id"])
        result = service.validate_blueprint(created["blueprint_id"])
        assert result["is_valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_blueprint_empty(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="EmptyBP")
        result = service.validate_blueprint(created["blueprint_id"])
        assert result["is_valid"] is False
        assert "no nodes" in result["errors"][0]

    def test_validate_blueprint_disconnected(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="DiscBP")
        service.add_node(created["blueprint_id"], "data_source", "S1")
        service.add_node(created["blueprint_id"], "transform", "T1")
        result = service.validate_blueprint(created["blueprint_id"])
        assert len(result["warnings"]) > 0

    def test_publish_blueprint(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="PubBP")
        n1 = service.add_node(created["blueprint_id"], "data_source", "S1")
        n2 = service.add_node(created["blueprint_id"], "transform", "T1")
        service.add_edge(created["blueprint_id"], n1["node_id"], n2["node_id"])
        result = service.publish_blueprint(created["blueprint_id"])
        assert result["is_published"] is True

    def test_publish_invalid_blueprint(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="PubInvBP")
        result = service.publish_blueprint(created["blueprint_id"])
        assert result["status"] == "error"

    def test_fork_blueprint(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="ForkBP", scenario_id="sc-1")
        service.add_node(created["blueprint_id"], "data_source", "S1")
        result = service.fork_blueprint(created["blueprint_id"], new_name="ForkedBP")
        assert result["status"] == "success"
        assert result["parent_version_id"] == created["blueprint_id"]
        forked = service.get_blueprint(result["blueprint_id"])
        assert forked["name"] == "ForkedBP"
        assert len(forked["nodes"]) == 1

    def test_fork_blueprint_not_found(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        result = service.fork_blueprint("nonexistent")
        assert result["status"] == "error"

    def test_export_json(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="ExportBP")
        service.add_node(created["blueprint_id"], "data_source", "S1")
        result = service.export_blueprint(created["blueprint_id"], format="json")
        assert result["format"] == "json"
        assert result["blueprint"]["name"] == "ExportBP"
        assert len(result["blueprint"]["nodes"]) == 1

    def test_export_code(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="CodeBP")
        service.add_node(created["blueprint_id"], "data_source", "MySource",
                         config={"source_type": "api"})
        result = service.export_blueprint(created["blueprint_id"], format="code")
        assert result["format"] == "code"
        assert "MySource" in result["code"]

    def test_export_unsupported_format(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        created = service.create_blueprint(name="FmtBP")
        result = service.export_blueprint(created["blueprint_id"], format="xml")
        assert result["status"] == "error"

    def test_export_not_found(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
        storage = _make_storage(tmp_path, BlueprintStorage)
        service = BlueprintDesignerService(storage=storage)
        result = service.export_blueprint("nonexistent")
        assert result["status"] == "error"

    def test_singleton(self, tmp_path):
        from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
        BlueprintDesignerService._instance = None
        from odap.biz.core.ontology.harness.blueprint import get_blueprint_designer
        s1 = get_blueprint_designer()
        s2 = get_blueprint_designer()
        assert s1 is s2
        BlueprintDesignerService._instance = None


class TestBlueprintEnums:
    def test_node_type_enum(self):
        from odap.biz.core.ontology.harness.blueprint.api.schemas import BlueprintNodeType
        assert BlueprintNodeType.DATA_SOURCE.value == "data_source"
        assert BlueprintNodeType.TRANSFORM.value == "transform"
        assert BlueprintNodeType.ONTOLOGY.value == "ontology"
        assert BlueprintNodeType.ACTION.value == "action"
        assert BlueprintNodeType.VALIDATION.value == "validation"
        assert BlueprintNodeType.OUTPUT.value == "output"
        assert BlueprintNodeType.AGENT.value == "agent"
        assert BlueprintNodeType.DECISION.value == "decision"

    def test_edge_type_enum(self):
        from odap.biz.core.ontology.harness.blueprint.api.schemas import BlueprintEdgeType
        assert BlueprintEdgeType.DATA_FLOW.value == "data_flow"
        assert BlueprintEdgeType.CONTROL_FLOW.value == "control_flow"
        assert BlueprintEdgeType.DEPENDENCY.value == "dependency"

    def test_enum_str_inheritance(self):
        from odap.biz.core.ontology.harness.blueprint.api.schemas import BlueprintNodeType, BlueprintEdgeType
        assert isinstance(BlueprintNodeType.DATA_SOURCE, str)
        assert isinstance(BlueprintEdgeType.DATA_FLOW, str)
