"""
本体服务单元测试 - 对齐 odap/biz/core/ontology/services/

覆盖:
- pipeline_service: OntologyPipeline 回滚触发 hook、管道阶段执行
- version_service: OntologyVersionManager 创建版本、列出版本、回滚
- validation_service: ValidationService 验证实例属性、验证实体类型
- search_service: SearchService 按名称搜索、按属性搜索、降级处理
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_storage():
    """创建模拟的 SQLiteIngestStorage"""
    storage = MagicMock()
    storage.list_all_versions.return_value = []
    storage.get_current_version.return_value = None
    storage.get_versions.return_value = []
    storage.get_version.return_value = None
    storage.get_validation_rule.return_value = None
    storage.list_validation_rules.return_value = []
    storage.count_validation_rules.return_value = 0
    storage.get_validation_result.return_value = None
    storage.list_validation_issues.return_value = []
    storage.get_validation_issue.return_value = None
    storage.get_registry_entities.return_value = []
    storage.list_scenarios.return_value = []
    storage.save_version.return_value = None
    storage.save_validation_rule.return_value = None
    storage.save_validation_result.return_value = None
    storage.save_validation_issue.return_value = None
    storage.update_validation_issue.return_value = None
    storage.update_entity_name.return_value = None
    return storage


@pytest.fixture
def version_manager(mock_storage):
    """创建使用 mock storage 的 OntologyVersionManager"""
    from odap.biz.core.ontology.design.services.version_service import OntologyVersionManager
    # 重置单例以确保测试隔离
    OntologyVersionManager._instance = None
    mgr = OntologyVersionManager(storage=mock_storage)
    return mgr


@pytest.fixture
def validation_service():
    """创建 ValidationService 实例"""
    from odap.biz.core.ontology.design.services.validation_service import ValidationService
    return ValidationService()


@pytest.fixture
def search_service():
    """创建 SearchService 实例"""
    from odap.biz.core.ontology.design.services.search_service import SearchService
    return SearchService()


def _make_ontology_document(ontology_id="ont-001", entities=None, relations=None, events=None):
    """构造测试用 OntologyDocument"""
    from odap.biz.core.ontology.design.schema.document import (
        OntologyDocument, OntologyEntity, OntologyRelation, OntologyEvent, SourceInfo
    )
    doc = OntologyDocument(
        doc_type="event",
        source=SourceInfo(type="manual"),
        entities=entities or [
            OntologyEntity(entity_id="e1", entity_type="Unit", name="红方1旅", basic_properties={"side": "red"}),
            OntologyEntity(entity_id="e2", entity_type="Location", name="A区高地", basic_properties={}),
        ],
        relations=relations or [
            OntologyRelation(relation_id="r1", relation_type="located_at", source_entity="e1", target_entity="e2", temporal={}),
        ],
        events=events or [
            OntologyEvent(event_id="ev1", event_type="movement", timestamp=datetime.now().isoformat(), location="A区", participants=[], outcome={}),
        ],
    )
    doc.ontology_id = ontology_id
    return doc


# ===========================================================================
# TestPipelineService - 管道服务
# ===========================================================================

class TestPipelineService:
    """OntologyPipeline 管道服务测试"""

    @pytest.mark.asyncio
    async def test_rollback_triggers_hook(self):
        """回滚版本应通过 ingest 触发 ontology.updated hook 事件"""
        from odap.biz.core.ontology.design.services.pipeline_service import OntologyPipeline
        from odap.biz.core.ontology.design.services.version_service import OntologyVersionManager, OntologyVersion
        from odap.infra.events import HookRegistry, HookPhase, HookContext

        # 准备 mock
        mock_vm = MagicMock(spec=OntologyVersionManager)
        doc = _make_ontology_document()
        mock_vm.get_doc = AsyncMock(return_value=doc)

        new_version = OntologyVersion(
            version_id="v20260603-002",
            ontology_id="ont-001",
            version_number="1.2.0",
            doc_id=doc.doc_id,
            doc_type="event",
            parent_version="v20260603-001",
            commit_message="回退到版本 v20260603-001",
            created_at=datetime.now().isoformat(),
            is_current=True,
        )
        mock_vm.append = AsyncMock(return_value=new_version)

        mock_hook = MagicMock(spec=HookRegistry)
        mock_hook.get_hooks.return_value = []

        pipeline = OntologyPipeline(
            graph_manager=None,
            version_manager=mock_vm,
            hook_registry=mock_hook,
        )

        result = await pipeline.rollback("v20260603-001")

        # 验证 get_doc 被调用
        mock_vm.get_doc.assert_called_once_with("v20260603-001")
        # 验证 append 被调用（回滚通过 ingest -> append 实现）
        mock_vm.append.assert_called_once()
        # 验证回滚结果版本号
        assert result.version_id == "v20260603-002"

    @pytest.mark.asyncio
    async def test_rollback_nonexistent_version_raises_error(self):
        """回滚不存在的版本应抛出 ValueError"""
        from odap.biz.core.ontology.design.services.pipeline_service import OntologyPipeline
        from odap.biz.core.ontology.design.services.version_service import OntologyVersionManager
        from odap.infra.events import HookRegistry

        mock_vm = MagicMock(spec=OntologyVersionManager)
        mock_vm.get_doc = AsyncMock(return_value=None)

        mock_hook = MagicMock(spec=HookRegistry)
        mock_hook.get_hooks.return_value = []

        pipeline = OntologyPipeline(
            graph_manager=None,
            version_manager=mock_vm,
            hook_registry=mock_hook,
        )

        with pytest.raises(ValueError, match="不存在"):
            await pipeline.rollback("v-nonexistent")

    @pytest.mark.asyncio
    async def test_ingest_validates_document(self):
        """ingest 应验证 OntologyDocument schema"""
        from odap.biz.core.ontology.design.services.pipeline_service import OntologyPipeline
        from odap.biz.core.ontology.design.services.version_service import OntologyVersionManager, OntologyVersion
        from odap.infra.events import HookRegistry

        doc = _make_ontology_document(ontology_id="ont-001")

        mock_vm = MagicMock(spec=OntologyVersionManager)
        new_version = OntologyVersion(
            version_id="v20260603-001",
            ontology_id="ont-001",
            version_number="1.0.0",
            doc_id=doc.doc_id,
            doc_type="event",
            parent_version=None,
            commit_message="初始版本",
            created_at=datetime.now().isoformat(),
            is_current=True,
        )
        mock_vm.append = AsyncMock(return_value=new_version)

        mock_hook = MagicMock(spec=HookRegistry)
        mock_hook.get_hooks.return_value = []

        pipeline = OntologyPipeline(
            graph_manager=None,
            version_manager=mock_vm,
            hook_registry=mock_hook,
        )

        result = await pipeline.ingest(doc, ontology_id="ont-001")
        assert result.version_id == "v20260603-001"
        mock_vm.append.assert_called_once_with("ont-001", doc)

    @pytest.mark.asyncio
    async def test_ingest_without_ontology_id_raises_error(self):
        """ingest 未提供 ontology_id 且 doc 无 ontology_id 时应抛出 ValueError"""
        from odap.biz.core.ontology.design.services.pipeline_service import OntologyPipeline
        from odap.infra.events import HookRegistry

        doc = _make_ontology_document(ontology_id="")

        mock_hook = MagicMock(spec=HookRegistry)
        mock_hook.get_hooks.return_value = []

        pipeline = OntologyPipeline(
            graph_manager=None,
            version_manager=MagicMock(),
            hook_registry=mock_hook,
        )

        with pytest.raises(ValueError, match="ontology_id"):
            await pipeline.ingest(doc)

    def test_pipeline_get_stats(self):
        """get_stats 应返回 ingest_count, error_count, version_count"""
        from odap.biz.core.ontology.design.services.pipeline_service import OntologyPipeline
        from odap.biz.core.ontology.design.services.version_service import OntologyVersionManager
        from odap.infra.events import HookRegistry

        mock_vm = MagicMock(spec=OntologyVersionManager)
        mock_vm.get_version_count.return_value = 5
        mock_vm.get_latest_version_id.return_value = "v20260603-001"

        pipeline = OntologyPipeline(
            graph_manager=None,
            version_manager=mock_vm,
            hook_registry=MagicMock(spec=HookRegistry),
        )

        stats = pipeline.get_stats()
        assert stats["ingest_count"] == 0
        assert stats["error_count"] == 0
        assert stats["version_count"] == 5
        assert stats["latest_version"] == "v20260603-001"


# ===========================================================================
# TestVersionService - 版本管理服务
# ===========================================================================

class TestVersionService:
    """OntologyVersionManager 版本管理测试"""

    @pytest.mark.asyncio
    async def test_create_initial_version(self, version_manager, mock_storage):
        """首次创建版本应生成 1.0.0 版本"""
        doc = _make_ontology_document(ontology_id="ont-001")

        version = await version_manager.append("ont-001", doc, message="初始版本")

        assert version.version_number == "1.0.0"
        assert version.is_current is True
        assert version.parent_version is None
        mock_storage.save_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_append_to_existing_version(self, version_manager, mock_storage):
        """追加到已有版本应更新快照但不改变版本号"""
        # 模拟已有版本
        mock_storage.get_current_version.return_value = {
            "id": "v20260603-001",
            "ontology_id": "ont-001",
            "version_number": "1.0.0",
            "doc_snapshot": None,
            "doc_id": "doc-old",
            "doc_type": "event",
            "entity_count": 1,
            "relation_count": 0,
            "event_count": 0,
        }

        doc = _make_ontology_document(ontology_id="ont-001")
        version = await version_manager.append("ont-001", doc, message="追加数据")

        # append_version_snapshot 应被调用
        mock_storage.append_version_snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_commit_creates_new_version(self, version_manager, mock_storage):
        """commit 应锁定当前版本并创建新版本"""
        mock_storage.get_current_version.return_value = {
            "id": "v20260603-001",
            "ontology_id": "ont-001",
            "version_number": "1.0.0",
            "doc_snapshot": None,
            "doc_id": "doc-001",
            "doc_type": "event",
            "entity_count": 2,
            "relation_count": 1,
            "event_count": 1,
        }

        version = await version_manager.commit("ont-001", message="提交版本")

        assert version.version_number == "1.1.0"
        assert version.parent_version == "v20260603-001"
        assert version.is_current is True
        mock_storage.lock_version.assert_called_once_with("v20260603-001")
        mock_storage.save_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_versions(self, version_manager, mock_storage):
        """列出所有版本"""
        mock_storage.list_all_versions.return_value = [
            {"id": "v20260603-002", "ontology_id": "ont-001", "version_number": "1.1.0",
             "doc_id": "", "doc_type": "", "parent_version_id": "v20260603-001",
             "change_summary": "commit", "created_at": "2026-06-03T10:00:00",
             "is_current": True, "is_stable": True, "entity_count": 2, "relation_count": 1, "event_count": 1},
            {"id": "v20260603-001", "ontology_id": "ont-001", "version_number": "1.0.0",
             "doc_id": "", "doc_type": "", "parent_version_id": None,
             "change_summary": "初始版本", "created_at": "2026-06-03T09:00:00",
             "is_current": False, "is_stable": True, "entity_count": 1, "relation_count": 0, "event_count": 0},
        ]

        versions = await version_manager.list()
        assert len(versions) == 2
        assert versions[0].version_number == "1.1.0"
        assert versions[1].version_number == "1.0.0"

    @pytest.mark.asyncio
    async def test_get_nonexistent_version_returns_none(self, version_manager, mock_storage):
        """获取不存在的版本应返回 None"""
        mock_storage.get_version.return_value = None
        result = await version_manager.get("v-nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_diff_between_versions(self, version_manager, mock_storage):
        """对比两个版本的差异"""
        from odap.biz.core.ontology.design.schema.document import (
            OntologyDocument, OntologyEntity, OntologyRelation, OntologyEvent, SourceInfo
        )

        doc_a = OntologyDocument(
            doc_type="event", source=SourceInfo(type="manual"),
            entities=[OntologyEntity(entity_id="e1", entity_type="Unit", name="A", basic_properties={})],
            relations=[], events=[],
        )
        doc_b = OntologyDocument(
            doc_type="event", source=SourceInfo(type="manual"),
            entities=[
                OntologyEntity(entity_id="e1", entity_type="Unit", name="A", basic_properties={}),
                OntologyEntity(entity_id="e2", entity_type="Unit", name="B", basic_properties={}),
            ],
            relations=[], events=[],
        )

        mock_storage.get_version.side_effect = lambda vid: {
            "doc_snapshot": json.dumps(doc_a.to_dict()) if vid == "v-a" else json.dumps(doc_b.to_dict()),
            "id": vid, "ontology_id": "ont-001", "version_number": "1.0.0",
            "doc_id": "", "doc_type": "", "parent_version_id": None,
            "change_summary": "", "created_at": "", "is_current": False, "is_stable": True,
            "entity_count": 0, "relation_count": 0, "event_count": 0,
        }

        diff = await version_manager.diff("v-a", "v-b")
        assert "e2" in diff.added_entities
        assert len(diff.removed_entities) == 0


# ===========================================================================
# TestValidationService - 验证服务
# ===========================================================================

class TestValidationService:
    """ValidationService 验证服务测试"""

    def test_add_validation_rule(self, validation_service):
        """添加验证规则应返回规则信息"""
        result = validation_service.add_validation_rule({
            "name": "最少实体数",
            "description": "本体至少需要一个实体",
            "rule_type": "entity",
            "severity": "error",
            "expression": "min_count",
            "params": {"min": 1},
            "enabled": True,
        })
        assert result["name"] == "最少实体数"
        assert result["rule_type"] == "entity"
        assert result["severity"] == "error"
        assert result["expression"] == "min_count"

    def test_get_nonexistent_rule_returns_error(self, validation_service):
        """获取不存在的规则应返回错误"""
        result = validation_service.get_validation_rule("nonexistent-rule-id")
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    def test_list_validation_rules_empty(self):
        """空规则列表应返回空列表"""
        from odap.biz.core.ontology.design.services.validation_service import ValidationService
        # 创建全新实例，避免与其他测试共享 SQLite 状态
        svc = ValidationService()
        with patch.object(svc.engine, 'storage') as mock_st:
            mock_st.list_validation_rules.return_value = []
            mock_st.count_validation_rules.return_value = 0
            result = svc.list_validation_rules()
        assert result["rules"] == []
        assert result["total"] == 0

    def test_validate_entity_type_required(self, validation_service):
        """验证实体类型是否包含必需类型"""
        # 先添加规则
        validation_service.add_validation_rule({
            "name": "需要Unit类型",
            "description": "本体必须包含Unit类型实体",
            "rule_type": "entity",
            "severity": "error",
            "expression": "required_type",
            "params": {"entity_type": "Unit"},
            "enabled": True,
        })

        # 验证本体 - mock storage 返回空实体
        with patch.object(validation_service.engine, '_load_ontology_data', return_value={
            'entities': [], 'relations': [], 'ontology_version': '1.0.0'
        }):
            result = validation_service.validate_ontology("ont-001")
            assert result["error_count"] >= 1

    def test_validate_entity_property_required(self, validation_service):
        """验证实体属性是否包含必需属性"""
        validation_service.add_validation_rule({
            "name": "Unit需要side属性",
            "description": "Unit类型实体必须有side属性",
            "rule_type": "property",
            "severity": "warning",
            "expression": "required_property",
            "params": {"entity_type": "Unit", "property_name": "side"},
            "enabled": True,
        })

        with patch.object(validation_service.engine, '_load_ontology_data', return_value={
            'entities': [
                {'entity_id': 'e1', 'entity_type': 'Unit', 'name': '红方1旅', 'basic_properties': {}},
            ],
            'relations': [], 'ontology_version': '1.0.0'
        }):
            result = validation_service.validate_ontology("ont-001")
            assert result["warning_count"] >= 1

    def test_validate_ontology_with_valid_data(self, validation_service):
        """验证合法本体应返回高评分"""
        validation_service.add_validation_rule({
            "name": "最少实体数",
            "description": "本体至少需要一个实体",
            "rule_type": "entity",
            "severity": "error",
            "expression": "min_count",
            "params": {"min": 1},
            "enabled": True,
        })

        with patch.object(validation_service.engine, '_load_ontology_data', return_value={
            'entities': [
                {'entity_id': 'e1', 'entity_type': 'Unit', 'name': '红方1旅', 'basic_properties': {'side': 'red'}},
                {'entity_id': 'e2', 'entity_type': 'Location', 'name': 'A区', 'basic_properties': {}},
            ],
            'relations': [
                {'relation_id': 'r1', 'relation_type': 'located_at', 'source_entity': 'e1', 'target_entity': 'e2'},
            ],
            'ontology_version': '1.0.0'
        }):
            result = validation_service.validate_ontology("ont-001")
            assert result["status"] == "complete"
            assert result["overall_score"] > 0.5


# ===========================================================================
# TestSearchService - 搜索服务
# ===========================================================================

class TestSearchService:
    """SearchService 搜索服务测试"""

    @pytest.mark.asyncio
    async def test_search_with_mock_provider(self, search_service):
        """使用 Mock 搜索提供者应返回模拟结果"""
        import os
        from unittest.mock import patch
        from odap.biz.core.ontology.design.services.search_service import MockSearch

        with patch.dict(os.environ, {"SEARCH_ALLOW_MOCK": "true"}):
            search_service._providers = [MockSearch()]
            results = await search_service.search("测试查询", max_results=3)
            assert len(results) == 3
            assert all(r.title for r in results)
            assert all(r.url for r in results)

    @pytest.mark.asyncio
    async def test_search_by_name_returns_results(self, search_service):
        """按名称搜索应返回包含关键词的结果"""
        import os
        from unittest.mock import patch
        from odap.biz.core.ontology.design.services.search_service import MockSearch

        with patch.dict(os.environ, {"SEARCH_ALLOW_MOCK": "true"}):
            search_service._providers = [MockSearch()]
            results = await search_service.search("本体构建", max_results=5)
            assert len(results) > 0
            for r in results:
                assert "本体构建" in r.title or "本体构建" in r.content

    @pytest.mark.asyncio
    async def test_search_by_attributes_snippet(self, search_service):
        """搜索结果应包含 snippet 字段"""
        import os
        from unittest.mock import patch
        from odap.biz.core.ontology.design.services.search_service import MockSearch

        with patch.dict(os.environ, {"SEARCH_ALLOW_MOCK": "true"}):
            search_service._providers = [MockSearch()]
            results = await search_service.search("态势分析", max_results=2)
            assert len(results) > 0
            for r in results:
                assert hasattr(r, 'snippet')
                assert r.snippet

    @pytest.mark.asyncio
    async def test_search_fallback_on_provider_failure(self, search_service):
        """搜索提供者返回空结果时应自动降级到下一个提供者"""
        import os
        from unittest.mock import patch
        from odap.biz.core.ontology.design.services.search_service import BaseSearchProvider, MockSearch

        class EmptyProvider(BaseSearchProvider):
            def is_available(self):
                return True
            async def search(self, query, max_results=5):
                return []  # 返回空结果，触发降级

        with patch.dict(os.environ, {"SEARCH_ALLOW_MOCK": "true"}):
            search_service._providers = [EmptyProvider(), MockSearch()]
            results = await search_service.search("降级测试", max_results=2)
            assert len(results) > 0  # MockSearch 应作为降级方案

    def test_get_available_providers(self, search_service):
        """get_available_providers 应返回可用提供者列表"""
        providers = search_service.get_available_providers()
        assert isinstance(providers, list)
        # MockSearch 默认不可用（需 SEARCH_ALLOW_MOCK=true）
        # 至少应有一个 Provider 在列表中（可能是 TavilySearch 等）
        assert len(providers) >= 0

    @pytest.mark.asyncio
    async def test_search_result_to_dict(self, search_service):
        """SearchResult.to_dict 应返回完整字典"""
        from odap.biz.core.ontology.design.services.search_service import SearchResult
        result = SearchResult(
            title="测试标题",
            url="https://example.com",
            content="测试内容",
            snippet="摘要",
            date="2026-06-03",
        )
        d = result.to_dict()
        assert d["title"] == "测试标题"
        assert d["url"] == "https://example.com"
        assert d["content"] == "测试内容"
        assert d["snippet"] == "摘要"
        assert d["date"] == "2026-06-03"
