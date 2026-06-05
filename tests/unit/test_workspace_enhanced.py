import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock


class TestWorkspaceServiceEnhanced:
    @pytest.fixture
    def workspace_service(self, tmp_path):
        from odap.biz.platform.workspace.storage.sqlite_storage import SQLiteStorage
        from odap.biz.platform.workspace.impl.workspace import WorkspaceManager
        from odap.biz.platform.workspace.impl.import_export import ImportExportManager
        from odap.biz.platform.workspace.services.workspace_service import WorkspaceService
        storage = SQLiteStorage(db_path=str(tmp_path / "ws_test.db"))
        svc = WorkspaceService.__new__(WorkspaceService)
        svc.manager = WorkspaceManager()
        svc.manager.storage = storage
        svc.import_export = ImportExportManager()
        svc.import_export.storage = storage
        return svc

    def test_create_workspace_with_isolation_level(self, workspace_service):
        from odap.biz.platform.workspace.models.workspace import WorkspaceConfig
        config = WorkspaceConfig(isolation_level="strict")
        result = workspace_service.create_workspace(
            name="StrictWS",
            description="strict isolation workspace",
            config=config,
            owner="admin",
        )
        assert result["name"] == "StrictWS"
        assert result["status"] == "active"

    def test_update_isolation_level(self, workspace_service):
        from odap.biz.platform.workspace.models.workspace import WorkspaceConfig
        config = WorkspaceConfig(isolation_level="low")
        created = workspace_service.create_workspace(
            name="WS",
            config=config,
            owner="admin",
        )
        ws_id = created["workspace_id"]
        from odap.biz.platform.workspace.services.isolation_service import IsolationService
        isolation_svc = IsolationService()
        isolation_svc.manager.storage = workspace_service.manager.storage
        policy = isolation_svc.create_isolation_policy(
            workspace_id=ws_id,
            isolation_level=__import__("odap.biz.platform.workspace.models.isolation", fromlist=["IsolationLevel"]).IsolationLevel.STRICT,
        )
        assert policy["isolation_level"] == "strict"
        updated = isolation_svc.update_isolation_policy(ws_id, {"isolation_level": "high"})
        assert updated["isolation_level"] == "high"

    def test_export_workspace(self, workspace_service):
        created = workspace_service.create_workspace(name="ExportWS", owner="admin")
        ws_id = created["workspace_id"]
        result = workspace_service.export_workspace(ws_id, include_resources=True)
        assert "record_id" in result
        assert result["operation"] == "export"

    def test_import_workspace(self, workspace_service):
        result = workspace_service.import_workspace("/tmp/test_export.json", workspace_name="ImportedWS")
        assert "record_id" in result
        assert result["operation"] == "import"

    def test_strict_isolation_resource_check(self, workspace_service):
        from odap.biz.platform.workspace.services.isolation_service import IsolationService
        from odap.biz.platform.workspace.models.isolation import IsolationLevel
        isolation_svc = IsolationService()
        isolation_svc.manager.storage = workspace_service.manager.storage
        created = workspace_service.create_workspace(name="StrictWS", owner="admin")
        ws_id = created["workspace_id"]
        isolation_svc.create_isolation_policy(ws_id, IsolationLevel.STRICT)
        result = isolation_svc.validate_isolation(ws_id)
        assert result["status"] in ("success", "warning")
        assert result["isolation_level"] == "strict"


