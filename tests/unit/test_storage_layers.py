import pytest
import sqlite3
import json
from datetime import datetime
from unittest.mock import MagicMock, patch


class TestWorkspaceSQLiteStorage:
    @pytest.fixture
    def storage(self, tmp_path):
        from odap.biz.workspace.storage.sqlite_storage import SQLiteStorage
        db_path = str(tmp_path / "workspace.db")
        return SQLiteStorage(db_path)

    def test_save_and_get_workspace(self, storage):
        from odap.biz.workspace.models.workspace import Workspace, WorkspaceStatus, WorkspaceType
        ws = Workspace(
            id="ws-test-001",
            name="测试空间",
            description="测试描述",
            type=WorkspaceType.DEFAULT,
            status=WorkspaceStatus.ACTIVE,
            owner="admin",
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        storage.save_workspace(ws)
        result = storage.get_workspace("ws-test-001")
        assert result is not None
        assert result.name == "测试空间"
        assert result.type == WorkspaceType.DEFAULT

    def test_list_workspaces(self, storage):
        from odap.biz.workspace.models.workspace import Workspace, WorkspaceStatus, WorkspaceType
        ws1 = Workspace(id="ws-1", name="空间1", type=WorkspaceType.DEFAULT, status=WorkspaceStatus.ACTIVE, owner="admin", created_at=datetime.utcnow().isoformat(), updated_at=datetime.utcnow().isoformat())
        ws2 = Workspace(id="ws-2", name="空间2", type=WorkspaceType.SHARED, status=WorkspaceStatus.ACTIVE, owner="admin", created_at=datetime.utcnow().isoformat(), updated_at=datetime.utcnow().isoformat())
        storage.save_workspace(ws1)
        storage.save_workspace(ws2)
        result = storage.list_workspaces()
        assert len(result) >= 2

    def test_update_workspace(self, storage):
        from odap.biz.workspace.models.workspace import Workspace, WorkspaceStatus, WorkspaceType
        ws = Workspace(id="ws-upd", name="更新前", type=WorkspaceType.DEFAULT, status=WorkspaceStatus.ACTIVE, owner="admin", created_at=datetime.utcnow().isoformat(), updated_at=datetime.utcnow().isoformat())
        storage.save_workspace(ws)
        ws.name = "更新后"
        storage.update_workspace(ws)
        result = storage.get_workspace("ws-upd")
        assert result is not None
        assert result.name == "更新后"

    def test_delete_workspace(self, storage):
        from odap.biz.workspace.models.workspace import Workspace, WorkspaceStatus, WorkspaceType
        ws = Workspace(id="ws-del", name="删除测试", type=WorkspaceType.DEFAULT, status=WorkspaceStatus.ACTIVE, owner="admin", created_at=datetime.utcnow().isoformat(), updated_at=datetime.utcnow().isoformat())
        storage.save_workspace(ws)
        storage.delete_workspace("ws-del")
        result = storage.get_workspace("ws-del")
        assert result is None

    def test_get_nonexistent_workspace(self, storage):
        result = storage.get_workspace("nonexistent-id")
        assert result is None

    def test_isolation_policy(self, storage):
        from odap.biz.workspace.models.workspace import Workspace, WorkspaceStatus, WorkspaceType
        ws = Workspace(id="ws-iso", name="隔离空间", type=WorkspaceType.PRIVATE, status=WorkspaceStatus.ACTIVE, owner="admin", created_at=datetime.utcnow().isoformat(), updated_at=datetime.utcnow().isoformat())
        storage.save_workspace(ws)
        policy = {"workspace_id": "ws-iso", "isolation_level": "strict", "resource_quota": {}, "network_policy": {}}
        storage.save_isolation_policy(policy)
        result = storage.get_isolation_policy("ws-iso")
        assert result is not None
        assert result["isolation_level"] == "strict"


class TestBusinessSQLiteStorage:
    @pytest.fixture
    def storage(self, tmp_path):
        from odap.biz.business.storage.sqlite_storage import BusinessStorage
        db_path = str(tmp_path / "business.db")
        return BusinessStorage(db_path)

    def test_create_process(self, storage):
        p = storage.create_process({"name": "测试流程", "display_name": "测试", "description": "描述"})
        assert p is not None
        assert p["name"] == "测试流程"
        assert p["status"] == "draft"

    def test_list_processes(self, storage):
        storage.create_process({"name": "流程1"})
        storage.create_process({"name": "流程2"})
        result = storage.list_processes()
        assert len(result) >= 2

    def test_update_process(self, storage):
        created = storage.create_process({"name": "更新前"})
        pid = created["process_id"]
        updated = storage.update_process(pid, {"name": "更新后"})
        assert updated is not None
        assert updated["name"] == "更新后"

    def test_delete_process(self, storage):
        created = storage.create_process({"name": "删除测试"})
        pid = created["process_id"]
        result = storage.delete_process(pid)
        assert result is True

    def test_create_rule(self, storage):
        r = storage.create_rule({"name": "测试规则", "description": "规则描述"})
        assert r is not None
        assert r["name"] == "测试规则"

    def test_create_logic(self, storage):
        l = storage.create_logic({"name": "测试逻辑", "logic_type": "filter"})
        assert l is not None
        assert l["logic_type"] == "filter"

    def test_create_indicator(self, storage):
        i = storage.create_indicator({"name": "测试指标", "indicator_type": "metric", "unit": "个"})
        assert i is not None
        assert i["indicator_type"] == "metric"
        assert i["unit"] == "个"


class TestAuditSQLiteChannel:
    @pytest.fixture
    def channel(self, tmp_path):
        from odap.infra.security.audit_sqlite_channel import SQLiteAuditChannel
        db_path = str(tmp_path / "audit.db")
        ch = SQLiteAuditChannel(db_path)
        return ch

    @pytest.mark.asyncio
    async def test_write_event(self, channel):
        from odap.infra.security.audit_models import AuditEvent, AuditSeverity, AuditEventType, ActorInfo, ResourceInfo, ActionResult
        event = AuditEvent(
            event_type=AuditEventType.USER_LOGIN,
            severity=AuditSeverity.INFO,
            actor=ActorInfo(actor_type="user", actor_id="user-001", actor_name="测试用户"),
            action="login",
            resource=ResourceInfo(resource_type="system", resource_id="auth", resource_name="认证"),
            result=ActionResult(status="success", message="登录成功"),
            workspace_id="default",
        )
        await channel.write(event)

    @pytest.mark.asyncio
    async def test_query_events(self, channel):
        from odap.infra.security.audit_models import AuditEvent, AuditSeverity, AuditEventType, ActorInfo, ResourceInfo, ActionResult, AuditFilter
        event = AuditEvent(
            event_type=AuditEventType.DATA_INGEST,
            severity=AuditSeverity.INFO,
            actor=ActorInfo(actor_type="system", actor_id="system", actor_name="系统"),
            action="ingest",
            resource=ResourceInfo(resource_type="ontology", resource_id="doc-001", resource_name="文档"),
            result=ActionResult(status="success", message="摄入成功"),
            workspace_id="default",
        )
        await channel.write(event)
        await channel.flush()
        audit_filter = AuditFilter(workspace_id="default")
        results = await channel.query(audit_filter)
        assert len(results) >= 1
