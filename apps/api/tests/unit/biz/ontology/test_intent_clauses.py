"""复合问句切分与主意图判定单测（`intent_clauses.py`）。

主意图规则就两条：**强度高者胜、同强度取最早子句**。
「动作词出现就抢占主意图」是上一版 61% 的根因，这里用反例钉死它。
"""

from __future__ import annotations

from odap.biz.core.ontology.orchestration.impl.intent_clauses import (
    CONNECTIVES,
    split_clauses,
    strongest_clause,
)


class TestSplitClauses:
    def test_split_on_comma(self):
        clauses = split_clauses("上季度退货率是多少，然后删除订单")
        assert [c.stripped for c in clauses] == ["上季度退货率是多少", "删除订单"]

    def test_split_on_connective_without_punctuation(self):
        clauses = split_clauses("退货率是多少并且冻结供应商")
        assert [c.stripped for c in clauses] == ["退货率是多少", "冻结供应商"]

    def test_connective_recorded_for_traceability(self):
        clauses = split_clauses("上季度退货率是多少，然后删除订单")
        assert clauses[1].connective == "然后"

    def test_longest_connective_wins(self):
        """`并且对比` 整块被吃掉，不能残留「对比」到下一个子句里。"""
        clauses = split_clauses("退货率和履约率是多少并且对比上月")
        assert clauses[-1].stripped == "上月"
        assert clauses[-1].connective == "并且对比"

    def test_single_clause_when_no_separator(self):
        clauses = split_clauses("上季度华东区退货率")
        assert len(clauses) == 1
        assert clauses[0].start == 0

    def test_offsets_preserved(self):
        text = "上季度退货率是多少，然后删除订单"
        for clause in split_clauses(text):
            assert text[clause.start:clause.end] == clause.text

    def test_empty_query_returns_one_empty_clause(self):
        assert len(split_clauses("")) == 1

    def test_connectives_cover_business_phrasings(self):
        for word in ("然后", "同时", "顺便", "还要看", "另外"):
            assert word in CONNECTIVES


class TestStrongestClause:
    def test_highest_score_wins(self):
        clauses = split_clauses("上季度退货率是多少，然后删除订单")
        assert strongest_clause(clauses, [0.6, 1.0]) == 1

    def test_tie_takes_earliest(self):
        """主句在前：同层证据时不能被后面的动作子句抢走。"""
        clauses = split_clauses("上季度退货率是多少，然后删除订单")
        assert strongest_clause(clauses, [1.0, 1.0]) == 0

    def test_zero_scores_take_first(self):
        clauses = split_clauses("你好，谢谢")
        assert strongest_clause(clauses, [0.0, 0.0]) == 0

    def test_empty_clauses_returns_minus_one(self):
        assert strongest_clause([], []) == -1

    def test_missing_scores_treated_as_zero(self):
        clauses = split_clauses("上季度退货率是多少，然后删除订单")
        assert strongest_clause(clauses, []) == 0
