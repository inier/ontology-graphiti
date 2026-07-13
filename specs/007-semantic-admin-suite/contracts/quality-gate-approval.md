# Contract: QualityGateService + ApprovalWorkflowService + OPA 16 Rego 规则

**Location**:
- `QualityGateService`: `odap/biz/core/ontology/semantic/services/quality_gate_service.py`
- `ApprovalWorkflowService`: `odap/biz/core/ontology/semantic/services/approval_workflow_service.py`
- `Quality Gate Rego Policies`: `odap/biz/core/ontology/semantic/services/policies/quality_gate.rego`

**依赖关系**: `QualityGateService` 依赖 `UslManagerService` + `UslQueryEngine` + `SqliteUslStorage`（quality_reports 读写）；`ApprovalWorkflowService` 依赖 `QualityGateService` + `UslManagerService`（promote to USL）+ `OntologyWritebackService`（可选写回）。

---

## Section 1: 公共数据类型

```python
from typing import Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

# ============= 枚举 =============
class OverallVerdict(str, Enum):
    PASS = "PASS"           # total_score >= 0.80
    REVIEW = "REVIEW"       # 0.50 <= total_score < 0.80
    FAIL = "FAIL"           # total_score < 0.50

class SubmetricThreshold:
    """16 子指标各自阈值（低于则 deny 触发）。可配置。"""
    G1_FIELD_TYPE_MATCH       = 0.70  # Gate1-1
    G1_REQUIRED_PRESENT       = 0.80  # Gate1-2
    G1_NO_UNDEFINED           = 0.90  # Gate1-3
    G1_RANGE_OK               = 0.75  # Gate1-4
    G2_SYNONYM_AMBIGUITY      = 0.80  # Gate2-1
    G2_HIERARCHY_CYCLE_FREE   = 1.00  # Gate2-2 硬门槛: 有环=0
    G2_TRANSITIVE_OK          = 0.70  # Gate2-3
    G2_DISJOINT_PAIR_OK       = 0.95  # Gate2-4
    G2_CARDINALITY_OK         = 0.85  # Gate2-5
    G2_ISA_ACYCLIC            = 1.00  # Gate2-6 硬门槛: 自环=0
    G3_DOMAIN_COVERAGE        = 0.60  # Gate3-1
    G3_NAMING_CONVENTION      = 0.75  # Gate3-2
    G3_TRACABILITY            = 0.65  # Gate3-3
    G3_CONF_DISTRIBUTION      = 0.70  # Gate3-4
    G3_REDUNDANCY_LOW         = 0.55  # Gate3-5（越低越好 → 反转分数）
    G3_FUTURE_EXPANDABLE      = 0.60  # Gate3-6

# ============= 子指标 =============
class SubmetricDetail(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    rule_name: str                    # 对应 Rego deny 规则名，如 "g1_no_undefined_fields"
    reason: str                       # 中文解释，如 "发现 2 个未在 PropertySpec 定义的字段"
    actual_value: Any = None          # 如 2/3 字段匹配 -> actual = 0.667

class Quality16Submetrics(BaseModel):
    # Gate1: Schema 一致性 4 个
    g1_field_type_match: SubmetricDetail
    g1_required_field_present: SubmetricDetail
    g1_no_undefined_fields: SubmetricDetail
    g1_range_constraint_ok: SubmetricDetail
    # Gate2: 语义一致性 6 个
    g2_synonym_ambiguity: SubmetricDetail
    g2_hierarchy_cycle_free: SubmetricDetail
    g2_hierarchy_transitive_ok: SubmetricDetail
    g2_disjoint_pair_ok: SubmetricDetail
    g2_cardinality_ok: SubmetricDetail
    g2_isa_acyclic: SubmetricDetail
    # Gate3: 业务一致性 6 个
    g3_domain_coverage: SubmetricDetail
    g3_business_naming_convention: SubmetricDetail
    g3_tracability: SubmetricDetail
    g3_confidence_distribution: SubmetricDetail
    g3_redundancy_rate: SubmetricDetail
    g3_future_expandable: SubmetricDetail

    def gate1_avg(self) -> float:
        return (self.g1_field_type_match.score + self.g1_required_field_present.score
                + self.g1_no_undefined_fields.score + self.g1_range_constraint_ok.score) / 4.0

    def gate2_avg(self) -> float:
        items = [self.g2_synonym_ambiguity, self.g2_hierarchy_cycle_free,
                 self.g2_hierarchy_transitive_ok, self.g2_disjoint_pair_ok,
                 self.g2_cardinality_ok, self.g2_isa_acyclic]
        return sum(x.score for x in items) / len(items)

    def gate3_avg(self) -> float:
        items = [self.g3_domain_coverage, self.g3_business_naming_convention,
                 self.g3_tracability, self.g3_confidence_distribution,
                 self.g3_redundancy_rate, self.g3_future_expandable]
        return sum(x.score for x in items) / len(items)

# ============= QualityReport =============
class QualityReport(BaseModel):
    report_id: str
    candidate_id: str
    run_id: Optional[str] = None
    generated_at: datetime
    gate1_score: float = Field(ge=0.0, le=1.0)     # = submetrics.gate1_avg()
    gate2_score: float = Field(ge=0.0, le=1.0)     # = submetrics.gate2_avg()
    gate3_score: float = Field(ge=0.0, le=1.0)     # = submetrics.gate3_avg()
    total_score: float = Field(ge=0.0, le=1.0)     # = 0.3*g1 + 0.4*g2 + 0.3*g3
    submetrics: Quality16Submetrics
    overall: OverallVerdict
    recommend_auto_skip: bool                      # total>=0.9 且审批流会跳过 admin

    @classmethod
    def compute_total(cls, g1: float, g2: float, g3: float) -> float:
        return round(0.3 * g1 + 0.4 * g2 + 0.3 * g3, 4)

    @classmethod
    def overall_from_score(cls, total: float) -> OverallVerdict:
        if total >= 0.80: return OverallVerdict.PASS
        if total >= 0.50: return OverallVerdict.REVIEW
        return OverallVerdict.FAIL
```

