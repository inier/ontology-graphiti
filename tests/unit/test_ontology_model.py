import pytest
import json
from unittest.mock import patch, MagicMock


class TestSQLiteModelStorage:
    @pytest.fixture
    def storage(self, tmp_path):
        from odap.biz.core.ontology.design.model.storage.sqlite_model_storage import SQLiteModelStorage
        return SQLiteModelStorage(db_path=str(tmp_path / "model_test.db"))

    def test_save_and_get_entity_type(self, storage):
        data = {"type_id": "et-1", "name": "Unit", "description": "test"}
        storage.save_entity_type(data)
        result = storage.get_entity_type("et-1")
        assert result is not None
        assert result["type_id"] == "et-1"
        assert result["name"] == "Unit"

    def test_get_entity_type_not_found(self, storage):
        result = storage.get_entity_type("nonexistent")
        assert result is None

    def test_list_entity_types(self, storage):
        storage.save_entity_type({"type_id": "et-1", "name": "Unit"})
        storage.save_entity_type({"type_id": "et-2", "name": "Equipment"})
        results = storage.list_entity_types()
        assert len(results) == 2

    def test_list_entity_types_with_filter(self, storage):
        storage.save_entity_type({"type_id": "et-1", "name": "Unit", "classification_level": "S"})
        storage.save_entity_type({"type_id": "et-2", "name": "Equipment", "classification_level": "U"})
        results = storage.list_entity_types(filters={"classification_level": "S"})
        assert len(results) == 1
        assert results[0]["classification_level"] == "S"

    def test_delete_entity_type(self, storage):
        storage.save_entity_type({"type_id": "et-1", "name": "Unit"})
        deleted = storage.delete_entity_type("et-1")
        assert deleted is True
        assert storage.get_entity_type("et-1") is None

    def test_delete_entity_type_not_found(self, storage):
        deleted = storage.delete_entity_type("nonexistent")
        assert deleted is False

    def test_save_entity_type_with_properties(self, storage):
        data = {
            "type_id": "et-1",
            "name": "Unit",
            "properties": [{"name": "unit_id", "data_type": "string", "required": True}],
        }
        storage.save_entity_type(data)
        result = storage.get_entity_type("et-1")
        assert len(result["properties"]) == 1
        assert result["properties"][0]["name"] == "unit_id"

    def test_save_entity_type_with_primary_key(self, storage):
        data = {
            "type_id": "et-1",
            "name": "Unit",
            "primary_key": ["unit_id"],
        }
        storage.save_entity_type(data)
        result = storage.get_entity_type("et-1")
        assert result["primary_key"] == ["unit_id"]

    def test_save_entity_type_with_constraints(self, storage):
        data = {
            "type_id": "et-1",
            "name": "Unit",
            "constraints": [{"name": "c1", "constraint_type": "pattern", "expression": "^[A-Z]", "error_message": "Must start with uppercase"}],
        }
        storage.save_entity_type(data)
        result = storage.get_entity_type("et-1")
        assert len(result["constraints"]) == 1
        assert result["constraints"][0]["name"] == "c1"

    def test_save_and_get_instance(self, storage):
        data = {"instance_id": "inst-1", "type_id": "et-1", "properties": {"name": "Alpha"}}
        storage.save_instance(data)
        result = storage.get_instance("inst-1")
        assert result is not None
        assert result["instance_id"] == "inst-1"
        assert result["properties"]["name"] == "Alpha"

    def test_get_instance_not_found(self, storage):
        result = storage.get_instance("nonexistent")
        assert result is None

    def test_list_instances(self, storage):
        storage.save_instance({"instance_id": "inst-1", "type_id": "et-1"})
        storage.save_instance({"instance_id": "inst-2", "type_id": "et-1"})
        storage.save_instance({"instance_id": "inst-3", "type_id": "et-2"})
        results = storage.list_instances(type_id="et-1")
        assert len(results) == 2

    def test_update_instance(self, storage):
        storage.save_instance({"instance_id": "inst-1", "type_id": "et-1", "properties": {"name": "Old"}})
        storage.save_instance({"instance_id": "inst-1", "type_id": "et-1", "properties": {"name": "New"}})
        result = storage.get_instance("inst-1")
        assert result["properties"]["name"] == "New"

    def test_delete_instance(self, storage):
        storage.save_instance({"instance_id": "inst-1", "type_id": "et-1"})
        deleted = storage.delete_instance("inst-1")
        assert deleted is True
        assert storage.get_instance("inst-1") is None

    def test_batch_import_instances(self, storage):
        instances = [
            {"instance_id": f"inst-{i}", "type_id": "et-1", "properties": {"idx": i}}
            for i in range(5)
        ]
        result = storage.batch_import_instances(instances)
        assert result["success"] == 5
        assert result["failed"] == 0

    def test_batch_import_partial_failure(self, storage):
        instances = [
            {"instance_id": "inst-ok", "type_id": "et-1", "properties": {}},
            {"type_id": "et-1", "properties": {}},
        ]
        result = storage.batch_import_instances(instances)
        assert result["success"] >= 1

    def test_save_and_get_document(self, storage):
        data = {"id": "doc-1", "name": "TestDoc", "version": "1.0.0", "object_types": [{"name": "Unit"}]}
        storage.save_document(data)
        result = storage.get_document("doc-1")
        assert result is not None
        assert result["name"] == "TestDoc"
        assert len(result["object_types"]) == 1

    def test_get_document_not_found(self, storage):
        result = storage.get_document("nonexistent")
        assert result is None


