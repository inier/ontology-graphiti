"""DeductionEngineImpl 单元测试"""

import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from odap.biz.simulation.simulation_deduction.impl.deduction_engine_impl import DeductionEngineImpl
from odap.biz.simulation.simulation_deduction.models.deduction import (
    DeductionStatus,
    ChainStatus,
    ConditionType,
)
from odap.biz.simulation.simulation_deduction.storage.sqlite_deduction_storage import SQLiteDeductionStorage


def _run(coro):
    """辅助: 在事件循环中运行异步协程"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestDeductionEngineCreateScenario(unittest.TestCase):
    """创建推演场景测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_deduction.db"
        self.storage = SQLiteDeductionStorage(db_path=db_path)
        self.engine = DeductionEngineImpl(storage=self.storage)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_create_scenario_basic(self):
        result = _run(self.engine.create_scenario(
            name="测试推演",
            description="测试描述",
        ))
        self.assertEqual(result["name"], "测试推演")
        self.assertEqual(result["status"], DeductionStatus.CONFIGURING.value)
        self.assertIn("scenario_id", result)

    def test_create_scenario_with_target(self):
        result = _run(self.engine.create_scenario(
            name="目标推演",
            description="带目标",
            target_object_id="obj-1",
            target_object_type="Unit",
        ))
        self.assertEqual(result["target_object_id"], "obj-1")
        self.assertEqual(result["target_object_type"], "Unit")

    def test_create_scenario_has_baseline(self):
        result = _run(self.engine.create_scenario(
            name="基线推演",
            description="测试",
            target_object_id="obj-1",
            target_object_type="Unit",
        ))
        self.assertIn("baseline_metrics", result)