---

## Section 2: QualityGateService 接口

```python
class QualityGateService:
    """三质量门评估。evaluate() 返回 16 子指标+总分。
    内部先调用 Python 计算 → 再调用 OPA Rego 规则对照（见 parity 测试 I3T15）。
    最终以 Python 结果 + OPA deny 列表合并为 report。
    """

    def __init__(self, usl_manager: "UslManagerService", storage: "SqliteUslStorage",
                 opa_policy_path: str | None = None, cache_ttl_sec: int = 3600): ...

    # ============ 主入口 ============
    def evaluate(self, candidate_id: str, force: bool = False) -> QualityReport:
        """评估 candidate → 生成 QualityReport。

        流程：
          1. 从 storage 读取 candidate；未找到 → CandidateNotFoundError
          2. cache_hit 且 force=False → 直接返回缓存 report（按 candidate_id 键）
          3. Gate1 评估 → 4 SubmetricDetail
          4. Gate2 评估 → 6 SubmetricDetail
          5. Gate3 评估 → 6 SubmetricDetail
          6. 计算 gate1_score/gate2_score/gate3_score/total_score/overall
          7. OPA eval 对照：deny 列表聚合到子指标 reason（分数低于阈值）
          8. 写 storage.quality_reports；返回 QualityReport

        Args:
            candidate_id: ol_candidates 主键
            force: True → 跳过缓存重新计算

        Returns:
            QualityReport（含 16 子指标 + 4 总分 + overall）

        Raises:
            CandidateNotFoundError: candidate_id 不存在
            RuntimeError: OPA eval 超时或 16 deny 全部 fail → 告警但仍返回 report
        """

    # ============ Gate1 (4) 子方法（public 便于单测） ============
    def eval_g1_field_type_match(self, cand: "Candidate") -> SubmetricDetail:
        """G1-1: 字段类型匹配率。
        取 candidate.attribute_dict 每个属性 → 对照 PropertySpec.data_type；
        match_count / total_count → score。"""

    def eval_g1_required_present(self, cand: "Candidate") -> SubmetricDetail:
        """G1-2: 必填字段填充率。
        对 target_term_id (或 domain 全局) PropertySpec.required=True 的项 → 统计已填 / 总数。"""

    def eval_g1_no_undefined(self, cand: "Candidate") -> SubmetricDetail:
        """G1-3: 无未定义字段。
        candidate 实际字段 - PropertySpec 允许集 = undefined_set；
        score = max(0, 1.0 - len(undefined_set)/max(1, len(fields)))。"""

    def eval_g1_range_ok(self, cand: "Candidate") -> SubmetricDetail:
        """G1-4: 数值/枚举范围内。
        对 INTEGER/FLOAT 检查 min/max_val；对 ENUM 检查 enum_values 包含；
        命中数 / 受检查字段数 → score。"""

    # ============ Gate2 (6) 子方法 ============
    def eval_g2_synonym_ambiguity(self, cand: "Candidate") -> SubmetricDetail:
        """G2-1: 同义词歧义度。
        每个 synonym → 查询其他 domain 是否相同 synonym；歧义=跨 domain 冲突次数；
        score = max(0, 1.0 - conflict_count/max(1, len(synonyms)))。"""

    def eval_g2_hierarchy_cycle_free(self, cand: "Candidate") -> SubmetricDetail:
        """G2-2: 层级无环（硬门槛）。
        对 candidate.hint_parents 调用 storage.detect_hierarchy_cycle → 有环 score=0.0，无环=1.0。"""

    def eval_g2_transitive_ok(self, cand: "Candidate") -> SubmetricDetail:
        """G2-3: 传递闭包一致性。
        若 parent(A,B) 且 parent(B,C) 但 system 中无 implicit A→C → 标失配；
        score = transitive_hits / total_transitive_pairs。"""

    def eval_g2_disjoint_pair_ok(self, cand: "Candidate") -> SubmetricDetail:
        """G2-4: 不相交对一致。
        若 (X,Y) ∈ disjoint_pairs(strict=True) 而 candidate 同时 hint_parents 含 X,Y → 违规；
        score = max(0, 1.0 - violations/max(1, checked_pairs))。"""

    def eval_g2_cardinality_ok(self, cand: "Candidate") -> SubmetricDetail:
        """G2-5: 基数约束满足。
        读取 cand → 实例化关系数 vs cardinality_rules.min/max；
        score = ok_count / rule_count（0 规则 = 1.0 默认值）。"""

    def eval_g2_isa_acyclic(self, cand: "Candidate") -> SubmetricDetail:
        """G2-6: is-a 无自环（硬门槛）。
        candidate 自身 canonical ∈ synonyms 集合 → 自环=0.0；否则=1.0。"""

    # ============ Gate3 (6) 子方法 ============
    def eval_g3_domain_coverage(self, cand: "Candidate") -> SubmetricDetail:
        """G3-1: 领域覆盖度。
        canonical + top-5 synonyms → 与 domain.en_mapping keys ∪ usl_terms canonical 集合 Jaccard 相似度；
        score = jaccard。"""

    def eval_g3_naming_convention(self, cand: "Candidate") -> SubmetricDetail:
        """G3-2: 命名规范度。
        正则（长度 2-32 汉字/英文，允许下划线；不以数字开头）+ en 中英映射存在性（en in domain.en_mapping）；
        命中项 / 3 → score。"""

    def eval_g3_tracability(self, cand: "Candidate") -> SubmetricDetail:
        """G3-3: 可追溯性。
        source_step 非空 + run_id 非空 + candidate.audit_log >=1；计数 / 3 → score。"""

    def eval_g3_conf_distribution(self, cand: "Candidate") -> SubmetricDetail:
        """G3-4: 置信度分布稳定性。
        取 run.run_id → 该 run 所有 candidate.confidence → 计算 σ；σ ≤ 0.15 → 高分；σ>0.4→低分；
        score = max(0, 1.0 - (σ - 0.15)/0.25)  clamped。"""

    def eval_g3_redundancy_rate(self, cand: "Candidate") -> SubmetricDetail:
        """G3-5: 与已有 USL 重复率（越低越好 → 反转）。
        canonical + synonym 与现有 usl_terms 做 Levenshtein；最相似相似度 s；
        score = max(0, 1.0 - s)（反转：完全相同=0，全新=1）。"""

    def eval_g3_future_expandable(self, cand: "Candidate") -> SubmetricDetail:
        """G3-6: 未来可扩展槽。
        hint_parents 的末端叶子（无 child）计数；层级树的平均深度；命名空间前缀一致性；
        子项得分平均 → score。"""

    # ============ OPA 联动 ============
    def _opa_evaluate(self, input_dict: dict[str, Any]) -> list[str]:
        """调用 OPA `opa eval -d policies/quality_gate.rego`。
        返回所有 deny[msg] 的 msg 列表。供 reason 聚合。"""
```

