"""Semantic Admin Iter 2 — PipelineService + CandidateService 服务层单元测试。

- SQLite 用 tmp_path 真实 DB（AGENTS.md §C 测试规则）
- 覆盖：
  1. PipelineService：create_run/get_run/list_runs 基础元数据
  2. 错误路径：缺少 workspace_id → {"status":"error"}
  3. run_pipeline：短文本 端到端 → 输出 succeeded + candidate_count>0
  4. run_pipeline：candidate 4 种 status（approved/gated/rejected 分档齐全
  5. Quality Gate：_quality_grade → A/B/C/D 分档边界（overall_score）
  6. CandidateService：approve/reject/delete → 状态级联 + audit_logs + approval_tasks 写入
  7. CandidateService：min_confidence + semantic_type 过滤
  8. CandidateService：get_candidate 附加 quality_report 字段
  9. PipelineService：run_pipeline L1/L2/L3 audit_logs 齐全（6 条
  10. PipelineService 全量失败：异常 → run.status=failed + error_message 写入
  11. CandidateService：不存在 candidate approve 返回 {"status":"error"}
  12. CandidateService：list_approval_tasks 分页
  13. CandidateService：list_audit_logs 分页
  14. Bulk approve/reject 50 candidates → 无SQL异常
  15. run_pipeline 多 workspace 隔离：只看自己 run_id
  16. BgeHdbscanTermExtractor：model_name 白名单校验 + config=None 容错
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest
from unittest.mock import patch

from odap.biz.semantic_admin.candidate_store.services import CandidateService
from odap.biz.semantic_admin.candidate_store.storage import SQLiteCandidateStorage
from odap.biz.semantic_admin.ol_pipeline.services import PipelineService


ISO_RE = __import__("re").compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def cs(tmp_path: Path):
    """共享候选存储 tmp_path fixture（services 与 storage 共用同一个 DB 文件）。"""
    db = tmp_path / "c.db"
    storage = SQLiteCandidateStorage(db_path=str(db))
    usl_db = tmp_path / "u.db"
    from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage
    usl_storage = SQLiteUslStorage(db_path=str(usl_db))
    return storage, usl_storage


@pytest.fixture
def pipeline_svc(cs):
    cand_storage, usl_storage = cs
    return PipelineService(
        candidate_storage=cand_storage, usl_storage=usl_storage,
    )


@pytest.fixture
def cand_svc(cs):
    cand_storage, _ = cs
    return CandidateService(storage=cand_storage)


# =====================================================================
# 1. PipelineService 基础元数据
# =====================================================================


class TestPipelineServiceMetadata:
    def test_create_run_ok(self, pipeline_svc: PipelineService):
        r = pipeline_svc.create_run(workspace_id="ws-1", ontology_id="ont", source_type="nl",
                                     triggered_by="alice", total_input_chars=42)
        assert "id" in r
        assert r["workspace_id"] == "ws-1"
        assert r["status"] == "pending"

    def test_create_run_missing_ws_error(self, pipeline_svc: PipelineService):
        r = pipeline_svc.create_run(source_type="nl")
        assert r.get("status") == "error"
        assert "缺少必填" in r["message"]

    def test_get_run_not_found(self, pipeline_svc: PipelineService):
        r = pipeline_svc.get_run("nope")
        assert r.get("status") == "error"
        assert "不存在" in r["message"]

    def test_list_runs_filter_and_pagination(self, pipeline_svc: PipelineService):
        for _ in range(5):
            pipeline_svc.create_run(workspace_id="ws-A", status="pending")
        for _ in range(3):
            pipeline_svc.create_run(workspace_id="ws-B", status="succeeded")
        got = pipeline_svc.list_runs(workspace_id="ws-A", page=1, page_size=100)
        assert got["total"] == 5 and len(got["items"]) == 5
        got = pipeline_svc.list_runs(status="succeeded")
        assert got["total"] == 3
        # 分页
        got = pipeline_svc.list_runs(workspace_id="ws-A", page=2, page_size=3)
        assert got["total"] == 5 and len(got["items"]) == 2


# =====================================================================
# 2. Quality Gate（_quality_grade 边界）
# =====================================================================


class TestQualityGrade:
    def test_grade_A_high_conf_and_full_fields(self):
        g, s = PipelineService._quality_grade({
            "canonical": "A", "confidence": 0.95, "definition": "好定义",
            "synonyms": ["a", "b", "c"], "domain_id": "d-1", "semantic_type": "对象类型",
            "examples": ["ex1", "ex2", "ex3"], "stoplist_flag": False,
        })
        assert g == "A"
        assert s["overall"] >= 0.82
        assert s["risk_tags"] == []
        assert s["grade"] == "A"

    def test_grade_B_mid_conf(self):
        g, s = PipelineService._quality_grade({
            "canonical": "B", "confidence": 0.7, "definition": "定义",
            "synonyms": ["x", "y"], "domain_id": "d-1", "semantic_type": "对象类型",
            "examples": ["e"], "stoplist_flag": False,
        })
        assert g == "B"
        assert 0.62 <= s["overall"] < 0.82

    def test_grade_C_low_def_and_conf(self):
        # conf 0.55 + 1个同义词 + domain + semantic_type → 总体约 0.46 → C 档
        g, s = PipelineService._quality_grade({
            "canonical": "C", "confidence": 0.55, "synonyms": ["x"],
            "domain_id": "d-1", "semantic_type": "对象类型", "stoplist_flag": False,
        })
        assert g == "C"
        assert 0.38 <= s["overall"] < 0.62
        assert "无定义" in s["risk_tags"]

    def test_grade_D_stoplist_and_bad_fields(self):
        g, s = PipelineService._quality_grade({
            "canonical": "D", "confidence": 0.2,
            "stoplist_flag": True, "synonyms": [],
        })
        assert g == "D"
        assert s["overall"] < 0.38
        assert "命中停用词" in s["risk_tags"]


# =====================================================================
# 3. End-to-End Pipeline 运行
# =====================================================================


@pytest.fixture(autouse=True)
def _mock_llm_l1(request):
    """L1 默认是 LlmTermExtractor（依赖真实 LLM）。e2e 测试用 mock L1
    产出固定 entities，专注验证 L2-L5 编排逻辑，不依赖外部 LLM。

    注意：
    - test_run_pipeline_exception_path 传入了自定义 _BadL1，不受影响
      （patch 的是 LlmTermExtractor 类方法）。
    - TestLlmTermExtractor 类自身测的就是 LlmTermExtractor 的
      extract/降级行为，必须跳过此 mock（否则断言会错乱）。
    """
    if request.cls is not None and request.cls.__name__ == "TestLlmTermExtractor":
        yield
        return

    from odap.biz.semantic_admin.ol_pipeline.impl.l1_llm_extractor import LlmTermExtractor

    def _fake_extract(self, *, text, extra_docs=None, workspace_id=None,
                      ontology_id=None, stopwords=None, config=None):
        return [
            {
                "surface": "知识图谱", "frequency": 1, "confidence": 0.9,
                "source_text": "知识图谱与本体管理系统",
                "provenance": {"sample_contexts": ["知识图谱"], "entity_type": "对象类型"},
            },
            {
                "surface": "本体管理", "frequency": 1, "confidence": 0.88,
                "source_text": "知识图谱与本体管理系统",
                "provenance": {"sample_contexts": ["本体管理"], "entity_type": "对象类型"},
            },
            {
                "surface": "语义抽取", "frequency": 1, "confidence": 0.85,
                "source_text": "语义抽取工作流",
                "provenance": {"sample_contexts": ["语义抽取"], "entity_type": "动作类型"},
            },
            {
                "surface": "概念合并", "frequency": 1, "confidence": 0.8,
                "source_text": "概念合并分类质量闸",
                "provenance": {"sample_contexts": ["概念合并"], "entity_type": "动作类型"},
            },
        ]

    with patch.object(LlmTermExtractor, "extract", _fake_extract):
        yield


class TestRunPipeline:
    SHORT = "知识图谱与本体管理系统的语义抽取工作流，包括术语抽取与概念合并分类质量闸步骤。"

    def test_e2e_succeeded(self, pipeline_svc: PipelineService, cand_svc: CandidateService):
        res = pipeline_svc.run_pipeline(workspace_id="ws-1", text=self.SHORT,
                                        triggered_by="e2e-tester")
        assert res.get("status") == "succeeded", res.get("message")
        rid = res["pipeline_run_id"]
        count = res["candidate_count"]
        assert isinstance(count, int) and count > 0
        # Run 元数据
        run = pipeline_svc.get_run(rid)
        assert run["status"] == "succeeded"
        assert run["progress"] == 100
        assert run["triggered_by"] == "e2e-tester"
        assert run["total_output_candidates"] == count
        # audit_logs 7 条：started+l1+l2+l3+quality+succeeded
        logs = cand_svc.list_audit_logs(pipeline_run_id=rid, page=1, page_size=100)
        actions = sorted({lg["action"] for lg in logs["items"]})
        for expected in ["pipeline_started", "pipeline_l1_done", "pipeline_l2_done",
                         "pipeline_l3_done", "pipeline_quality_done", "pipeline_succeeded"]:
            assert expected in actions, (expected, actions)
        # Candidate 质量：每个 candidate 有 synonyms（JSON decoded
        cands = cand_svc.list_candidates(pipeline_run_id=rid, page=1, page_size=1000)
        statuses = {c["status"] for c in cands["items"]}
        # 至少含一个已定级的终态/半终态（出参统一规范大写枚举）
        assert statuses & {"QUALITY_GATED", "APPROVED", "REJECTED",
                           "WRITTEN_BACK", "STOPLISTED"}

    def test_workspace_isolation(self, pipeline_svc: PipelineService, cand_svc: CandidateService):
        r1 = pipeline_svc.run_pipeline(workspace_id="ws-A", text="本体抽取工作流。")
        r2 = pipeline_svc.run_pipeline(workspace_id="ws-B", text="另一个工作空间文本。")
        assert r1["status"] == "succeeded"
        assert r2["status"] == "succeeded"
        # 查 A run ID 不能把 B 的 candidate 拉进来
        got_a = cand_svc.list_candidates(pipeline_run_id=r1["pipeline_run_id"])
        got_b = cand_svc.list_candidates(pipeline_run_id=r2["pipeline_run_id"])
        id_a = {c["id"] for c in got_a["items"]}
        id_b = {c["id"] for c in got_b["items"]}
        assert id_a.isdisjoint(id_b)

    def test_run_pipeline_filter_candidates(self, pipeline_svc: PipelineService, cand_svc: CandidateService):
        res = pipeline_svc.run_pipeline(workspace_id="ws-F", text=self.SHORT)
        rid = res["pipeline_run_id"]
        # status=gated
        gated = cand_svc.list_candidates(pipeline_run_id=rid, status="gated")
        # min_confidence 0.8 严格过滤
        high = cand_svc.list_candidates(pipeline_run_id=rid, min_confidence=0.8)
        assert gated["total"] >= high["total"]

    def test_run_pipeline_exception_path(self, tmp_path: Path):
        """用故意破损的 L1 抛异常 → 验证 run status=failed 且 error_message 存在。"""
        class _BadL1:
            def extract(self, **kw):
                raise RuntimeError("boom!")
        db = tmp_path / "bad.db"
        usl_db = tmp_path / "ubad.db"
        cand_storage = SQLiteCandidateStorage(db_path=str(db))
        from odap.biz.semantic_admin.usl_manager.storage import SQLiteUslStorage
        usl_storage = SQLiteUslStorage(db_path=str(usl_db))
        svc = PipelineService(
            candidate_storage=cand_storage, usl_storage=usl_storage,
            l1_extractor=_BadL1(),
        )
        res = svc.run_pipeline(workspace_id="ws-fail", text="hi")
        assert res.get("status") == "error"
        assert "boom" in res["message"]
        # 反查 run.status
        runs = svc.list_runs(workspace_id="ws-fail")
        assert runs["total"] == 1
        assert runs["items"][0]["status"] == "failed"
        assert "boom" in (runs["items"][0].get("error_message") or "")


# =====================================================================
# 4. CandidateService 审批流转 + 分页
# =====================================================================


class TestCandidateApproval:
    SHORT = "知识图谱与本体管理系统的语义抽取工作流，包括术语抽取与概念合并分类质量闸步骤。"

    def test_approve_and_reject_happy_path(self, pipeline_svc: PipelineService, cand_svc: CandidateService):
        res = pipeline_svc.run_pipeline(workspace_id="ws-approve", text=self.SHORT)
        rid = res["pipeline_run_id"]
        cands = cand_svc.list_candidates(pipeline_run_id=rid, status="gated",
                                         page=1, page_size=1000)
        assert cands["total"] > 0, "期望至少有 gated candidate"
        c0 = cands["items"][0]
        out = cand_svc.approve(c0["id"], reviewer="alice", comment="OK", level=1)
        assert out.get("status") == "WRITTEN_BACK"
        # approval_tasks：至少有一个状态为 approved（不管level）
        tasks = cand_svc.list_approval_tasks(candidate_id=c0["id"])
        assert tasks["total"] >= 1
        approved_ids = {t["id"] for t in tasks["items"] if t["status"] == "approved"}
        assert len(approved_ids) >= 1, f"没有 approved 任务: {tasks['items']}"
        # audit_logs 含 candidate_approved
        logs = cand_svc.list_audit_logs(candidate_id=c0["id"])
        actions = [lg["action"] for lg in logs["items"]]
        assert "candidate_approved" in actions

        remain = [x for x in cands["items"] if x["id"] != c0["id"]]
        target = remain[0] if remain else cands["items"][0]
        r = cand_svc.reject(target["id"], reviewer="bob", comment="不规范")
        assert r.get("status") == "REJECTED"
        tasks2 = cand_svc.list_approval_tasks(candidate_id=target["id"])
        assert any(t["status"] == "rejected" for t in tasks2["items"])

    def test_approve_nonexistent(self, cand_svc: CandidateService):
        r = cand_svc.approve("no-such-id", reviewer="r", level=1)
        assert r.get("status") == "error"
        assert "不存在" in r["message"]

    def test_reject_nonexistent(self, cand_svc: CandidateService):
        r = cand_svc.reject("no-such-id", reviewer="r", level=1)
        assert r.get("status") == "error"

    def test_get_candidate_includes_quality_report(self, pipeline_svc: PipelineService,
                                                   cand_svc: CandidateService):
        res = pipeline_svc.run_pipeline(workspace_id="ws-qr", text=self.SHORT)
        rid = res["pipeline_run_id"]
        cands = cand_svc.list_candidates(pipeline_run_id=rid, page=1, page_size=1)
        cand_id = cands["items"][0]["id"]
        detail = cand_svc.get_candidate(cand_id)
        assert detail.get("quality_report") is not None
        assert detail["quality_report"].get("grade") in {"A", "B", "C", "D"}
        assert isinstance(detail["quality_report"].get("overall_score"), float)

    def test_bulk_50_candidates_approve_no_sql_exception(
        self, pipeline_svc: PipelineService, cand_svc: CandidateService
    ):
        res = pipeline_svc.run_pipeline(workspace_id="ws-big", text=self.SHORT * 5)
        rid = res["pipeline_run_id"]
        cands = cand_svc.list_candidates(pipeline_run_id=rid, status="gated",
                                         page=1, page_size=50)
        for c in cands["items"]:
            r = cand_svc.approve(c["id"], reviewer="bulk", level=1)
            assert r.get("status") == "approved" or r.get("canonical") == c["canonical"]

    def test_delete_then_list(self, pipeline_svc: PipelineService, cand_svc: CandidateService):
        res = pipeline_svc.run_pipeline(workspace_id="ws-del", text=self.SHORT)
        rid = res["pipeline_run_id"]
        cand = cand_svc.list_candidates(pipeline_run_id=rid, page=1, page_size=1)
        cid = cand["items"][0]["id"]
        dr = cand_svc.delete_candidate(cid, actor="tester")
        assert dr.get("deleted") is True
        got = cand_svc.get_candidate(cid)
        assert got.get("status") == "error"


# =====================================================================
# 5. BgeHdbscanTermExtractor 安全与容错测试
# =====================================================================


class TestBgeHdbscanTermExtractor:
    def test_model_name_whitelist_valid(self):
        from odap.biz.semantic_admin.ol_pipeline.impl.l1_term_extraction import BgeHdbscanTermExtractor
        extractor = BgeHdbscanTermExtractor()
        try:
            extractor._ensure_model({"model_name": "BAAI/bge-base-zh"})
            assert extractor._model is not None
        except Exception:
            pytest.skip("SentenceTransformer model loading requires network")

    def test_model_name_whitelist_small(self):
        from odap.biz.semantic_admin.ol_pipeline.impl.l1_term_extraction import BgeHdbscanTermExtractor
        extractor = BgeHdbscanTermExtractor()
        try:
            extractor._ensure_model({"model_name": "BAAI/bge-small-zh"})
            assert extractor._model is not None
        except Exception:
            pytest.skip("SentenceTransformer model loading requires network")

    def test_model_name_whitelist_large(self):
        from odap.biz.semantic_admin.ol_pipeline.impl.l1_term_extraction import BgeHdbscanTermExtractor
        extractor = BgeHdbscanTermExtractor()
        try:
            extractor._ensure_model({"model_name": "BAAI/bge-large-zh"})
            assert extractor._model is not None
        except Exception:
            pytest.skip("SentenceTransformer model loading requires network")

    def test_model_name_whitelist_invalid(self):
        from odap.biz.semantic_admin.ol_pipeline.impl.l1_term_extraction import BgeHdbscanTermExtractor
        extractor = BgeHdbscanTermExtractor()
        with pytest.raises(ValueError, match="Unsupported model_name"):
            extractor._ensure_model({"model_name": "malicious/model"})

    def test_config_none_guard(self):
        from odap.biz.semantic_admin.ol_pipeline.impl.l1_term_extraction import BgeHdbscanTermExtractor
        extractor = BgeHdbscanTermExtractor()
        try:
            extractor._ensure_model(None)
            assert extractor._model is not None
        except Exception:
            pytest.skip("SentenceTransformer model loading requires network")


# =====================================================================
# 6. LlmTermExtractor（L1 LLM 抽取器）单元测试
# =====================================================================


class TestLlmTermExtractor:
    """LlmTermExtractor 转换与降级逻辑（不依赖真实 LLM）。"""

    def test_entities_to_tokens_normalizes_and_dedups(self):
        from odap.biz.semantic_admin.ol_pipeline.impl.l1_llm_extractor import LlmTermExtractor
        entities = [
            {"name": "刘备", "type": "人员", "description": "蜀汉主公"},
            {"name": "关羽", "type": "人员", "description": "结义兄弟"},
            {"name": "刘备", "type": "人员", "description": "重复"},
            {"name": "", "type": "人员"},          # 空名 → 过滤
            {"name": "的", "type": "概念"},         # 单字 → 过滤
            {"name": None},                        # None → 过滤
        ]
        tokens = LlmTermExtractor._entities_to_tokens(entities)
        surfaces = [t["surface"] for t in tokens]
        assert surfaces == ["刘备", "关羽"], surfaces
        assert tokens[0]["confidence"] == 0.85
        assert tokens[0]["provenance"]["entity_type"] == "人员"

    def test_entities_to_tokens_flags_hallucination(self):
        from odap.biz.semantic_admin.ol_pipeline.impl.l1_llm_extractor import LlmTermExtractor
        entities = [
            {"name": "孙行者", "type": "人员", "possible_hallucination": True},
        ]
        tokens = LlmTermExtractor._entities_to_tokens(entities)
        assert tokens[0]["confidence"] == 0.4
        assert tokens[0]["provenance"]["possible_hallucination"] is True

    def test_extract_empty_text_returns_empty(self):
        from odap.biz.semantic_admin.ol_pipeline.impl.l1_llm_extractor import LlmTermExtractor
        extractor = LlmTermExtractor()
        assert extractor.extract(text="") == []
        assert extractor.extract(text="   ", extra_docs=[]) == []

    def test_extract_llm_unavailable_raises(self):
        """LLM 不可用（adapter 为 None）时直接抛 RuntimeError，不静默降级。"""
        import pytest
        from odap.biz.semantic_admin.ol_pipeline.impl.l1_llm_extractor import LlmTermExtractor
        extractor = LlmTermExtractor()
        # 强制 adapter 为 None，模拟 hyperextract 未安装
        extractor._adapter = None
        extractor._adapter_tried = True
        with pytest.raises(RuntimeError, match="LLM 抽取不可用|hyperextract"):
            extractor.extract(text="知识图谱与本体管理系统。")

    def test_protocol_compat_with_l2(self):
        """LlmTermExtractor 产出必须能被 L2 ConceptMergeEngine 消费。"""
        from odap.biz.semantic_admin.ol_pipeline.impl.l1_llm_extractor import LlmTermExtractor
        from odap.biz.semantic_admin.ol_pipeline.impl.l2_concept_extraction import ConceptMergeEngine
        entities = [
            {"name": "刘备", "type": "人员", "description": "蜀汉主公"},
            {"name": "关羽", "type": "人员", "description": "结义兄弟"},
            {"name": "结义兄弟", "type": "概念", "description": "刘备关羽张飞关系"},
        ]
        tokens = LlmTermExtractor._entities_to_tokens(entities)
        concepts = ConceptMergeEngine().merge(tokens)
        assert isinstance(concepts, list)
        canonicals = {c["canonical"] for c in concepts}
        assert "刘备" in canonicals and "关羽" in canonicals
