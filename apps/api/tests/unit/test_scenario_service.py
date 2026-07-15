"""ScenarioService 单元测试"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from odap.biz.platform.workspace.services.scenario_service import ScenarioService
from odap.biz.platform.workspace.storage.sqlite_storage import SQLiteStorage


class TestScenarioServiceCreate(unittest.TestCase):
    """场景创建测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_workspace.db"
        self.storage = SQLiteStorage(db_path=db_path)
        self.svc = ScenarioService()
        self.svc.storage = self.storage

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_create_scenario_basic(self):
        result = self.svc.create_scenario(
            workspace_id="ws-1",
            name="测试场景",
            description="描述",
        )
        self.assertEqual(result["name"], "测试场景")
        self.assertEqual(result["workspace_id"], "ws-1")
        self.assertEqual(result["status"], "draft")
        self.assertIn("scenario_id", result)

    def test_create_scenario_with_ontology(self):
        result = self.svc.create_scenario(
            workspace_id="ws-1",
            name="带本体场景",
            ontology_id="ont-123",
        )
        self.assertEqual(result["ontology_id"], "ont-123")
        self.assertIn("ont-123", result["ontology_ids"])

    def test_create_scenario_auto_generates_ontology_id(self):
        result = self.svc.create_scenario(
            workspace_id="ws-1",
            name="自动本体",
        )
        self.assertIsNotNone(result["ontology_id"])

    def test_create_scenario_with_tags(self):
        result = self.svc.create_scenario(
            workspace_id="ws-1",
            name="标签场景",
            tags=["tag1", "tag2"],
        )
        self.assertEqual(result["tags"], ["tag1", "tag2"])

    def test_create_scenario_default_counts(self):
        result = self.svc.create_scenario(
            workspace_id="ws-1",
            name="计数场景",
        )
        self.assertEqual(result["doc_count"], 0)
        self.assertEqual(result["event_count"], 0)
        self.assertEqual(result["entity_count"], 0)


class TestScenarioServiceCRUD(unittest.TestCase):
    """场景 CRUD 测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_workspace.db"
        self.storage = SQLiteStorage(db_path=db_path)
        self.svc = ScenarioService()
        self.svc.storage = self.storage
        self.scenario = self.svc.create_scenario(
            workspace_id="ws-1",
            name="测试场景",
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_get_scenario(self):
        result = self.svc.get_scenario(self.scenario["scenario_id"])
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "测试场景")

    def test_get_scenario_not_found(self):
        result = self.svc.get_scenario("nonexistent-id")
        self.assertIsNone(result)

    def test_list_scenarios_by_workspace(self):
        self.svc.create_scenario(workspace_id="ws-1", name="场景2")
        results = self.svc.get_scenarios_by_workspace("ws-1", page=1, page_size=10)
        self.assertGreaterEqual(len(results), 1)

    def test_update_scenario(self):
        updated = self.svc.update_scenario(
            self.scenario["scenario_id"],
            {"name": "更新名称", "description": "更新描述"},
        )
        self.assertEqual(updated["name"], "更新名称")

    def test_update_scenario_not_found(self):
        with self.assertRaises(ValueError):
            self.svc.update_scenario("nonexistent-id", {"name": "X"})

    def test_delete_scenario(self):
        result = self.svc.delete_scenario(self.scenario["scenario_id"])
        self.assertTrue(result)
        self.assertIsNone(self.svc.get_scenario(self.scenario["scenario_id"]))

    def test_delete_scenario_not_found(self):
        result = self.svc.delete_scenario("nonexistent-id")
        self.assertFalse(result)


class TestScenarioServiceBindOntology(unittest.TestCase):
    """场景绑定/解绑本体测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_workspace.db"
        self.storage = SQLiteStorage(db_path=db_path)
        self.svc = ScenarioService()
        self.svc.storage = self.storage
        self.scenario = self.svc.create_scenario(
            workspace_id="ws-1",
            name="绑定场景",
            ontology_id="ont-1",
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_bind_ontology(self):
        result = self.svc.bind_ontology(
            self.scenario["scenario_id"],
            "ont-2",
        )
        self.assertEqual(result["binding_status"], "active")

    def test_bind_ontology_scenario_not_found(self):
        result = self.svc.bind_ontology("nonexistent", "ont-2")
        self.assertEqual(result["status"], "error")

    def test_unbind_ontology(self):
        self.svc.bind_ontology(self.scenario["scenario_id"], "ont-2")
        result = self.svc.unbind_ontology(
            self.scenario["scenario_id"],
            "ont-2",
        )
        self.assertEqual(result["status"], "success")

    def test_unbind_ontology_not_bound(self):
        result = self.svc.unbind_ontology(
            self.scenario["scenario_id"],
            "ont-999",
        )
        self.assertEqual(result["status"], "error")

    def test_get_scenario_ontologies(self):
        result = self.svc.get_scenario_ontologies(self.scenario["scenario_id"])
        self.assertEqual(result["scenario_id"], self.scenario["scenario_id"])
        self.assertGreaterEqual(result["total"], 1)

    def test_get_scenario_ontologies_not_found(self):
        result = self.svc.get_scenario_ontologies("nonexistent")
        self.assertEqual(result["status"], "error")


class TestScenarioServiceExtractEntities(unittest.TestCase):
    """文本实体抽取测试"""

    def setUp(self):
        self.svc = ScenarioService()

    def test_extract_location(self):
        entities = self.svc._extract_entities_from_text("北京和上海是重要城市")
        loc_names = [e["name"] for e in entities if e["type"] == "Location"]
        self.assertIn("北京", loc_names)
        self.assertIn("上海", loc_names)

    def test_extract_organization(self):
        entities = self.svc._extract_entities_from_text("华为科技公司发布了新产品")
        org_names = [e["name"] for e in entities if e["type"] == "Organization"]
        self.assertTrue(any("公司" in n for n in org_names))

    def test_extract_no_entities(self):
        entities = self.svc._extract_entities_from_text("这是一段普通文本")
        self.assertEqual(len(entities), 0)

    def test_extract_deduplication(self):
        entities = self.svc._extract_entities_from_text("北京到北京的航班")
        loc_entities = [e for e in entities if e["type"] == "Location"]
        self.assertEqual(len(loc_entities), 1)


if __name__ == "__main__":
    unittest.main()
