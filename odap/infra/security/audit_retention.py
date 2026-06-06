#!/usr/bin/env python3
"""
审计日志保留策略 (T328 - SC-05)

职责:
- 按 workspace + data_classification 配置的保留期 (默认 90 天)
- 过期审计自动归档到 MinIO (bucket: audit-archives) 或硬删除
- 提供历史归档查询 (从 MinIO 拉取)
- 维护归档索引 (审计归档清单)

设计原则 (AGENTS.md):
- 不修改任何现有模块
- 调用链: services -> manager (impl) -> storage
- 函数体 <= 40 行; 超过即拆分
- 容器字段用 Field(default_factory=...) (本文件使用 dataclass, 默认值安全)
- 错误处理: MinIO 不可用时, 跳过当前批次 (不删除本地行)
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("audit_retention")

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

DEFAULT_RETENTION_DAYS: int = 90
ARCHIVE_BUCKET: str = "audit-archives"
ARCHIVE_KEY_PREFIX: str = "archives"


# ---------------------------------------------------------------------------
# Enum & dataclass
# ---------------------------------------------------------------------------


class RetentionAction(str, Enum):
    """过期处理动作."""

    ARCHIVE_TO_MINIO = "archive_to_minio"
    HARD_DELETE = "hard_delete"
    KEEP_FOREVER = "keep_forever"


@dataclass
class RetentionPolicy:
    """单条保留策略.

    ws_id / classification 都支持 "*" 通配. 匹配优先级:
      1) 精确 (ws_id, classification)
      2) 精确 ws_id + 通配 classification
      3) 通配 ws_id + 精确 classification
      4) 双通配
    """

    ws_id: str
    classification: str
    retention_days: int
    action: RetentionAction
    created_at: datetime
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _build_archive_key(ws_id: str, ts: datetime) -> str:
    """构造 MinIO 归档 key.

    格式: archives/{ws_id}/{year}/{month}/{timestamp_unix}.json.gz
    """
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    safe_ws = (ws_id or "default").replace("/", "_").replace("..", "_")
    return (
        f"{ARCHIVE_KEY_PREFIX}/{safe_ws}/"
        f"{ts.year:04d}/{ts.month:02d}/"
        f"{int(ts.timestamp())}.json.gz"
    )


def _parse_event_timestamp(value: Any) -> datetime:
    """兼容 datetime / ISO 字符串 / SQLite 默认时间戳."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.now()
    return datetime.now()


