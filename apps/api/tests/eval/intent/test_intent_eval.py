"""F7 意图评测集门禁（AC-32 ~ AC-35）。

两层校验：
1. **数据集完整性**（AC-32）：四类用例数量下限、id/query 唯一、无占位词、真实业务语义；
2. **指标回归**（AC-33/34）：调用 `scripts/eval_intent.py`，跑回归门禁 + 绝对阈值。

三级漏斗（L1 词典 → L2 语义召回 → L3 受限消歧，ADR-095）落地后，
AC-33/AC-34 的绝对阈值已达标，因此这里**全部是硬断言**，不再有 xfail 兜底：
任一项跌破阈值即失败，参数调优不留"挂着标记继续跑"的余地。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
EVAL_DIR = ROOT / "apps" / "api" / "tests" / "eval" / "intent"
CASES = EVAL_DIR / "cases.json"
BASELINE = EVAL_DIR / "baseline.json"
RUNNER = ROOT / "scripts" / "eval_intent.py"

MIN_COUNTS = {"synonym": 200, "cross_domain": 100, "composite": 100, "distractor": 100}
PLACEHOLDER = re.compile(r"\b(foo|bar|baz|qux|test123|abc123|xxx)\b", re.IGNORECASE)


def _load_cases() -> dict:
    return json.loads(CASES.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dataset() -> dict:
    assert CASES.is_file(), f"评测集缺失：{CASES}（运行 build_cases.py 生成）"
    return _load_cases()


@pytest.fixture(scope="module")
def metrics(tmp_path_factory) -> dict:
    """跑一次 runner，取指标（同时验证 CLI 退出码 = 0）。"""
    out = tmp_path_factory.mktemp("eval") / "result.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--json", str(out)],
        cwd=str(ROOT), capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "apps" / "api")},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(out.read_text(encoding="utf-8"))


class TestDatasetSize:
    def test_category_counts_meet_ac32(self, dataset):
        counts = dataset["counts"]
        for category, minimum in MIN_COUNTS.items():
            assert counts[category] >= minimum, (
                f"AC-32 要求 {category} ≥ {minimum}，实际 {counts[category]}"
            )

    def test_total_matches_actual_cases(self, dataset):
        assert dataset["counts"]["total"] == len(dataset["cases"])

    def test_all_four_categories_present(self, dataset):
        categories = {c["category"] for c in dataset["cases"]}
        assert categories == set(MIN_COUNTS)


class TestDatasetIntegrity:
    def test_ids_unique(self, dataset):
        ids = [c["id"] for c in dataset["cases"]]
        assert len(set(ids)) == len(ids)

    def test_queries_unique(self, dataset):
        queries = [c["query"] for c in dataset["cases"]]
        assert len(set(queries)) == len(queries)

    def test_no_placeholder_vocabulary(self, dataset):
        bad = [c["query"] for c in dataset["cases"] if PLACEHOLDER.search(c["query"])]
        assert not bad, f"评测集出现占位词：{bad[:3]}"

    def test_queries_are_chinese_business_language(self, dataset):
        for case in dataset["cases"]:
            assert re.search(r"[\u4e00-\u9fff]", case["query"]), case
            assert len(case["query"]) >= 4, case

    def test_expected_intent_in_taxonomy(self, dataset):
        allowed = {
            "concept_lookup", "relation_lookup", "property_lookup", "metric_query",
            "process_lookup", "rule_lookup", "action_request", "unknown",
        }
        for case in dataset["cases"]:
            assert case["expected_intent"] in allowed, case

    def test_distractors_have_no_expected_slots(self, dataset):
        for case in dataset["cases"]:
            if case["category"] == "distractor":
                assert case["expected_terms"] == [], case

    def test_non_distractors_declare_slots(self, dataset):
        for case in dataset["cases"]:
            if case["category"] != "distractor":
                assert case["expected_terms"], case

    def test_business_terminology_coverage(self, dataset):
        """数据集必须覆盖真实业务词（订单/退货率/供应商/品类/库存），不许空壳。"""
        corpus = "".join(c["query"] for c in dataset["cases"])
        for keyword in ("退货", "库存", "供应商", "品类", "订单"):
            assert keyword in corpus, f"评测集缺少业务词：{keyword}"


class TestMetrics:
    def test_all_metrics_reported(self, metrics):
        reported = metrics["metrics"]
        for key in ("intent_acc_at_1", "slot_f1", "gen_gap", "clarify_rate",
                    "unmapped_rate"):
            assert key in reported, f"缺少指标 {key}"

    def test_metric_ranges(self, metrics):
        reported = metrics["metrics"]
        for key in ("intent_acc_at_1", "slot_f1", "clarify_rate", "unmapped_rate"):
            assert 0.0 <= reported[key] <= 1.0, key
        assert -1.0 <= reported["gen_gap"] <= 1.0

    def test_clarify_rate_is_nonzero(self, metrics):
        """L1 词典不可能全命中；有澄清说明系统在"不猜"（AC-25）而不是乱答。"""
        assert metrics["metrics"]["clarify_rate"] > 0.0

    def test_no_regression_against_baseline(self, metrics):
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        reported = metrics["metrics"]
        tolerance = 0.02
        for key, base in baseline.items():
            current = reported[key]
            if key in {"gen_gap", "unmapped_rate"}:
                assert current <= base + tolerance, (
                    f"{key} 劣于基线：{current:.4f} > {base:.4f}"
                )
            else:
                assert current >= base - tolerance, (
                    f"{key} 劣于基线：{current:.4f} < {base:.4f}"
                )


class TestAcceptanceThresholds:
    """AC-33 / AC-34 的绝对阈值 + 跨域/复合分类准确率下限（硬断言，无 xfail）。"""

    @pytest.mark.regression
    def test_ac33_intent_acc(self, metrics):
        assert metrics["metrics"]["intent_acc_at_1"] >= 0.90

    @pytest.mark.regression
    def test_ac33_slot_f1(self, metrics):
        assert metrics["metrics"]["slot_f1"] >= 0.85

    @pytest.mark.regression
    def test_ac34_gen_gap(self, metrics):
        assert metrics["metrics"]["gen_gap"] <= 0.10

    @pytest.mark.regression
    def test_cross_domain_accuracy(self, metrics):
        """跨域迁移：未见过的域词也要靠形态/上下文判对，单看总 Acc 会掩盖它。"""
        assert metrics["metrics"]["acc_by_category"]["cross_domain"] >= 0.80

    @pytest.mark.regression
    def test_composite_accuracy(self, metrics):
        """复合问句：主意图 + 子意图都要对，主意图错则该条判错。"""
        assert metrics["metrics"]["acc_by_category"]["composite"] >= 0.80

    @pytest.mark.regression
    def test_distractor_accuracy(self, metrics):
        """干扰项必须走澄清，不许硬判一个意图（AC-25 不猜）。"""
        assert metrics["metrics"]["acc_by_category"]["distractor"] >= 0.80
