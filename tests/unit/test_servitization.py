import pytest
import os
import json
from datetime import datetime


def _make_storage(tmp_path, storage_cls):
    db_path = str(tmp_path / "test.db")
    return storage_cls(db_path=db_path)


def _make_template(**overrides):
    defaults = {
        "name": "TestTemplate",
        "description": "A test template",
        "service_type": "skill",
        "object_type": "Unit",
        "function_mappings": [{"action": "query", "method": "get"}],
        "parameter_schema": {"type": "object", "properties": {"id": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
        "code_template": "class TestSkill:\n    pass",
    }
    defaults.update(overrides)
    return defaults


def _make_service(**overrides):
    defaults = {
        "name": "TestService",
        "description": "A test service",
        "service_type": "skill",
        "source_ontology_id": "ont-001",
        "source_object_type": "Unit",
        "source_function_ids": ["func-001"],
        "template_id": None,
        "code": "class TestSkill:\n    pass",
        "parameter_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "endpoint_path": None,
        "status": "pending",
        "version": 1,
    }
    defaults.update(overrides)
    return defaults


class TestSQLiteServitizationStorage:
    def test_init_db(self, tmp_path):
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        assert os.path.exists(storage.db_path)

    def test_template_crud(self, tmp_path):
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        template = _make_template(template_id="tpl-test-001")
        saved = storage.save_template(template)
        assert saved["template_id"] == "tpl-test-001"

        fetched = storage.get_template("tpl-test-001")
        assert fetched is not None
        assert fetched["name"] == "TestTemplate"
        assert fetched["service_type"] == "skill"
        assert len(fetched["function_mappings"]) == 1

        templates = storage.list_templates()
        assert len(templates) >= 1

        templates_filtered = storage.list_templates(service_type="skill")
        assert len(templates_filtered) >= 1

        assert storage.delete_template("tpl-test-001") is True
        assert storage.delete_template("tpl-test-001") is False
        assert storage.get_template("tpl-test-001") is None

    def test_service_crud(self, tmp_path):
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        service = _make_service(service_id="svc-test-001")
        saved = storage.save_service(service)
        assert saved["service_id"] == "svc-test-001"

        fetched = storage.get_service("svc-test-001")
        assert fetched is not None
        assert fetched["name"] == "TestService"
        assert fetched["status"] == "pending"

        services = storage.list_services()
        assert len(services) >= 1

        services_filtered = storage.list_services(service_type="skill")
        assert len(services_filtered) >= 1

        assert storage.update_service_status("svc-test-001", "completed") is True
        updated = storage.get_service("svc-test-001")
        assert updated["status"] == "completed"

        assert storage.delete_service("svc-test-001") is True
        assert storage.delete_service("svc-test-001") is False
        assert storage.get_service("svc-test-001") is None

    def test_deployment_crud(self, tmp_path):
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        deployment = {
            "deployment_id": "dpl-test-001",
            "service_id": "svc-test-001",
            "endpoint_url": "http://localhost:8000/api/test",
            "deployed_at": datetime.now().isoformat(),
            "is_active": True,
            "health_status": "healthy",
            "last_health_check": None,
        }
        saved = storage.save_deployment(deployment)
        assert saved["deployment_id"] == "dpl-test-001"

        fetched = storage.get_deployment("dpl-test-001")
        assert fetched is not None
        assert fetched["endpoint_url"] == "http://localhost:8000/api/test"
        assert fetched["is_active"] is True

        by_service = storage.get_deployment_by_service("svc-test-001")
        assert by_service is not None

        assert storage.get_deployment_by_service("nonexistent") is None

        assert storage.update_deployment_status("dpl-test-001", is_active=False, health_status="stopped") is True
        updated = storage.get_deployment("dpl-test-001")
        assert updated["is_active"] is False
        assert updated["health_status"] == "stopped"

        assert storage.delete_deployment("dpl-test-001") is True
        assert storage.delete_deployment("dpl-test-001") is False

    def test_json_fields_serialization(self, tmp_path):
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        template = _make_template(
            template_id="tpl-json-001",
            function_mappings=[{"action": "query"}, {"action": "mutate"}],
            parameter_schema={"type": "object", "properties": {"a": {"type": "integer"}}},
            output_schema={"type": "array"},
        )
        storage.save_template(template)
        fetched = storage.get_template("tpl-json-001")
        assert len(fetched["function_mappings"]) == 2
        assert fetched["parameter_schema"]["type"] == "object"
        assert fetched["output_schema"]["type"] == "array"

    def test_get_nonexistent(self, tmp_path):
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        assert storage.get_template("nonexistent") is None
        assert storage.get_service("nonexistent") is None
        assert storage.get_deployment("nonexistent") is None


class TestServitizationModels:
    def test_service_type_enum(self):
        from odap.biz.core.ontology.servitization.models import ServiceType
        assert ServiceType.SKILL.value == "skill"
        assert ServiceType.MCP_TOOL.value == "mcp_tool"
        assert ServiceType.REST_API.value == "rest_api"
        assert ServiceType.GRAPHQL.value == "graphql"

    def test_generation_status_enum(self):
        from odap.biz.core.ontology.servitization.models import GenerationStatus
        assert GenerationStatus.PENDING.value == "pending"
        assert GenerationStatus.GENERATING.value == "generating"
        assert GenerationStatus.COMPLETED.value == "completed"
        assert GenerationStatus.FAILED.value == "failed"
        assert GenerationStatus.DEPLOYED.value == "deployed"

    def test_skill_template_defaults(self):
        from odap.biz.core.ontology.servitization.models import SkillTemplate, ServiceType
        tpl = SkillTemplate(name="test")
        assert tpl.name == "test"
        assert tpl.service_type == ServiceType.SKILL
        assert tpl.function_mappings == []
        assert tpl.parameter_schema == {}
        assert tpl.output_schema == {}
        assert tpl.template_id.startswith("tpl-")

    def test_generated_service_defaults(self):
        from odap.biz.core.ontology.servitization.models import GeneratedService, GenerationStatus
        svc = GeneratedService(name="test")
        assert svc.name == "test"
        assert svc.status == GenerationStatus.PENDING
        assert svc.version == 1
        assert svc.source_function_ids == []
        assert svc.service_id.startswith("svc-")

    def test_service_deployment_defaults(self):
        from odap.biz.core.ontology.servitization.models import ServiceDeployment
        dpl = ServiceDeployment(service_id="svc-001", endpoint_url="http://test")
        assert dpl.is_active is True
        assert dpl.health_status == "unknown"
        assert dpl.last_health_check is None
        assert dpl.deployment_id.startswith("dpl-")

    def test_enum_str_inheritance(self):
        from odap.biz.core.ontology.servitization.models import ServiceType, GenerationStatus
        assert isinstance(ServiceType.SKILL, str)
        assert isinstance(GenerationStatus.PENDING, str)


class TestKnowledgeServitizationEngine:
    def test_create_template(self, tmp_path):
        from odap.biz.core.ontology.servitization.impl.servitization_engine import KnowledgeServitizationEngine
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        engine = KnowledgeServitizationEngine(storage)

        result = engine.create_template(_make_template())
        assert "template_id" in result
        assert result["service_type"] == "skill"

    def test_list_templates(self, tmp_path):
        from odap.biz.core.ontology.servitization.impl.servitization_engine import KnowledgeServitizationEngine
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        engine = KnowledgeServitizationEngine(storage)

        engine.create_template(_make_template(name="T1"))
        engine.create_template(_make_template(name="T2", service_type="mcp_tool"))

        all_templates = engine.list_templates()
        assert len(all_templates) == 2

        skill_templates = engine.list_templates(service_type="skill")
        assert len(skill_templates) == 1

    def test_generate_service(self, tmp_path):
        from odap.biz.core.ontology.servitization.impl.servitization_engine import KnowledgeServitizationEngine
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        engine = KnowledgeServitizationEngine(storage)

        tpl = engine.create_template(_make_template(code_template="class {{name}}Skill: pass"))
        result = engine.generate_service(tpl["template_id"], {"name": "MyService", "source_ontology_id": "ont-001"})
        assert result["name"] == "MyService"
        assert result["status"] == "completed"
        assert result["source_ontology_id"] == "ont-001"
        assert "MyService" in result["code"]

    def test_generate_service_template_not_found(self, tmp_path):
        from odap.biz.core.ontology.servitization.impl.servitization_engine import KnowledgeServitizationEngine
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        engine = KnowledgeServitizationEngine(storage)

        with pytest.raises(ValueError, match="not found"):
            engine.generate_service("nonexistent", {})

    def test_deploy_and_undeploy(self, tmp_path):
        from odap.biz.core.ontology.servitization.impl.servitization_engine import KnowledgeServitizationEngine
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        engine = KnowledgeServitizationEngine(storage)

        tpl = engine.create_template(_make_template())
        svc = engine.generate_service(tpl["template_id"], {"name": "DeployTest"})

        deploy_result = engine.deploy_service(svc["service_id"])
        assert "deployment_id" in deploy_result
        assert deploy_result["health_status"] == "healthy"

        svc_after = engine.get_service(svc["service_id"])
        assert svc_after["status"] == "deployed"

        undeploy_result = engine.undeploy_service(svc["service_id"])
        assert undeploy_result["status"] == "undeployed"

    def test_deploy_already_deployed(self, tmp_path):
        from odap.biz.core.ontology.servitization.impl.servitization_engine import KnowledgeServitizationEngine
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        engine = KnowledgeServitizationEngine(storage)

        tpl = engine.create_template(_make_template())
        svc = engine.generate_service(tpl["template_id"], {"name": "DoubleDeploy"})
        engine.deploy_service(svc["service_id"])

        result = engine.deploy_service(svc["service_id"])
        assert result["status"] == "error"

    def test_deploy_nonexistent(self, tmp_path):
        from odap.biz.core.ontology.servitization.impl.servitization_engine import KnowledgeServitizationEngine
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        engine = KnowledgeServitizationEngine(storage)

        with pytest.raises(ValueError, match="not found"):
            engine.deploy_service("nonexistent")

    def test_undeploy_no_deployment(self, tmp_path):
        from odap.biz.core.ontology.servitization.impl.servitization_engine import KnowledgeServitizationEngine
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        engine = KnowledgeServitizationEngine(storage)

        with pytest.raises(ValueError, match="No active deployment"):
            engine.undeploy_service("nonexistent")

    def test_get_and_list_services(self, tmp_path):
        from odap.biz.core.ontology.servitization.impl.servitization_engine import KnowledgeServitizationEngine
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        engine = KnowledgeServitizationEngine(storage)

        tpl = engine.create_template(_make_template())
        svc1 = engine.generate_service(tpl["template_id"], {"name": "Svc1"})
        svc2 = engine.generate_service(tpl["template_id"], {"name": "Svc2"})

        fetched = engine.get_service(svc1["service_id"])
        assert fetched["name"] == "Svc1"

        all_services = engine.list_services()
        assert len(all_services) == 2

        assert engine.get_service("nonexistent") is None


class TestKnowledgeServitizationService:
    def test_create_template(self, tmp_path):
        from odap.biz.core.ontology.servitization.services.servitization_service import KnowledgeServitizationService
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        service = KnowledgeServitizationService(storage=storage)

        result = service.create_template(_make_template())
        assert "template_id" in result

    def test_list_templates(self, tmp_path):
        from odap.biz.core.ontology.servitization.services.servitization_service import KnowledgeServitizationService
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        service = KnowledgeServitizationService(storage=storage)

        service.create_template(_make_template(name="T1"))
        result = service.list_templates()
        assert result["count"] >= 1
        assert "templates" in result

    def test_generate_service_error(self, tmp_path):
        from odap.biz.core.ontology.servitization.services.servitization_service import KnowledgeServitizationService
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        service = KnowledgeServitizationService(storage=storage)

        result = service.generate_service("nonexistent", {})
        assert result["status"] == "error"

    def test_get_service_not_found(self, tmp_path):
        from odap.biz.core.ontology.servitization.services.servitization_service import KnowledgeServitizationService
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        service = KnowledgeServitizationService(storage=storage)

        result = service.get_service("nonexistent")
        assert result["status"] == "error"

    def test_list_services(self, tmp_path):
        from odap.biz.core.ontology.servitization.services.servitization_service import KnowledgeServitizationService
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        service = KnowledgeServitizationService(storage=storage)

        result = service.list_services()
        assert "services" in result
        assert "count" in result

    def test_deploy_service_error(self, tmp_path):
        from odap.biz.core.ontology.servitization.services.servitization_service import KnowledgeServitizationService
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        service = KnowledgeServitizationService(storage=storage)

        result = service.deploy_service("nonexistent")
        assert result["status"] == "error"

    def test_undeploy_service_error(self, tmp_path):
        from odap.biz.core.ontology.servitization.services.servitization_service import KnowledgeServitizationService
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        service = KnowledgeServitizationService(storage=storage)

        result = service.undeploy_service("nonexistent")
        assert result["status"] == "error"

    def test_full_workflow(self, tmp_path):
        from odap.biz.core.ontology.servitization.services.servitization_service import KnowledgeServitizationService
        from odap.biz.core.ontology.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
        storage = _make_storage(tmp_path, SQLiteServitizationStorage)
        service = KnowledgeServitizationService(storage=storage)

        tpl_result = service.create_template(_make_template(code_template="class {{name}}Skill: pass"))
        assert "template_id" in tpl_result

        svc_result = service.generate_service(
            tpl_result["template_id"],
            {"name": "WorkflowService", "source_ontology_id": "ont-001"}
        )
        assert svc_result["status"] == "completed"

        deploy_result = service.deploy_service(svc_result["service_id"])
        assert "deployment_id" in deploy_result

        fetched = service.get_service(svc_result["service_id"])
        assert fetched["status"] == "deployed"

        undeploy_result = service.undeploy_service(svc_result["service_id"])
        assert undeploy_result["status"] == "undeployed"

    def test_singleton(self, tmp_path):
        from odap.biz.core.ontology.servitization.services.servitization_service import KnowledgeServitizationService
        KnowledgeServitizationService._instance = None
        from odap.biz.core.ontology.servitization.services import get_servitization_service
        s1 = get_servitization_service()
        s2 = get_servitization_service()
        assert s1 is s2
        KnowledgeServitizationService._instance = None


class TestServitizationSchemas:
    def test_create_template_request(self):
        from odap.biz.core.ontology.servitization.api.schemas import CreateTemplateRequest
        req = CreateTemplateRequest(name="Test")
        assert req.name == "Test"
        assert req.service_type.value == "skill"

    def test_generate_service_request(self):
        from odap.biz.core.ontology.servitization.api.schemas import GenerateServiceRequest
        req = GenerateServiceRequest(template_id="tpl-001")
        assert req.template_id == "tpl-001"
        assert req.source_ontology_id == ""

    def test_deploy_service_request(self):
        from odap.biz.core.ontology.servitization.api.schemas import DeployServiceRequest
        req = DeployServiceRequest(service_id="svc-001")
        assert req.service_id == "svc-001"

    def test_generate_from_ontology_request(self):
        from odap.biz.core.ontology.servitization.api.schemas import GenerateFromOntologyRequest
        req = GenerateFromOntologyRequest(ontology_id="ont-001")
        assert req.ontology_id == "ont-001"
        assert req.service_type.value == "skill"
