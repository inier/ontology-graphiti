"""ODAP v2 八表 DDL（SPEC-v2 §6 锁定）—— infra 层存储契约。

为什么在 infra：表结构是「数据访问基础设施」，biz 各域（knowledge / ontology 编排）
只写自己的 Repository，DDL 单点维护，避免两套建表逻辑（任务书要求「不要自造第二套」）。

建表口径与仓库既有模块一致：
- SQLite（`odap_main.db`），`DATA_DIR` 优先；每次操作短连接，无连接池（AGENTS.md 规则 8）。
- JSON 字段用 TEXT 存储，`ensure_ascii=False` 保中文。
- 时间统一 ISO-8601 字符串（UTC）。
- 全部 `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`，可重复执行（幂等迁移）。
- 不使用 SQLAlchemy/Alembic：仓库既有 9 个 SQLite 模块均走 `sqlite3` 直连（`SqliteBaseStorage`），
  本模块沿用同一机制，不引入第二套迁移体系。

表清单：
    wiki_entries / wiki_versions / wiki_citations / governed_documents
    qa_traces / qa_provenance / qa_actions / feature_flags
"""

from __future__ import annotations

import os
import sqlite3
from typing import Optional

MAIN_DB_NAME = "odap_main.db"

_DDL = """
-- ── F1 LLM Wiki：条目 ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wiki_entries (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'draft',
    owner_id        TEXT NOT NULL,                       -- SPEC §6 约束：NOT NULL
    version         TEXT NOT NULL DEFAULT '0.1.0',       -- semver（AC-01/AC-08）
    source_ref      TEXT,                                -- repo:docs/... 导入来源（AC-15）
    superseded_by   TEXT,
    supersedes      TEXT NOT NULL DEFAULT '[]',          -- JSON array（AC-10 双向链）
    content_hash    TEXT NOT NULL DEFAULT '',            -- sha256:...（AC-04 判重）
    content         TEXT NOT NULL DEFAULT '',            -- Markdown 正文（当前版本）
    last_verified   TEXT,                                -- ISO date（AC-13 陈旧检测）
    tags            TEXT NOT NULL DEFAULT '[]',
    concept_refs    TEXT NOT NULL DEFAULT '[]',          -- TBox 概念引用
    workspace_id    TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wiki_entries_status ON wiki_entries(status);
CREATE INDEX IF NOT EXISTS idx_wiki_entries_owner ON wiki_entries(owner_id);
CREATE INDEX IF NOT EXISTS idx_wiki_entries_hash ON wiki_entries(content_hash);
CREATE INDEX IF NOT EXISTS idx_wiki_entries_ws_status ON wiki_entries(workspace_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_wiki_entries_source_ref
    ON wiki_entries(source_ref) WHERE source_ref IS NOT NULL;

-- ── F1：版本快照（AC-03/AC-05，禁止物理删除）────────────────────────────────
CREATE TABLE IF NOT EXISTS wiki_versions (
    id              TEXT PRIMARY KEY,
    entry_id        TEXT NOT NULL,
    version         TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    content_hash    TEXT NOT NULL DEFAULT '',
    author_id       TEXT NOT NULL DEFAULT '',
    change_note     TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    FOREIGN KEY (entry_id) REFERENCES wiki_entries(id)
);
CREATE INDEX IF NOT EXISTS idx_wiki_versions_entry ON wiki_versions(entry_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wiki_versions_hash ON wiki_versions(content_hash);

-- ── F1：引用关系（AC-06 / AC-11，反向建引用图）──────────────────────────────
CREATE TABLE IF NOT EXISTS wiki_citations (
    id              TEXT PRIMARY KEY,
    entry_id        TEXT NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'doc',
    ref             TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (entry_id) REFERENCES wiki_entries(id)
);
CREATE INDEX IF NOT EXISTS idx_wiki_citations_entry ON wiki_citations(entry_id);
CREATE INDEX IF NOT EXISTS idx_wiki_citations_ref ON wiki_citations(ref);

-- ── F2：仓库文档纳管（AC-09~AC-14，source_ref 唯一）─────────────────────────
CREATE TABLE IF NOT EXISTS governed_documents (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'draft',
    owner_id        TEXT,                                -- 允许为空以暴露 MISSING_OWNER
    version         TEXT NOT NULL DEFAULT '0.1.0',
    source_ref      TEXT,                                -- repo:docs/...（UNIQUE）
    superseded_by   TEXT,
    supersedes      TEXT NOT NULL DEFAULT '[]',
    content_hash    TEXT NOT NULL DEFAULT '',
    content         TEXT NOT NULL DEFAULT '',
    last_verified   TEXT,
    role            TEXT NOT NULL DEFAULT '',            -- pm/architect/designer/fe/be/qa/devops
    tags            TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_governed_documents_source_ref
    ON governed_documents(source_ref) WHERE source_ref IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_governed_documents_status ON governed_documents(status);
CREATE INDEX IF NOT EXISTS idx_governed_documents_role ON governed_documents(role);
CREATE INDEX IF NOT EXISTS idx_governed_documents_hash ON governed_documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_governed_documents_verified ON governed_documents(last_verified);

-- ── F8：问答流转（AC-36~AC-38 溯源锚定）─────────────────────────────────────
CREATE TABLE IF NOT EXISTS qa_traces (
    trace_id        TEXT PRIMARY KEY,                    -- urn:odap:trace:<ulid>
    query           TEXT NOT NULL,
    workspace_id    TEXT NOT NULL DEFAULT '',
    user_id         TEXT NOT NULL DEFAULT '',
    intent_json     TEXT NOT NULL DEFAULT '{}',
    tbox_version    TEXT NOT NULL DEFAULT '',
    contract_ok     INTEGER NOT NULL DEFAULT 0,
    degraded        INTEGER NOT NULL DEFAULT 0,
    citations_json  TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_qa_traces_ws ON qa_traces(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_qa_traces_user ON qa_traces(user_id);
CREATE INDEX IF NOT EXISTS idx_qa_traces_contract ON qa_traces(contract_ok);

CREATE TABLE IF NOT EXISTS qa_provenance (
    id                  TEXT PRIMARY KEY,
    trace_id            TEXT NOT NULL,
    step                TEXT NOT NULL,                   -- intent/map/guard/retrieve/compose/gate
    component           TEXT NOT NULL,
    component_version   TEXT NOT NULL DEFAULT '',
    evidence            TEXT NOT NULL DEFAULT '[]',
    ts                  TEXT NOT NULL,
    FOREIGN KEY (trace_id) REFERENCES qa_traces(trace_id),
    UNIQUE (trace_id, step)
);
CREATE INDEX IF NOT EXISTS idx_qa_provenance_trace ON qa_provenance(trace_id, step);

-- ── F9 预留：动作与 HITL（本轮只建表，不实现执行，见未完成项）───────────────
CREATE TABLE IF NOT EXISTS qa_actions (
    id              TEXT PRIMARY KEY,
    trace_id        TEXT NOT NULL,
    action_type     TEXT NOT NULL,
    risk_level      TEXT NOT NULL DEFAULT 'low',         -- low/high
    payload         TEXT NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'proposed',
    approved_by     TEXT,
    executed_at     TEXT,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (trace_id) REFERENCES qa_traces(trace_id)
);
CREATE INDEX IF NOT EXISTS idx_qa_actions_trace ON qa_actions(trace_id);
CREATE INDEX IF NOT EXISTS idx_qa_actions_status ON qa_actions(status);
CREATE INDEX IF NOT EXISTS idx_qa_actions_risk ON qa_actions(risk_level);

-- ── 灰度：Feature Flag（ARCHITECTURE-v2 §8.3）───────────────────────────────
CREATE TABLE IF NOT EXISTS feature_flags (
    key             TEXT PRIMARY KEY,
    enabled         INTEGER NOT NULL DEFAULT 0,
    rollouts        TEXT NOT NULL DEFAULT '{}',          -- {"user_ids":[],"percentage":0}
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feature_flags_enabled ON feature_flags(enabled);
"""


def default_db_path() -> str:
    """`odap_main.db` 路径（DATA_DIR 优先，与 SQLite 存储基类口径一致）。"""
    data_dir = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, MAIN_DB_NAME)


def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    """打开连接（Row 工厂；调用方负责 close，无连接池）。"""
    conn = sqlite3.connect(db_path or default_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def ensure_v2_schema(db_path: Optional[str] = None) -> str:
    """幂等建表 + 建索引，返回实际使用的 db_path。"""
    path = db_path or default_db_path()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_DDL)
        conn.commit()
    finally:
        conn.close()
    return path


__all__ = ["MAIN_DB_NAME", "default_db_path", "connect", "ensure_v2_schema"]
