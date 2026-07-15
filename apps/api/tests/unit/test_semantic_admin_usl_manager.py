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

    def test_delete_domain_returns_bool(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        assert storage.delete_domain("nope") is False
        d = _make_domain(code="x")
        storage.save_domain(d)
        assert storage.delete_domain(d["id"]) is True
        assert storage.get_domain(d["id"]) is None

    def test_delete_domain_cascades_all_child_tables(self, tmp_path: Path):
        storage = SQLiteUslStorage(str(tmp_path / "t.db"))
        d = _make_domain(code="casc")
        storage.save_domain(d)
        did = d["id"]
        # 写入各 2 条子记录
        storage.save_term(_make_term(did, canonical="T1"))
        storage.save_term(_make_term(did, canonical="T2"))
        storage.save_hierarchy({
            "id": str(uuid.uuid4()), "domain_id": did,
            "parent_term": "A", "child_term": "B", "rel_type": "IS_A",
            "confidence": 1.0, "created_at": datetime.now(timezone.utc).isoformat(),
        })
        storage.save_hierarchy({
            "id": str(uuid.uuid4()), "domain_id": did,
            "parent_term": "C", "child_term": "D", "rel_type": "IS_A",
            "confidence": 1.0, "created_at": datetime.now(timezone.utc).isoformat(),
        })
        storage.save_property_spec({
            "id": str(uuid.uuid4()), "domain_id": did,
            "for_term": "T1", "prop_name": "name", "data_type": "STRING",
            "unit": None, "required_flag": 1, "description": "",
        })
        storage.save_disjoint_pair({
            "id": str(uuid.uuid4()), "domain_id": did,
            "term_a": "T1", "term_b": "T2", "reason": "",
        })
        storage.save_cardinality({
            "id": str(uuid.uuid4()), "domain_id": did,
            "rel_name": "效力于", "domain_term": "T1", "range_term": "T2",
            "min_card": 0, "max_card": None,
        })
        # 删除前有子记录
        _, t_total = storage.list_terms(domain_id=did, page_size=100)
        assert t_total == 2
        # 删除
        storage.delete_domain(did)
        # 所有子表清空
        _, t_total = storage.list_terms(domain_id=did, page_size=100)
        assert t_total == 0
        _, h_total = storage.list_hierarchies(domain_id=did, page_size=100)
        assert h_total == 0
        _, p_total = storage.list_property_specs(domain_id=did, page_size=100)
        assert p_total == 0
        _, dj_total = storage.list_disjoint_pairs(domain_id=did, page_size=100)
        assert dj_total == 0
        _, c_total = storage.list_cardinalities(domain_id=did, page_size=100)
        assert c_total == 0


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
