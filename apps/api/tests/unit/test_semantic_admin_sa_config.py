"""语义管理台 sa_config 模块单元测试。

覆盖：
  - storage: SQLiteSaConfigStorage — CRUD、JSON 序列化、唯一键冲突、删除未存在
  - models: SaConfigEntry — 严格校验、to_row/from_row 往返、JSON 值
  - manager: SaConfigManager — set/get/delete/list、domain_semantic 便捷方法
  - services: SaConfigService — 错误码格式、空参防御、Dict 返回

所有存储测试均使用 tmp_path 创建真实 SQLite 文件（禁止 MagicMock 模拟数据库）。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "sa_config.db")


@pytest.fixture
def storage(db_path: str):
    from odap.biz.semantic_admin.sa_config.storage import Storage

    return Storage(db_path=db_path)


@pytest.fixture
def manager(storage):
    from odap.biz.semantic_admin.sa_config.impl import SaConfigManager

    return SaConfigManager(storage=storage)


@pytest.fixture
def service(manager):
    from odap.biz.semantic_admin.sa_config.services import SaConfigService

    return SaConfigService(manager=manager)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestSaConfigEntryModel:
    def test_defaults_fill_id_and_timestamps(self):
        from odap.biz.semantic_admin.sa_config.models import SaConfigEntry

        e = SaConfigEntry(scope="global", config_key="k", config_value={"a": 1})
        assert e.id and len(e.id) > 0
        assert e.scope == "global"
        assert e.config_key == "k"
        assert e.config_value == {"a": 1}
        assert e.created_at.endswith("+00:00") or "T" in e.created_at
        assert e.updated_at

    def test_to_row_roundtrip_via_from_row(self):
        from odap.biz.semantic_admin.sa_config.models import SaConfigEntry

        src = SaConfigEntry(
            scope="domain:demo",
            config_key="semantic_layer",
            config_value={"terms": ["a", "b"], "level": 3},
            updated_by="tester",
        )
        row = src.to_row()
        assert row["scope"] == "domain:demo"
        assert row["config_key"] == "semantic_layer"
        parsed_val = json.loads(row["config_value_json"])
        assert parsed_val["level"] == 3
        rebuilt = SaConfigEntry.from_row(row)
        assert rebuilt.config_value["terms"] == ["a", "b"]
        assert rebuilt.updated_by == "tester"

    def test_strict_rejects_extra_fields(self):
        from pydantic import ValidationError
        from odap.biz.semantic_admin.sa_config.models import SaConfigEntry

        with pytest.raises(ValidationError):
            SaConfigEntry(scope="g", config_key="k", unknown_field="x")

    def test_scope_and_key_min_length(self):
        from pydantic import ValidationError
        from odap.biz.semantic_admin.sa_config.models import SaConfigEntry

        with pytest.raises(ValidationError):
            SaConfigEntry(scope="", config_key="k")
        with pytest.raises(ValidationError):
            SaConfigEntry(scope="g", config_key="")

    def test_config_value_json_coercion_on_load(self):
        from odap.biz.semantic_admin.sa_config.models import SaConfigEntry

        row = {
            "id": "x",
            "scope": "g",
            "config_key": "k",
            "config_value": {},
            "config_value_json": '{"foo":"bar"}',
            "updated_by": "s",
            "created_at": "t0",
            "updated_at": "t1",
        }
        e = SaConfigEntry.from_row(row)
        assert e.config_value == {"foo": "bar"}


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


class TestSQLiteSaConfigStorage:
    def test_save_and_get_roundtrip(self, storage):
        from odap.biz.semantic_admin.sa_config.models import SaConfigEntry

        entry = SaConfigEntry(
            scope="domain:sanguo",
            config_key="semantic_layer",
            config_value={"layer": "story", "confidence": 0.9},
            updated_by="seed",
        )
        saved = storage.save_config(entry)
        assert saved.id == entry.id
        fetched = storage.get_config("domain:sanguo", "semantic_layer")
        assert fetched is not None
        assert fetched.config_value["layer"] == "story"
        assert fetched.config_value["confidence"] == 0.9

    def test_save_upsert_same_scope_key_updates_value(self, storage):
        from odap.biz.semantic_admin.sa_config.models import SaConfigEntry

        e1 = SaConfigEntry(scope="g", config_key="k", config_value={"v": 1})
        storage.save_config(e1)
        e2 = SaConfigEntry(scope="g", config_key="k", config_value={"v": 2, "extra": True})
        saved2 = storage.save_config(e2)
        # 应该保留原 id，因为同一个 (scope, key)
        fetched = storage.get_config("g", "k")
        assert fetched.config_value == {"v": 2, "extra": True}
        # 两种 id：e2.id 或者 e1.id，只要 value 是新的即可
        assert fetched.id in (e1.id, e2.id, saved2.id)

    def test_get_config_not_found_returns_none(self, storage):
        assert storage.get_config("nope", "nothing") is None
        assert storage.get_value("nope", "nothing") is None

    def test_list_configs_scope_filter(self, storage):
        from odap.biz.semantic_admin.sa_config.models import SaConfigEntry

        for s in ("A", "A", "B"):
            storage.save_config(
                SaConfigEntry(scope=s, config_key=f"k-{os.urandom(2).hex()}", config_value={})
            )
        lst_a = storage.list_configs("A")
        assert len(lst_a) == 2
        lst_all = storage.list_configs()
        assert len(lst_all) == 3

    def test_delete_existing_vs_missing(self, storage):
        from odap.biz.semantic_admin.sa_config.models import SaConfigEntry

        storage.save_config(SaConfigEntry(scope="g", config_key="k", config_value={}))
        assert storage.delete_config("g", "k") is True
        assert storage.delete_config("g", "k") is False
        assert storage.delete_config("not", "there") is False


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class TestSaConfigManager:
    def test_set_and_get_domain_semantic(self, manager):
        semantic = {
            "core_terms": ["刘备", "关羽", "张飞"],
            "relations": {"结义": ["trilateral", "oath"]},
        }
        manager.set_domain_semantic("sanguo", semantic, updated_by="seed")
        got = manager.get_domain_semantic("sanguo")
        assert got is not None
        assert got["core_terms"] == ["刘备", "关羽", "张飞"]

    def test_set_and_get_arbitrary_scalar_wrapped(self, manager):
        manager.set("pipeline:thresholds", "min_confidence", 0.7)
        got = manager.get("pipeline:thresholds", "min_confidence")
        assert got == {"value": 0.7}

    def test_list_returns_flat_dicts(self, manager):
        manager.set("g", "k1", {"a": 1})
        manager.set("g", "k2", {"b": 2})
        items = manager.list("g")
        assert len(items) == 2
        for it in items:
            assert set(it.keys()) == {
                "id",
                "scope",
                "config_key",
                "config_value",
                "updated_by",
                "created_at",
                "updated_at",
            }

    def test_delete_and_missing_get_returns_default(self, manager):
        manager.set("g", "k", {"x": 1})
        assert manager.delete("g", "k") is True
        assert manager.get("g", "k", "DEFAULT") == "DEFAULT"


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


class TestSaConfigService:
    def test_set_config_empty_scope_returns_error_dict(self, service):
        r = service.set_config("", "k", {"a": 1})
        assert r["status"] == "error"
        assert "不能为空" in r["message"]

    def test_set_config_happy_returns_ok_flat(self, service):
        r = service.set_config("domain:demo", "semantic_layer", {"terms": ["x"]})
        assert r["status"] == "ok"
        assert r["scope"] == "domain:demo"
        assert isinstance(r["config_value"], dict)

    def test_get_config_happy_and_missing(self, service):
        service.set_config("g", "k", {"a": 1})
        r = service.get_config("g", "k")
        assert r["status"] == "ok" and r["config_value"] == {"a": 1}
        r_miss = service.get_config("g", "not-exist", {"fallback": True})
        assert r_miss["config_value"] == {"fallback": True}

    def test_list_configs_empty_ok_and_count_matches(self, service):
        r = service.list_configs()
        assert r["status"] == "ok"
        assert r["count"] == 0
        service.set_config("g", "k1", {})
        service.set_config("g", "k2", {})
        r = service.list_configs("g")
        assert r["count"] == 2

    def test_delete_config_reports_whether_deleted(self, service):
        service.set_config("g", "k", {})
        r = service.delete_config("g", "k")
        assert r["status"] == "ok" and r["deleted"] is True
        r2 = service.delete_config("g", "k")
        assert r2["status"] == "ok" and r2["deleted"] is False

    def test_get_domain_semantic_empty_code_error(self, service):
        r = service.get_domain_semantic("")
        assert r["status"] == "error"

    def test_set_domain_semantic_non_dict_is_error(self, service):
        r = service.set_domain_semantic("demo", "not-a-dict")
        assert r["status"] == "error"
        assert "dict" in r["message"]

    def test_set_domain_semantic_then_get_roundtrip(self, service):
        semantic = {
            "stoplist": ["是", "的"],
            "semantic_hints": {"角色": ["刘备", "曹操"]},
        }
        w = service.set_domain_semantic("demo", semantic, updated_by="tester")
        assert w["status"] == "ok"
        r = service.get_domain_semantic("demo")
        assert r["status"] == "ok"
        assert r["semantic"]["stoplist"] == ["是", "的"]
        assert r["domain_code"] == "demo"

    def test_ensure_builtin_domains_no_legacy_does_not_crash(self, service):
        # 旧的 semantic_config.py 已删除，确保不会抛异常
        r = service.ensure_builtin_domains(force_overwrite=False)
        assert r["status"] == "ok"
        assert "scopes" in r
        assert "migrated" in r
