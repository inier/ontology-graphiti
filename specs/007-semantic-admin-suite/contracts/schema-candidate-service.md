# Contract: SchemaCandidateService — 14 状态推进方法签名

**Location**:
- `SchemaCandidateService`: `odap/biz/semantic_admin/candidate_store/services/candidate_service.py`
- `CandidateStateMachine`: `odap/biz/semantic_admin/approval_workflow/impl/candidate_state_machine.py`（纯函数 transition）
- `ApprovalService`: `odap/biz/semantic_admin/approval_workflow/services/approval_service.py`（M10~M14 审批相关动作委托）

**依赖关系**: `HTTP API Routes` → `SchemaCandidateService` → `CandidateDualWriter`（状态推进时刷新 SQLite + 必要时更新 Neo4j 节点标签/状态属性）→ `CandidateStateMachine`（纯函数校验 transition 合法性）→ `QualityGateService`（QUALITY_REVIEW 时 evaluate）→ `ApprovalService`（AUDITOR/ADMIN 动作）。

**核心原则**：所有 `transition()` 调用都是**纯函数 + DB 事务**：先 `next_status = state_machine.transition(current_status, event, context)` 校验 → 再 `storage.update_schema_candidate_status(id, next_status, ...)` → 最后 `dual_writer` 更新 Neo4j。任何校验失败前**不**写 DB。

---

## Section 0: 公共数据类型（复用 candidate-dual-writer.md + 扩展）

```python
from typing import Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

# ============= 复用枚举：CandidateType / OriginLayer / CandidateLifecycleStatus / LifecycleGate =============
# （见 candidate-dual-writer.md Section 0）

# ============= 状态迁移事件（10+ 状态 × 事件矩阵，对齐 data-model.md §3） =============
class CandidateEvent(str, Enum):
    SUBMIT_TO_L1          = "SUBMIT_TO_L1"          # SUBMITTED → L1_REVIEW_PENDING
    L1_ACCEPT             = "L1_ACCEPT"             # L1_REVIEW_PENDING → L1_ACCEPTED
    L1_REJECT             = "L1_REJECT"             # L1_REVIEW_PENDING → DUPLICATE / STOPLISTED
    PROMOTE_TO_L2         = "PROMOTE_TO_L2"         # L1_ACCEPTED → L2_REVIEW_PENDING
    L2_ACCEPT             = "L2_ACCEPT"             # L2_REVIEW_PENDING → L2_ACCEPTED
    L2_REJECT             = "L2_REJECT"             # L2_REVIEW_PENDING → L2_REJECTED
    SEND_TO_QUALITY       = "SEND_TO_QUALITY"       # L2_ACCEPTED → QUALITY_REVIEW（触发 QualityGateService.evaluate）
    QUALITY_PASS          = "QUALITY_PASS"          # QUALITY_REVIEW → AUDITOR_REVIEW
    QUALITY_SENT_TO_L2    = "QUALITY_SENT_TO_L2"    # QUALITY_REVIEW → L2_REVIEW_PENDING（质量严重不合格回退）
    AUDITOR_APPROVE       = "AUDITOR_APPROVE"       # AUDITOR_REVIEW → ADMIN_REVIEW （或 AUTO SKIP → APPROVED）
    AUDITOR_MODIFY        = "AUDITOR_MODIFY"        # AUDITOR_REVIEW →（保持 AUDITOR_REVIEW 但打 MODIFIED 标记；或回退 L2_REVIEW_PENDING）
    AUDITOR_REJECT        = "AUDITOR_REJECT"        # AUDITOR_REVIEW → AUDITOR_REJECTED
    ADMIN_APPROVE         = "ADMIN_APPROVE"         # ADMIN_REVIEW → APPROVED（下一步：writeback）
    ADMIN_REJECT          = "ADMIN_REJECT"          # ADMIN_REVIEW → REJECTED（可选 → STOPLISTED）
    ADMIN_RETURN_TO_AUDITOR = "ADMIN_RETURN_TO_AUDITOR" # ADMIN_REVIEW → AUDITOR_REVIEW（打回一级审核人重做）
    WRITEBACK_OK          = "WRITEBACK_OK"          # APPROVED → MERGED_INTO_USL（HITL 飞轮写回成功）
    WRITEBACK_FAIL        = "WRITEBACK_FAIL"        # APPROVED →（保持 APPROVED，标记 retryable=True）
    MARK_STOPLISTED       = "MARK_STOPLISTED"       # REJECTED / L2_REJECTED → STOPLISTED（加入黑名单）
    MARK_DUPLICATE        = "MARK_DUPLICATE"        # 任何态 → DUPLICATE（与已有候选/术语判定重复）
    REOPEN                = "REOPEN"                # STOPLISTED / REJECTED → SUBMITTED（管理员纠正）

# ============= 状态迁移上下文（传给 state_machine.transition 的 ctx） =============
class TransitionContext(BaseModel):
    operator_id: Optional[str] = None
    operator_role: Optional[str] = None     # "schema_auditor" | "ontology_admin" | "system" | user_role
    comment: Optional[str] = None
    quality_report_id: Optional[str] = None
    reason_code: Optional[str] = None       # 用于 REJECT / STOPLISTED / DUPLICATE 等事件
    context_extra: dict[str, Any] = Field(default_factory=dict)   # 如 {"fast_track_eligible": True, "quality_total_score": 0.91}

# ============= 状态机纯函数 =============
class CandidateStateMachine:
    """纯函数状态机。无 DB I/O，只做 transition 合法性校验 + 返回 next_status。
    测试对齐 data-model.md §3 10 状态 × 事件矩阵全路径。"""

    @staticmethod
    def transition(current_status: CandidateLifecycleStatus,
                   event: CandidateEvent,
                   ctx: TransitionContext | None = None
                   ) -> tuple[CandidateLifecycleStatus, dict[str, Any]]:
        """返回 (new_status, side_effect_hints)。
        Raises:
            InvalidTransitionError: 非法迁移（含角色不满足、comment 为空时 MODIFY/REJECT 强制要 comment 等）
        """
        ...
```

