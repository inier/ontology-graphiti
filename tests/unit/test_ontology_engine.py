"""
本体管理引擎单元测试
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

# 测试 OntologyTransformService
class TestOntologyTransformService:
    """测试数据转换服务"""

    @pytest.fixture
    def transform_service(self):
        from odap.biz.core.ontology.services.transform_service import OntologyTransformService
        return OntologyTransformService()

    @pytest.mark.asyncio
    async def test_transform_json(self, transform_service):
        """测试 JSON 数据转换"""
        data = {
            "doc_id": "test-doc-1",
            "doc_type": "event",
            "entities": [
                {
                    "entity_id": "ent-1",
                    "entity_type": "Person",
                    "name": "测试实体"
                }
            ]
        }

        result = await transform_service.transform(data, "json")

        assert result.doc_id == "test-doc-1"
        assert result.doc_type == "event"
        assert len(result.entities) >= 0

    @pytest.mark.asyncio
    async def test_transform_csv(self, transform_service):
        """测试 CSV 数据转换"""
        csv_data = "name,value\ntest,123\ntest2,456"

        result = await transform_service.transform(csv_data, "csv")

        assert result.doc_type == "batch"
        assert len(result.entities) == 2

    @pytest.mark.asyncio
    async def test_data_quality_validation(self, transform_service):
        """测试数据质量校验"""
        from odap.biz.core.ontology.schema.document import OntologyDocument, DocumentMeta, SourceInfo

        doc = OntologyDocument(
            doc_id="test-doc",
            doc_type="event",
            source=SourceInfo(type="test", collected_at="2026-04-26T00:00:00Z", confidence=0.9),
            meta=DocumentMeta(title="测试文档")
        )

        quality_result = transform_service.validate_quality(doc)

        assert quality_result.is_valid is True

    def test_transform_stats(self, transform_service):
        """测试转换统计"""
        stats = transform_service.get_transform_stats()

        assert "transform_count" in stats
        assert "error_count" in stats
        assert "success_rate" in stats


# 测试 QAOntologyBuilder
class TestQAOntologyBuilder:
    """测试 QA 驱动的本体构建"""

    @pytest.fixture
    def qa_builder(self):
        from odap.biz.core.ontology.services.qa_ontology_builder import QAOntologyBuilder
        return QAOntologyBuilder()

    @pytest.mark.asyncio
    async def test_process_question(self, qa_builder):
        """测试问题处理"""
        result = await qa_builder.process_question(
            question="请分析美伊战争走势",
            user_id="test-user"
        )

        assert "task_id" in result
        assert "answer" in result
        assert "status" in result

    @pytest.mark.asyncio
    async def test_get_progress(self, qa_builder):
        """测试获取进度"""
        # 先创建任务
        result = await qa_builder.process_question(
            question="测试问题",
            user_id="test-user"
        )

        task_id = result["task_id"]
        progress = await qa_builder.get_progress(task_id)

        assert progress is not None
        assert progress["task_id"] == task_id

    @pytest.mark.asyncio
    async def test_intent_analysis(self, qa_builder):
        """测试意图分析"""
        # 分析需要搜索的问题
        result = await qa_builder._analyze_intent("请分析美伊战争最新消息")

        assert result.requires_search is True
        assert result.intent_type.value in ["update", "analyze"]

        # 分析查询问题
        result2 = await qa_builder._analyze_intent("什么是人工智能")

        assert result2.requires_search is False
        assert result2.intent_type.value == "query"


# 测试 OntologyBuilderService
class TestOntologyBuilderService:
    """测试本体构建服务"""

    @pytest.fixture
    def builder_service(self):
        from odap.biz.core.ontology.services.build_service import OntologyBuilderService
        return OntologyBuilderService()

    @pytest.mark.asyncio
    async def test_extract_entities_relations(self, builder_service):
        """测试实体和关系抽取"""
        from odap.biz.core.ontology.schema.document import (
            OntologyDocument, OntologyEntity, OntologyRelation
        )

        # 创建测试文档
        doc = OntologyDocument(
            doc_id="test-doc",
            doc_type="event",
            source={"type": "test", "collected_at": "2026-04-26T00:00:00Z", "confidence": 0.9},
            meta={"title": "测试"}
        )

        # 添加实体
        doc.entities.append(OntologyEntity(
            entity_id="ent-1",
            entity_type="Person",
            name="测试实体"
        ))

        entities, relations = await builder_service._extract_entities_relations(doc)

        assert len(entities) == 1
        assert entities[0]["entity_id"] == "ent-1"
        assert len(relations) == 0

    @pytest.mark.asyncio
    async def test_detect_changes(self, builder_service):
        """测试变化检测"""
        from odap.biz.core.ontology.schema.document import OntologyDocument

        doc = OntologyDocument(
            doc_id="test-doc",
            doc_type="event",
            source={"type": "test", "collected_at": "2026-04-26T00:00:00Z", "confidence": 0.9},
            meta={"title": "测试"}
        )

        changes = await builder_service.detect_changes(doc, "v1")

        assert "entities" in changes
        assert "relations" in changes

# 测试 API Version Controller
class TestAPIVersionController:
    """测试 API 版本控制"""

    @pytest.fixture
    def version_controller(self):
        from odap.biz.core.ontology.services.api_version import APIVersionController
        return APIVersionController()

    def test_get_version_info(self, version_controller):
        """测试获取版本信息"""
        from odap.biz.core.ontology.services.api_version import APIVersion

        info = version_controller.get_version_info(APIVersion.V2)

        assert info["version"] == "v2"
        assert "endpoints_count" in info

    def test_check_compatibility(self, version_controller):
        """测试版本兼容性检查"""
        from odap.biz.core.ontology.services.api_version import APIVersion

        result = version_controller.check_compatibility(
            APIVersion.V1,
            APIVersion.V2
        )

        assert "compatible" in result
        assert "migration_guide" in result

    def test_get_change_log(self, version_controller):
        """测试获取变更日志"""
        logs = version_controller.get_change_log()

        assert isinstance(logs, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])