---

## Section 3: ApprovalWorkflowService 5 方法

```python
from typing import Optional
from datetime import datetime, timedelta, timezone

class ApprovalTaskStatus(str, Enum):
    PENDING             = "pending"
    AUDITED             = "audited"
    MODIFIED            = "modified"
    REJECTED            = "rejected"
    FINAL_APPROVED      = "final_approved"
    AUTO_SKIPPED_ADMIN  = "auto_skipped_admin"
    CANCELLED           = "cancelled"

class AuditComment(BaseModel):
    comment_id: str
    user_id: str
    action: str          # "audit"/"modify"/"reject"/"final_approve"/"system"
    comment: str
    at: datetime

class ApprovalTask(BaseModel):
    id: str
    candidate_id: str
    report_id: Optional[str] = None
    assigned_role: SemanticRoleEnum
    assignee_user_id: Optional[str] = None
    status: ApprovalTaskStatus
    reviewer_comment: Optional[str] = None
    comments: list[AuditComment] = []
    created_at: datetime
    resolved_at: Optional[datetime] = None
    sla_deadline: datetime                 # created_at + 48h（可配置 approval.sla_hours）
    auto_triggered: bool = False           # True 表示来自 auto_skip_admin

class SubmetricDecision(BaseModel):
    submetric_name: str                    # 如 "g2_hierarchy_cycle_free"
    accepted: bool
    note: Optional[str] = None

class ApprovalWorkflowService:
    """审批工作流：5 个动作方法 = audit / modify / reject / final_approve / auto_skip_admin。
    每次动作都写 comments 历史 + 推送通知。
    """

    def __init__(self, storage: "SqliteUslStorage", quality_gate: QualityGateService,
                 usl_manager: "UslManagerService", writeback_svc: Optional["OntologyWritebackService"] = None,
                 sla_hours: int = 48, auto_skip_threshold: float = 0.90): ...

    # ================= M1: audit =================
    def audit(self, task_id: str, auditor_id: str, comment: str,
              decisions: Optional[list[SubmetricDecision]] = None) -> ApprovalTask:
        """M1: 审核动作（reviewer 或 term_editor 初审）。
        语义：审阅者对 16 指标逐条或整体给出接受/驳回。

        步骤：
          1. 取 task；task.status ∉ {PENDING, MODIFIED} → CandidateNotEditableError
          2. role check：assigned_role ∈ user.roles（SemanticRoleEnum REVIEWER 或更高）→ 否则 403
          3. 追加 comment 到 comments；追加 decisions 到 meta（存 JSON）
          4. status = AUDITED；assignee_user_id = auditor_id；resolved_at 暂不填（待 final_approve）
          5. 保存 storage；推送通知

        Args:
            task_id:       approval_tasks.id
            auditor_id:    执行审核的 user_id
            comment:       审核说明（≥3 字）
            decisions:     可选：16 子指标逐条决策

        Returns: 更新后 ApprovalTask

        Raises:
            CandidateNotFoundError(task 对应 candidate 已被删)
            CandidateNotEditableError(status 非法)
            ValueError(comment <3 字)
        """

    # ================= M2: modify =================
    def modify(self, task_id: str, editor_id: str,
               candidate_patch: dict[str, Any], editor_comment: str) -> ApprovalTask:
        """M2: 修改 candidate → 重新触发 evaluate。
        用于 term_editor 纠正 canonical/synonyms/parents/confidence 后再评估。

        步骤：
          1. 取 task；status ∉ {PENDING, AUDITED, MODIFIED} → 409
          2. role check: TERM_EDITOR 或更高
          3. 调 `storage.update_candidate(candidate_id, candidate_patch)` → 返回 updated
          4. 调 `quality_gate.evaluate(candidate_id, force=True)` → 新 report，写 report_id
          5. status = MODIFIED；追加 comment；resolved_at=None
          6. 推送通知（通知 reviewer 重新审阅）

        Args:
            task_id:           approval_tasks.id
            editor_id:         编辑 user_id
            candidate_patch:   {canonical_term?, synonyms?, hint_parents?, confidence?}
            editor_comment:    修改说明（≥3 字）

        Returns: ApprovalTask（含最新 report 摘要）

        Raises: 同 audit + PATCH 失败原因（status不可改）
        """

    # ================= M3: reject =================
    def reject(self, task_id: str, reviewer_id: str, reason: str,
               close_task: bool = True, auto_reject_threshold: float = 0.30) -> ApprovalTask:
        """M3: 驳回。
        当质量门总分较低（<0.3）或 reviewer 认为不可用时，直接 reject candidate。

        步骤：
          1. 取 task；task.status=REJECTED/FINAL_APPROVED/AUTO → 409 ALREADY_RESOLVED
          2. role check: REVIEWER 或更高
          3. storage.update_candidate(cand_id, rejected=True, rejection_reason=reason)
          4. task.status = REJECTED；resolved_at=utcnow；追加 reason 到 comments
          5. 可选 close_task=True → task.active=False
          6. 可选：total_score<auto_reject_threshold → 系统自动再标 "AUTO_REJECT" system comment

        Args:
            task_id:              approval_tasks.id
            reviewer_id:          reviewer/super_admin id
            reason:               驳回原因（≥5 字）
            close_task:           True → 标记关闭不再接受后续动作
            auto_reject_threshold: 默认 0.3 → 低于该分数加 system comment

        Returns: 更新后 ApprovalTask

        Raises: ValueError(reason<5 字) / 409 / 403
        """

    # ================= M4: final_approve =================
    def final_approve(self, task_id: str, super_admin_id: str, comment: str,
                      auto_promote: bool = True, writeback_now: bool = True,
                      promote_overwrite: bool = False) -> ApprovalTask:
        """M4: 终审通过 → promote + writeback。**仅允许 super_admin**。

        步骤：
          1. role check: MUST be SemanticRoleEnum.SUPER_ADMIN → 否则 403 `SUPER_ADMIN_ONLY`
          2. 取 task；若已 REJECTED → 409；若 FINAL_APPROVED → 幂等返回
          3. 若 report 不存在或陈旧（< latest）→ 自动调 quality_gate.evaluate(force=False)
          4. task.status = FINAL_APPROVED；resolved_at=utcnow；assignee=super_admin
          5. candidate.status = FINAL_APPROVED
          6. auto_promote=True → 调 `usl_manager.create_term(...)`（等价 B7 promote-to-usl），处理冲突：
             - 同 canonical 存在且 promote_overwrite=False → PromoteConflictError
             - 否则创建或覆盖
          7. writeback_now=True 且 writeback_svc 非 None → 调 writeback_svc.writeback_candidate(cand_id)
          8. 推送通知（对发起 pipeline 的 user）

        Args:
            task_id:            task
            super_admin_id:     user（必须 SUPER_ADMIN，内部二次断言）
            comment:            终审意见（≥5 字）
            auto_promote:       True → 升为正式 USL Term
            writeback_now:      True → 立即写回 Graphiti/Neo4j
            promote_overwrite:  对 USL 已有 term 是否覆盖

        Returns: ApprovalTask + 嵌套 {promoted_term_id, writeback_status}

        Raises: 403(非 super_admin) / 409(REJECTED) / PromoteConflictError(冲突) / ValueError
        """

    # ================= M5: auto_skip_admin =================
    def auto_skip_admin(self, candidate_id: str,
                        trigger: str = "AUTO_THRESHOLD") -> ApprovalTask:
        """M5: 自动跳过 Admin 审批（质量极高时触发）。

        触发条件（ALL true）：
          a. quality_gate.evaluate(cand_id).total_score ≥ auto_skip_threshold（默认 0.90）
          b. 该 candidate.assigned_role 的下一任本为 super_admin
          c. 当前未存在 REJECTED 任务
          d. candidate 来源步骤 ∈ {l1,l2,l3,l4,l5}（非人工导入）

        执行：
          1. 先 evaluate → 不满足 a → raise ValueError(f"AUTO_SKIP_NOT_QUALIFIED: score={s}")
          2. 创建 ApprovalTask（auto_triggered=True；status=AUTO_SKIPPED_ADMIN；assignee=SYSTEM）
          3. candidate.status = AUTO_SKIPPED_ADMIN
          4. 执行 promote-to-usl（等价 final_approve auto_promote=True + promote_overwrite=False）
          5. 若 writeback_svc: writeback_now=True
          6. 追加 system comment: "AUTO_SKIP_ADMIN trigger={trigger}; total_score={s} ≥ {threshold}"

        Args:
            candidate_id: candidate_id
            trigger: 触发来源（日志用），如 "AUTO_THRESHOLD" / "HUMAN_TRIGGER"

        Returns: 新建 ApprovalTask（status=AUTO_SKIPPED_ADMIN）

        Raises:
            CandidateNotFoundError
            ValueError("AUTO_SKIP_NOT_QUALIFIED") 附带分数详情
            PromoteConflictError（与 final_approve 一样）
        """
```