class TestModelService:
    @pytest.fixture
    def service(self, tmp_path):
        from odap.biz.core.ontology.design.model.storage.sqlite_model_storage import SQLiteModelStorage
        from odap.biz.core.ontology.design.model.impl.model_repository_impl import ModelRepositoryImpl
        from odap.biz.core.ontology.design.model.services.model_service import ModelService
        ModelService._instance = None
        storage = SQLiteModelStorage(db_path=str(tmp_path / "model_svc_test.db"))
        repo = ModelRepositoryImpl(storage=storage)
        svc = ModelService(repository=repo)
        return svc

    def test_create_entity_type(self, service):
        result = service.create_entity_type({"name": "Unit"})
        assert "type_id" in result
        assert result["name"] == "Unit"

    def test_create_entity_type_no_name(self, service):
        result = service.create_entity_type({})
        assert result.get("status") == "error"

    def test_get_entity_type(self, service):
        created = service.create_entity_type({"name": "Unit"})
        result = service.get_entity_type(created["type_id"])
        assert result["name"] == "Unit"

    def test_get_entity_type_not_found(self, service):
        result = service.get_entity_type("nonexistent")
        assert result.get("status") == "error"

    def test_list_entity_types(self, service):
        service.create_entity_type({"name": "Unit"})
        service.create_entity_type({"name": "Equipment"})
        result = service.list_entity_types()
        assert len(result["entity_types"]) == 2

    def test_update_entity_type(self, service):
        created = service.create_entity_type({"name": "Unit"})
        result = service.update_entity_type(created["type_id"], {"description": "updated"})
        assert result["description"] == "updated"

    def test_update_entity_type_not_found(self, service):
        result = service.update_entity_type("nonexistent", {"name": "X"})
        assert result.get("status") == "error"

    def test_delete_entity_type(self, service):
        created = service.create_entity_type({"name": "Unit"})
        result = service.delete_entity_type(created["type_id"])
        assert result["status"] == "ok"

    def test_delete_entity_type_not_found(self, service):
        result = service.delete_entity_type("nonexistent")
        assert result.get("status") == "error"

    def test_create_instance(self, service):
        et = service.create_entity_type({"name": "Unit"})
        result = service.create_instance({"type_id": et["type_id"], "properties": {"name": "Alpha"}})
        assert "instance_id" in result

    def test_create_instance_no_type_id(self, service):
        result = service.create_instance({"properties": {}})
        assert result.get("status") == "error"

    def test_get_instance(self, service):
        et = service.create_entity_type({"name": "Unit"})
        created = service.create_instance({"type_id": et["type_id"], "properties": {"name": "Alpha"}})
        result = service.get_instance(created["instance_id"])
        assert result["properties"]["name"] == "Alpha"

    def test_validate_instance_required_fields(self, service):
        et = service.create_entity_type({
            "name": "Unit",
            "properties": [{"name": "unit_id", "required": True}],
        })
        result = service.validate_instance(et["type_id"], {})
        assert result.get("status") == "error"
        assert len(result.get("errors", [])) > 0

    def test_validate_instance_constraint_pattern(self, service):
        from odap.biz.core.ontology.design.engine.impl.validation_engine_impl import ValidationEngineImpl
        engine = ValidationEngineImpl()
        type_def = {
            "name": "Unit",
            "properties": [{"name": "code", "required": True}],
            "constraints": [{"name": "c1", "constraint_type": "pattern", "expression": "^[A-Z]", "error_message": "Must start uppercase"}],
        }
        result = engine.validate_instance(type_def, {"code": "abc"})
        assert "is_valid" in result

    def test_validate_instance_classification(self, service):
        et = service.create_entity_type({
            "name": "Unit",
            "classification_level": "S",
            "properties": [{"name": "unit_id", "required": True}],
        })
        result = service.validate_instance(et["type_id"], {"unit_id": "U-1"})
        assert result.get("status") == "ok"

    def test_create_document(self, service):
        result = service.create_document({"name": "TestOntology"})
        assert "id" in result
        assert result["name"] == "TestOntology"

    def test_export_document_to_palantir(self, service):
        created = service.create_document({
            "name": "TestOntology",
            "object_types": [{"name": "Unit"}],
            "action_types": [{"name": "deploy", "target_object_type": "Unit"}],
        })
        result = service.export_document(created["id"])
        assert "ontology" in result
        assert "objectTypes" in result["ontology"]
        assert "actionTypes" in result["ontology"]

    def test_export_document_not_found(self, service):
        result = service.export_document("nonexistent")
        assert result.get("status") == "error"


