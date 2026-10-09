"""子项目 B：缺口回归集 builder 测试（真实 tmp_path DB，规则 9/14.6）。

覆盖：固化不可变（同参数二次 build 生成新集不覆盖旧的）；scope 隔离；
min_heat 过滤；case 结构 {query, expression, gap_id, source} 真实来自 gap 记录。
"""
import pytest
from odap.biz.semantic_admin.gap_pool.models import GapSignalSource
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage
from odap.biz.semantic_admin.gap_pool.regression.builder import RegressionSetBuilder
from odap.biz.semantic_admin.gap_pool.regression.storage import SQLiteGapRegressionStorage


@pytest.fixture
def gap_store(tmp_path):
    return SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))


@pytest.fixture
def reg_store(tmp_path):
    return SQLiteGapRegressionStorage(db_path=str(tmp_path / "gap_regression.db"))


@pytest.fixture
def builder(gap_store, reg_store):
    return RegressionSetBuilder(gap_storage=gap_store, storage=reg_store)


def test_build_fixates_cases_from_real_gaps(builder, gap_store, reg_store):
    g = gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                                workspace_id="ws1", domain_id="d1")
    gap_store.record_signal(GapSignalSource.QA_UNANSWERED, "诸侯",
                            workspace_id="ws1", domain_id="d1")
    r = builder.build(workspace_id="ws1", domain_id="d1")
    assert r["status"] == "ok"
    s = reg_store.get_set(r["set_id"])
    assert s is not None
    assert s["case_count"] == 1                       # 同 expression 聚合成一条
    case = s["cases_json"][0]
    assert case["query"] == "诸侯"
    assert case["expression"] == "诸侯"
    assert case["gap_id"] == g["id"]
    assert case["source"] in ("term_resolve_miss", "qa_unanswered")
    assert s["scope_key"] == "ws1::d1"
    assert g["id"] in s["source_gap_ids_json"]
    assert s["model_id"]                             # 构建时模型指纹非空


def test_build_twice_creates_new_set_not_overwrite(builder, gap_store, reg_store):
    """回归集不可变：同参数二次 build 生成新集，旧集原样保留（ADR-088 D3）。"""
    gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                            workspace_id="ws1", domain_id="d1")
    r1 = builder.build(workspace_id="ws1", domain_id="d1")
    gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "阵营",
                            workspace_id="ws1", domain_id="d1")
    r2 = builder.build(workspace_id="ws1", domain_id="d1")
    assert r1["set_id"] != r2["set_id"]              # 新集，不覆盖
    s1 = reg_store.get_set(r1["set_id"])
    assert s1["case_count"] == 1                     # 旧集固化内容不变
    assert s1["cases_json"][0]["expression"] == "诸侯"


def test_build_scope_isolation(builder, gap_store):
    gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                            workspace_id="ws1", domain_id="d1")
    gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                            workspace_id="ws2", domain_id="d1")
    r = builder.build(workspace_id="ws2", domain_id="d1")
    assert r["status"] == "ok"
    assert r["set"]["case_count"] == 1
    assert r["set"]["scope_key"] == "ws2::d1"


def test_build_min_heat_filter(builder, gap_store):
    gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "冷词",
                            workspace_id="ws1", domain_id="d1")   # heat=1
    for _ in range(5):
        gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "热词",
                                workspace_id="ws1", domain_id="d1")
    r = builder.build(workspace_id="ws1", domain_id="d1", min_heat=3)
    assert r["status"] == "ok"
    exprs = [c["expression"] for c in r["set"]["cases_json"]]
    assert exprs == ["热词"]


def test_build_status_filter(builder, gap_store):
    from odap.biz.semantic_admin.gap_pool.models import GapStatus
    g = gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "已晋升",
                                workspace_id="ws1", domain_id="d1")
    gap_store.update_status(g["id"], GapStatus.PROMOTED.value,
                            promoted_candidate_id="c1")
    gap_store.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "待处理",
                            workspace_id="ws1", domain_id="d1")
    r = builder.build(workspace_id="ws1", domain_id="d1", status="open")
    exprs = [c["expression"] for c in r["set"]["cases_json"]]
    assert exprs == ["待处理"]


def test_build_empty_scope_returns_empty_set(builder):
    r = builder.build(workspace_id="ws-none", domain_id="d1")
    assert r["status"] == "ok"
    assert r["set"]["case_count"] == 0
