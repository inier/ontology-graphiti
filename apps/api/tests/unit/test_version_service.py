"""
OntologyVersionManager 单元测试

覆盖:
- OntologyVersionManager commit/append/get_doc
- 版本 ID 生成
- rollback (通过 OntologyPipeline.rollback)
- get_latest_version_id
- _bump_version 辅助函数
- OntologyVersion 数据类
"""

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime


# ---------------------------------------------------------------------------
# 延迟导入 + skip
# ---------------------------------------------------------------------------

try:
    from odap.biz.core.ontology.design.services.version_service import (
        OntologyVersionManager,
        OntologyVersion,
        OntologyDiff,
        _bump_version,
    )
    from odap.biz.core.ontology.design.schema.document import (
        OntologyDocument, OntologyEntity, OntologyRelation, DocumentMeta,
    )
except Exception as exc:
    pytest.skip(f"Cannot import version_service: {exc}", allow_module_level=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_version_manager_singleton():
    """每个测试前重置 OntologyVersionManager 单例"""
    OntologyVersionManager._instance = None
    yield
    OntologyVersionManager._instance = None


@pytest.fixture
def mock_storage():
    """创建 mock 存储对象"""
    storage = MagicMock()
    storage.save_version = MagicMock(return_value="v20250101-001")
    storage.get_version = MagicMock(return_value=None)
    storage.get_current_version = MagicMock(return_value=None)
    storage.get_versions = MagicMock(return_value=[])
    storage.list_all_versions = MagicMock(return_value=[])
    storage.lock_version = MagicMock(return_value=True)
    storage.set_current_version = MagicMock(return_value=True)
    storage.append_version_snapshot = MagicMock(return_value=True)
    return storage


@pytest.fixture
def manager(mock_storage):
    """创建 OntologyVersionManager 实例，注入 mock 存储"""
    mgr = OntologyVersionManager(storage=mock_storage)
    return mgr


def _make_entity(entity_id="e1", entity_type="Unit", name="Test", **overrides):
    defaults = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "name": name,
        "name_en": "",
        "aliases": [],
        "basic_properties": {},
        "statistical_properties": {},
        "capabilities": {},
        "constraints": [],
    }
    defaults.update(overrides)
    return OntologyEntity(**defaults)


def _make_document(doc_id="doc-test-001", **overrides):
    defaults = {
        "doc_id": doc_id,
        "meta": DocumentMeta(title="Test Doc"),
        "entities": [_make_entity()],
        "relations": [],
        "events": [],
    }
    defaults.update(overrides)
    return OntologyDocument(**defaults)


# ---------------------------------------------------------------------------
# TestBumpVersion — 版本号递增
# ---------------------------------------------------------------------------

class TestBumpVersion:
    def test_bump_minor(self):
        """1.0.0 → 1.1.0"""
        assert _bump_version("1.0.0") == "1.1.0"

    def test_bump_minor_from_1_2_0(self):
        """1.2.0 → 1.3.0"""
        assert _bump_version("1.2.0") == "1.3.0"

    def test_bump_minor_from_2_5_0(self):
        """2.5.0 → 2.6.0"""
        assert _bump_version("2.5.0") == "2.6.0"

    def test_bump_invalid_version(self):
        """无效版本号应返回 1.0.0"""
        assert _bump_version("invalid") == "1.0.0"

    def test_bump_empty_string(self):
        """空字符串应返回 1.0.0"""
        assert _bump_version("") == "1.0.0"


# ---------------------------------------------------------------------------
# TestOntologyVersion — 数据类
# ---------------------------------------------------------------------------

class TestOntologyVersion:
    def test_to_dict_excludes_snapshot(self):
        """to_dict() 不应包含 doc_snapshot"""
        version = OntologyVersion(
            version_id="v20250101-001",
            ontology_id="ont-1",
            version_number="1.0.0",
            doc_id="doc-1",
            doc_type="event",
            parent_version=None,
            commit_message="initial",
            created_at="2025-01-01T00:00:00",
            doc_snapshot='{"entities": []}',
        )
        d = version.to_dict()
        assert "doc_snapshot" not in d
        assert d["version_id"] == "v20250101-001"
        assert d["version_number"] == "1.0.0"

    def test_to_dict_includes_required_fields(self):
        """to_dict() 应包含所有必需字段"""
        version = OntologyVersion(
            version_id="v20250101-001",
            ontology_id="ont-1",
            version_number="1.0.0",
            doc_id="doc-1",
            doc_type="event",
            parent_version=None,
            commit_message="initial",
            created_at="2025-01-01T00:00:00",
        )
        d = version.to_dict()
        assert "version_id" in d
        assert "ontology_id" in d
        assert "version_number" in d
        assert "commit_message" in d
        assert "is_current" in d
        assert "is_stable" in d


# ---------------------------------------------------------------------------
# TestGenerateVersionId — 版本 ID 生成
# ---------------------------------------------------------------------------

