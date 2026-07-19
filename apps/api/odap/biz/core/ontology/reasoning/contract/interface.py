"""
+AI ReasoningServiceContract — 推理能力统一入口。

供 L1 Design、L3 Application 调用 AI 推理能力。
注意: reasoning/ 是技术能力层而非领域层。
实现可替换（规则引擎 / LLM-based / 混合）。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TypeInferenceResult:
    """类型推断结果"""
    suggestions: tuple = ()           # tuple of dicts {entity_type_name, description, confidence}
    explanation: str = ""
    confidence: float = 0.0


@dataclass(frozen=True)
class ConstraintSuggestion:
    """约束建议"""
    property_name: str
    suggested_constraint: str         # e.g. "required", "min:0", "enum:['a','b']"
    rationale: str = ""
    confidence: float = 0.0


@dataclass(frozen=True)
class ConsistencyReport:
    """一致性校验报告"""
    entity_type_id: str = ""
    pass_count: int = 0
    fail_count: int = 0
    anomalies: tuple = ()             # tuple of anomaly dicts
    severity: str = "info"            # info / warning / error
    generated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ReasoningServiceContract:
    """
    +AI Reasoning 统一推理服务契约.

    所有 AI 推理能力通过此契约暴露。tool-calling 智能体
    可通过 get_reasoning_capabilities() 动态发现可用能力。
    """

    # ── 推理组 (服务 L1 Design) ──

    def infer_types(
        self, data_sample: dict, workspace_id: str,
    ) -> TypeInferenceResult:
        """分析数据样本，建议新 EntityType"""
        raise NotImplementedError

    def suggest_constraints(
        self, entity_type_id: str,
    ) -> List[ConstraintSuggestion]:
        """分析已有实例，建议属性约束"""
        raise NotImplementedError

    # ── 一致性组 (服务 L2 Construction) ──

    def check_schema_consistency(
        self, ontology_id: str,
    ) -> ConsistencyReport:
        """Schema 级一致性校验"""
        raise NotImplementedError

    def check_instance_consistency(
        self, entity_type_id: str, instance_ids: Optional[List[str]] = None,
    ) -> ConsistencyReport:
        """实例级一致性校验"""
        raise NotImplementedError

    # ── 分析组 (服务 L3 Application) ──

    def get_reasoning_capabilities(self) -> List[str]:
        """返回可用推理能力列表（供工具注册发现）"""
        raise NotImplementedError
