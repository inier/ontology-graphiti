"""Candidate Store SQLite 实现（严格对齐 specs/007-semantic-admin-suite/data-model.md §2）。

5+1 Pipeline 表（§2.1~§2.5 + audit_logs）：
  1. usl_pipeline_runs          — 流水线运行记录（10 状态英文大写枚举）
  2. usl_schema_candidates      — Schema 候选核心表（10+ 状态状态机）
  3. usl_pipeline_layer_snapshots — 层间快照（L1~L6 input/output/duration）
  4. usl_quality_reports        — 三关质量闸报告（G1×7 / G2×4 / G3×5，tier HIGH/MEDIUM/LOW/VERY_LOW）
  5. usl_approval_records       — 2 级审批流水（APPROVE/REJECT/MODIFY/COMMENT 动作）
  6. audit_logs                 — 全链路事件审计（保留）

AGENTS.md §C SQLite 存储规则：
  - 每次操作 sqlite3.connect() → 用完 conn.close()（无连接池）
  - Dict/List → JSON TEXT；Enum → .value 字符串；datetime → ISO 字符串
  - JSON 字段读取时同时兼容 xxx（旧）和 xxx_json（新 spec）两种列名
  - 写入时**永远写新列名**（xxx_json），向前兼容旧 DB 中已有数据
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ======================================================================
# 阶段 A2：枚举统一（全文件所有常量改英文大写）
# ======================================================================

# ---- PipelineStatus 枚举（10 状态） ----
PIPELINE_DRAFT     = "DRAFT"
PIPELINE_RUNNING   = "RUNNING"
PIPELINE_L1_DONE   = "L1_DONE"
PIPELINE_L2_DONE   = "L2_DONE"
PIPELINE_L3_DONE   = "L3_DONE"
PIPELINE_L4_DONE   = "L4_DONE"
PIPELINE_L5_DONE   = "L5_DONE"
PIPELINE_L6_DONE   = "L6_DONE"
PIPELINE_FAILED    = "FAILED"
PIPELINE_COMPLETED = "COMPLETED"

# 兼容别名：旧 RUN_* 常量 → 新枚举（旧代码/测试不立即爆炸）
RUN_PENDING   = PIPELINE_DRAFT       # 旧 pending → DRAFT
RUN_RUNNING   = PIPELINE_RUNNING     # 旧 running → RUNNING
RUN_SUCCEEDED = PIPELINE_COMPLETED   # 旧 succeeded → COMPLETED
RUN_FAILED    = PIPELINE_FAILED      # 旧 failed → FAILED

# ---- CandidateStatus 枚举（12 状态，严格对齐 spec §5 状态机图） ----
CAND_DRAFT              = "DRAFT"
CAND_L1_DONE            = "L1_DONE"
CAND_L2_DONE            = "L2_DONE"
CAND_PENDING_REVIEW     = "PENDING_REVIEW"
CAND_AUDITOR_APPROVED   = "AUDITOR_APPROVED"
CAND_AUDITOR_REJECTED   = "AUDITOR_REJECTED"
CAND_AUDITOR_MODIFIED   = "AUDITOR_MODIFIED"
CAND_ADMIN_PENDING      = "ADMIN_PENDING"
CAND_APPROVED           = "APPROVED"
CAND_REJECTED           = "REJECTED"
CAND_WRITTEN_BACK       = "WRITTEN_BACK"
CAND_STOPLISTED         = "STOPLISTED"

# 短别名（spec §5 直接名，代码里更常引用）
DRAFT            = CAND_DRAFT
QUALITY_GATED    = "QUALITY_GATED"   # 额外：经过 quality_gate 但未评审
PENDING_REVIEW   = CAND_PENDING_REVIEW
AUDITOR_APPROVED = CAND_AUDITOR_APPROVED
AUDITOR_REJECTED = CAND_AUDITOR_REJECTED
AUDITOR_MODIFIED = CAND_AUDITOR_MODIFIED
ADMIN_PENDING    = CAND_ADMIN_PENDING
ADMIN_APPROVED   = CAND_APPROVED    # 最终态：管理员审批通过 → APPROVED
ADMIN_REJECTED   = "ADMIN_REJECTED"   # 额外：管理员驳回
APPROVED         = CAND_APPROVED
REJECTED         = CAND_REJECTED
WRITTEN_BACK     = CAND_WRITTEN_BACK
STOPLISTED       = CAND_STOPLISTED
ARCHIVED         = "ARCHIVED"         # 额外：归档

# 旧 9 状态别名 → 映射到新状态机（保持测试 & 上游代码兼容）
CAND_NEW      = CAND_DRAFT             # 旧 "new" → DRAFT
CAND_GATED    = CAND_PENDING_REVIEW    # 旧 "gated" → PENDING_REVIEW
CAND_WRITTEN  = CAND_WRITTEN_BACK      # 旧 "written" → WRITTEN_BACK

# ---- CandidateOrigin 枚举 ----
ORIGIN_USL    = "usl"
ORIGIN_LLM    = "llm"
ORIGIN_HYBRID = "hybrid"
ORIGIN_HUMAN  = "human"

# ---- QualityTier 枚举（替代 grade A/B/C/D，按 §4.2 阈值） ----
TIER_HIGH     = "HIGH"        # ≥ 0.85
TIER_MEDIUM   = "MEDIUM"      # [0.70, 0.85)
TIER_LOW      = "LOW"         # [0.50, 0.70)
TIER_VERY_LOW = "VERY_LOW"    # < 0.50

# ---- ApprovalAction 枚举 ----
ACTION_APPROVE   = "APPROVE"
ACTION_REJECT    = "REJECT"
ACTION_MODIFY    = "MODIFY"
ACTION_COMMENT   = "COMMENT"
ACTION_RETURN    = "RETURN_BACK"
ACTION_ESCALATE  = "ESCALATE"

# 短别名（流水表 action 值，直接用大写英）
APPROVE     = ACTION_APPROVE
REJECT      = ACTION_REJECT
MODIFY      = ACTION_MODIFY
COMMENT     = ACTION_COMMENT
RETURN_BACK = ACTION_RETURN
ESCALATE    = ACTION_ESCALATE

# ---- Approval task status（旧枚举，流水表不再用 task 状态机，但保留作 wrapper 兼容） ----
APPR_PENDING  = "pending"
APPR_APPROVED = "approved"
APPR_REJECTED = "rejected"

# ---- Quality grade（旧枚举，映射 tier） ----
GRADE_A = "A"  # → HIGH
GRADE_B = "B"  # → MEDIUM
GRADE_C = "C"  # → LOW
GRADE_D = "D"  # → VERY_LOW


# ======================================================================
# 合法 SemanticType（spec §1.2 脚注 + G1.3 枚举）
# ======================================================================
VALID_SEMANTIC_TYPES = {
    "对象类型", "关系类型", "属性", "动作类型", "过程类型", "规则类型",
}


class SQLiteCandidateStorage:
    """Candidate Store SQLite 存储实现。

    每实例一个 db_path；默认 DATA_DIR/candidate_store.db
    """

    # 暴露枚举给外部
    PIPELINE_DRAFT     = PIPELINE_DRAFT
    PIPELINE_RUNNING   = PIPELINE_RUNNING
    PIPELINE_L1_DONE   = PIPELINE_L1_DONE
    PIPELINE_L2_DONE   = PIPELINE_L2_DONE
    PIPELINE_L3_DONE   = PIPELINE_L3_DONE
    PIPELINE_L4_DONE   = PIPELINE_L4_DONE
    PIPELINE_L5_DONE   = PIPELINE_L5_DONE
    PIPELINE_L6_DONE   = PIPELINE_L6_DONE
    PIPELINE_FAILED    = PIPELINE_FAILED
    PIPELINE_COMPLETED = PIPELINE_COMPLETED

    RUN_PENDING   = RUN_PENDING
    RUN_RUNNING   = RUN_RUNNING
    RUN_SUCCEEDED = RUN_SUCCEEDED
    RUN_FAILED    = RUN_FAILED

    CAND_DRAFT            = CAND_DRAFT
    CAND_L1_DONE          = CAND_L1_DONE
    CAND_L2_DONE          = CAND_L2_DONE
    CAND_PENDING_REVIEW   = CAND_PENDING_REVIEW
    CAND_AUDITOR_APPROVED = CAND_AUDITOR_APPROVED
    CAND_AUDITOR_REJECTED = CAND_AUDITOR_REJECTED
    CAND_AUDITOR_MODIFIED = CAND_AUDITOR_MODIFIED
    CAND_ADMIN_PENDING    = CAND_ADMIN_PENDING
    CAND_APPROVED         = CAND_APPROVED
    CAND_REJECTED         = CAND_REJECTED
    CAND_WRITTEN_BACK     = CAND_WRITTEN_BACK
    CAND_STOPLISTED       = CAND_STOPLISTED

    CAND_NEW      = CAND_NEW
    CAND_GATED    = CAND_GATED
    CAND_APPROVED = CAND_APPROVED
    CAND_REJECTED = CAND_REJECTED
    CAND_WRITTEN  = CAND_WRITTEN
    CAND_AUDITOR_APPROVED = CAND_AUDITOR_APPROVED
    CAND_ADMIN_PENDING    = CAND_ADMIN_PENDING
    CAND_WRITTEN_BACK     = CAND_WRITTEN_BACK
    CAND_STOPLISTED       = CAND_STOPLISTED

    APPR_PENDING  = APPR_PENDING
    APPR_APPROVED = APPR_APPROVED
    APPR_REJECTED = APPR_REJECTED

    GRADE_A = GRADE_A
    GRADE_B = GRADE_B
    GRADE_C = GRADE_C
    GRADE_D = GRADE_D

    ORIGIN_USL    = ORIGIN_USL
    ORIGIN_LLM    = ORIGIN_LLM
    ORIGIN_HYBRID = ORIGIN_HYBRID
    ORIGIN_HUMAN  = ORIGIN_HUMAN

    TIER_HIGH     = TIER_HIGH
    TIER_MEDIUM   = TIER_MEDIUM
    TIER_LOW      = TIER_LOW
    TIER_VERY_LOW = TIER_VERY_LOW

    ACTION_APPROVE = ACTION_APPROVE
    ACTION_REJECT  = ACTION_REJECT
    ACTION_MODIFY  = ACTION_MODIFY
    ACTION_COMMENT = ACTION_COMMENT

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            self.db_path = os.path.join(
                os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
                "candidate_store.db",
            )
        else:
            self.db_path = db_path
        # :memory: 或临时空路径时跳过 makedirs（dirname 为空）
        parent_dir = os.path.dirname(self.db_path)
        if parent_dir and self.db_path != ":memory:":
            os.makedirs(parent_dir, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # 向后兼容：旧枚举值 → 新枚举值（A2 统一阶段的输入兼容层）
    # 保留旧值是为了让服务层和已有代码在过渡期无需立即重写，不会炸
    # ------------------------------------------------------------------
    _RUN_STATUS_COMPAT = {
        # 小写旧值 → 大写新值
        "pending":   PIPELINE_DRAFT,
        "draft":     PIPELINE_DRAFT,
        "running":   PIPELINE_RUNNING,
        "succeeded": PIPELINE_COMPLETED,
        "completed": PIPELINE_COMPLETED,
        "success":   PIPELINE_COMPLETED,
        "failed":    PIPELINE_FAILED,
        "error":     PIPELINE_FAILED,
        # L1~L6 旧值
        "layer_1_done": PIPELINE_L1_DONE,
        "layer_2_done": PIPELINE_L2_DONE,
        "layer_3_done": PIPELINE_L3_DONE,
        "layer_4_done": PIPELINE_L4_DONE,
        "layer_5_done": PIPELINE_L5_DONE,
        "layer_6_done": PIPELINE_L6_DONE,
    }

    _CAND_STATUS_COMPAT = {
        "new":              DRAFT,
        "gated":            QUALITY_GATED,
        "quality_gated":      QUALITY_GATED,
        "pending":          PENDING_REVIEW,
        "pending_review":   PENDING_REVIEW,
        "review_pending":   PENDING_REVIEW,
        "auditor_pending":  PENDING_REVIEW,
        "approved":         APPROVED,
        "admin_approved":    ADMIN_APPROVED,
        "final_approved":   ADMIN_APPROVED,
        "auditor_approved": AUDITOR_APPROVED,
        "admin_pending":    ADMIN_PENDING,
        "rejected":         REJECTED,
        "auditor_rejected": AUDITOR_REJECTED,
        "stoplisted":       STOPLISTED,
    }

    _APPR_STATUS_COMPAT = {
        "pending":  APPR_PENDING,
        "approved": APPR_APPROVED,
        "rejected": APPR_REJECTED,
    }

    _APPR_ACTION_COMPAT = {
        "approve": APPROVE,
        "reject":  REJECT,
        "modify":  MODIFY,
        "comment": COMMENT,
        "return_back": RETURN_BACK,
        "escalate": ESCALATE,
    }

    # ----- 新枚举 → 旧枚举（反查，出参时翻译） -----
    _CAND_STATUS_NEW_TO_LEGACY = {
        DRAFT:              "new",
        QUALITY_GATED:      "gated",
        PENDING_REVIEW:     "pending",
        AUDITOR_APPROVED:   "auditor_approved",
        ADMIN_PENDING:      "admin_pending",
        ADMIN_APPROVED:     "approved",
        APPROVED:           "approved",
        AUDITOR_REJECTED:   "rejected",
        ADMIN_REJECTED:     "rejected",
        REJECTED:           "rejected",
        WRITTEN_BACK:       "written_back",
        STOPLISTED:         "stoplisted",
        ARCHIVED:           "archived",
    }

    @classmethod
    def _legacy_status(cls, s: Optional[str]) -> str:
        """把新枚举翻译为旧枚举对外暴露。如果不认识就原样返回。"""
        if s is None:
            return "new"
        return cls._CAND_STATUS_NEW_TO_LEGACY.get(s, str(s))

    @classmethod
    def _norm_run_status(cls, s: Optional[str]) -> str:
        if s is None:
            return PIPELINE_DRAFT
        s2 = str(s)
        lower = s2.lower().replace("-", "_")
        if lower in cls._RUN_STATUS_COMPAT:
            return cls._RUN_STATUS_COMPAT[lower]
        up = s2.upper().replace("-", "_")
        if up in set(cls._RUN_STATUS_COMPAT.values()):
            return up
        return s2

    @classmethod
    def _norm_cand_status(cls, s: Optional[str]) -> str:
        if s is None:
            return DRAFT
        s2 = str(s)
        lower = s2.lower().replace("-", "_")
        if lower in cls._CAND_STATUS_COMPAT:
            return cls._CAND_STATUS_COMPAT[lower]
        up = s2.upper().replace("-", "_")
        if up in set(cls._CAND_STATUS_COMPAT.values()):
            return up
        return s2

    @classmethod
    def _norm_appr_status(cls, s: Optional[str]) -> str:
        if s is None: return APPR_PENDING
        s2 = str(s)
        lower = s2.lower()
        if lower in cls._APPR_STATUS_COMPAT:
            return cls._APPR_STATUS_COMPAT[lower]
        up = s2.upper()
        if up in cls._APPR_STATUS_COMPAT.values():
            return up
        return s2

    @classmethod
    def _norm_appr_action(cls, s: Optional[str]) -> str:
        if s is None: return COMMENT
        s2 = str(s) if not isinstance(s, str) else s
        lower = s2.lower().replace("-", "_")
        if lower in cls._APPR_ACTION_COMPAT:
            return cls._APPR_ACTION_COMPAT[lower]
        up = s2.upper().replace("-", "_")
        if up in cls._APPR_ACTION_COMPAT.values():
            return up
        return s2

    @classmethod
    def _norm_origin(cls, o: Optional[str]) -> str:
        if o is None: return ORIGIN_HYBRID
        o2 = str(o).strip().lower()
        if o2 in ("人工", "human", "人工标注"): return ORIGIN_HUMAN
        if o2 in ("usl", "schema", "schema库"): return ORIGIN_USL
        if o2 in ("llm", "大模型", "llm生成", "ai"): return ORIGIN_LLM
        if o2 in ("hybrid", "混合", "llm+人工"): return ORIGIN_HYBRID
        return o2

    @classmethod
    def _norm_tier(cls, t: Optional[str]) -> str:
        if t is None: return TIER_LOW
        t2 = str(t).strip().upper()
        mapping = {
            "A": TIER_HIGH, "S": TIER_HIGH, "HIGH": TIER_HIGH,
            "B": TIER_MEDIUM, "MEDIUM": TIER_MEDIUM, "MID": TIER_MEDIUM,
            "C": TIER_LOW, "LOW": TIER_LOW,
            "D": TIER_VERY_LOW, "VERY_LOW": TIER_VERY_LOW, "VL": TIER_VERY_LOW, "BAD": TIER_VERY_LOW,
        }
        return mapping.get(t2, t2)

    # ------------------------------------------------------------------
    # 初始化（CREATE TABLE IF NOT EXISTS + 索引 + 迁移旧列）
    # ------------------------------------------------------------------
    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.executescript(
                """
                -- §2.1 usl_pipeline_runs（DDL 严格抄 data-model.md §2.1 + 扩展字段）
                CREATE TABLE IF NOT EXISTS usl_pipeline_runs (
                    id TEXT PRIMARY KEY,
                    domain_id TEXT,
                    workspace_id TEXT NOT NULL,
                    doc_sources_json TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'DRAFT',
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    error_message TEXT,
                    stats_json TEXT NOT NULL DEFAULT '{}',
                    -- 扩展字段（spec 无但有用，保留）
                    ontology_id TEXT,
                    source_type TEXT DEFAULT 'natural_language',
                    source_ref TEXT,
                    triggered_by TEXT,
                    progress INTEGER DEFAULT 0,
                    total_input_chars INTEGER DEFAULT 0,
                    total_output_candidates INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pipeline_runs_workspace
                    ON usl_pipeline_runs(workspace_id);
                CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status
                    ON usl_pipeline_runs(status);
                CREATE INDEX IF NOT EXISTS idx_pipeline_runs_domain
                    ON usl_pipeline_runs(domain_id);

                -- §2.2 usl_schema_candidates（严格抄 §2.2 DDL + 扩展字段）
                CREATE TABLE IF NOT EXISTS usl_schema_candidates (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES usl_pipeline_runs(id) ON DELETE CASCADE,
                    canonical TEXT NOT NULL,
                    en TEXT NOT NULL DEFAULT '',
                    semantic_type TEXT NOT NULL,
                    synonyms_json TEXT NOT NULL DEFAULT '[]',
                    aliases_json TEXT NOT NULL DEFAULT '[]',
                    origin TEXT NOT NULL DEFAULT 'hybrid',
                    cluster_confidence REAL NOT NULL DEFAULT 0,
                    usl_align_confidence REAL NOT NULL DEFAULT 0,
                    review_confidence REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'DRAFT',
                    domain_id TEXT,
                    doc_refs_json TEXT NOT NULL DEFAULT '[]',
                    parent_candidates_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    -- 扩展字段（旧 ol_candidates 字段，保留作兼容）
                    near_synonyms_json TEXT NOT NULL DEFAULT '[]',
                    definition TEXT,
                    examples_json TEXT NOT NULL DEFAULT '[]',
                    stoplist_flag INTEGER NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL DEFAULT 0,
                    source_text TEXT,
                    provenance_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_cand_run      ON usl_schema_candidates(run_id);
                CREATE INDEX IF NOT EXISTS idx_cand_status   ON usl_schema_candidates(status);
                CREATE INDEX IF NOT EXISTS idx_cand_sem_type ON usl_schema_candidates(semantic_type);
                CREATE INDEX IF NOT EXISTS idx_cand_domain   ON usl_schema_candidates(domain_id);

                -- §2.3 usl_pipeline_layer_snapshots（新增）
                CREATE TABLE IF NOT EXISTS usl_pipeline_layer_snapshots (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES usl_pipeline_runs(id) ON DELETE CASCADE,
                    layer_name TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_snap_run ON usl_pipeline_layer_snapshots(run_id);
                CREATE INDEX IF NOT EXISTS idx_snap_layer ON usl_pipeline_layer_snapshots(layer_name);

                -- §2.4 usl_quality_reports（严格抄 §2.4 DDL，废除 grade/A/B/C/D）
                CREATE TABLE IF NOT EXISTS usl_quality_reports (
                    id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL REFERENCES usl_schema_candidates(id) ON DELETE CASCADE,
                    gate1_score REAL NOT NULL,
                    gate1_details TEXT NOT NULL,
                    gate2_score REAL NOT NULL,
                    gate2_details TEXT NOT NULL,
                    gate3_score REAL NOT NULL,
                    gate3_details TEXT NOT NULL,
                    total_score REAL NOT NULL,
                    tier TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_qr_cand  ON usl_quality_reports(candidate_id);
                CREATE INDEX IF NOT EXISTS idx_qr_tier  ON usl_quality_reports(tier);
                CREATE INDEX IF NOT EXISTS idx_qr_total ON usl_quality_reports(total_score);

                -- §2.5 usl_approval_records（严格抄 §2.5 DDL，流水表不是任务表）
                CREATE TABLE IF NOT EXISTS usl_approval_records (
                    id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL REFERENCES usl_schema_candidates(id) ON DELETE CASCADE,
                    approver_id TEXT NOT NULL,
                    approver_role TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    before_status TEXT NOT NULL,
                    after_status TEXT NOT NULL,
                    review_score REAL,
                    comment TEXT,
                    changes_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_appr_cand ON usl_approval_records(candidate_id);
                CREATE INDEX IF NOT EXISTS idx_appr_user ON usl_approval_records(approver_id);
                CREATE INDEX IF NOT EXISTS idx_appr_role ON usl_approval_records(approver_role);
                CREATE INDEX IF NOT EXISTS idx_appr_ws   ON usl_approval_records(workspace_id);
                CREATE INDEX IF NOT EXISTS idx_appr_act  ON usl_approval_records(action);

                -- audit_logs（保留，字段对齐 spec）
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    pipeline_run_id TEXT,
                    candidate_id TEXT,
                    approval_task_id TEXT,
                    approval_record_id TEXT,
                    action TEXT NOT NULL,
                    actor TEXT,
                    payload TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_logs_candidate ON audit_logs(candidate_id);
                CREATE INDEX IF NOT EXISTS idx_audit_logs_action    ON audit_logs(action);
                CREATE INDEX IF NOT EXISTS idx_audit_logs_run       ON audit_logs(pipeline_run_id);
                """
            )

            # ---------- 迁移：从旧表名 → 新表名（幂等，只做一次） ----------
            self._migrate_old_tables_to_new(cur)

            # ---------- 迁移：补充缺失列（旧 DB 中可能只有部分列） ----------
            for alter_stmt in self._build_missing_column_alters(cur):
                try:
                    cur.execute(alter_stmt)
                except sqlite3.OperationalError:
                    pass  # 列已存在

            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 迁移辅助：旧表名 → 新表名（数据复制 + 删旧表）
    # ------------------------------------------------------------------
    def _migrate_old_tables_to_new(self, cur: sqlite3.Cursor) -> None:
        """若存在 pipeline_runs 旧表，则把数据搬运到 usl_pipeline_runs 新表（幂等）。"""
        # 检查旧表是否存在
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_runs'")
        old_tables_exist = cur.fetchone() is not None
        if not old_tables_exist:
            return

        # 检查新表是否已经有数据（避免重复迁移）
        cur.execute("SELECT COUNT(*) FROM usl_pipeline_runs")
        if cur.fetchone()[0] > 0:
            return  # 已迁移过

        # 1) pipeline_runs → usl_pipeline_runs
        cur.execute("SELECT * FROM pipeline_runs")
        cols = [d[0] for d in cur.description]
        colset = set(cols)
        for row in cur.fetchall():
            r = dict(zip(cols, row))
            now = r.get("started_at") or r.get("created_at") or datetime.now().isoformat()
            cur.execute(
                """INSERT OR IGNORE INTO usl_pipeline_runs (
                    id, domain_id, workspace_id, doc_sources_json, status,
                    started_at, finished_at, error_message, stats_json,
                    ontology_id, source_type, source_ref, triggered_by,
                    progress, total_input_chars, total_output_candidates, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    r.get("id"),
                    r.get("domain_id"),
                    r.get("workspace_id"),
                    r.get("doc_sources_json") or r.get("doc_sources") or "[]",
                    self._map_pipeline_status_legacy(r.get("status") or "pending"),
                    now,
                    r.get("finished_at"),
                    r.get("error_message"),
                    r.get("stats_json") or r.get("stats") or "{}",
                    r.get("ontology_id"),
                    r.get("source_type") or "natural_language",
                    r.get("source_ref"),
                    r.get("triggered_by"),
                    r.get("progress", 0),
                    r.get("total_input_chars", 0),
                    r.get("total_output_candidates"),
                    r.get("created_at") or now,
                ),
            )

        # 2) ol_candidates → usl_schema_candidates
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ol_candidates'")
        if cur.fetchone() is not None:
            cur.execute("SELECT * FROM ol_candidates")
            cols2 = [d[0] for d in cur.description]
            for row in cur.fetchall():
                r = dict(zip(cols2, row))
                now = r.get("created_at") or datetime.now().isoformat()
                cur.execute(
                    """INSERT OR IGNORE INTO usl_schema_candidates (
                        id, run_id, canonical, en, semantic_type,
                        synonyms_json, aliases_json, origin,
                        cluster_confidence, usl_align_confidence, review_confidence,
                        status, domain_id, doc_refs_json, parent_candidates_json,
                        created_at, updated_at,
                        near_synonyms_json, definition, examples_json,
                        stoplist_flag, confidence, source_text, provenance_json
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        r.get("id"),
                        r.get("pipeline_run_id") or r.get("run_id"),
                        r.get("canonical"),
                        r.get("en") or r.get("en_mapping") or "",
                        r.get("semantic_type") or "对象类型",
                        r.get("synonyms_json") or r.get("synonyms") or "[]",
                        r.get("aliases_json") or r.get("aliases") or "[]",
                        r.get("origin") or ORIGIN_HYBRID,
                        float(r.get("cluster_confidence") or 0),
                        float(r.get("usl_align_confidence") or 0),
                        float(r.get("review_confidence") or 0),
                        self._map_candidate_status_legacy(r.get("status") or "new"),
                        r.get("domain_id"),
                        r.get("doc_refs_json") or r.get("doc_refs") or "[]",
                        r.get("parent_candidates_json") or r.get("parent_candidates") or "[]",
                        now,
                        r.get("updated_at") or now,
                        r.get("near_synonyms_json") or r.get("near_synonyms") or "[]",
                        r.get("definition"),
                        r.get("examples_json") or r.get("examples") or "[]",
                        int(r.get("stoplist_flag") or 0),
                        float(r.get("confidence") or 0),
                        r.get("source_text"),
                        r.get("provenance_json") or r.get("provenance") or "{}",
                    ),
                )

        # 3) quality_reports → usl_quality_reports
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quality_reports'")
        if cur.fetchone() is not None:
            cur.execute("SELECT * FROM quality_reports")
            cols3 = [d[0] for d in cur.description]
            for row in cur.fetchall():
                r = dict(zip(cols3, row))
                overall = float(r.get("overall_score") or 0)
                tier = self._score_to_tier(overall)
                now = r.get("created_at") or datetime.now().isoformat()
                extras = {
                    "risk_tags": self._safe_json_list_any(r.get("risk_tags")),
                    "suggestions": self._safe_json_list_any(r.get("suggestions")),
                    "checker": r.get("checker"),
                    "legacy_overall_breakdown": {
                        "novelty_score": r.get("novelty_score"),
                        "completeness_score": r.get("completeness_score"),
                        "orthogonality_score": r.get("orthogonality_score"),
                        "consistency_score": r.get("consistency_score"),
                    },
                }
                g1d = [self._mk_submetric(f"g1_legacy_{i}", 1.0, "legacy migrated", "migrate_rule", None) for i in range(7)]
                g2d = [self._mk_submetric(f"g2_legacy_{i}", 1.0, "legacy migrated", "migrate_rule", None) for i in range(4)]
                g3d = [self._mk_submetric(f"g3_legacy_{i}", 1.0, "legacy migrated", "migrate_rule", None) for i in range(4)]
                g3d.append(self._mk_submetric("g3_legacy_extras", 1.0, "legacy extras", "migrate_rule", None))
                g3d[-1]["extras"] = extras  # type: ignore[assignment]
                cur.execute(
                    """INSERT OR IGNORE INTO usl_quality_reports (
                        id, candidate_id, gate1_score, gate1_details, gate2_score, gate2_details,
                        gate3_score, gate3_details, total_score, tier, created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        r.get("id"),
                        r.get("candidate_id"),
                        overall, json.dumps(g1d, ensure_ascii=False),
                        overall, json.dumps(g2d, ensure_ascii=False),
                        overall, json.dumps(g3d, ensure_ascii=False),
                        overall, tier, now,
                    ),
                )

        # 4) approval_tasks → usl_approval_records（把 task 状态变更翻译成流水）
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='approval_tasks'")
        if cur.fetchone() is not None:
            cur.execute("SELECT * FROM approval_tasks")
            cols4 = [d[0] for d in cur.description]
            for row in cur.fetchall():
                r = dict(zip(cols4, row))
                lvl = int(r.get("level") or 1)
                approver_role = "schema_auditor" if lvl == 1 else "admin"
                st = r.get("status") or "pending"
                if st == "approved":
                    action = ACTION_APPROVE
                    before_status = CAND_PENDING_REVIEW
                    after_status = CAND_AUDITOR_APPROVED if lvl == 1 else CAND_APPROVED
                elif st == "rejected":
                    action = ACTION_REJECT
                    before_status = CAND_PENDING_REVIEW
                    after_status = CAND_AUDITOR_REJECTED if lvl == 1 else CAND_REJECTED
                else:
                    action = ACTION_COMMENT
                    before_status = CAND_PENDING_REVIEW
                    after_status = CAND_PENDING_REVIEW
                cur.execute(
                    """INSERT OR IGNORE INTO usl_approval_records (
                        id, candidate_id, approver_id, approver_role, workspace_id,
                        action, before_status, after_status, review_score, comment,
                        changes_json, created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        r.get("id"),
                        r.get("candidate_id"),
                        r.get("reviewer") or r.get("assignee") or "legacy_approver",
                        approver_role,
                        r.get("workspace_id") or "legacy_ws",
                        action, before_status, after_status,
                        None,
                        r.get("comment"),
                        "{}",
                        r.get("approved_at") or r.get("updated_at") or r.get("created_at") or datetime.now().isoformat(),
                    ),
                )

    @staticmethod
    def _map_pipeline_status_legacy(s: str) -> str:
        return SQLiteCandidateStorage._norm_run_status(s)

    @staticmethod
    def _map_candidate_status_legacy(s: str) -> str:
        return SQLiteCandidateStorage._norm_cand_status(s)

    @staticmethod
    def _score_to_tier(s: float) -> str:
        s = float(s or 0)
        if s >= 0.85: return TIER_HIGH
        if s >= 0.70: return TIER_MEDIUM
        if s >= 0.50: return TIER_LOW
        return TIER_VERY_LOW

    @staticmethod
    def _mk_submetric(submetric: str, score: float, reason: str,
                      rule_name: str, threshold: Optional[float]) -> Dict[str, Any]:
        return {
            "submetric": submetric,
            "score": float(score),
            "reason": reason,
            "rule_name": rule_name,
            "threshold": threshold,
        }

    # ------------------------------------------------------------------
    def _build_missing_column_alters(self, cur: sqlite3.Cursor) -> List[str]:
        """返回 ALTER TABLE 语句，补充新表上可能缺失的列（旧 DB 用了早期 schema）。"""
        alters: List[str] = []
        # 用 PRAGMA 查列，但为简单起见：直接尝试 ALTER，外层 try/except 忽略失败
        # usl_pipeline_runs 扩展列
        for col_def in [
            ("usl_pipeline_runs", "doc_sources_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("usl_pipeline_runs", "domain_id", "TEXT"),
            ("usl_pipeline_runs", "stats_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("usl_schema_candidates", "en", "TEXT NOT NULL DEFAULT ''"),
            ("usl_schema_candidates", "origin", "TEXT NOT NULL DEFAULT 'hybrid'"),
            ("usl_schema_candidates", "cluster_confidence", "REAL NOT NULL DEFAULT 0"),
            ("usl_schema_candidates", "usl_align_confidence", "REAL NOT NULL DEFAULT 0"),
            ("usl_schema_candidates", "review_confidence", "REAL NOT NULL DEFAULT 0"),
            ("usl_schema_candidates", "doc_refs_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("usl_schema_candidates", "parent_candidates_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("usl_schema_candidates", "synonyms_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("usl_schema_candidates", "aliases_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("usl_schema_candidates", "near_synonyms_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("usl_schema_candidates", "examples_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("usl_schema_candidates", "provenance_json", "TEXT NOT NULL DEFAULT '{}'"),
        ]:
            alters.append(f"ALTER TABLE {col_def[0]} ADD COLUMN {col_def[1]} {col_def[2]}")
        return alters

    # ==================================================================
    # 1. Pipeline Runs — create/update/status/stats + get/list
    # ==================================================================
    def create_pipeline_run(
        self,
        *,
        workspace_id: str,
        ontology_id: Optional[str] = None,
        source_type: str = "natural_language",
        source_ref: Optional[str] = None,
        status: Optional[str] = None,
        triggered_by: Optional[str] = None,
        progress: Optional[int] = None,
        total_input_chars: int = 0,
        total_output_candidates: Optional[int] = None,
        error_message: Optional[str] = None,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        created_at: Optional[str] = None,
        id: Optional[str] = None,
        stats: Optional[Dict[str, Any]] = None,
        # 新 spec 字段
        domain_id: Optional[str] = None,
        doc_sources: Optional[List[Dict[str, Any]]] = None,
        stats_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """创建 Pipeline Run。非 workspace_id 字段可选。
        兼容传参：stats / stats_json 都能传入，取并集（stats_json 优先）。"""
        now = datetime.now().isoformat()
        run_id = id or str(uuid.uuid4())
        actual_status = self._map_pipeline_status_legacy(status or RUN_PENDING)
        actual_progress = 0 if progress is None else int(progress)
        actual_created = created_at or now
        actual_started = started_at or now
        merged_stats: Dict[str, Any] = {}
        if stats: merged_stats.update(stats)
        if stats_json: merged_stats.update(stats_json)
        doc_sources_json = json.dumps(doc_sources or [], ensure_ascii=False)
        stats_json_s = json.dumps(merged_stats, ensure_ascii=False)

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO usl_pipeline_runs (
                    id, domain_id, workspace_id, doc_sources_json, status,
                    started_at, finished_at, error_message, stats_json,
                    ontology_id, source_type, source_ref, triggered_by,
                    progress, total_input_chars, total_output_candidates, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id, domain_id, workspace_id, doc_sources_json, actual_status,
                    actual_started, finished_at, error_message, stats_json_s,
                    ontology_id, source_type, source_ref, triggered_by,
                    actual_progress, total_input_chars, total_output_candidates, actual_created,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_pipeline_run(run_id) or {
            "id": run_id, "status": actual_status, "created_at": actual_created,
        }

    def update_pipeline_run_status(
        self,
        run_id: str,
        *,
        status: str,
        progress: Optional[int] = None,
        total_output_candidates: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        now = datetime.now().isoformat()
        actual_status = self._map_pipeline_status_legacy(status)
        fields: List[str] = ["status = ?"]
        values: List[Any] = [actual_status]
        if progress is not None:
            fields.append("progress = ?")
            values.append(progress)
        if total_output_candidates is not None:
            fields.append("total_output_candidates = ?")
            values.append(total_output_candidates)
        if error_message is not None:
            fields.append("error_message = ?")
            values.append(error_message)
        if actual_status in (PIPELINE_COMPLETED, PIPELINE_FAILED):
            fields.append("finished_at = ?")
            values.append(now)
        elif actual_status == PIPELINE_RUNNING:
            fields.append("started_at = COALESCE(started_at, ?)")
            values.append(now)
        values.append(run_id)
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                f"UPDATE usl_pipeline_runs SET {', '.join(fields)} WHERE id = ?", values
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def update_pipeline_run_stats(
        self,
        run_id: str,
        *,
        stats_update: Dict[str, Any],
        merge: bool = True,
    ) -> bool:
        """增量更新 stats_json（与 stats 字段兼容；旧调用传 stats_update 仍生效）。"""
        if stats_update is None:
            return False
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT stats_json FROM usl_pipeline_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if not row:
                # 兼容旧列：若 stats_json 空但 stats 存在 → 读 stats
                row2 = conn.execute(
                    "SELECT stats_json, stats FROM usl_pipeline_runs WHERE id = ?", (run_id,)
                ).fetchone()
                if not row2:
                    return False
                raw = row2["stats_json"] or row2["stats"] or "{}"
            else:
                raw = row["stats_json"] or "{}"
            if merge:
                try:
                    prev = json.loads(raw) if raw else {}
                    if not isinstance(prev, dict): prev = {}
                except (json.JSONDecodeError, ValueError, TypeError):
                    prev = {}
                merged: Dict[str, Any] = dict(prev)
                for k, v in stats_update.items():
                    if (
                        isinstance(v, int) and not isinstance(v, bool)
                        and isinstance(merged.get(k), int) and not isinstance(merged.get(k), bool)
                    ):
                        merged[k] = merged[k] + v
                    else:
                        merged[k] = v
                final_stats = merged
            else:
                final_stats = dict(stats_update)
            stats_json = json.dumps(final_stats, ensure_ascii=False)
            cur = conn.execute(
                "UPDATE usl_pipeline_runs SET stats_json = ? WHERE id = ?",
                (stats_json, run_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def get_pipeline_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM usl_pipeline_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            # 向前兼容：同时导出 stats（从 stats_json 复制）、doc_sources
            self._deserialize_run(data)
            return data
        finally:
            conn.close()

    def list_pipeline_runs(
        self,
        *,
        workspace_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        domain_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        conds: List[str] = []
        args: List[Any] = []
        if workspace_id:
            conds.append("workspace_id = ?")
            args.append(workspace_id)
        if status:
            conds.append("status = ?")
            args.append(self._map_pipeline_status_legacy(status))
        if domain_id:
            conds.append("domain_id = ?")
            args.append(domain_id)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM usl_pipeline_runs {where}", args
            ).fetchone()[0]
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"SELECT * FROM usl_pipeline_runs {where} "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                args + [page_size, offset],
            ).fetchall()
            items: List[Dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                self._deserialize_run(d)
                items.append(d)
            return {"items": items, "total": total,
                    "page": page, "page_size": page_size}
        finally:
            conn.close()

    # ------------------------------------------------------------------
    @classmethod
    def _deserialize_run(cls, data: Dict[str, Any]) -> None:
        """向前兼容：stats / stats_json / doc_sources / doc_sources_json 两种命名同时读出。"""
        # doc_sources
        raw = data.get("doc_sources_json") or data.get("doc_sources")
        data["doc_sources_json"] = cls._safe_json_list_any(raw)
        data["doc_sources"] = data["doc_sources_json"]  # 兼容旧命名
        # stats
        raw2 = data.get("stats_json") or data.get("stats")
        data["stats_json"] = cls._safe_json_dict_any(raw2)
        data["stats"] = data["stats_json"]  # 兼容旧命名

    # ==================================================================
    # 1b. Pipeline Layer Snapshots（CRUD：新增）
    # ==================================================================
    def save_snapshot(
        self,
        *,
        run_id: str,
        layer_name: str,
        input_data: Any,
        output_data: Any,
        duration_ms: int,
        created_at: Optional[str] = None,
        id: Optional[str] = None,
    ) -> Dict[str, Any]:
        snap_id = id or str(uuid.uuid4())
        now = created_at or datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO usl_pipeline_layer_snapshots (
                    id, run_id, layer_name, input_json, output_json, duration_ms, created_at
                ) VALUES (?,?,?,?,?,?,?)""",
                (
                    snap_id, run_id, layer_name,
                    json.dumps(input_data, ensure_ascii=False),
                    json.dumps(output_data, ensure_ascii=False),
                    int(duration_ms), now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return {
            "id": snap_id, "run_id": run_id, "layer_name": layer_name,
            "duration_ms": int(duration_ms), "created_at": now,
        }

    def get_snapshots_by_run(self, run_id: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM usl_pipeline_layer_snapshots
                   WHERE run_id = ? ORDER BY layer_name, created_at""",
                (run_id,),
            ).fetchall()
            out: List[Dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                d["input_json"] = self._safe_json_any(d.get("input_json"))
                d["output_json"] = self._safe_json_any(d.get("output_json"))
                d["input"] = d["input_json"]  # 便捷别名
                d["output"] = d["output_json"]
                out.append(d)
            return out
        finally:
            conn.close()

    def delete_snapshots_by_run(self, run_id: str) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "DELETE FROM usl_pipeline_layer_snapshots WHERE run_id = ?",
                (run_id,),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    # ==================================================================
    # 2. Schema Candidates — save/bulk + get/list + statusUpdate + delete
    # ==================================================================
    def save_candidate(self, cand: Dict[str, Any]) -> Dict[str, Any]:
        return self.bulk_insert_candidates([cand])[0]

    def bulk_insert_candidates(
        self, candidates: Iterable[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """批量插入（兼容旧字段 pipeline_run_id → run_id，同义词/别名/近同义词/例子/来源 JSON 双重命名）。"""
        now = datetime.now().isoformat()
        cands_out: List[Dict[str, Any]] = []
        for c in candidates:
            run_id = c.get("run_id") or c.get("pipeline_run_id")
            if not run_id:
                raise ValueError("candidate missing run_id/pipeline_run_id")
            synonyms = c.get("synonyms") or c.get("synonyms_json") or []
            if isinstance(synonyms, str):
                synonyms = self._safe_json_list_any(synonyms)
            aliases = c.get("aliases") or c.get("aliases_json") or []
            if isinstance(aliases, str):
                aliases = self._safe_json_list_any(aliases)
            near_synonyms = c.get("near_synonyms") or c.get("near_synonyms_json") or []
            if isinstance(near_synonyms, str):
                near_synonyms = self._safe_json_list_any(near_synonyms)
            examples = c.get("examples") or c.get("examples_json") or []
            if isinstance(examples, str):
                examples = self._safe_json_list_any(examples)
            provenance = c.get("provenance") or c.get("provenance_json") or {}
            if isinstance(provenance, str):
                provenance = self._safe_json_dict_any(provenance)
            doc_refs = c.get("doc_refs") or c.get("doc_refs_json") or []
            if isinstance(doc_refs, str):
                doc_refs = self._safe_json_list_any(doc_refs)
            parent_candidates = (
                c.get("parent_candidates") or c.get("parent_candidates_json") or []
            )
            if isinstance(parent_candidates, str):
                parent_candidates = self._safe_json_list_any(parent_candidates)
            rec: Dict[str, Any] = {
                "id": c.get("id") or str(uuid.uuid4()),
                "run_id": run_id,
                "canonical": c["canonical"],
                "en": c.get("en") or c.get("en_mapping") or "",
                "semantic_type": c.get("semantic_type") or "对象类型",
                "synonyms_json": json.dumps(list(synonyms), ensure_ascii=False),
                "aliases_json":  json.dumps(list(aliases), ensure_ascii=False),
                "origin": c.get("origin") or ORIGIN_HYBRID,
                "cluster_confidence":   float(c.get("cluster_confidence") or 0),
                "usl_align_confidence": float(c.get("usl_align_confidence") or 0),
                "review_confidence":    float(c.get("review_confidence") or 0),
                "status": self._map_candidate_status_legacy(c.get("status") or CAND_DRAFT),
                "domain_id": c.get("domain_id"),
                "doc_refs_json":          json.dumps(list(doc_refs), ensure_ascii=False),
                "parent_candidates_json": json.dumps(list(parent_candidates), ensure_ascii=False),
                "created_at": c.get("created_at") or now,
                "updated_at": now,
                "near_synonyms_json": json.dumps(list(near_synonyms), ensure_ascii=False),
                "definition": c.get("definition"),
                "examples_json":   json.dumps(list(examples), ensure_ascii=False),
                "stoplist_flag": 1 if c.get("stoplist_flag") else 0,
                "confidence": float(c.get("confidence") or 0.0),
                "source_text": c.get("source_text"),
                "provenance_json": json.dumps(dict(provenance), ensure_ascii=False),
            }
            cands_out.append(rec)

        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(
                """INSERT OR REPLACE INTO usl_schema_candidates (
                    id, run_id, canonical, en, semantic_type,
                    synonyms_json, aliases_json, origin,
                    cluster_confidence, usl_align_confidence, review_confidence,
                    status, domain_id, doc_refs_json, parent_candidates_json,
                    created_at, updated_at,
                    near_synonyms_json, definition, examples_json,
                    stoplist_flag, confidence, source_text, provenance_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    (
                        c["id"], c["run_id"], c["canonical"], c["en"], c["semantic_type"],
                        c["synonyms_json"], c["aliases_json"], c["origin"],
                        c["cluster_confidence"], c["usl_align_confidence"], c["review_confidence"],
                        c["status"], c["domain_id"], c["doc_refs_json"], c["parent_candidates_json"],
                        c["created_at"], c["updated_at"],
                        c["near_synonyms_json"], c["definition"], c["examples_json"],
                        c["stoplist_flag"], c["confidence"], c["source_text"], c["provenance_json"],
                    )
                    for c in cands_out
                ],
            )
            conn.commit()
        finally:
            conn.close()

        # 反序列化 JSON → Python，向前兼容导出 pipeline_run_id + 旧命名
        result: List[Dict[str, Any]] = []
        for c in cands_out:
            out = dict(c)
            for kj, ko in [
                ("synonyms_json", "synonyms"),
                ("aliases_json",  "aliases"),
                ("near_synonyms_json", "near_synonyms"),
                ("examples_json", "examples"),
                ("doc_refs_json", "doc_refs"),
                ("parent_candidates_json", "parent_candidates"),
            ]:
                out[kj] = self._safe_json_list_any(c.get(kj))
                out[ko] = out[kj]  # 旧命名
            out["provenance_json"] = self._safe_json_dict_any(c.get("provenance_json"))
            out["provenance"] = out["provenance_json"]
            out["stoplist_flag"] = bool(c["stoplist_flag"])
            out["pipeline_run_id"] = c["run_id"]  # 旧命名兼容
            result.append(out)
        return result

    def get_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM usl_schema_candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
            if not row:
                return None
            d = self._deserialize_candidate_row(dict(row))
            return d
        finally:
            conn.close()

    def list_candidates(
        self,
        *,
        pipeline_run_id: Optional[str] = None,
        run_id: Optional[str] = None,
        domain_id: Optional[str] = None,
        status: Optional[str] = None,
        statuses: Optional[List[str]] = None,
        semantic_type: Optional[str] = None,
        min_confidence: Optional[float] = None,
        page: int = 1,
        page_size: int = 100,
        origin: Optional[str] = None,
        canonical_q: Optional[str] = None,
    ) -> Dict[str, Any]:
        conds: List[str] = []
        args: List[Any] = []
        actual_run_id = run_id or pipeline_run_id
        if actual_run_id:
            conds.append("run_id = ?")
            args.append(actual_run_id)
        if domain_id:
            conds.append("domain_id = ?")
            args.append(domain_id)
        if status:
            conds.append("status = ?")
            args.append(self._map_candidate_status_legacy(status))
        elif statuses:
            cleaned = []
            for s in statuses:
                if not s:
                    continue
                cleaned.append(self._map_candidate_status_legacy(str(s)))
            if cleaned:
                placeholders = ", ".join(["?"] * len(cleaned))
                conds.append(f"status IN ({placeholders})")
                args.extend(cleaned)
        if semantic_type:
            conds.append("semantic_type = ?")
            args.append(semantic_type)
        if min_confidence is not None:
            conds.append("confidence >= ?")
            args.append(min_confidence)
        if origin:
            conds.append("origin = ?")
            args.append(origin)
        if canonical_q:
            conds.append("canonical LIKE ?")
            args.append(f"%{canonical_q}%")
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM usl_schema_candidates {where}", args
            ).fetchone()[0]
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"SELECT * FROM usl_schema_candidates {where} "
                "ORDER BY confidence DESC, created_at DESC LIMIT ? OFFSET ?",
                args + [page_size, offset],
            ).fetchall()
            items: List[Dict[str, Any]] = []
            for r in rows:
                items.append(self._deserialize_candidate_row(dict(r)))
            return {"items": items, "total": total,
                    "page": page, "page_size": page_size}
        finally:
            conn.close()

    def update_candidate_status(
        self, candidate_id: str, status: str, **extra
    ) -> bool:
        """更新 status + 可选扩展字段。status 自动做新旧值映射。"""
        actual_status = self._map_candidate_status_legacy(status)
        fields = ["status = ?", "updated_at = ?"]
        values: List[Any] = [actual_status, datetime.now().isoformat()]
        for k, v in extra.items():
            if k in ("provenance", "provenance_json") and isinstance(v, (dict, list)):
                fields.append("provenance_json = ?")
                values.append(json.dumps(v, ensure_ascii=False))
            elif k == "stoplist_flag":
                fields.append("stoplist_flag = ?")
                values.append(1 if v else 0)
            elif k in ("synonyms", "synonyms_json") and isinstance(v, list):
                fields.append("synonyms_json = ?")
                values.append(json.dumps(v, ensure_ascii=False))
            elif k in ("aliases", "aliases_json") and isinstance(v, list):
                fields.append("aliases_json = ?")
                values.append(json.dumps(v, ensure_ascii=False))
            elif k in ("doc_refs", "doc_refs_json") and isinstance(v, list):
                fields.append("doc_refs_json = ?")
                values.append(json.dumps(v, ensure_ascii=False))
            elif k == "review_confidence":
                fields.append("review_confidence = ?")
                values.append(float(v))
            elif k == "confidence":
                fields.append("confidence = ?")
                values.append(float(v))
            elif k == "cluster_confidence":
                fields.append("cluster_confidence = ?")
                values.append(float(v))
            elif k == "usl_align_confidence":
                fields.append("usl_align_confidence = ?")
                values.append(float(v))
            else:
                fields.append(f"{k} = ?")
                values.append(v)
        values.append(candidate_id)
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                f"UPDATE usl_schema_candidates SET {', '.join(fields)} WHERE id = ?", values
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def delete_candidate(self, candidate_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            # 级联：先删子表（质量/审批/snapshot/audit），再主表
            conn.execute("DELETE FROM usl_quality_reports WHERE candidate_id = ?", (candidate_id,))
            conn.execute("DELETE FROM usl_approval_records WHERE candidate_id = ?", (candidate_id,))
            conn.execute("DELETE FROM audit_logs    WHERE candidate_id = ?", (candidate_id,))
            # snapshots 是 run_id 维度，无需单独删 candidate
            cur = conn.execute("DELETE FROM usl_schema_candidates WHERE id = ?", (candidate_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    @classmethod
    def _deserialize_candidate_row(cls, d: Dict[str, Any]) -> Dict[str, Any]:
        # 读 JSON 字段（同时兼容 xxx / xxx_json 两种列名）
        for kj, ko in [
            ("synonyms_json", "synonyms"),
            ("aliases_json",  "aliases"),
            ("near_synonyms_json", "near_synonyms"),
            ("examples_json", "examples"),
            ("doc_refs_json", "doc_refs"),
            ("parent_candidates_json", "parent_candidates"),
        ]:
            raw = d.get(kj) or d.get(ko)
            val = cls._safe_json_list_any(raw)
            d[kj] = val
            d[ko] = val  # 旧命名
        prov = d.get("provenance_json") or d.get("provenance")
        d["provenance_json"] = cls._safe_json_dict_any(prov)
        d["provenance"] = d["provenance_json"]
        d["stoplist_flag"] = bool(d.get("stoplist_flag"))
        # 兼容旧命名 pipeline_run_id
        d["pipeline_run_id"] = d.get("run_id")
        # en / en_mapping
        if "en_mapping" not in d:
            d["en_mapping"] = d.get("en") or ""
        # 过渡期：DB 内新大写枚举 → 对外暴露旧小写枚举
        d["status"] = cls._legacy_status(d.get("status"))
        return d

    # ==================================================================
    # 3. Quality Reports — save/get/getByCandidate/list (G1×7 / G2×4 / G3×5)
    # ==================================================================
    def save_quality_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """保存三关质量报告。
        兼容：report 中传 grade/risk_tags/suggestions/checker 会被合并进 gate3_details extras。
        兼容：report 中传 overall_score / novelty/completeness/... → 自动映射。"""
        report_id = report.get("id") or str(uuid.uuid4())
        now = report.get("created_at") or datetime.now().isoformat()
        cid = report["candidate_id"]

        # 如果传新字段（gate1/2/3）就用，否则从旧 overall/novelty 等合成
        if "gate1_score" in report and "gate2_score" in report and "gate3_score" in report:
            g1s = float(report["gate1_score"])
            g1d = report.get("gate1_details") or []
            g2s = float(report["gate2_score"])
            g2d = report.get("gate2_details") or []
            g3s = float(report["gate3_score"])
            g3d = report.get("gate3_details") or []
            total = float(report.get("total_score") or (0.35 * g1s + 0.40 * g2s + 0.25 * g3s))
            tier = report.get("tier") or self._score_to_tier(total)
        else:
            total = float(report.get("overall_score") or 0)
            tier = report.get("tier") or self._score_to_tier(total)
            g1s = g2s = g3s = total
            g1d = [self._mk_submetric(f"g1_compat_{i}", 1.0, "compat", "compat_rule", None) for i in range(7)]
            g2d = [self._mk_submetric(f"g2_compat_{i}", 1.0, "compat", "compat_rule", None) for i in range(4)]
            g3d = [self._mk_submetric(f"g3_compat_{i}", 1.0, "compat", "compat_rule", None) for i in range(5)]

        # gate3_details extras：吸收旧字段 risk_tags/suggestions/checker + legacy 分数
        extras: Dict[str, Any] = {}
        if "risk_tags"   in report: extras["risk_tags"]   = list(report["risk_tags"] or [])
        if "suggestions" in report: extras["suggestions"] = list(report["suggestions"] or [])
        if "checker"     in report: extras["checker"]     = report["checker"]
        for k in ("novelty_score", "completeness_score",
                  "orthogonality_score", "consistency_score",
                  "overall_score", "grade"):
            if k in report and report[k] is not None:
                extras[k] = report[k]
        if extras:
            try:
                g3d_list = list(g3d) if isinstance(g3d, (list, tuple)) else self._safe_json_list_any(g3d)
                if not g3d_list:
                    # 空 g3d 时创建一个占位子项挂 extras，保证反序列化时可读回
                    g3d_list.append(self._mk_submetric("g3_extras", 1.0, "compatibility extras", "compat_extras", None))
                if isinstance(g3d_list[-1], dict):
                    prev = g3d_list[-1].get("extras") or {}
                    merged_ex = dict(prev); merged_ex.update(extras)
                    g3d_list[-1]["extras"] = merged_ex
                g3d = g3d_list
            except Exception:
                pass

        g1d_s = g1d if isinstance(g1d, str) else json.dumps(g1d, ensure_ascii=False)
        g2d_s = g2d if isinstance(g2d, str) else json.dumps(g2d, ensure_ascii=False)
        g3d_s = g3d if isinstance(g3d, str) else json.dumps(g3d, ensure_ascii=False)

        conn = sqlite3.connect(self.db_path)
        try:
            # ⭐ UPSERT 语义：先 DELETE 同 candidate_id 的旧行，再 INSERT
            #    （DDL 可能缺少 UNIQUE(candidate_id) 迁移，DELETE+INSERT 更稳）
            conn.execute("DELETE FROM usl_quality_reports WHERE candidate_id = ?", (cid,))
            new_id = report.get("id") or report_id or str(uuid.uuid4())
            conn.execute(
                """INSERT INTO usl_quality_reports (
                    id, candidate_id, gate1_score, gate1_details, gate2_score, gate2_details,
                    gate3_score, gate3_details, total_score, tier, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    new_id, cid,
                    g1s, g1d_s,
                    g2s, g2d_s,
                    g3s, g3d_s,
                    float(total), tier, now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_quality_report(new_id) or {"id": new_id, "candidate_id": cid}

    def get_quality_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM usl_quality_reports WHERE id = ?", (report_id,)
            ).fetchone()
            if not row:
                return None
            d = self._deserialize_quality_report(dict(row))
            return d
        finally:
            conn.close()

    def get_quality_report_by_candidate(
        self, candidate_id: str
    ) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM usl_quality_reports WHERE candidate_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (candidate_id,),
            ).fetchone()
            if not row:
                return None
            return self._deserialize_quality_report(dict(row))
        finally:
            conn.close()

    def list_quality_reports(
        self,
        *,
        candidate_id: Optional[str] = None,
        tier: Optional[str] = None,
        total_ge: Optional[float] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        conds: List[str] = []
        args: List[Any] = []
        if candidate_id:
            conds.append("candidate_id = ?")
            args.append(candidate_id)
        if tier:
            conds.append("tier = ?")
            args.append(tier)
        if total_ge is not None:
            conds.append("total_score >= ?")
            args.append(float(total_ge))
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM usl_quality_reports {where}", args
            ).fetchone()[0]
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"SELECT * FROM usl_quality_reports {where} "
                "ORDER BY total_score DESC, created_at DESC LIMIT ? OFFSET ?",
                args + [page_size, offset],
            ).fetchall()
            items = [self._deserialize_quality_report(dict(r)) for r in rows]
            return {"items": items, "total": total,
                    "page": page, "page_size": page_size}
        finally:
            conn.close()

    @classmethod
    def _deserialize_quality_report(cls, d: Dict[str, Any]) -> Dict[str, Any]:
        for k in ("gate1_details", "gate2_details", "gate3_details"):
            raw = d.get(k)
            if isinstance(raw, str):
                d[k] = cls._safe_json_list_any(raw)
        # 先从 gate3_details[-1].extras 取出所有兼容字段（包括 grade、legacy scores）
        ex: Dict[str, Any] = {}
        try:
            g3d = d.get("gate3_details") or []
            if isinstance(g3d, list) and g3d and isinstance(g3d[-1], dict):
                ex = dict(g3d[-1].get("extras") or {})
        except Exception:
            ex = {}
        # 展开 extras（risk_tags/suggestions/checker/grade/legacy scores）
        if "risk_tags"   in ex and "risk_tags"   not in d: d["risk_tags"]   = list(ex["risk_tags"])
        if "suggestions" in ex and "suggestions" not in d: d["suggestions"] = list(ex["suggestions"])
        if "checker"     in ex and "checker"     not in d: d["checker"]     = ex["checker"]
        for k in ("novelty_score", "completeness_score",
                  "orthogonality_score", "consistency_score"):
            if k in ex and k not in d: d[k] = ex[k]
        # overall_score 兼容：extras 优先 → 其次 total_score
        d["overall_score"] = ex.get("overall_score") if ex.get("overall_score") is not None else d.get("total_score")
        # grade：先看 extras（用户写入）→ 再按 tier 推导
        tier = d.get("tier") or ""
        if "grade" in ex and ex["grade"]:
            d["grade"] = ex["grade"]
        else:
            grade_map = {TIER_HIGH: "A", TIER_MEDIUM: "B", TIER_LOW: "C", TIER_VERY_LOW: "D"}
            d["grade"] = grade_map.get(tier, "C")
        return d

    # ==================================================================
    # 4. Approval Records（流水表 API — 阶段 A4 核心）
    # ==================================================================
    def save_approval_log(self, log: Dict[str, Any]) -> Dict[str, Any]:
        """旧接口兼容：ApprovalService 旧路径调用 save_approval_log。

        内部转 append_approval_record（新接口）。
        入参字段：candidate_id, level, reviewer, decision, comment, changed_fields
        """
        cid = str(log.get("candidate_id") or "")
        cand = self.get_candidate(cid) or {}
        ws_id = str(cand.get("workspace_id") or "unknown_ws")
        level = str(log.get("level") or "")
        _amap = {
            "SUBMIT": "SUBMIT", "L1": "AUDIT", "L2": "FINAL_APPROVE",
            "AUDIT": "AUDIT", "MODIFY": "MODIFY", "REJECT": "REJECT",
        }
        action = _amap.get(level, level or "AUDIT")
        approver_role = "admin" if (level == "L2" or action == "FINAL_APPROVE") else "schema_auditor"
        changed_fields = dict(log.get("changed_fields") or {})
        before_status = ""
        after_status = ""
        if isinstance(changed_fields.get("status"), dict):
            before_status = str(changed_fields["status"].get("from") or "")
            after_status = str(changed_fields["status"].get("to") or before_status)
        if not before_status:
            before_status = str(cand.get("status") or "")
        if not after_status:
            after_status = before_status
        return self.append_approval_record(
            candidate_id=cid,
            approver_id=str(log.get("reviewer") or "system"),
            approver_role=approver_role,
            workspace_id=ws_id,
            action=action,
            before_status=before_status,
            after_status=after_status,
            comment=str(log.get("comment") or ""),
            changes=changed_fields,
        )

    def append_approval_record(
        self,
        *,
        candidate_id: str,
        approver_id: str,
        approver_role: str,
        workspace_id: str,
        action: str,
        before_status: str,
        after_status: str,
        review_score: Optional[float] = None,
        comment: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """写入一条审批流水记录并返回。"""
        rec_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        changes_s = json.dumps(changes or {}, ensure_ascii=False)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO usl_approval_records (
                    id, candidate_id, approver_id, approver_role, workspace_id,
                    action, before_status, after_status, review_score, comment,
                    changes_json, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    rec_id, candidate_id, approver_id, approver_role, workspace_id,
                    (action or "").upper() if action else ACTION_COMMENT,
                    self._map_candidate_status_legacy(before_status),
                    self._map_candidate_status_legacy(after_status),
                    float(review_score) if review_score is not None else None,
                    comment, changes_s, now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return {
            "id": rec_id, "candidate_id": candidate_id,
            "approver_id": approver_id, "approver_role": approver_role,
            "workspace_id": workspace_id, "action": (action or "").upper() if action else ACTION_COMMENT,
            "before_status": self._map_candidate_status_legacy(before_status),
            "after_status": self._map_candidate_status_legacy(after_status),
            "review_score": float(review_score) if review_score is not None else None,
            "comment": comment, "changes": changes or {}, "created_at": now,
        }

    def list_approval_records(
        self,
        *,
        candidate_id: Optional[str] = None,
        approver_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        action: Optional[str] = None,
        approver_role: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        conds: List[str] = []
        args: List[Any] = []
        if candidate_id:
            conds.append("candidate_id = ?")
            args.append(candidate_id)
        if approver_id:
            conds.append("approver_id = ?")
            args.append(approver_id)
        if workspace_id:
            conds.append("workspace_id = ?")
            args.append(workspace_id)
        if action:
            conds.append("action = ?")
            args.append(action.upper() if action else action)
        if approver_role:
            conds.append("approver_role = ?")
            args.append(approver_role)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM usl_approval_records {where}", args
            ).fetchone()[0]
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"SELECT * FROM usl_approval_records {where} "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                args + [page_size, offset],
            ).fetchall()
            items: List[Dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                ch = d.get("changes_json")
                if isinstance(ch, str):
                    try: d["changes"] = json.loads(ch)
                    except Exception: d["changes"] = {}
                else:
                    d["changes"] = ch if isinstance(ch, dict) else {}
                d["changes_json"] = d["changes"]
                items.append(d)
            return {"items": items, "total": total,
                    "page": page, "page_size": page_size}
        finally:
            conn.close()

    # ---------------- 兼容 Wrapper：旧 create_approval_task 等 API ----------------
    def create_approval_task(
        self,
        *,
        candidate_id: str,
        level: int = 1,
        assignee: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """旧审批任务表 API → 内部转流水记录。
        为了让旧代码不爆炸，返回一个带 level/status 的『虚拟 task』dict。"""
        lvl = int(level or 1)
        approver_role = "schema_auditor" if lvl == 1 else "admin"
        # 幂等：若已有该 candidate+level 的 PENDING 流水 COMMENT，直接返回
        page = self.list_approval_records(candidate_id=candidate_id, page_size=100)
        task_id: Optional[str] = None
        for rec in page["items"]:
            # 兼容：找一条 COMMENT 作为创建记录
            if rec.get("action") == ACTION_COMMENT and rec.get("approver_role") == approver_role:
                task_id = rec["id"]
                break
        if task_id is None:
            rec = self.append_approval_record(
                candidate_id=candidate_id,
                approver_id=assignee or "unassigned",
                approver_role=approver_role,
                workspace_id=workspace_id or "unknown_ws",
                action=ACTION_COMMENT,
                before_status=CAND_PENDING_REVIEW,
                after_status=CAND_PENDING_REVIEW,
                comment="task_created",
            )
            task_id = rec["id"]
        return {
            "id": task_id,
            "candidate_id": candidate_id,
            "level": lvl,
            "status": APPR_PENDING,
            "assignee": assignee,
            "reviewer": None,
            "comment": None,
            "approved_at": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    def update_approval_task(
        self,
        task_id: str,
        *,
        status: str,
        reviewer: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> bool:
        """旧 update_approval_task → 转成流水 append（把 task 动作翻译成流水 action）。"""
        st = (status or "").lower()
        # 反查 candidate_id（流水的第一条同 id 记录）
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT candidate_id, approver_role, workspace_id, before_status, after_status "
                "FROM usl_approval_records WHERE id = ? LIMIT 1",
                (task_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return False
        cid = row[0]
        approver_role = row[1] or "schema_auditor"
        ws = row[2] or "unknown_ws"
        before = row[4] or CAND_PENDING_REVIEW
        if st == APPR_APPROVED:
            action = ACTION_APPROVE
            after = (
                CAND_AUDITOR_APPROVED if approver_role == "schema_auditor" else CAND_APPROVED
            )
        elif st == APPR_REJECTED:
            action = ACTION_REJECT
            after = (
                CAND_AUDITOR_REJECTED if approver_role == "schema_auditor" else CAND_REJECTED
            )
        else:
            action = ACTION_COMMENT
            after = before
        self.append_approval_record(
            candidate_id=cid,
            approver_id=reviewer or "unknown",
            approver_role=approver_role,
            workspace_id=ws,
            action=action,
            before_status=before,
            after_status=after,
            comment=comment,
        )
        # 同步更新 candidate 的 status
        if action != ACTION_COMMENT:
            self.update_candidate_status(cid, after)
        return True

    def get_approval_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        # 1) 先查 task_id 对应的流水 → 拿到 candidate_id + approver_role
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM usl_approval_records WHERE id = ? LIMIT 1", (task_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        d0 = dict(row)
        cid = d0.get("candidate_id")
        role = d0.get("approver_role") or "schema_auditor"
        level = 1 if role == "schema_auditor" else 2

        # 2) 找 (candidate_id, approver_role) 的**最新一条**流水作为状态
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            latest = conn.execute(
                """SELECT * FROM usl_approval_records
                   WHERE candidate_id = ? AND approver_role = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (cid, role),
            ).fetchone()
        finally:
            conn.close()
        d = dict(latest) if latest is not None else d0
        action = d.get("action") or ""
        if action == ACTION_APPROVE:
            st = APPR_APPROVED
        elif action == ACTION_REJECT:
            st = APPR_REJECTED
        else:
            st = APPR_PENDING
        return {
            "id": task_id,
            "candidate_id": cid,
            "level": level,
            "status": st,
            "assignee": d.get("approver_id"),
            "reviewer": d.get("approver_id"),
            "comment": d.get("comment"),
            "approved_at": d.get("created_at") if st != APPR_PENDING else None,
            "created_at": d0.get("created_at"),
            "updated_at": d.get("created_at"),
        }

    def list_approval_tasks(
        self,
        *,
        status: Optional[str] = None,
        candidate_id: Optional[str] = None,
        level: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """旧 list_approval_tasks → 把流水按 (candidate, approver_role) 合并成『task』视图。
        这里返回最近一条流水视作当前 task 状态。"""
        approver_role: Optional[str] = None
        if level is not None:
            approver_role = "schema_auditor" if int(level) == 1 else "admin"
        records_page = self.list_approval_records(
            candidate_id=candidate_id, approver_role=approver_role,
            page=1, page_size=max(page_size * 5, 200),
        )
        # 去重：以 (candidate_id, approver_role) 为 key，保留最新一条作为 task 视图
        seen: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for rec in records_page["items"]:
            key = (rec.get("candidate_id") or "", rec.get("approver_role") or "")
            if key in seen:
                continue
            seen[key] = rec
        items: List[Dict[str, Any]] = []
        for rec in seen.values():
            role = rec.get("approver_role") or "schema_auditor"
            lv = 1 if role == "schema_auditor" else 2
            action = rec.get("action") or ""
            if action == ACTION_APPROVE:
                st = APPR_APPROVED
            elif action == ACTION_REJECT:
                st = APPR_REJECTED
            else:
                st = APPR_PENDING
            if status and st != status:
                continue
            items.append({
                "id": rec["id"],
                "candidate_id": rec.get("candidate_id"),
                "level": lv,
                "status": st,
                "assignee": rec.get("approver_id"),
                "reviewer": rec.get("approver_id"),
                "comment": rec.get("comment"),
                "approved_at": rec.get("created_at") if st != APPR_PENDING else None,
                "created_at": rec.get("created_at"),
                "updated_at": rec.get("created_at"),
            })
        total = len(items)
        start = (page - 1) * page_size
        paged = items[start:start + page_size]
        return {"items": paged, "total": total, "page": page, "page_size": page_size}

    # ==================================================================
    # 5. Audit Logs — append/list
    # ==================================================================
    def append_audit_log(
        self,
        *,
        action: str,
        actor: Optional[str] = "system",
        pipeline_run_id: Optional[str] = None,
        candidate_id: Optional[str] = None,
        approval_task_id: Optional[str] = None,
        approval_record_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        log_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            actual_run_id = pipeline_run_id
            if actual_run_id is None and candidate_id:
                row = conn.execute(
                    "SELECT run_id FROM usl_schema_candidates WHERE id = ?",
                    (candidate_id,),
                ).fetchone()
                if row is not None:
                    actual_run_id = row[0]
            conn.execute(
                """INSERT INTO audit_logs (
                    id, pipeline_run_id, candidate_id, approval_task_id,
                    approval_record_id, action, actor, payload, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    log_id, actual_run_id, candidate_id, approval_task_id,
                    approval_record_id, action, actor,
                    json.dumps(payload or {}, ensure_ascii=False), now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return {"id": log_id, "action": action, "created_at": now}

    def list_audit_logs(
        self,
        *,
        candidate_id: Optional[str] = None,
        pipeline_run_id: Optional[str] = None,
        action: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
        approval_record_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        conds: List[str] = []
        args: List[Any] = []
        if candidate_id:
            conds.append("candidate_id = ?")
            args.append(candidate_id)
        if pipeline_run_id:
            conds.append("pipeline_run_id = ?")
            args.append(pipeline_run_id)
        if action:
            conds.append("action = ?")
            args.append(action)
        if approval_record_id:
            conds.append("approval_record_id = ?")
            args.append(approval_record_id)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                f"SELECT COUNT(*) FROM audit_logs {where}", args
            ).fetchone()[0]
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"SELECT * FROM audit_logs {where} "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                args + [page_size, offset],
            ).fetchall()
            items = []
            for r in rows:
                d = dict(r)
                d["payload"] = self._safe_json_dict(d.get("payload"))
                items.append(d)
            return {"items": items, "total": total,
                    "page": page, "page_size": page_size}
        finally:
            conn.close()

    # ==================================================================
    # 内部辅助（JSON 安全反序列化）
    # ==================================================================
    @classmethod
    def _safe_json_list(cls, raw: Optional[str]) -> List[Any]:
        if not raw:
            return []
        try:
            v = json.loads(raw)
            return v if isinstance(v, list) else []
        except (ValueError, TypeError):
            return []

    @classmethod
    def _safe_json_dict(cls, raw: Optional[str]) -> Dict[str, Any]:
        if not raw:
            return {}
        try:
            v = json.loads(raw)
            return v if isinstance(v, dict) else {}
        except (ValueError, TypeError):
            return {}

    @classmethod
    def _safe_json_list_any(cls, raw: Any) -> List[Any]:
        if raw is None or raw == "":
            return []
        if isinstance(raw, list):
            return raw
        if isinstance(raw, (dict, tuple, set)):
            return list(raw)
        try:
            v = json.loads(raw) if isinstance(raw, str) else raw
            return v if isinstance(v, list) else list(v) if isinstance(v, (tuple, set)) else []
        except (ValueError, TypeError):
            return []

    @classmethod
    def _safe_json_dict_any(cls, raw: Any) -> Dict[str, Any]:
        if raw is None or raw == "":
            return {}
        if isinstance(raw, dict):
            return raw
        try:
            v = json.loads(raw) if isinstance(raw, str) else raw
            return v if isinstance(v, dict) else {}
        except (ValueError, TypeError):
            return {}

    @classmethod
    def _safe_json_any(cls, raw: Any) -> Any:
        if raw is None:
            return None
        if isinstance(raw, (dict, list, int, float, bool)):
            return raw
        if isinstance(raw, str):
            if raw == "": return ""
            try:
                return json.loads(raw)
            except (ValueError, TypeError):
                return raw
        return raw

    def _get_one(
        self,
        table: str,
        pk_value: str,
        json_list_keys: Iterable[str] = (),
    ) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (pk_value,)).fetchone()
            if not row:
                return None
            d = dict(row)
            for k in json_list_keys:
                d[k] = self._safe_json_list(d.get(k))
            return d
        finally:
            conn.close()
