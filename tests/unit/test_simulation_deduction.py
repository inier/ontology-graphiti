import pytest
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock


class TestSQLiteDeductionStorage:
    def _make_storage(self, tmp_path):
        from odap.biz.simulation.simulation_deduction.storage.sqlite_deduction_storage import SQLiteDeductionStorage
        db_path = str(tmp_path / "test_deduction.db")
        return SQLiteDeductionStorage(db_path=db_path)

    def _make_scenario(self, **overrides):
        defaults = {
            "scenario_id": "test-scenario-001",
            "name": "测试推演场景",
            "description": "测试描述",
            "source_recommendation_id": None,
            "source_analysis_id": None,
            "target_object_id": "unit-001",
            "target_object_type": "Unit",
            "baseline_metrics": {"combat_power": 0.8, "morale": 0.7},
            "available_conditions": [],
            "chains": [],
            "results": [],
            "status": "draft",
            "best_chain_id": None,
            "tags": ["test"],
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }
        defaults.update(overrides)
        return defaults

    def test_save_and_get(self, tmp_path):
        storage = self._make_storage(tmp_path)
        scenario = self._make_scenario()
        storage.save_scenario(scenario)
        result = storage.get_scenario("test-scenario-001")
        assert result is not None
        assert result["scenario_id"] == "test-scenario-001"
        assert result["name"] == "测试推演场景"
        assert result["baseline_metrics"]["combat_power"] == 0.8

    def test_get_not_found(self, tmp_path):
        storage = self._make_storage(tmp_path)
        result = storage.get_scenario("nonexistent")
        assert result is None

    def test_list_scenarios_pagination(self, tmp_path):
        storage = self._make_storage(tmp_path)
        for i in range(5):
            storage.save_scenario(self._make_scenario(
                scenario_id=f"scenario-{i}",
                name=f"场景 {i}",
            ))
        result = storage.list_scenarios(page=1, page_size=3)
        assert result["total"] == 5
        assert len(result["scenarios"]) == 3
        assert result["page"] == 1

    def test_list_scenarios_filter_status(self, tmp_path):
        storage = self._make_storage(tmp_path)
        storage.save_scenario(self._make_scenario(scenario_id="s1", status="draft"))
        storage.save_scenario(self._make_scenario(scenario_id="s2", status="completed"))
        result = storage.list_scenarios(filters={"status": "draft"})
        assert result["total"] == 1
        assert result["scenarios"][0]["scenario_id"] == "s1"

    def test_list_scenarios_filter_name(self, tmp_path):
        storage = self._make_storage(tmp_path)
        storage.save_scenario(self._make_scenario(scenario_id="s1", name="攻击推演"))
        storage.save_scenario(self._make_scenario(scenario_id="s2", name="防御推演"))
        result = storage.list_scenarios(filters={"name": "攻击"})
        assert result["total"] == 1

    def test_delete_scenario(self, tmp_path):
        storage = self._make_storage(tmp_path)
        storage.save_scenario(self._make_scenario())
        assert storage.delete_scenario("test-scenario-001") is True
        assert storage.get_scenario("test-scenario-001") is None

    def test_delete_not_found(self, tmp_path):
        storage = self._make_storage(tmp_path)
        assert storage.delete_scenario("nonexistent") is False

    def test_json_fields_serialization(self, tmp_path):
        storage = self._make_storage(tmp_path)
        scenario = self._make_scenario(
            chains=[{
                "chain_id": "chain-001",
                "name": "链路1",
                "description": "",
                "steps": [{"step_id": "step-001", "action_type_id": "attack", "target_object_id": "unit-001", "target_object_type": "Unit", "parameters": {"intensity": 0.8}}],
                "conditions": [],
                "status": "pending",
                "tags": [],
            }],
            results=[{
                "chain_id": "chain-001",
                "status": "completed",
                "metric_impacts": [{"metric_name": "combat_power", "before": 0.8, "after": 0.64, "delta": -0.2}],
                "risk_level": "high",
                "risk_score": 45.0,
                "rule_violations": [],
                "recommendation": "高风险",
                "confidence": 0.6,
                "projected_state": {},
            }],
        )
        storage.save_scenario(scenario)
        result = storage.get_scenario("test-scenario-001")
        assert len(result["chains"]) == 1
        assert result["chains"][0]["chain_id"] == "chain-001"
        assert len(result["results"]) == 1
        assert result["results"][0]["risk_level"] == "high"

    def test_upsert_scenario(self, tmp_path):
        storage = self._make_storage(tmp_path)
        storage.save_scenario(self._make_scenario(name="原始名称"))
        storage.save_scenario(self._make_scenario(name="更新名称"))
        result = storage.get_scenario("test-scenario-001")
        assert result["name"] == "更新名称"