def _is_wildcard(value: str) -> bool:
    return value in ("*", "", None)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class AuditRetentionManager:
    """审计保留策略管理器.

    用法:
        mgr = AuditRetentionManager(db_path, minio_client)
        mgr.upsert_policy(RetentionPolicy(...))
        summary = mgr.archive_expired(now=datetime.now())
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        minio_client: Any = None,
        policy_loader: Optional[Callable[[], List[RetentionPolicy]]] = None,
    ):
        if db_path is None:
            data_dir = os.environ.get(
                "DATA_DIR", os.path.join(os.getcwd(), "data")
            )
            db_path = os.path.join(data_dir, "audit_retention.db")
        self.db_path = db_path
        self.minio_client = minio_client
        self.policy_loader = policy_loader
        self._init_db()

    # ---- DB -------------------------------------------------------------

    def _init_db(self) -> None:
        """初始化 policies + archive_index 两张表."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_retention_policies (
                    id TEXT PRIMARY KEY,
                    ws_id TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    retention_days INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(ws_id, classification)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_archive_index (
                    id TEXT PRIMARY KEY,
                    ws_id TEXT NOT NULL,
                    minio_bucket TEXT NOT NULL,
                    minio_key TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    archived_at TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_archive_ws "
                "ON audit_archive_index(ws_id)"
            )
            conn.commit()
        finally:
            conn.close()

    # ---- Policy CRUD ----------------------------------------------------

    def upsert_policy(self, policy: RetentionPolicy) -> None:
        """插入或更新策略 (按 (ws_id, classification) 唯一)."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO audit_retention_policies
                    (id, ws_id, classification, retention_days, action, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(ws_id, classification) DO UPDATE SET
                    retention_days = excluded.retention_days,
                    action = excluded.action,
                    created_at = excluded.created_at
                """,
                (
                    policy.id,
                    policy.ws_id,
                    policy.classification,
                    policy.retention_days,
                    policy.action.value
                    if isinstance(policy.action, RetentionAction)
                    else str(policy.action),
                    policy.created_at.isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _load_policies(self) -> List[RetentionPolicy]:
        """从 DB + 注入 loader 加载所有策略."""
        policies: List[RetentionPolicy] = []
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "SELECT id, ws_id, classification, retention_days, "
                "action, created_at FROM audit_retention_policies"
            )
            for row in cur.fetchall():
                pid, ws_id, cls, days, action_str, ts = row
                try:
                    action = RetentionAction(action_str)
                except ValueError:
                    action = RetentionAction.ARCHIVE_TO_MINIO
                policies.append(
                    RetentionPolicy(
                        id=pid,
                        ws_id=ws_id,
                        classification=cls,
                        retention_days=days,
                        action=action,
                        created_at=datetime.fromisoformat(ts),
                    )
                )
        finally:
            conn.close()

        if self.policy_loader is not None:
            try:
                extra = self.policy_loader() or []
                policies.extend(extra)
            except Exception as exc:  # pragma: no cover - 防御
                logger.warning("policy_loader failed: %s", exc)
        return policies

    def get_retention_policy(
        self, ws_id: str, classification: str
    ) -> RetentionPolicy:
        """解析 (ws_id, classification) 对应的策略 (最长匹配优先).

        匹配优先级 (从高到低):
            1) (ws_id, classification) 精确
            2) (ws_id, *) 通配 classification
            3) (*, classification) 通配 ws_id
            4) (*, *) 双通配
        都不匹配时返回默认 90 天 / ARCHIVE_TO_MINIO.
        """
        policies = self._load_policies()

        def _key(p: RetentionPolicy) -> tuple:
            # (ws_match_rank, cls_match_rank) 越小越优先
            ws_rank = 0 if p.ws_id == ws_id else (1 if _is_wildcard(p.ws_id) else 2)
            cls_rank = (
                0
                if p.classification == classification
                else (1 if _is_wildcard(p.classification) else 2)
            )
            return (ws_rank, cls_rank)

        candidates = [p for p in policies if _key(p) != (2, 2)]
        if candidates:
            candidates.sort(key=_key)
            return candidates[0]
        return RetentionPolicy(
            ws_id=ws_id,
            classification=classification,
            retention_days=DEFAULT_RETENTION_DAYS,
            action=RetentionAction.ARCHIVE_TO_MINIO,
            created_at=datetime.now(),
        )

    # ---- Expiry 判断 ----------------------------------------------------

    def is_expired(
        self,
        event: Dict[str, Any],
        now: datetime,
        classification: Optional[str] = None,
    ) -> bool:
        """判断事件是否过期 (严格 > retention_days 才视为过期)."""
        ws_id = event.get("workspace_id", "default")
        cls = classification or event.get("classification") or "U"
        policy = self.get_retention_policy(ws_id, cls)
        if policy.action == RetentionAction.KEEP_FOREVER:
            return False
        ts = _parse_event_timestamp(event.get("timestamp"))
        # 用 total_seconds 精确比较 (避免 days 字段舍入误差)
        elapsed_seconds = (now - ts).total_seconds()
        threshold = policy.retention_days * 86400
        return elapsed_seconds > threshold

    # ---- 扫描过期事件 ---------------------------------------------------

    def _fetch_expired_batch(
        self, now: datetime, batch_size: int
    ) -> List[Dict[str, Any]]:
        """按 batch 取出过期的 audit_events 行 (用 Python 端 is_expired 过滤)."""
        results: List[Dict[str, Any]] = []
        rows = self._select_all_audit_rows()
        for row in rows:
            if len(results) >= batch_size:
                break
            event = self._row_to_event_dict(row)
            if self.is_expired(event, now):
                results.append(event)
        return results

    def _select_all_audit_rows(self) -> List[tuple]:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "SELECT id, timestamp, event_type, severity, actor_type, "
                "actor_id, actor_name, action, resource_type, resource_id, "
                "result_status, result_message, workspace_id, trace_id, "
                "parent_event_id, duration_ms, context, changes, checksum "
                "FROM audit_events ORDER BY timestamp ASC"
            )
            return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def _row_to_event_dict(row: tuple) -> Dict[str, Any]:
        return {
            "id": row[0], "timestamp": row[1], "event_type": row[2],
            "severity": row[3], "actor_type": row[4], "actor_id": row[5],
            "actor_name": row[6], "action": row[7], "resource_type": row[8],
            "resource_id": row[9], "result_status": row[10],
            "result_message": row[11], "workspace_id": row[12],
            "trace_id": row[13], "parent_event_id": row[14],
            "duration_ms": row[15], "context": row[16], "changes": row[17],
            "checksum": row[18],
        }

    def _delete_events(self, event_ids: List[str]) -> int:
        """从 audit_events 物理删除指定 id 列表."""
        if not event_ids:
            return 0
        conn = sqlite3.connect(self.db_path)
        try:
            placeholders = ",".join(["?"] * len(event_ids))
            cur = conn.execute(
                f"DELETE FROM audit_events WHERE id IN ({placeholders})",
                event_ids,
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    # ---- 归档索引 -------------------------------------------------------

    def _record_archive_index(
        self,
        ws_id: str,
        bucket: str,
        key: str,
        event_count: int,
        start_time: datetime,
        end_time: datetime,
        size_bytes: int,
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO audit_archive_index
                    (id, ws_id, minio_bucket, minio_key, event_count,
                     start_time, end_time, archived_at, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    ws_id,
                    bucket,
                    key,
                    event_count,
                    start_time.isoformat(),
                    end_time.isoformat(),
                    datetime.now().isoformat(),
                    size_bytes,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_archive_index(self, ws_id: str) -> List[Dict[str, Any]]:
        """获取某工作空间的归档索引列表."""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                "SELECT id, ws_id, minio_bucket, minio_key, event_count, "
                "start_time, end_time, archived_at, size_bytes "
                "FROM audit_archive_index WHERE ws_id = ? "
                "ORDER BY archived_at DESC",
                (ws_id,),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "ws_id": r[1],
                    "minio_bucket": r[2],
                    "minio_key": r[3],
                    "event_count": r[4],
                    "start_time": r[5],
                    "end_time": r[6],
                    "archived_at": r[7],
                    "size_bytes": r[8],
                }
                for r in rows
            ]
        finally:
            conn.close()

    # ---- 归档主流程 -----------------------------------------------------

    def archive_expired(
        self,
        now: Optional[datetime] = None,
        batch_size: int = 1000,
    ) -> Dict[str, Any]:
        """执行归档任务并返回 summary."""
        start = now or datetime.now()
        t0 = datetime.now()
        summary = self._new_summary()

        while True:
            batch = self._fetch_expired_batch(start, batch_size)
            if not batch:
                break
            by_ws = self._group_by_workspace(batch)
            failed = self._process_workspace_groups(start, by_ws, summary)
            if failed:
                break

        summary["duration_ms"] = int(
            (datetime.now() - t0).total_seconds() * 1000
        )
        return summary

    @staticmethod
    def _new_summary() -> Dict[str, Any]:
        return {
            "archived_count": 0,
            "archived_bytes": 0,
            "minio_keys": [],
            "duration_ms": 0,
        }

    @staticmethod
    def _group_by_workspace(
        events: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for ev in events:
            ws = ev.get("workspace_id", "default")
            groups.setdefault(ws, []).append(ev)
        return groups

    def _process_workspace_groups(
        self,
        start: datetime,
        by_ws: Dict[str, List[Dict[str, Any]]],
        summary: Dict[str, Any],
    ) -> bool:
        """逐 ws 处理; 失败时返回 True (调用方应退出 while)."""
        for ws_id, events in by_ws.items():
            action = self.get_retention_policy(ws_id, "U").action
            if action == RetentionAction.KEEP_FOREVER:
                continue
            if action == RetentionAction.HARD_DELETE:
                deleted = self._delete_events([e["id"] for e in events])
                summary["archived_count"] += deleted
                continue
            ok = self._archive_one_workspace(start, ws_id, events, summary)
            if not ok:
                return True
        return False

    def _archive_one_workspace(
        self,
        start: datetime,
        ws_id: str,
        events: List[Dict[str, Any]],
        summary: Dict[str, Any],
    ) -> bool:
        """打包 + MinIO 上传 + 删除; 失败返回 False."""
        key = _build_archive_key(ws_id, start)
        payload = json.dumps(events, default=str).encode("utf-8")
        compressed = gzip.compress(payload)
        result = self._upload_to_minio(key, compressed)
        if result.get("status") != "success":
            logger.warning(
                "archive upload failed for %s: %s",
                key,
                result.get("message"),
            )
            return False
        self._record_archive_index(
            ws_id=ws_id,
            bucket=ARCHIVE_BUCKET,
            key=key,
            event_count=len(events),
            start_time=_parse_event_timestamp(events[0]["timestamp"]),
            end_time=_parse_event_timestamp(events[-1]["timestamp"]),
            size_bytes=len(compressed),
        )
        self._delete_events([e["id"] for e in events])
        summary["archived_count"] += len(events)
        summary["archived_bytes"] += len(compressed)
        summary["minio_keys"].append(key)
        return True

    def _upload_to_minio(
        self, key: str, data: bytes
    ) -> Dict[str, Any]:
        """封装 MinIO 上传; 客户端为 None 时降级."""
        if self.minio_client is None:
            return {"status": "error", "message": "minio_client not configured"}
        try:
            return self.minio_client.upload_object(
                ARCHIVE_BUCKET, key, data, content_type="application/gzip"
            )
        except Exception as exc:  # pragma: no cover - 防御
            logger.warning("MinIO upload exception: %s", exc)
            return {"status": "error", "message": str(exc)}

    # ---- 历史查询 -------------------------------------------------------

    def query_archived(
        self,
        ws_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """从 MinIO 拉取归档事件并按时间窗过滤."""
        index = self.get_archive_index(ws_id)
        if not index:
            return []

        results: List[Dict[str, Any]] = []
        for entry in index:
            events = self._download_archive(entry)
            for ev in events:
                ts = _parse_event_timestamp(ev.get("timestamp"))
                if start_time <= ts <= end_time:
                    results.append(ev)
        return results

    def _download_archive(self, entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从 MinIO 下载并解压一份归档."""
        if self.minio_client is None:
            return []
        try:
            result = self.minio_client.download_object(
                entry["minio_bucket"], entry["minio_key"]
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("MinIO download exception: %s", exc)
            return []
        if result.get("status") != "success":
            return []
        data = result.get("data")
        if not data:
            return []
        try:
            decompressed = gzip.decompress(data)
            payload = json.loads(decompressed.decode("utf-8"))
            return payload if isinstance(payload, list) else []
        except Exception as exc:  # pragma: no cover
            logger.warning("decompress/archive parse failed: %s", exc)
            return []


__all__ = [
    "DEFAULT_RETENTION_DAYS",
    "ARCHIVE_BUCKET",
    "ARCHIVE_KEY_PREFIX",
    "RetentionAction",
    "RetentionPolicy",
    "AuditRetentionManager",
    "_build_archive_key",
]