---

## Section 4: OPA Rego 16 条规则（`quality_gate.rego` 原文）

文件路径：`odap/biz/core/ontology/semantic/services/policies/quality_gate.rego`

**Rego Package & Input Schema**：

```rego
package quality_gate

# ============================================================
# Input Schema（Python QualityGateService 传入）:
# {
#   "candidate": {
#     "id": str, "domain_id": str, "canonical_term": str,
#     "synonyms": [str], "hint_parents": [str], "confidence": float,
#     "source_step": str, "run_id": str, "attributes": {k: v},
#     "rejected": bool, "created_at": str
#   },
#   "context": {
#     "usl_terms": [{"id","canonical","synonyms","en"}],
#     "property_specs": [{"prop_name","data_type","required","default_value","enum_values","min_val","max_val"}],
#     "hierarchy_edges": [{"parent","child","edge_type"}],
#     "disjoint_pairs": [{"term_a_id","term_b_id","strict"}],
#     "cardinality_rules": [{"source_term_id","relation","target_term_id","min_card","max_card"}],
#     "domain_en_mapping": {zh: en},
#     "sibling_confidences": [float]   # run 内其他 candidate.confidence
#   },
#   "thresholds": {
#     "g1_field_type_match": 0.7, ... 等 16 阈值
#   }
# }
# ============================================================

import future.keywords.if
import future.keywords.in

# ---------- 辅助 ----------
cand := input.candidate
ctx  := input.context
th   := input.thresholds

len_arr(xs) := count(xs) if xs is array else 0

# ---------- GATE 1: Schema 一致性 ----------

deny["G1-1 g1_field_type_match score 低于阈值; 类型不匹配字段已标记"] if {
    count([1 | spec := ctx.property_specs[_]; attr := cand.attributes[spec.prop_name]; not _type_ok(spec, attr)]) > 0
    _sub_score_g1_1 < th.g1_field_type_match
}
_sub_score_g1_1 := _ok / _total if {
    _total := max([count(ctx.property_specs), 1])
    _ok    := count([1 | spec := ctx.property_specs[_]; attr := cand.attributes[spec.prop_name]; _type_ok(spec, attr)])
} else := 1.0 if {
    count(ctx.property_specs) == 0
}
_type_ok(spec, attr) := true if { spec.data_type == "STRING";  is_string(attr) }
_type_ok(spec, attr) := true if { spec.data_type == "INTEGER"; is_number(attr); floor(attr) == attr }
_type_ok(spec, attr) := true if { spec.data_type == "FLOAT";   is_number(attr) }
_type_ok(spec, attr) := true if { spec.data_type == "BOOLEAN"; (attr == true; attr == false) }
_type_ok(spec, attr) := true if { spec.data_type == "ENUM";    enum_val_contains(spec, attr) }
_type_ok(spec, attr) := true if { spec.data_type == "DATETIME"; regex.match(`^\\d{4}-\\d{2}-\\d{2}T`, sprintf("%v", [attr])) }
_type_ok(spec, attr) := true if { spec.data_type == "JSON"; (is_object(attr); is_array(attr); is_string(attr)) }
_type_ok(_, _) := false
enum_val_contains(spec, attr) := true if { vals := spec.enum_values; some v in vals; sprintf("%v", [v]) == sprintf("%v", [attr]) }

deny["G1-2 g1_required_field_present score 低于阈值; 必填字段缺失"] if {
    _sub_score_g1_2 < th.g1_required_present
}
_sub_score_g1_2 := _ok / _total if {
    _required := [s | s := ctx.property_specs[_]; s.required == true]
    _total    := max([count(_required), 1])
    _ok       := count([s | s := _required[_]; cand.attributes[s.prop_name] != null; cand.attributes[s.prop_name] != ""])
} else := 1.0 if {
    count([s | s := ctx.property_specs[_]; s.required == true]) == 0
}

deny["G1-3 g1_no_undefined_fields score 低于阈值; 发现未定义字段"] if {
    _sub_score_g1_3 < th.g1_no_undefined
}
_sub_score_g1_3 := 1.0 - (_bad / _max) if {
    _def  := {name | name := ctx.property_specs[_].prop_name}
    _real := {name | some name, _ in cand.attributes}
    _bad  := count(_real - _def)
    _max  := max([count(_real), 1])
} else := 1.0

deny["G1-4 g1_range_constraint_ok score 低于阈值; 数值/枚举范围违规"] if {
    _sub_score_g1_4 < th.g1_range_ok
}
_sub_score_g1_4 := _ok / _total if {
    _range_bounded := [s | s := ctx.property_specs[_]; (s.min_val != null; s.max_val != null; s.enum_values != null)]
    _total         := max([count(_range_bounded), 1])
    _ok            := count([1 | s := _range_bounded[_]; _bound_ok(s, cand.attributes[s.prop_name])])
} else := 1.0
_bound_ok(s, val) := true if {
    is_number(val); is_number(s.min_val); val >= s.min_val; is_number(s.max_val); val <= s.max_val
}
_bound_ok(s, val) := true if {
    vals := s.enum_values; some v in vals; sprintf("%v", [v]) == sprintf("%v", [val])
}
_bound_ok(_, null) := true
_bound_ok(_, _) := false

# ---------- GATE 2: 语义一致性 ----------

deny["G2-1 g2_synonym_ambiguity 低于阈值; 同义词跨 domain 冲突"] if { _sub_score_g2_1 < th.g2_synonym_ambiguity }
_sub_score_g2_1 := 1.0 - (_conflict / _max) if {
    _all_syns := {s | s := ctx.usl_terms[_].synonyms[_]; ctx.usl_terms[_].domain_id != cand.domain_id}
    _me       := {cand.canonical_term} | {s | s := cand.synonyms[_]}
    _conflict := count(_all_syns & _me)
    _max      := max([count(_me), 1])
} else := 1.0

deny["G2-2 g2_hierarchy_cycle_free = 0; 检测到层级环"] if { _sub_score_g2_2 < 1.0 }
_sub_score_g2_2 := 0.0 if { _detect_cycle(cand.hint_parents, cand.id) } else := 1.0
_detect_cycle(parents, self_id) := true if {
    some p in parents; edges := ctx.hierarchy_edges
    # 若 p 的 child 路径能回到 self_id（简化：任何含自环的迹象）
    some e in edges; e.parent == p; _reachable(e.child, self_id)
} else := false
_detect_cycle(parents, self_id) := true if { some p in parents; p == self_id }
_reachable(src, dst) := true if { some e in ctx.hierarchy_edges; e.parent == src; e.child == dst }
_reachable(src, dst) := true if { some e in ctx.hierarchy_edges; e.parent == src; _reachable(e.child, dst) }

deny["G2-3 g2_hierarchy_transitive_ok 低于阈值; 传递闭包失配"] if { _sub_score_g2_3 < th.g2_hierarchy_transitive_ok }
_sub_score_g2_3 := _ok / max([_pairs, 1]) if {
    # (A,B),(B,C) 隐含 (A,C)
    _pairs := count([1 | ab := ctx.hierarchy_edges[_]; bc := ctx.hierarchy_edges[_]; ab.child == bc.parent])
    _ok    := count([1 | ab := ctx.hierarchy_edges[_]; bc := ctx.hierarchy_edges[_]; ab.child == bc.parent;
                     some ac in ctx.hierarchy_edges; ac.parent == ab.parent; ac.child == bc.child])
} else := 1.0 if { _pairs == 0 }

deny["G2-4 g2_disjoint_pair_ok 低于阈值; 不相交对违规"] if { _sub_score_g2_4 < th.g2_disjoint_pair_ok }
_sub_score_g2_4 := 1.0 - (_vio / max([_checked, 1])) if {
    _checked := count(ctx.disjoint_pairs)
    _vio     := count([1 | dp := ctx.disjoint_pairs[_]; dp.strict == true; _strict_violated(dp)])
} else := 1.0
_strict_violated(dp) := true if {
    p_a := dp.term_a_id; p_b := dp.term_b_id
    # candidate 的 hint_parents 或 canonical 同时属于 A 与 B 的子树 → 违规
    (p_a == cand.id; p_b == cand.id)
}
_strict_violated(dp) := true if {
    some p in cand.hint_parents; dp.term_a_id == p
    some q in cand.hint_parents; dp.term_b_id == q
}

deny["G2-5 g2_cardinality_ok 低于阈值; 基数约束违规"] if { _sub_score_g2_5 < th.g2_cardinality_ok }
_sub_score_g2_5 := _ok / max([_rules, 1]) if {
    _rules := count(ctx.cardinality_rules)
    _ok    := count([1 | r := ctx.cardinality_rules[_]; _card_ok(r)])
} else := 1.0
_card_ok(r) := true if {
    n := count([e | e := ctx.hierarchy_edges[_]; e.parent == r.source_term_id; r.target_term_id == null; e.edge_type == r.relation_name])
    n >= r.min_card; (r.max_card == null; n <= r.max_card)
}

deny["G2-6 g2_isa_acyclic = 0; 检测到 is-a 自环"] if { _sub_score_g2_6 < 1.0 }
_sub_score_g2_6 := 0.0 if { some s in cand.synonyms; s == cand.canonical_term } else := 1.0

# ---------- GATE 3: 业务一致性 ----------

deny["G3-1 g3_domain_coverage 低于阈值; 与当前领域词汇重合度低"] if { _sub_score_g3_1 < th.g3_domain_coverage }
_sub_score_g3_1 := _inter / _union if {
    _dom := {t.canonical | t := ctx.usl_terms[_]; t.domain_id == cand.domain_id} | set(object.keys(ctx.domain_en_mapping))
    _me  := {cand.canonical_term} | {s | s := cand.synonyms[_]} | {s | s := cand.synonyms[_]}
    _inter := count(_dom & _me)
    _union := max([count(_dom | _me), 1])
} else := 0.0

deny["G3-2 g3_business_naming_convention 低于阈值; 命名不规范"] if { _sub_score_g3_2 < th.g3_naming_convention }
_sub_score_g3_2 := (_ok_len + _ok_prefix + _ok_en) / 3.0
_ok_len := 1 if { regex.match(`^[A-Za-z\\u4e00-\\u9fa5][A-Za-z0-9_\\u4e00-\\u9fa5]{1,31}$`, cand.canonical_term) } else := 0
_ok_prefix := 1 if { not regex.match(`^\\d`, cand.canonical_term) } else := 0
_ok_en    := 1 if { some _, v in ctx.domain_en_mapping; v == cand.canonical_term; true } else := 0
_ok_en    := 1 if { ct := cand.canonical_term; some en in object.values(ctx.domain_en_mapping); lower(en) == lower(ct) } else := _ok_en

deny["G3-3 g3_tracability 低于阈值; 溯源字段缺失"] if { _sub_score_g3_3 < th.g3_tracability }
_sub_score_g3_3 := (_src + _run + _audit) / 3.0
_src   := 1 if { cand.source_step != ""; cand.source_step != null } else := 0
_run   := 1 if { cand.run_id     != ""; cand.run_id     != null } else := 0
_audit := 1 if { true } else := 0  # SQL 层日志存在性此处简化; Python 侧补全精确值

deny["G3-4 g3_confidence_distribution 低于阈值; 候选置信度分布不稳定"] if { _sub_score_g3_4 < th.g3_conf_distribution }
_sub_score_g3_4 := 1.0 - clamp((_sigma - 0.15) / 0.25, 0.0, 1.0) if {
    _xs := ctx.sibling_confidences
    _mu := sum(_xs) / count(_xs)
    _variance := sum([(x - _mu) * (x - _mu) | x := _xs[_]]) / count(_xs)
    _sigma := math.sqrt(_variance)
} else := 1.0 if { count(ctx.sibling_confidences) < 2 }
clamp(x, lo, hi) := lo if x < lo else hi if x > hi else x

deny["G3-5 g3_redundancy_rate 低于阈值; 与现有 USL 术语高度相似（疑似重复）"] if { _sub_score_g3_5 < th.g3_redundancy_low }
_sub_score_g3_5 := 1.0 - _max_sim if {
    _sims := [s | t := ctx.usl_terms[_]; s := _lev_similarity(cand.canonical_term, t.canonical)]
    _max_sim := max(_sims)
} else := 0.0 if { count(ctx.usl_terms) == 0 }
_lev_similarity(a, b) := s if { d := _lev_dist(a, b); m := max([len(a), len(b)]); s := 1.0 - (d / m) } else := 0.0
_lev_dist(a, b) := d if { d := levenshtein.distance(a, b) } else := 999  # 若 OPA 内置无 lev; 实际 Python 侧对齐

deny["G3-6 g3_future_expandable 低于阈值; 扩展槽预留不足"] if { _sub_score_g3_6 < th.g3_future_expandable }
_sub_score_g3_6 := (_leaf_slot + _depth + _ns_prefix) / 3.0
_leaf_slot := 1 if {
    count([p | p := cand.hint_parents[_]; _is_leaf(p)]) > 0
} else := 0
_is_leaf(p) := true if { not some e in ctx.hierarchy_edges; e.parent == p } else := false
_depth := 1 if {
    _ds := [_depth_of(p) | p := cand.hint_parents[_]]
    avg(_ds) <= 5  # 平均深度不过深，预留扩展
} else := 0
_depth_of(x) := d if { d := count([1 | e := ctx.hierarchy_edges[_]; e.child == x]) + 1 } else := 1
_ns_prefix := 1 if { regex.match(`^[a-zA-Z]+_`, cand.canonical_term); true } else := 0  # 命名空间前缀鼓励

# ---------- 整体 allow / verdict ----------

g1_avg := (_sub_score_g1_1 + _sub_score_g1_2 + _sub_score_g1_3 + _sub_score_g1_4) / 4.0
g2_avg := (_sub_score_g2_1 + _sub_score_g2_2 + _sub_score_g2_3 + _sub_score_g2_4 + _sub_score_g2_5 + _sub_score_g2_6) / 6.0
g3_avg := (_sub_score_g3_1 + _sub_score_g3_2 + _sub_score_g3_3 + _sub_score_g3_4 + _sub_score_g3_5 + _sub_score_g3_6) / 6.0
total  := round((0.3 * g1_avg) + (0.4 * g2_avg) + (0.3 * g3_avg), 4)

verdict := "PASS"   if total >= 0.80
verdict := "REVIEW" if total >= 0.50; total < 0.80
verdict := "FAIL"   if total < 0.50

recommend_auto_skip := true if { total >= 0.90 } else := false

allow if {
    count(deny) == 0
    verdict == "PASS"
}
```

