# Contract: QualityGateService + ApprovalWorkflowService + OPA 22 Rego 规则

> ## 版块清理说明（2026-08-07 · 已完成 D3.3 修正）
>
> 质量闸从 3 关 × 16 子指标扩展为 **3 关 × 22 子指标**（从 006 ValidationEngine 移交 6 项）：
> - **QG-1 新增** G1.8 fill_rate / G1.9 empty_rate / G1.10 orphan_count（完整性）
> - **QG-2 新增** G2.5 dangling_relations / G2.6 invalid_action_targets / G2.7 invalid_rule_references（引用一致性）
> - QG-3 不变（5 子项）
>
> **权威来源**：`specs/007-semantic-admin-suite/data-model.md §4`（G1×10 / G2×7 / G3×5，权重 0.35/0.40/0.25）。
> 本契约正文与 data-model.md 完全对齐：`Quality22Submetrics` 类定义 22 字段、`SubmetricThreshold` 定义 22 阈值、Rego 22 条 deny 规则、权重公式 `0.35*g1 + 0.40*g2 + 0.25*g3`。
>
> 006 ValidationEngine 契约已废弃（见 `specs/006-he-extraction-chain/contracts/validation-engine.md` 顶部声明）。
> 详见 `specs/REFACTORING-NOTES.md`。

**Location**:
- `QualityGateService`: `odap/biz/core/ontology/semantic/services/quality_gate_service.py`
- `QualityCalculator` (22 子指标计算): `odap/biz/semantic_admin/quality_gate/services/quality_calculator.py`
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
    """22 子指标各自阈值（低于则 deny 触发）。可配置。

    权威来源：data-model.md §4.3 / §4.4 / §4.5。
    G1.1-G1.7 / G2.1-G2.4 / G3.1-G3.5 为原有 16 项；
    G1.8-G1.10 / G2.5-G2.7 为版块清理从 006 ValidationEngine 移交的 6 项。
    """
    # ---------- Gate 1: 句法/结构（10 项） ----------
    G1_NAME_VALID              = None   # G1.1 名称合规（布尔，无连续阈值）
    G1_EN_MAPPING_VALID        = None   # G1.2 en_mapping 可用 PascalCase（布尔）
    G1_SEMANTIC_TYPE_VALID     = None   # G1.3 semantic_type 合法 6 枚举（布尔）
    G1_SYNONYMS_SIZE_VALID     = 30.0   # G1.4 同义词集大小 ∈ [0, 30]
    G1_SYNONYMS_DEDUP_RATIO    = 0.98   # G1.5 同义词去重率 ≥ 0.98
    G1_CIRCULAR_INCLUSION_FREE = None   # G1.6 canonical 与同义词无互相包含环（布尔）
    G1_USL_DUPLICATE_CHECK     = None   # G1.7 USL 同名冲突检查（布尔，命中 → origin=usl）
    G1_FILL_RATE               = 0.50   # G1.8 [006 移交] 属性字段填充率 ≥ 0.5
    G1_EMPTY_RATE              = 0.30   # G1.9 [006 移交] 必填字段空值率 ≤ 0.3
    G1_ORPHAN_RATIO            = 0.30   # G1.10 [006 移交] 孤儿实体占比 ≤ 0.3
    # ---------- Gate 2: 语义一致性（7 项） ----------
    G2_USL_DISJOINTNESS        = None   # G2.1 USL Disjointness 不相交（布尔，硬门槛 FAIL）
    G2_CARDINALITY_CONSTRAINT  = None   # G2.2 基数约束（min=0, max=NULL）
    G2_ISA_ACYCLIC             = None   # G2.3 is_a 无环（布尔，硬门槛 FAIL）
    G2_LLM_SEMANTIC_JUDGE      = None   # G2.4 LLM Judge 语义一致性（布尔，默认关闭）
    G2_DANGLING_RELATIONS      = None   # G2.5 [006 移交] 悬空关系检查（布尔）
    G2_INVALID_ACTION_TARGETS  = None   # G2.6 [006 移交] 动作目标指向无效 ObjectType（布尔）
    G2_INVALID_RULE_REFERENCES = None   # G2.7 [006 移交] 规则引用实体不存在（布尔）
    # ---------- Gate 3: 领域质量（5 项，连续分子权重） ----------
    G3_PROPERTY_DENSITY        = 0.20   # G3.1 属性密度（confidence×1.5 阈值）
    G3_TERM_FREQUENCY_COVERAGE = 10.0   # G3.2 词频覆盖率 doc_hits 目标
    G3_SYNONYM_RICHNESS        = 5.0    # G3.3 同义词丰富度目标
    G3_USL_ALIGNMENT_NOVELTY   = None   # G3.4 USL 对齐率（反向新颖度，无阈值）
    G3_HIERARCHY_CONTRIBUTION  = 3.0    # G3.5 层级贡献度 l3_children_est 目标


