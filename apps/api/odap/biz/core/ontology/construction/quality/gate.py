"""QualityGate — 三级质量门禁系统。

构建前校验 (pre) → 构建中监控 (inline) → 构建后验证 (post)

每级门禁有独立的规则集，支持 BLOCK(阻断)、WARN(告警)、PASS(通过) 三种结果。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class GateLevel(str, Enum):
    PRE = "pre"        # 构建前
    INLINE = "inline"  # 构建中
    POST = "post"      # 构建后


class GateAction(str, Enum):
    BLOCK = "block"    # 阻断构建
    WARN = "warn"      # 告警但继续
    PASS = "pass"      # 通过


@dataclass
class GateCheckResult:
    """单条规则检查结果"""
    rule_name: str
    level: GateLevel
    action: GateAction
    passed: bool
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    score: float = 1.0  # 0-1 质量分


@dataclass
class GateResult:
    """门禁执行结果"""
    level: GateLevel
    checks: List[GateCheckResult] = field(default_factory=list)
    blocked: bool = False

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def warnings(self) -> List[GateCheckResult]:
        return [c for c in self.checks if c.action == GateAction.WARN]

    @property
    def failures(self) -> List[GateCheckResult]:
        return [c for c in self.checks if c.action == GateAction.BLOCK and not c.passed]

    @property
    def overall_score(self) -> float:
        if not self.checks:
            return 1.0
        return sum(c.score for c in self.checks) / len(self.checks)


class QualityGate:
    """质量门禁 — 单例"""

    _instance: Optional["QualityGate"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._rules: Dict[GateLevel, List[Callable]] = {
            GateLevel.PRE: [],
            GateLevel.INLINE: [],
            GateLevel.POST: [],
        }
        self._register_builtin_rules()
        self._initialized = True

    def register_rule(self, level: GateLevel, rule_fn: Callable):
        """注册自定义规则"""
        self._rules[level].append(rule_fn)

    async def pre_check(self, context: Dict[str, Any]) -> GateResult:
        """构建前校验"""
        return await self._run_checks(GateLevel.PRE, context)

    async def inline_check(self, step_type: str, step_result: Dict[str, Any]) -> GateResult:
        """构建中监控"""
        context = {"step_type": step_type, **step_result}
        return await self._run_checks(GateLevel.INLINE, context)

    async def post_check(self, construction_snapshot: Dict[str, Any]) -> GateResult:
        """构建后验证"""
        return await self._run_checks(GateLevel.POST, construction_snapshot)

    async def _run_checks(self, level: GateLevel, context: Dict[str, Any]) -> GateResult:
        result = GateResult(level=level)
        for rule_fn in self._rules[level]:
            try:
                check = await rule_fn(context) if hasattr(rule_fn, '__await__') else rule_fn(context)
                result.checks.append(check)
                if check.action == GateAction.BLOCK and not check.passed:
                    result.blocked = True
            except Exception as e:
                logger.warning("Quality rule %s failed: %s", getattr(rule_fn, '__name__', 'unknown'), e)
                result.checks.append(GateCheckResult(
                    rule_name=getattr(rule_fn, '__name__', 'unknown'),
                    level=level, action=GateAction.WARN,
                    passed=False, message=f"Rule execution error: {e}",
                ))
        return result

    def _register_builtin_rules(self):
        """注册内置规则"""
        # Pre-build rules
        self._rules[GateLevel.PRE].append(self._rule_data_completeness)
        self._rules[GateLevel.PRE].append(self._rule_schema_alignment)
        # Inline rules
        self._rules[GateLevel.INLINE].append(self._rule_field_fill_rate)
        # Post-build rules
        self._rules[GateLevel.POST].append(self._rule_orphan_detection)
        self._rules[GateLevel.POST].append(self._rule_entity_count_threshold)

    # ── 内置规则 ──

    def _rule_data_completeness(self, ctx: dict) -> GateCheckResult:
        """规则: 数据完整性 — 输入数据不得为空"""
        entities = ctx.get("entities", [])
        if not entities:
            return GateCheckResult(
                rule_name="data_completeness", level=GateLevel.PRE,
                action=GateAction.BLOCK, passed=False,
                message="没有可构建的实体数据",
            )
        return GateCheckResult(
            rule_name="data_completeness", level=GateLevel.PRE,
            action=GateAction.PASS, passed=True,
            message=f"输入数据包含 {len(entities)} 个实体",
        )

    def _rule_schema_alignment(self, ctx: dict) -> GateCheckResult:
        """规则: Schema对齐 — 实体类型需在本体定义中存在"""
        entities = ctx.get("entities", [])
        ontology_schema = ctx.get("ontology_schema", {})
        if not ontology_schema:
            return GateCheckResult(
                rule_name="schema_alignment", level=GateLevel.PRE,
                action=GateAction.WARN, passed=True,
                message="未提供本体Schema，跳过类型校验",
                score=0.5,
            )
        valid_types = set(ontology_schema.get("object_types", {}).keys())
        unknown_types = set()
        for e in entities:
            etype = e.get("entity_type", e.get("type", ""))
            if etype and etype not in valid_types:
                unknown_types.add(etype)
        if unknown_types:
            return GateCheckResult(
                rule_name="schema_alignment", level=GateLevel.PRE,
                action=GateAction.WARN, passed=True,
                message=f"发现 {len(unknown_types)} 个未定义类型: {unknown_types}",
                details={"unknown_types": list(unknown_types)},
                score=0.7,
            )
        return GateCheckResult(
            rule_name="schema_alignment", level=GateLevel.PRE,
            action=GateAction.PASS, passed=True,
            message="所有实体类型在本体Schema中有定义",
        )

    def _rule_field_fill_rate(self, ctx: dict) -> GateCheckResult:
        """规则: 字段填充率 — 关键字段不能大面积缺失"""
        entities = ctx.get("entities", [])
        step_type = ctx.get("step_type", "")
        if step_type not in ("normalization", "graph_write"):
            return GateCheckResult(
                rule_name="field_fill_rate", level=GateLevel.INLINE,
                action=GateAction.PASS, passed=True,
                message=f"步骤 {step_type} 不需要检查字段填充率",
            )
        total = len(entities)
        if total == 0:
            return GateCheckResult(
                rule_name="field_fill_rate", level=GateLevel.INLINE,
                action=GateAction.PASS, passed=True, message="无实体数据",
            )
        missing_name = sum(1 for e in entities if not e.get("name") and not e.get("entity_name"))
        missing_type = sum(1 for e in entities if not e.get("entity_type") and not e.get("type"))
        name_rate = missing_name / total
        type_rate = missing_type / total
        if name_rate > 0.5:
            return GateCheckResult(
                rule_name="field_fill_rate", level=GateLevel.INLINE,
                action=GateAction.BLOCK, passed=False,
                message=f"实体名称缺失率 {name_rate:.0%} 超过 50%",
                score=max(0, 1 - name_rate),
            )
        if name_rate > 0.1 or type_rate > 0.1:
            return GateCheckResult(
                rule_name="field_fill_rate", level=GateLevel.INLINE,
                action=GateAction.WARN, passed=True,
                message=f"名称缺失率 {name_rate:.0%}, 类型缺失率 {type_rate:.0%}",
                score=0.8,
            )
        return GateCheckResult(
            rule_name="field_fill_rate", level=GateLevel.INLINE,
            action=GateAction.PASS, passed=True,
            message=f"字段填充率正常 (name={1-name_rate:.0%}, type={1-type_rate:.0%})",
        )

    def _rule_orphan_detection(self, ctx: dict) -> GateCheckResult:
        """规则: 孤立节点检测"""
        entities = ctx.get("entities", [])
        relations = ctx.get("relations", [])
        if not entities:
            return GateCheckResult(
                rule_name="orphan_detection", level=GateLevel.POST,
                action=GateAction.PASS, passed=True, message="无实体数据",
            )
        if not relations:
            return GateCheckResult(
                rule_name="orphan_detection", level=GateLevel.POST,
                action=GateAction.WARN, passed=True,
                message=f"共 {len(entities)} 个实体，0 条关系 — 全部为孤立节点",
                score=0.3,
            )
        linked_ids = set()
        for r in relations:
            linked_ids.add(r.get("source_entity_id", r.get("source", "")))
            linked_ids.add(r.get("target_entity_id", r.get("target", "")))
        entity_ids = {e.get("id", e.get("entity_id", "")) for e in entities}
        orphans = entity_ids - linked_ids - {""}
        orphan_rate = len(orphans) / len(entity_ids) if entity_ids else 0
        if orphan_rate > 0.5:
            return GateCheckResult(
                rule_name="orphan_detection", level=GateLevel.POST,
                action=GateAction.WARN, passed=True,
                message=f"孤立节点率 {orphan_rate:.0%} ({len(orphans)}/{len(entity_ids)})",
                score=max(0, 1 - orphan_rate),
            )
        return GateCheckResult(
            rule_name="orphan_detection", level=GateLevel.POST,
            action=GateAction.PASS, passed=True,
            message=f"孤立节点率正常 ({orphan_rate:.0%})",
        )

    def _rule_entity_count_threshold(self, ctx: dict) -> GateCheckResult:
        """规则: 实体数量阈值 — 过多或过少都告警"""
        entities = ctx.get("entities", [])
        count = len(entities)
        if count == 0:
            return GateCheckResult(
                rule_name="entity_count_threshold", level=GateLevel.POST,
                action=GateAction.BLOCK, passed=False,
                message="构建结果包含 0 个实体",
            )
        if count > 50000:
            return GateCheckResult(
                rule_name="entity_count_threshold", level=GateLevel.POST,
                action=GateAction.WARN, passed=True,
                message=f"实体数量 {count} 超过 50000，建议启用分片",
                score=0.6,
            )
        return GateCheckResult(
            rule_name="entity_count_threshold", level=GateLevel.POST,
            action=GateAction.PASS, passed=True,
            message=f"实体数量 {count} 在正常范围内",
        )


def get_quality_gate() -> QualityGate:
    return QualityGate()


__all__ = [
    "GateLevel", "GateAction", "GateCheckResult", "GateResult",
    "QualityGate", "get_quality_gate",
]
