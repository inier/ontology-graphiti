"""六步管线的输入/输出契约与插槽 Protocol（ARCHITECTURE-v2 §2.1 / §8.2）。

设计原则：
- **插槽化**：每一步是一个 Protocol（`IntentRouter` / `OntologyAligner` / `RuleGuard` /
  `RetrievalExecutor` / `AnswerComposer` / `OutputContractGate`），编排器只依赖 Protocol，
  换实现（LLM、检索后端、策略引擎）不改编排。
- **每步自带 provenance**（`prov`），由管线聚合为 `Provenance`（§2.3）。
- 契约模型用 Pydantic v2：可直接序列化进响应与 `qa_provenance.evidence`。

失败语义：
- 业务拒绝抛 `ApiError`（fail-closed），不返回「部分成功」的假象；
- 降级在结果对象里显式标注（`degraded` / `degraded_engines`），不隐藏。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class Step(str, Enum):
    """六步固定枚举（AC-36：缺步即不合格）。"""

    INTENT = "intent"
    MAP = "map"
    GUARD = "guard"
    RETRIEVE = "retrieve"
    COMPOSE = "compose"
    GATE = "gate"


#: 步骤顺序（管线执行序 + 溯源校验序）
STEP_ORDER: tuple[str, ...] = tuple(s.value for s in Step)


class Evidence(BaseModel):
    """一条可机械校验的证据（AC-37）。"""

    model_config = ConfigDict(extra="ignore")

    kind: str
    ref: str
    decision: Optional[bool] = None
    asof: Optional[str] = None


class StepProv(BaseModel):
    """单步溯源记录（由各实现填写，管线聚合）。"""

    model_config = ConfigDict(extra="ignore")

    component: str
    version: str = "v2.0"
    evidence: List[Evidence] = Field(default_factory=list)


class SubIntent(BaseModel):
    """复合问句里的子意图（槽位归属到各自子意图，不混进主槽位袋）。"""

    model_config = ConfigDict(extra="ignore")

    intent_type: str
    terms: List[str] = Field(default_factory=list)
    text: str = ""
    confidence: float = 0.0


class IntentFrame(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent_type: str
    #: 主意图（与 `intent_type` 同值；单列出来让「主/子意图」语义显式，避免混用槽位）
    primary_intent: str = ""
    sub_intents: List[SubIntent] = Field(default_factory=list)
    slots: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    level: str = "L1"
    clarify_question: Optional[str] = None
    prov: StepProv = Field(default_factory=lambda: StepProv(component="IntentRouter"))


class MappedRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    slot: str
    kind: str
    ref: str


class UnmappedSlot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    slot: str
    raw: str
    suggested_gap_id: Optional[str] = None


class MappedQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: IntentFrame
    object_types: List[MappedRef] = Field(default_factory=list)
    relation_types: List[MappedRef] = Field(default_factory=list)
    metrics: List[MappedRef] = Field(default_factory=list)
    entity_links: List[MappedRef] = Field(default_factory=list)
    unmapped: List[UnmappedSlot] = Field(default_factory=list)
    prov: StepProv = Field(default_factory=lambda: StepProv(component="OntologyAligner"))


class GuardResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    allowed: bool = True
    risk_level: str = "low"
    violations: List[str] = Field(default_factory=list)
    obligations: List[str] = Field(default_factory=list)
    degraded: bool = False
    decision_ref: Optional[str] = None
    prov: StepProv = Field(default_factory=lambda: StepProv(component="RuleGuard"))


class RetrievalResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chains: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Evidence] = Field(default_factory=list)
    degraded_engines: List[str] = Field(default_factory=list)
    evidence_count: int = 0
    prov: StepProv = Field(default_factory=lambda: StepProv(component="RetrievalExecutor"))


class DraftAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str = ""
    citations: List[Evidence] = Field(default_factory=list)
    no_answer: bool = False
    no_answer_reason: str = ""
    #: 结构化载荷（Turtle 文本）。非空时输出契约走 SHACL 分支（AC-31）。
    payload_ttl: Optional[str] = None
    #: 载荷的目标类型（IRI 或本地名），用于定位已登记形状。
    payload_class: Optional[str] = None
    prov: StepProv = Field(default_factory=lambda: StepProv(component="AnswerComposer"))


class GateResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str = ""
    citations: List[Evidence] = Field(default_factory=list)
    contract_ok: bool = True
    blocked_reasons: List[str] = Field(default_factory=list)
    prov: StepProv = Field(default_factory=lambda: StepProv(component="OutputContractGate"))


class QaStatus(str, Enum):
    ANSWERED = "answered"
    CLARIFY = "clarify"
    NO_ANSWER = "no_answer"
    BLOCKED = "blocked"


class SuggestedAction(BaseModel):
    """执行建议（AC-40：必须含 `risk_level`）。

    `risk_level=high` 的动作**必须**经 HITL 确认后才允许执行（AC-41），
    管线只把它们落成 `status=proposed`，绝不自动执行。
    """

    model_config = ConfigDict(extra="ignore")

    action_id: Optional[str] = None
    action_type: str
    risk_level: Literal["low", "high"] = "low"
    requires_hitl: bool = False
    executable: bool = True
    status: str = "proposed"
    summary: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    execution_error_code: Optional[str] = None


class AnswerEnvelope(BaseModel):
    """问答响应信封（openapi-v2 `QaResponse`）。"""

    model_config = ConfigDict(extra="ignore")

    status: QaStatus = QaStatus.ANSWERED
    trace_id: str
    answer: Optional[str] = None
    no_answer: bool = False
    no_answer_reason: Optional[str] = None
    intent: Optional[IntentFrame] = None
    mapped_refs: List[MappedRef] = Field(default_factory=list)
    unmapped: List[UnmappedSlot] = Field(default_factory=list)
    clarify_question: Optional[str] = None
    citations: List[Evidence] = Field(default_factory=list)
    suggested_actions: List[SuggestedAction] = Field(default_factory=list)
    contract_ok: bool = True
    blocked_reasons: List[str] = Field(default_factory=list)
    degraded: bool = False
    degraded_engines: List[str] = Field(default_factory=list)


# ── 插槽 Protocol（六步均可替换）────────────────────────────────────────────


@runtime_checkable
class IntentRouter(Protocol):
    name: str
    version: str

    async def route(self, query: str, user_ctx: Dict[str, Any],
                    workspace_id: str) -> IntentFrame: ...


@runtime_checkable
class OntologyAligner(Protocol):
    name: str
    version: str

    async def align(self, intent: IntentFrame, workspace_id: str) -> MappedQuery: ...


@runtime_checkable
class RuleGuard(Protocol):
    name: str
    version: str

    async def check(self, mapped: MappedQuery, user_ctx: Dict[str, Any],
                    workspace_id: str) -> GuardResult: ...


@runtime_checkable
class RetrievalExecutor(Protocol):
    name: str
    version: str

    async def execute(self, mapped: MappedQuery, query: str,
                      workspace_id: str, mode: str = "auto") -> RetrievalResult: ...


@runtime_checkable
class AnswerComposer(Protocol):
    name: str
    version: str

    async def compose(self, retrieval: RetrievalResult, query: str) -> DraftAnswer: ...


@runtime_checkable
class OutputContractGate(Protocol):
    name: str
    version: str

    async def validate(self, draft: DraftAnswer, mapped: MappedQuery) -> GateResult: ...


__all__ = [
    "Step", "STEP_ORDER", "Evidence", "StepProv", "IntentFrame", "SubIntent", "MappedRef",
    "UnmappedSlot", "MappedQuery", "GuardResult", "RetrievalResult", "DraftAnswer",
    "GateResult", "QaStatus", "SuggestedAction", "AnswerEnvelope",
    "IntentRouter", "OntologyAligner", "RuleGuard", "RetrievalExecutor",
    "AnswerComposer", "OutputContractGate",
]
