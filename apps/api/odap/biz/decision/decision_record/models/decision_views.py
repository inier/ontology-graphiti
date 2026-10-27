"""决策读模型（因果链 / 影响分析 / 门禁结果 / 因果边）

与 `DecisionRecord`（写模型 + 图节点序列化）分文件，避免单文件越过 300 行，
也把"决策对象本体"与"围绕它的聚合视图"分开——后者字段演进节奏不同。
"""

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from odap.biz.decision.decision_record.models.decision_record import DecisionRecord
from odap.biz.decision.decision_record.models.enums import CausalLinkType
from odap.biz.decision.decision_record.models.timestamps import utcnow


class DecisionCausalLink(BaseModel):
    """决策间因果边（ADR-076 §4.5）"""

    from_decision_id: str = Field(description="边起点决策（子决策/被影响方/新决策）")
    to_decision_id: str = Field(description="边终点决策（父决策/影响方/先例）")
    link_type: CausalLinkType = Field(description="因果边类型")
    workspace_id: str = Field(description="工作空间（两端必须同空间）")
    created_at: datetime = Field(default_factory=utcnow)


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