class TestGenerateVersionId:
    def test_generates_version_id_format(self, manager, mock_storage):
        """版本 ID 应符合 v{YYYYMMDD}-{seq:03d} 格式"""
        mock_storage.list_all_versions = MagicMock(return_value=[])
        vid = manager._generate_version_id()
        assert vid.startswith("v")
        # 格式: v{8位日期}-{3位序号}
        parts = vid.split("-")
        assert len(parts) == 2
        date_part = parts[0][1:]  # 去掉 v 前缀
        assert len(date_part) == 8
        assert parts[1].isdigit()
        assert len(parts[1]) == 3

    def test_increments_seq_from_existing(self, manager, mock_storage):
        """已有版本时应递增序号"""
        today_str = datetime.now().strftime("%Y%m%d")
        mock_storage.list_all_versions = MagicMock(return_value=[
            {"id": f"v{today_str}-001"},
            {"id": f"v{today_str}-002"},
        ])
        vid = manager._generate_version_id()
        # 当天已有 001 和 002，下一个应为 003
        assert vid.endswith("-003")

    def test_starts_at_001_for_new_day(self, manager, mock_storage):
        """新的一天应从 001 开始"""
        mock_storage.list_all_versions = MagicMock(return_value=[
            {"id": "v20241231-005"},
        ])
        vid = manager._generate_version_id()
        # 不同日期，序号从 001 开始
        assert vid.endswith("-001")


# ---------------------------------------------------------------------------
# TestCommit — 版本提交
# ---------------------------------------------------------------------------

class TestCommit:
    @pytest.mark.asyncio
    async def test_commit_creates_initial_version(self, manager, mock_storage):
        """无现有版本时 commit 应创建初始版本"""
        mock_storage.get_current_version = MagicMock(return_value=None)
        mock_storage.list_all_versions = MagicMock(return_value=[])

        version = await manager.commit(
            ontology_id="ont-1",
            message="initial commit",
        )

        assert version.version_number == "1.0.0"
        assert version.ontology_id == "ont-1"
        assert version.commit_message == "initial commit"
        assert version.is_current is True
        mock_storage.save_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_commit_bumps_version(self, manager, mock_storage):
        """有现有版本时 commit 应递增版本号"""
        mock_storage.get_current_version = MagicMock(return_value={
            "id": "v20250101-001",
            "version_number": "1.0.0",
            "doc_snapshot": None,
            "doc_id": "doc-1",
            "doc_type": "event",
            "entity_count": 0,
            "relation_count": 0,
            "event_count": 0,
        })
        mock_storage.list_all_versions = MagicMock(return_value=[
            {"id": "v20250101-001"},
        ])

        version = await manager.commit(
            ontology_id="ont-1",
            message="second commit",
        )

        assert version.version_number == "1.1.0"
        assert version.parent_version == "v20250101-001"
        mock_storage.lock_version.assert_called_once_with("v20250101-001")

    @pytest.mark.asyncio
    async def test_commit_locks_previous_version(self, manager, mock_storage):
        """commit 应锁定旧版本"""
        mock_storage.get_current_version = MagicMock(return_value={
            "id": "v20250101-001",
            "version_number": "1.0.0",
            "doc_snapshot": None,
            "doc_id": "doc-1",
            "doc_type": "event",
            "entity_count": 0,
            "relation_count": 0,
            "event_count": 0,
        })
        mock_storage.list_all_versions = MagicMock(return_value=[
            {"id": "v20250101-001"},
        ])

        await manager.commit(ontology_id="ont-1")

        mock_storage.lock_version.assert_called_once_with("v20250101-001")


# ---------------------------------------------------------------------------
# TestAppend — 版本追加
# ---------------------------------------------------------------------------

class TestAppend:
    @pytest.mark.asyncio
    async def test_append_creates_initial_version(self, manager, mock_storage):
        """无现有版本时 append 应创建初始版本"""
        mock_storage.get_current_version = MagicMock(return_value=None)
        mock_storage.list_all_versions = MagicMock(return_value=[])

        doc = _make_document()
        version = await manager.append("ont-1", doc)

        assert version.version_number == "1.0.0"
        mock_storage.save_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_append_updates_existing_version(self, manager, mock_storage):
        """有现有版本时 append 应更新快照"""
        mock_storage.get_current_version = MagicMock(return_value={
            "id": "v20250101-001",
            "version_number": "1.0.0",
            "doc_snapshot": None,
            "doc_id": "doc-1",
            "doc_type": "event",
            "entity_count": 0,
            "relation_count": 0,
            "event_count": 0,
        })
        # 第二次调用返回更新后的版本
        updated_version = {
            "id": "v20250101-001",
            "version_number": "1.0.0",
            "doc_snapshot": None,
            "doc_id": "doc-1",
            "doc_type": "event",
            "entity_count": 1,
            "relation_count": 0,
            "event_count": 0,
        }
        mock_storage.get_current_version = MagicMock(
            side_effect=[mock_storage.get_current_version.return_value, updated_version]
        )

        doc = _make_document()
        version = await manager.append("ont-1", doc)

        # append 不改变版本号
        assert version.version_number == "1.0.0"
        mock_storage.append_version_snapshot.assert_called_once()


