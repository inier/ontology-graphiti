"""TDD：inject vs query 成本对比（子项目 C E-9）——离线可跑，不接 LLM。"""
from __future__ import annotations

from odap.biz.data.qa.evaluation.compare_inject_vs_query import (
    compare_inject_vs_query,
    run_mode,
    ModeRun,
)
from odap.biz.data.qa.pipeline.understanding.intent_recognizer import EntityExtractor


def _mk(mode, mapping=None, provider=None):
    ex = EntityExtractor()
    if mode == "query":
        ex.set_entity_context(mode="query")
        if provider is not None:
            ex.semantics_provider = provider
    else:
        ex.set_entity_context(mode=mode)
    return ex


class _Provider:
    def __init__(self):
        self.calls = []

    def query(self, expression, domain_id="", kinds=("content",)):
        self.calls.append(expression)
        return {"content": {"canonical": expression}}


def test_run_mode_offline_no_llm():
    ex = _mk("off")
    run = run_mode(ex, ["「甲乙」", "「乙丙」"], mode="off")
    assert isinstance(run, ModeRun)
    assert run.summary["count"] == 2
    assert run.summary["total_entities"] == 2
    assert all(r["round_trips"] == 0 for r in run.per_query)


def test_compare_returns_verdict_and_both_modes():
    out = compare_inject_vs_query(
        ["「甲乙」", "「乙丙」"],
        inject_extractor_factory=lambda: _mk("inject"),
        query_extractor_factory=lambda: _mk("query"),
        provider_map={"甲": "甲", "乙": "乙"},
    )
    assert set(out.keys()) == {"inject", "query", "verdict"}
    assert out["verdict"] in ("ok", "regression")
    assert out["query"]["summary"]["mode"] == "query"


def test_query_mode_counts_round_trips():
    provider = _Provider()
    ex = _mk("query", provider=provider)
    run = run_mode(ex, ["「甲乙」", "「甲乙」"], mode="query",
                   round_counter=provider.calls)
    # 两次 extract 各自清缓存 → provider 被调用（>=1）
    assert run.summary["total_round_trips"] >= 1