class TestOntologyDocumentModel:
    def test_to_palantir(self):
        from odap.biz.core.ontology.design.model.models.ontology_document import OntologyDocument, ActionTypeDefinition
        doc = OntologyDocument(
            id="doc-1",
            name="Test",
            object_types=[{"name": "Unit"}],
            action_types=[ActionTypeDefinition(name="deploy", target_object_type="Unit")],
        )
        result = doc.to_palantir()
        assert "ontology" in result
        assert len(result["ontology"]["objectTypes"]) == 1
        assert len(result["ontology"]["actionTypes"]) == 1

    def test_from_palantir(self):
        from odap.biz.core.ontology.design.model.models.ontology_document import OntologyDocument
        data = {
            "name": "Test",
            "ontology": {
                "objectTypes": [{"name": "Unit"}],
                "actionTypes": [{"name": "deploy", "target_object_type": "Unit"}],
            },
            "metadata": {"key": "val"},
        }
        doc = OntologyDocument.from_palantir(data)
        assert doc.name == "Test"
        assert len(doc.object_types) == 1
        assert len(doc.action_types) == 1
        assert doc.metadata["key"] == "val"

    def test_from_palantir_empty(self):
        from odap.biz.core.ontology.design.model.models.ontology_document import OntologyDocument
        doc = OntologyDocument.from_palantir({})
        assert doc.name == ""
        assert doc.object_types == []
        assert doc.action_types == []


class TestEntityTypeDefinition:
    def test_create_entity_type_definition(self):
        from odap.biz.core.ontology.design.model.models.entity_type import EntityTypeDefinition, PropertyDefinition
        et = EntityTypeDefinition(
            name="Unit",
            properties=[PropertyDefinition(name="unit_id", data_type="string", required=True)],
            primary_key=["unit_id"],
        )
        assert et.name == "Unit"
        assert len(et.properties) == 1
        assert et.primary_key == ["unit_id"]

    def test_default_values(self):
        from odap.biz.core.ontology.design.model.models.entity_type import EntityTypeDefinition
        et = EntityTypeDefinition(name="Unit")
        assert et.properties == []
        assert et.primary_key == []
        assert et.links == []
        assert et.constraints == []
        assert et.classification_level == "U"