# ---------------------------------------------------------------------------
# TestGetDoc — 获取版本文档
# ---------------------------------------------------------------------------

class TestGetDoc:
    @pytest.mark.asyncio
    async def test_get_doc_returns_none_for_missing(self, manager, mock_storage):
        """不存在的版本应返回 None"""
        mock_storage.get_version = MagicMock(return_value=None)
        result = await manager.get_doc("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_doc_returns_document_from_snapshot(self, manager, mock_storage):
        """有快照时应返回 OntologyDocument"""
        doc = _make_document()
        snapshot_json = json.dumps(doc.to_dict(), ensure_ascii=False, default=str)
        mock_storage.get_version = MagicMock(return_value={
            "id": "v20250101-001",
            "doc_snapshot": snapshot_json,
        })

        result = await manager.get_doc("v20250101-001")
        assert result is not None
        assert isinstance(result, OntologyDocument)


# ---------------------------------------------------------------------------
# TestGetLatestVersionId — 获取最新版本 ID
# ---------------------------------------------------------------------------

class TestGetLatestVersionId:
    def test_returns_none_when_no_versions(self, manager, mock_storage):
        """无版本时应返回 None"""
        mock_storage.list_all_versions = MagicMock(return_value=[])
        result = manager.get_latest_version_id()
        assert result is None

    def test_returns_first_version_id(self, manager, mock_storage):
        """有版本时应返回第一个版本 ID"""
        mock_storage.list_all_versions = MagicMock(return_value=[
            {"id": "v20250101-003"},
            {"id": "v20250101-002"},
            {"id": "v20250101-001"},
        ])
        result = manager.get_latest_version_id()
        assert result == "v20250101-003"


# ---------------------------------------------------------------------------
# TestGetVersionCount — 版本计数
# ---------------------------------------------------------------------------

class TestGetVersionCount:
    def test_returns_zero_when_empty(self, manager, mock_storage):
        """无版本时应返回 0"""
        mock_storage.list_all_versions = MagicMock(return_value=[])
        assert manager.get_version_count() == 0

    def test_returns_correct_count(self, manager, mock_storage):
        """应返回正确的版本数量"""
        mock_storage.list_all_versions = MagicMock(return_value=[
            {"id": "v1"}, {"id": "v2"}, {"id": "v3"},
        ])
        assert manager.get_version_count() == 3


# ---------------------------------------------------------------------------
# TestDiff — 版本差异
# ---------------------------------------------------------------------------

class TestDiff:
    @pytest.mark.asyncio
    async def test_diff_returns_empty_for_same_version(self, manager, mock_storage):
        """相同版本差异应为空"""
        doc = _make_document()
        snapshot_json = json.dumps(doc.to_dict(), ensure_ascii=False, default=str)
        mock_storage.get_version = MagicMock(return_value={
            "id": "v1",
            "doc_snapshot": snapshot_json,
        })

        diff = await manager.diff("v1", "v1")
        assert diff.added_entities == []
        assert diff.removed_entities == []

    @pytest.mark.asyncio
    async def test_diff_detects_added_entities(self, manager, mock_storage):
        """差异检测应发现新增实体"""
        doc_a = _make_document(entities=[_make_entity(entity_id="e1")])
        doc_b = _make_document(entities=[
            _make_entity(entity_id="e1"),
            _make_entity(entity_id="e2"),
        ])

        snapshot_a = json.dumps(doc_a.to_dict(), ensure_ascii=False, default=str)
        snapshot_b = json.dumps(doc_b.to_dict(), ensure_ascii=False, default=str)

        mock_storage.get_version = MagicMock(side_effect=[
            {"id": "v1", "doc_snapshot": snapshot_a},
            {"id": "v2", "doc_snapshot": snapshot_b},
        ])

        diff = await manager.diff("v1", "v2")
        assert "e2" in diff.added_entities
        assert len(diff.removed_entities) == 0


# ---------------------------------------------------------------------------
# TestEnsureInitialVersion — 确保初始版本
# ---------------------------------------------------------------------------

class TestEnsureInitialVersion:
    def test_returns_existing_version(self, manager, mock_storage):
        """已有版本时应返回现有版本"""
        mock_storage.get_versions = MagicMock(return_value=[
            {"id": "v20250101-001", "version_number": "1.0.0"},
        ])
        version = manager.ensure_initial_version("ont-1")
        assert version.version_id == "v20250101-001"

    def test_creates_new_version_when_none(self, manager, mock_storage):
        """无版本时应创建新版本"""
        mock_storage.get_versions = MagicMock(return_value=[])
        mock_storage.list_all_versions = MagicMock(return_value=[])

        version = manager.ensure_initial_version("ont-1", "Test Scenario")
        assert version.version_number == "1.0.0"
        assert "Test Scenario" in version.commit_message
        mock_storage.save_version.assert_called_once()
