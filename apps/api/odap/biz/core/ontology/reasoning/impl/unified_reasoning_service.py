"""UnifiedReasoningServiceV2 — 确定性优先的推理服务实现 (ADR-075)。

扩展 ReasoningServiceContract：
- 保留 LLM-based 能力（类型推断/约束建议），复用现有服务逻辑。
- 新增确定性推理入口 reason()：Datalog 引擎 + hybrid 降级。
- 规则库来自 rules.storage（随本体版本）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..contract.interface import (
    ReasoningServiceContract,
    TypeInferenceResult,
    ConstraintSuggestion,
    ConsistencyReport,
)
from ..engines.deterministic.datalog_engine import DatalogEngine, ReasoningResult
from ..engines.deterministic.rule_loader import RuleLoader, RuleValidationError
from ..engines.hybrid.hybrid_strategy import HybridStrategy, HybridOutcome
from ..rules.storage import SQLiteRuleStorage, get_rule_storage

logger = logging.getLogger(__name__)


class UnifiedReasoningServiceV2(ReasoningServiceContract):
    """确定性优先的统一推理服务（ADR-075 §4）"""

    def __init__(
        self,
        rule_storage: Optional[SQLiteRuleStorage] = None,
        engine: Optional[DatalogEngine] = None,
        hybrid: Optional[HybridStrategy] = None,
        conf_threshold: Optional[float] = None,
    ):
        self.rule_storage = rule_storage or get_rule_storage()
        self.engine = engine or DatalogEngine(rule_loader=RuleLoader())
        import os
        threshold = conf_threshold or float(
            os.environ.get("REASONING_CONF_THRESHOLD", "0.5")
        )
        self.hybrid = hybrid or HybridStrategy(conf_threshold=threshold)
        self._capabilities_cache: Optional[List[str]] = None

    # ── 确定性推理入口（ADR-075 核心）──

    def reason(
        self,
        goal: str,
        ontology_id: str,
        workspace_id: str = "default",
        entity_type_ids: Optional[List[str]] = None,
        bindings: Optional[Dict[str, Any]] = None,
    ) -> HybridOutcome:
        """执行确定性推理（hybrid 降级）。

        流程：
        1. 加载本体启用规则（rules.storage）
        2. 加载 ABox 事实（fact_loader）
        3. Datalog 目标化查询
        4. hybrid 决策（确定性优先 / 降级 / 拒绝服务）
        """
        # 1. 加载规则
        rules = self.rule_storage.list(
            ontology_id=ontology_id,
            workspace_id=workspace_id,
            enabled_only=True,
        )
        if not rules:
            return HybridOutcome(
                source="deterministic",
                rows=[],
                confidence=0.0,
                fallback_reason="no_rules",
            )

        try:
            # 2. 重置引擎并加载规则 + 事实
            self.engine.clear()
            self.engine.load_rules([r.model_dump() for r in rules])
            facts = self._load_facts(ontology_id, workspace_id, entity_type_ids)
            self.engine.load_fact_objects(facts)

            # 3. 目标化查询
            query = self._bind_goal(goal, bindings)
            result = self.engine.ask(query)

            # 4. hybrid 决策
            deterministic = {
                "rows": result.rows,
                "truncated": result.truncated,
                "elapsed_ms": result.elapsed_ms,
                "error": result.error,
                "confidence": self._confidence(result),
            }
            outcome = self.hybrid.decide(
                goal=query,
                deterministic=deterministic,
                context={
                    "ontology_id": ontology_id,
                    "workspace_id": workspace_id,
                    "rule_count": len(rules),
                    "fact_count": len(facts),
                },
            )
            return outcome
        except RuleValidationError as e:
            logger.error("规则校验失败（拒绝服务）: %s", e)
            return HybridOutcome(
                source="error",
                rows=[],
                confidence=0.0,
                fallback_reason=f"rule_validation_error:{e}",
            )
        except Exception as e:
            logger.error("确定性推理失败（拒绝服务，不降级）: %s", e)
            return HybridOutcome(
                source="error",
                rows=[],
                confidence=0.0,
                fallback_reason=f"engine_error:{e}",
            )

    def _load_facts(
        self,
        ontology_id: str,
        workspace_id: str,
        entity_type_ids: Optional[List[str]],
    ) -> List[Any]:
        """加载 ABox 事实（entity/type_prop/rel/interval）"""
        from ..engines.deterministic.fact_loader import FactLoader
        loader = FactLoader()
        return loader.load_all(
            entity_type_ids=entity_type_ids,
            workspace_id=workspace_id,
        )

    @staticmethod
    def _bind_goal(goal: str, bindings: Optional[Dict[str, Any]]) -> str:
        """将 bindings 中的常量绑定到 goal 中同名变量。

        goal 中形如 {name} 的占位符替换为常量字面量。
        """
        if not bindings:
            return goal
        import re
        for name, val in bindings.items():
            goal = goal.replace("{" + name + "}", _literal(val))
        return goal

    @staticmethod
    def _confidence(result: ReasoningResult) -> float:
        """确定性推导置信度：有结论且无错误 → 1.0；否则 0.0"""
        if result.error or not result.rows:
            return 0.0
        return 1.0

    # ── ReasoningServiceContract 兼容（复用既有能力）──

    def infer_types(self, data_sample: dict, workspace_id: str) -> TypeInferenceResult:
        from ..services.unified_reasoning import get_reasoning_service
        return get_reasoning_service().infer_types(data_sample, workspace_id)

    def suggest_constraints(self, entity_type_id: str) -> List[ConstraintSuggestion]:
        from ..services.unified_reasoning import get_reasoning_service
        return get_reasoning_service().suggest_constraints(entity_type_id)

    def check_schema_consistency(self, ontology_id: str) -> ConsistencyReport:
        from ..services.unified_reasoning import get_reasoning_service
        return get_reasoning_service().check_schema_consistency(ontology_id)

    def check_instance_consistency(
        self, entity_type_id: str, instance_ids: Optional[List[str]] = None,
    ) -> ConsistencyReport:
        from ..services.unified_reasoning import get_reasoning_service
        return get_reasoning_service().check_instance_consistency(entity_type_id, instance_ids)

    def get_reasoning_capabilities(self) -> List[str]:
        if self._capabilities_cache is None:
            self._capabilities_cache = [
                "infer_types",
                "suggest_constraints",
                "check_schema_consistency",
                "check_instance_consistency",
                "reason",                 # ★ ADR-075 确定性推理
                "rule_crud",              # ★ 规则库管理
                "unified_retrieve",
                "trace_provenance",
            ]
        return self._capabilities_cache

    # ── 规则库管理 ──

    def create_rule(self, rule: Any) -> Any:
        """保存规则（白名单校验后入库）"""
        self.engine._rule_loader.compile_rule(rule.rule_text, rule.rule_id)
        return self.rule_storage.save(rule)

    def list_rules(self, ontology_id: str, workspace_id: str = "default") -> List[Any]:
        return self.rule_storage.list(
            ontology_id=ontology_id, workspace_id=workspace_id, enabled_only=False,
        )

    def snapshot_rules(self, version_id: str, ontology_id: str, workspace_id: str) -> int:
        """版本快照（§3.2 回滚联动）"""
        return self.rule_storage.snapshot_for_version(version_id, ontology_id, workspace_id)

    def restore_rules(self, version_id: str) -> int:
        """版本回滚恢复（§3.2）"""
        return self.rule_storage.restore_version(version_id)


def _literal(val: Any) -> str:
    """将绑定值渲染为 Datalog 字面量"""
    from ..engines.deterministic.fact_loader import _render_arg
    return _render_arg(val)


_instance: Optional[UnifiedReasoningServiceV2] = None


def get_reasoning_service_v2() -> UnifiedReasoningServiceV2:
    """获取确定性优先推理服务单例"""
    global _instance
    if _instance is None:
        _instance = UnifiedReasoningServiceV2()
    return _instance


__all__ = ["UnifiedReasoningServiceV2", "get_reasoning_service_v2"]
