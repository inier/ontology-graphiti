"""决策一等公民数据模型（ADR-076 §3 + ADR-101 §4.1）

DecisionRecord 是跨 Agent/会话引用的结构化决策记录，
承载"谁、何时、基于什么证据、选择了什么、结果如何"的完整信息。

ADR-101 新增 5 个字段（`outcome` 五态零变更）：
- `status` 6 态流程位置（服务端产生）
- `entry_source` 7 值入口来源
- `recommended_action` 可执行载荷（补齐 execute 的数据缺口）
- `resolution` 裁决留痕（独立字段，不塞 `outcome_details`——后者会被 pipeline 覆写）
- `status_assumed` 存量推定标记（true 不进待决策队列）
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from odap.biz.decision.decision_record.models.enums import (
    CausalLinkType,
    DecisionEntrySource,
    DecisionOutcome,
    DecisionStatus,
)
from odap.biz.decision.decision_record.models.status_matrix import reconcile_on_read
from odap.biz.decision.decision_record.models.timestamps import iso_utc, parse_iso, utcnow


def _load_json(value: Any, default: Any) -> Any:
    """宽松 JSON 解析：已是容器直接返回，字符串解析失败回落默认值。"""
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _coerce_enum(raw: Any, enum_cls: Any, fallback: Any) -> Any:
    try:
        return enum_cls(raw)
    except (ValueError, TypeError):
        return fallback


def _resolution_at_iso(resolution: Optional[Dict[str, Any]]) -> Optional[str]:
    """`resolution.at` 的标量副本。

    `resolution` 在图上存的是 JSON **字符串**，无法用 `n.resolution.at` 做区间
    过滤；而 `to_execute` 档的 SLA 计时与计数都要按裁决时刻取区间，故写时派生
    一个定宽 UTC 标量 `decided_at`（与 `evidence_count` 同一处理方式）。
    """
    if not isinstance(resolution, dict):
        return None
    return iso_utc(parse_iso(resolution.get("at")))


def _parse_state(props: Dict[str, Any]) -> Tuple[DecisionStatus, DecisionEntrySource, bool]:
    """解析流程状态三元组（status / entry_source / status_assumed），缺失即回落。

    读侧默认值刻意与写侧默认值不同：缺失 `entry_source` 说明这条记录早于
    ADR-101，标 `LEGACY`（来源不明），不伪装成 `manual`。
    """
    status = _coerce_enum(
        props.get("status") or DecisionStatus.PENDING.value, DecisionStatus, DecisionStatus.PENDING
    )
    entry_source = _coerce_enum(
        props.get("entry_source") or DecisionEntrySource.LEGACY.value,
        DecisionEntrySource,
        DecisionEntrySource.LEGACY,
    )
    return status, entry_source, bool(props.get("status_assumed") or False)


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

    # 流程（ADR-101）
    status: DecisionStatus = Field(default=DecisionStatus.PENDING, description="流程位置（服务端产生）")
    status_assumed: bool = Field(
        default=False, description="true = status 系存量推定，非真实流程状态（不进队列）"
    )
    entry_source: DecisionEntrySource = Field(
        default=DecisionEntrySource.MANUAL, description="入口来源"
    )
    recommended_action: Optional[Dict[str, Any]] = Field(
        default=None, description="可执行载荷 action_type_id/target_object_id/target_object_type/parameters"
    )
    resolution: Optional[Dict[str, Any]] = Field(
        default=None, description="裁决留痕 action/actor_type/by/at/reason"
    )

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
    created_at: datetime = Field(default_factory=utcnow, description="创建时间（业务时态锚点）")
    updated_at: datetime = Field(default_factory=utcnow, description="更新时间")
    valid_at: datetime = Field(default_factory=utcnow, description="生效时间（业务时态）")
    invalid_at: Optional[datetime] = Field(None, description="失效时间（业务时态）")

    # ---------------- 图节点序列化 ----------------

    def to_node_properties(self) -> Dict[str, Any]:
        """转为图节点扩展属性（复杂结构序列化为 JSON 字符串）。"""
        props: Dict[str, Any] = {}
        props.update(self._input_properties())
        props.update(self._output_properties())
        props.update(self._meta_properties())
        return props

    def _input_properties(self) -> Dict[str, Any]:
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
            # 排序键：evidence_entity_ids 在图上是 JSON 字符串，size() 无效，写时算一次
            "evidence_count": len(self.evidence_entity_ids),
        }

    def _output_properties(self) -> Dict[str, Any]:
        return {
            "recommended_option": self.recommended_option,
            "alternative_options": json.dumps(self.alternative_options, ensure_ascii=False),
            "decision_method": self.decision_method,
            "decision_type": self.decision_type,
            "status": self.status.value,
            "status_assumed": self.status_assumed,
            "entry_source": self.entry_source.value,
            "recommended_action": json.dumps(self.recommended_action, ensure_ascii=False, default=str)
            if self.recommended_action is not None
            else None,
            "resolution": json.dumps(self.resolution, ensure_ascii=False, default=str)
            if self.resolution is not None
            else None,
            "decided_at": _resolution_at_iso(self.resolution),
            "parent_decision_id": self.parent_decision_id,
            "root_goal_id": self.root_goal_id,
            "precedent_decision_ids": json.dumps(self.precedent_decision_ids),
            "action_record_id": self.action_record_id,
            "outcome": self.outcome.value,
            "outcome_details": json.dumps(self.outcome_details, ensure_ascii=False, default=str),
            "feedback_summary": self.feedback_summary,
        }

    def _meta_properties(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "opa_approved": self.opa_approved,
            "opa_decision": json.dumps(self.opa_decision, ensure_ascii=False, default=str)
            if self.opa_decision is not None
            else None,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
            "valid_at": iso_utc(self.valid_at),
            "invalid_at": iso_utc(self.invalid_at),
        }

    # ---------------- 反序列化 ----------------

    @classmethod
    def from_node_properties(cls, props: Dict[str, Any]) -> "DecisionRecord":
        """从图节点属性还原（容忍缺失字段；非法 status/outcome 只告警不抛错）。"""
        status, entry_source, assumed = _parse_state(props)
        outcome = _coerce_enum(
            props.get("outcome") or DecisionOutcome.PENDING.value,
            DecisionOutcome,
            DecisionOutcome.PENDING,
        )
        reconcile_on_read(
            status.value, outcome.value, props.get("decision_id") or props.get("uuid", "")
        )
        return cls(**_record_kwargs(props, status, entry_source, assumed, outcome))


def _record_kwargs(
    props: Dict[str, Any],
    status: DecisionStatus,
    entry_source: DecisionEntrySource,
    assumed: bool,
    outcome: DecisionOutcome,
) -> Dict[str, Any]:
    """把图节点属性映射成构造参数（缺失字段一律回落默认值，不抛错）。"""
    kwargs: Dict[str, Any] = {
        "decision_id": props.get("decision_id") or props.get("uuid", ""),
        "workspace_id": props.get("workspace_id") or props.get("group_id", ""),
        "context_summary": props.get("context_summary") or "",
        "constraints": _load_json(props.get("constraints"), {}),
        "reasoning": props.get("reasoning") or "",
        "reasoning_trace": _load_json(props.get("reasoning_trace"), []),
        "confidence": float(props.get("confidence") or 0.0),
        "evidence_episode_ids": _load_json(props.get("evidence_episode_ids"), []),
        "evidence_entity_ids": _load_json(props.get("evidence_entity_ids"), []),
        "recommended_option": props.get("recommended_option") or "",
        "alternative_options": _load_json(props.get("alternative_options"), []),
        "decision_method": props.get("decision_method") or "recommendation_engine",
        "decision_type": props.get("decision_type") or "general",
        "status": status,
        "status_assumed": assumed,
        "entry_source": entry_source,
        "recommended_action": _load_json(props.get("recommended_action"), None),
        "resolution": _load_json(props.get("resolution"), None),
        "parent_decision_id": props.get("parent_decision_id"),
        "root_goal_id": props.get("root_goal_id"),
        "precedent_decision_ids": _load_json(props.get("precedent_decision_ids"), []),
        "action_record_id": props.get("action_record_id"),
        "outcome": outcome,
        "outcome_details": _load_json(props.get("outcome_details"), {}),
        "feedback_summary": props.get("feedback_summary"),
        "agent_id": props.get("agent_id"),
        "opa_approved": props.get("opa_approved"),
        "opa_decision": _load_json(props.get("opa_decision"), None),
    }
    kwargs.update(_time_kwargs(props))
    return kwargs


def _time_kwargs(props: Dict[str, Any]) -> Dict[str, Any]:
    """时态字段（缺失即取当前时间，保证 `created_at` 永不为空）。"""
    return {
        "created_at": parse_iso(props.get("created_at")) or utcnow(),
        "updated_at": parse_iso(props.get("updated_at")) or utcnow(),
        "valid_at": parse_iso(props.get("valid_at")) or utcnow(),
        "invalid_at": parse_iso(props.get("invalid_at")),
    }

