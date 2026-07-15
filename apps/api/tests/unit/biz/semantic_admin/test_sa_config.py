"""sa_config 单元测试：6 层模块 CRUD + 领域语义便捷方法。

测试范围：
  T1 存储层：SQLite upsert / get / list / delete / JSON 字段
  T2 领域模型：SaConfigEntry 校验 (strict + extra=forbid)
  T3 impl：SaConfigManager.set/get/list/delete + 语义迁移
  T4 services：Dict 返回 + 错误映射
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


# ---------------------------------------------------------------------------
# T1 SQLite storage (用 tmp_path 真实 DB)
# ---------------------------------------------------------------------------

class TestSQLiteSaConfigStorage:
    def _storage(self, tmp_path):
        from odap.biz.semantic_admin.sa_config.storage import SQLiteSaConfigStorage

        db = str(tmp_path / "sa_cfg.db")
        return SQLiteSaConfigStorage(db_path=db)

    def test_set_and_get_roundtrip_json(self, tmp_path):
        """T1-a: dict value 存入→取出，JSON 结构无损"""
        s = self._storage(tmp_path)
        from odap.biz.semantic_admin.sa_config.models import SaConfigEntry

        entry = SaConfigEntry(
            scope="pipeline:thresholds",
            config_key="quality_gate_v1",
            config_value={"overall": 0.7, "per_metric_floor": 0.4, "levels": ["L1", "L2"]},
            updated_by="tester",
        )
        saved = s.save_config(entry)
        got = s.get_config(saved.scope, saved.config_key)
        assert got is not None
        assert got.config_value["overall"] == 0.7
        assert got.config_value["per_metric_floor"] == 0.4
        assert got.config_value["levels"] == ["L1", "L2"]
        assert got.updated_by == "tester"

    def test_upsert_same_scope_key_overwrites_value(self, tmp_path):
        """T1-b: 重复 (scope,key) 保存触发 upsert"""
        s = self._storage(tmp_path)
        from odap.biz.semantic_admin.sa_config.models import SaConfigEntry

        e1 = SaConfigEntry(scope="domain:alpha", config_key="x", config_value={"v": 1})
        e2 = SaConfigEntry(scope="domain:alpha", config_key="x", config_value={"v": 2})
        s.save_config(e1)
        s.save_config(e2)
        # count should be 1 (not 2): UNIQUE constraint on (scope, key)
        lst = s.list_configs(scope="domain:alpha")
        assert len(lst) == 1, f"upsert 失败，期望记录数=1，实际={len(lst)}"
        assert lst[0].config_value["v"] == 2

    def test_get_missing_returns_none(self, tmp_path):
        """T1-c: 不存在返回 None，不抛异常"""
        s = self._storage(tmp_path)
        assert s.get_config("nope", "nope") is None
        assert s.get_value("nope", "nope") is None

    def test_list_and_delete(self, tmp_path):
        """T1-d: list 返回全部；delete 不存在返回 False"""
        s = self._storage(tmp_path)
        from odap.biz.semantic_admin.sa_config.models import SaConfigEntry

        s.save_config(SaConfigEntry(scope="A", config_key="k1", config_value={"a": 1}))
        s.save_config(SaConfigEntry(scope="A", config_key="k2", config_value={"b": 2}))
        s.save_config(SaConfigEntry(scope="B", config_key="k1", config_value={"c": 3}))

        assert len(s.list_configs()) == 3
        assert len(s.list_configs(scope="A")) == 2
        assert len(s.list_configs(scope="ZZZ")) == 0

        # delete 不存在
        assert s.delete_config("ZZZ", "nope") is False
        # delete 存在
        assert s.delete_config("A", "k1") is True
        assert len(s.list_configs(scope="A")) == 1


# ---------------------------------------------------------------------------
# T2 SaConfigEntry model strict validation
# ---------------------------------------------------------------------------

class TestSaConfigEntryValidation:
    def test_extra_fields_forbidden(self):
        """T2-a: strict + extra=forbid，未知字段抛 ValueError"""
        from pydantic import ValidationError
        from odap.biz.semantic_admin.sa_config.models import SaConfigEntry

        with pytest.raises(ValidationError):
            SaConfigEntry(
                scope="s",
                config_key="k",
                config_value={},
                unknown_field_123="oops",  # extra="forbid"
            )

    def test_scope_or_key_missing_raises(self):
        """T2-b: scope / config_key 必填"""
        from pydantic import ValidationError
        from odap.biz.semantic_admin.sa_config.models import SaConfigEntry

        with pytest.raises(ValidationError):
            SaConfigEntry(scope="", config_key="k")  # min_length=1


# ---------------------------------------------------------------------------
# T3 SaConfigManager impl + domain semantic
# ---------------------------------------------------------------------------

class TestSaConfigManager:
    @staticmethod
    def _mgr(tmp_path):
        from odap.biz.semantic_admin.sa_config.impl import SaConfigManager
        from odap.biz.semantic_admin.sa_config.storage import SQLiteSaConfigStorage

        storage = SQLiteSaConfigStorage(db_path=str(tmp_path / "sa.db"))
        return SaConfigManager(storage=storage)

    def test_set_and_get_domain_semantic_roundtrip(self, tmp_path):
        """T3-a: set_domain_semantic → get_domain_semantic 结果一致"""
        mgr = self._mgr(tmp_path)
        sem = {
            "domain": "ecommerce",
            "display_name": "电商标准域",
            "en_mapping": {"SKU": "SKU", "SPU": "SPU"},
            "canonical_terms": {"SKU": {"synonyms": ["库存单元"]}},
            "expansion_rules": [],
        }
        mgr.set_domain_semantic("ecommerce", sem, updated_by="tester")
        got = mgr.get_domain_semantic("ecommerce")
        assert got is not None
        assert got["display_name"] == "电商标准域"
        assert got["canonical_terms"]["SKU"]["synonyms"][0] == "库存单元"

    def test_get_unknown_domain_returns_none_without_exception(self, tmp_path):
        """T3-b: 获取未知 code 不抛异常，返回 None（或者 fallback legacy，但 legacy 已删）"""
        mgr = self._mgr(tmp_path)
        # unknown domain code (not in builtin set) → None
        assert mgr.get_domain_semantic("___nope___") is None

    def test_list_and_delete_manager(self, tmp_path):
        """T3-c: list / delete 透传底层 storage"""
        mgr = self._mgr(tmp_path)
        mgr.set("qg", "t1", {"a": 1})
        mgr.set("qg", "t2", {"b": 2})
        got = mgr.list(scope="qg")
        assert len(got) == 2
        mgr.delete("qg", "t1")
        assert len(mgr.list(scope="qg")) == 1


# ---------------------------------------------------------------------------
# T4 SaConfigService: Dict returns + error mapping
# ---------------------------------------------------------------------------

class TestSaConfigService:
    @staticmethod
    def _svc(tmp_path):
        from odap.biz.semantic_admin.sa_config.impl import SaConfigManager
        from odap.biz.semantic_admin.sa_config.services import SaConfigService
        from odap.biz.semantic_admin.sa_config.storage import SQLiteSaConfigStorage

        storage = SQLiteSaConfigStorage(db_path=str(tmp_path / "sa_svc.db"))
        return SaConfigService(manager=SaConfigManager(storage=storage))

    def test_set_get_crud_status_ok(self, tmp_path):
        """T4-a: set / get / list / delete 返回 status=ok"""
        svc = self._svc(tmp_path)
        s = svc.set_config("x", "y", {"foo": "bar"}, updated_by="u")
        assert s["status"] == "ok"
        g = svc.get_config("x", "y")
        assert g["status"] == "ok"
        assert g["config_value"] == {"foo": "bar"}
        lst = svc.list_configs(scope="x")
        assert lst["status"] == "ok" and lst["count"] == 1
        d = svc.delete_config("x", "y")
        assert d["status"] == "ok" and d["deleted"] is True

    def test_missing_args_return_error_status(self, tmp_path):
        """T4-b: 空 scope/key → status=error（不抛 HTTP 异常——服务层不抛）"""
        svc = self._svc(tmp_path)
        g = svc.get_config("", "y")
        assert g["status"] == "error"
        s = svc.set_config("", "y", {"a": 1})
        assert s["status"] == "error"
        d = svc.delete_config("x", "")
        assert d["status"] == "error"

    def test_set_domain_semantic_non_dict_returns_error(self, tmp_path):
        """T4-c: semantic 必填且为 dict"""
        svc = self._svc(tmp_path)
        r = svc.set_domain_semantic("z", semantic="not_a_dict")  # type: ignore
        assert r["status"] == "error"


# ---------------------------------------------------------------------------
# T5 Integration: seed_sanguo_xiyou 路径 — 通过 sa_config 读 sanguo/xiyou 语义
# ---------------------------------------------------------------------------

class TestSeedViaSaConfig:
    def test_get_domain_semantic_after_manual_seed(self, tmp_path):
        """T5-a: 手动写入 2 条最小 semantic → 可被 SaConfigManager 正确读出"""
        from odap.biz.semantic_admin.sa_config.impl import SaConfigManager
        from odap.biz.semantic_admin.sa_config.storage import SQLiteSaConfigStorage

        storage = SQLiteSaConfigStorage(db_path=str(tmp_path / "seed.db"))
        mgr = SaConfigManager(storage=storage)

        # seed 2 minimal domains
        for code, disp in [("sanguo", "三国演示"), ("xiyou", "西游演示")]:
            mgr.set_domain_semantic(
                code,
                {
                    "domain": code,
                    "display_name": disp,
                    "en_mapping": {"势力": "Faction", "人物": "Character"},
                    "canonical_terms": {},
                    "expansion_rules": [],
                },
                updated_by="seed_manual",
            )

        s = mgr.get_domain_semantic("sanguo")
        x = mgr.get_domain_semantic("xiyou")
        assert s is not None and s["display_name"] == "三国演示"
        assert x is not None and x["display_name"] == "西游演示"
