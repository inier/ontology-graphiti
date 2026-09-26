"""Semantic Admin - USL Manager Storage 层单元测试。

覆盖（全部 tmp_path 真实 SQLite DB，严禁 MagicMock 替 storage）：
 1. 6 大领域模型：字段默认值、UUID 唯一性、容器 default_factory、Enum 值/双继承
 2. Domain CRUD + 分页 + get_by_code + delete 级联
 3. Term   CRUD + 分页 + semantic_type 过滤 + 同义词模糊搜索 + UNIQUE冲突
 4. Term: stoplist_flag 切换（False->True->False）持久化
 5. Term JSON roundtrip：synonyms/near_synonyms/aliases 写入→读取后类型、顺序、元素一致
 6. Hierarchy CRUD + confidence 0~1 校验 + UNIQUE(parent/child/rel_type) 幂等
 7. PropertySpec CRUD + for_term 过滤 + UNIQUE(domain,for_term,prop_name)
 8. DisjointPair CRUD + term_a==term_b 业务层禁止（UNIQUE(domain,term_a,term_b)）
 9. Cardinality CRUD + rel_name 过滤 + max_card=None 存 NULL
10. Domain en_mapping Dict[str,str] JSON roundtrip
11. get 不存在返回 None；delete 不存在返回 False
12. UNIQUE code 冲突不抛异常（ON CONFLICT DO UPDATE 幂等）
13. Seed 迁移（三国 + 西游）跑 2 次，各表 COUNT 一致（幂等性）
14. delete_domain 级联删除：子表全部清空
15. 非法 JSON 文本容错：_loads 遇到损坏 JSON 返回 default 不抛
"""
from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest

from odap.biz.semantic_admin.usl_manager.models import (
    DataType,
    HierarchyRel,
    SemanticType,
    UslCardinality,
    UslDisjointPair,
    UslDomain,
    UslHierarchy,
    UslPropertySpec,
    UslTerm,
)
from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage


