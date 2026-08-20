"""TDD 单元测试：ADR-075 确定性推理引擎。

覆盖：
  T-DET-1: rule_loader 白名单拒绝 eval/exec/import/双下划线
  T-DET-2: rule_loader 白名单拒绝 ';' 析取 / 裸 not / 递归深度超限
  T-DET-3: rule_loader 编译合法规则并重建子句
  T-DET-4: datalog_engine 目标化查询（join）
  T-DET-5: datalog_engine 受限递归（ancestor）
  T-DET-6: datalog_engine 结论截断（> max_conclusions → truncated）
  T-DET-7: temporal_algebra Allen 13 关系判定
  T-DET-8: temporal_algebra 逆关系 / compose / path_consistent
  T-DET-9: rules storage CRUD
  T-DET-10: rules storage 版本快照 + 回滚（§3.2）
  T-DET-11: hybrid 确定性优先
  T-DET-12: hybrid 零推导降级 LLM
  T-DET-13: hybrid 引擎错误拒绝服务（不降级）
  T-DET-14: fact_loader 事实渲染子句

约定（遵循 test_reasoning_persistence_service.py）：
  - SQLite 用 tmp_path 真实 DB，严禁 MagicMock 模拟存储层
  - 每个用例独立临时 DB
  - pyDatalog 全局状态需 clear，防止用例互污染
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from odap.biz.core.ontology.reasoning.engines.deterministic.rule_loader import (
    RuleLoader,
    RuleValidationError,
    validate_rule_text,
)
from odap.biz.core.ontology.reasoning.engines.deterministic.datalog_engine import (
    DatalogEngine,
    ReasoningResult,
)
from odap.biz.core.ontology.reasoning.engines.deterministic.temporal_algebra import (
    BEFORE, MEETS, OVERLAPS, STARTS, DURING, FINISHES, EQUALS,
    AFTER, MET_BY, OVERLAPPED_BY, STARTED_BY, CONTAINS, FINISHED_BY,
    ALLEN_RELATIONS,
    Interval, relation, inverse, compose, path_consistent,
)
from odap.biz.core.ontology.reasoning.engines.deterministic.fact_loader import (
    Fact, FactLoader, facts_to_clauses,
)
from odap.biz.core.ontology.reasoning.rules.models import BusinessRule, RulePriority
from odap.biz.core.ontology.reasoning.rules.storage import SQLiteRuleStorage
from odap.biz.core.ontology.reasoning.engines.hybrid.hybrid_strategy import (
    HybridStrategy,
    HybridOutcome,
)


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def rule_loader() -> RuleLoader:
    return RuleLoader()


@pytest.fixture
def engine() -> DatalogEngine:
    eng = DatalogEngine(max_conclusions=100, rule_timeout_ms=2000)
    yield eng
    eng.clear()
    eng.close()


@pytest.fixture
def rule_storage(tmp_path: Path) -> SQLiteRuleStorage:
    return SQLiteRuleStorage(db_path=str(tmp_path / "rules_test.db"))


@pytest.fixture
def base_rule() -> dict:
    return {
        "rule_id": "r1",
        "ontology_id": "ont1",
        "workspace_id": "ws1",
        "name": "parent_to_ancestor",
        "rule_text": 'ancestor(X, Z) <= parent(X, Y) & ancestor(Y, Z)',
    }


# =====================================================================
# T-DET-1 ~ T-DET-3: rule_loader 白名单
# =====================================================================


class TestRuleLoader:
    def test_reject_forbidden_keywords(self, rule_loader: RuleLoader):
        for kw in ("eval", "exec", "import", "getattr", "open"):
            with pytest.raises(RuleValidationError, match="禁止"):
                rule_loader.compile_rule(
                    f'evil(X) <= parent(X, Y) & {kw}(Y)', "r_x",
                )

    def test_reject_double_underscore(self, rule_loader: RuleLoader):
        with pytest.raises(RuleValidationError, match="禁止片段|双下划线"):
            rule_loader.compile_rule(
                'evil(X) <= parent(X, Y) & __builtins__(Y)', "r_x",
            )

    def test_reject_semicolon_and_not(self, rule_loader: RuleLoader):
        with pytest.raises(RuleValidationError, match="析取|禁止片段"):
            rule_loader.compile_rule(
                'a(X) <= b(X); c(X)', "r_semi",
            )
        with pytest.raises(RuleValidationError, match="禁止片段"):
            rule_loader.compile_rule(
                'a(X) <= b(X) & not c(X)', "r_not",
            )

    def test_reject_missing_arrow(self, rule_loader: RuleLoader):
        with pytest.raises(RuleValidationError, match="'<='"):
            rule_loader.compile_rule('a(X) b(X)', "r_noarrow")

    def test_compile_valid_rule(self, rule_loader: RuleLoader):
        clause = rule_loader.compile_rule(
            'ancestor(X, Z) <= parent(X, Y) & ancestor(Y, Z)', "r1",
        )
        assert "ancestor" in clause and "<=" in clause

    def test_batch_over_limit(self, rule_loader: RuleLoader):
        rules = [{"rule_id": f"r{i}", "rule_text": f'p{i}(X) <= q(X)'} for i in range(101)]
        with pytest.raises(RuleValidationError, match="上限"):
            rule_loader.compile_many(rules)


# =====================================================================
# T-DET-4 ~ T-DET-6: datalog_engine
# =====================================================================


class TestDatalogEngine:
    def test_join_query(self, engine: DatalogEngine):
        engine.load_rules([
            {"rule_id": "r1", "rule_text": 'cousin(X, Z) <= parent(X, Y) & sibling(Y, Z)'},
        ])
        engine.load_facts([
            'parent("alice", "bob")',
            'parent("bob", "carol")',
            'sibling("bob", "dave")',
        ])
        result = engine.ask('cousin("alice", X)')
        assert result.error is None
        assert ("dave",) in result.rows

    def test_recursive_query(self, engine: DatalogEngine):
        engine.load_rules([
            {"rule_id": "r1", "rule_text": 'ancestor(X, Z) <= parent(X, Y) & ancestor(Y, Z)'},
            {"rule_id": "r2", "rule_text": 'ancestor(X, Y) <= parent(X, Y)'},
        ])
        engine.load_facts([
            'parent("a", "b")',
            'parent("b", "c")',
            'parent("c", "d")',
        ])
        result = engine.ask('ancestor("a", X)')
        assert result.error is None
        assert ("b",) in result.rows
        assert ("c",) in result.rows
        assert ("d",) in result.rows

    def test_truncation(self, engine: DatalogEngine):
        # 100+ 事实触发截断
        engine.load_rules([{"rule_id": "r1", "rule_text": 'big(X, Y) <= edge(X, Y)'}])
        facts = [f'edge("n{i}", "n{i + 1}")' for i in range(150)]
        engine.load_facts(facts)
        result = engine.ask('big(X, Y)')
        assert result.truncated is True
        assert len(result.rows) <= 100

    def test_goal_unknown_returns_empty(self, engine: DatalogEngine):
        result = engine.ask('nonexistent(X)')
        assert result.error is None
        assert result.rows == []


# =====================================================================
# T-DET-7 ~ T-DET-8: temporal_algebra
# =====================================================================


class TestTemporalAlgebra:
    def test_all_13_relations(self):
        cases = [
            (Interval(1, 2), Interval(3, 4), BEFORE),
            (Interval(1, 2), Interval(2, 3), MEETS),
            (Interval(1, 3), Interval(2, 4), OVERLAPS),
            (Interval(1, 2), Interval(1, 3), STARTS),
            (Interval(2, 3), Interval(1, 4), DURING),
            (Interval(2, 3), Interval(1, 3), FINISHES),
            (Interval(1, 3), Interval(1, 3), EQUALS),
            (Interval(3, 4), Interval(1, 2), AFTER),
            (Interval(2, 3), Interval(1, 2), MET_BY),
            (Interval(2, 4), Interval(1, 3), OVERLAPPED_BY),
            (Interval(1, 3), Interval(1, 2), STARTED_BY),
            (Interval(1, 4), Interval(2, 3), CONTAINS),
            (Interval(1, 3), Interval(2, 3), FINISHED_BY),
        ]
        for a, b, expected in cases:
            assert relation(a, b) == expected, f"{a} vs {b}"

    def test_inverse(self):
        assert inverse(BEFORE) == AFTER
        assert inverse(AFTER) == BEFORE
        assert inverse(MEETS) == MET_BY
        assert inverse(EQUALS) == EQUALS

    def test_compose(self):
        assert compose(BEFORE, BEFORE) == BEFORE
        assert compose(EQUALS, DURING) == DURING
        assert compose(DURING, BEFORE) == BEFORE

    def test_path_consistent(self):
        chain = [(Interval(1, 2), Interval(2, 3))]
        assert path_consistent(chain, [[MEETS]]) is True
        assert path_consistent(chain, [[BEFORE]]) is False

    def test_relation_count(self):
        assert len(ALLEN_RELATIONS) == 13


# =====================================================================
# T-DET-9 ~ T-DET-10: rules storage
# =====================================================================


class TestRuleStorage:
    def test_crud(self, rule_storage: SQLiteRuleStorage):
        rule = BusinessRule(
            ontology_id="ont1", workspace_id="ws1", name="r1",
            rule_text='ancestor(X, Z) <= parent(X, Y) & ancestor(Y, Z)',
        )
        rule_storage.save(rule)
        got = rule_storage.get(rule.rule_id)
        assert got is not None
        assert got.name == "r1"
        listed = rule_storage.list(ontology_id="ont1", workspace_id="ws1")
        assert len(listed) == 1
        assert rule_storage.delete(rule.rule_id) is True
        assert rule_storage.get(rule.rule_id) is None

    def test_version_snapshot_and_restore(self, rule_storage: SQLiteRuleStorage):
        r1 = BusinessRule(
            rule_id="r1", ontology_id="ont1", workspace_id="ws1",
            name="v1_rule", rule_text='a(X) <= b(X)',
        )
        rule_storage.save(r1)

        # 快照 v1
        n = rule_storage.snapshot_for_version("v1", "ont1", "ws1")
        assert n == 1

        # 删除并新增（模拟 v2 变更）
        rule_storage.delete("r1")
        r2 = BusinessRule(
            rule_id="r2", ontology_id="ont1", workspace_id="ws1",
            name="v2_rule", rule_text='c(X) <= d(X)',
        )
        rule_storage.save(r2)

        # 回滚到 v1 → r1 恢复，r2 消失
        restored = rule_storage.restore_version("v1")
        assert restored == 1
        assert rule_storage.get("r1") is not None
        assert rule_storage.get("r2") is None

    def test_restore_missing_version(self, rule_storage: SQLiteRuleStorage):
        assert rule_storage.restore_version("nonexistent") == 0


# =====================================================================
# T-DET-11 ~ T-DET-13: hybrid strategy
# =====================================================================


class TestHybridStrategy:
    def test_deterministic_priority(self):
        strategy = HybridStrategy(conf_threshold=0.5)
        outcome = strategy.decide("goal", {"rows": [("a",)], "confidence": 1.0})
        assert outcome.source == "deterministic"
        assert outcome.rows == [("a",)]

    def test_zero_derivations_fallback_to_llm(self):
        captured = {}

        def llm(goal, ctx):
            captured["goal"] = goal
            return HybridOutcome(source="llm_hybrid", rows=[("llm",)], confidence=0.9)

        strategy = HybridStrategy(conf_threshold=0.5, llm_fallback=llm)
        outcome = strategy.decide("g", {"rows": [], "confidence": 0.0})
        assert outcome.source == "llm_hybrid"
        assert outcome.fallback_reason == "zero_derivations"
        assert captured["goal"] == "g"

    def test_low_confidence_fallback(self):
        strategy = HybridStrategy(conf_threshold=0.5)

        def llm(goal, ctx):
            return HybridOutcome(source="llm_hybrid", rows=[("llm",)], confidence=0.8)

        strategy.set_llm_fallback(llm)
        outcome = strategy.decide("g", {"rows": [("x",)], "confidence": 0.2})
        assert outcome.source == "llm_hybrid"
        assert outcome.fallback_reason == "low_confidence:0.2"

    def test_engine_error_refuses_service(self):
        strategy = HybridStrategy(conf_threshold=0.5)

        def llm(goal, ctx):
            raise AssertionError("不应降级")

        strategy.set_llm_fallback(llm)
        outcome = strategy.decide("g", {"rows": [], "error": "engine exploded"})
        assert outcome.source == "error"
        assert "engine_error" in outcome.fallback_reason

    def test_timeout_is_fallback_not_error(self):
        strategy = HybridStrategy(conf_threshold=0.5)

        def llm(goal, ctx):
            return HybridOutcome(source="llm_hybrid", rows=[], confidence=0.0)

        strategy.set_llm_fallback(llm)
        outcome = strategy.decide("g", {"rows": [], "error": "timeout (>500ms)"})
        assert outcome.source == "llm_hybrid"
        assert outcome.fallback_reason == "timeout"


# =====================================================================
# T-DET-14: fact_loader
# =====================================================================


class TestFactLoader:
    def test_fact_to_clause(self):
        f = Fact("entity", ("e1", "Person"))
        assert f.to_clause() == 'entity("e1", "Person")'
        f2 = Fact("rel", ("e1", "knows", "e2"))
        assert f2.to_clause() == 'rel("e1", "knows", "e2")'
        f3 = Fact("num", (42,))
        assert f3.to_clause() == "num(42)"

    def test_facts_to_clauses(self):
        facts = [Fact("entity", ("e1", "Person")), Fact("rel", ("e1", "knows", "e2"))]
        clauses = facts_to_clauses(facts)
        assert len(clauses) == 2
        assert clauses[0].startswith("entity(")

    def test_load_entity_facts_empty_on_error(self):
        loader = FactLoader()
        facts = loader.load_entity_facts("MissingType", workspace_id="nonexistent")
        assert facts == []