---

## Section 5: 对照测试（Parity Test）要点

对应 **I3T15** `tests/unit/test_opa_16rules_parity.py`:

| 对照维度 | 断言 |
|---------|------|
| 逐子指标 score | `abs(py_score - opa_sub_score) ≤ 0.03`（对 20 组 edge case × 16 指标 = 320 断言） |
| gate 平均 | `abs(py.gate1_score - g1_avg) ≤ 0.03`；g2/g3 同 |
| total_score | `abs(py.total_score - opa.total) ≤ 0.03` |
| overall verdict | `py.overall == verdict` 或容错 REVIEW↔PASS 当 0.795~0.805 边界 |
| recommend_auto_skip | 布尔严格相等 |
| deny 列表一致性 | 任一 `deny[i]` 对应 Python 子指标 reason 中关键词匹配（如 G1-3 触发 → reason 含 "未定义" 或 "undefined"） |

**20 组 Edge Case Input**（构造覆盖）：
- Case 1-4: 全 PASS / 全 FAIL / 边界 0.5 / 边界 0.8 / 边界 0.9 (auto skip)
- Case 5-8: G2-2 / G2-6 硬门槛触发（环 / 自环）→ score=0.0
- Case 9-12: G1-2 / G1-3 / G1-4 各一个单独 fail
- Case 13-15: G2-1 跨域歧义 / G2-4 不相交对违规 / G2-5 基数违规
- Case 16-18: G3-2 命名违规（含数字开头）/ G3-3 缺 source_step / G3-5 高冗余（lev=0.95）
- Case 19-20: 纯空候选 + 最大规模候选（synonyms=50, hint_parents=50）