# =====================================================================
# Helpers / 工厂
# =====================================================================


ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def _make_domain(code: str = "test", **overrides: Any) -> Dict[str, Any]:
    defaults = dict(
        id=str(uuid.uuid4()),
        code=code,
        display_name=f"{code}-display",
        description=f"{code} 领域",
        en_mapping={"势力": "Faction", "人物": "Character"},
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    defaults.update(overrides)
    return defaults


def _make_term(domain_id: str, canonical: str = "人物", **overrides: Any) -> Dict[str, Any]:
    defaults = dict(
        id=str(uuid.uuid4()),
        domain_id=domain_id,
        canonical=canonical,
        semantic_type=SemanticType.OBJECT_TYPE.value,
        synonyms=["角色", "人"],
        near_synonyms=["武将", "文臣"],
        aliases=["英雄"],
        stoplist_flag=False,
        definition=f"规范术语: {canonical}",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    defaults.update(overrides)
    return defaults


# =====================================================================
# 1. 领域模型（Pydantic）基础属性
# =====================================================================


class TestDomainModels:
    """6 大模型的默认值 / UUID / 容器 default_factory / Enum 双继承."""

    # -------- UslDomain --------

    def test_domain_defaults_uuid_unique(self):
        a = UslDomain(code="a", display_name="A")
        b = UslDomain(code="b", display_name="B")
        assert a.id != b.id
        assert len(a.id) == 36

    def test_domain_en_mapping_isolated(self):
        a = UslDomain(code="a", display_name="A")
        a.en_mapping["x"] = "X"
        b = UslDomain(code="b", display_name="B")
        assert "x" not in b.en_mapping

    def test_domain_created_at_is_iso_string(self):
        d = UslDomain(code="a", display_name="A")
        assert ISO8601_RE.match(d.created_at)
        assert ISO8601_RE.match(d.updated_at)

    # -------- UslTerm --------

    def test_term_synonyms_not_shared(self):
        a = UslTerm(domain_id="d", canonical="c1")
        b = UslTerm(domain_id="d", canonical="c2")
        a.synonyms.append("x")
        a.near_synonyms.append("y")
        a.aliases.append("z")
        assert b.synonyms == []
        assert b.near_synonyms == []
        assert b.aliases == []

    def test_term_semantic_type_is_str_enum(self):
        """SemanticType 必须 (str, Enum) 双继承：str(instance) == .value"""
        t = UslTerm(domain_id="d", canonical="c", semantic_type=SemanticType.LINK_TYPE)
        assert t.semantic_type == "关系类型"
        assert str(t.semantic_type) == "关系类型"
        assert t.semantic_type.value == "关系类型"

    def test_term_stoplist_default_false(self):
        t = UslTerm(domain_id="d", canonical="c")
        assert t.stoplist_flag is False

    def test_term_model_config_strict_extra_forbid(self):
        """strict=True, extra='forbid' → 构造时传非法字段抛 ValueError"""
        with pytest.raises(Exception):
            UslTerm(domain_id="d", canonical="c", unknown_field="boom")  # type: ignore[call-arg]

    # -------- UslHierarchy --------

    def test_hierarchy_confidence_bounds(self):
        UslHierarchy(domain_id="d", parent_term="A", child_term="B", confidence=0.0)
        UslHierarchy(domain_id="d", parent_term="A", child_term="B", confidence=1.0)
        with pytest.raises(ValueError):
            UslHierarchy(domain_id="d", parent_term="A", child_term="B", confidence=1.5)
        with pytest.raises(ValueError):
            UslHierarchy(domain_id="d", parent_term="A", child_term="B", confidence=-0.1)

    def test_hierarchy_rel_type_is_str_enum(self):
        h = UslHierarchy(domain_id="d", parent_term="A", child_term="B",
                         rel_type=HierarchyRel.PART_OF)
        assert h.rel_type == "PART_OF"
        assert isinstance(h.rel_type, str)

    # -------- UslPropertySpec --------

    def test_prop_spec_data_type_enum(self):
        for t in DataType:
            spec = UslPropertySpec(domain_id="d", for_term="人物", prop_name="x", data_type=t)
            assert spec.data_type.value == t.value
            assert isinstance(spec.data_type, str)

    def test_prop_spec_unit_optional(self):
        s1 = UslPropertySpec(domain_id="d", for_term="T", prop_name="x")
        assert s1.unit is None
        s2 = UslPropertySpec(domain_id="d", for_term="T", prop_name="x", unit="岁")
        assert s2.unit == "岁"

    # -------- UslDisjointPair --------

    def test_dj_pair_reason_default(self):
        p = UslDisjointPair(domain_id="d", term_a="A", term_b="B")
        assert p.reason == ""

    # -------- UslCardinality --------

    def test_card_min_max_bounds(self):
        c = UslCardinality(domain_id="d", rel_name="R", domain_term="A", range_term="B")
        assert c.min_card == 0
        assert c.max_card is None
        # min_card 必须 >= 0
        with pytest.raises(ValueError):
            UslCardinality(domain_id="d", rel_name="R", domain_term="A",
                           range_term="B", min_card=-1)
        # max_card None 或 > 0
        with pytest.raises(ValueError):
            UslCardinality(domain_id="d", rel_name="R", domain_term="A",
                           range_term="B", max_card=0)


# =====================================================================
# 2. Domain CRUD
# =====================================================================


class TestStorageDomain:
    """SQLiteUslStorage Domain 相关."""

    def test_save_and_get_domain(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        d = _make_domain(code="sanguo")
        storage.save_domain(d)
        got = storage.get_domain(d["id"])
        assert got is not None
        assert got["code"] == "sanguo"
        assert got["en_mapping"] == {"势力": "Faction", "人物": "Character"}
        assert ISO8601_RE.match(got["created_at"])

    def test_get_domain_none(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        assert storage.get_domain("no-such-id") is None

    def test_get_domain_by_code(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        storage.save_domain(_make_domain(code="foo"))
        got = storage.get_domain_by_code("foo")
        assert got is not None and got["code"] == "foo"
        assert storage.get_domain_by_code("bar") is None

    def test_list_domains_pagination(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        for i in range(7):
            storage.save_domain(_make_domain(code=f"d{i}"))
        items, total = storage.list_domains(page=1, page_size=3)
        assert total == 7
        assert len(items) == 3
        items2, _ = storage.list_domains(page=3, page_size=3)
        assert len(items2) == 1

    def test_unique_code_conflict_update_instead_of_error(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        d1 = _make_domain(code="shared", display_name="Old",
                          en_mapping={"a": "A"})
        storage.save_domain(d1)
        d2 = _make_domain(code="shared", display_name="New",
                          en_mapping={"b": "B"})
        storage.save_domain(d2)
        # 同 code：记录总数仍为 1，且 en_mapping 被更新为新值
        _, total = storage.list_domains()
        assert total == 1
        got = storage.get_domain_by_code("shared")
        assert got is not None
        assert got["display_name"] == "New"
        assert got["en_mapping"] == {"b": "B"}

    def test_delete_domain_reports_counts_and_removes_domain_row(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        unknown = storage.delete_domain("nope")
        assert unknown["deleted"] is False
        assert unknown["resolved"] is False
        d = _make_domain(code="x")
        storage.save_domain(d)
        result = storage.delete_domain(d["id"])
        assert result["deleted"] is True
        assert result["code"] == "x"
        assert result["counts"]["usl_domains"] == 1
        assert storage.get_domain(d["id"]) is None
        assert storage.get_domain("x") is None

    def test_delete_domain_unknown_ref_deletes_nothing(self, tmp_path: Path):
        """解析不到的 ref 必须一行都不删。

        旧实现无条件 `DELETE FROM usl_terms WHERE domain_id = <传入值>`：传一个不存在
        的 ref 时，任何 domain_id 字面等于它的子记录都会被清掉，而领域行一行没删、
        还返回 False（毁数据 + 报失败）。
        """
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        d = _make_domain(code="keep")
        storage.save_domain(d)
        storage.save_term(_make_term("keep", canonical="T1"))

        result = storage.delete_domain("ghost-code")

        assert result["deleted"] is False
        _, total = storage.list_terms(domain_id="keep", page_size=100)
        assert total == 1
        assert storage.get_domain("keep") is not None

    def test_delete_domain_cascades_all_child_tables(self, tmp_path: Path):
        """级联必须同时清掉 code 键与历史 uuid 键写下的子记录。

        子表 domain_id 列没有外键，历史上被两套值写过（前端传 code、
        seed_sanguo_xiyou.py:554 传 uuid），所以这个用例刻意两种键都写，
        并用裸 SQL COUNT 断言 —— 走 list_* 会被读路径的双键展开掩盖漏删。
        """
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        d = _make_domain(code="casc")
        storage.save_domain(d)
        did = d["id"]
        # 一半用 uuid 键（seed 迁移的写法），一半用 code 键（前端的写法）
        storage.save_term(_make_term(did, canonical="T-uuid"))
        storage.save_term(_make_term("casc", canonical="T-code"))
        storage.save_hierarchy({
            "id": str(uuid.uuid4()), "domain_id": did,
            "parent_term": "A", "child_term": "B", "rel_type": "IS_A",
            "confidence": 1.0, "created_at": datetime.now(timezone.utc).isoformat(),
        })
        storage.save_hierarchy({
            "id": str(uuid.uuid4()), "domain_id": "casc",
            "parent_term": "C", "child_term": "D", "rel_type": "IS_A",
            "confidence": 1.0, "created_at": datetime.now(timezone.utc).isoformat(),
        })
        storage.save_property_spec({
            "id": str(uuid.uuid4()), "domain_id": did,
            "for_term": "T1", "prop_name": "name", "data_type": "STRING",
            "unit": None, "required_flag": 1, "description": "",
        })
        storage.save_disjoint_pair({
            "id": str(uuid.uuid4()), "domain_id": "casc",
            "term_a": "T1", "term_b": "T2", "reason": "",
        })
        storage.save_cardinality({
            "id": str(uuid.uuid4()), "domain_id": did,
            "rel_name": "效力于", "domain_term": "T1", "range_term": "T2",
            "min_card": 0, "max_card": None,
        })

        result = storage.delete_domain(did)

        assert result["counts"]["usl_terms"] == 2
        assert result["counts"]["usl_hierarchies"] == 2
        assert result["counts"]["usl_property_specs"] == 1
        assert result["counts"]["usl_disjoint_pairs"] == 1
        assert result["counts"]["usl_cardinalities"] == 1
        conn = sqlite3.connect(str(tmp_path / "t.db"))
        try:
            for table in (
                "usl_terms",
                "usl_hierarchies",
                "usl_property_specs",
                "usl_disjoint_pairs",
                "usl_cardinalities",
            ):
                left = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE domain_id IN (?, ?)",
                    (did, "casc"),
                ).fetchone()[0]
                assert left == 0, f"{table} 仍有 {left} 条残留"
            domains_left = conn.execute(
                "SELECT COUNT(*) FROM usl_domains WHERE code = ? OR id = ?",
                ("casc", did),
            ).fetchone()[0]
            assert domains_left == 0
        finally:
            conn.close()


# =====================================================================
# 2b. domain_ref 双键归一（code / uuid split-brain 回归）
# =====================================================================


def _raw_child_count(db_path: Path, table: str, domain_id: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE domain_id = ?", (domain_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def _insert_legacy_uuid_child(db_path: Path, domain_id: str, term_id: str) -> None:
    """绕过写入归一，直接种一条历史 uuid 键的子记录（seed 迁移留下的形态）。"""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO usl_terms (id, domain_id, canonical, semantic_type,"
            " synonyms, near_synonyms, aliases, stoplist_flag, definition,"
            " created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                term_id, domain_id, "legacy-uuid-term", "对象类型",
                "[]", "[]", "[]", 0, "",
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


class TestDomainRefDualKey:
    """领域标识双键归一：读认两个键、写只落 code、删两个键都清。"""

    def test_get_domain_accepts_code_and_uuid(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        d = _make_domain(code="sanguo")
        storage.save_domain(d)
        by_code = storage.get_domain("sanguo")
        by_uuid = storage.get_domain(d["id"])
        assert by_code is not None and by_uuid is not None
        assert by_code["id"] == by_uuid["id"] == d["id"]
        assert storage.get_domain("ghost") is None

    def test_resolve_domain_ref_prefers_code(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        d = _make_domain(code="xiyou")
        storage.save_domain(d)
        assert storage.resolve_domain_ref("xiyou") == (d["id"], "xiyou")
        assert storage.resolve_domain_ref(d["id"]) == (d["id"], "xiyou")
        assert storage.resolve_domain_ref("") is None
        assert storage.resolve_domain_ref("ghost") is None

    def test_child_write_normalizes_uuid_to_code(self, tmp_path: Path):
        """写入收口：即使调用方传 uuid，落库的 domain_id 也是 code。"""
        db = tmp_path / "t.db"
        storage = SQLiteUslStorage(str(db))
        d = _make_domain(code="norm")
        storage.save_domain(d)
        did = d["id"]

        saved = storage.save_term(_make_term(did, canonical="T1"))
        assert saved["domain_id"] == "norm"
        assert _raw_child_count(db, "usl_terms", did) == 0
        assert _raw_child_count(db, "usl_terms", "norm") == 1

        storage.save_hierarchy({
            "id": str(uuid.uuid4()), "domain_id": did,
            "parent_term": "A", "child_term": "B", "rel_type": "IS_A",
            "confidence": 1.0, "created_at": datetime.now(timezone.utc).isoformat(),
        })
        assert _raw_child_count(db, "usl_hierarchies", "norm") == 1
        storage.save_property_spec({
            "id": str(uuid.uuid4()), "domain_id": did,
            "for_term": "T1", "prop_name": "p", "data_type": "STRING",
            "unit": None, "required_flag": 0, "description": "",
        })
        assert _raw_child_count(db, "usl_property_specs", "norm") == 1
        storage.save_disjoint_pair({
            "id": str(uuid.uuid4()), "domain_id": did,
            "term_a": "A", "term_b": "B", "reason": "",
        })
        assert _raw_child_count(db, "usl_disjoint_pairs", "norm") == 1
        storage.save_cardinality({
            "id": str(uuid.uuid4()), "domain_id": did,
            "rel_name": "r", "domain_term": "A", "range_term": "B",
            "min_card": 0, "max_card": None,
        })
        assert _raw_child_count(db, "usl_cardinalities", "norm") == 1

    def test_read_by_code_sees_legacy_uuid_rows(self, tmp_path: Path):
        """前端用 code 查术语时，必须看见 seed 迁移用 uuid 写下的历史行。"""
        db = tmp_path / "t.db"
        storage = SQLiteUslStorage(str(db))
        d = _make_domain(code="legacy")
        storage.save_domain(d)
        _insert_legacy_uuid_child(db, d["id"], str(uuid.uuid4()))
        storage.save_term(_make_term("legacy", canonical="new-term"))

        by_code, total_code = storage.list_terms(domain_id="legacy", page_size=100)
        by_uuid, total_uuid = storage.list_terms(domain_id=d["id"], page_size=100)
        assert total_code == 2
        assert total_uuid == 2
        assert {t["canonical"] for t in by_code} == {t["canonical"] for t in by_uuid}

    def test_legacy_uuid_rows_visible_in_all_child_lists(self, tmp_path: Path):
        db = tmp_path / "t.db"
        storage = SQLiteUslStorage(str(db))
        d = _make_domain(code="legacy2")
        storage.save_domain(d)
        did = d["id"]
        conn = sqlite3.connect(str(db))
        try:
            conn.execute(
                "INSERT INTO usl_hierarchies (id, domain_id, rel_type, parent_term,"
                " child_term, confidence, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), did, "IS_A", "A", "B", 1.0,
                 datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
        _, total = storage.list_hierarchies(domain_id="legacy2", page_size=100)
        assert total == 1

    def test_unresolvable_domain_ref_is_kept_and_warned(self, tmp_path: Path, caplog):
        """解析不到的 ref 原样保留并 warning，不按命名约定猜测归一（规则 14 要求 4）。"""
        db = tmp_path / "t.db"
        storage = SQLiteUslStorage(str(db))
        with caplog.at_level("WARNING"):
            saved = storage.save_term(_make_term("USL__ghost", canonical="T1"))
        assert saved["domain_id"] == "USL__ghost"
        assert _raw_child_count(db, "usl_terms", "USL__ghost") == 1
        assert any("USL__ghost" in r.getMessage() for r in caplog.records)

    def test_read_with_unknown_ref_does_not_match_other_domains(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        d = _make_domain(code="real")
        storage.save_domain(d)
        storage.save_term(_make_term("real", canonical="T1"))
        _, total = storage.list_terms(domain_id="ghost", page_size=100)
        assert total == 0


class TestFrontendDomainFlowWithCode:
    """业务人员视角的端到端：前端全程只持有 code，必须能查、能改、能加术语。

    这条链路在修复前是断的 —— get_domain 只做 `WHERE id = ?`，于是
    GET/PUT /domains/{code} 一律 404，create_term 被 _ensure_domain_exists
    判为「领域不存在」，前端 DomainForm 只 console.warn 后打开空表单。
    """

    def _service(self, tmp_path: Path):
        from odap.biz.semantic_admin.usl_manager.services import UslManagerService

        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        return UslManagerService(storage=storage), storage

    def test_domain_edit_and_term_creation_by_code(self, tmp_path: Path):
        svc, _ = self._service(tmp_path)
        created = svc.create_domain({"code": "sanguo", "display_name": "三国"})
        assert created.get("status") != "error"
        code = created["code"]

        got = svc.get_domain(code)
        assert got.get("status") != "error", got
        assert got["display_name"] == "三国"

        updated = svc.update_domain(code, {"display_name": "三国演义"})
        assert updated.get("status") != "error", updated
        assert updated["display_name"] == "三国演义"
        assert updated["code"] == code
        assert updated["id"] == created["id"]

        term = svc.create_term({
            "domain_id": code, "canonical": "刘备", "semantic_type": "对象类型",
        })
        assert term.get("status") != "error", term
        assert term["domain_id"] == code

        listed = svc.list_terms(domain_id=code, page_size=100)
        assert listed["total"] == 1

    def test_domain_flow_also_works_with_uuid(self, tmp_path: Path):
        """uuid 调用方（seed 迁移 / QueryPipeline）不能被这次修复打断。"""
        svc, _ = self._service(tmp_path)
        created = svc.create_domain({"code": "xiyou", "display_name": "西游"})
        did = created["id"]
        assert svc.get_domain(did)["display_name"] == "西游"
        assert svc.update_domain(did, {"display_name": "西游记"})["display_name"] == "西游记"
        term = svc.create_term({
            "domain_id": did, "canonical": "孙悟空", "semantic_type": "对象类型",
        })
        assert term.get("status") != "error", term
        # 写入归一到 code，因此用 code 也查得到
        assert term["domain_id"] == "xiyou"
        assert svc.list_terms(domain_id="xiyou", page_size=100)["total"] == 1
        assert svc.list_terms(domain_id=did, page_size=100)["total"] == 1

    def test_delete_by_code_reports_cascade_counts(self, tmp_path: Path):
        svc, _ = self._service(tmp_path)
        created = svc.create_domain({"code": "del", "display_name": "D"})
        svc.create_term({"domain_id": "del", "canonical": "T1"})
        result = svc.delete_domain("del")
        assert result["status"] == "ok"
        assert result["deleted"] is True
        assert result["cascade_counts"]["usl_terms"] == 1
        assert svc.get_domain("del")["status"] == "error"

    def test_delete_unknown_domain_is_404_not_silent_success(self, tmp_path: Path):
        svc, _ = self._service(tmp_path)
        result = svc.delete_domain("ghost")
        assert result["status"] == "error"
        assert "不存在" in result["message"]


# =====================================================================
# 3. Term CRUD + 过滤 + JSON roundtrip
# =====================================================================


class TestStorageTerm:
    @pytest.fixture
    def storage_with_domain(self, tmp_path: Path):
        s = SQLiteUslStorage(str(tmp_path / "t.db"))
        d = _make_domain(code="d")
        s.save_domain(d)
        return s, d["id"]

    def test_save_get_term_json_roundtrip(self, storage_with_domain):
        storage, did = storage_with_domain
        synonyms = ["角色", "将军", "谋士"]
        near = ["武将", "文臣", "主公"]
        aliases = ["英雄"]
        t = _make_term(did, canonical="人物", synonyms=synonyms[:],
                       near_synonyms=near[:], aliases=aliases[:],
                       definition="自定义定义", stoplist_flag=False)
        storage.save_term(t)
        got = storage.get_term(t["id"])
        assert got is not None
        assert got["canonical"] == "人物"
        assert got["synonyms"] == synonyms
        assert got["near_synonyms"] == near
        assert got["aliases"] == aliases
        assert got["definition"] == "自定义定义"
        assert got["stoplist_flag"] is False
        assert got["semantic_type"] == "对象类型"  # 字符串，不是 Enum

    def test_stoplist_flag_persists_after_toggle(self, storage_with_domain):
        storage, did = storage_with_domain
        t = _make_term(did, canonical="人物", stoplist_flag=False)
        storage.save_term(t)
        # 切换为 True
        t["stoplist_flag"] = True
        storage.save_term(t)
        got = storage.get_term(t["id"])
        assert got is not None and got["stoplist_flag"] is True
        # 再切换回 False
        t["stoplist_flag"] = False
        storage.save_term(t)
        got = storage.get_term(t["id"])
        assert got is not None and got["stoplist_flag"] is False

    def test_list_filter_by_semantic_type(self, storage_with_domain):
        storage, did = storage_with_domain
        storage.save_term(_make_term(did, canonical="obj", semantic_type="对象类型"))
        storage.save_term(_make_term(did, canonical="rel", semantic_type="关系类型"))
        storage.save_term(_make_term(did, canonical="act", semantic_type="动作类型"))
        items, total = storage.list_terms(domain_id=did, semantic_type="关系类型", page_size=100)
        assert total == 1
        assert items[0]["canonical"] == "rel"

    def test_list_synonym_keyword_fuzzy_match(self, storage_with_domain):
        storage, did = storage_with_domain
        storage.save_term(_make_term(did, canonical="势力", synonyms=["阵营", "国家"]))
        storage.save_term(_make_term(did, canonical="人物", synonyms=["角色", "英雄"]))
        storage.save_term(_make_term(did, canonical="谋略", aliases=["计策"]))
        # 搜同义词 "阵营" → 只命中 势力
        items, total = storage.list_terms(synonym_keyword="阵营", page_size=100)
        assert total == 1 and items[0]["canonical"] == "势力"
        # 搜 aliases "计策" → 命中谋略
        items, total = storage.list_terms(synonym_keyword="计策", page_size=100)
        assert total == 1 and items[0]["canonical"] == "谋略"
        # 搜 canonical 关键字 "谋" → 命中谋略
        items, total = storage.list_terms(synonym_keyword="谋", page_size=100)
        assert total >= 1 and any(i["canonical"] == "谋略" for i in items)

    def test_unique_domain_canonical_conflict_is_idempotent(self, storage_with_domain):
        storage, did = storage_with_domain
        t1 = _make_term(did, canonical="人物", synonyms=["a"])
        t2 = _make_term(did, canonical="人物", synonyms=["b"])  # 同 canonical
        storage.save_term(t1)
        storage.save_term(t2)
        _, total = storage.list_terms(domain_id=did, page_size=100)
        assert total == 1
        got = storage.list_terms(domain_id=did, page_size=100)[0][0]
        assert got["synonyms"] == ["b"]  # 更新为 t2 的值

    def test_term_delete_and_get_none(self, storage_with_domain):
        storage, did = storage_with_domain
        t = _make_term(did, canonical="x")
        storage.save_term(t)
        assert storage.delete_term(t["id"]) is True
        assert storage.get_term(t["id"]) is None
        assert storage.delete_term("nope") is False

    def test_invalid_semantic_type_at_impl_layer(self, storage_with_domain):
        """语义上非法 semantic_type 会在 Impl 层被拦截（此处 storage 层接受任意字符串，
        因此只验证 storage 本身不会抛错）。"""
        storage, did = storage_with_domain
        t = _make_term(did, canonical="x", semantic_type="对象类型")
        storage.save_term(t)
        got = storage.get_term(t["id"])
        assert got is not None and got["semantic_type"] == "对象类型"


# =====================================================================
# 4. Hierarchy
# =====================================================================


class TestStorageHierarchy:
    @pytest.fixture
    def s(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        storage.save_domain(_make_domain(code="d"))
        return storage

    def _did(self, storage):
        return storage.list_domains()[0][0]["id"]

    def test_save_get_list_and_delete(self, s):
        did = self._did(s)
        h = {
            "id": str(uuid.uuid4()), "domain_id": did,
            "rel_type": HierarchyRel.IS_A.value,
            "parent_term": "人物", "child_term": "武将",
            "confidence": 0.85,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        s.save_hierarchy(h)
        got = s.get_hierarchy(h["id"])
        assert got is not None
        assert got["rel_type"] == "IS_A"
        assert abs(float(got["confidence"]) - 0.85) < 1e-6
        _, total = s.list_hierarchies(page_size=100)
        assert total == 1
        assert s.delete_hierarchy(h["id"]) is True
        assert s.get_hierarchy(h["id"]) is None
        assert s.delete_hierarchy("nope") is False

    def test_unique_rel_parent_child_idempotent(self, s):
        did = self._did(s)
        base = dict(
            domain_id=did, rel_type="IS_A", parent_term="A", child_term="B",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        h1 = dict(id=str(uuid.uuid4()), confidence=0.5, **base)
        h2 = dict(id=str(uuid.uuid4()), confidence=1.0, **base)  # 同 4 字段 key
        s.save_hierarchy(h1)
        s.save_hierarchy(h2)
        items, total = s.list_hierarchies(page_size=100)
        assert total == 1
        assert items[0]["confidence"] == 1.0


# =====================================================================
# 5. PropertySpec
# =====================================================================


class TestStoragePropertySpec:
    @pytest.fixture
    def s(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        storage.save_domain(_make_domain(code="d"))
        return storage, storage.list_domains()[0][0]["id"]

    def test_crud_and_filter_by_for_term(self, s):
        storage, did = s
        s1 = {
            "id": str(uuid.uuid4()), "domain_id": did,
            "for_term": "人物", "prop_name": "姓名",
            "data_type": "STRING", "unit": None,
            "required_flag": 1, "description": "人物姓名",
        }
        s2 = {
            "id": str(uuid.uuid4()), "domain_id": did,
            "for_term": "势力", "prop_name": "都城",
            "data_type": "STRING", "unit": None,
            "required_flag": 0, "description": "",
        }
        storage.save_property_spec(s1)
        storage.save_property_spec(s2)
        items, _ = storage.list_property_specs(for_term="人物", page_size=100)
        assert len(items) == 1 and items[0]["prop_name"] == "姓名"
        got = storage.get_property_spec(s1["id"])
        assert got is not None and got["required_flag"] is True
        assert got["unit"] is None
        storage.delete_property_spec(s1["id"])
        assert storage.get_property_spec(s1["id"]) is None
        assert storage.delete_property_spec("nope") is False

    def test_unique_3key_conflict(self, s):
        storage, did = s
        def_spec = dict(domain_id=did, for_term="人物", prop_name="x")
        a = dict(id=str(uuid.uuid4()), data_type="STRING", required_flag=0,
                 unit=None, description="old", **def_spec)
        b = dict(id=str(uuid.uuid4()), data_type="INTEGER", required_flag=1,
                 unit="岁", description="new", **def_spec)
        storage.save_property_spec(a)
        storage.save_property_spec(b)
        _, total = storage.list_property_specs(page_size=100)
        assert total == 1
        got = storage.list_property_specs(for_term="人物", page_size=100)[0][0]
        assert got["data_type"] == "INTEGER"
        assert got["description"] == "new"
        assert got["unit"] == "岁"


# =====================================================================
# 6. DisjointPair
# =====================================================================


class TestStorageDisjointPair:
    @pytest.fixture
    def s(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        storage.save_domain(_make_domain(code="d"))
        return storage, storage.list_domains()[0][0]["id"]

    def test_crud_and_unique_key(self, s):
        storage, did = s
        a = {"id": str(uuid.uuid4()), "domain_id": did,
             "term_a": "A", "term_b": "B", "reason": "old"}
        b = {"id": str(uuid.uuid4()), "domain_id": did,
             "term_a": "A", "term_b": "B", "reason": "new"}
        storage.save_disjoint_pair(a)
        storage.save_disjoint_pair(b)
        _, total = storage.list_disjoint_pairs(page_size=100)
        assert total == 1
        storage.get_disjoint_pair(a["id"])
        # 由于 ON CONFLICT DO UPDATE 使用的是 excluded.id 未替换原 id；保存 b 时 UNIQUE 冲突
        # 且原行 id=a.id。实际 Storage 代码里 `id` 不在 ON CONFLICT DO UPDATE SET 里
        # 所以返回的是 b.id，但 row 仍为原 id（UNIQUE 行的主键不会变）
        # 所以查 a.id 可能返回 a.id 行，reason 已更新为 new
        assert storage.list_disjoint_pairs(page_size=100)[0][0]["reason"] == "new"
        # 删除
        pid = storage.list_disjoint_pairs(page_size=100)[0][0]["id"]
        storage.delete_disjoint_pair(pid)
        assert storage.get_disjoint_pair(pid) is None


# =====================================================================
# 7. Cardinality
# =====================================================================


class TestStorageCardinality:
    @pytest.fixture
    def s(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        storage.save_domain(_make_domain(code="d"))
        return storage, storage.list_domains()[0][0]["id"]

    def test_crud_max_card_none_stored_as_null(self, s):
        storage, did = s
        c = {"id": str(uuid.uuid4()), "domain_id": did,
             "rel_name": "效力于", "domain_term": "人物", "range_term": "势力",
             "min_card": 0, "max_card": None}
        storage.save_cardinality(c)
        got = storage.get_cardinality(c["id"])
        assert got is not None
        assert got["max_card"] is None
        assert got["min_card"] == 0
        # 设置 max_card=5
        c["max_card"] = 5
        storage.save_cardinality(c)
        got = storage.get_cardinality(c["id"])
        assert got["max_card"] == 5

    def test_filter_rel_name_and_unique_4key(self, s):
        storage, did = s
        k = dict(domain_id=did, rel_name="R", domain_term="A", range_term="B")
        a = dict(id=str(uuid.uuid4()), min_card=0, max_card=None, **k)
        b = dict(id=str(uuid.uuid4()), min_card=1, max_card=10, **k)
        storage.save_cardinality(a)
        storage.save_cardinality(b)
        items, total = storage.list_cardinalities(rel_name="R", page_size=100)
        assert total == 1
        assert items[0]["min_card"] == 1 and items[0]["max_card"] == 10


# =====================================================================
# 8. Domain en_mapping JSON roundtrip
# =====================================================================


class TestStorageJsonRoundtrip:
    def test_en_mapping_full_dict_roundtrip(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        mapping = {
            "势力": "Faction", "人物": "Character", "地点": "Location",
            "事件": "Event", "关系": "Relationship",
        }
        d = _make_domain(code="mapped", en_mapping=mapping)
        storage.save_domain(d)
        got = storage.get_domain_by_code("mapped")
        assert got is not None
        assert got["en_mapping"] == mapping

    def test_invalid_json_text_returns_default_silently(self, tmp_path: Path):
        """Storage 内部 _loads 在遇到损坏 JSON 时返回默认值。"""
        db_path = str(tmp_path / "t.db")
        storage = SQLiteUslStorage(db_path)
        # 直接用 sqlite3 写入非法 JSON 到 en_mapping
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT INTO usl_domains (id,code,display_name,en_mapping,"
                "created_at,updated_at) VALUES (?,?,?,?,?,?)",
                ("x", "bad", "Bad", "{invalid json,,,", "now", "now"),
            )
            conn.commit()
        finally:
            conn.close()
        # 读出来 en_mapping 是默认 {}，不抛异常
        got = storage.get_domain("x")
        assert got is not None
        assert got["en_mapping"] == {}


# =====================================================================
# 9. Seed 迁移幂等性
# =====================================================================

_SEED_SANGUO_SEMANTIC_MINIMAL = {
    "domain": "sanguo",
    "display_name": "三国（种子最小版）",
    "description": "用于测试的三国领域种子语义数据",
    "en_mapping": {
        "主公": "Lord",
        "丞相": "Chancellor",
        "武将": "General",
        "文臣": "Advisor",
        "士兵": "Soldier",
        "州府": "Province",
        "战役": "Battle",
        "兵力": "TroopStrength",
        "统领": "Commands",
        "攻打": "Attacks",
        "发生于": "OccursAt",
        "统治": "Rules",
        "拥有": "HasStrength",
        "献策": "Advises",
    },
    "canonical_terms": {
        "主公": {"synonyms": ["主上", "君主", "王"], "aliases": []},
        "丞相": {"synonyms": ["相国", "宰相"], "aliases": []},
        "武将": {"synonyms": ["将领", "将军", "大将"], "aliases": []},
        "文臣": {"synonyms": ["谋臣", "文官", "谋士"], "aliases": []},
        "士兵": {"synonyms": ["兵卒", "军士", "步卒"], "aliases": []},
        "州府": {"synonyms": ["州郡", "州城", "府城"], "aliases": []},
        "战役": {"synonyms": ["战争", "大战", "会战"], "aliases": []},
        "兵力": {"synonyms": ["军队数量", "兵员数量"], "aliases": []},
    },
    "expansion_rules": [
        {
            "pattern": "主公",
            "expansion": ["武将", "文臣", "丞相"],
        },
        {
            "pattern": "武将",
            "expansion": ["士兵"],
        },
        {
            "pattern": "州府",
            "expansion": ["战役"],
        },
    ],
}

_SEED_XIYOU_SEMANTIC_MINIMAL = {
    "domain": "xiyou",
    "display_name": "西游（种子最小版）",
    "description": "用于测试的西游领域种子语义数据",
    "en_mapping": {
        "佛陀": "Buddha",
        "菩萨": "Bodhisattva",
        "徒弟": "Disciple",
        "妖怪": "Demon",
        "神仙": "Deity",
        "经文": "Sutra",
        "灵山": "SpiritMountain",
        "劫难": "Calamity",
        "法力": "Power",
        "度化": "Enlightens",
        "取得": "Obtains",
        "阻挠": "Obstructs",
        "镇压": "Suppresses",
        "位于": "Hosts",
        "产生": "Produces",
        "修炼": "Practices",
    },
    "canonical_terms": {
        "佛陀": {"synonyms": ["佛", "世尊", "如来"], "aliases": []},
        "菩萨": {"synonyms": ["大士", "尊者"], "aliases": []},
        "徒弟": {"synonyms": ["弟子", "学徒", "徒儿"], "aliases": []},
        "妖怪": {"synonyms": ["妖魔", "精怪", "妖精"], "aliases": []},
        "神仙": {"synonyms": ["仙人", "仙家"], "aliases": []},
        "经文": {"synonyms": ["佛经", "真经", "典籍"], "aliases": []},
        "灵山": {"synonyms": ["佛国", "西天"], "aliases": []},
        "劫难": {"synonyms": ["灾厄", "灾祸"], "aliases": []},
        "法力": {"synonyms": ["道行", "修为"], "aliases": []},
    },
    "expansion_rules": [
        {
            "pattern": "徒弟",
            "expansion": ["法力", "经文"],
        },
        {
            "pattern": "佛陀",
            "expansion": ["菩萨", "灵山"],
        },
        {
            "pattern": "劫难",
            "expansion": ["妖怪"],
        },
    ],
}

_TEST_SEMANTICS = {
    "sanguo": _SEED_SANGUO_SEMANTIC_MINIMAL,
    "xiyou": _SEED_XIYOU_SEMANTIC_MINIMAL,
}


class TestSeedIdempotency:
    def _count_all(self, storage: SQLiteUslStorage) -> Dict[str, int]:
        counts = {}
        _, counts["domains"] = storage.list_domains(page_size=1)
        _, counts["terms"] = storage.list_terms(page_size=1)
        _, counts["hierarchies"] = storage.list_hierarchies(page_size=1)
        _, counts["specs"] = storage.list_property_specs(page_size=1)
        _, counts["dj"] = storage.list_disjoint_pairs(page_size=1)
        _, counts["cards"] = storage.list_cardinalities(page_size=1)
        return counts

    def test_seed_runs_twice_counts_stable(self, tmp_path: Path):
        from odap.biz.semantic_admin.usl_manager.migrations.seed_sanguo_xiyou import run_seed

        db_path = str(tmp_path / "seed.db")
        run_seed(db_path=db_path, semantics=_TEST_SEMANTICS)
        s1 = SQLiteUslStorage(db_path=db_path)
        c1 = self._count_all(s1)
        # 至少有 sanguo + xiyou 两个领域
        assert c1["domains"] >= 2
        assert c1["terms"] > 20
        # 第 2 次跑
        run_seed(db_path=db_path, semantics=_TEST_SEMANTICS)
        s2 = SQLiteUslStorage(db_path=db_path)
        c2 = self._count_all(s2)
        assert c1 == c2

    def test_seeded_terms_have_correct_semantic_type_values_str(
        self, tmp_path: Path
    ):
        from odap.biz.semantic_admin.usl_manager.migrations.seed_sanguo_xiyou import run_seed

        db_path = str(tmp_path / "seed.db")
        run_seed(db_path=db_path, semantics=_TEST_SEMANTICS)
        storage = SQLiteUslStorage(db_path=db_path)
        # 按语义类型分类汇总
        valid_st = {e.value for e in SemanticType}
        terms, _ = storage.list_terms(page_size=500)
        for t in terms:
            assert isinstance(t["semantic_type"], str)
            assert t["semantic_type"] in valid_st
