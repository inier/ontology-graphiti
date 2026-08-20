"""决策一等公民数据模型（ADR-076 §3）

DecisionRecord 是跨 Agent/会话引用的结构化决策记录，
承载"谁、何时、基于什么证据、选择了什么、结果如何"的完整信息。
"""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DecisionOutcome(str, Enum):
    """决策结果（ADR-076 §3：含 partial_success 五值，OPA 拒绝路径必填 rejected）"""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    PENDING = "pending"
    REJECTED = "rejected"


class CausalLinkType(str, Enum):
    """决策间因果边类型（ADR-076 §4.5，对齐 Semantica CAUSED/INFLUENCED/PRECEDENT_FOR）"""

    CAUSED_BY = "CAUSED_BY"          # 直接导致（父决策语义）
    INFLUENCED_BY = "INFLUENCED_BY"  # 弱影响（上下文参考但未直接采纳）
    PRECEDENT_FOR = "PRECEDENT_FOR"  # 先例引用留痕（旧决策 → 新决策）


class DecisionRecord(BaseModel):
    """决策记录（一等公民对象）"""

    # 标识
    decision_id: str = Field(
        default_factory=lambda: f"dec_{uuid.uuid4().hex[:12]}",
        description="决策唯一标识",
    )
    workspace_id: str = Field(description="工作空间（隔离主键，禁止为空）")

    # 输入
    context_summary: str = Field(default="", description="决策场景描述")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="约束条件")

    # 推理
    reasoning: str = Field(default="", description="推理过程摘要")
    reasoning_trace: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="结构化推理轨迹（规范格式见 ADR-075 §4 step 对象）",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="置信度 0-1")

    # 证据
    evidence_episode_ids: List[str] = Field(
        default_factory=list, description="证据 Episode UUID 列表"
    )
    evidence_entity_ids: List[str] = Field(
        default_factory=list, description="证据实体 UUID 列表"
    )

    # 输出
    recommended_option: str = Field(default="", description="选定方案")
    alternative_options: List[str] = Field(default_factory=list, description="备选方案")
    decision_method: str = Field(default="recommendation_engine", description="决策方法")
    decision_type: str = Field(default="general", description="决策类型")

    # 因果链
    parent_decision_id: Optional[str] = Field(None, description="父决策（CAUSED_BY 链）")
    root_goal_id: Optional[str] = Field(None, description="根目标 ID")
    precedent_decision_ids: List[str] = Field(
        default_factory=list,
        description="实际采纳的先例决策（record 时自动建立 PRECEDENT_FOR 边留痕）",
    )

    # 执行关联
    action_record_id: Optional[str] = Field(None, description="关联 ActionRecord")

    # 结果
    outcome: DecisionOutcome = Field(default=DecisionOutcome.PENDING, description="决策结果")
    outcome_details: Dict[str, Any] = Field(default_factory=dict, description="结果明细")
    feedback_summary: Optional[str] = Field(None, description="反馈摘要")

    # 元数据
    agent_id: Optional[str] = Field(None, description="决策 Agent")
    opa_approved: Optional[bool] = Field(None, description="OPA 门禁批准（落库前校验）")
    opa_decision: Optional[Dict[str, Any]] = Field(None, description="OPA 完整决策详情")
    created_at: datetime = Field(default_factory=_utcnow, description="创建时间（业务时态锚点）")
    updated_at: datetime = Field(default_factory=_utcnow, description="更新时间")
    valid_at: datetime = Field(default_factory=_utcnow, description="生效时间（业务时态）")
    invalid_at: Optional[datetime] = Field(None, description="失效时间（业务时态）")

    def to_node_properties(self) -> Dict[str, Any]:
        """转为图节点扩展属性（复杂结构序列化为 JSON 字符串）"""

        def _dt(v: Optional[datetime]) -> Optional[str]:
            return v.isoformat() if v else None

        return {
            "decision_id": self.decision_id,
            "workspace_id": self.workspace_id,
            "context_summary": self.context_summary,
            "constraints": json.dumps(self.constraints, ensure_ascii=False, default=str),
            "reasoning": self.reasoning,
            "reasoning_trace": json.dumps(self.reasoning_trace, ensure_ascii=False, default=str),
            "confidence": self.confidence,
            "evidence_episode_ids": json.dumps(self.evidence_episode_ids),
            "evidence_entity_ids": json.dumps(self.evidence_entity_ids),
            "recommended_option": self.recommended_option,
            "alternative_options": json.dumps(self.alternative_options, ensure_ascii=False),
            "decision_method": self.decision_method,
            "decision_type": self.decision_type,
            "parent_decision_id": self.parent_decision_id,
            "root_goal_id": self.root_goal_id,
            "precedent_decision_ids": json.dumps(self.precedent_decision_ids),
            "action_record_id": self.action_record_id,
            "outcome": self.outcome.value,
            "outcome_details": json.dumps(self.outcome_details, ensure_ascii=False, default=str),
            "feedback_summary": self.feedback_summary,
            "agent_id": self.agent_id,
            "opa_approved": self.opa_approved,
            "opa_decision": json.dumps(self.opa_decision, ensure_ascii=False, default=str)
            if self.opa_decision is not None
            else None,
            "created_at": _dt(self.created_at),
            "updated_at": _dt(self.updated_at),
            "valid_at": _dt(self.valid_at),
            "invalid_at": _dt(self.invalid_at),
        }

    @classmethod
    def from_node_properties(cls, props: Dict[str, Any]) -> "DecisionRecord":
        """从图节点属性还原（容忍缺失字段）"""

        def _json(v: Any, default: Any) -> Any:
            if v is None:
                return default
            if isinstance(v, (list, dict)):
                return v
            try:
                return json.loads(v)
            except (TypeError, ValueError):
                return default

        def _dt(v: Any) -> Optional[datetime]:
            if v is None:
                return None
            if isinstance(v, datetime):
                return v
            try:
                return datetime.fromisoformat(str(v))
            except ValueError:
                return None

        outcome_raw = props.get("outcome") or DecisionOutcome.PENDING.value
        try:
            outcome = DecisionOutcome(outcome_raw)
        except ValueError:
            outcome = DecisionOutcome.PENDING

        return cls(
            decision_id=props.get("decision_id") or props.get("uuid", ""),
            workspace_id=props.get("workspace_id") or props.get("group_id", ""),
            context_summary=props.get("context_summary") or "",
            constraints=_json(props.get("constraints"), {}),
            reasoning=props.get("reasoning") or "",
            reasoning_trace=_json(props.get("reasoning_trace"), []),
            confidence=float(props.get("confidence") or 0.0),
            evidence_episode_ids=_json(props.get("evidence_episode_ids"), []),
            evidence_entity_ids=_json(props.get("evidence_entity_ids"), []),
            recommended_option=props.get("recommended_option") or "",
            alternative_options=_json(props.get("alternative_options"), []),
            decision_method=props.get("decision_method") or "recommendation_engine",
            decision_type=props.get("decision_type") or "general",
            parent_decision_id=props.get("parent_decision_id"),
            root_goal_id=props.get("root_goal_id"),
            precedent_decision_ids=_json(props.get("precedent_decision_ids"), []),
            action_record_id=props.get("action_record_id"),
            outcome=outcome,
            outcome_details=_json(props.get("outcome_details"), {}),
            feedback_summary=props.get("feedback_summary"),
            agent_id=props.get("agent_id"),
            opa_approved=props.get("opa_approved"),
            opa_decision=_json(props.get("opa_decision"), None),
            created_at=_dt(props.get("created_at")) or _utcnow(),
            updated_at=_dt(props.get("updated_at")) or _utcnow(),
            valid_at=_dt(props.get("valid_at")) or _utcnow(),
            invalid_at=_dt(props.get("invalid_at")),
        )


