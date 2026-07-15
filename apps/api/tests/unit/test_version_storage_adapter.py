"""test_version_storage_adapter.py - VersionStorageAdapter 单元测试

测试双存储版本适配器的写入、读取、合并去重和容错。
"""

import pytest


# ---------------------------------------------------------------------------
# 延迟导入 fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def primary_storage(tmp_path):
    """创建主存储（使用真实 SQLite）"""
    try:
        from odap.biz.core.ontology.design.engine.storage.sqlite_engine_storage import SQLiteEngineStorage
    except ImportError:
        pytest.skip("SQLiteEngineStorage not importable")
    return SQLiteEngineStorage(db_path=str(tmp_path / "primary.db"))


@pytest.fixture
def secondary_storage(tmp_path):
    """创建备用存储（使用真实 SQLite）"""
    try:
        from odap.biz.core.ontology.design.engine.storage.sqlite_engine_storage import SQLiteEngineStorage
    except ImportError:
        pytest.skip("SQLiteEngineStorage not importable")
    return SQLiteEngineStorage(db_path=str(tmp_path / "secondary.db"))


@pytest.fixture
def adapter(primary_storage, secondary_storage):
    """创建 VersionStorageAdapter"""
    try:
        from odap.biz.core.ontology.design.engine.storage.version_storage_adapter import VersionStorageAdapter
    except ImportError:
        pytest.skip("VersionStorageAdapter not importable")
    return VersionStorageAdapter(primary_storage, secondary_storage)


def _make_version(version_id="v-1", ontology_id="ont-1", version_number="1.0.0",
                  changelog="initial", status="active", snapshot=None):
    """工厂函数：构造版本数据"""
    return {
        "version_id": version_id,
        "ontology_id": ontology_id,
        "version_number": version_number,
        "changelog": changelog,
        "valid_time": "2026-01-01T00:00:00",
        "transaction_time": "2026-01-01T00:00:00",
        "status": status,
        "snapshot": snapshot or {},
    }


# ---------------------------------------------------------------------------
# TestSaveVersion
# ---------------------------------------------------------------------------

class TestSaveVersion:
    def test_save_writes_to_both_storages(self, adapter, primary_storage, secondary_storage):
        version = _make_version(version_id="v-dual-1")
        adapter.save_version(version)

        # 主存储应有数据
        result_primary = primary_storage.get_version("v-dual-1")
        assert result_primary is not None
        assert result_primary["version_id"] == "v-dual-1"

        # 备用存储应有数据
        result_secondary = secondary_storage.get_version("v-dual-1")
        assert result_secondary is not None
        assert result_secondary["version_id"] == "v-dual-1"

    def test_save_returns_version(self, adapter):
        version = _make_version(version_id="v-ret")
        result = adapter.save_version(version)
        assert result["version_id"] == "v-ret"

    def test_save_secondary_failure_does_not_block(self, adapter, primary_storage):
        """备用存储写入失败不应阻塞主存储"""
        # 替换备用存储为会抛异常的 mock
        class FailingStorage:
            def save_version(self, v):
                raise RuntimeError("secondary down")
            def get_version(self, vid):
                return None
            def list_versions(self, oid, page=1, page_size=20):
                return []

        adapter._secondary = FailingStorage()
        version = _make_version(version_id="v-fail-secondary")
        result = adapter.save_version(version)

        # 主存储应该成功
        assert result["version_id"] == "v-fail-secondary"
        primary_result = primary_storage.get_version("v-fail-secondary")
        assert primary_result is not None


# ---------------------------------------------------------------------------
# TestGetVersion
# ---------------------------------------------------------------------------

class TestGetVersion:
    def test_get_from_primary_first(self, adapter):
        version = _make_version(version_id="v-primary-first")
        adapter.save_version(version)

        result = adapter.get_version("v-primary-first")
        assert result is not None
        assert result["version_id"] == "v-primary-first"

    def test_get_falls_back_to_secondary(self, adapter, primary_storage, secondary_storage):
        """主存储没有数据时，从备用存储读取"""
        version = _make_version(version_id="v-secondary-only")
        # 只写入备用存储
        secondary_storage.save_version(version)
        # 确认主存储没有
        assert primary_storage.get_version("v-secondary-only") is None

        result = adapter.get_version("v-secondary-only")
        assert result is not None
        assert result["version_id"] == "v-secondary-only"

    def test_get_returns_none_when_not_found(self, adapter):
        result = adapter.get_version("nonexistent-id")
        assert result is None


# ---------------------------------------------------------------------------
# TestListVersions
# ---------------------------------------------------------------------------

class TestListVersions:
    def test_list_merges_results(self, adapter, primary_storage, secondary_storage):
        """两个存储都有数据时，合并结果"""
        v1 = _make_version(version_id="v-merge-1", ontology_id="ont-merge")
        v2 = _make_version(version_id="v-merge-2", ontology_id="ont-merge")

        # v1 只在主存储
        primary_storage.save_version(v1)
        # v2 只在备用存储
        secondary_storage.save_version(v2)

        results = adapter.list_versions("ont-merge")
        ids = [r["version_id"] for r in results]
        assert "v-merge-1" in ids
        assert "v-merge-2" in ids

    def test_list_deduplicates(self, adapter):
        """两个存储有相同 version_id 时，去重"""
        version = _make_version(version_id="v-dup", ontology_id="ont-dup")
        adapter.save_version(version)  # 写入两个存储

        results = adapter.list_versions("ont-dup")
        ids = [r["version_id"] for r in results]
        # 不应出现重复
        assert ids.count("v-dup") == 1

    def test_list_primary_failure_returns_secondary(self, adapter, secondary_storage):
        """主存储失败时，返回备用存储的数据"""
        version = _make_version(version_id="v-sec-only", ontology_id="ont-sec")
        secondary_storage.save_version(version)

        class FailingPrimary:
            def save_version(self, v):
                pass
            def get_version(self, vid):
                return None
            def list_versions(self, oid, page=1, page_size=20):
                raise RuntimeError("primary down")

        adapter._primary = FailingPrimary()
        results = adapter.list_versions("ont-sec")
        ids = [r["version_id"] for r in results]
        assert "v-sec-only" in ids

    def test_list_empty_when_no_data(self, adapter):
        results = adapter.list_versions("ont-nonexistent")
        assert results == []
