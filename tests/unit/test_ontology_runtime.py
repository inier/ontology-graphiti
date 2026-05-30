import pytest
import os
import json
from datetime import datetime


def _make_storage(tmp_path, storage_cls):
    db_path = str(tmp_path / "test.db")
    return storage_cls(db_path=db_path)


class TestSQLiteRuntimeStorage:
    def test_init_db(self, tmp_path):
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        assert os.path.exists(storage.db_path)

    def test_function_crud(self, tmp_path):
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        func = {
            "function_id": "func-test-001",
            "name": "CalculateRisk",
            "display_name": "风险计算",
            "description": "计算实体风险评分",
            "function_type": "transform",
            "status": "active",
            "target_object_type": "Unit",
            "input_schema": {"entity_id": "str"},
            "output_schema": {"risk_score": "float"},
            "implementation": "result = context.get('combat_power', 0) * 0.5",
            "implementation_type": "python",
            "dependencies": [],
            "bound_action_contract": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        saved = storage.save_function(func)
        assert saved["function_id"] == "func-test-001"

        fetched = storage.get_function("func-test-001")
        assert fetched is not None
        assert fetched["name"] == "CalculateRisk"
        assert fetched["function_type"] == "transform"

        functions = storage.list_functions(function_type="transform")
        assert len(functions) >= 1

        all_functions = storage.list_functions()
        assert len(all_functions) >= 1

        deleted = storage.delete_function("func-test-001")
        assert deleted is True

        deleted_again = storage.delete_function("func-test-001")
        assert deleted_again is False

        assert storage.get_function("func-test-001") is None

    def test_contract_crud(self, tmp_path):
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        contract = {
            "contract_id": "contract-test-001",
            "action_type_id": "attack",
            "action_name": "攻击",
            "description": "攻击行动契约",
            "read_set": [{"object_type": "Unit", "property_name": "combat_power"}],
            "write_set": [{"object_type": "Unit", "property_name": "combat_power"}],
            "side_effect_set": [{"object_type": "Unit", "property_name": "morale"}],
            "preconditions": ["combat_power > 0"],
            "postconditions": ["target.combat_power < before"],
            "is_verified": False,
            "verified_at": None,
            "created_at": datetime.now().isoformat(),
        }
        saved = storage.save_contract(contract)
        assert saved["contract_id"] == "contract-test-001"

        fetched = storage.get_contract("contract-test-001")
        assert fetched is not None
        assert fetched["action_type_id"] == "attack"
        assert len(fetched["write_set"]) == 1
        assert len(fetched["side_effect_set"]) == 1

        by_action = storage.get_contract_by_action("attack")
        assert by_action is not None
        assert by_action["contract_id"] == "contract-test-001"

        contracts = storage.list_contracts()
        assert len(contracts) >= 1

        assert storage.get_contract_by_action("nonexistent") is None
        assert storage.delete_contract("contract-test-001") is True
        assert storage.delete_contract("contract-test-001") is False

    def test_mutation_crud(self, tmp_path):
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        mutation = {
            "mutation_id": "mut-test-001",
            "action_type_id": "attack",
            "action_name": "攻击",
            "target_object_id": "unit-001",
            "target_object_type": "Unit",
            "property_name": "combat_power",
            "old_value": 0.8,
            "new_value": 0.5,
            "mutation_type": "update",
            "timestamp": datetime.now().isoformat(),
            "actor": "agent-001",
            "scenario_id": "sc-001",
        }
        saved = storage.save_mutation(mutation)
        assert saved["mutation_id"] == "mut-test-001"

        mutations = storage.query_mutations(target_object_id="unit-001")
        assert len(mutations) >= 1
        assert mutations[0]["property_name"] == "combat_power"

        mutations_by_action = storage.query_mutations(action_type_id="attack")
        assert len(mutations_by_action) >= 1

        empty = storage.query_mutations(target_object_id="nonexistent")
        assert len(empty) == 0

    def test_snapshot_crud(self, tmp_path):
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        snapshot = {
            "snapshot_id": "snap-test-001",
            "name": "基线快照",
            "description": "推演前基线",
            "object_states": {"Unit": {"count": 10}, "Location": {"count": 5}},
            "scenario_id": "sc-001",
            "is_baseline": True,
            "created_at": datetime.now().isoformat(),
        }
        saved = storage.save_snapshot(snapshot)
        assert saved["snapshot_id"] == "snap-test-001"

        fetched = storage.get_snapshot("snap-test-001")
        assert fetched is not None
        assert fetched["is_baseline"] is True
        assert "Unit" in fetched["object_states"]

        snapshots = storage.list_snapshots(scenario_id="sc-001")
        assert len(snapshots) >= 1

        assert storage.delete_snapshot("snap-test-001") is True
        assert storage.get_snapshot("snap-test-001") is None

    def test_aggregate_crud(self, tmp_path):
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        agg = {
            "agg_id": "agg-test-001",
            "name": "战斗力求和",
            "target_object_type": "Unit",
            "target_property": "combat_power",
            "method": "sum",
            "window": "raw",
            "group_by": [],
            "output_property": "total_combat_power",
            "is_active": True,
        }
        saved = storage.save_aggregate(agg)
        assert saved["agg_id"] == "agg-test-001"

        fetched = storage.get_aggregate("agg-test-001")
        assert fetched is not None
        assert fetched["method"] == "sum"

        aggs = storage.list_aggregates(target_object_type="Unit")
        assert len(aggs) >= 1

        assert storage.delete_aggregate("agg-test-001") is True
        assert storage.get_aggregate("agg-test-001") is None

    def test_propagation_graph_crud(self, tmp_path):
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        graph = {
            "graph_id": "spg-test-001",
            "name": "测试传播图",
            "description": "",
            "edges": [
                {"source_type": "Unit", "action_name": "attack", "target_type": "Unit", "propagation_type": "direct", "probability": 1.0},
            ],
            "object_types": ["Unit"],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        saved = storage.save_propagation_graph(graph)
        assert saved["graph_id"] == "spg-test-001"

        fetched = storage.get_propagation_graph("spg-test-001")
        assert fetched is not None
        assert len(fetched["edges"]) == 1

        assert storage.delete_propagation_graph("spg-test-001") is True


class TestFunctionEngine:
    def test_register_and_execute(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.function_engine import FunctionEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = FunctionEngine(storage)

        func = engine.register_function({
            "name": "DoubleValue",
            "target_object_type": "Unit",
            "function_type": "transform",
            "implementation": "result = context.get('value', 0) * 2",
        })
        assert "function_id" in func

        result = engine.execute_function(func["function_id"], {"value": 5})
        assert result["status"] == "success"
        assert result["result"] == 10

    def test_register_missing_name(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.function_engine import FunctionEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = FunctionEngine(storage)

        with pytest.raises(ValueError, match="name is required"):
            engine.register_function({"target_object_type": "Unit"})

    def test_execute_nonexistent(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.function_engine import FunctionEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = FunctionEngine(storage)

        result = engine.execute_function("nonexistent", {})
        assert result["status"] == "error"


class TestActionContractEngine:
    def test_create_and_verify(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.action_contract_engine import ActionContractEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = ActionContractEngine(storage)

        contract = engine.create_contract({
            "action_type_id": "move",
            "action_name": "移动",
            "write_set": [{"object_type": "Unit", "property_name": "location"}],
            "side_effect_set": [{"object_type": "Location", "property_name": "occupant_count"}],
        })
        assert "contract_id" in contract

        mutation_log = [
            {"mutation_id": "m1", "target_object_type": "Unit", "property_name": "location"},
            {"mutation_id": "m2", "target_object_type": "Location", "property_name": "occupant_count"},
        ]
        result = engine.verify_contract(contract["contract_id"], mutation_log)
        assert result["is_verified"] is True

    def test_verify_with_violation(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.action_contract_engine import ActionContractEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = ActionContractEngine(storage)

        contract = engine.create_contract({
            "action_type_id": "attack",
            "action_name": "攻击",
            "write_set": [{"object_type": "Unit", "property_name": "combat_power"}],
        })

        mutation_log = [
            {"mutation_id": "m1", "target_object_type": "Unit", "property_name": "combat_power"},
            {"mutation_id": "m2", "target_object_type": "Equipment", "property_name": "status"},
        ]
        result = engine.verify_contract(contract["contract_id"], mutation_log)
        assert result["is_verified"] is False
        assert len(result["violations"]) == 1

    def test_duplicate_contract(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.action_contract_engine import ActionContractEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = ActionContractEngine(storage)

        engine.create_contract({"action_type_id": "defend", "action_name": "防御"})
        with pytest.raises(ValueError, match="already exists"):
            engine.create_contract({"action_type_id": "defend", "action_name": "防御2"})


class TestAggregateEngine:
    def test_compute_sum(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.aggregate_engine import AggregateEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = AggregateEngine(storage)

        agg = engine.register_aggregate({
            "name": "总兵力",
            "target_object_type": "Unit",
            "target_property": "combat_power",
            "method": "sum",
        })
        result = engine.compute_aggregate(agg["agg_id"], [
            {"combat_power": 0.8}, {"combat_power": 0.6}, {"combat_power": 0.9},
        ])
        assert result["status"] == "success"
        assert abs(result["result"] - 2.3) < 0.01

    def test_compute_avg(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.aggregate_engine import AggregateEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = AggregateEngine(storage)

        agg = engine.register_aggregate({
            "name": "平均士气",
            "target_object_type": "Unit",
            "target_property": "morale",
            "method": "avg",
        })
        result = engine.compute_aggregate(agg["agg_id"], [
            {"morale": 0.8}, {"morale": 0.6},
        ])
        assert result["status"] == "success"
        assert abs(result["result"] - 0.7) < 0.01


class TestOntologyRuntimeService:
    def test_full_workflow(self, tmp_path):
        from odap.biz.core.ontology.runtime.services.runtime_service import OntologyRuntimeService
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        service = OntologyRuntimeService(storage=storage)

        func_result = service.register_function({
            "name": "CalcRisk",
            "target_object_type": "Unit",
            "function_type": "predict",
            "implementation": "result = 0.5",
        })
        assert "function_id" in func_result

        contract_result = service.create_contract({
            "action_type_id": "attack",
            "action_name": "攻击",
            "write_set": [{"object_type": "Unit", "property_name": "combat_power"}],
            "side_effect_set": [{"object_type": "Unit", "property_name": "morale"}],
        })
        assert "contract_id" in contract_result

        graph_result = service.build_propagation_graph()
        assert "graph_id" in graph_result

        impact_result = service.compute_impact(
            graph_result["graph_id"], "attack", "Unit"
        )
        assert impact_result["status"] == "success"

        mutation_result = service.record_mutation({
            "action_type_id": "attack",
            "action_name": "攻击",
            "target_object_id": "unit-001",
            "target_object_type": "Unit",
            "property_name": "combat_power",
            "old_value": 0.8,
            "new_value": 0.5,
        })
        assert "mutation_id" in mutation_result

        snap_result = service.capture_snapshot("测试快照")
        assert "snapshot_id" in snap_result

        agg_result = service.register_aggregate({
            "name": "总战力",
            "target_object_type": "Unit",
            "target_property": "combat_power",
            "method": "sum",
        })
        assert "agg_id" in agg_result

        compute_result = service.compute_aggregate(agg_result["agg_id"], [
            {"combat_power": 0.5}, {"combat_power": 0.8},
        ])
        assert compute_result["status"] == "success"
        assert abs(compute_result["result"] - 1.3) < 0.01


class TestHarnessService:
    def test_session_lifecycle(self, tmp_path):
        from odap.biz.core.ontology.harness.services.harness_service import HarnessService
        from odap.biz.core.ontology.harness.storage.sqlite_harness_storage import SQLiteHarnessStorage
        storage = _make_storage(tmp_path, SQLiteHarnessStorage)
        service = HarnessService(storage=storage)

        session = service.create_session("测试会话", "描述")
        assert "session_id" in session
        assert session["current_stage"] == "data_selection"
        session_id = session["session_id"]

        advanced = service.advance_stage(session_id, {"selected_sources": ["db1"]})
        assert advanced["current_stage"] == "data_processing"

        hitl = service.create_hitl_confirmation(
            session_id, "ontology_modeling", "high",
            "高风险操作", "删除实体类型", ["Unit"]
        )
        assert "confirmation_id" in hitl

        resolved = service.resolve_hitl(
            session_id, hitl["confirmation_id"], "approved", "admin"
        )
        assert resolved["status"] == "success"

        task = service.add_agent_task(
            session_id, "data_agent", "data_selection", "探索数据源"
        )
        assert "task_id" in task

        updated = service.update_agent_task(
            session_id, task["task_id"],
            output_data={"tables_found": 5},
            status="completed"
        )
        assert updated["status"] == "success"

    def test_blueprint(self, tmp_path):
        from odap.biz.core.ontology.harness.services.harness_service import HarnessService
        from odap.biz.core.ontology.harness.storage.sqlite_harness_storage import SQLiteHarnessStorage
        storage = _make_storage(tmp_path, SQLiteHarnessStorage)
        service = HarnessService(storage=storage)

        bp = service.create_blueprint("测试蓝图", "描述")
        assert "blueprint_id" in bp
        assert len(bp["nodes"]) == 6
        assert len(bp["edges"]) == 5

        fetched = service.get_blueprint(bp["blueprint_id"])
        assert fetched["name"] == "测试蓝图"

        updated = service.update_blueprint(bp["blueprint_id"], {"name": "更新蓝图"})
        assert updated["version"] == 2

    def test_hitl_check(self, tmp_path):
        from odap.biz.core.ontology.harness.services.harness_service import HarnessService
        from odap.biz.core.ontology.harness.storage.sqlite_harness_storage import SQLiteHarnessStorage
        storage = _make_storage(tmp_path, SQLiteHarnessStorage)
        service = HarnessService(storage=storage)

        high_risk = service.check_hitl_required("delete", ["Unit"])
        assert high_risk["hitl_required"] is True
        assert high_risk["risk_level"] == "high"

        low_risk = service.check_hitl_required("query", [])
        assert low_risk["hitl_required"] is False


class TestSQLiteRuntimeStorageTrigger:
    def test_trigger_crud(self, tmp_path):
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        trigger = {
            "trigger_id": "trig-test-001",
            "name": "高风险预警",
            "description": "战斗力低于阈值时触发",
            "conditions": [
                {
                    "condition_id": "cond-001",
                    "trigger_type": "state_driven",
                    "object_type": "Unit",
                    "property_name": "combat_power",
                    "operator": "lt",
                    "threshold_value": 0.3,
                    "threshold_max": None,
                    "description": "战斗力低于0.3",
                    "is_active": True,
                }
            ],
            "action_type_id": "alert",
            "action_name": "预警通知",
            "target_object_type": "Unit",
            "target_object_id": None,
            "parameters": {"level": "high"},
            "is_active": True,
            "priority": 10,
            "cooldown_seconds": 60,
            "last_fired_at": None,
            "fire_count": 0,
            "created_at": datetime.now().isoformat(),
        }
        saved = storage.save_trigger(trigger)
        assert saved["trigger_id"] == "trig-test-001"

        fetched = storage.get_trigger("trig-test-001")
        assert fetched is not None
        assert fetched["name"] == "高风险预警"
        assert len(fetched["conditions"]) == 1
        assert fetched["conditions"][0]["operator"] == "lt"

        triggers = storage.list_triggers(target_object_type="Unit")
        assert len(triggers) >= 1

        active_triggers = storage.list_triggers(is_active=True)
        assert len(active_triggers) >= 1

        assert storage.delete_trigger("trig-test-001") is True
        assert storage.delete_trigger("trig-test-001") is False
        assert storage.get_trigger("trig-test-001") is None

    def test_execution_crud(self, tmp_path):
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        execution = {
            "execution_id": "exec-test-001",
            "trigger_id": "trig-test-001",
            "action_type_id": "alert",
            "action_name": "预警通知",
            "triggered_by": {"object_id": "unit-001", "property": "combat_power", "value": 0.2},
            "target_object_id": "unit-001",
            "target_object_type": "Unit",
            "parameters": {"level": "high"},
            "status": "completed",
            "result": {"notified": True},
            "error": None,
            "started_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
        }
        saved = storage.save_execution(execution)
        assert saved["execution_id"] == "exec-test-001"

        executions = storage.query_executions(trigger_id="trig-test-001")
        assert len(executions) >= 1
        assert executions[0]["status"] == "completed"
        assert executions[0]["result"] == {"notified": True}

        all_executions = storage.query_executions()
        assert len(all_executions) >= 1

    def test_trigger_get_nonexistent(self, tmp_path):
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        assert storage.get_trigger("nonexistent") is None


class TestActionTriggerEngine:
    def test_register_and_get(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.action_trigger_engine import ActionTriggerEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = ActionTriggerEngine(storage)

        trigger = engine.register_trigger({
            "name": "低士气预警",
            "conditions": [
                {"trigger_type": "state_driven", "object_type": "Unit", "property_name": "morale", "operator": "lt", "threshold_value": 0.3}
            ],
            "action_type_id": "alert",
            "action_name": "士气预警",
            "target_object_type": "Unit",
        })
        assert "trigger_id" in trigger
        assert trigger["name"] == "低士气预警"

        fetched = engine.get_trigger(trigger["trigger_id"])
        assert fetched is not None
        assert fetched["action_type_id"] == "alert"

    def test_register_missing_name(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.action_trigger_engine import ActionTriggerEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = ActionTriggerEngine(storage)

        with pytest.raises(ValueError, match="name is required"):
            engine.register_trigger({
                "action_type_id": "alert",
                "target_object_type": "Unit",
            })

    def test_register_missing_action(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.action_trigger_engine import ActionTriggerEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = ActionTriggerEngine(storage)

        with pytest.raises(ValueError, match="action_type_id or action_name is required"):
            engine.register_trigger({
                "name": "无动作触发器",
                "target_object_type": "Unit",
            })

    def test_list_and_delete(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.action_trigger_engine import ActionTriggerEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = ActionTriggerEngine(storage)

        engine.register_trigger({
            "name": "触发器A",
            "action_name": "动作A",
            "target_object_type": "Unit",
        })
        engine.register_trigger({
            "name": "触发器B",
            "action_name": "动作B",
            "target_object_type": "Location",
        })

        all_triggers = engine.list_triggers()
        assert len(all_triggers) == 2

        unit_triggers = engine.list_triggers(target_object_type="Unit")
        assert len(unit_triggers) == 1
        assert unit_triggers[0]["name"] == "触发器A"

        assert engine.delete_trigger(all_triggers[0]["trigger_id"]) is True
        assert engine.delete_trigger("nonexistent") is False

    def test_evaluate_triggers_state_driven(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.action_trigger_engine import ActionTriggerEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = ActionTriggerEngine(storage)

        engine.register_trigger({
            "name": "低战斗力预警",
            "conditions": [
                {"trigger_type": "state_driven", "object_type": "Unit", "property_name": "combat_power", "operator": "lt", "threshold_value": 0.3}
            ],
            "action_type_id": "alert",
            "action_name": "战斗力预警",
            "target_object_type": "Unit",
            "priority": 5,
        })

        matched = engine.evaluate_triggers("Unit", "unit-001", {"combat_power": 0.2})
        assert len(matched) == 1
        assert matched[0]["name"] == "低战斗力预警"

        not_matched = engine.evaluate_triggers("Unit", "unit-002", {"combat_power": 0.8})
        assert len(not_matched) == 0

    def test_evaluate_triggers_multiple_operators(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.action_trigger_engine import ActionTriggerEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = ActionTriggerEngine(storage)

        engine.register_trigger({
            "name": "eq触发器",
            "conditions": [
                {"trigger_type": "state_driven", "object_type": "Unit", "property_name": "status", "operator": "eq", "threshold_value": "destroyed"}
            ],
            "action_type_id": "cleanup",
            "action_name": "清理",
            "target_object_type": "Unit",
        })
        engine.register_trigger({
            "name": "between触发器",
            "conditions": [
                {"trigger_type": "state_driven", "object_type": "Unit", "property_name": "combat_power", "operator": "between", "threshold_value": 0.3, "threshold_max": 0.7}
            ],
            "action_type_id": "monitor",
            "action_name": "监控",
            "target_object_type": "Unit",
        })
        engine.register_trigger({
            "name": "contains触发器",
            "conditions": [
                {"trigger_type": "state_driven", "object_type": "Unit", "property_name": "tags", "operator": "contains", "threshold_value": "critical"}
            ],
            "action_type_id": "tag_alert",
            "action_name": "标签预警",
            "target_object_type": "Unit",
        })

        eq_matched = engine.evaluate_triggers("Unit", "unit-001", {"status": "destroyed"})
        assert len(eq_matched) == 1
        assert eq_matched[0]["name"] == "eq触发器"

        between_matched = engine.evaluate_triggers("Unit", "unit-002", {"combat_power": 0.5})
        assert len(between_matched) == 1
        assert between_matched[0]["name"] == "between触发器"

        between_out = engine.evaluate_triggers("Unit", "unit-003", {"combat_power": 0.9})
        assert len(between_out) == 0

        contains_matched = engine.evaluate_triggers("Unit", "unit-004", {"tags": ["critical", "frontline"]})
        assert len(contains_matched) == 1
        assert contains_matched[0]["name"] == "contains触发器"

    def test_execute_trigger(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.action_trigger_engine import ActionTriggerEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = ActionTriggerEngine(storage)

        trigger = engine.register_trigger({
            "name": "执行测试触发器",
            "conditions": [
                {"trigger_type": "state_driven", "object_type": "Unit", "property_name": "health", "operator": "lt", "threshold_value": 0.1}
            ],
            "action_type_id": "respawn",
            "action_name": "重生",
            "target_object_type": "Unit",
        })

        result = engine.execute_trigger(trigger["trigger_id"], {"object_id": "unit-001", "health": 0.05})
        assert result["status"] == "completed"
        assert result["trigger_id"] == trigger["trigger_id"]

        fetched = engine.get_trigger(trigger["trigger_id"])
        assert fetched["fire_count"] == 1
        assert fetched["last_fired_at"] is not None

    def test_execute_nonexistent_trigger(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.action_trigger_engine import ActionTriggerEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = ActionTriggerEngine(storage)

        result = engine.execute_trigger("nonexistent", {})
        assert result["status"] == "error"

    def test_get_execution_history(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.action_trigger_engine import ActionTriggerEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = ActionTriggerEngine(storage)

        trigger = engine.register_trigger({
            "name": "历史测试触发器",
            "action_type_id": "log",
            "action_name": "记录日志",
            "target_object_type": "Unit",
        })

        engine.execute_trigger(trigger["trigger_id"], {"reason": "test1"})
        engine.execute_trigger(trigger["trigger_id"], {"reason": "test2"})

        history = engine.get_execution_history(trigger_id=trigger["trigger_id"])
        assert len(history) == 2

        all_history = engine.get_execution_history()
        assert len(all_history) >= 2

    def test_cooldown_prevents_firing(self, tmp_path):
        from odap.biz.core.ontology.runtime.impl.action_trigger_engine import ActionTriggerEngine
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        engine = ActionTriggerEngine(storage)

        trigger = engine.register_trigger({
            "name": "冷却测试触发器",
            "conditions": [
                {"trigger_type": "state_driven", "object_type": "Unit", "property_name": "heat", "operator": "gt", "threshold_value": 80}
            ],
            "action_type_id": "cool_down",
            "action_name": "冷却",
            "target_object_type": "Unit",
            "cooldown_seconds": 3600,
        })

        engine.execute_trigger(trigger["trigger_id"], {"heat": 90})

        matched = engine.evaluate_triggers("Unit", "unit-001", {"heat": 95})
        assert len(matched) == 0


class TestOntologyRuntimeServiceTrigger:
    def test_trigger_workflow(self, tmp_path):
        from odap.biz.core.ontology.runtime.services.runtime_service import OntologyRuntimeService
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        service = OntologyRuntimeService(storage=storage)

        trigger = service.register_trigger({
            "name": "服务层触发器",
            "conditions": [
                {"trigger_type": "state_driven", "object_type": "Unit", "property_name": "combat_power", "operator": "lt", "threshold_value": 0.5}
            ],
            "action_type_id": "reinforce",
            "action_name": "增援",
            "target_object_type": "Unit",
        })
        assert "trigger_id" in trigger

        fetched = service.get_trigger(trigger["trigger_id"])
        assert fetched["name"] == "服务层触发器"

        listed = service.list_triggers()
        assert listed["count"] >= 1

        eval_result = service.evaluate_triggers("Unit", "unit-001", {"combat_power": 0.3})
        assert eval_result["count"] == 1

        exec_result = service.execute_trigger(trigger["trigger_id"], {"object_id": "unit-001"})
        assert exec_result["status"] == "completed"

        history = service.get_trigger_history(trigger_id=trigger["trigger_id"])
        assert history["count"] >= 1

        delete_result = service.delete_trigger(trigger["trigger_id"])
        assert delete_result["status"] == "success"

        not_found = service.get_trigger(trigger["trigger_id"])
        assert not_found["status"] == "error"

    def test_trigger_not_found(self, tmp_path):
        from odap.biz.core.ontology.runtime.services.runtime_service import OntologyRuntimeService
        from odap.biz.core.ontology.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
        storage = _make_storage(tmp_path, SQLiteRuntimeStorage)
        service = OntologyRuntimeService(storage=storage)

        result = service.get_trigger("nonexistent")
        assert result["status"] == "error"

        result = service.delete_trigger("nonexistent")
        assert result["status"] == "error"
