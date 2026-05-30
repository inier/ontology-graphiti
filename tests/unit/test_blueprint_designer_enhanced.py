import pytest
import os
import json
from datetime import datetime
from pydantic import ValidationError


def _make_service(tmp_path):
    from odap.biz.core.ontology.harness.blueprint.blueprint_service import BlueprintDesignerService
    from odap.biz.core.ontology.harness.blueprint.storage import BlueprintStorage
    db_path = str(tmp_path / "test_blueprint_enhanced.db")
    storage = BlueprintStorage(db_path=db_path)
    return BlueprintDesignerService(storage=storage)


class TestBlueprintSchemas:
    def test_create_blueprint_request_validates_required_fields(self):
        from odap.biz.core.ontology.harness.blueprint.api.schemas import CreateBlueprintRequest
        req = CreateBlueprintRequest(name="TestBP")
        assert req.name == "TestBP"
        assert req.description == ""
        assert req.nodes == []
        assert req.edges == []
        assert req.layout == {}
        assert req.metadata == {}
        with pytest.raises(ValidationError):
            CreateBlueprintRequest()

    def test_add_node_request_validates_required_fields(self):
        from odap.biz.core.ontology.harness.blueprint.api.schemas import AddNodeRequest
        req = AddNodeRequest(node_type="data_source", name="Source")
        assert req.node_type == "data_source"
        assert req.name == "Source"
        assert req.position is None
        assert req.config is None
        with pytest.raises(ValidationError):
            AddNodeRequest(node_type="data_source")
        with pytest.raises(ValidationError):
            AddNodeRequest(name="Source")

    def test_add_edge_request_validates_required_fields(self):
        from odap.biz.core.ontology.harness.blueprint.api.schemas import AddEdgeRequest
        req = AddEdgeRequest(source="n1", target="n2")
        assert req.source == "n1"
        assert req.target == "n2"
        assert req.edge_type == "data_flow"
        assert req.label == ""
        with pytest.raises(ValidationError):
            AddEdgeRequest(source="n1")
        with pytest.raises(ValidationError):
            AddEdgeRequest()

    def test_update_blueprint_request_optional_fields(self):
        from odap.biz.core.ontology.harness.blueprint.api.schemas import UpdateBlueprintRequest
        req = UpdateBlueprintRequest()
        assert req.name is None
        assert req.description is None
        assert req.nodes is None
        assert req.edges is None
        assert req.layout is None
        assert req.metadata is None
        req2 = UpdateBlueprintRequest(name="NewName", description="NewDesc")
        assert req2.name == "NewName"
        assert req2.description == "NewDesc"

    def test_transition_request_validates_required_fields(self):
        from odap.biz.core.ontology.harness.blueprint.api.schemas import BatchAddNodesRequest, BatchAddEdgesRequest, BatchUpdatePositionsRequest
        with pytest.raises(ValidationError):
            BatchAddNodesRequest()
        with pytest.raises(ValidationError):
            BatchAddEdgesRequest()
        with pytest.raises(ValidationError):
            BatchUpdatePositionsRequest()
        batch_nodes = BatchAddNodesRequest(nodes=[
            {"node_type": "data_source", "name": "S1"},
            {"node_type": "transform", "name": "T1"},
        ])
        assert len(batch_nodes.nodes) == 2
        batch_edges = BatchAddEdgesRequest(edges=[
            {"source": "n1", "target": "n2"},
        ])
        assert len(batch_edges.edges) == 1
        batch_pos = BatchUpdatePositionsRequest(positions={"n1": {"x": 10.0, "y": 20.0}})
        assert "n1" in batch_pos.positions


