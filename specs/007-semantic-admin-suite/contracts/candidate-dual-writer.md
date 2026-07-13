# Contract: CandidateDualWriter — SQLite + Neo4j 双写 8 方法签名

**Location**:
- `CandidateDualWriter` (Interface ABC): `odap/biz/semantic_admin/candidate_store/interfaces/dual_writer.py`
- `Neo4jSchemaGraphWriter` (Impl): `odap/biz/semantic_admin/candidate_store/impl/neo4j_schema_graph_writer.py`（Neo4j 侧）
- `SqlitePipelineStorage` (SQLite 侧，复用 ol_pipeline 模块): `odap/biz/semantic_admin/ol_pipeline/storage/sqlite_pipeline_storage.py`

**依赖关系**: `ol_pipeline/L{1,2}_stage.py → CandidateDualWriter`（流水线每产出一批候选就调用）。SQLite 为主（强一致），Neo4j 为从（最终一致，失败降级：SQLite 仍成功，Neo4j 仅记录告警 + 重试队列）。**禁止**双写任一侧失败时抛出阻断异常（除非 `strict=True`）——避免影响 OL 流水线主流程。

---

## Section 0: 公共数据类型

```python
from typing import Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

# ============= 枚举 =============
class CandidateType(str, Enum):
    TERM           = "term"
    SYNONYM        = "synonym"
    HIERARCHY      = "hierarchy"
    PROPERTY       = "property"
    CROSS_MAPPING  = "cross_mapping"

class OriginLayer(str, Enum):
    L1 = "L1"
    L2 = "L2"

class CandidateLifecycleStatus(str, Enum):
    """10+ 状态枚举（对齐 data-model.md §2 schema_candidates.lifecycle_status + §3 状态机）。"""
    SUBMITTED               = "SUBMITTED"
    L1_REVIEW_PENDING       = "L1_REVIEW_PENDING"
    L1_ACCEPTED             = "L1_ACCEPTED"
    L2_REVIEW_PENDING       = "L2_REVIEW_PENDING"
    L2_ACCEPTED             = "L2_ACCEPTED"
    L2_REJECTED             = "L2_REJECTED"
    QUALITY_REVIEW          = "QUALITY_REVIEW"
    AUDITOR_REVIEW          = "AUDITOR_REVIEW"
    ADMIN_REVIEW            = "ADMIN_REVIEW"
    APPROVED                = "APPROVED"
    PUBLISHED               = "PUBLISHED"
    MERGED                  = "MERGED"
    AUDITOR_REJECTED        = "AUDITOR_REJECTED"
    REJECTED                = "REJECTED"
    STOPLISTED              = "STOPLISTED"
    DUPLICATE               = "DUPLICATE"
    MERGED_INTO_USL         = "MERGED_INTO_USL"

class LifecycleGate(str, Enum):
    G1 = "G1"   # 结构一致性关（7 子指标）
    G2 = "G2"   # 语义一致性关（4 子指标）
    G3 = "G3"   # 领域覆盖关（5 子指标）

class WriteSide(str, Enum):
    SQLITE  = "sqlite"
    NEO4J   = "neo4j"
    BOTH    = "both"

# ============= 核心 Pydantic =============
class SchemaCandidate(BaseModel):
    """候选本体条目（term/synonym/hierarchy/property/cross_mapping）。
    统一以 payload_json 存储类型特定字段，避免 schema_candidates 表随 candidate_type 增加频繁改列。"""
    model_config = {"from_attributes": True, "extra": "allow"}

    id: str
    run_id: str
    domain_id: str
    origin_layer: OriginLayer
    candidate_type: CandidateType
    lifecycle_status: CandidateLifecycleStatus = CandidateLifecycleStatus.SUBMITTED
    current_gate: Optional[LifecycleGate] = None
    next_approver_role: Optional[str] = None
    merged_into_term_id: Optional[str] = None
    duplicate_of_candidate_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)   # JSON → schema_candidates.payload_json
    source_evidence: list[dict[str, Any]] = Field(default_factory=list)  # JSON → source_evidence_json
    gate1_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    gate2_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    gate3_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    quality_total_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    quality_details: Optional[dict[str, Any]] = None
    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None
    l1_processed_at: Optional[datetime] = None
    l2_promoted_at: Optional[datetime] = None
    l2_rejected_at: Optional[datetime] = None
    quality_reviewed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    written_back_at: Optional[datetime] = None
    current_assignee: Optional[str] = None
    current_step_order: int = 0
    priority_score: float = 0.0
    row_version: int = 1
    created_at: datetime
    updated_at: datetime

class Neo4jWriteResult(BaseModel):
    node_id: Optional[str] = None               # MERGE 后返回的元素 ID（如 <element_id>）
    edge_types_written: list[str] = Field(default_factory=list)
    side: WriteSide = WriteSide.BOTH
    sqlite_ok: bool = True
    neo4j_ok: bool = True
    neo4j_error_message: Optional[str] = None
    retryable: bool = False                     # True=网络瞬断可重试；False=数据/约束错误
```

