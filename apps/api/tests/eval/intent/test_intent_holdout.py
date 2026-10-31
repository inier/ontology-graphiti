"""留出集（holdout）泛化验证 —— 与 `cases.json` 的回归口径分开。

`cases.json` 由 `build_cases.py` 模板生成，长期迭代后容易"被实现拟合"。
本文件读 `holdout_cases.json`（人工撰写的真实口语/业务问法，不参与生成器），
专门回答一个问题：**换一批没见过的说法，还认不认得对**。

口径：留出集只在代码改动后跑，不参与调参；出现失败必须补实现或补本体，
不允许改这里的期望值（改期望值等于自己给自己出题）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from odap.biz.core.ontology.orchestration.impl.intent_router import (
    L1IntentRouter,
    UslDictionary,
)

EVAL_DIR = Path(__file__).resolve().parent
HOLDOUT = EVAL_DIR / "holdout_cases.json"
TERMS = EVAL_DIR / "usl_terms.json"

MIN_CASES = 50
MIN_CATEGORY_ACC = 0.80


def _load_cases() -> List[Dict[str, Any]]:
    payload = json.loads(HOLDOUT.read_text(encoding="utf-8"))
    return payload["cases"]


@pytest.fixture(scope="module")
def cases() -> List[Dict[str, Any]]:
    assert HOLDOUT.is_file(), f"留出集缺失：{HOLDOUT}"
    return _load_cases()


@pytest.fixture(scope="module")
def predictions(cases) -> List[Dict[str, Any]]:
    terms = json.loads(TERMS.read_text(encoding="utf-8"))["terms"]
    router = L1IntentRouter(dictionary=UslDictionary(loader=lambda: list(terms)))

    async def _run() -> List[Dict[str, Any]]:
        out = []
        for case in cases:
            frame = await router.route(case["query"], {"sub": "holdout"}, "ws-holdout")
            out.append({
                "intent_type": frame.intent_type,
                "terms": list(frame.slots.get("terms") or []),
            })
        return out

    import asyncio

    return asyncio.run(_run())


class TestHoldoutDataset:
    def test_size_meets_floor(self, cases):
        assert len(cases) >= MIN_CASES

    def test_ids_and_queries_unique(self, cases):
        assert len({c["id"] for c in cases}) == len(cases)
        assert len({c["query"] for c in cases}) == len(cases)

    def test_expected_intents_within_taxonomy(self, cases):
        allowed = {
            "concept_lookup", "relation_lookup", "property_lookup", "metric_query",
            "process_lookup", "rule_lookup", "action_request", "unknown",
        }
        for case in cases:
            assert case["expected_intent"] in allowed, case

    def test_covers_all_four_categories(self, cases):
        assert {c["category"] for c in cases} == {
            "synonym", "cross_domain", "composite", "distractor",
        }


class TestHoldoutAccuracy:
    def test_every_case_intent_correct(self, cases, predictions):
        failures = [
            (case["id"], case["query"], case["expected_intent"], pred["intent_type"])
            for case, pred in zip(cases, predictions)
            if pred["intent_type"] != case["expected_intent"]
        ]
        assert not failures, f"留出集意图错判 {len(failures)} 条：{failures[:5]}"

    def test_every_expected_term_grounded(self, cases, predictions):
        """期望术语必须被 ground 到（允许槽位带上左侧修饰语，如「仓库拣货路径」）。

        槽位边界与实体边界不完全对齐是中文的常态（`仓库拣货路径` 是一个名词短语），
        因此这里用「期望术语是否出现在已 ground 的槽位里」判定，不用字面相等。
        """
        missing = [
            (case["id"], case["expected_terms"], pred["terms"])
            for case, pred in zip(cases, predictions)
            if not all(any(term in slot for slot in pred["terms"])
                       for term in case["expected_terms"])
        ]
        assert not missing, f"留出集槽位漏召回 {len(missing)} 条：{missing[:5]}"

    def test_distractors_never_answered(self, cases, predictions):
        """干扰项必须走澄清；判出任何意图都算过度自信。"""
        wrong = [
            (case["id"], pred["intent_type"])
            for case, pred in zip(cases, predictions)
            if case["category"] == "distractor" and pred["intent_type"] != "unknown"
        ]
        assert not wrong, f"干扰项被硬判意图：{wrong[:5]}"

    @pytest.mark.parametrize("category", ["synonym", "cross_domain", "composite", "distractor"])
    def test_per_category_accuracy(self, cases, predictions, category):
        pairs = [(c, p) for c, p in zip(cases, predictions) if c["category"] == category]
        assert pairs, f"留出集缺少类别 {category}"
        correct = sum(1 for c, p in pairs if p["intent_type"] == c["expected_intent"])
        assert correct / len(pairs) >= MIN_CATEGORY_ACC, f"{category} 准确率 {correct}/{len(pairs)}"