class TestDeductionModels:
    def test_deduction_status_enum(self):
        from odap.biz.simulation.simulation_deduction.models.deduction import DeductionStatus
        assert DeductionStatus.DRAFT == "draft"
        assert DeductionStatus.COMPLETED == "completed"
        assert DeductionStatus.FAILED == "failed"

    def test_condition_type_enum(self):
        from odap.biz.simulation.simulation_deduction.models.deduction import ConditionType
        assert ConditionType.RULE_BASED == "rule_based"
        assert ConditionType.CONSTRAINT_BASED == "constraint_based"
        assert ConditionType.CUSTOM == "custom"

    def test_chain_status_enum(self):
        from odap.biz.simulation.simulation_deduction.models.deduction import ChainStatus
        assert ChainStatus.PENDING == "pending"
        assert ChainStatus.COMPLETED == "completed"

    def test_simulation_condition_defaults(self):
        from odap.biz.simulation.simulation_deduction.models.deduction import SimulationCondition
        cond = SimulationCondition(name="测试条件")
        assert cond.condition_type.value == "custom"
        assert cond.parameters == {}
        assert cond.allowed_values == []
        assert cond.is_active is True

    def test_execution_chain_container_fields(self):
        from odap.biz.simulation.simulation_deduction.models.deduction import ExecutionChain
        chain = ExecutionChain(name="测试链路")
        assert chain.steps == []
        assert chain.conditions == []
        assert chain.tags == []

    def test_deduction_scenario_full(self):
        from odap.biz.simulation.simulation_deduction.models.deduction import (
            DeductionScenario, ExecutionChain, ChainStep, SimulationCondition,
            DeductionStatus, ConditionType,
        )
        scenario = DeductionScenario(
            name="完整推演",
            description="测试完整场景",
            target_object_id="unit-001",
            target_object_type="Unit",
            baseline_metrics={"combat_power": 0.8},
            chains=[
                ExecutionChain(
                    name="攻击链路",
                    steps=[
                        ChainStep(action_type_id="attack", target_object_id="unit-001", target_object_type="Unit")
                    ],
                    conditions=[
                        SimulationCondition(name="火力约束", condition_type=ConditionType.CONSTRAINT_BASED)
                    ],
                )
            ],
        )
        assert scenario.status == DeductionStatus.DRAFT
        assert len(scenario.chains) == 1
        assert len(scenario.chains[0].steps) == 1
        assert scenario.chains[0].conditions[0].condition_type == ConditionType.CONSTRAINT_BASED

    def test_chain_result_risk_score(self):
        from odap.biz.simulation.simulation_deduction.models.deduction import ChainResult, ChainStatus
        result = ChainResult(chain_id="chain-001", risk_score=75.5, risk_level="high")
        assert result.status == ChainStatus.COMPLETED
        assert result.risk_score == 75.5