---

## Section 1: CandidateDualWriter 8 方法签名

```python
class CandidateDualWriter:
    """候选双写抽象基类（SQLite 为主 + Neo4j 为从）。
    默认策略：任一侧失败都不中断 OL 流水线主流程（严格模式 strict=True 除外）。
    所有写操作幂等：重复调用相同 (candidate_id, side) 不产生重复数据。
    """

    def __init__(self,
                 sqlite_storage: "SqlitePipelineStorage",
                 neo4j_driver: Any | None = None,    # None = 降级：只写 SQLite
                 neo4j_namespace_prefix: str = "USL__",
                 strict: bool = False,               # True = Neo4j 失败也抛异常（仅质量闸/审批前使用）
                 retry_attempts: int = 3,
                 retry_backoff_sec: float = 0.5):
        ...

    # ============= M1: create_candidate（高流量入口，流水线 L1/L2 批量主路径） =============
    def create_candidate(self, candidate: SchemaCandidate, *,
                         side: WriteSide = WriteSide.BOTH,
                         batch_id: Optional[str] = None) -> Neo4jWriteResult:
        """M1: 新建候选（= SQLite INSERT schema_candidates + Neo4j MERGE USL__Candidate 节点
                                + 可选 USL__IS_A_DRAFT 域根边）。

        内部实现委托：M2 upsert_sqlite + M3 write_neo4j_usl_candidate_node + M5 link_neo4j_draft_edge。

        Args:
            candidate: 完整候选实体（必填：run_id, domain_id, origin_layer, candidate_type, payload, source_evidence）
            side:      BOTH = 双写；SQLITE = 只写 SQLite（降级）；NEO4J = 只补 Neo4j（补齐回补场景）
            batch_id:  可选：批量写入批次 ID（便于日志聚合）

        Returns:
            Neo4jWriteResult（含 node_id / side / sqlite_ok / neo4j_ok / 错误详情）

        Raises:
            ValueError: candidate 必填字段缺失（payload 必须至少含 {canonical_name, proposed_name, ...}，
                        具体由 candidate_type 的 schema 校验）
            ConstraintViolationError: strict=True 且任一侧 UNIQUE/FOREIGN KEY 失败
        """

    # ============= M2: upsert_sqlite（低阶：仅写 SQLite 侧） =============
    def upsert_sqlite(self, candidate: SchemaCandidate) -> SchemaCandidate:
        """M2: 仅 SQLite 侧 upsert schema_candidates（UNIQUE(id) → ON CONFLICT DO UPDATE）。
        被 create_candidate / update_status / quality 回写等场景复用。

        Args:
            candidate: 待持久化候选

        Returns:
            写后最新实体（含 row_version + updated_at = now）

        Raises:
            ValueError: candidate.id / candidate.run_id / candidate.domain_id 为空
        """

    # ============= M3: write_neo4j_usl_candidate_node（Neo4j 候选节点写入/更新） =============
    def write_neo4j_usl_candidate_node(self, candidate: SchemaCandidate) -> Neo4jWriteResult:
        """M3: MERGE (c:USL__Candidate {id: candidate.id}) SET ...（对齐 data-model.md §3 2.3 Cypher 片段）。
        写入的属性严格白名单：domain_id, canonical_name, proposed_name, l1_category, l2_category,
        status (= lifecycle_status.value), confidence, quality_total_score, quality_level,
        source_document, pipeline_run_id, created_at, updated_at。

        Args:
            candidate: 候选（必填 id, domain_id, payload['canonical_name']）

        Returns:
            Neo4jWriteResult(node_id=...)；降级场景 neo4j_driver=None → neo4j_ok=False 但不抛错
        """

    # ============= M4: write_neo4j_l2_edges（L2 层级成员关系边） =============
    def write_neo4j_l2_edges(self, child_candidate_id: str,
                             parent_candidate_ids: list[str],
                             *,
                             confidence: float = 1.0,
                             relation_type: str = "IS_A") -> Neo4jWriteResult:
        """M4: 批量写入 L2 层级边：MATCH (child:USL__Candidate) MATCH (parent:USL__Candidate)
                                          MERGE (child)-[r:USL__L2_MEMBER_OF]->(parent) SET r.*
        （对齐 data-model.md §3 2.4 Cypher 片段）。

        Args:
            child_candidate_id:    schema_candidates.id（子节点）
            parent_candidate_ids:  父候选 ID 列表（通常 1-3 个；空列表 → 跳过写，直接返回空结果）
            confidence:            payload_json 中的层级置信度 [0,1]
            relation_type:         "IS_A" 固定（hierarchy_type 枚举更丰富时可扩展）

        Returns:
            Neo4jWriteResult(edge_types_written=["USL__L2_MEMBER_OF"])；
            任何单个 parent 不存在 → 在 error_message 中记录 "parent_missing: [ids]"，但仍返回 result.neo4j_ok=True（避免整体失败）
        """

    # ============= M5: link_neo4j_draft_edge（草稿状态 → 域根节点边，便于"草稿箱"图查询） =============
    def link_neo4j_draft_edge(self, candidate_id: str, domain_id: str, *,
                              candidate_status: str = "SUBMITTED") -> Neo4jWriteResult:
        """M5: MERGE (domain_root:USL__DomainRoot {domain_id})
              MERGE (c:USL__Candidate {id: candidate_id})-[r:USL__IS_A_DRAFT]->(domain_root) SET r.status + r.timestamps
        （对齐 data-model.md §3 2.5 Cypher 片段）。审批通过后由 M8 或 writeback 模块删此边。

        Args:
            candidate_id:     schema_candidates.id
            domain_id:        usl_domains.id（域根节点 USL__DomainRoot 创建或 MERGE）
            candidate_status: lifecycle_status.value 字符串（冗余在边上，方便按边 status 过滤）

        Returns:
            Neo4jWriteResult(edge_types_written=["USL__IS_A_DRAFT"])
        """

    # ============= M6: count_sqlite_by_status（待办列表 / Dashboard 计数） =============
    def count_sqlite_by_status(self, *, domain_id: Optional[str] = None,
                               group_by_lifecycle: bool = True,
                               group_by_gate: bool = False,
                               group_by_approver: bool = False) -> dict[str, Any]:
        """M6: 按各种维度聚合 schema_candidates 计数（SQLite COUNT + GROUP BY，只读）。
        Dashboard 与候选人列表顶部计数条的统一数据源。**使用 schema_candidates 覆盖索引**避免全表扫描。

        Args:
            domain_id:          None=全局；否则按域过滤
            group_by_lifecycle: True → 按 lifecycle_status 分桶（10+ 状态）
            group_by_gate:      True → 按 current_gate (G1/G2/G3/None) 分桶
            group_by_approver:  True → 按 next_approver_role (schema_auditor / ontology_admin / None) 分桶

        Returns:
            {
              "total": int,
              "by_lifecycle": {"SUBMITTED": int, "AUDITOR_REVIEW": int, ...},   # group_by_lifecycle=True
              "by_gate":      {"G1": int, "G2": int, "G3": int, None: int},     # group_by_gate=True
              "by_approver":  {"schema_auditor": int, "ontology_admin": int, None: int}, # group_by_approver=True
              "domain_id":    str | None
            }

        Raises:
            ValueError: 三个 group_by 全 False（至少一个 True 才有意义）
        """

    # ============= M7: get_run_candidates（单次 run 的候选清单 / 分页） =============
    def get_run_candidates(self, run_id: str, *,
                           lifecycle_status: Optional[CandidateLifecycleStatus | list[CandidateLifecycleStatus]] = None,
                           candidate_type: Optional[CandidateType] = None,
                           min_quality_score: Optional[float] = None,
                           only_assigned_to: Optional[str] = None,
                           include_payload_summary: bool = True,
                           page: int = 1,
                           page_size: int = 100) -> tuple[int, list[SchemaCandidate]]:
        """M7: 取某次 pipeline run 产出的候选（分页 + 多维筛选）。
        前端 /pipeline/runs/{run_id} 详情页 + /candidates 列表页（按 run_id 筛选标签）共同数据源。

        Args:
            run_id:                 pipeline_runs.id（必填）
            lifecycle_status:       单状态或状态列表
            candidate_type:         term/synonym/hierarchy/property/cross_mapping
            min_quality_score:      quality_total_score >= min 才返回
            only_assigned_to:       current_assignee == user_id（用于"我的待办"）
            include_payload_summary: True → 从 payload_json 中提取 5-8 个关键字段拼到 model 顶层，避免解析整个大 JSON
            page/page_size:         分页

        Returns:
            (total_count, candidates_list)

        Raises:
            ValueError: run_id 为空 / page_size > 500 硬上限
        """

    # ============= M8: bulk_delete_duplicates（批量去重：标记 DUPLICATE + 删 Neo4j 重复节点草稿边） =============
    def bulk_delete_duplicates(self, domain_id: str,
                               duplicate_pairs: list[tuple[str, str]],   # [(winner_id, loser_id), ...]
                               *,
                               operator_id: str,
                               note: str = "dedup: semantic_similarity >= 0.95") -> dict[str, int]:
        """M8: 批量标记重复（OL L2 聚类后或人工审核"判定重复"时调用）。
        对每个 loser_id：
            (1) SQLite 侧 UPDATE schema_candidates SET lifecycle_status='DUPLICATE',
                duplicate_of_candidate_id = winner_id, updated_at = now, row_version++
                WHERE id = loser_id
            (2) Neo4j 侧 MATCH (loser:USL__Candidate)-[draft:USL__IS_A_DRAFT]->(root)
                DELETE draft;  OPTIONAL SET loser :USL__Duplicate（保留节点用于审计，不直接 DETACH DELETE）
            (3) loser 如有 USL__L2_MEMBER_OF 子边 → MOVE 到 winner 下（MERGE + DELETE 原边）

        Args:
            domain_id:           域（用于索引 + 跨域防护）
            duplicate_pairs:     重复对列表 [(winner_id, loser_id), ...]，长度建议 <= 500/批
            operator_id:         去重操作人（审计记录用，存到 loser.payload.dedup_meta.operator_id）
            note:                去重说明（默认：相似度阈值触发）

        Returns:
            {"processed_pairs": int, "sqlite_updated": int, "neo4j_draft_edges_deleted": int, "neo4j_labels_applied": int}

        Raises:
            ValueError: duplicate_pairs 长度为 0 或 winner_id == loser_id（自指）
            DomainMismatchError: winner 或 loser 的 domain_id 与形参 domain_id 不符
        """
```