# ============= 子指标详情 =============
class SubmetricDetail(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    threshold: Optional[float]            # None=无具体阈值（布尔判定）；float=连续分阈值
    rule_name: str                        # 对应 Rego deny 规则名，如 "g1_name_valid"
    reason: str                           # 中文解释，如 "发现 2 个未在 PropertySpec 定义的字段"
    actual_value: Any = None              # 如 2/3 字段匹配 -> actual = 0.667


class Quality22Submetrics(BaseModel):
    """22 子指标完整详情（G1×10 / G2×7 / G3×5）。

    权威来源：data-model.md §4.3 / §4.4 / §4.5。
    - G1.1-G1.7：原有 7 项（句法/结构）
    - G1.8-G1.10：从 006 ValidationEngine 移交 3 项（完整性）
    - G2.1-G2.4：原有 4 项（语义一致性）
    - G2.5-G2.7：从 006 ValidationEngine 移交 3 项（引用一致性）
    - G3.1-G3.5：原有 5 项（领域质量，不变）
    """

    # ---------- Gate 1: 句法/结构（10 项） ----------
    g1_name_valid: SubmetricDetail                   # G1.1 名称合规
    g1_en_mapping_valid: SubmetricDetail             # G1.2 en_mapping 可用
    g1_semantic_type_valid: SubmetricDetail          # G1.3 semantic_type 合法
    g1_synonyms_size_valid: SubmetricDetail          # G1.4 同义词集大小
    g1_synonyms_dedup_ratio: SubmetricDetail         # G1.5 同义词去重率
    g1_circular_inclusion_free: SubmetricDetail      # G1.6 canonical 与同义词无环
    g1_usl_duplicate_check: SubmetricDetail          # G1.7 USL 同名冲突
    g1_fill_rate: SubmetricDetail                    # G1.8 [006 移交] 属性字段填充率
    g1_empty_rate: SubmetricDetail                   # G1.9 [006 移交] 必填字段空值率
    g1_orphan_ratio: SubmetricDetail                 # G1.10 [006 移交] 孤儿实体占比

    # ---------- Gate 2: 语义一致性（7 项） ----------
    g2_usl_disjointness: SubmetricDetail             # G2.1 USL Disjointness
    g2_cardinality_constraint: SubmetricDetail       # G2.2 基数约束
    g2_isa_acyclic: SubmetricDetail                  # G2.3 is_a 无环
    g2_llm_semantic_judge: SubmetricDetail           # G2.4 LLM Judge（默认关）
    g2_dangling_relations: SubmetricDetail           # G2.5 [006 移交] 悬空关系
    g2_invalid_action_targets: SubmetricDetail       # G2.6 [006 移交] 动作目标无效
    g2_invalid_rule_references: SubmetricDetail      # G2.7 [006 移交] 规则引用无效

    # ---------- Gate 3: 领域质量（5 项） ----------
    g3_property_density: SubmetricDetail             # G3.1 属性密度
    g3_term_frequency_coverage: SubmetricDetail      # G3.2 词频覆盖率
    g3_synonym_richness: SubmetricDetail             # G3.3 同义词丰富度
    g3_usl_alignment_novelty: SubmetricDetail        # G3.4 USL 对齐率（新颖度）
    g3_hierarchy_contribution: SubmetricDetail       # G3.5 层级贡献度

    def gate1_avg(self) -> float:
        """G1 平均分（10 子项加权：FAIL 类×5，WARN 类×1）。

        权重来自 data-model.md §4.3 扣分项：
        G1.1/G1.3 为 FAIL 类（×5），其余为 WARN 类（×1）。
        """
        items = [
            (5.0, self.g1_name_valid.score),               # G1.1 FAIL
            (1.0, self.g1_en_mapping_valid.score),         # G1.2 WARN
            (5.0, self.g1_semantic_type_valid.score),      # G1.3 FAIL
            (1.0, self.g1_synonyms_size_valid.score),      # G1.4 WARN
            (1.0, self.g1_synonyms_dedup_ratio.score),     # G1.5 WARN
            (1.0, self.g1_circular_inclusion_free.score),  # G1.6 WARN
            (1.0, self.g1_usl_duplicate_check.score),      # G1.7 INFO
            (1.0, self.g1_fill_rate.score),                # G1.8 WARN [006 移交]
            (1.0, self.g1_empty_rate.score),               # G1.9 WARN [006 移交]
            (1.0, self.g1_orphan_ratio.score),             # G1.10 WARN [006 移交]
        ]
        total_w = sum(w for w, _ in items)
        numer = sum(w * s for w, s in items)
        return numer / total_w if total_w > 0 else 0.0

    def gate2_avg(self) -> float:
        """G2 平均分（7 子项简单平均）。

        G2.1 / G2.3 为硬门槛（命中 → 0.0 → FAIL），其余为 WARN。
        """
        items = [
            self.g2_usl_disjointness.score,            # G2.1 硬门槛
            self.g2_cardinality_constraint.score,       # G2.2
            self.g2_isa_acyclic.score,                  # G2.3 硬门槛
            self.g2_llm_semantic_judge.score,           # G2.4 默认关
            self.g2_dangling_relations.score,           # G2.5 [006 移交]
            self.g2_invalid_action_targets.score,       # G2.6 [006 移交]
            self.g2_invalid_rule_references.score,      # G2.7 [006 移交]
        ]
        return sum(items) / max(1, len(items))

    def gate3_avg(self) -> float:
        """G3 平均分（5 子项内部加权：0.30/0.20/0.15/0.15/0.20）。

        权重来自 data-model.md §4.5。
        """
        weights = (0.30, 0.20, 0.15, 0.15, 0.20)
        items = [
            self.g3_property_density.score,
            self.g3_term_frequency_coverage.score,
            self.g3_synonym_richness.score,
            self.g3_usl_alignment_novelty.score,
            self.g3_hierarchy_contribution.score,
        ]
        total_w = sum(weights)
        numer = sum(w * s for w, s in zip(weights, items))
        return numer / total_w if total_w > 0 else 0.0


# ============= QualityReport =============
class QualityReport(BaseModel):
    report_id: str
    candidate_id: str
    run_id: Optional[str] = None
    generated_at: datetime
    gate1_score: float = Field(ge=0.0, le=1.0)     # = submetrics.gate1_avg()
    gate2_score: float = Field(ge=0.0, le=1.0)     # = submetrics.gate2_avg()
    gate3_score: float = Field(ge=0.0, le=1.0)     # = submetrics.gate3_avg()
    total_score: float = Field(ge=0.0, le=1.0)     # = 0.35*g1 + 0.40*g2 + 0.25*g3
    submetrics: Quality22Submetrics
    overall: OverallVerdict
    recommend_auto_skip: bool                      # total>=0.9 且审批流会跳过 admin

    @classmethod
    def compute_total(cls, g1: float, g2: float, g3: float) -> float:
        """权重 0.35/0.40/0.25（data-model.md §4.1 权威定义）。"""
        return round(0.35 * g1 + 0.40 * g2 + 0.25 * g3, 4)

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
    """三质量门评估。evaluate() 返回 22 子指标 + 总分。
    内部先调用 Python 计算 → 再调用 OPA Rego 规则对照（见 parity 测试 I3T15）。
    最终以 Python 结果 + OPA deny 列表合并为 report。

    版块清理（2026-08-07）：22 子指标 = 16 原有 + 6 项从 006 ValidationEngine 移交
    （G1.8-G1.10 完整性 + G2.5-G2.7 引用一致性）。
    """

    def __init__(self, usl_manager: "UslManagerService", storage: "SqliteUslStorage",
                 opa_policy_path: str | None = None, cache_ttl_sec: int = 3600): ...

    # ============ 主入口 ============
    def evaluate(self, candidate_id: str, force: bool = False) -> QualityReport:
        """评估 candidate → 生成 QualityReport。

        流程：
          1. 从 storage 读取 candidate；未找到 → CandidateNotFoundError
          2. cache_hit 且 force=False → 直接返回缓存 report（按 candidate_id 键）
          3. Gate1 评估 → 10 SubmetricDetail（G1.1-G1.7 原有 + G1.8-G1.10 移交）
          4. Gate2 评估 → 7 SubmetricDetail（G2.1-G2.4 原有 + G2.5-G2.7 移交）
          5. Gate3 评估 → 5 SubmetricDetail（G3.1-G3.5 不变）
          6. 计算 gate1_score/gate2_score/gate3_score/total_score/overall
             total_score = 0.35*g1 + 0.40*g2 + 0.25*g3
          7. OPA eval 对照：deny 列表聚合到子指标 reason（分数低于阈值）
          8. 写 storage.quality_reports；返回 QualityReport

        Args:
            candidate_id: ol_candidates 主键
            force: True → 跳过缓存重新计算

        Returns:
            QualityReport（含 22 子指标 + 3 关总分 + overall）

        Raises:
            CandidateNotFoundError: candidate_id 不存在
            RuntimeError: OPA eval 超时或 22 deny 全部 fail → 告警但仍返回 report
        """

    # ============ Gate1 (10) 子方法（public 便于单测） ============
    # ----- 原有 7 项（句法/结构） -----
    def eval_g1_name_valid(self, cand: "Candidate") -> SubmetricDetail:
        """G1.1: 名称合规。
        canonical 匹配正则 `^[\\u4e00-\\u9fa5A-Za-z0-9_.-]{1,40}$` → 1.0；否则 0.0（FAIL -0.35）。"""

    def eval_g1_en_mapping_valid(self, cand: "Candidate") -> SubmetricDetail:
        """G1.2: en_mapping 可用。
        en 非空且为 PascalCase（`^[A-Z][A-Za-z0-9]*$`）→ 1.0；否则 0.0（WARN -0.08，USL 回退补全）。"""

    def eval_g1_semantic_type_valid(self, cand: "Candidate") -> SubmetricDetail:
        """G1.3: semantic_type 合法 6 枚举。
        semantic_type ∈ {对象类型, 关系类型, 属性, 动作类型, 过程类型, 规则类型} → 1.0；
        否则 0.0（FAIL -0.15，默认回退 '对象类型'）。"""

    def eval_g1_synonyms_size_valid(self, cand: "Candidate") -> SubmetricDetail:
        """G1.4: 同义词集大小 ∈ [0, 30]。
        0 ≤ len(synonyms) ≤ 30 → 1.0；否则 0.0（WARN，截断前 30 个）。"""

    def eval_g1_synonyms_dedup_ratio(self, cand: "Candidate") -> SubmetricDetail:
        """G1.5: 同义词去重率 ≥ 0.98。
        unique/original；< 0.98 → 自动去重（WARN）。"""

    def eval_g1_circular_inclusion_free(self, cand: "Candidate") -> SubmetricDetail:
        """G1.6: canonical 与同义词无互相包含环。
        canonical 不在 synonyms 集合中 → 1.0；否则 0.0（WARN，自动剔除）。"""

    def eval_g1_usl_duplicate_check(self, cand: "Candidate") -> SubmetricDetail:
        """G1.7: USL 同名冲突检查。
        查同 domain 下同 canonical；命中 → origin=usl，score=1.0；未命中 → 视为新增（INFO）。"""

    # ----- 从 006 ValidationEngine 移交 3 项（完整性） -----
    def eval_g1_fill_rate(self, cand: "Candidate") -> SubmetricDetail:
        """G1.8 [006 移交]: 属性字段填充率 fill_rate ≥ 0.5。
        已填字段数 / 总字段数；< 0.5 → WARN，标记 needs_review（-0.10）。
        计算来源：candidate.attributes vs PropertySpec 允许字段集。"""

    def eval_g1_empty_rate(self, cand: "Candidate") -> SubmetricDetail:
        """G1.9 [006 移交]: 必填字段空值率 empty_rate ≤ 0.3。
        空必填字段数 / 必填字段总数；> 0.3 → WARN，标记 needs_review（-0.08）。
        计算来源：PropertySpec.required=True 的字段中值为空/null/''的比例。"""

    def eval_g1_orphan_ratio(self, cand: "Candidate") -> SubmetricDetail:
        """G1.10 [006 移交]: 孤儿实体占比 orphan_count / total ≤ 0.3。
        无任何关系连接的实体数 / 总实体数；> 0.3 → WARN，标记 needs_review（-0.05）。
        计算来源：candidate 图谱中无入边+出边的节点比例。"""

    # ============ Gate2 (7) 子方法 ============
    # ----- 原有 4 项（语义一致性） -----
    def eval_g2_usl_disjointness(self, cand: "Candidate") -> SubmetricDetail:
        """G2.1: USL Disjointness 不相交检查（硬门槛 FAIL）。
        candidate 的 canonical + synonyms + near_synonyms + aliases 集合
        与 usl_disjoint_pairs 中任一 (term_a, term_b) 同时命中 → 0.0（FAIL -0.40）；
        否则 1.0。"""

    def eval_g2_cardinality_constraint(self, cand: "Candidate") -> SubmetricDetail:
        """G2.2: 基数约束检查。
        usl_cardinalities 中 (domain_term, rel_name, range_term) 的 min/max_card；
        实际关系数超出 → 每超 10% 扣 0.06；命中即 1.0。"""

    def eval_g2_isa_acyclic(self, cand: "Candidate") -> SubmetricDetail:
        """G2.3: is_a 无环检查（硬门槛 FAIL）。
        对 candidate.hint_parents 做拓扑排序；有环 → 0.0（FAIL -0.20，列出环边）；
        无环 → 1.0。"""

    def eval_g2_llm_semantic_judge(self, cand: "Candidate") -> SubmetricDetail:
        """G2.4: LLM Judge 语义一致性（可选，默认关闭）。
        feature flag `SEMANTIC_ADMIN_ENABLE_LLM_JUDGE=false` → 默认 1.0；
        开启后调用 LLM 判定 yes/no；no → 每次扣 0.05。"""

    # ----- 从 006 ValidationEngine 移交 3 项（引用一致性） -----
    def eval_g2_dangling_relations(self, cand: "Candidate") -> SubmetricDetail:
        """G2.5 [006 移交]: 悬空关系检查 dangling_relations（布尔，WARN -0.15）。
        扫描 candidate 的 relations 集合，找出 subject/object 不在 entities 集合中的边；
        命中 → 0.0（WARN，列出悬空边）；无悬空 → 1.0。"""

    def eval_g2_invalid_action_targets(self, cand: "Candidate") -> SubmetricDetail:
        """G2.6 [006 移交]: 动作目标指向无效 ObjectType（布尔，WARN -0.10）。
        扫描 action_types 集合，验证每个 action 的 target 字段指向已存在的 ObjectType；
        命中无效目标 → 0.0（WARN，列出无效目标）；全部有效 → 1.0。"""

    def eval_g2_invalid_rule_references(self, cand: "Candidate") -> SubmetricDetail:
        """G2.7 [006 移交]: 规则引用实体不存在（布尔，WARN -0.10）。
        扫描 rule_types 集合，验证每个 rule 的 references 字段指向已存在的实体；
        命中无效引用 → 0.0（WARN，列出无效引用）；全部有效 → 1.0。"""

    # ============ Gate3 (5) 子方法 ============
    def eval_g3_property_density(self, cand: "Candidate") -> SubmetricDetail:
        """G3.1: 属性密度。s = min(1, confidence*1.5)，子权重 0.30。"""

    def eval_g3_term_frequency_coverage(self, cand: "Candidate") -> SubmetricDetail:
        """G3.2: 词频覆盖率。s = min(1, doc_hits/10)，子权重 0.20。
        doc_hits 来自 candidate.provenance.doc_hits。"""

    def eval_g3_synonym_richness(self, cand: "Candidate") -> SubmetricDetail:
        """G3.3: 同义词丰富度。s = min(1, (syn+near+alias)/5)，子权重 0.15。"""

    def eval_g3_usl_alignment_novelty(self, cand: "Candidate") -> SubmetricDetail:
        """G3.4: USL 对齐率（反向=新颖度）。s = 1 − usl_align_confidence，子权重 0.15。"""

    def eval_g3_hierarchy_contribution(self, cand: "Candidate") -> SubmetricDetail:
        """G3.5: 层级贡献度。s = min(1, l3_children_est/3)，子权重 0.20。"""

    # ============ OPA 联动 ============
    def _opa_evaluate(self, input_dict: dict[str, Any]) -> list[str]:
        """调用 OPA `opa eval -d policies/quality_gate.rego`。
        返回所有 deny[msg] 的 msg 列表（22 条 deny 规则）。供 reason 聚合。"""
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
    submetric_name: str                    # 如 "g2_dangling_relations" / "g1_fill_rate"
    accepted: bool
    note: Optional[str] = None

class ApprovalWorkflowService:
    """审批工作流：5 个动作方法 = audit / modify / reject / final_approve / auto_skip_admin。
    每次动作都写 comments 历史 + 推送通知。

    版块清理（2026-08-07）：审批可对 22 子指标逐条决策
    （16 原有 + 6 项从 006 ValidationEngine 移交）。
    """

    def __init__(self, storage: "SqliteUslStorage", quality_gate: QualityGateService,
                 usl_manager: "UslManagerService", writeback_svc: Optional["OntologyWritebackService"] = None,
                 sla_hours: int = 48, auto_skip_threshold: float = 0.90): ...

    # ================= M1: audit =================
    def audit(self, task_id: str, auditor_id: str, comment: str,
              decisions: Optional[list[SubmetricDecision]] = None) -> ApprovalTask:
        """M1: 审核动作（reviewer 或 term_editor 初审）。
        语义：审阅者对 22 子指标逐条或整体给出接受/驳回。

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
            decisions:     可选：22 子指标逐条决策（含 6 项 006 移交子指标）

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
          4. 调 `quality_gate.evaluate(candidate_id, force=True)` → 新 report（22 子指标），写 report_id
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

## Section 4: OPA Rego 22 条规则（`quality_gate.rego` 原文）

文件路径：`odap/biz/core/ontology/semantic/services/policies/quality_gate.rego`

**Rego Package & Input Schema**：

```rego
package quality_gate

# ============================================================
# Input Schema（Python QualityGateService 传入）:
# {
#   "candidate": {
#     "id": str, "domain_id": str, "canonical_term": str,
#     "synonyms": [str], "near_synonyms": [str], "aliases": [str],
#     "en": str, "semantic_type": str, "confidence": float,
#     "usl_align_confidence": float, "hint_parents": [str],
#     "source_step": str, "run_id": str, "attributes": {k: v},
#     "provenance": {"doc_hits": int, "l3_children_est": int},
#     "rejected": bool, "created_at": str,
#     # 006 移交字段（G1.8-G1.10 / G2.5-G2.7 用）:
#     "fill_rate": float, "empty_rate": float, "orphan_ratio": float,
#     "dangling_relations": [{"subject": str, "relation": str, "object": str}],
#     "invalid_action_targets": [str], "invalid_rule_references": [str],
#     "entities": [str], "action_types": [dict], "rule_types": [dict]
#   },
#   "context": {
#     "usl_terms": [{"id","canonical","synonyms","en","domain_id"}],
#     "property_specs": [{"prop_name","data_type","required","default_value","enum_values","min_val","max_val"}],
#     "hierarchy_edges": [{"parent","child","edge_type"}],
#     "disjoint_pairs": [{"term_a_id","term_b_id","strict"}],
#     "cardinality_rules": [{"source_term_id","relation","target_term_id","min_card","max_card"}],
#     "domain_en_mapping": {zh: en},
#     "domain_terms": [str],            # 同 domain 已有 canonical 集合（G1.7）
#     "sibling_confidences": [float]    # run 内其他 candidate.confidence
#   },
#   "thresholds": {
#     "g1_synonyms_dedup_ratio": 0.98, "g1_synonyms_size_valid": 30,
#     "g1_fill_rate": 0.5, "g1_empty_rate": 0.3, "g1_orphan_ratio": 0.3,
#     "g3_property_density": 0.2, "g3_term_frequency_coverage": 10,
#     "g3_synonym_richness": 5, "g3_hierarchy_contribution": 3
#   },
#   "enable_llm_judge": false
# }
# ============================================================

import future.keywords.if
import future.keywords.in

# ---------- 辅助 ----------
cand := input.candidate
ctx  := input.context
th   := input.thresholds

len_arr(xs) := count(xs) if xs is array else 0

# ---------- GATE 1: 句法/结构（10 子项） ----------

# G1.1 名称合规（FAIL -0.35）
deny["G1-1 g1_name_valid FAIL: canonical 不符合名称正则"] if {
    not regex.match(`^[\u4e00-\u9fa5A-Za-z0-9_.-]{1,40}$`, cand.canonical_term)
}

# G1.2 en_mapping 可用 PascalCase（WARN -0.08）
deny["G1-2 g1_en_mapping_valid WARN: en 为空或非 PascalCase"] if {
    en := object.get(cand, "en", "")
    not regex.match(`^[A-Z][A-Za-z0-9]*$`, en)
}

# G1.3 semantic_type 合法 6 枚举（FAIL -0.15）
deny["G1-3 g1_semantic_type_valid FAIL: semantic_type 非法合法集"] if {
    st := object.get(cand, "semantic_type", "对象类型")
    not st in {"对象类型", "关系类型", "属性", "动作类型", "过程类型", "规则类型"}
}

# G1.4 同义词集大小 ∈ [0, 30]（WARN，截断）
deny["G1-4 g1_synonyms_size_valid WARN: 同义词数 > 30"] if {
    count(cand.synonyms) > 30
}

# G1.5 同义词去重率 ≥ 0.98（WARN，自动去重）
deny["G1-5 g1_synonyms_dedup_ratio WARN: 去重率 < 0.98"] if {
    ratio := _dedup_ratio(cand.synonyms)
    ratio < th.g1_synonyms_dedup_ratio
}
_dedup_ratio(syns) := count({norm(s) | some s in syns}) / max([count(syns), 1]) if {
    count(syns) > 0
} else := 1.0

# G1.6 canonical 与同义词无互相包含环（WARN，自动剔除）
deny["G1-6 g1_circular_inclusion_free WARN: canonical 出现在同义词集合中"] if {
    cn := lower(trim(cand.canonical_term, " \t\r\n"))
    some s in cand.synonyms
    cn == lower(trim(s, " \t\r\n"))
}

# G1.7 USL 同名冲突检查（INFO，命中 → origin=usl，不 deny）
# OPA 侧依靠 input.domain_terms 比对；命中视为去重成功，不产生 deny

# G1.8 [006 移交] 属性字段填充率 fill_rate ≥ 0.5（WARN -0.10）
deny["G1-8 g1_fill_rate WARN: 属性字段填充率 < 0.5"] if {
    fill_rate := object.get(cand, "fill_rate", 1.0)
    fill_rate < th.g1_fill_rate
}

# G1.9 [006 移交] 必填字段空值率 empty_rate ≤ 0.3（WARN -0.08）
deny["G1-9 g1_empty_rate WARN: 必填字段空值率 > 0.3"] if {
    empty_rate := object.get(cand, "empty_rate", 0.0)
    empty_rate > th.g1_empty_rate
}

# G1.10 [006 移交] 孤儿实体占比 orphan_ratio ≤ 0.3（WARN -0.05）
deny["G1-10 g1_orphan_ratio WARN: 孤儿实体占比 > 0.3"] if {
    orphan_ratio := object.get(cand, "orphan_ratio", 0.0)
    orphan_ratio > th.g1_orphan_ratio
}

# ---------- GATE 2: 语义一致性（7 子项） ----------

# G2.1 USL Disjointness 不相交（硬门槛 FAIL -0.40）
deny["G2-1 g2_usl_disjointness FAIL: 命中 disjoint pair"] if {
    all_terms := {norm(x) | some x in array.concat([cand.canonical_term], array.concat(cand.synonyms, array.concat(cand.near_synonyms, cand.aliases)))}
    some dp in object.get(ctx, "disjoint_pairs", [])
    norm(dp.term_a_id) in all_terms
    norm(dp.term_b_id) in all_terms
}

# G2.2 基数约束检查（WARN，每超 10% 扣 0.06）
# 占位：待 L5 基数归纳后实现具体规则
# deny["G2-2 g2_cardinality_constraint WARN: 基数超限"] if { ... }

# G2.3 is_a 无环（硬门槛 FAIL -0.20）
# 占位：待 L3 拓扑排序后实现具体规则
# deny["G2-3 g2_isa_acyclic FAIL: 检测到层级环"] if { ... }

# G2.4 LLM Judge 语义一致性（默认关，开启后 WARN -0.05/次）
deny["G2-4 g2_llm_semantic_judge FAIL: LLM 判定未通过"] if {
    object.get(input, "enable_llm_judge", false)
    object.get(input, "llm_judge_passed", false) == false
}

# G2.5 [006 移交] 悬空关系检查 dangling_relations（WARN -0.15）
deny["G2-5 g2_dangling_relations WARN: 存在悬空关系"] if {
    count(cand.dangling_relations) > 0
}

# G2.6 [006 移交] 动作目标指向无效 ObjectType（WARN -0.10）
deny["G2-6 g2_invalid_action_targets WARN: 存在无效动作目标"] if {
    count(cand.invalid_action_targets) > 0
}

# G2.7 [006 移交] 规则引用实体不存在（WARN -0.10）
deny["G2-7 g2_invalid_rule_references WARN: 存在无效规则引用"] if {
    count(cand.invalid_rule_references) > 0
}

# ---------- GATE 3: 领域质量（5 子项，连续分子权重 0.30/0.20/0.15/0.15/0.20） ----------

# G3.1 属性密度 s = min(1, confidence*1.5)
deny["G3-1 g3_property_density WARN: 置信度不足"] if {
    conf := to_number(object.get(cand, "confidence", 0))
    s := min([1.0, conf * 1.5])
    s < 0.3
}

# G3.2 词频覆盖率 s = min(1, doc_hits/10)
deny["G3-2 g3_term_frequency_coverage WARN: doc_hits 不足"] if {
    doc_hits := to_number(object.get(object.get(cand, "provenance", {}), "doc_hits", 1))
    s := min([1.0, doc_hits / th.g3_term_frequency_coverage])
    s < 0.5
}

# G3.3 同义词丰富度 s = min(1, (syn+near+alias)/5)
deny["G3-3 g3_synonym_richness WARN: 同义词丰富度低"] if {
    total := count(cand.synonyms) + count(cand.near_synonyms) + count(cand.aliases)
    s := min([1.0, total / th.g3_synonym_richness])
    s < 0.5
}

# G3.4 USL 对齐率（新颖度反向） s = 1 - usl_align_confidence
deny["G3-4 g3_usl_alignment_novelty WARN: 与 USL 重复度过高"] if {
    align := to_number(object.get(cand, "usl_align_confidence", 0))
    s := max([0.0, min([1.0, 1.0 - align])])
    s < 0.2
}

# G3.5 层级贡献度 s = min(1, l3_children_est/3)
deny["G3-5 g3_hierarchy_contribution WARN: 层级贡献度低"] if {
    children := to_number(object.get(object.get(cand, "provenance", {}), "l3_children_est", 1))
    s := min([1.0, children / th.g3_hierarchy_contribution])
    s < 0.3
}

# ---------- 整体 allow / verdict ----------
# Gate 加权（data-model.md §4.1：0.35/0.40/0.25）
g1_avg := _g1_avg
g2_avg := _g2_avg
g3_avg := _g3_avg
total  := round((0.35 * g1_avg) + (0.40 * g2_avg) + (0.25 * g3_avg), 4)

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

对应 **I3T15** `tests/unit/test_opa_22rules_parity.py`（版块清理后从 16 → 22 规则）:

| 对照维度 | 断言 |
|---------|------|
| 逐子指标 score | `abs(py_score - opa_sub_score) ≤ 0.03`（对 20 组 edge case × 22 指标 = 440 断言） |
| gate 平均 | `abs(py.gate1_score - g1_avg) ≤ 0.03`；g2/g3 同 |
| total_score | `abs(py.total_score - opa.total) ≤ 0.03`，权重 0.35/0.40/0.25 |
| overall verdict | `py.overall == verdict` 或容错 REVIEW↔PASS 当 0.795~0.805 边界 |
| recommend_auto_skip | 布尔严格相等 |
| deny 列表一致性 | 任一 `deny[i]` 对应 Python 子指标 reason 中关键词匹配（如 G1-8 触发 → reason 含 "填充率" 或 "fill_rate"） |

**20 组 Edge Case Input**（构造覆盖 22 子指标）：
- Case 1-4: 全 PASS / 全 FAIL / 边界 0.5 / 边界 0.8 / 边界 0.9 (auto skip)
- Case 5-8: G2.1 / G2.3 硬门槛触发（disjoint 命中 / 层级环）→ score=0.0
- Case 9-12: G1.1 / G1.3 / G1.5 / G1.6 各一个单独 fail
- Case 13-15: G2.5 悬空关系 / G2.6 无效动作目标 / G2.7 无效规则引用（[006 移交] 3 项）
- Case 16-18: G1.8 fill_rate < 0.5 / G1.9 empty_rate > 0.3 / G1.10 orphan_ratio > 0.3（[006 移交] 3 项）
- Case 19-20: G3.2 doc_hits 不足 / G3.5 l3_children_est 不足 + 纯空候选 + 最大规模候选（synonyms=50, hint_parents=50）

**权重验证断言**（确保权重更新为 0.35/0.40/0.25）:
```python
# 验证权重公式（data-model.md §4.1 权威定义）
assert QualityReport.compute_total(1.0, 0.0, 0.0) == 0.35   # 仅 G1 满分
assert QualityReport.compute_total(0.0, 1.0, 0.0) == 0.40   # 仅 G2 满分
assert QualityReport.compute_total(0.0, 0.0, 1.0) == 0.25   # 仅 G3 满分
assert QualityReport.compute_total(1.0, 1.0, 1.0) == 1.0    # 全满分
```