class TestDeductionService:
    def _make_service(self, tmp_path):
        from odap.biz.simulation.simulation_deduction.services.deduction_service import DeductionService
        from odap.biz.simulation.simulation_deduction.storage.sqlite_deduction_storage import SQLiteDeductionStorage
        service = DeductionService()
        db_path = str(tmp_path / "test_service.db")
        storage = SQLiteDeductionStorage(db_path=db_path)
        service._engine._storage = storage
        return service

    def test_create_scenario(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.create_scenario(
            name="测试场景", description="描述",
            target_object_id="unit-001", target_object_type="Unit"
        )
        assert "scenario_id" in result
        assert result["name"] == "测试场景"
        assert result["status"] == "configuring"

    def test_get_scenario(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_scenario(name="获取测试", description="测试")
        result = service.get_scenario(created["scenario_id"])
        assert result["scenario_id"] == created["scenario_id"]

    def test_get_scenario_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.get_scenario("nonexistent")
        assert result.get("status") == "error"

    def test_list_scenarios(self, tmp_path):
        service = self._make_service(tmp_path)
        service.create_scenario(name="场景1", description="测试1")
        service.create_scenario(name="场景2", description="测试2")
        result = service.list_scenarios()
        assert result["total"] >= 2

    def test_delete_scenario(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_scenario(name="删除测试", description="测试")
        result = service.delete_scenario(created["scenario_id"])
        assert result["status"] == "ok"

    def test_delete_scenario_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.delete_scenario("nonexistent")
        assert result.get("status") == "error"

    def test_add_execution_chain(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_scenario(name="链路测试", description="测试")
        result = service.add_execution_chain(
            scenario_id=created["scenario_id"],
            name="攻击链路",
            description="测试攻击",
            steps=[{"action_type_id": "attack", "target_object_id": "unit-001", "target_object_type": "Unit", "parameters": {}}],
        )
        assert "chain_id" in result
        assert result["name"] == "攻击链路"

    def test_delete_chain(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_scenario(name="删除链路测试", description="测试")
        chain = service.add_execution_chain(
            scenario_id=created["scenario_id"],
            name="待删除链路",
            description="",
            steps=[{"action_type_id": "attack", "target_object_id": "unit-001", "target_object_type": "Unit", "parameters": {}}],
        )
        chain_id = chain["chain_id"]
        result = service.delete_chain(created["scenario_id"], chain_id)
        assert result["status"] == "ok"
        assert result["chain_id"] == chain_id
        scenario = service.get_scenario(created["scenario_id"])
        chain_ids = [c["chain_id"] for c in scenario.get("chains", [])]
        assert chain_id not in chain_ids

    def test_delete_chain_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_scenario(name="删除链路测试", description="测试")
        result = service.delete_chain(created["scenario_id"], "nonexistent-chain")
        assert result.get("status") == "error"
        assert "Chain not found" in result.get("message", "")

    def test_delete_chain_scenario_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.delete_chain("nonexistent-scenario", "some-chain")
        assert result.get("status") == "error"
        assert "Scenario not found" in result.get("message", "")

    def test_delete_chain_clears_best_chain_id(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_scenario(name="最佳链路测试", description="测试")
        chain = service.add_execution_chain(
            scenario_id=created["scenario_id"],
            name="最佳链路",
            description="",
            steps=[],
        )
        chain_id = chain["chain_id"]
        from odap.biz.simulation.simulation_deduction.storage.sqlite_deduction_storage import SQLiteDeductionStorage
        data = service._engine._storage.get_scenario(created["scenario_id"])
        data["best_chain_id"] = chain_id
        service._engine._storage.save_scenario(data)
        service.delete_chain(created["scenario_id"], chain_id)
        scenario = service.get_scenario(created["scenario_id"])
        assert scenario.get("best_chain_id") is None

    def test_delete_chain_clears_results(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_scenario(name="结果清理测试", description="测试")
        chain = service.add_execution_chain(
            scenario_id=created["scenario_id"],
            name="链路",
            description="",
            steps=[],
        )
        chain_id = chain["chain_id"]
        from odap.biz.simulation.simulation_deduction.storage.sqlite_deduction_storage import SQLiteDeductionStorage
        data = service._engine._storage.get_scenario(created["scenario_id"])
        data["results"] = [{"chain_id": chain_id, "status": "completed"}]
        service._engine._storage.save_scenario(data)
        service.delete_chain(created["scenario_id"], chain_id)
        scenario = service.get_scenario(created["scenario_id"])
        result_chain_ids = [r["chain_id"] for r in scenario.get("results", [])]
        assert chain_id not in result_chain_ids

    def test_update_chain(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_scenario(name="更新链路测试", description="测试")
        chain = service.add_execution_chain(
            scenario_id=created["scenario_id"],
            name="原始链路",
            description="原始描述",
            steps=[{"action_type_id": "attack", "target_object_id": "unit-001", "target_object_type": "Unit", "parameters": {}}],
        )
        chain_id = chain["chain_id"]
        result = service.update_chain(
            scenario_id=created["scenario_id"],
            chain_id=chain_id,
            name="更新链路",
            description="更新描述",
        )
        assert result["name"] == "更新链路"
        assert result["description"] == "更新描述"
        assert result["status"] == "pending"

    def test_update_chain_with_steps(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_scenario(name="更新步骤测试", description="测试")
        chain = service.add_execution_chain(
            scenario_id=created["scenario_id"],
            name="链路",
            description="",
            steps=[{"action_type_id": "attack", "target_object_id": "unit-001", "target_object_type": "Unit", "parameters": {}}],
        )
        chain_id = chain["chain_id"]
        result = service.update_chain(
            scenario_id=created["scenario_id"],
            chain_id=chain_id,
            steps=[{"action_type_id": "defend", "target_object_id": "unit-002", "target_object_type": "Unit", "parameters": {}}],
        )
        assert len(result["steps"]) == 1
        assert result["steps"][0]["action_type_id"] == "defend"

    def test_update_chain_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_scenario(name="更新链路测试", description="测试")
        result = service.update_chain(
            scenario_id=created["scenario_id"],
            chain_id="nonexistent-chain",
            name="新名称",
        )
        assert result.get("status") == "error"
        assert "Chain not found" in result.get("message", "")

    def test_update_chain_scenario_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.update_chain(
            scenario_id="nonexistent-scenario",
            chain_id="some-chain",
            name="新名称",
        )
        assert result.get("status") == "error"
        assert "Scenario not found" in result.get("message", "")

    def test_update_condition(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_scenario(name="条件测试", description="测试")
        cond_result = service.add_execution_chain(
            scenario_id=created["scenario_id"],
            name="链路",
            description="",
            steps=[],
            conditions=[{"name": "火力约束", "condition_type": "constraint_based", "value": None}],
        )
        cond_id = None
        for cond in cond_result.get("conditions", []):
            cond_id = cond.get("condition_id")
            break
        if cond_id:
            result = service.update_condition(created["scenario_id"], cond_id, 0.5)
            assert result["status"] == "ok"
