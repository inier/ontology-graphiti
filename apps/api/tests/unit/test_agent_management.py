import pytest
import json
import sqlite3


def _make_agent_data(**overrides):
    data = {
        "name": "test_agent",
        "display_name": "测试代理",
        "avatar": "https://example.com/avatar.png",
        "description": "测试描述",
        "main_object": "obj_001",
        "related_objects": ["obj_001", "obj_002"],
        "related_processes": ["proc_001"],
        "related_rules": ["rule_001"],
        "related_business_logic": ["bl_001"],
        "related_indicators": ["ind_001"],
        "related_skills": ["skill_001"],
        "related_knowledge_bases": ["kb_001"],
        "allowed_roles": ["role_admin", "role_viewer"],
        "created_by": "admin",
    }
    data.update(overrides)
    return data


class TestSQLiteAgentStorage:
    @pytest.fixture
    def storage(self, tmp_path):
        from odap.biz.management.agent_management.storage.sqlite_agent_storage import SQLiteAgentStorage
        db_path = str(tmp_path / "agents.db")
        return SQLiteAgentStorage(db_path)

    def test_create_agent(self, storage):
        data = _make_agent_data()
        result = storage.create_agent(data)
        assert result is not None
        assert result["name"] == "test_agent"
        assert result["display_name"] == "测试代理"
        assert result["agent_id"].startswith("agent_")
        assert result["created_at"] is not None
        assert result["updated_at"] is not None

    def test_get_agent(self, storage):
        data = _make_agent_data()
        created = storage.create_agent(data)
        result = storage.get_agent(created["agent_id"])
        assert result is not None
        assert result["agent_id"] == created["agent_id"]
        assert result["name"] == "test_agent"

    def test_get_agent_not_found(self, storage):
        result = storage.get_agent("nonexistent_id")
        assert result is None

    def test_list_agents(self, storage):
        storage.create_agent(_make_agent_data(name="agent_a"))
        storage.create_agent(_make_agent_data(name="agent_b"))
        results = storage.list_agents()
        assert len(results) == 2
        names = [r["name"] for r in results]
        assert "agent_a" in names
        assert "agent_b" in names

    def test_list_agents_filter_by_role_id(self, storage):
        storage.create_agent(_make_agent_data(name="with_role", allowed_roles=["role_admin", "role_viewer"]))
        storage.create_agent(_make_agent_data(name="no_role", allowed_roles=[]))
        storage.create_agent(_make_agent_data(name="other_role", allowed_roles=["role_other"]))
        results = storage.list_agents(role_id="role_admin")
        names = [r["name"] for r in results]
        assert "with_role" in names
        assert "no_role" in names
        assert "other_role" not in names

    def test_update_agent(self, storage):
        created = storage.create_agent(_make_agent_data())
        updated = storage.update_agent(created["agent_id"], {
            "name": "updated_name",
            "description": "更新后的描述",
            "related_objects": ["obj_003"],
        })
        assert updated is not None
        assert updated["name"] == "updated_name"
        assert updated["description"] == "更新后的描述"
        assert updated["related_objects"] == ["obj_003"]

    def test_update_agent_not_found(self, storage):
        result = storage.update_agent("nonexistent_id", {"name": "x"})
        assert result is None

    def test_delete_agent(self, storage):
        created = storage.create_agent(_make_agent_data())
        assert storage.delete_agent(created["agent_id"]) is True
        assert storage.get_agent(created["agent_id"]) is None

    def test_delete_agent_not_found(self, storage):
        assert storage.delete_agent("nonexistent_id") is False

    def test_json_fields_serialization(self, storage):
        data = _make_agent_data(
            related_objects=["obj_a", "obj_b"],
            related_processes=["proc_x"],
            related_rules=["rule_y"],
            related_business_logic=["bl_z"],
            related_indicators=["ind_w"],
            related_skills=["skill_m"],
            related_knowledge_bases=["kb_n"],
            allowed_roles=["role_1", "role_2"],
        )
        created = storage.create_agent(data)
        fetched = storage.get_agent(created["agent_id"])
        assert fetched["related_objects"] == ["obj_a", "obj_b"]
        assert fetched["related_processes"] == ["proc_x"]
        assert fetched["related_rules"] == ["rule_y"]
        assert fetched["related_business_logic"] == ["bl_z"]
        assert fetched["related_indicators"] == ["ind_w"]
        assert fetched["related_skills"] == ["skill_m"]
        assert fetched["related_knowledge_bases"] == ["kb_n"]
        assert fetched["allowed_roles"] == ["role_1", "role_2"]

    def test_row_to_dict_invalid_json_tolerance(self, storage):
        data = _make_agent_data()
        created = storage.create_agent(data)
        conn = storage._get_conn()
        try:
            conn.execute(
                "UPDATE agents SET related_objects = ? WHERE agent_id = ?",
                ("not-valid-json", created["agent_id"]),
            )
            conn.execute(
                "UPDATE agents SET allowed_roles = ? WHERE agent_id = ?",
                ("{broken", created["agent_id"]),
            )
            conn.commit()
        finally:
            conn.close()
        result = storage.get_agent(created["agent_id"])
        assert result["related_objects"] == []
        assert result["allowed_roles"] == []

    def test_update_agent_ignores_readonly_fields(self, storage):
        created = storage.create_agent(_make_agent_data())
        original_created_at = created["created_at"]
        original_created_by = created["created_by"]
        updated = storage.update_agent(created["agent_id"], {
            "agent_id": "hacked_id",
            "created_at": "2000-01-01",
            "created_by": "hacker",
            "name": "safe_update",
        })
        assert updated["agent_id"] == created["agent_id"]
        assert updated["created_at"] == original_created_at
        assert updated["created_by"] == original_created_by
        assert updated["name"] == "safe_update"

    def test_update_agent_updates_timestamp(self, storage):
        created = storage.create_agent(_make_agent_data())
        original_updated_at = created["updated_at"]
        updated = storage.update_agent(created["agent_id"], {"name": "new_name"})
        assert updated["updated_at"] != original_updated_at


