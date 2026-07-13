"""Semantic Admin - USL Services 层单元测试。

覆盖：
 1. 6 类资源 create/get/list/update/delete 成功返回：扁平 dict（不含 Pydantic/Enum 对象）
 2. 错误场景返回 {"status":"error","message":"..."}，不抛 HTTPException
 3. 类型转换：
    - Enum 字段在返回值中是字符串（.value）
    - datetime 字段是 ISO 字符串
    - Dict/List 容器返回 Python dict/list，不是 Pydantic 对象
 4. Impl 层 raise ValueError 被 services 捕获转为 error dict
 5. Paged 响应格式为标准 {items,total,page,page_size}
 6. get 不存在 → {"status":"error","message":"... 不存在"}
 7. update 不存在 → error
 8. delete 不存在 → error
 9. create 时必填参数缺失 → error
10. disjoint term_a == term_b → error
11. create_term 引用不存在的 domain_id → error（Impl 层 raise ValueError 被 services 捕获）
12. 非法 semantic_type 值在 list_terms 时 → error（Impl 校验）
"""
from __future__ import annotations

import re
from pathlib import Path


from odap.biz.semantic_admin.usl_manager.models import SemanticType
from odap.biz.semantic_admin.usl_manager.services import UslManagerService
from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage


ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


# =====================================================================
# Helpers
# =====================================================================


