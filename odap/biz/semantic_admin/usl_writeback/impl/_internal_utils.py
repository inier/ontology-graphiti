"""USL Writeback 内部工具（AGENTS.md 250 LOC 限制拆分）。"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, Optional


DATA_DIR: str = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
CANDIDATE_DB_PATH: str = os.path.join(DATA_DIR, "candidate_store.db")
DEFAULT_DOMAIN_CODE = "GENERAL"
DEFAULT_DOMAIN_DISPLAY = "通用语义域"


def _resolve_or_create_domain_id(usl_storage: Any, fallback_code: str) -> str:
    """domain_id 为空时 lazy-create 默认领域，返回其 id。"""
    existed = usl_storage.get_domain_by_code(fallback_code)
    if existed:
        return str(existed["id"])
    created = usl_storage.save_domain({
        "code": fallback_code,
        "display_name": DEFAULT_DOMAIN_DISPLAY,
        "description": "Writeback 自动创建的通用语义域",
    })
    return str(created["id"])


def _merge_provenance(existing_prov: Any, **extra: Any) -> Dict[str, Any]:
    """安全合并 provenance dict（不破坏原 JSON）。"""
    base: Dict[str, Any] = {}
    if isinstance(existing_prov, dict):
        base = dict(existing_prov)
    elif isinstance(existing_prov, str) and existing_prov:
        try:
            v = json.loads(existing_prov)
            if isinstance(v, dict):
                base = v
        except (ValueError, TypeError):
            base = {}
    base.update(extra)
    return base


def _update_candidate_row(
    candidate_id: str,
    *,
    status: str,
    db_path: str,
    provenance_patch: Optional[Dict[str, Any]] = None,
    stoplist_flag: Optional[int] = None,
) -> bool:
    """UPDATE usl_schema_candidates（支持 provenance_json merge + stoplist_flag）。"""
    fields = ["status = ?", "updated_at = ?"]
    values: list = [status, datetime.now().isoformat()]

    if provenance_patch:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT provenance_json FROM usl_schema_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            old_raw = row[0] if row and len(row) > 0 else None
            merged = _merge_provenance(old_raw, **provenance_patch)
            fields.append("provenance_json = ?")
            values.append(json.dumps(merged, ensure_ascii=False))
        finally:
            conn.close()
    if stoplist_flag is not None:
        fields.append("stoplist_flag = ?")
        values.append(1 if stoplist_flag else 0)

    values.append(candidate_id)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            f"UPDATE usl_schema_candidates SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def _append_candidate_audit(
    candidate_id: str,
    *,
    action: str,
    actor: str,
    payload: Dict[str, Any],
    db_path: str,
) -> Dict[str, Any]:
    """往 candidate_store.audit_logs 写一条事件。"""
    log_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = sqlite3.connect(db_path)
    try:
        run_row = conn.execute(
            "SELECT run_id FROM usl_schema_candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        run_id = run_row[0] if run_row else None
        conn.execute(
            """INSERT INTO audit_logs (
                id, pipeline_run_id, candidate_id, approval_task_id,
                action, actor, payload, created_at
            ) VALUES (?,?,?,?,?,?,?,?)""",
            (
                log_id, run_id, candidate_id, None,
                action, actor, json.dumps(payload or {}, ensure_ascii=False), now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": log_id, "action": action, "created_at": now}
