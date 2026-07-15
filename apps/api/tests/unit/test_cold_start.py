"""
ColdStart 单元测试 (T322, TDD)

按 AGENTS.md 规则 9 必测。
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from odap.biz.core.ontology.cold_start.impl import ColdStartBootstrap
from odap.biz.core.ontology.cold_start.models import Industry
from odap.biz.core.ontology.cold_start.models.template_loader import (
    list_industries,
    load_template,
)
from odap.biz.core.ontology.cold_start.services import ColdStartService


class TestTemplateLoader(unittest.TestCase):
    """模板加载器测试"""

    def test_list_industries_returns_three_industries(self):
        industries = list_industries()
        self.assertIn("finance", industries)
        self.assertIn("healthcare", industries)
        self.assertIn("manufacturing", industries)
        self.assertEqual(len(industries), 3)

    def test_load_finance_template(self):
        template = load_template(Industry.FINANCE)
        self.assertIsNotNone(template)
        self.assertEqual(template["industry"], "finance")
        self.assertIn("entity_types", template)
        self.assertGreater(len(template["entity_types"]), 0)

    def test_load_healthcare_template(self):
        template = load_template(Industry.HEALTHCARE)
        self.assertIsNotNone(template)
        self.assertEqual(template["industry"], "healthcare")
        entity_names = {et["name"] for et in template["entity_types"]}
        self.assertIn("Patient", entity_names)
        self.assertIn("Doctor", entity_names)

    def test_load_manufacturing_template(self):
        template = load_template(Industry.MANUFACTURING)
        self.assertIsNotNone(template)
        self.assertEqual(template["industry"], "manufacturing")
        entity_names = {et["name"] for et in template["entity_types"]}
        self.assertIn("Equipment", entity_names)
        self.assertIn("WorkOrder", entity_names)

    def test_load_unknown_industry_returns_none(self):
        template = load_template("nonexistent_industry")
        self.assertIsNone(template)

    def test_load_template_via_string(self):
        template = load_template("finance")
        self.assertIsNotNone(template)
        self.assertEqual(template["industry"], "finance")

    def test_template_has_relationships(self):
        template = load_template(Industry.FINANCE)
        self.assertIn("relationships", template)
        self.assertGreater(len(template["relationships"]), 0)

    def test_template_has_sample_data(self):
        template = load_template(Industry.HEALTHCARE)
        self.assertIn("sample_data", template)
        self.assertGreater(len(template["sample_data"]), 0)


class TestColdStartBootstrap(unittest.TestCase):
    """冷启动引导测试"""

    def test_bootstrap_loads_finance_template(self):
        bootstrap = ColdStartBootstrap()
        report = bootstrap.bootstrap("ws-1", Industry.FINANCE)
        self.assertEqual(report.workspace_id, "ws-1")
        self.assertEqual(report.industry, Industry.FINANCE)
        self.assertEqual(report.template_name, "finance_template")
        self.assertGreater(report.entity_type_count, 0)
        self.assertGreater(report.sample_data_count, 0)

    def test_bootstrap_uses_injected_loader(self):
        mock_loader = MagicMock(return_value=4)
        bootstrap = ColdStartBootstrap(ontology_loader=mock_loader)
        report = bootstrap.bootstrap("ws-2", Industry.HEALTHCARE)
        mock_loader.assert_called_once()
        self.assertEqual(report.notes, "Loaded 4 entity types from template 'healthcare_template'")

    def test_bootstrap_raises_on_unknown_industry(self):
        bootstrap = ColdStartBootstrap()
        with self.assertRaises(ValueError) as ctx:
            bootstrap.bootstrap("ws-3", "unknown_industry")
        self.assertIn("Industry template not found", str(ctx.exception))

    def test_bootstrap_handles_loader_exception(self):
        mock_loader = MagicMock(side_effect=RuntimeError("DB error"))
        bootstrap = ColdStartBootstrap(ontology_loader=mock_loader)
        report = bootstrap.bootstrap("ws-4", Industry.MANUFACTURING)
        # 即使 loader 失败，bootstrap 也不抛出，返回 entity_type_count = 0 (loader 异常计数)
        self.assertEqual(report.notes, "Loaded 0 entity types from template 'manufacturing_template'")

    def test_bootstrap_if_needed_loads_when_empty(self):
        bootstrap = ColdStartBootstrap()
        out = bootstrap.bootstrap_if_needed("ws-empty", Industry.FINANCE)
        self.assertEqual(out["status"], "success")
        self.assertEqual(out["industry"], "finance")
        self.assertGreater(out["entity_types_loaded"], 0)
        self.assertIn("loaded_at", out)

    def test_bootstrap_if_needed_error(self):
        bootstrap = ColdStartBootstrap()
        out = bootstrap.bootstrap_if_needed("ws-x", "nonexistent")
        self.assertEqual(out["status"], "error")
        self.assertIn("bootstrap failed", out["message"])

    def test_detect_empty_workspace(self):
        bootstrap = ColdStartBootstrap()
        out = bootstrap.detect_empty_workspace("ws-1")
        self.assertEqual(out["workspace_id"], "ws-1")
        self.assertTrue(out["is_empty"])


class TestColdStartService(unittest.TestCase):
    """服务层契约测试（AGENTS.md 规则 2）"""

    def setUp(self):
        self.svc = ColdStartService()

    def test_list_industries_returns_dict(self):
        out = self.svc.list_available_industries()
        self.assertIsInstance(out, dict)
        self.assertIn("industries", out)
        self.assertIn("count", out)
        self.assertEqual(out["count"], 3)

    def test_bootstrap_workspace_success(self):
        out = self.svc.bootstrap_workspace("ws-svc", "finance")
        self.assertEqual(out["status"], "success")
        self.assertEqual(out["industry"], "finance")
        self.assertEqual(out["template"], "finance_template")

    def test_bootstrap_workspace_unknown_industry(self):
        out = self.svc.bootstrap_workspace("ws-svc", "agriculture")
        self.assertEqual(out["status"], "error")
        self.assertIn("unknown industry", out["message"])


class TestColdStartSchemas(unittest.TestCase):
    """Pydantic 模型验证（规则 4、5）"""

    def test_industry_enum_str_compatible(self):
        self.assertEqual(Industry.FINANCE.value, "finance")
        self.assertEqual(Industry.FINANCE, "finance")

    def test_cold_start_report_default_factory(self):
        from odap.biz.core.ontology.cold_start.models import ColdStartReport
        report = ColdStartReport(
            workspace_id="ws",
            industry=Industry.FINANCE,
            template_name="x",
            template_version="1.0",
            entity_type_count=1,
            relationship_count=0,
            sample_data_count=0,
        )
        self.assertEqual(report.entity_types, [])
        self.assertTrue(len(report.id) > 0)
        self.assertIsNotNone(report.loaded_at)

    def test_cold_start_report_unique_id(self):
        from odap.biz.core.ontology.cold_start.models import ColdStartReport
        r1 = ColdStartReport(workspace_id="a", industry=Industry.FINANCE, template_name="t", template_version="1", entity_type_count=0, relationship_count=0, sample_data_count=0)
        r2 = ColdStartReport(workspace_id="a", industry=Industry.FINANCE, template_name="t", template_version="1", entity_type_count=0, relationship_count=0, sample_data_count=0)
        self.assertNotEqual(r1.id, r2.id)


if __name__ == "__main__":
    unittest.main()
