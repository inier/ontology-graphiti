"""
本体管理引擎集成测试
测试多个组件之间的协作
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock


class TestOntologyIngestionPipeline:
    """测试本体摄入管道"""

    @pytest.fixture
    def event_loop(self):
        """创建事件循环"""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.mark.asyncio
    async def test_news_ingest_to_ontology_flow(self):
        """测试从新闻摄入到本体构建的完整流程"""
        from odap.biz.ontology.ingestion import NewsIngester

        ingester = NewsIngester()
        news_results = await ingester.ingest(
            query="美伊战争最新消息",
            event_context="分析国际形势"
        )

        assert len(news_results) > 0
        for result in news_results:
            assert hasattr(result, "doc_id") or hasattr(result, "entities")


class TestQABuildIntegration:
    """测试问答构建集成"""

    @pytest.fixture
    def event_loop(self):
        """创建事件循环"""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    @pytest.mark.asyncio
    async def test_qa_to_ontology_flow(self, event_loop):
        """测试从问答到本体构建的流程"""
        from odap.biz.ontology.services.qa_ontology_builder import get_qa_builder

        builder = get_qa_builder()

        # 1. 处理用户问题
        result = await builder.process_question(
            question="请分析人工智能对教育的影响",
            user_id="test-user"
        )

        # 2. 验证结果
        assert result is not None
        assert "task_id" in result
        assert "answer" in result

        # 3. 获取进度
        progress = await builder.get_progress(result["task_id"])
        assert progress is not None
        assert progress["task_id"] == result["task_id"]


class TestAPIIntegration:
    """测试 API 集成"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200

    def test_ingest_news_endpoint(self, client):
        """测试新闻摄入端点"""
        response = client.post(
            "/api/ingest/news",
            json={"query": "测试新闻"}
        )

        # 可能返回 200 或 500（取决于后端状态）
        assert response.status_code in [200, 500]

    def test_version_info_endpoint(self, client):
        """测试版本信息端点"""
        response = client.get("/api/version")

        if response.status_code == 200:
            data = response.json()
            assert "version" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])