class TestAgentSchemas:
    def test_agent_create_required_fields(self):
        from odap.biz.management.agent_management.api.schemas import AgentCreate
        with pytest.raises(Exception):
            AgentCreate()
        with pytest.raises(Exception):
            AgentCreate(name="only_name")
        with pytest.raises(Exception):
            AgentCreate(display_name="only_display")

    def test_agent_create_valid(self):
        from odap.biz.management.agent_management.api.schemas import AgentCreate
        agent = AgentCreate(name="test", display_name="测试")
        assert agent.name == "test"
        assert agent.display_name == "测试"
        assert agent.avatar == ""
        assert agent.description == ""
        assert agent.related_objects == []
        assert agent.allowed_roles == []

    def test_agent_create_name_too_long(self):
        from odap.biz.management.agent_management.api.schemas import AgentCreate
        with pytest.raises(Exception):
            AgentCreate(name="a" * 51, display_name="测试")

    def test_agent_create_name_empty(self):
        from odap.biz.management.agent_management.api.schemas import AgentCreate
        with pytest.raises(Exception):
            AgentCreate(name="", display_name="测试")

    def test_agent_create_display_name_empty(self):
        from odap.biz.management.agent_management.api.schemas import AgentCreate
        with pytest.raises(Exception):
            AgentCreate(name="test", display_name="")

    def test_agent_update_all_optional(self):
        from odap.biz.management.agent_management.api.schemas import AgentUpdate
        update = AgentUpdate()
        assert update.name is None
        assert update.display_name is None
        assert update.avatar is None
        assert update.description is None
        assert update.related_objects is None
        assert update.allowed_roles is None

    def test_agent_update_partial(self):
        from odap.biz.management.agent_management.api.schemas import AgentUpdate
        update = AgentUpdate(name="new_name")
        assert update.name == "new_name"
        assert update.display_name is None

    def test_agent_full_fields(self):
        from odap.biz.management.agent_management.api.schemas import Agent
        agent = Agent(
            agent_id="agent_abc123",
            name="test",
            display_name="测试",
            avatar="https://example.com/a.png",
            description="描述",
            main_object="obj_1",
            related_objects=["obj_1"],
            related_processes=["proc_1"],
            related_rules=["rule_1"],
            related_business_logic=["bl_1"],
            related_indicators=["ind_1"],
            related_skills=["skill_1"],
            related_knowledge_bases=["kb_1"],
            allowed_roles=["role_1"],
            created_by="admin",
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        )
        assert agent.agent_id == "agent_abc123"
        assert agent.name == "test"
        assert agent.display_name == "测试"
        assert agent.related_objects == ["obj_1"]
        assert agent.allowed_roles == ["role_1"]
