"""
tests/e2e/test_semantic_admin_chain.py
======================================

E2E 冒烟测试：B2(USL Domain) → B3(USL Term) → C1(Pipeline) → C3(Quality)
         → C4(2 级审批) → B7(promote_to_usl) → C5(Graphiti 双写验证)

* 不依赖 HTTP / 容器运行 — 直接调用服务层，可在本地 pytest 独立执行
* SQLite 用 tmp_path 真实 DB，不用 MagicMock
* 标记：-m e2e（但默认也跑，因为不依赖 Neo4j）
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pytest


# ---------------------------------------------------------------------------
# Fixture：独立 tmp_path，给所有 storage 使用
# ---------------------------------------------------------------------------
@pytest.fixture()
def _isolated_data_root(tmp_path: Path, monkeypatch):
    """
    将所有模块的 DATA_DIR 定向到 tmp_path。
    - candidate_store、usl_writeback、usl_manager、ontology storage
    都是基于 DATA_DIR 构造 sqlite 路径，模块级单例不共享数据。
    """
    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", data_dir)
    # 强制每次新建 instance（不走模块级单例缓存）
    import importlib

    mods = [
        "odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage",
        "odap.biz.semantic_admin.usl_manager.storage.sqlite_usl_storage",
    ]
    for m in mods:
        try:
            mod = importlib.import_module(m)
            if hasattr(mod, "_instance"):
                try:
                    delattr(mod, "_instance")
                except AttributeError:
                    pass
        except Exception:
            pass
    yield data_dir


@pytest.fixture()
def services(_isolated_data_root):
    """返回所有要用到的服务，构造时都走 tmp_path storage。"""
    from odap.biz.semantic_admin.candidate_store.services.candidate_service import (
        CandidateService,
    )
    from odap.biz.semantic_admin.usl_manager.services.usl_manager_service import (
        UslManagerService,
    )
    from odap.biz.semantic_admin.ol_pipeline.services import PipelineService
    from odap.biz.core.ontology.ontology_api.services.ontology_service import (
        OntologyService,
    )

    return {
        "cand": CandidateService(),
        "usl": UslManagerService(),
        "pipe": PipelineService(),
        "ont": OntologyService(),
    }


# ---------------------------------------------------------------------------
# 小工具函数
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now().isoformat()


def _seed(services, workspace_id: str, domain_id: str, n_candidates: int = 8):
    """写入 n 个候选（5 个对象类型 + 2 个关系类型 + 1 个动作类型）。"""
    pipe = services["pipe"]
    storage = pipe.candidate_storage  # 通过 PipelineService 访问底层 Storage
    run = storage.create_pipeline_run(
        workspace_id=workspace_id,
        status="succeeded",
        created_at=_now(),
    )
    run_id = str(run.get("id") or run.get("run_id"))
    assert run_id, f"pipeline_run 未返回 id: {run}"

    semantic_types = ["对象类型"] * 5 + ["关系类型"] * 2 + ["动作类型"] * 1
    canonical_stems = [
        "军师",
        "将军",
        "丞相",
        "主公",
        "校尉",
        "效忠于",
        "结拜于",
        "出征",
    ]
    candidates = []
    for i in range(min(n_candidates, len(canonical_stems))):
        canonical = canonical_stems[i]
        candidates.append(
            {
                "run_id": run_id,
                "workspace_id": workspace_id,
                "domain_id": domain_id,
                "canonical": canonical,
                "semantic_type": semantic_types[i],
                "confidence": 0.92,
                "definition": f"{canonical}：三国时期常见术语（E2E 冒烟）",
                "synonyms": json.dumps([f"{canonical}(同)"]),
                "aliases": json.dumps([f"{canonical}-alias"]),
                "near_synonyms": json.dumps([]),
                "status": "L5_DONE",
                "quality_tier": "VERY_HIGH",
                "total_score": 0.96,
                "stoplist_flag": 0,
                "provenance": json.dumps({"layer": "e2e_smoke"}),
                "custom_attributes": json.dumps({}),
                "created_at": _now(),
                "updated_at": _now(),
            }
        )
    inserted = storage.bulk_insert_candidates(candidates)
    assert isinstance(inserted, list) and len(inserted) >= 3, (
        f"bulk_insert 只插入了 {len(inserted) if isinstance(inserted, list) else inserted}"
    )
    return run_id, [c["id"] for c in inserted]


def _attach_quality_reports(services, candidate_ids):
    """伪造质量闸分数（VERY_HIGH → L1 快速通过）。"""
    storage = services["pipe"].candidate_storage
    for cid in candidate_ids:
        storage.save_quality_report(
            {
                "report_id": str(uuid.uuid4()),
                "candidate_id": cid,
                "gate1_score": 0.98,
                "gate2_score": 0.97,
                "gate3_score": 0.99,
                "total_score": 0.98,
                "tier": "VERY_HIGH",
                "submetrics": json.dumps(
                    {
                        "gate1": [{"submetric": "s1", "score": 0.98, "rule_name": "r1"}],
                        "gate2": [],
                        "gate3": [],
                    }
                ),
                "overall": "PASS",
                "recommend_auto_skip": 1,
                "generated_at": _now(),
            }
        )


# ---------------------------------------------------------------------------
# E2E 主测试
# ---------------------------------------------------------------------------
def test_b2_b3_c1_c3_c4_b7_c5_full_chain(services):
    """
    B2 → B3 → C1 → C3 → C4 → B7 → C5
    """
    ws_id = f"ws-e2e-{uuid.uuid4().hex[:6]}"

    # ======= B2. 创建 USL Domain =======
    usl_svc = services["usl"]
    domain_code = "sanguo_common_e2e"
    dom_res = usl_svc.create_domain(
        {
            "code": domain_code,
            "display_name": "三国通用语域(E2E)",
            "description": "E2E 冒烟测试专用",
            "en_mapping": {"ZhugeLiang": "诸葛亮"},
        }
    )
    assert dom_res.get("id") or dom_res.get("code"), f"B2 创建 domain 失败: {dom_res}"
    domain_id = str(dom_res.get("id") or dom_res.get("code"))
    assert usl_svc.get_domain(domain_id) is not None

    # ======= B3. 预置 1 个 seed 术语（写回时验证冲突合并能力）=======
    seed_res = usl_svc.create_term(
        {
            "domain_id": domain_id,
            "canonical": "主公",  # 与 candidate 里的 canonical 冲突
            "semantic_type": "对象类型",
            "synonyms": ["明公"],
            "definition": "预置seed：主公（君主）",
        }
    )
    assert seed_res.get("id"), f"B3 seed term 失败: {seed_res}"
    seed_term_id = str(seed_res["id"])

    # ======= C1. 创建 PipelineRun + 8 个候选 =======
    run_id, cand_ids = _seed(services, workspace_id=ws_id, domain_id=domain_id)

    # ======= C3. 质量闸：写入 VERY_HIGH 质量报告 =======
    _attach_quality_reports(services, cand_ids)
    storage = services["pipe"].candidate_storage
    listed = storage.list_candidates(pipeline_run_id=run_id, page=1, page_size=50)
    assert listed["total"] >= len(cand_ids)

    # ======= C4. 两级审批：L1 AUDITOR_APPROVED → L2 APPROVED（直接写状态更稳定）=======
    promoted = []
    skipped = []

    for idx, cid in enumerate(cand_ids):
        upd1 = storage.update_candidate_status(cid, "AUDITOR_APPROVED")
        assert upd1, f"L1 update 失败 {cid}"

        # 第 2 个 → 跳过（REVIEWER_REJECTED），验证不会 promote
        if idx == 1:
            storage.update_candidate_status(cid, "REVIEWER_REJECTED")
            skipped.append(cid)
            continue

        storage.update_candidate_status(cid, "APPROVED")
        promoted.append(cid)

    # ======= B7. promote_to_usl：批量提升 → USL 写回 + Graphiti 双写 =======
    promoted_info: Dict[str, Any] = {}
    for cid in promoted:
        res = services["cand"].promote_to_usl(
            cid,
            admin_id="admin-001",
            force_overwrite=False,
        )
        # 返回结构：无 status=success，但 usl_term_id 存在即成功
        assert res.get("usl_term_id"), f"B7 promote 失败: {res}"
        assert "graphiti" in res and "graphiti_ontology_id" in res, (
            f"B7 缺少 Graphiti 字段: {list(res.keys())}"
        )
        promoted_info[cid] = res

    # ======= C5. 验证双写 =======
    #   C5.1 provenance 字段完整
    any_gw_ok = False
    for cid, res in promoted_info.items():
        cand = storage.get_candidate(cid)
        assert cand is not None, f"candidate {cid} 不存在"
        prov = cand.get("provenance") or {}
        # USL
        usl_tid = prov.get("writeback_usl_term_id") or prov.get("usl_term_id")
        assert usl_tid, f"C5.1 USL term_id 缺失: cid={cid} prov_keys={list(prov.keys())}"
        # Graphiti
        gw = prov.get("graphiti_writeback") or prov.get("graphiti") or res.get("graphiti")
        oid = prov.get("graphiti_ontology_id") or res.get("graphiti_ontology_id")
        tid = prov.get("graphiti_type_id") or res.get("graphiti_type_id")
        assert isinstance(gw, dict), f"C5.1 graphiti_writeback 非 dict: {gw}"
        assert oid, f"C5.1 Graphiti Ontology ID 缺失 cid={cid}"
        assert tid, f"C5.1 Graphiti Type ID 缺失 cid={cid}"
        st = gw.get("status")
        assert st in {"ok", "skipped", "error"}, (
            f"C5.1 status={st!r} 非法 cid={cid}"
        )
        if st == "ok":
            any_gw_ok = True

    # 至少一个 Graphiti 写入成功（对象类型必定成功）
    assert any_gw_ok, (
        f"C5.2 没有任何 Graphiti 写入成功: "
        f"{ {k:v.get('graphiti') for k,v in promoted_info.items()} }"
    )

    #   C5.3 冲突合并：seed 的 "主公" → promote 时应该重用 seed_term_id
    for cid, res in promoted_info.items():
        cand = storage.get_candidate(cid) or {}
        if cand.get("canonical") == "主公":
            prov = cand.get("provenance") or {}
            merged_term_id = prov.get("writeback_usl_term_id") or res.get("usl_term_id")
            assert (
                merged_term_id == seed_term_id
            ), f"C5.3 主公 冲突未合并：expected={seed_term_id} actual={merged_term_id}"

    #   C5.4 OntologyService 端读回：至少一个 object_type 存在且 match canonical
    for cid, res in promoted_info.items():
        cand = storage.get_candidate(cid) or {}
        prov = cand.get("provenance") or {}
        oid = prov.get("graphiti_ontology_id") or res.get("graphiti_ontology_id")
        tid = prov.get("graphiti_type_id") or res.get("graphiti_type_id")
        if oid and tid:
            # 只需要验证第一个找到的
            listed_ot = services["ont"].list_object_types(ontology_id=str(oid))
            items = listed_ot.get("object_types") or listed_ot.get("items") or []
            found = any(str(i.get("type_id")) == str(tid) for i in items)
            assert (
                found
            ), f"C5.4 Ontology({oid}) 中找不到 type_id={tid}，共 {len(items)} 个 type"
            # 完成验证
            return
    # 如果没有 object_type 被回写成功，说明我们断言过早（至少应当已经在 any_gw_ok 处失败）
    pytest.fail("C5.4 未能找到任何可验证的 graphiti type 结果")


def test_c6_execute_all_l3_to_l6_stats(services):
    """C6. 在 B2/B3 seed USL 基础上：建 run → 填候选 → execute_all → 断言 L3~L6 stats."""
    import uuid as _uuid

    ws_id = f"ws-c6-{_uuid.uuid4().hex[:6]}"
    pipe = services["pipe"]
    usl_svc = services["usl"]

    # B2. 建 domain + B3. seed 1 existing term for L5 merge
    dom = usl_svc.create_domain({
        "code": f"sanguo_c6_{_uuid.uuid4().hex[:4]}",
        "display_name": "三国 C6 语域",
        "description": "E2E C6 test",
    })
    domain_id = str(dom.get("id") or dom.get("code"))
    usl_svc.create_term({
        "domain_id": domain_id,
        "canonical": "主公",
        "semantic_type": "对象类型",
        "synonyms": ["明公", "君主"],
        "definition": "seed existing：主公 是一国之主。",
    })

    # C1. new run (status=CREATED default)
    run = pipe.create_run(workspace_id=ws_id, source_type="natural_language",
                          source_ref="c6_demo", total_input_chars=800)
    rid = str(run.get("id") or run.get("run_id"))
    assert rid

    storage = pipe.candidate_storage
    cand_ids = []

    def _add(cid_pref, canonical, sem_type, **prov_extra):
        cid = f"c-{cid_pref}-{_uuid.uuid4().hex[:5]}"
        payload = {
            "candidate_id": cid, "run_id": rid, "workspace_id": ws_id,
            "domain_id": domain_id, "canonical": canonical,
            "semantic_type": sem_type, "confidence": 0.9,
            "status": "pending_review",
            "provenance": {"L1": True, **prov_extra},
        }
        # synonyms/definition for FCA / L5 signal
        if sem_type == "对象类型":
            payload["synonyms"] = [canonical, f"{canonical}(同)"]
            payload["definition"] = f"{canonical} 的定义描述。"
        cand_ids.append(cid)
        return payload

    # 4 entities for FCA (so ≥2 concepts)
    cands = [
        _add("e1", "主公", "对象类型", synonyms=["明公", "君主"]),
        _add("e2", "丞相", "对象类型"),
        _add("e3", "军师", "对象类型"),
        _add("e4", "将军", "对象类型"),
        # 2 relations with known relation_phrase (L4 provenance needs these; if not set, L4 falls back)
        {
            **_add("r1", "丞相_效忠于_主公", "关系类型"),
            "provenance": {"L4": True, "subject_canonical": "丞相",
                           "object_canonical": "主公", "relation_phrase": "隶属于",
                           "frequency": 3, "relation_type": "is_a",
                           "relation_type_score": 0.7, "relation_type_rule": "隶属"},
        },
        {
            **_add("r2", "军师_具有_谋略", "关系类型"),
            "provenance": {"L4": True, "subject_canonical": "军师",
                           "object_canonical": "谋略", "relation_phrase": "具有",
                           "frequency": 2, "relation_type": "attribute_of",
                           "relation_type_score": 0.6, "relation_type_rule": "具有"},
        },
    ]
    storage.bulk_insert_candidates(cands)

    # execute
    result = pipe.execute_all(run_id=rid, fail_fast=True)
    assert result.get("status") in ("succeeded", "completed"), (
        f"execute_all FAIL: {result}"
    )

    run_obj = storage.get_pipeline_run(rid)
    assert run_obj.get("status") == "COMPLETED", (
        f"run.status = {run_obj.get('status')}, expected COMPLETED; errors={run_obj.get('error_json')}"
    )
    stats = run_obj.get("stats_json")
    if isinstance(stats, str):
        stats = json.loads(stats)
    stats = stats or {}

    # --- 核心断言：L3/L4/L5/L6 状态 = ok + 数值合理 ---
    assert stats.get("L3") == "ok", f"L3 NOT ok: stats={stats}"
    assert stats.get("L4") == "ok", f"L4 NOT ok: stats={stats}"
    assert stats.get("L5") == "ok", f"L5 NOT ok: stats={stats}"
    assert stats.get("L6") == "ok", f"L6 NOT ok: stats={stats}"

    assert (stats.get("l3_concept_count") or 0) >= 2, f"L3 concept <2: {stats}"
    assert (stats.get("l3_suggested_edges") or 0) >= 1, f"L3 edges <1: {stats}"
    by_t = stats.get("l4_relations_by_type") or {}
    assert by_t.get("is_a", 0) >= 1, f"L4 is_a 缺失: {by_t}"
    assert by_t.get("attribute_of", 0) >= 1, f"L4 attribute_of 缺失: {by_t}"
    assert (stats.get("l5_merged_count") or 0) >= 1, f"L5 merge 0: {stats}"
    assert (stats.get("l6_axiom_total") or 0) >= 4, f"L6 axioms <4: {stats}"
    ax_by = stats.get("l6_axioms_by_type") or {}
    # 至少 subClassOf + domain/range/disjoint 中若干命中
    assert sum(int(v or 0) for v in ax_by.values()) == int(stats.get("l6_axiom_total") or 0), (
        f"L6 by_type 累加 != total: {stats}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