def _mk_service(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    storage = SQLiteUslStorage(db_path)
    service = UslManagerService(storage=storage)
    return service, storage


def _create_domain(service: UslManagerService, code: str = "test") -> str:
    r = service.create_domain(dict(
        code=code, display_name=f"{code}-display",
        description="d", en_mapping={"a": "A"},
    ))
    assert "status" not in r or r.get("status") != "error", f"创建领域失败: {r}"
    return r["id"]


# =====================================================================
# 1. Domain - Dict 返回正确性 / 类型转换 / 错误格式
# =====================================================================


class TestServiceDomain:
    def test_create_returns_flat_dict_with_str_enum_and_iso_dates(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        r = svc.create_domain(dict(
            code="sanguo", display_name="三国", en_mapping={"势力": "Faction"},
        ))
        # 返回值不是 error
        assert r.get("status") != "error"
        # UUID 正确
        assert "id" in r and len(r["id"]) == 36
        # code / display_name
        assert r["code"] == "sanguo"
        assert r["display_name"] == "三国"
        # en_mapping 是 dict（不是 Pydantic model_dump_json 字符串）
        assert isinstance(r["en_mapping"], dict)
        assert r["en_mapping"] == {"势力": "Faction"}
        # datetime 字段为 ISO 字符串
        assert ISO_RE.match(r["created_at"])
        assert ISO_RE.match(r["updated_at"])
        # 没有 status 标记（成功时不返回 status: ok，而是扁平 dict）
        assert "status" not in r

    def test_get_domain_not_found_returns_error_dict(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        r = svc.get_domain("no-such")
        assert r["status"] == "error"
        assert "不存在" in r["message"]
        # 不抛异常 → HTTPException
        assert isinstance(r, dict)

    def test_get_domain_success(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d1")
        r = svc.get_domain(did)
        assert r["id"] == did
        assert r["code"] == "d1"
        assert "status" not in r

    def test_list_standard_paged_format(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        for i in range(5):
            _create_domain(svc, f"d{i}")
        r = svc.list_domains(page=2, page_size=2)
        # 标准分页格式
        assert set(r.keys()) == {"items", "total", "page", "page_size"}
        assert r["total"] == 5
        assert r["page"] == 2
        assert r["page_size"] == 2
        assert len(r["items"]) == 2
        for d in r["items"]:
            assert "code" in d

    def test_update_modifies_field(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "x")
        r = svc.update_domain(did, dict(
            display_name="New", description="new desc",
            en_mapping={"k": "K"},
        ))
        assert "status" not in r
        assert r["display_name"] == "New"
        assert r["description"] == "new desc"
        assert r["en_mapping"] == {"k": "K"}
        # code 不可改
        assert r["code"] == "x"

    def test_update_not_found_error(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        r = svc.update_domain("nope", dict(display_name="X"))
        assert r["status"] == "error"
        assert "不存在" in r["message"]

    def test_delete_ok_and_error(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "z")
        r = svc.delete_domain(did)
        assert r["status"] == "ok" and r["deleted"] is True
        # 重复删 → 不存在
        r = svc.delete_domain(did)
        assert r["status"] == "error" and "不存在" in r["message"]

    def test_create_missing_code_error(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        r = svc.create_domain(dict(display_name="Nocode"))
        assert r["status"] == "error"
        assert "code" in r["message"]


# =====================================================================
# 2. Term - Dict 返回正确性 / 类型转换 / 错误
# =====================================================================


class TestServiceTerm:
    def test_create_returns_all_strings_no_enum_objects(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        r = svc.create_term(dict(
            domain_id=did,
            canonical="人物",
            semantic_type="对象类型",
            synonyms=["角色", "人"],
            near_synonyms=["武将"],
            aliases=["英雄"],
            stoplist_flag=False,
            definition="test def",
        ))
        # 不是 error
        assert "status" not in r
        # semantic_type 是字符串不是 Enum 对象
        assert r["semantic_type"] == "对象类型"
        assert isinstance(r["semantic_type"], str)
        # 同义词列表类型
        assert isinstance(r["synonyms"], list)
        assert r["synonyms"] == ["角色", "人"]
        # stoplist 布尔
        assert r["stoplist_flag"] is False
        # datetime iso
        assert ISO_RE.match(r["created_at"])

    def test_create_term_bad_domain_id_is_impl_valueerror_caught(self, tmp_path: Path):
        """Impl 层 raise ValueError('领域不存在') → services 捕获 → error dict"""
        svc, _ = _mk_service(tmp_path)
        r = svc.create_term(dict(
            domain_id="NO_SUCH_DOMAIN",
            canonical="人物",
        ))
        assert r["status"] == "error"
        assert "领域不存在" in r["message"]

    def test_create_term_missing_canonical(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        r = svc.create_term(dict(domain_id=did, canonical=""))
        assert r["status"] == "error"
        assert "canonical" in r["message"]

    def test_get_not_found_and_success(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        r = svc.get_term("no")
        assert r["status"] == "error" and "不存在" in r["message"]
        t = svc.create_term(dict(domain_id=did, canonical="T"))
        assert "status" not in t
        got = svc.get_term(t["id"])
        assert got["canonical"] == "T"

    def test_list_paged_and_filter(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        svc.create_term(dict(domain_id=did, canonical="A", semantic_type="对象类型",
                             synonyms=["阵营"]))
        svc.create_term(dict(domain_id=did, canonical="B", semantic_type="关系类型"))
        svc.create_term(dict(domain_id=did, canonical="C", semantic_type="动作类型"))
        # 过滤 semantic_type
        r = svc.list_terms(semantic_type="关系类型")
        assert r["total"] == 1 and r["items"][0]["canonical"] == "B"
        # 非法 semantic_type → Impl 校验 → error
        r = svc.list_terms(semantic_type="NO_SUCH_TYPE")
        assert r["status"] == "error"
        assert "非法 semantic_type" in r["message"]
        # synonym 关键字
        r = svc.list_terms(synonym_keyword="阵营")
        assert r["total"] == 1 and r["items"][0]["canonical"] == "A"

    def test_update_term_toggle_stoplist_and_synonyms(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        t = svc.create_term(dict(domain_id=did, canonical="T"))
        r = svc.update_term(t["id"], dict(
            stoplist_flag=True, synonyms=["a", "b"],
            definition="upd",
        ))
        assert "status" not in r
        assert r["stoplist_flag"] is True
        assert r["synonyms"] == ["a", "b"]
        assert r["definition"] == "upd"

    def test_delete_term_success_and_missing(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        t = svc.create_term(dict(domain_id=did, canonical="T"))
        r = svc.delete_term(t["id"])
        assert r["status"] == "ok" and r["deleted"] is True
        r = svc.delete_term("xxx")
        assert r["status"] == "error"


# =====================================================================
# 3. Hierarchy
# =====================================================================


class TestServiceHierarchy:
    def test_create_and_get_success(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        r = svc.create_hierarchy(dict(
            domain_id=did, rel_type="IS_A",
            parent_term="人物", child_term="武将",
            confidence=0.9,
        ))
        assert "status" not in r
        assert r["rel_type"] == "IS_A"
        assert abs(r["confidence"] - 0.9) < 1e-6
        got = svc.get_hierarchy(r["id"])
        assert got["child_term"] == "武将"

    def test_create_missing_required_fields_error(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        r = svc.create_hierarchy(dict(domain_id=did, parent_term="A"))
        assert r["status"] == "error"
        assert "child_term" in r["message"] or "不能为空" in r["message"]

    def test_create_bad_domain_impl_error_caught(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        r = svc.create_hierarchy(dict(
            domain_id="BAD", parent_term="A", child_term="B",
        ))
        assert r["status"] == "error" and "领域不存在" in r["message"]


# =====================================================================
# 4. PropertySpec
# =====================================================================


class TestServicePropertySpec:
    def test_create_unit_required_flags_dict_types(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        r = svc.create_property_spec(dict(
            domain_id=did, for_term="人物", prop_name="年龄",
            data_type="INTEGER", unit="岁", required_flag=True,
            description="人物年龄",
        ))
        assert "status" not in r
        assert r["data_type"] == "INTEGER"
        assert r["unit"] == "岁"
        assert r["required_flag"] is True
        assert r["for_term"] == "人物"

    def test_create_missing_fields_error(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        r = svc.create_property_spec(dict(domain_id=did, for_term="T"))
        assert r["status"] == "error"
        assert "prop_name" in r["message"]

    def test_list_filter_for_term(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        svc.create_property_spec(dict(domain_id=did, for_term="A", prop_name="p1"))
        svc.create_property_spec(dict(domain_id=did, for_term="B", prop_name="p2"))
        r = svc.list_property_specs(for_term="A")
        assert r["total"] == 1 and r["items"][0]["prop_name"] == "p1"


# =====================================================================
# 5. DisjointPair
# =====================================================================


class TestServiceDisjointPair:
    def test_term_a_equals_term_b_blocked_by_services(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        r = svc.create_disjoint_pair(dict(
            domain_id=did, term_a="X", term_b="X",
        ))
        assert r["status"] == "error"
        assert "不能相同" in r["message"]

    def test_create_and_update_and_list(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        r = svc.create_disjoint_pair(dict(
            domain_id=did, term_a="A", term_b="B", reason="互斥",
        ))
        assert "status" not in r
        # 列表
        got = svc.list_disjoint_pairs()
        assert got["total"] == 1
        assert got["items"][0]["reason"] == "互斥"
        # 更新 reason 以及 term_b
        r2 = svc.update_disjoint_pair(r["id"], dict(
            term_b="C", reason="new reason",
        ))
        assert "status" not in r2
        assert r2["term_b"] == "C" and r2["reason"] == "new reason"


# =====================================================================
# 6. Cardinality
# =====================================================================


class TestServiceCardinality:
    def test_create_max_card_none_and_integer(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        r = svc.create_cardinality(dict(
            domain_id=did, rel_name="R",
            domain_term="A", range_term="B",
            min_card=0, max_card=None,
        ))
        assert "status" not in r
        assert r["min_card"] == 0
        assert r["max_card"] is None
        # 更新为 max_card=10
        r2 = svc.update_cardinality(r["id"], dict(max_card=10, min_card=1))
        assert r2["min_card"] == 1 and r2["max_card"] == 10

    def test_create_missing_fields_error(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        r = svc.create_cardinality(dict(domain_id=did, rel_name="R"))
        assert r["status"] == "error"
        assert "domain_term" in r["message"] or "range_term" in r["message"]

    def test_list_filter_rel_name(self, tmp_path: Path):
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        svc.create_cardinality(dict(
            domain_id=did, rel_name="R1", domain_term="A", range_term="B"))
        svc.create_cardinality(dict(
            domain_id=did, rel_name="R2", domain_term="A", range_term="C"))
        r = svc.list_cardinalities(rel_name="R2")
        assert r["total"] == 1
        assert r["items"][0]["range_term"] == "C"


# =====================================================================
# 7. 类型转换完整性（通用）
# =====================================================================


class TestServiceTypeConversion:
    def test_all_6_entity_returns_no_pydantic_or_enum_objects(self, tmp_path: Path):
        """验证：services 返回值中所有 Enum 字段都是 str，没有 Enum 对象。"""
        svc, _ = _mk_service(tmp_path)
        did = _create_domain(svc, "d")
        # 创建各 1 条
        t = svc.create_term(dict(
            domain_id=did, canonical="人物",
            semantic_type=SemanticType.OBJECT_TYPE.value,
        ))
        h = svc.create_hierarchy(dict(
            domain_id=did, rel_type="IS_A",
            parent_term="人物", child_term="武将",
        ))
        p = svc.create_property_spec(dict(
            domain_id=did, for_term="人物", prop_name="x",
        ))
        dj = svc.create_disjoint_pair(dict(
            domain_id=did, term_a="A", term_b="B",
        ))
        c = svc.create_cardinality(dict(
            domain_id=did, rel_name="R", domain_term="A", range_term="B",
        ))
        # 遍历所有返回值检查类型
        results = [("domain", svc.get_domain(did)),
                   ("term", t), ("hier", h), ("prop", p),
                   ("dj", dj), ("card", c)]
        for name, obj in results:
            # 返回值必须是 dict，不是 Pydantic Model
            assert isinstance(obj, dict), f"{name} 不是 dict: {type(obj)}"
            # 枚举值字段（如果有）必须是字符串
            if "semantic_type" in obj:
                assert obj["semantic_type"] in ("对象类型", "关系类型", "属性",
                                                "动作类型", "过程类型",
                                                "规则类型")
                assert isinstance(obj["semantic_type"], str)
            if "rel_type" in obj:
                assert obj["rel_type"] in ("IS_A", "PART_OF", "INSTANCE_OF")
                assert isinstance(obj["rel_type"], str)
            if "data_type" in obj:
                assert isinstance(obj["data_type"], str)
            # 日期字段
            for k in ("created_at", "updated_at"):
                if k in obj:
                    assert isinstance(obj[k], str), f"{name}.{k} 不是字符串"
                    assert ISO_RE.match(obj[k]), f"{name}.{k} 不是 ISO 格式: {obj[k]}"