class TestBlueprintBatchOperations:
    def test_batch_add_nodes(self, tmp_path):
        service = _make_service(tmp_path)
        created = service.create_blueprint(name="BatchNodeBP")
        nodes = [
            {"node_type": "data_source", "name": "Source1", "position": {"x": 0, "y": 0}},
            {"node_type": "transform", "name": "Transform1", "position": {"x": 250, "y": 0}},
            {"node_type": "output", "name": "Output1", "position": {"x": 500, "y": 0}},
        ]
        result = service.batch_add_nodes(created["blueprint_id"], nodes)
        assert result["status"] == "success"
        assert result["added_count"] == 3
        assert len(result["node_ids"]) == 3
        fetched = service.get_blueprint(created["blueprint_id"])
        assert len(fetched["nodes"]) == 3

    def test_batch_add_edges(self, tmp_path):
        service = _make_service(tmp_path)
        created = service.create_blueprint(name="BatchEdgeBP")
        n1 = service.add_node(created["blueprint_id"], "data_source", "S1")
        n2 = service.add_node(created["blueprint_id"], "transform", "T1")
        n3 = service.add_node(created["blueprint_id"], "output", "O1")
        edges = [
            {"source": n1["node_id"], "target": n2["node_id"], "edge_type": "data_flow"},
            {"source": n2["node_id"], "target": n3["node_id"], "edge_type": "data_flow"},
        ]
        result = service.batch_add_edges(created["blueprint_id"], edges)
        assert result["status"] == "success"
        assert result["added_count"] == 2
        assert len(result["edge_ids"]) == 2
        fetched = service.get_blueprint(created["blueprint_id"])
        assert len(fetched["edges"]) == 2

    def test_batch_update_positions(self, tmp_path):
        service = _make_service(tmp_path)
        created = service.create_blueprint(name="PosBP")
        n1 = service.add_node(created["blueprint_id"], "data_source", "S1",
                              position={"x": 0, "y": 0})
        n2 = service.add_node(created["blueprint_id"], "transform", "T1",
                              position={"x": 0, "y": 0})
        positions = {
            n1["node_id"]: {"x": 100.0, "y": 200.0},
            n2["node_id"]: {"x": 300.0, "y": 400.0},
        }
        result = service.batch_update_positions(created["blueprint_id"], positions)
        assert result["status"] == "success"
        assert result["updated_count"] == 2
        fetched = service.get_blueprint(created["blueprint_id"])
        node_map = {n["node_id"]: n for n in fetched["nodes"]}
        assert node_map[n1["node_id"]]["position"] == {"x": 100.0, "y": 200.0}
        assert node_map[n2["node_id"]]["position"] == {"x": 300.0, "y": 400.0}

    def test_batch_update_positions_partial(self, tmp_path):
        service = _make_service(tmp_path)
        created = service.create_blueprint(name="PartialPosBP")
        n1 = service.add_node(created["blueprint_id"], "data_source", "S1",
                              position={"x": 0, "y": 0})
        positions = {
            n1["node_id"]: {"x": 50.0, "y": 60.0},
            "nonexistent-node": {"x": 999.0, "y": 999.0},
        }
        result = service.batch_update_positions(created["blueprint_id"], positions)
        assert result["status"] == "success"
        assert result["updated_count"] == 1
        assert result["skipped_count"] == 1
        fetched = service.get_blueprint(created["blueprint_id"])
        node_map = {n["node_id"]: n for n in fetched["nodes"]}
        assert node_map[n1["node_id"]]["position"] == {"x": 50.0, "y": 60.0}


class TestBlueprintAutoLayout:
    def test_auto_layout_creates_positions(self, tmp_path):
        service = _make_service(tmp_path)
        created = service.create_blueprint(name="AutoLayoutBP")
        service.add_node(created["blueprint_id"], "data_source", "S1")
        service.add_node(created["blueprint_id"], "transform", "T1")
        service.add_node(created["blueprint_id"], "output", "O1")
        result = service.auto_layout(created["blueprint_id"])
        assert result["status"] == "success"
        assert result["layout_count"] == 3
        fetched = service.get_blueprint(created["blueprint_id"])
        for node in fetched["nodes"]:
            assert "x" in node["position"]
            assert "y" in node["position"]

    def test_auto_layout_preserves_existing_positions(self, tmp_path):
        service = _make_service(tmp_path)
        created = service.create_blueprint(name="PreservePosBP")
        n1 = service.add_node(created["blueprint_id"], "data_source", "S1",
                              position={"x": 42.0, "y": 99.0})
        n2 = service.add_node(created["blueprint_id"], "transform", "T1")
        result = service.auto_layout(created["blueprint_id"])
        assert result["status"] == "success"
        fetched = service.get_blueprint(created["blueprint_id"])
        node_map = {n["node_id"]: n for n in fetched["nodes"]}
        assert node_map[n1["node_id"]]["position"]["x"] == 42.0
        assert node_map[n1["node_id"]]["position"]["y"] == 99.0

    def test_auto_layout_empty_blueprint(self, tmp_path):
        service = _make_service(tmp_path)
        created = service.create_blueprint(name="EmptyLayoutBP")
        result = service.auto_layout(created["blueprint_id"])
        assert result["status"] == "success"
        assert result["layout_count"] == 0


