# Contract: UslWritebackService — HITL 飞轮 9 方法签名

**Location**:
- `UslWritebackService` (Interface): `odap/biz/semantic_admin/usl_writeback/interfaces/writeback_handler.py`
- `WritebackServiceImpl`: `odap/biz/semantic_admin/usl_writeback/impl/writeback_service_impl.py`
- `OntologyTBoxWriter`: `odap/biz/semantic_admin/usl_writeback/impl/ontology_tbox_writer.py`（POST 到 biz/core/ontology/ API）
- `HookEventEmitter`: `odap/biz/semantic_admin/usl_writeback/impl/hook_event_emitter.py`（通过 Hook 系统广播 schema_candidate.written_back 事件）

**依赖关系**: `ApprovalService.admin_approve` / `auditor_approve(加速通道)` 触发 → `UslWritebackService.write_approved` → 两步写：
1. 写 USL 4 张核心表（terms / term_synonyms / term_hierarchies / term_properties）+ `usl_cross_domain_mappings`（5 子类型），通过 `UslManagerService`（幂等、冲突合并）；
2. 写 Ontology TBox（ObjectType / LinkType / PropertyDefinition），调用 `biz/core/ontology/api/routes.py`（失败时不回滚步骤 1，但标记 NOT_WRITTEN_BACK + 重试队列）。
最后更新 `schema_candidates.lifecycle_status = MERGED_INTO_USL` + 写回时间戳 + Neo4j USL__Candidate → USL__Term 原子切换。

---

## Section 0: 公共数据类型

```python
from typing import Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

# ============= 枚举 =============
class WritebackStatus(str, Enum):
    NOT_STARTED     = "not_started"
    USL_WRITTEN     = "usl_written"            # USL 成功，Ontology TBox 待执行 / 失败重试
    FULLY_WRITTEN   = "fully_written"          # USL + Ontology TBox 双写成功
    PARTIAL_FAILED  = "partial_failed"         # USL OK + TBox 失败（可重试）
    FULL_FAILED     = "full_failed"            # USL 本身失败（一般数据错误不可自动重试）
    ROLLBACKED      = "rollbacked"             # 管理员主动回滚

class WritebackTarget(str, Enum):
    USL                      = "usl"
    ONTOLOGY_TBOX            = "ontology_tbox"
    BOTH                     = "both"

class SynonymDisposition(str, Enum):
    """写回时 candidate 同义词与现有 USL 同义词冲突如何处理。"""
    MERGE       = "merge"           # 合并去重（默认）
    OVERWRITE   = "overwrite"       # 以候选为准覆盖
    SKIP        = "skip"            # 保留原 USL 的
    ERROR       = "error"           # 冲突即报错（最严格，用于敏感域）

# ============= 核心 Pydantic =============
class WritebackPayload(BaseModel):
    """APPROVED 候选 payload_json 在写回阶段的统一视图（避免写回时解析大 JSON 字段名歧义）。
    由 UslWritebackService._normalize(candidate.payload) 构造，用于 M4/M5/M6/M7 各子写回器。"""
    # —— 基本信息 ——
    canonical_name: str
    proposed_name: Optional[str] = None        # None = canonical
    display_name: Optional[str] = None
    description: Optional[str] = None
    short_definition: Optional[str] = None
    term_type: str = "class"   # "class"/"relation"/"event"/"attribute"/"metric"/"process"/"rule"（对齐 data-model §2 usl_terms.term_type）
    # —— 同义词（可写 term_synonyms） ——
    synonyms: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    stopwords: list[str] = Field(default_factory=list)
    ambiguous_with: list[str] = Field(default_factory=list)   # 歧义候选 term_id 列表
    # —— 层级（term_hierarchies） ——
    parent_term_ids: list[str] = Field(default_factory=list)   # 父候选或父 USL term 的 ID
    hierarchy_type: str = "is_a"                               # "is_a" / "part_of" / "has_role" / "member_of" / "located_in"
    # —— 属性（term_properties） ——
    property_specs: list[dict[str, Any]] = Field(default_factory=list)
      # 每项: {"property_code": str, "property_name": str, "datatype": str,
      #        "required": bool, "allow_multiple": bool, "enum_values": list[str]|None, ...}
    # —— 跨域映射 ——
    cross_mappings: list[dict[str, Any]] = Field(default_factory=list)
      # 每项: {"target_term_id": str, "mapping_type": "exact_match"/..., "directionality": "bidirectional"/...,
      #        "confidence_score": float, "mapping_reason": str|None}
    # —— USL → Ontology 映射提示 ——
    ontology_hints: dict[str, Any] = Field(default_factory=dict)
      # {"object_type_icon": str, "color": str, "default_properties": [...], "link_to": ["ontology_id_1", ...]}

class WritebackResult(BaseModel):
    candidate_id: str
    status: WritebackStatus
    target: WritebackTarget
    # —— USL 侧产物 ——
    usl_term_id: Optional[str] = None
    usl_synonym_ids: list[str] = Field(default_factory=list)
    usl_hierarchy_ids: list[str] = Field(default_factory=list)
    usl_property_ids: list[str] = Field(default_factory=list)
    usl_mapping_ids: list[str] = Field(default_factory=list)
    # —— Ontology TBox 侧产物 ——
    ontology_object_type_id: Optional[str] = None
    ontology_link_type_ids: list[str] = Field(default_factory=list)
    ontology_property_ids: list[str] = Field(default_factory=list)
    # —— 审计 & 元数据 ——
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    executed_by: Optional[str] = None
    errors: list[dict[str, Any]] = Field(default_factory=list)   # [{step, code, message, retryable}, ...]
    warnings: list[str] = Field(default_factory=list)
    retry_attempt: int = 0
    idempotency_key: str = ""
```

