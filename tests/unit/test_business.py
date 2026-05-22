import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.business.storage.sqlite_storage import BusinessStorage


@pytest.fixture
def storage(tmp_path):
    db_file = str(tmp_path / "test_business.db")
    return BusinessStorage(db_path=db_file)


class TestProcessCRUD:
    def test_create_process(self, storage):
        data = {"name": "proc1", "description": "Test process"}
        result = storage.create_process(data)
        assert result is not None
        assert result["name"] == "proc1"
        assert result["description"] == "Test process"
        assert result["status"] == "draft"
        assert "process_id" in result

    def test_create_process_with_id(self, storage):
        data = {"process_id": "custom-pid", "name": "proc_custom"}
        result = storage.create_process(data)
        assert result["process_id"] == "custom-pid"

    def test_get_process(self, storage):
        data = {"name": "proc_get"}
        created = storage.create_process(data)
        result = storage.get_process(created["process_id"])
        assert result is not None
        assert result["name"] == "proc_get"

    def test_get_process_nonexistent(self, storage):
        result = storage.get_process("nonexistent")
        assert result is None

    def test_list_processes(self, storage):
        storage.create_process({"name": "p1"})
        storage.create_process({"name": "p2"})
        result = storage.list_processes()
        assert len(result) == 2

    def test_list_processes_with_ontology_filter(self, storage):
        storage.create_process({"name": "p1", "ontology_id": "ont1"})
        storage.create_process({"name": "p2", "ontology_id": "ont2"})
        result = storage.list_processes(ontology_id="ont1")
        assert len(result) == 1
        assert result[0]["name"] == "p1"

    def test_update_process(self, storage):
        created = storage.create_process({"name": "proc_upd"})
        result = storage.update_process(created["process_id"], {"name": "updated"})
        assert result is not None
        assert result["name"] == "updated"

    def test_update_process_nonexistent(self, storage):
        result = storage.update_process("nonexistent", {"name": "x"})
        assert result is None

    def test_delete_process(self, storage):
        created = storage.create_process({"name": "proc_del"})
        result = storage.delete_process(created["process_id"])
        assert result is True
        assert storage.get_process(created["process_id"]) is None

    def test_delete_process_nonexistent(self, storage):
        result = storage.delete_process("nonexistent")
        assert result is False


class TestRuleCRUD:
    def test_create_rule(self, storage):
        data = {"name": "rule1", "description": "Test rule"}
        result = storage.create_rule(data)
        assert result is not None
        assert result["name"] == "rule1"
        assert result["status"] == "draft"

    def test_get_rule(self, storage):
        created = storage.create_rule({"name": "rule_get"})
        result = storage.get_rule(created["rule_id"])
        assert result is not None
        assert result["name"] == "rule_get"

    def test_get_rule_nonexistent(self, storage):
        result = storage.get_rule("nonexistent")
        assert result is None

    def test_list_rules(self, storage):
        storage.create_rule({"name": "r1"})
        storage.create_rule({"name": "r2"})
        result = storage.list_rules()
        assert len(result) == 2

    def test_list_rules_with_version_filter(self, storage):
        storage.create_rule({"name": "r1", "version_id": "v1"})
        storage.create_rule({"name": "r2", "version_id": "v2"})
        result = storage.list_rules(version_id="v1")
        assert len(result) == 1

    def test_update_rule(self, storage):
        created = storage.create_rule({"name": "rule_upd"})
        result = storage.update_rule(created["rule_id"], {"name": "updated_rule"})
        assert result is not None
        assert result["name"] == "updated_rule"

    def test_update_rule_nonexistent(self, storage):
        result = storage.update_rule("nonexistent", {"name": "x"})
        assert result is None

    def test_delete_rule(self, storage):
        created = storage.create_rule({"name": "rule_del"})
        result = storage.delete_rule(created["rule_id"])
        assert result is True
        assert storage.get_rule(created["rule_id"]) is None

    def test_delete_rule_nonexistent(self, storage):
        result = storage.delete_rule("nonexistent")
        assert result is False

    def test_rule_conditions_parsed(self, storage):
        data = {"name": "cond_rule", "rule_conditions": [{"field": "status", "op": "eq", "value": "active"}]}
        created = storage.create_rule(data)
        result = storage.get_rule(created["rule_id"])
        assert isinstance(result["rule_conditions"], list)
        assert len(result["rule_conditions"]) == 1