class TestBlueprintImportExport:
    def test_import_from_json(self, tmp_path):
        service = _make_service(tmp_path)
        import_data = {
            "nodes": [
                {"node_type": "data_source", "name": "Source", "config": {"source_type": "api"}},
                {"node_type": "transform", "name": "Transform"},
            ],
            "edges": [
                {"source": 0, "target": 1, "edge_type": "data_flow"},
            ],
        }
        result = service.import_blueprint(name="ImportedBP", data=import_data, scenario_id="sc-1")
        assert result["status"] == "success"
        assert result["blueprint_id"].startswith("bp-")
        fetched = service.get_blueprint(result["blueprint_id"])
        assert fetched["name"] == "ImportedBP"
        assert fetched["scenario_id"] == "sc-1"
        assert len(fetched["nodes"]) == 2
        assert len(fetched["edges"]) == 1

    def test_import_validates_required_fields(self, tmp_path):
        service = _make_service(tmp_path)
        result = service.import_blueprint(name="", data={})
        assert result["status"] == "error"
        result2 = service.import_blueprint(name="NoData", data=None)
        assert result2["status"] == "error"

    def test_export_to_pipeline_config(self, tmp_path):
        service = _make_service(tmp_path)
        created = service.create_blueprint(name="PipelineBP")
        n1 = service.add_node(created["blueprint_id"], "data_source", "Source",
                              config={"source_type": "api"})
        n2 = service.add_node(created["blueprint_id"], "transform", "Transform",
                              config={"transform_type": "map"})
        service.add_edge(created["blueprint_id"], n1["node_id"], n2["node_id"],
                        edge_type="data_flow", label="raw_data")
        result = service.export_to_pipeline_config(created["blueprint_id"])
        assert result["status"] == "success"
        assert "pipeline" in result
        pipeline = result["pipeline"]
        assert "name" in pipeline
        assert "stages" in pipeline
        assert "connections" in pipeline
        assert len(pipeline["stages"]) == 2
        assert len(pipeline["connections"]) == 1


class TestBlueprintVersionHistory:
    def test_get_version_history(self, tmp_path):
        service = _make_service(tmp_path)
        created = service.create_blueprint(name="VersionBP")
        service.update_blueprint(created["blueprint_id"], name="VersionBP_v2")
        service.update_blueprint(created["blueprint_id"], description="Updated desc")
        result = service.get_version_history(created["blueprint_id"])
        assert result["status"] == "success"
        assert "history" in result
        assert len(result["history"]) >= 1

    def test_compare_versions(self, tmp_path):
        service = _make_service(tmp_path)
        created = service.create_blueprint(name="CompareBP")
        bp = service.get_blueprint(created["blueprint_id"])
        original_data = {
            "name": bp["name"],
            "description": bp.get("description", ""),
            "nodes": bp.get("nodes", []),
            "edges": bp.get("edges", []),
        }
        service.update_blueprint(created["blueprint_id"], name="CompareBP_v2")
        service.add_node(created["blueprint_id"], "data_source", "NewSource")
        updated = service.get_blueprint(created["blueprint_id"])
        updated_data = {
            "name": updated["name"],
            "description": updated.get("description", ""),
            "nodes": updated.get("nodes", []),
            "edges": updated.get("edges", []),
        }
        result = service.compare_versions(created["blueprint_id"],
                                          original_data, updated_data)
        assert result["status"] == "success"
        assert "diff" in result
        diff = result["diff"]
        assert "name_changed" in diff
        assert diff["name_changed"] is True
        assert "nodes_added" in diff