---

## Section 1: UslWritebackService 9 方法签名

```python
class UslWritebackService:
    """HITL 写回主服务。9 方法：
    M1~M3: 主入口（write_approved / write_rejected / writeback_status）；
    M4~M7: 5 子类型原子写回（同义词/层级/属性/跨域映射/本体 TBox）；
    M8~M9: 运行表状态推进 + Neo4j DRAFT 边清理。
    """

    def __init__(self,
                 usl_manager: "UslManagerService",
                 ontology_writer: "OntologyTBoxWriter",
                 dual_writer: "CandidateDualWriter",
                 hook_emitter: "HookEventEmitter",
                 sqlite_storage: "SqlitePipelineStorage",
                 *,
                 synonym_disposition: SynonymDisposition = SynonymDisposition.MERGE,
                 write_ontology_tbox_in_same_tx: bool = False,  # False → 先写 USL OK 再写 TBox，TBox 失败不回滚 USL
                 retry_max_attempts: int = 5,
                 retry_backoff_sec: list[float] | None = None):
        ...

    # ============= M1: write_approved（APPROVED → MERGED_INTO_USL，幂等） =============
    def write_approved(self, candidate_id: str, *,
                       target: WritebackTarget = WritebackTarget.BOTH,
                       executed_by: Optional[str] = None,
                       force_idempotency_key: Optional[str] = None,
                       synonym_disposition: Optional[SynonymDisposition] = None,
                       conflict_patch: Optional[dict[str, Any]] = None) -> WritebackResult:
        """M1: 单个 APPROVED 候选写回。**幂等核心方法**。
        若此 candidate_id 已完成写回（schema_candidates.lifecycle_status = MERGED_INTO_USL）→ 直接查历史返回，不做任何写入。

        步骤（顺序严格）：
          1. 读取 candidate；status ∉ {APPROVED, MERGED_INTO_USL, WRITEBACK_FAIL} → WritebackStateError
          2. 幂等检查：查 usl_term_id 是否已存在于 payload._writeback_meta.usl_term_id → 存在 → 直接组装 result 返回
          3. 规范化 payload: wb = WritebackPayload(**_normalize(cand.payload))
          4. 第一步写 USL：
               - M4 usl_term_id  = write_term_to_usl(wb, ...)（术语本身）
               - M5 ids(syn)    = write_synonyms_to_usl(usl_term_id, wb, disposition)
               - M6 ids(hier)   = write_hierarchy_to_usl(usl_term_id, wb, ...)
               - M7 ids(prop)   = write_properties_to_usl(usl_term_id, wb, ...)
               - M8 ids(xmap)   = write_cross_mappings_to_usl(usl_term_id, wb, ...)
          5. 更新 pipeline_runs.writeback_written_count++；若步骤 4 全部 OK → status 暂置 USL_WRITTEN
          6. 若 target ∈ {ONTOLOGY_TBOX, BOTH}：调用 M9.write_ontology_tbox(usl_term_id, wb)
               - 成功 → result.status = FULLY_WRITTEN
               - 失败 retryable=True  → status = PARTIAL_FAILED（保留 USL；记录 errors[0].retryable=True；入重试队列）
               - 失败 retryable=False → PARTIAL_FAILED + 告警
          7. M8：更新 schema_candidates.lifecycle_status = MERGED_INTO_USL（或 APPROVED + retryable 标记）
          8. M9：Neo4j 原子切换 USL__Candidate → USL__Term + 删 USL__IS_A_DRAFT（若写回目标成功）
          9. hook_emitter.broadcast("schema_candidate.written_back", {id, usl_term_id, ...})
         10. 写审计日志（unified_audit: semantic_admin.writeback）

        Args:
            candidate_id:       APPROVED 候选 ID
            target:             USL 只 / TBox 只 / 双写（默认双写）
            executed_by:        操作人；None = "system"（加速通道/定时重试时）
            force_idempotency_key: 手动指定幂等键；默认 = f"wb-{candidate_id}-v{candidate.row_version}"
            synonym_disposition: 对同义词冲突处理；None = 使用构造函数默认 MERGE
            conflict_patch:     可选：已知 USL 冲突时的手工修正（如 domain_override / canonical_name_override）

        Returns: WritebackResult

        Raises:
            CandidateNotFoundError
            WritebackStateError(candidate.status 非可写回态)
            WritebackDataError(payload 缺必填 canonical_name / term_type 非法 / ...) —— 非瞬态，重试无效
        """

    # ============= M2: write_rejected（REJECTED / AUDITOR_REJECTED / L2_REJECTED → 写回黑名单 + 清理 Neo4j） =============
    def write_rejected(self, candidate_id: str, *,
                       reason_code: str,
                       operator_id: Optional[str] = None,
                       add_to_stoplist: bool = False,
                       purge_from_neo4j: bool = True) -> dict[str, Any]:
        """M2: 对"被拒绝候选"做收尾写回：(1) 可选加入 stoplist；(2) 清理 Neo4j 草稿节点/边。
        注意：此方法**不**删除 SQLite 记录（保留全链路审计）；只是状态推进 + 图清理。

        Args:
            candidate_id:       REJECTED / AUDITOR_REJECTED / L2_REJECTED / STOPLISTED
            reason_code:        stoplist 原因代码（如 "spurious_extraction"/"semantic_duplicate"/"insufficient_quality"）
            operator_id:        操作人
            add_to_stoplist:    True → lifecycle_status = STOPLISTED，同义词写入 usl_term_synonyms.is_blacklisted=1 集合
            purge_from_neo4j:   True → MATCH (c:USL__Candidate {id}) DETACH DELETE（或打 USL__Rejected 标签；默认真删因为草稿非终态）

        Returns: {"candidate_id": str, "new_status": str, "stoplist_added": bool, "neo4j_purged": bool}
        """
        ...

    # ============= M3: writeback_status（查询写回状态 + 错误详情） =============
    def writeback_status(self, candidate_ids: list[str]) -> dict[str, WritebackResult | None]:
        """M3: 批量查询写回状态。优先从 storage.payload_json._writeback_meta（每次成功写回时写入）读取，
        不命中时扫 error_summary 最近一次写回失败记录构建 PARTIAL_FAILED/FAILED。

        Returns: {candidate_id: WritebackResult}（未开始写回的 candidate → None）
        """
        ...

    # ============= M4: write_term_to_usl（术语主表原子写） =============
    def write_term_to_usl(self, wb: WritebackPayload, *,
                          domain_id: str, created_by: str,
                          disposition_overwrite: bool = False) -> str:
        """M4: 写入/幂等合并 usl_terms。
        若 domain 内已有相同 normalized_name → disposition_overwrite=False → 合并 synonyms 等并返回既有 term_id；
        disposition_overwrite=True → 以 candidate 的 proposed_name/description 覆盖 USL 现有字段。

        Returns: usl_terms.id（新创建或复用的 ID）
        """
        ...

    # ============= M5: write_synonyms_to_usl（术语同义词原子写） =============
    def write_synonyms_to_usl(self, usl_term_id: str, wb: WritebackPayload, *,
                              disposition: SynonymDisposition) -> list[str]:
        """M5: 批量写 usl_term_synonyms（synonym_type = alias/abbreviation/stopword/ambiguous 等）。
        UNIQUE 冲突按 disposition 处理；返回全部写入/复用的 synonym row id 列表。
        """
        ...

    # ============= M6: write_hierarchy_to_usl（层级边原子写） =============
    def write_hierarchy_to_usl(self, usl_term_id: str, wb: WritebackPayload, *,
                               created_by: str,
                               detect_cycle: bool = True) -> list[str]:
        """M6: 写 usl_term_hierarchies。parent_term_ids 若是 candidate_id → 先查已写回的对应 usl_term_id 再连线；
        detect_cycle=True → 写前调 usl_manager.detect_hierarchy_cycle 环检测 → 有环抛错。
        Returns: 新建 hierarchy id 列表。
        """
        ...

    # ============= M7: write_properties_to_usl（属性规范原子写） =============
    def write_properties_to_usl(self, usl_term_id: str, wb: WritebackPayload) -> list[str]:
        """M7: 写 usl_term_properties（WB 中 property_specs 数组逐项写）。
        UNIQUE(term_id, property_code) → ON CONFLICT DO UPDATE（覆盖 datatype/required/enum_values...）
        """
        ...

    # ============= M8: _update_statuses（内部：更新 schema_candidates.lifecycle_status + pipeline_runs 计数） =============
    def _update_statuses(self, candidate_id: str, *,
                         new_status: CandidateLifecycleStatus,
                         result: WritebackResult,
                         pipeline_run_id: Optional[str]) -> None:
        """M8（内部，对外作为流程步骤）：写回后更新两张运行表状态。
            - schema_candidates: 写入 merged_into_term_id / written_back_at / lifecycle_status / payload._writeback_meta
            - pipeline_runs: writeback_written_count++ 或 writeback_failed_count++
        由 write_approved/write_rejected 内部调用；对外不单独暴露。
        """
        ...

    # ============= M9: _neo4j_finalize_switch（内部：Neo4j USL__Candidate → USL__Term 原子切换 + 删除 DRAFT 边） =============
    def _neo4j_finalize_switch(self, candidate_id: str, usl_term_id: str, *,
                               success: bool,
                               reject_purge: bool = False) -> None:
        """M9（内部）：对应 data-model.md §3 2.6 原子切换 Cypher 片段。
        success=True:
            DELETE USL__IS_A_DRAFT → MERGE (t:USL__Term {id=usl_term_id}) SET t.* ← candidate.*
              → L2 边迁移到 t → DETACH DELETE candidate。
        success=False 且 reject_purge=True：
            MATCH (c:USL__Candidate {id}) DETACH DELETE（或打 USL__Rejected 标签，供审计查询）。
        """
        ...
```