class TestLogicCRUD:
    def test_create_logic(self, storage):
        data = {"name": "logic1", "logic_type": "filter", "logic_expression": "x > 0"}
        result = storage.create_logic(data)
        assert result is not None
        assert result["name"] == "logic1"
        assert result["logic_type"] == "filter"

    def test_get_logic(self, storage):
        created = storage.create_logic({"name": "logic_get"})
        result = storage.get_logic(created["logic_id"])
        assert result is not None
        assert result["name"] == "logic_get"

    def test_get_logic_nonexistent(self, storage):
        result = storage.get_logic("nonexistent")
        assert result is None

    def test_list_logics(self, storage):
        storage.create_logic({"name": "l1"})
        storage.create_logic({"name": "l2"})
        result = storage.list_logics()
        assert len(result) == 2

    def test_update_logic(self, storage):
        created = storage.create_logic({"name": "logic_upd"})
        result = storage.update_logic(created["logic_id"], {"name": "updated_logic"})
        assert result is not None
        assert result["name"] == "updated_logic"

    def test_update_logic_nonexistent(self, storage):
        result = storage.update_logic("nonexistent", {"name": "x"})
        assert result is None

    def test_delete_logic(self, storage):
        created = storage.create_logic({"name": "logic_del"})
        result = storage.delete_logic(created["logic_id"])
        assert result is True
        assert storage.get_logic(created["logic_id"]) is None

    def test_delete_logic_nonexistent(self, storage):
        result = storage.delete_logic("nonexistent")
        assert result is False


class TestIndicatorCRUD:
    def test_create_indicator(self, storage):
        data = {"name": "metric1", "indicator_type": "metric", "calculation_formula": "SUM(x)", "unit": "kg"}
        result = storage.create_indicator(data)
        assert result is not None
        assert result["name"] == "metric1"
        assert result["indicator_type"] == "metric"
        assert result["unit"] == "kg"

    def test_get_indicator(self, storage):
        created = storage.create_indicator({"name": "ind_get"})
        result = storage.get_indicator(created["indicator_id"])
        assert result is not None
        assert result["name"] == "ind_get"

    def test_get_indicator_nonexistent(self, storage):
        result = storage.get_indicator("nonexistent")
        assert result is None

    def test_list_indicators(self, storage):
        storage.create_indicator({"name": "i1"})
        storage.create_indicator({"name": "i2"})
        result = storage.list_indicators()
        assert len(result) == 2

    def test_update_indicator(self, storage):
        created = storage.create_indicator({"name": "ind_upd"})
        result = storage.update_indicator(created["indicator_id"], {"name": "updated_ind"})
        assert result is not None
        assert result["name"] == "updated_ind"

    def test_update_indicator_nonexistent(self, storage):
        result = storage.update_indicator("nonexistent", {"name": "x"})
        assert result is None

    def test_delete_indicator(self, storage):
        created = storage.create_indicator({"name": "ind_del"})
        result = storage.delete_indicator(created["indicator_id"])
        assert result is True
        assert storage.get_indicator(created["indicator_id"]) is None

    def test_delete_indicator_nonexistent(self, storage):
        result = storage.delete_indicator("nonexistent")
        assert result is False


class TestRelatedFieldsParsing:
    def test_related_objects_parsed_as_list(self, storage):
        data = {"name": "rel_proc", "related_objects": ["obj1", "obj2"]}
        created = storage.create_process(data)
        result = storage.get_process(created["process_id"])
        assert isinstance(result["related_objects"], list)
        assert len(result["related_objects"]) == 2

    def test_related_fields_default_empty_list(self, storage):
        created = storage.create_process({"name": "empty_rel"})
        result = storage.get_process(created["process_id"])
        assert result["related_processes"] == []
        assert result["related_rules"] == []
        assert result["related_logics"] == []
        assert result["related_indicators"] == []
