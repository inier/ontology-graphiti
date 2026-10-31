"""L2 形态学召回单测（`intent_cues.py`）。

重点不是"能召回多少"，而是**召回纪律**：
- 后缀必须落在名词右边界、且后面是明确的数据问法；
- 弱后缀（数/量/天数）必须带业务域词，否则「年假天数还剩多少」会被当业务指标；
- 同比/环比、介词「比」不能当后缀。

这些反例就是跨域泛化不崩的原因，缺一条都会让干扰项识别退化。
"""

from __future__ import annotations

import pytest

from odap.biz.core.ontology.orchestration.impl.intent_cues import (
    METRIC_CUES,
    extract_cue_spans,
)


def _surfaces(text: str):
    return [(c.surface, c.intent) for c in extract_cue_spans(text)]


class TestMetricRecall:
    @pytest.mark.parametrize("query,surface", [
        ("电商业务的动销率这季度怎么样", "动销率"),
        ("仓容利用率还有多少空间", "仓容利用率"),
        ("最近三个月的库存周转天数是多少", "库存周转天数"),
        ("咱们店的坪效现在什么水平", "坪效"),
        ("缺货天数超过五天", "缺货天数"),
        ("库存量有没有变化", "库存量"),
    ])
    def test_unseen_domain_noun_recalled_as_metric(self, query, surface):
        """词典里没有的词，靠构词后缀也要能判成指标。"""
        found = _surfaces(query)
        assert (surface, "metric_query") in found, found

    def test_long_suffix_preferred_over_short(self):
        """`利用率` 不能被拆成 `率` 后把前缀丢掉。"""
        spans = extract_cue_spans("仓容利用率还有多少空间")
        assert spans[0].cue == "利用率"
        assert spans[0].surface == "仓容利用率"

    def test_metric_span_score_range(self):
        for span in extract_cue_spans("电商业务的动销率这季度怎么样"):
            assert 0.85 <= span.score < 1.0


class TestNonMetricRecall:
    @pytest.mark.parametrize("query", [
        "补货触发条件有哪些",
        "退货质检环节有哪些",
        "安全库存水位现在多少",
    ])
    def test_other_intent_suffixes(self, query):
        intents = [c.intent for c in extract_cue_spans(query)]
        assert intents and intents[0] in {"rule_lookup", "process_lookup", "property_lookup"}


class TestWeakSuffixGate:
    """弱后缀必须伴随业务域词 —— 这是挡住 HR/行政类域外问题的唯一闸门。"""

    @pytest.mark.parametrize("query", [
        "年假天数还剩多少",
        "员工数量有多少",
        "社保基数是多少",
    ])
    def test_weak_suffix_without_business_token_not_recalled(self, query):
        assert extract_cue_spans(query) == []

    @pytest.mark.parametrize("query", [
        "缺货天数超过五天",
        "订单量怎么算",
        "库存周转天数是多少",
    ])
    def test_weak_suffix_with_business_token_recalled(self, query):
        assert extract_cue_spans(query), query


class TestModifierExclusion:
    def test_year_over_year_is_modifier_not_cue(self):
        """「退货率同比情况」的「比」是修饰语，槽位应止于 `退货率`。"""
        spans = extract_cue_spans("上季度华东区退货率同比情况")
        assert [s.surface for s in spans] == ["季度华东区退货率"]

    def test_bi_as_preposition_not_cue(self):
        """「人效比去年」的「比」是介词，槽位应止于 `人效`。"""
        surfaces = [s.surface for s in extract_cue_spans("人效比去年提升了多少")]
        assert surfaces == ["人效"]

    def test_month_over_month_still_recalls_metric(self):
        surfaces = [s.surface for s in extract_cue_spans("动销率环比变化")]
        assert surfaces == ["动销率"]


class TestQuestionShapeGate:
    @pytest.mark.parametrize("query", [
        "动销率下降",
        "毛利率提升了",
        "社保基数调整了吗",
        "报销流程怎么走",
    ])
    def test_statement_or_out_of_domain_not_recalled(self, query):
        """宁可漏召回，也不把陈述句/域外问题当数据问句。"""
        assert extract_cue_spans(query) == []

    def test_bare_noun_phrase_recalled(self):
        assert [s.surface for s in extract_cue_spans("退货率")] == ["退货率"]

    def test_temporal_adverb_before_marker(self):
        """「目前如何」：时间副词剥离后仍要看问法。"""
        assert extract_cue_spans("人效目前如何")


class TestSpanShape:
    def test_boundary_stops_at_left_modifier(self):
        span = extract_cue_spans("上季度华东区退货率")[0]
        assert span.surface.endswith("退货率")
        assert not span.surface.startswith("上")

    def test_offsets_match_surface(self):
        text = "电商业务的动销率这季度怎么样"
        for span in extract_cue_spans(text):
            assert text[span.start:span.end] == span.surface

    def test_no_duplicate_nested_spans(self):
        spans = extract_cue_spans("仓容利用率还有多少空间")
        assert len(spans) == len({(s.start, s.end) for s in spans})

    def test_metric_cues_include_core_suffixes(self):
        for suffix in ("率", "额", "量", "天数", "利用率", "周转率"):
            assert suffix in METRIC_CUES
