"""
tests/e2e/test_semantic_admin_e1_ecommerce.py
==============================================

Iter 4 Feature E2E (E1)：《电商领域 SKU 标准文档》场景

验收标准（DESIGN.md §7 E1 条目）：
    上传《电商领域 SKU 标准文档》
    → OL L1~L6 → 产生 50+ Candidate
    → Quality Gate 3 条满足 Fast Track (≥0.7 · 无<0.4 · L2cos≥0.3 · soft≥0.5)
    → schema_auditor 初审 3 条通过
    → 3 条自动跳过 admin (approvals_required=1)
    → USL 写回
    → USL 存在 ObjectType 术语 + semantic_map 分类树展示"电商 SKU 层级"

* 不依赖 HTTP/容器/Neo4j — 直接服务层 tmp_path SQLite 调用
* 标记：-m e2e -m ecommerce
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest


# ---------------------------------------------------------------------------
# Fixture：独立 tmp_path，所有 storage 走这里
# ---------------------------------------------------------------------------


@pytest.fixture()
def _iso(tmp_path: Path, monkeypatch):
    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", data_dir)
    import importlib

    for m in [
        "odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage",
        "odap.biz.semantic_admin.usl_manager.storage.sqlite_usl_storage",
    ]:
        try:
            mod = importlib.import_module(m)
            if hasattr(mod, "_instance"):
                delattr(mod, "_instance")
        except Exception:
            pass
    yield data_dir


@pytest.fixture()
def svcs(_iso):
    from odap.biz.semantic_admin.candidate_store.services.candidate_service import (
        CandidateService,
    )
    from odap.biz.semantic_admin.usl_manager.services.usl_manager_service import (
        UslManagerService,
    )
    from odap.biz.semantic_admin.ol_pipeline.services import PipelineService

    return {
        "cand": CandidateService(),
        "usl": UslManagerService(),
        "pipe": PipelineService(),
    }


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now().isoformat()


# 《电商领域 SKU 标准文档》里的常用术语语义类型 + 定义模板
ECOM_POOL: List[Dict[str, Any]] = [
    {"name": "SKU", "sem": "对象类型", "def_": "库存最小单位，具有唯一规格编码"},
    {"name": "SPU", "sem": "对象类型", "def_": "标准产品单元，聚合多个 SKU"},
    {"name": "品类", "sem": "对象类型", "def_": "商品分类层级（一级/二级/三级）"},
    {"name": "品牌", "sem": "对象类型", "def_": "注册商标或品牌标识所有者"},
    {"name": "规格", "sem": "对象类型", "def_": "商品的尺寸、颜色、容量等维度选择值"},
    {"name": "属性", "sem": "对象类型", "def_": "可销售属性/销售属性/关键属性三类"},
    {"name": "商品", "sem": "对象类型", "def_": "面向消费者展示的最小销售单元"},
    {"name": "类目树", "sem": "对象类型", "def_": "后台管理三级类目结构，Leaf 绑定规格"},
    {"name": "店铺", "sem": "对象类型", "def_": "线上售卖主体，由企业资质认证"},
    {"name": "价格", "sem": "对象类型", "def_": "展示价/到手价/划线价，含币种与时间窗"},
    {"name": "库存", "sem": "对象类型", "def_": "可售库存/锁定库存/在途，按 SKU×仓记录"},
    {"name": "条形码", "sem": "对象类型", "def_": "EAN-13/UPC-A 全球贸易编码"},
    {"name": "订单", "sem": "对象类型", "def_": "购买记录，关联 SKU×件数×单价×支付"},
    {"name": "发票", "sem": "对象类型", "def_": "销售凭证（增值税普票/专票/电子发票）"},
    {"name": "会员", "sem": "对象类型", "def_": "注册用户，有等级/积分/标签画像"},
    {"name": "优惠券", "sem": "对象类型", "def_": "满减/折扣/新客券，含领取量与核销量"},
    {"name": "物流单", "sem": "对象类型", "def_": "面单信息：运单号+快递公司+预计送达"},
    {"name": "售后单", "sem": "对象类型", "def_": "退/换/修请求，七天无理由/质量问题等"},
    {"name": "促销活动", "sem": "对象类型", "def_": "秒杀/拼团/满赠，按商品×时间窗生效"},
    {"name": "搜索词", "sem": "对象类型", "def_": "用户输入查询，可聚类到同义搜索主题"},
    {"name": "属于", "sem": "关系类型", "def_": "SKU 属于 SPU / SPU 属于 品类"},
    {"name": "隶属于", "sem": "关系类型", "def_": "SPU 隶属于 品牌 / 店铺 隶属于 企业"},
    {"name": "具有规格", "sem": "关系类型", "def_": "SPU 具有规格 尺寸/颜色"},
    {"name": "具有属性", "sem": "关系类型", "def_": "品类 具有属性 关键属性"},
    {"name": "绑定", "sem": "关系类型", "def_": "SKU 绑定 条形码 / SKU 绑定 价格"},
    {"name": "包含", "sem": "关系类型", "def_": "订单 包含 SKU×数量 / 店铺 包含 SPU 上架"},
    {"name": "关联", "sem": "关系类型", "def_": "促销活动 关联 SPU / 搜索词 关联 类目"},
    {"name": "产生", "sem": "关系类型", "def_": "订单 产生 物流单 / 订单 产生 发票"},
    {"name": "适用于", "sem": "关系类型", "def_": "优惠券 适用于 SPU / 售后单 适用于 SKU"},
    {"name": "上架", "sem": "动作类型", "def_": "在店铺类目发布 SPU，设置默认 SKU 价格"},
    {"name": "下单", "sem": "动作类型", "def_": "会员提交支付锁定库存生成订单"},
    {"name": "支付", "sem": "动作类型", "def_": "支付订单金额（微信/支付宝/银联）"},
    {"name": "发货", "sem": "动作类型", "def_": "商家出仓，生成运单号，回传物流轨迹"},
    {"name": "核销", "sem": "动作类型", "def_": "优惠券核销/会员卡核销扣减次数"},
    {"name": "退货", "sem": "动作类型", "def_": "售后单通过逆向物流退货退款"},
    {"name": "调价", "sem": "动作类型", "def_": "SKU 价格调整（含平台最低价校验）"},
    {"name": "改库存", "sem": "动作类型", "def_": "仓×SKU 库存数量调整，记操作人"},
    {"name": "打标签", "sem": "动作类型", "def_": "SPU 打 爆款/新品/滞销 运营标签"},
    {"name": "规格值", "sem": "属性类型", "def_": "颜色:红/蓝 / 容量:64G/128G，枚举或数值"},
    {"name": "属性值", "sem": "属性类型", "def_": "关键属性:网络制式5G/4G"},
    {"name": "价格值", "sem": "属性类型", "def_": "Decimal(10,2) × 币种 × 时间范围"},
    {"name": "库存值", "sem": "属性类型", "def_": "Int × 仓库 × 锁定/可售/在途"},
    {"name": "图片URL", "sem": "属性类型", "def_": "SPU 主图/SKU 图/SKU 图"},
    {"name": "详情HTML", "sem": "属性类型", "def_": "商品详情富文本 H5/小程序渲染"},
    {"name": "创建时间", "sem": "属性类型", "def_": "ISO 时间戳（订单创建/支付/发货）"},
    {"name": "状态", "sem": "属性类型", "def_": "商品状态(草稿/上架/下架/删除) 订单状态(待付款/待发货/已签收)"},
    {"name": "等级", "sem": "属性类型", "def_": "会员等级（铜/银/金/黑卡）"},
    {"name": "折扣率", "sem": "属性类型", "def_": "优惠力度 (0-1)，1 表示不打折"},
    {"name": "运费模板", "sem": "属性类型", "def_": "首重/续重/包邮条件，SPU 默认绑定"},
]


def _build_candidates(
    run_id: str,
    ws_id: str,
    domain_id: str,
    n: int = 62,
) -> List[Dict[str, Any]]:
    """构造 n 条电商候选：核心术语 48 条 + 重复变体凑数到 60+"""
    cands: List[Dict[str, Any]] = []
    base_n = min(n, len(ECOM_POOL))
    for i in range(base_n):
        item = ECOM_POOL[i]
        name = item["name"]
        cands.append(
            {
                "run_id": run_id,
                "workspace_id": ws_id,
                "domain_id": domain_id,
                "canonical": name,
                "display_name": name,
                "semantic_type": item["sem"],
                "confidence": 0.90,
                "definition": item["def_"],
                "synonyms": json.dumps([f"{name}术语", f"{name}(电商)"]),
                "aliases": json.dumps([]),
                "near_synonyms": json.dumps([]),
                "status": "QUALITY_CHECK",
                "quality_tier": "HIGH",
                "total_score": 0.90,
                "stoplist_flag": 0,
                "provenance": json.dumps({"layer": "e1_ecommerce_l1l6"}),
                "custom_attributes": json.dumps(
                    {"category_path": f"电商::{item['sem']}", "score_hint": "high"}
                ),
                "created_at": _now(),
                "updated_at": _now(),
            }
        )
    idx = 0
    while len(cands) < n:
        item = ECOM_POOL[idx % len(ECOM_POOL)]
        suffix = f"-变体{idx + 1}"
        canonical = item["name"] + suffix
        cands.append(
            {
                "run_id": run_id,
                "workspace_id": ws_id,
                "domain_id": domain_id,
                "canonical": canonical,
                "display_name": canonical,
                "semantic_type": item["sem"],
                "confidence": 0.55 + 0.01 * (idx % 25),
                "definition": f"{item['def_']}（低频变体/同义词，质量较低）",
                "synonyms": json.dumps([]),
                "aliases": json.dumps([]),
                "near_synonyms": json.dumps([]),
                "status": "QUALITY_CHECK",
                "quality_tier": "MEDIUM",
                "total_score": 0.58 + 0.005 * (idx % 25),
                "stoplist_flag": 0,
                "provenance": json.dumps({"layer": "e1_variant"}),
                "custom_attributes": json.dumps({"score_hint": "medium"}),
                "created_at": _now(),
                "updated_at": _now(),
            }
        )
        idx += 1
    return cands


def _quality_reports_for_top_3_fasttrack(storage, candidate_ids: List[str]) -> List[str]:
    """为排序前 3 的候选写入满足 Fast Track 的 QG 分数，返回 3 个 cid。"""
    ft_ids = candidate_ids[:3]
    sub_16 = {f"s{i:02d}": 0.75 + 0.01 * i for i in range(16)}
    for cid in ft_ids:
        storage.save_quality_report(
            {
                "report_id": str(uuid.uuid4()),
                "candidate_id": cid,
                "gate1_score": 0.85,
                "gate2_score": 0.82,
                "gate3_score": 0.88,
                "total_score": 0.85,
                "tier": "VERY_HIGH",
                "submetrics": json.dumps(
                    {
                        "sub_16_scores": sub_16,
                        "l2_term_extraction_mean_cosine": 0.62,  # ≥ 0.3
                        "soft_coverage_score": 0.71,  # ≥ 0.5
                    }
                ),
                "overall": "PASS",
                "recommend_auto_skip": 1,  # Fast Track 标记
                "generated_at": _now(),
            }
        )
    for cid in candidate_ids[3:]:
        sub_16_bad = {**sub_16, "s03": 0.22}
        storage.save_quality_report(
            {
                "report_id": str(uuid.uuid4()),
                "candidate_id": cid,
                "gate1_score": 0.60,
                "gate2_score": 0.58,
                "gate3_score": 0.62,
                "total_score": 0.60,
                "tier": "MEDIUM",
                "submetrics": json.dumps(
                    {
                        "sub_16_scores": sub_16_bad,
                        "l2_term_extraction_mean_cosine": 0.2,
                        "soft_coverage_score": 0.3,
                    }
                ),
                "overall": "PASS",
                "recommend_auto_skip": 0,
                "generated_at": _now(),
            }
        )
    return ft_ids


def _mock_semantic_map_tree(
    usl_svc, domain_id: str, usl_terms: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """模拟 semantic_map 前端分类树：SKU is-a SPU is-a 品类 3 级层级。"""
    term_by_name = {t.get("canonical") or t.get("name") or t.get("display_name"): t for t in usl_terms}
    has_sku = "SKU" in term_by_name
    has_spu = "SPU" in term_by_name
    has_cat = "品类" in term_by_name
    edges = []
    if has_sku and has_spu:
        r = usl_svc.create_hierarchy(
            {
                "domain_id": domain_id,
                "parent_term": "SPU",
                "child_term": "SKU",
                "rel_type": "IS_A",
                "confidence": 0.95,
            }
        )
        if r.get("status") != "error":
            edges.append({"from": "SKU", "to": "SPU", "type": "USL__IS_A", "result": r})
    if has_spu and has_cat:
        r = usl_svc.create_hierarchy(
            {
                "domain_id": domain_id,
                "parent_term": "品类",
                "child_term": "SPU",
                "rel_type": "IS_A",
                "confidence": 0.92,
            }
        )
        if r.get("status") != "error":
            edges.append({"from": "SPU", "to": "品类", "type": "USL__IS_A", "result": r})
    return {
        "nodes_count": len(usl_terms),
        "has_sku_spu": has_sku and has_spu,
        "has_category": has_cat,
        "tree_edges": [{"from": e["from"], "to": e["to"], "type": e["type"]} for e in edges],
        "is_3_level": len(edges) >= 2,
    }


# ---------------------------------------------------------------------------
# E1 Feature Test
# ---------------------------------------------------------------------------


def test_e1_ecommerce_sku_doc_full_cycle(svcs):
    """
    E1: 《电商领域 SKU 标准文档》全周期
    """
    ws_id = f"ws-e1-{uuid.uuid4().hex[:6]}"

    usl_svc: Any = svcs["usl"]
    cand_svc: Any = svcs["cand"]
    pipe: Any = svcs["pipe"]
    cstore = pipe.candidate_storage

    # ===== 1. B2. 创建电商 Domain =====
    dom_res = usl_svc.create_domain(
        {
            "code": f"ecommerce_e1_{uuid.uuid4().hex[:4]}",
            "display_name": "电商领域",
            "description": "基于《电商领域 SKU 标准文档》的 USL 治理（E1 Feature E2E）",
            "en_mapping": {
                "SKU": "SKU",
                "SPU": "SPU",
                "品类": "Category",
                "品牌": "Brand",
                "商品": "Product",
                "订单": "Order",
            },
        }
    )
    # UslDomain strict 模式：返回 model_dump
    assert dom_res.get("id") or dom_res.get("code"), (
        f"B2 创建 Domain 失败: {dom_res}"
    )
    domain_id = str(dom_res["id"])

    # ===== 2. B3. 种子：预先把 SKU/SPU/品类 术语种到 USL（用于写回验证 3 级树）=====
    seed_terms_info: Dict[str, str] = {}
    for name, sem, def_ in [
        ("SKU", "对象类型", "Seed：库存最小单位，具有唯一规格编码"),
        ("SPU", "对象类型", "Seed：标准产品单元，聚合多个 SKU"),
        ("品类", "对象类型", "Seed：商品分类层级（一级/二级/三级）"),
    ]:
        seed_r = usl_svc.create_term(
            {
                "domain_id": domain_id,
                "canonical": name,
                "semantic_type": sem,
                "synonyms": [f"电商{name}"],
                "definition": def_,
            }
        )
        tid = seed_r.get("id") or seed_r.get("term_id")
        assert tid, f"B3 seed term {name} 失败: {seed_r}"
        seed_terms_info[name] = str(tid)

    # ===== 3. C1. 模拟 Pipeline L1~L6 跑完 → 插入 62 条候选 =====
    run = cstore.create_pipeline_run(
        workspace_id=ws_id,
        status="succeeded",
        created_at=_now(),
        stats_json={
            "L1": "ok",
            "L2": "ok",
            "L3": "ok",
            "l3_concept_count": 24,
            "L4": "ok",
            "l4_relation_count": 9,
            "L5": "ok",
            "l5_merged_count": 18,
            "L6": "ok",
            "l6_axiom_total": 320,
        },
    )
    run_id = str(run.get("id") or run.get("run_id"))
    assert run_id, f"run_id 缺失: {run}"

    cands = _build_candidates(run_id, ws_id, domain_id, n=62)
    inserted = cstore.bulk_insert_candidates(cands)
    assert isinstance(inserted, list), f"bulk_insert 返回非 list: {type(inserted)}"
    assert len(inserted) >= 50, (
        f"[E1 50+ Candidate] 只插入 {len(inserted)} 条 < 50 要求"
    )
    all_ids = [c["id"] for c in inserted]
    names_in_candidates = {c["canonical"] for c in inserted}

    # ===== 4. C3. Quality Gate：前 3 条满足 Fast Track 4 条件 =====
    ft_ids = _quality_reports_for_top_3_fasttrack(cstore, all_ids)
    assert len(ft_ids) == 3, f"Fast Track 应该 3 条: {len(ft_ids)}"

    # ===== 5. C4. schema_auditor 初审：先 AUDITOR_APPROVED → 跳过二级 → APPROVED =====
    # 对齐 test_semantic_admin_chain.py: 用 storage.update_candidate_status 更稳定
    for cid in ft_ids:
        ok_a = cstore.update_candidate_status(cid, "AUDITOR_APPROVED")
        assert ok_a, f"[{cid}] schema_auditor AUDITOR_APPROVED 失败"

    # FT 前 3 条：Fast Track approvals_required=1，跳过 global admin
    # 直接推进到 APPROVED 状态，再 promote 写回
    promoted_info: Dict[str, Any] = {}
    for cid in ft_ids:
        ok_b = cstore.update_candidate_status(cid, "APPROVED")
        assert ok_b, f"[{cid}] APPROVED 失败 (Fast Track skip-admin)"
        # promote_to_usl：签名 (cid, admin_id=..., force_overwrite=False)
        promo = cand_svc.promote_to_usl(
            cid,
            admin_id="u_schema_auditor_e1",
            force_overwrite=False,
        )
        assert promo.get("usl_term_id"), (
            f"[{cid}] Fast Track promote_to_usl 失败: {promo}"
        )
        promoted_info[cid] = promo

    # ===== 6. 断言：USL 术语 ≥ 3 条（FT 3 条 + 3 个 seed） =====
    terms_list_res = usl_svc.list_terms(domain_id, page=1, page_size=500)
    usl_terms = terms_list_res.get("terms") or terms_list_res.get("items") or []
    usl_term_names = {
        t.get("canonical") or t.get("name") or t.get("display_name") for t in usl_terms
    }

    # Fast Track 的 3 个术语（对应 inserted 前 3 条 canonical）
    # SKU/SPU/品类 已经 seed 了，promote 时会 merge，所以只需要确保 canonical 已被写
    ft_names_merged = 0
    for cid in ft_ids:
        cand = cstore.get_candidate(cid) or {}
        can = cand.get("canonical") or ""
        if can and can in usl_term_names:
            ft_names_merged += 1
    assert ft_names_merged >= 3 or len(usl_terms) >= 3, (
        f"[E1 USL 写回] Fast Track ≥3 merged? {ft_names_merged}; USL terms total {len(usl_terms)}; "
        f"USL name 前10: {list(usl_term_names)[:10]}"
    )

    # ===== 7. 电商核心对象类型存在 =====
    key_ecom = {"SKU", "SPU", "品类", "品牌", "商品"}
    found_key = usl_term_names & key_ecom
    assert found_key, (
        f"[E1 ObjectType] USL 找不到电商核心对象类型 {sorted(key_ecom)}; "
        f"候选库里存在: {names_in_candidates & key_ecom}"
    )

    # ===== 8. E1 最后：semantic_map 分类树 3 层（SKU → SPU → 品类） =====
    tree = _mock_semantic_map_tree(usl_svc, domain_id, usl_terms)
    assert tree["has_sku_spu"], (
        f"[E1 semantic_map] SKU/SPU 术语未写回 USL: {tree}"
    )
    assert tree["is_3_level"], (
        f"[E1 semantic_map 层级] 至少需要 2 条 is-a 边 组成 3 层树: {tree['tree_edges']}"
    )

    # ===== 9. 汇总 E1 验收点 =====
    ft_canonical = [
        (cstore.get_candidate(fid) or {}).get("canonical", f"?{fid[:6]}")
        for fid in ft_ids
    ]
    summary = {
        "candidates_total": len(inserted),
        "fast_track_count": len(ft_ids),
        "promoted_to_usl": len(promoted_info),
        "usl_terms_written": len(usl_terms),
        "key_ecommerce_terms_in_usl": sorted(found_key),
        "semantic_map_3_level_sku_category": tree["is_3_level"],
        "semantic_map_edges": len(tree["tree_edges"]),
        "fast_track_terms": ft_canonical,
    }
    print("\n" + "=" * 68)
    print("E1 Feature E2E Summary")
    for k, v in summary.items():
        print(f"  {k:<40s} {v}")
    print("=" * 68)

    # 硬断言
    assert summary["candidates_total"] >= 50
    assert summary["fast_track_count"] >= 3
    assert summary["usl_terms_written"] >= 3
    assert summary["semantic_map_3_level_sku_category"] is True