---

## Section 1: SchemaCandidateService 14 方法

```python
class SchemaCandidateService:
    """候选 14 个业务动作方法：submit/promote_to_l1/promote_to_l2/submit_review + L2 回退 + 各审批层级动作。
    每个方法内部先调用 CandidateStateMachine.transition 校验 → 再更新 SQLite（必要时 Neo4j） → 推通知。
    """

    def __init__(self,
                 storage: "SqlitePipelineStorage",
                 state_machine: CandidateStateMachine,
                 dual_writer: "CandidateDualWriter",
                 quality_gate: "QualityGateService",
                 approval_service: "ApprovalService",
                 comment_required_for_modify_or_reject: bool = True):
        ...

    # ============= M1: submit（初始创建候选 → SUBMITTED，通常由 ol_pipeline 调用） =============
    def submit(self, candidate: SchemaCandidate, *, created_by: str) -> SchemaCandidate:
        """M1: 初始提交。等价于 CandidateDualWriter.create_candidate 后将状态置于 SUBMITTED。
        注：大多数情况下 ol_pipeline 直接用 create_candidate，本方法作为业务层 submit 语义（保留 created_by 审计）。
        """

    # ============= M2: promote_to_l1（SUBMITTED → L1_REVIEW_PENDING，送 L1 人工或自动分类） =============
    def promote_to_l1(self, candidate_id: str, *, operator_id: str,
                      auto: bool = False, comment: Optional[str] = None) -> SchemaCandidate:
        """M2: SUBMITTED → L1_REVIEW_PENDING。
        auto=True 时表示"系统自动通过 L1 预检"，operator_id 可为 "system"。
        Raises: InvalidTransitionError, CandidateNotFoundError"""
        ...

    # ============= M3: l1_accept（L1_REVIEW_PENDING → L1_ACCEPTED，一级分类通过） =============
    def l1_accept(self, candidate_id: str, *, operator_id: str,
                  auto: bool = False, comment: Optional[str] = None) -> SchemaCandidate:
        """M3: L1_REVIEW_PENDING → L1_ACCEPTED。"""
        ...

    # ============= M4: l1_reject（L1_REVIEW_PENDING → STOPLISTED / DUPLICATE，L1 不通过） =============
    def l1_reject(self, candidate_id: str, *, operator_id: str,
                  as_duplicate_of: Optional[str] = None,
                  stoplist_reason: Optional[str] = None,
                  comment: str) -> SchemaCandidate:
        """M4: L1_REVIEW_PENDING 不通过。
        - as_duplicate_of 填 winner_id → 最终状态 = DUPLICATE
        - 否则 → STOPLISTED（必填 stoplist_reason）
        若两者都不填 → ValueError 至少一种。comment 必填。
        """
        ...

    # ============= M5: promote_to_l2（L1_ACCEPTED → L2_REVIEW_PENDING，触发 L2 聚类/语义分类） =============
    def promote_to_l2(self, candidate_id: str, *, operator_id: str,
                      auto: bool = False, comment: Optional[str] = None) -> SchemaCandidate:
        """M5: L1_ACCEPTED → L2_REVIEW_PENDING。auto=True 表示"系统自动触发 L2 批处理"。"""
        ...

    # ============= M6: l2_accept（L2_REVIEW_PENDING → L2_ACCEPTED，L2 自动/人工接受） =============
    def l2_accept(self, candidate_id: str, *, operator_id: str,
                  auto: bool = False, comment: Optional[str] = None,
                  parent_ids_for_l2: Optional[list[str]] = None) -> SchemaCandidate:
        """M6: L2_REVIEW_PENDING → L2_ACCEPTED。
        parent_ids_for_l2: 若填，额外调用 CandidateDualWriter.write_neo4j_l2_edges 写 USL__L2_MEMBER_OF。
        """
        ...

    # ============= M7: l2_reject（L2_REVIEW_PENDING → L2_REJECTED，L2 不通过，保留但不再走后续主流程） =============
    def l2_reject(self, candidate_id: str, *, operator_id: str,
                  comment: str) -> SchemaCandidate:
        """M7: L2_REVIEW_PENDING → L2_REJECTED。comment 必填。
        注意 L2_REJECTED 不是终态：管理员仍可 REOPEN。
        """
        ...

    # ============= M8: submit_review（L2_ACCEPTED → QUALITY_REVIEW，触发 QualityGateService.evaluate 批量） =============
    def submit_review(self, candidate_ids: list[str], *, operator_id: str,
                      auto: bool = False,
                      batch_id: Optional[str] = None) -> dict[str, Any]:
        """M8: L2_ACCEPTED → QUALITY_REVIEW。对候选批次调用 QualityGateService.evaluate 批量。
        本方法也可在单个候选上调用（candidate_ids 长度 1）。

        Returns: {"submitted": int, "quality_failed_list": [candidate_id, ...],
                  "reports": {candidate_id: QualityReport 摘要}, "batch_id": str}
        Raises: 单个 candidate 失败不抛整体错（在 failed_list 中列出），除非全部失败。
        """
        ...

    # ============= M9: quality_pass_advance（QUALITY_REVIEW → AUDITOR_REVIEW，质量达标 → 进入人工一级审核） =============
    def quality_pass_advance(self, candidate_id: str, *, operator_id: str = "system",
                             quality_report_id: str,
                             comment: Optional[str] = None) -> SchemaCandidate:
        """M9: QUALITY_REVIEW → AUDITOR_REVIEW。前置：quality_total_score >= 0.50（通过 REVIEW 档下限）。
        operator_id 默认 system（quality_calculator 调完自动推进）。
        """
        ...

    # ============= M10: quality_return_to_l2（QUALITY_REVIEW → L2_REVIEW_PENDING，质量严重不合格打回重做 L2） =============
    def quality_return_to_l2(self, candidate_id: str, *, operator_id: str,
                             quality_report_id: str,
                             comment: str,
                             force: bool = False) -> SchemaCandidate:
        """M10: QUALITY_REVIEW → L2_REVIEW_PENDING。
        默认只有 quality_total_score < 0.30 或某硬门槛为 0（G2-2 环 / G2-6 自环）时才允许；force=True 时管理员可强制任意分。comment 必填。
        """
        ...

    # ============= M11: auditor_approve（AUDITOR_REVIEW → ADMIN_REVIEW 或 APPROVED 加速通道） =============
    def auditor_approve(self, candidate_id: str, *, operator_id: str,
                        comment: Optional[str] = None,
                        submetric_decisions: Optional[dict[str, bool]] = None) -> SchemaCandidate:
        """M11: AUDITOR_REVIEW 审核人通过。
        规则（对齐 contracts/quality-gate-approval.md 加速通道）：
          - 若 quality_total_score >= 0.70 → 自动跳过 ADMIN：状态 = APPROVED（next_approver_role = None）
          - 否则 → ADMIN_REVIEW（next_approver_role = ontology_admin）
        Raises: InvalidTransitionError, ForbiddenError（operator 非 schema_auditor 角色）
        """
        ...

    # ============= M12: auditor_modify（AUDITOR_REVIEW 审核人修改 candidate.payload 后保持/回退） =============
    def auditor_modify(self, candidate_id: str, *, operator_id: str,
                       payload_patch: dict[str, Any],
                       comment: str,
                       return_to_l2: bool = False) -> SchemaCandidate:
        """M12: 审核人修改。
        return_to_l2=False → 仍停在 AUDITOR_REVIEW（current_step_order++，标记 modified_flag）。
        return_to_l2=True  → 回退到 L2_REVIEW_PENDING（修改幅度大需重做聚类）。
        comment 必填。payload_patch 会被合并到 candidate.payload_json。
        """
        ...

    # ============= M13: auditor_reject（AUDITOR_REVIEW → AUDITOR_REJECTED，一级审核人拒） =============
    def auditor_reject(self, candidate_id: str, *, operator_id: str,
                       comment: str,
                       mark_stoplist: bool = False,
                       stoplist_reason: Optional[str] = None) -> SchemaCandidate:
        """M13: AUDITOR_REVIEW → AUDITOR_REJECTED。comment 必填。
        mark_stoplist=True → 再调 M17（见下 MARK_STOPLISTED）将其进一步 → STOPLISTED（一步到位）。
        """
        ...

    # ============= M14: admin_approve（ADMIN_REVIEW → APPROVED，终审通过） =============
    def admin_approve(self, candidate_id: str, *, operator_id: str,
                      comment: str,
                      auto_writeback: bool = True,
                      writeback_svc: Optional["UslWritebackService"] = None) -> SchemaCandidate:
        """M14: ADMIN_REVIEW → APPROVED。comment 必填。
        auto_writeback=True 且 writeback_svc 注入时：同步调用 writeback_svc.write_approved(candidate_id)
            → 成功 → MERGED_INTO_USL；失败 → APPROVED（标记 retryable，后台重试）
        """
        ...

    # --- 注：admin_reject / writeback_ok / mark_stoplisted 等剩余动作由 ApprovalService / UslWritebackService 提供；
    #     SchemaCandidateService 作为"状态主推进 14 法"覆盖 submit 到 admin_approve 主链路 + 质量回退 + auditor 修改。
```