---

## Section 2: 降级与故障切换规则（Contract Guarantee）

| 场景 | 行为（strict=False，默认） | 行为（strict=True） |
|------|---------------------------|---------------------|
| Neo4j 不可用（连接失败） | SQLite 写入**仍然成功**；返回 `Neo4jWriteResult(neo4j_ok=False, neo4j_error_message="...", retryable=True)`；写入重试队列（SQLite `retry_queue` 表或内存 TTL） | 抛 `Neo4jTransientError`（retryable=True），调用方决定重试 |
| Neo4j 约束错误（UNIQUE 同 id 但属性冲突） | MERGE 解决（属性以 SET 为准）；通常不失败；极端冲突 → neo4j_ok=False + 日志 | 抛 `Neo4jConstraintError`（retryable=False） |
| SQLite FK 失败（run_id 不存在） | **立即失败**（因为 SQLite 是主；不允许主从角色颠倒） | 同上 |
| 双写都成功后 Neo4j 后台丢数据（理论上小概率） | 由后台任务 `dual_writer_reconciliation_job(domain_id)` 对比 SQLite→Neo4j：SQLite 存在但 Neo4j 缺失的节点 → 重跑 M3+M5 补齐（幂等） | 同上 |

**SLA 保证**：默认 strict=False 下，**只要 SQLite 可用，候选创建的可用性 = SQLite 可用性**（Neo4j 只是可视化加速，不阻断 OL 主流程）。
