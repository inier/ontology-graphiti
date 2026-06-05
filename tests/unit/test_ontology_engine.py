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
        from odap.biz.core.ontology.design.services.transform_service import OntologyTransformService
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
        from odap.biz.core.ontology.design.schema.document import OntologyDocument, DocumentMeta, SourceInfo

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
        from odap.biz.core.ontology.design.services.qa_ontology_builder import QAOntologyBuilder
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
        from odap.biz.core.ontology.design.services.build_service import OntologyBuilderService
        return OntologyBuilderService()

    @pytest.mark.asyncio
    async def test_extract_entities_relations(self, builder_service):
        """测试实体和关系抽取"""
        from odap.biz.core.ontology.design.schema.document import (
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
        from odap.biz.core.ontology.design.schema.document import OntologyDocument

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
        from odap.biz.core.ontology.design.services.api_version import APIVersionController
        return APIVersionController()

    def test_get_version_info(self, version_controller):
        """测试获取版本信息"""
        from odap.biz.core.ontology.design.services.api_version import APIVersion

        info = version_controller.get_version_info(APIVersion.V2)

        assert info["version"] == "v2"
        assert "endpoints_count" in info

    def test_check_compatibility(self, version_controller):
        """测试版本兼容性检查"""
        from odap.biz.core.ontology.design.services.api_version import APIVersion

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


class TestVersionRecord:
    def test_version_record_creation(self):
        from odap.biz.core.ontology.design.engine.models.version import VersionRecord, VersionStatus
        record = VersionRecord(
            ontology_id="ont-1",
            version_number="1.0.0",
            changelog="Initial version",
            status=VersionStatus.DRAFT,
        )
        assert record.version_number == "1.0.0"
        assert record.status == VersionStatus.DRAFT

    def test_version_status_is_str_enum(self):
        from odap.biz.core.ontology.design.engine.models.version import VersionStatus
        assert isinstance(VersionStatus.DRAFT, str)
        assert VersionStatus.DRAFT.value == "draft"

class TestAuditRecord:
    def test_audit_record_creation(self):
        from odap.biz.core.ontology.design.engine.models.audit import AuditRecord
        record = AuditRecord(
            source="upload",
            process_steps=[{"step": "validate"}, {"step": "store"}],
        )
        assert record.source == "upload"
        assert len(record.process_steps) == 2

    def test_audit_record_default_factory(self):
        from odap.biz.core.ontology.design.engine.models.audit import AuditRecord
        r1 = AuditRecord(source="test")
        r2 = AuditRecord(source="test")
        assert r1.process_steps is not r2.process_steps


class TestValidationResult:
    def test_validation_result_valid(self):
        from odap.biz.core.ontology.design.engine.models.validation import ValidationResult
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_validation_result_invalid(self):
        from odap.biz.core.ontology.design.engine.models.validation import ValidationResult
        result = ValidationResult(is_valid=False, errors=["Missing required field"])
        assert result.is_valid is False
        assert len(result.errors) == 1


class TestSQLiteEngineStorage:
    def test_save_and_get_version(self, tmp_path):
        from odap.biz.core.ontology.design.engine.storage.sqlite_engine_storage import SQLiteEngineStorage
        storage = SQLiteEngineStorage(str(tmp_path / "engine.db"))
        from odap.biz.core.ontology.design.engine.models.version import VersionRecord, VersionStatus
        version = VersionRecord(
            ontology_id="ont-1",
            version_number="1.0.0",
            changelog="Initial",
            status=VersionStatus.DRAFT,
        )
        data = version.model_dump()
        data["version_id"] = "v-1"
        storage.save_version(data)
        result = storage.get_version("v-1")
        assert result is not None
        assert result["version_number"] == "1.0.0"

    def test_get_version_not_found(self, tmp_path):
        from odap.biz.core.ontology.design.engine.storage.sqlite_engine_storage import SQLiteEngineStorage
        storage = SQLiteEngineStorage(str(tmp_path / "engine.db"))
        result = storage.get_version("nonexistent-id")
        assert result is None

    def test_list_versions(self, tmp_path):
        from odap.biz.core.ontology.design.engine.storage.sqlite_engine_storage import SQLiteEngineStorage
        storage = SQLiteEngineStorage(str(tmp_path / "engine.db"))
        from odap.biz.core.ontology.design.engine.models.version import VersionRecord, VersionStatus
        for i in range(3):
            v = VersionRecord(ontology_id="ont-1", version_number=f"{i+1}.0.0", changelog=f"v{i+1}", status=VersionStatus.DRAFT)
            data = v.model_dump()
            data["version_id"] = f"v-{i+1}"
            storage.save_version(data)
        versions = storage.list_versions("ont-1")
        assert len(versions) == 3

    def test_save_and_get_audit(self, tmp_path):
        from odap.biz.core.ontology.design.engine.storage.sqlite_engine_storage import SQLiteEngineStorage
        storage = SQLiteEngineStorage(str(tmp_path / "engine.db"))
        from odap.biz.core.ontology.design.engine.models.audit import AuditRecord
        audit = AuditRecord(source="upload", process_steps=[{"step": "validate"}])
        data = audit.model_dump()
        data["audit_id"] = "a-1"
        storage.save_audit(data)
        result = storage.get_audit("a-1")
        assert result is not None
        assert result["source"] == "upload"

    def test_get_audit_not_found(self, tmp_path):
        from odap.biz.core.ontology.design.engine.storage.sqlite_engine_storage import SQLiteEngineStorage
        storage = SQLiteEngineStorage(str(tmp_path / "engine.db"))
        result = storage.get_audit("nonexistent")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])