---

## Section 2: 14 方法 × 当前状态 × 目标状态 速查表

| M # | 方法 | 事件 | 起始状态 | → 目标状态 | 操作者角色最低要求 |
|-----|------|------|---------|-----------|------------------|
| M1 | `submit` | — (初始创建) | NEW | SUBMITTED | pipeline system |
| M2 | `promote_to_l1` | SUBMIT_TO_L1 | SUBMITTED | L1_REVIEW_PENDING | schema_auditor / system |
| M3 | `l1_accept` | L1_ACCEPT | L1_REVIEW_PENDING | L1_ACCEPTED | schema_auditor / system |
| M4 | `l1_reject` | L1_REJECT | L1_REVIEW_PENDING | STOPLISTED / DUPLICATE | schema_auditor + |
| M5 | `promote_to_l2` | PROMOTE_TO_L2 | L1_ACCEPTED | L2_REVIEW_PENDING | schema_auditor / system |
| M6 | `l2_accept` | L2_ACCEPT | L2_REVIEW_PENDING | L2_ACCEPTED | schema_auditor / system |
| M7 | `l2_reject` | L2_REJECT | L2_REVIEW_PENDING | L2_REJECTED | schema_auditor |
| M8 | `submit_review` | SEND_TO_QUALITY | L2_ACCEPTED | QUALITY_REVIEW | system / schema_auditor |
| M9 | `quality_pass_advance` | QUALITY_PASS | QUALITY_REVIEW | AUDITOR_REVIEW | system / schema_auditor |
| M10 | `quality_return_to_l2` | QUALITY_SENT_TO_L2 | QUALITY_REVIEW | L2_REVIEW_PENDING | schema_auditor + / admin 强制 |
| M11 | `auditor_approve` | AUDITOR_APPROVE | AUDITOR_REVIEW | ADMIN_REVIEW **或** APPROVED（加速通道） | schema_auditor |
| M12 | `auditor_modify` | AUDITOR_MODIFY (内部事件) | AUDITOR_REVIEW | AUDITOR_REVIEW **或** L2_REVIEW_PENDING | schema_auditor |
| M13 | `auditor_reject` | AUDITOR_REJECT | AUDITOR_REVIEW | AUDITOR_REJECTED | schema_auditor |
| M14 | `admin_approve` | ADMIN_APPROVE | ADMIN_REVIEW | APPROVED（或 MERGED_INTO_USL 写回同步） | ontology_admin |