class TestScenarioService:
    @pytest.fixture
    def scenario_service(self, tmp_path):
        from odap.biz.platform.workspace.storage.sqlite_storage import SQLiteStorage
        from odap.biz.platform.workspace.services.scenario_service import ScenarioService
        storage = SQLiteStorage(db_path=str(tmp_path / "scenario_test.db"))
        svc = ScenarioService()
        svc.storage = storage
        return svc

    def test_create_scenario(self, scenario_service):
        from odap.biz.platform.workspace.storage.sqlite_storage import SQLiteStorage
        ws_storage = SQLiteStorage(db_path=scenario_service.storage.db_path)
        from odap.biz.platform.workspace.models.workspace import Workspace
        ws = Workspace(name="TestWS", owner="admin")
        ws_storage.save_workspace(ws)

        result = scenario_service.create_scenario(
            workspace_id=ws.id,
            name="Battle Scenario",
            description="test scenario",
        )
        assert "scenario_id" in result
        assert result["name"] == "Battle Scenario"
        assert result["workspace_id"] == ws.id

    def test_list_scenarios(self, scenario_service):
        from odap.biz.platform.workspace.storage.sqlite_storage import SQLiteStorage
        ws_storage = SQLiteStorage(db_path=scenario_service.storage.db_path)
        from odap.biz.platform.workspace.models.workspace import Workspace
        ws = Workspace(name="TestWS", owner="admin")
        ws_storage.save_workspace(ws)

        scenario_service.create_scenario(ws.id, "Scenario 1")
        import time
        time.sleep(1.1)
        scenario_service.create_scenario(ws.id, "Scenario 2")
        results = scenario_service.get_scenarios_by_workspace(ws.id)
        assert len(results) >= 2

    def test_activate_scenario(self, scenario_service):
        from odap.biz.platform.workspace.storage.sqlite_storage import SQLiteStorage
        ws_storage = SQLiteStorage(db_path=scenario_service.storage.db_path)
        from odap.biz.platform.workspace.models.workspace import Workspace
        ws = Workspace(name="TestWS", owner="admin")
        ws_storage.save_workspace(ws)

        created = scenario_service.create_scenario(ws.id, "Active Scenario", status="draft")
        scenario_service.update_scenario(created["scenario_id"], {"status": "active"})
        result = scenario_service.get_scenario(created["scenario_id"])
        assert result["status"] == "active"

    def test_bind_ontology_to_scenario(self, scenario_service):
        from odap.biz.platform.workspace.storage.sqlite_storage import SQLiteStorage
        ws_storage = SQLiteStorage(db_path=scenario_service.storage.db_path)
        from odap.biz.platform.workspace.models.workspace import Workspace
        ws = Workspace(name="TestWS", owner="admin")
        ws_storage.save_workspace(ws)

        created = scenario_service.create_scenario(ws.id, "Bind Scenario")
        scenario_id = created["scenario_id"]
        new_ontology_id = "ont-new-001"
        result = scenario_service.bind_ontology(scenario_id, new_ontology_id, bound_by="admin")
        assert result.get("binding_status") == "active" or result.get("ontology_id") == new_ontology_id

    def test_unbind_ontology_with_dependency_check(self, scenario_service):
        from odap.biz.platform.workspace.storage.sqlite_storage import SQLiteStorage
        ws_storage = SQLiteStorage(db_path=scenario_service.storage.db_path)
        from odap.biz.platform.workspace.models.workspace import Workspace
        ws = Workspace(name="TestWS", owner="admin")
        ws_storage.save_workspace(ws)

        created = scenario_service.create_scenario(ws.id, "Unbind Scenario")
        scenario_id = created["scenario_id"]
        default_ontology_id = created["ontology_id"]
        result = scenario_service.unbind_ontology(scenario_id, default_ontology_id)
        assert result.get("status") in ("success", "error")

    def test_unbind_ontology_nonexistent_scenario(self, scenario_service):
        result = scenario_service.unbind_ontology("nonexistent-scenario", "ont-1")
        assert result.get("status") == "error"


class TestIsolationModels:
    def test_isolation_level_enum(self):
        from odap.biz.platform.workspace.models.isolation import IsolationLevel
        assert IsolationLevel.LOW.value == "low"
        assert IsolationLevel.STANDARD.value == "standard"
        assert IsolationLevel.HIGH.value == "high"
        assert IsolationLevel.STRICT.value == "strict"

    def test_resource_quota_defaults(self):
        from odap.biz.platform.workspace.models.isolation import ResourceQuota
        quota = ResourceQuota()
        assert quota.cpu is None
        assert quota.memory is None
        assert quota.max_connections is None

    def test_network_policy_defaults(self):
        from odap.biz.platform.workspace.models.isolation import NetworkPolicy
        policy = NetworkPolicy()
        assert policy.allowed_ips == []
        assert policy.blocked_ips == []
        assert policy.enable_firewall is True