class DecisionCausalLink(BaseModel):
    """决策间因果边（ADR-076 §4.5）"""

    from_decision_id: str = Field(description="边起点决策（子决策/被影响方/新决策）")
    to_decision_id: str = Field(description="边终点决策（父决策/影响方/先例）")
    link_type: CausalLinkType = Field(description="因果边类型")
    workspace_id: str = Field(description="工作空间（两端必须同空间）")
    created_at: datetime = Field(default_factory=_utcnow)


class DecisionGateResult(BaseModel):
    """落库前规则门禁结果（ADR-076 §4.6）"""

    approved: bool = Field(description="门禁是否通过")
    gate: str = Field(default="opa", description="门禁来源（opa / business_rule / hybrid）")
    details: Dict[str, Any] = Field(default_factory=dict, description="门禁完整判定详情")


class DecisionChain(BaseModel):
    """决策因果链（ADR-076 §4.2）"""

    decision: DecisionRecord
    evidence_entities: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_episodes: List[Dict[str, Any]] = Field(default_factory=list)
    parent_chain: List[DecisionRecord] = Field(default_factory=list)
    precedents: List[DecisionRecord] = Field(default_factory=list)
    reasoning_trace: List[Dict[str, Any]] = Field(default_factory=list)


class DecisionImpact(BaseModel):
    """决策影响分析（ADR-076 §4.4，返回结构标注完整性）"""

    decision_id: str
    derived_decisions: List[Dict[str, Any]] = Field(
        default_factory=list, description="下游决策（CAUSED_BY 反向遍历 ≤3 跳）"
    )
    target_changes: List[Dict[str, Any]] = Field(
        default_factory=list, description="生效后目标对象的图变化"
    )
    co_evidence_decisions: List[Dict[str, Any]] = Field(
        default_factory=list, description="共享证据实体的其他决策"
    )
    impact_completeness: str = Field(
        default="full",
        description="完整性标注：full / degraded_target_resolution / partial",
    )
