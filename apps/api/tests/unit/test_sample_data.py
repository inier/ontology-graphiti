"""示例数据生成服务测试"""

import pytest
import os


class TestSampleDataService:
    """示例数据生成服务测试"""

    def _make_service(self):
        from odap.biz.platform.workspace.services.sample_data_service import SampleDataService
        return SampleDataService()

    def _make_workspace(self, tmp_path):
        """创建测试工作空间"""
        from odap.biz.platform.workspace.storage import Storage
        from odap.biz.platform.workspace.models.workspace import Workspace
        db_path = str(tmp_path / "test_workspace.db")
        storage = Storage(db_path=db_path)
        ws = Workspace(name="测试工作空间", description="测试", owner="test")
        storage.save_workspace(ws)
        return ws.id, storage

    def test_generate_sample_data(self, tmp_path):
        """测试生成示例数据"""
        ws_id, _ = self._make_workspace(tmp_path)
        svc = self._make_service()
        result = svc.generate_sample_data(ws_id)

        assert result["workspace_id"] == ws_id
        assert result["status"] == "success"
        assert "ontology" in result["created_resources"]
        assert "agent" in result["created_resources"]
        assert "scenario" in result["created_resources"]

    def test_create_sample_ontology(self, tmp_path):
        """测试创建示例本体"""
        ws_id, _ = self._make_workspace(tmp_path)
        svc = self._make_service()
        result = svc._create_sample_ontology(ws_id)

        assert result["status"] == "success"
        assert result["ontology_id"]
        assert result["entity_types_count"] == 3
        assert result["instances_count"] == 10
        assert "Equipment" in str(result["instances"])
        assert "Personnel" in str(result["instances"])
        assert "Facility" in str(result["instances"])

    def test_create_sample_agent(self, tmp_path):
        """测试创建示例智能体"""
        ws_id, _ = self._make_workspace(tmp_path)
        svc = self._make_service()
        result = svc._create_sample_agent(ws_id)

        assert result["status"] == "success"
        assert result["agent_id"]
        assert "智能体" in result["display_name"]

    def test_create_sample_scenario(self, tmp_path):
        """测试创建示例场景"""
        ws_id, _ = self._make_workspace(tmp_path)
        svc = self._make_service()
        result = svc._create_sample_scenario(ws_id)

        assert result["status"] == "success"
        assert result["scenario_id"]
        assert "场景" in result["name"]

    def test_generate_sample_data_idempotent(self, tmp_path):
        """测试重复生成示例数据不会报错"""
        ws_id, _ = self._make_workspace(tmp_path)
        svc = self._make_service()

        result1 = svc.generate_sample_data(ws_id)
        result2 = svc.generate_sample_data(ws_id)

        assert result1["status"] == "success"
        assert result2["status"] == "success"