class TestDeductionEngineGetScenario(unittest.TestCase):
    """获取推演场景测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_deduction.db"
        self.storage = SQLiteDeductionStorage(db_path=db_path)
        self.engine = DeductionEngineImpl(storage=self.storage)
        self.scenario = _run(self.engine.create_scenario(
            name="查询场景",
            description="测试",
        ))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_get_scenario(self):
        result = _run(self.engine.get_scenario(self.scenario["scenario_id"]))
        self.assertNotEqual(result.get("status"), "error")
        self.assertEqual(result["name"], "查询场景")

    def test_get_scenario_not_found(self):
        result = _run(self.engine.get_scenario("nonexistent"))
        self.assertEqual(result["status"], "error")


class TestDeductionEngineListScenarios(unittest.TestCase):
    """列出推演场景测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_deduction.db"
        self.storage = SQLiteDeductionStorage(db_path=db_path)
        self.engine = DeductionEngineImpl(storage=self.storage)
        _run(self.engine.create_scenario(name="场景1", description="d1"))
        _run(self.engine.create_scenario(name="场景2", description="d2"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_list_scenarios(self):
        result = _run(self.engine.list_scenarios())
        self.assertIn("scenarios", result)
        self.assertGreaterEqual(result["total"], 2)


class TestDeductionEngineDeleteScenario(unittest.TestCase):
    """删除推演场景测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_deduction.db"
        self.storage = SQLiteDeductionStorage(db_path=db_path)
        self.engine = DeductionEngineImpl(storage=self.storage)
        self.scenario = _run(self.engine.create_scenario(name="删除场景", description="d"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_delete_scenario(self):
        result = _run(self.engine.delete_scenario(self.scenario["scenario_id"]))
        self.assertEqual(result["status"], "ok")

    def test_delete_scenario_not_found(self):
        result = _run(self.engine.delete_scenario("nonexistent"))
        self.assertEqual(result["status"], "error")


class TestDeductionEngineExecutionChain(unittest.TestCase):
    """执行链管理测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_deduction.db"
        self.storage = SQLiteDeductionStorage(db_path=db_path)
        self.engine = DeductionEngineImpl(storage=self.storage)
        self.scenario = _run(self.engine.create_scenario(
            name="链测试", description="d",
        ))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_add_execution_chain(self):
        result = _run(self.engine.add_execution_chain(
            scenario_id=self.scenario["scenario_id"],
            name="测试链",
            description="链描述",
            steps=[{"action_type_id": "attack", "step_order": 0}],
        ))
        self.assertEqual(result["name"], "测试链")
        self.assertIn("chain_id", result)

    def test_add_chain_scenario_not_found(self):
        result = _run(self.engine.add_execution_chain(
            scenario_id="nonexistent",
            name="链",
            description="d",
            steps=[],
        ))
        self.assertEqual(result["status"], "error")

    def test_delete_chain(self):
        chain = _run(self.engine.add_execution_chain(
            scenario_id=self.scenario["scenario_id"],
            name="待删链",
            description="d",
            steps=[],
        ))
        result = _run(self.engine.delete_chain(
            self.scenario["scenario_id"],
            chain["chain_id"],
        ))
        self.assertEqual(result["status"], "ok")

    def test_delete_chain_not_found(self):
        result = _run(self.engine.delete_chain(
            self.scenario["scenario_id"],
            "nonexistent-chain",
        ))
        self.assertEqual(result["status"], "error")

    def test_update_chain(self):
        chain = _run(self.engine.add_execution_chain(
            scenario_id=self.scenario["scenario_id"],
            name="原名",
            description="d",
            steps=[],
        ))
        result = _run(self.engine.update_chain(
            self.scenario["scenario_id"],
            chain["chain_id"],
            name="新名称",
        ))
        self.assertEqual(result["name"], "新名称")


class TestDeductionEngineSimulateChain(unittest.TestCase):
    """链模拟测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_deduction.db"
        self.storage = SQLiteDeductionStorage(db_path=db_path)
        self.engine = DeductionEngineImpl(storage=self.storage)
        self.scenario = _run(self.engine.create_scenario(
            name="模拟测试", description="d",
            target_object_id="obj-1",
            target_object_type="Unit",
        ))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_simulate_chain_not_found(self):
        result = _run(self.engine.simulate_chain(
            self.scenario["scenario_id"],
            "nonexistent-chain",
        ))
        self.assertEqual(result["status"], "error")

    def test_simulate_chain_scenario_not_found(self):
        result = _run(self.engine.simulate_chain(
            "nonexistent",
            "chain-1",
        ))
        self.assertEqual(result["status"], "error")


class TestDeductionEngineRiskScore(unittest.TestCase):
    """风险评分计算测试"""

    def setUp(self):
        self.engine = DeductionEngineImpl(storage=MagicMock())

    def test_risk_score_no_impacts(self):
        score = self.engine._calculate_risk_score([], [])
        self.assertEqual(score, 0.0)

    def test_risk_score_negative_impact(self):
        impacts = [{"delta": -0.5}]
        score = self.engine._calculate_risk_score(impacts, [])
        self.assertGreater(score, 0)

    def test_risk_score_with_violations(self):
        violations = [{"severity": "critical"}]
        score = self.engine._calculate_risk_score([], violations)
        self.assertEqual(score, 30.0)

    def test_risk_score_capped_at_100(self):
        impacts = [{"delta": -10.0}] * 20
        score = self.engine._calculate_risk_score(impacts, [])
        self.assertEqual(score, 100.0)


class TestDeductionEngineRecommendation(unittest.TestCase):
    """推荐生成测试"""

    def setUp(self):
        self.engine = DeductionEngineImpl(storage=MagicMock())

    def test_low_risk_recommendation(self):
        rec = self.engine._generate_chain_recommendation([], [], "low")
        self.assertIn("低风险", rec)

    def test_high_risk_recommendation(self):
        rec = self.engine._generate_chain_recommendation([], [], "high")
        self.assertIn("高风险", rec)

    def test_critical_risk_recommendation(self):
        rec = self.engine._generate_chain_recommendation([], [], "critical")
        self.assertIn("极高风险", rec)

    def test_medium_risk_recommendation(self):
        rec = self.engine._generate_chain_recommendation([], [], "medium")
        self.assertIn("中等风险", rec)

    def test_recommendation_with_violations(self):
        violations = [{"severity": "warning"}]
        rec = self.engine._generate_chain_recommendation([], violations, "low")
        self.assertIn("1", rec)


if __name__ == "__main__":
    unittest.main()