---

## Section 2: 9 方法速查表 + 幂等性

| # | 方法 | 对 candidate 的效果 | 幂等策略 | 失败策略 |
|---|------|--------------------|---------|---------|
| M1 | `write_approved(id)` | 写入 USL + Ontology TBox → MERGED_INTO_USL | idempotency_key = `wb-{id}-v{row_version}`，已写入 → 直接返回 | TBox 瞬错保留 USL，入重试队列 |
| M2 | `write_rejected(id, reason)` | STOPLISTED + 清理 Neo4j | 重复调用：状态已是 STOPLISTED → OK（只确保同义词 in stoplist） | 不抛错 |
| M3 | `writeback_status(ids)` | 只读 | — | — |
| M4 | `write_term_to_usl(wb, did)` | UPSERT usl_terms | UNIQUE(domain, normalized_name) 合并/覆盖 | 数据错误直接抛 |
| M5 | `write_synonyms_to_usl(tid, wb, disp)` | UPSERT usl_term_synonyms | UNIQUE(term_id, norm_syn, type, lang) + disposition | 单条坏数据不影响整体（收集到 warnings） |
| M6 | `write_hierarchy_to_usl(tid, wb)` | INSERT usl_term_hierarchies | UNIQUE(parent, child, type) 跳过 | 有环 → 整条报错；单个 parent 缺失 → warning 跳过 |
| M7 | `write_properties_to_usl(tid, wb)` | UPSERT usl_term_properties | UNIQUE(term_id, property_code) 更新 | enum_values 非法 → 单个 property 跳过 + warning |
| M8 | `_update_statuses(id, new_status, res, run_id)` | UPDATE schema_candidates + pipeline_runs | row_version 条件更新；并发冲突 → 重试一次 | SQLite 约束错误 → 抛（主流程回滚） |
| M9 | `_neo4j_finalize_switch(cand_id, usl_id, ok, purge)` | 切换 Neo4j 节点/边 | MERGE / DETACH DELETE 幂等 | 网络瞬错 → retryable=True + 告警 |

**写回顺序严格约束**（避免孤儿数据）：
`M4 term → M5 synonym → M6 hierarchy → M7 property → M8 statuses → M9 neo4j switch`
