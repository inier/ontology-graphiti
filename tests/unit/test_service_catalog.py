import pytest
import os
import json
from datetime import datetime


def _make_storage(tmp_path, storage_cls):
    db_path = str(tmp_path / "test_catalog.db")
    return storage_cls(db_path=db_path)


def _make_catalog_entry(**overrides):
    now = datetime.now().isoformat()
    defaults = {
        "catalog_id": "cat-test001",
        "service_id": "svc-test001",
        "service_name": "TestService",
        "service_type": "skill",
        "source_ontology_id": "ont-001",
        "source_object_type": "Unit",
        "source_ontology_version": "v1",
        "current_version": 1,
        "status": "active",
        "capabilities": ["query", "mutate"],
        "endpoint_path": "/api/test",
        "description": "A test service",
        "registered_at": now,
        "last_updated_at": now,
        "metadata": {"env": "test"},
    }
    defaults.update(overrides)
    return defaults


class TestServiceCatalogStorage:
    def test_init_db(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        assert os.path.exists(storage.db_path)

    def test_register_and_get(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        entry = _make_catalog_entry()
        storage.register(entry)
        fetched = storage.get("cat-test001")
        assert fetched is not None
        assert fetched["service_name"] == "TestService"
        assert fetched["service_type"] == "skill"
        assert fetched["capabilities"] == ["query", "mutate"]
        assert fetched["metadata"] == {"env": "test"}

    def test_get_by_service_id(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        entry = _make_catalog_entry()
        storage.register(entry)
        fetched = storage.get_by_service_id("svc-test001")
        assert fetched is not None
        assert fetched["catalog_id"] == "cat-test001"

    def test_list_entries(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        storage.register(_make_catalog_entry(catalog_id="cat-1", service_id="svc-1", service_name="S1"))
        storage.register(_make_catalog_entry(catalog_id="cat-2", service_id="svc-2", service_name="S2", service_type="mcp_tool"))
        all_entries = storage.list_entries()
        assert len(all_entries) == 2
        skill_entries = storage.list_entries(service_type="skill")
        assert len(skill_entries) == 1
        assert skill_entries[0]["service_name"] == "S1"
        ont_entries = storage.list_entries(source_ontology_id="ont-001")
        assert len(ont_entries) == 2

    def test_update_status(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        storage.register(_make_catalog_entry())
        assert storage.update_status("cat-test001", "deprecated") is True
        fetched = storage.get("cat-test001")
        assert fetched["status"] == "deprecated"
        assert storage.update_status("nonexistent", "active") is False

    def test_delete(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        storage.register(_make_catalog_entry())
        assert storage.delete("cat-test001") is True
        assert storage.get("cat-test001") is None
        assert storage.delete("cat-test001") is False

    def test_version_links(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        storage.register(_make_catalog_entry())
        link_data = {
            "link_id": "vl-test001",
            "catalog_id": "cat-test001",
            "ontology_version_id": "ont-v2",
            "service_version": 2,
            "is_compatible": False,
            "notes": "Version changed",
            "created_at": datetime.now().isoformat(),
        }
        storage.add_version_link(link_data)
        links = storage.get_version_links("cat-test001")
        assert len(links) == 1
        assert links[0]["ontology_version_id"] == "ont-v2"
        assert links[0]["is_compatible"] is False

    def test_get_services_by_ontology_version(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        storage.register(_make_catalog_entry())
        storage.add_version_link({
            "link_id": "vl-001", "catalog_id": "cat-test001",
            "ontology_version_id": "ont-v2", "service_version": 1,
            "is_compatible": True, "notes": "", "created_at": datetime.now().isoformat(),
        })
        services = storage.get_services_by_ontology_version("ont-v2")
        assert len(services) == 1
        assert services[0]["catalog_id"] == "cat-test001"

    def test_get_nonexistent(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        assert storage.get("nonexistent") is None
        assert storage.get_by_service_id("nonexistent") is None

    def test_json_fields_serialization(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        entry = _make_catalog_entry(
            catalog_id="cat-json",
            capabilities=["read", "write", "delete"],
            metadata={"key1": "val1", "nested": {"a": 1}},
        )
        storage.register(entry)
        fetched = storage.get("cat-json")
        assert len(fetched["capabilities"]) == 3
        assert fetched["metadata"]["nested"]["a"] == 1


class TestServiceCatalogService:
    def test_register_service(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService, ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        service = ServiceCatalogService(storage=storage)
        result = service.register_service(
            service_id="svc-001", service_name="MyService", service_type="skill",
            source_ontology_id="ont-001", source_ontology_version="v1",
            capabilities=["query"],
        )
        assert result["status"] == "success"
        assert result["catalog_id"].startswith("cat-")

    def test_register_duplicate(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService, ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        service = ServiceCatalogService(storage=storage)
        service.register_service(service_id="svc-dup", service_name="Dup", service_type="skill")
        result = service.register_service(service_id="svc-dup", service_name="Dup2", service_type="skill")
        assert result["status"] == "success"
        assert "already registered" in result["message"]

    def test_get_entry(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService, ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        service = ServiceCatalogService(storage=storage)
        reg = service.register_service(service_id="svc-get", service_name="GetSvc", service_type="skill")
        result = service.get_entry(reg["catalog_id"])
        assert result["status"] == "success"
        assert result["service_name"] == "GetSvc"
        assert result["entry_status"] == "active"

    def test_get_entry_not_found(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService, ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        service = ServiceCatalogService(storage=storage)
        result = service.get_entry("nonexistent")
        assert result["status"] == "error"

    def test_list_services(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService, ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        service = ServiceCatalogService(storage=storage)
        service.register_service(service_id="svc-l1", service_name="L1", service_type="skill")
        service.register_service(service_id="svc-l2", service_name="L2", service_type="mcp_tool")
        result = service.list_services()
        assert result["count"] == 2
        result_filtered = service.list_services(service_type="skill")
        assert result_filtered["count"] == 1

    def test_discover_services(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService, ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        service = ServiceCatalogService(storage=storage)
        service.register_service(
            service_id="svc-d1", service_name="DiscSvc", service_type="skill",
            source_object_type="Unit", capabilities=["query"],
        )
        result = service.discover_services(object_type="Unit")
        assert result["count"] == 1
        result_cap = service.discover_services(capability="query")
        assert result_cap["count"] == 1
        result_none = service.discover_services(object_type="NonExistent")
        assert result_none["count"] == 0

    def test_deprecate_and_retire(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService, ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        service = ServiceCatalogService(storage=storage)
        reg = service.register_service(service_id="svc-dep", service_name="DepSvc", service_type="skill")
        result = service.deprecate_service(reg["catalog_id"])
        assert result["new_status"] == "deprecated"
        result = service.retire_service(reg["catalog_id"])
        assert result["new_status"] == "retired"

    def test_deprecate_not_found(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService, ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        service = ServiceCatalogService(storage=storage)
        result = service.deprecate_service("nonexistent")
        assert result["status"] == "error"

    def test_delete_entry(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService, ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        service = ServiceCatalogService(storage=storage)
        reg = service.register_service(service_id="svc-del", service_name="DelSvc", service_type="skill")
        result = service.delete_entry(reg["catalog_id"])
        assert result["status"] == "success"
        result = service.delete_entry(reg["catalog_id"])
        assert result["status"] == "error"

    def test_on_ontology_version_changed(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService, ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        service = ServiceCatalogService(storage=storage)
        service.register_service(
            service_id="svc-v1", service_name="VSvc1", service_type="skill",
            source_ontology_id="ont-vchange",
        )
        service.register_service(
            service_id="svc-v2", service_name="VSvc2", service_type="skill",
            source_ontology_id="ont-vchange",
        )
        result = service.on_ontology_version_changed("ont-vchange", "ont-vchange-v2")
        assert result["services_flagged"] == 2
        assert len(result["catalog_ids"]) == 2
        entry1 = service.get_entry(result["catalog_ids"][0])
        assert entry1["entry_status"] == "needs_update"

    def test_get_version_links(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService, ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        service = ServiceCatalogService(storage=storage)
        reg = service.register_service(
            service_id="svc-vl", service_name="VLSvc", service_type="skill",
            source_ontology_id="ont-vl", source_ontology_version="v1",
        )
        result = service.get_version_links(reg["catalog_id"])
        assert result["status"] == "success"
        assert len(result["links"]) == 1
        assert result["links"][0]["is_compatible"] is True

    def test_health_check(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService, ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        service = ServiceCatalogService(storage=storage)
        reg = service.register_service(service_id="svc-hc", service_name="HCSvc", service_type="skill")
        result = service.health_check(reg["catalog_id"])
        assert result["service_status"] == "active"
        result = service.health_check("nonexistent")
        assert result["status"] == "error"

    def test_auto_link_version(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService, ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        service = ServiceCatalogService(storage=storage)
        reg = service.register_service(
            service_id="svc-al", service_name="ALSvc", service_type="skill",
            source_ontology_id="ont-al", source_ontology_version="v1",
        )
        links = service.get_version_links(reg["catalog_id"])
        assert len(links["links"]) == 1
        assert links["links"][0]["notes"] == "Auto-linked on registration"

    def test_auto_link_version_skipped(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService, ServiceCatalogStorage
        storage = _make_storage(tmp_path, ServiceCatalogStorage)
        service = ServiceCatalogService(storage=storage)
        reg = service.register_service(
            service_id="svc-nov", service_name="NoVSvc", service_type="skill",
            source_ontology_id="ont-nov",
        )
        links = service.get_version_links(reg["catalog_id"])
        assert len(links["links"]) == 0

    def test_singleton(self, tmp_path):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService
        ServiceCatalogService._instance = None
        from odap.biz.core.ontology.servitization.catalog import get_service_catalog
        s1 = get_service_catalog()
        s2 = get_service_catalog()
        assert s1 is s2
        ServiceCatalogService._instance = None


class TestCatalogEntryStatus:
    def test_enum_values(self):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import CatalogEntryStatus
        assert CatalogEntryStatus.ACTIVE.value == "active"
        assert CatalogEntryStatus.DEPRECATED.value == "deprecated"
        assert CatalogEntryStatus.NEEDS_UPDATE.value == "needs_update"
        assert CatalogEntryStatus.RETIRED.value == "retired"

    def test_enum_str_inheritance(self):
        from odap.biz.core.ontology.servitization.catalog.service_catalog import CatalogEntryStatus
        assert isinstance(CatalogEntryStatus.ACTIVE, str)
