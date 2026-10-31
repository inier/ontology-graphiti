"""动作意图组合式召回单测（`intent_actions.py`）。

规则：`<动词> …(≤8字)… <对象术语>`，对象必须是**已召回术语**。
这条约束把「把简历投递出去」这类域外说法挡在写操作之外，
也是「删除一批测试订单」能被认出来的原因（词典里没有连写形式）。
"""

from __future__ import annotations

import pytest

from odap.biz.core.ontology.orchestration.impl.intent_actions import (
    ACTION_VERBS,
    find_action_spans,
)
from odap.biz.core.ontology.orchestration.impl.intent_terms import TermSpan


def _term(surface: str, intent: str = "concept_lookup", start: int = 0) -> TermSpan:
    return TermSpan(surface=surface, start=start, end=start + len(surface),
                    intent=intent, score=1.0, source="dict", canonical=surface)


class TestComposeRecall:
    def test_verb_then_separated_object(self):
        text = "帮我删掉这批测试订单"
        spans = find_action_spans(text, [_term("订单", start=text.index("订单"))])
        assert len(spans) == 1
        assert spans[0].intent == "action_request"
        assert spans[0].surface == "删掉这批测试订单"
        assert spans[0].source == "compose"

    def test_object_before_verb(self):
        text = "把滞销商品清单导出来"
        spans = find_action_spans(text, [_term("商品", start=text.index("商品"))])
        assert spans and spans[0].surface.startswith("商品")

    def test_compose_score_below_dict(self):
        text = "导出订单"
        spans = find_action_spans(text, [_term("订单", start=2)])
        assert spans and spans[0].score < 1.0

    def test_offsets_match_surface(self):
        text = "帮我冻结供应商"
        spans = find_action_spans(text, [_term("供应商", start=text.index("供应商"))])
        assert text[spans[0].start:spans[0].end] == spans[0].surface


class TestRejections:
    def test_no_term_no_action(self):
        """对象不是已召回术语 → 不做开放式猜测。"""
        assert find_action_spans("帮我删掉那个东西", []) == []

    def test_verb_outside_whitelist_ignored(self):
        """投递/申请/寄出 不在业务动作白名单里。"""
        text = "把简历投递出去"
        assert find_action_spans(text, [_term("简历", start=2)]) == []
        for verb in ("投递", "申请", "寄出"):
            assert verb not in ACTION_VERBS

    def test_metric_is_not_an_action_object(self):
        """指标不能被"删除"（对象意图类别受限）。"""
        text = "删除退货率"
        assert find_action_spans(text, [_term("退货率", "metric_query", 2)]) == []

    def test_gap_beyond_limit_rejected(self):
        text = "删除" + "一二三四五六七八九十" + "订单"
        assert find_action_spans(text, [_term("订单", start=text.index("订单"))]) == []

    @pytest.mark.parametrize("intent", ["concept_lookup", "property_lookup", "relation_lookup"])
    def test_allowed_object_intents(self, intent):
        text = "冻结供应商"
        spans = find_action_spans(text, [_term("供应商", intent, 2)])
        assert spans and spans[0].intent == "action_request"


class TestDedupe:
    def test_overlapping_matches_collapse_to_longest(self):
        text = "更新订单状态"
        terms = [_term("订单", start=2), _term("状态", "property_lookup", 4)]
        spans = find_action_spans(text, terms)
        assert len(spans) == 1
        assert text[spans[0].start:spans[0].end] == spans[0].surface

    def test_multiple_verbs_keep_separate_spans(self):
        text = "冻结供应商，然后导出订单"
        terms = [_term("供应商", start=2), _term("订单", start=text.index("订单"))]
        spans = find_action_spans(text, terms)
        assert [s.surface for s in spans] == ["冻结供应商", "导出订单"]

    def test_output_sorted_by_position(self):
        text = "冻结供应商，然后导出订单"
        terms = [_term("供应商", start=2), _term("订单", start=text.index("订单"))]
        spans = find_action_spans(text, terms)
        assert [s.start for s in spans] == sorted(s.start for s in spans)


def test_action_verbs_cover_common_business_writes():
    for verb in ("删除", "导出", "冻结", "调整", "下发", "驳回"):
        assert verb in ACTION_VERBS
