#!/usr/bin/env python3
"""
审计日志保留策略测试 (T328)

覆盖范围:
- Policy 数据结构与默认 90 天保留
- 最长匹配 (ws_id + classification) 策略解析
- is_expired 过期判断
- archive_expired 归档流程 (SQLite -> MinIO)
- query_archived 历史归档查询
- archive_index 索引管理
- 边界条件: 空 DB / 无过期 / MinIO 不可用降级
- 归档摘要字段完整性

测试规则 (AGENTS.md):
- SQLite 存储用 tmp_path 真实 DB
- MinIO 通过依赖注入 (MagicMock) 模拟
- 不修改任何现有代码
"""
import gzip
import json
import os
import sqlite3
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# 辅助 fixtures & factories
# ---------------------------------------------------------------------------


def _make_event(
    event_id: str = None,
    workspace_id: str = "default",
    event_type: str = "user.login",
    severity: str = "info",
    actor_id: str = "user-1",
    action: str = "user_login",
    resource_type: str = "auth",
    resource_id: str = "auth-1",
    timestamp: datetime = None,
    context: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """构造一个 audit_events 行所需的 dict (与 SQLiteAuditChannel schema 对齐)."""
    return {
        "id": event_id or str(uuid.uuid4()),
        "timestamp": (timestamp or datetime.now()).isoformat(),
        "event_type": event_type,
        "severity": severity,
        "actor_type": "user",
        "actor_id": actor_id,
        "actor_name": actor_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "result_status": "success",
        "result_message": "ok",
        "workspace_id": workspace_id,
        "trace_id": str(uuid.uuid4()),
        "parent_event_id": None,
        "duration_ms": 10,
        "context": json.dumps(context or {}),
        "changes": json.dumps({}),
        "checksum": "deadbeef",
    }


@pytest.fixture
def audit_db_path(tmp_path) -> str:
    """返回真实临时 SQLite DB 路径 (与 audit_sqlite_channel 同样的 schema)."""
    db = str(tmp_path / "audit.db")
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'info',
                actor_type TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                actor_name TEXT NOT NULL,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                result_status TEXT NOT NULL,
                result_message TEXT DEFAULT '',
                workspace_id TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                parent_event_id TEXT,
                duration_ms INTEGER,
                context TEXT,
                changes TEXT,
                checksum TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
    return db


@pytest.fixture
def mock_minio() -> MagicMock:
    """构造一个 MagicMock MinIO 客户端 (满足 duck-type 接口)."""
    client = MagicMock()
    client.upload_object = MagicMock(
        return_value={"status": "success", "key": "fake-key"}
    )
    client.download_object = MagicMock(
        return_value={
            "status": "success",
            "data": b"",
            "size": 0,
        }
    )
    client.list_objects = MagicMock(
        return_value={"status": "success", "objects": [], "count": 0}
    )
    client.ensure_bucket = MagicMock(
        return_value={"status": "success", "created": False}
    )
    return client


@pytest.fixture
def ret_module():
    """延迟加载被测模块 (允许独立运行)."""
    from odap.infra.security import audit_retention
    return audit_retention


@pytest.fixture
def manager(ret_module, audit_db_path, mock_minio):
    """一个默认配置的 AuditRetentionManager."""
    return ret_module.AuditRetentionManager(
        db_path=audit_db_path, minio_client=mock_minio
    )


def _insert_event(db_path: str, event: Dict[str, Any]) -> None:
    """直接写入 audit_events 表 (用于构造测试数据)."""
    conn = sqlite3.connect(db_path)
    try:
        cols = ", ".join(event.keys())
        placeholders = ", ".join(["?"] * len(event))
        conn.execute(
            f"INSERT INTO audit_events ({cols}) VALUES ({placeholders})",
            list(event.values()),
        )
        conn.commit()
    finally:
        conn.close()


def _count_events(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM audit_events")
        return cur.fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# TestRetentionActionEnum
# ---------------------------------------------------------------------------


class TestRetentionActionEnum:
    """RetentionAction 枚举必须是 (str, Enum) 双继承."""

    def test_values(self, ret_module):
        assert ret_module.RetentionAction.ARCHIVE_TO_MINIO.value == "archive_to_minio"
        assert ret_module.RetentionAction.HARD_DELETE.value == "hard_delete"
        assert ret_module.RetentionAction.KEEP_FOREVER.value == "keep_forever"

    def test_string_enum_membership(self, ret_module):
        # str + Enum 双继承: 成员可与 str 比较
        assert ret_module.RetentionAction.ARCHIVE_TO_MINIO == "archive_to_minio"
        assert ret_module.RetentionAction.HARD_DELETE in ("hard_delete",)


# ---------------------------------------------------------------------------
# TestRetentionPolicyDataclass
# ---------------------------------------------------------------------------


class TestRetentionPolicyDataclass:
    """RetentionPolicy dataclass 字段 & 默认值."""

    def test_required_fields(self, ret_module):
        p = ret_module.RetentionPolicy(
            ws_id="ws-1",
            classification="C",
            retention_days=30,
            action=ret_module.RetentionAction.HARD_DELETE,
            created_at=datetime.now(),
        )
        assert p.ws_id == "ws-1"
        assert p.classification == "C"
        assert p.retention_days == 30
        assert p.action == ret_module.RetentionAction.HARD_DELETE

    def test_wildcard_supported(self, ret_module):
        p = ret_module.RetentionPolicy(
            ws_id="*",
            classification="*",
            retention_days=90,
            action=ret_module.RetentionAction.ARCHIVE_TO_MINIO,
            created_at=datetime(2024, 1, 1),
        )
        assert p.ws_id == "*"
        assert p.classification == "*"

    def test_asdict_roundtrip(self, ret_module):
        ts = datetime(2024, 6, 1, 12, 0, 0)
        p = ret_module.RetentionPolicy(
            ws_id="ws-1",
            classification="S",
            retention_days=365,
            action=ret_module.RetentionAction.KEEP_FOREVER,
            created_at=ts,
        )
        d = asdict(p)
        assert d["ws_id"] == "ws-1"
        assert d["retention_days"] == 365


# ---------------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_default_retention_days(self, ret_module):
        assert ret_module.DEFAULT_RETENTION_DAYS == 90

    def test_archive_bucket(self, ret_module):
        assert ret_module.ARCHIVE_BUCKET == "audit-archives"

    def test_archive_key_pattern(self, ret_module):
        # Key 格式: archives/{ws_id}/{year}/{month}/{timestamp}.json.gz
        ts = datetime(2024, 6, 15, 10, 30, 0)
        key = ret_module._build_archive_key("ws-1", ts)
        assert key.startswith("archives/ws-1/2024/06/")
        assert key.endswith(".json.gz")
        assert ts.isoformat() in key or str(int(ts.timestamp())) in key


# ---------------------------------------------------------------------------
# TestManagerInit
# ---------------------------------------------------------------------------


class TestManagerInit:
    def test_default_db_path(self, ret_module, mock_minio, tmp_path, monkeypatch):
        # 当 db_path 为 None 时, 应当使用默认路径 (且不要求目录存在)
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        m = ret_module.AuditRetentionManager(minio_client=mock_minio)
        assert m.db_path != ""

    def test_explicit_db_path(self, ret_module, audit_db_path, mock_minio):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        assert m.db_path == audit_db_path

    def test_creates_retention_tables(self, ret_module, audit_db_path, mock_minio):
        ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        conn = sqlite3.connect(audit_db_path)
        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_retention_policies'"
            )
            assert cur.fetchone() is not None
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_archive_index'"
            )
            assert cur.fetchone() is not None
        finally:
            conn.close()

    def test_policy_loader_invoked(self, ret_module, audit_db_path, mock_minio):
        calls = []

        def loader():
            calls.append(True)
            return [
                ret_module.RetentionPolicy(
                    ws_id="*",
                    classification="*",
                    retention_days=42,
                    action=ret_module.RetentionAction.ARCHIVE_TO_MINIO,
                    created_at=datetime.now(),
                )
            ]

        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path,
            minio_client=mock_minio,
            policy_loader=loader,
        )
        # init 时不应调用; 只在解析策略时调用
        assert calls == []
        p = m.get_retention_policy("ws-1", "C")
        assert p.retention_days == 42
        assert calls == [True]


# ---------------------------------------------------------------------------
# TestPolicyMatching
# ---------------------------------------------------------------------------


class TestPolicyMatching:
    """最长匹配优先 (ws_id+classification), 数据库策略覆盖 loader."""

    def test_default_90_days_when_no_policies(self, ret_module, manager):
        p = manager.get_retention_policy("ws-1", "C")
        assert p.retention_days == ret_module.DEFAULT_RETENTION_DAYS
        assert p.action == ret_module.RetentionAction.ARCHIVE_TO_MINIO

    def test_custom_ws_policy(self, ret_module, audit_db_path, mock_minio):
        # ws="ws-1", classification="*" = 30 天
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        m.upsert_policy(
            ret_module.RetentionPolicy(
                ws_id="ws-1",
                classification="*",
                retention_days=30,
                action=ret_module.RetentionAction.HARD_DELETE,
                created_at=datetime.now(),
            )
        )
        p = m.get_retention_policy("ws-1", "C")
        assert p.retention_days == 30
        assert p.action == ret_module.RetentionAction.HARD_DELETE

    def test_classification_specific_beats_ws_wildcard(
        self, ret_module, audit_db_path, mock_minio
    ):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        m.upsert_policy(
            ret_module.RetentionPolicy(
                ws_id="ws-1",
                classification="*",
                retention_days=30,
                action=ret_module.RetentionAction.HARD_DELETE,
                created_at=datetime.now(),
            )
        )
        m.upsert_policy(
            ret_module.RetentionPolicy(
                ws_id="ws-1",
                classification="S",
                retention_days=365,
                action=ret_module.RetentionAction.ARCHIVE_TO_MINIO,
                created_at=datetime.now(),
            )
        )
        p = m.get_retention_policy("ws-1", "S")
        assert p.retention_days == 365  # classification-specific wins

    def test_exact_ws_beats_global_wildcard(self, ret_module, audit_db_path, mock_minio):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        m.upsert_policy(
            ret_module.RetentionPolicy(
                ws_id="*",
                classification="*",
                retention_days=10,
                action=ret_module.RetentionAction.HARD_DELETE,
                created_at=datetime.now(),
            )
        )
        m.upsert_policy(
            ret_module.RetentionPolicy(
                ws_id="ws-1",
                classification="*",
                retention_days=60,
                action=ret_module.RetentionAction.ARCHIVE_TO_MINIO,
                created_at=datetime.now(),
            )
        )
        p = m.get_retention_policy("ws-1", "U")
        assert p.retention_days == 60

    def test_keep_forever_overrides(self, ret_module, audit_db_path, mock_minio):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        m.upsert_policy(
            ret_module.RetentionPolicy(
                ws_id="ws-1",
                classification="TS",
                retention_days=99999,
                action=ret_module.RetentionAction.KEEP_FOREVER,
                created_at=datetime.now(),
            )
        )
        p = m.get_retention_policy("ws-1", "TS")
        assert p.action == ret_module.RetentionAction.KEEP_FOREVER


# ---------------------------------------------------------------------------
# TestIsExpired
# ---------------------------------------------------------------------------


class TestIsExpired:
    def test_event_within_retention(self, ret_module, manager):
        now = datetime(2024, 6, 15)
        ev = _make_event(timestamp=now - timedelta(days=10))
        assert manager.is_expired(ev, now) is False

    def test_event_at_boundary_not_expired(self, ret_module, manager):
        # 默认 90 天: timestamp + 90 days == now 视为未过期
        now = datetime(2024, 6, 15)
        ev = _make_event(timestamp=now - timedelta(days=90))
        # 应使用严格小于, 边界值不视为过期
        assert manager.is_expired(ev, now) is False

    def test_event_just_past_retention_expired(self, ret_module, manager):
        now = datetime(2024, 6, 15)
        ev = _make_event(timestamp=now - timedelta(days=91))
        assert manager.is_expired(ev, now) is True

    def test_keep_forever_never_expired(self, ret_module, audit_db_path, mock_minio):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        m.upsert_policy(
            ret_module.RetentionPolicy(
                ws_id="*",
                classification="TS",
                retention_days=1,
                action=ret_module.RetentionAction.KEEP_FOREVER,
                created_at=datetime.now(),
            )
        )
        ev = _make_event(
            timestamp=datetime.now() - timedelta(days=365),
            workspace_id="ws-1",
        )
        ev["_classification"] = "TS"  # hint for matching
        # 通过 patch context 强制匹配 TS
        assert m.is_expired(
            ev,
            datetime.now(),
            classification="TS",
        ) is False

    def test_custom_short_retention(self, ret_module, audit_db_path, mock_minio):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        m.upsert_policy(
            ret_module.RetentionPolicy(
                ws_id="ws-1",
                classification="*",
                retention_days=7,
                action=ret_module.RetentionAction.HARD_DELETE,
                created_at=datetime.now(),
            )
        )
        now = datetime(2024, 6, 15)
        ev = _make_event(
            workspace_id="ws-1", timestamp=now - timedelta(days=10)
        )
        assert m.is_expired(ev, now) is True


# ---------------------------------------------------------------------------
# TestArchiveExpired
# ---------------------------------------------------------------------------


class TestArchiveExpired:
    def test_no_events_returns_zero_summary(
        self, ret_module, manager, mock_minio
    ):
        summary = manager.archive_expired(now=datetime.now())
        assert summary["archived_count"] == 0
        assert summary["archived_bytes"] == 0
        assert summary["minio_keys"] == []
        assert "duration_ms" in summary
        mock_minio.upload_object.assert_not_called()

    def test_expired_events_archived_to_minio(
        self, ret_module, audit_db_path, mock_minio
    ):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        # 100 天前: 已过期 (默认 90 天)
        old_ts = datetime.now() - timedelta(days=100)
        for i in range(3):
            _insert_event(
                audit_db_path,
                _make_event(
                    event_id=f"e-{i}",
                    workspace_id="ws-1",
                    timestamp=old_ts,
                ),
            )
        # 10 天前: 未过期
        for i in range(2):
            _insert_event(
                audit_db_path,
                _make_event(
                    event_id=f"r-{i}",
                    workspace_id="ws-1",
                    timestamp=datetime.now() - timedelta(days=10),
                ),
            )
        assert _count_events(audit_db_path) == 5

        summary = m.archive_expired(now=datetime.now(), batch_size=10)

        assert summary["archived_count"] == 3
        assert _count_events(audit_db_path) == 2
        assert len(summary["minio_keys"]) == 1  # 3 个事件打包为 1 个归档
        mock_minio.upload_object.assert_called_once()

    def test_archive_summary_fields(
        self, ret_module, audit_db_path, mock_minio
    ):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        old_ts = datetime.now() - timedelta(days=120)
        _insert_event(
            audit_db_path,
            _make_event(
                event_id="x-1", workspace_id="ws-1", timestamp=old_ts
            ),
        )
        summary = m.archive_expired(now=datetime.now())
        for k in (
            "archived_count",
            "archived_bytes",
            "minio_keys",
            "duration_ms",
        ):
            assert k in summary
        assert summary["archived_count"] == 1
        assert summary["archived_bytes"] >= 0
        assert isinstance(summary["duration_ms"], int)

    def test_archive_key_format(self, ret_module, audit_db_path, mock_minio):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        old_ts = datetime.now() - timedelta(days=200)
        _insert_event(
            audit_db_path,
            _make_event(
                event_id="k-1", workspace_id="ws-9", timestamp=old_ts
            ),
        )
        m.archive_expired(now=datetime.now())
        # 验证 MinIO upload_object 收到的 key 格式
        args, kwargs = mock_minio.upload_object.call_args
        bucket = args[0] if args else kwargs.get("bucket")
        key = args[1] if len(args) > 1 else kwargs.get("key")
        assert bucket == ret_module.ARCHIVE_BUCKET
        assert key.startswith("archives/ws-9/")
        assert key.endswith(".json.gz")

    def test_archive_payload_is_gzip_json(
        self, ret_module, audit_db_path, mock_minio
    ):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        old_ts = datetime.now() - timedelta(days=200)
        _insert_event(
            audit_db_path,
            _make_event(
                event_id="g-1", workspace_id="ws-1", timestamp=old_ts
            ),
        )
        m.archive_expired(now=datetime.now())
        args, kwargs = mock_minio.upload_object.call_args
        data = args[2] if len(args) > 2 else kwargs.get("data")
        # gzip 解压
        decompressed = gzip.decompress(data)
        payload = json.loads(decompressed.decode("utf-8"))
        assert isinstance(payload, list)
        assert len(payload) == 1
        assert payload[0]["id"] == "g-1"

    def test_archive_index_recorded(
        self, ret_module, audit_db_path, mock_minio
    ):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        old_ts = datetime.now() - timedelta(days=200)
        _insert_event(
            audit_db_path,
            _make_event(
                event_id="i-1", workspace_id="ws-7", timestamp=old_ts
            ),
        )
        m.archive_expired(now=datetime.now())

        index = m.get_archive_index("ws-7")
        assert len(index) == 1
        rec = index[0]
        assert rec["ws_id"] == "ws-7"
        assert rec["minio_bucket"] == ret_module.ARCHIVE_BUCKET
        assert rec["event_count"] == 1
        assert rec["minio_key"].endswith(".json.gz")

    def test_hard_delete_action(self, ret_module, audit_db_path, mock_minio):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        m.upsert_policy(
            ret_module.RetentionPolicy(
                ws_id="*",
                classification="*",
                retention_days=30,
                action=ret_module.RetentionAction.HARD_DELETE,
                created_at=datetime.now(),
            )
        )
        old_ts = datetime.now() - timedelta(days=60)
        for i in range(2):
            _insert_event(
                audit_db_path,
                _make_event(
                    event_id=f"h-{i}", workspace_id="ws-1", timestamp=old_ts
                ),
            )
        summary = m.archive_expired(now=datetime.now())
        # HARD_DELETE: 不写 MinIO, 直接删行
        assert summary["minio_keys"] == []
        mock_minio.upload_object.assert_not_called()
        assert _count_events(audit_db_path) == 0

    def test_keep_forever_events_not_archived(
        self, ret_module, audit_db_path, mock_minio
    ):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        m.upsert_policy(
            ret_module.RetentionPolicy(
                ws_id="*",
                classification="*",
                retention_days=1,
                action=ret_module.RetentionAction.KEEP_FOREVER,
                created_at=datetime.now(),
            )
        )
        old_ts = datetime.now() - timedelta(days=365)
        _insert_event(
            audit_db_path,
            _make_event(
                event_id="k-1", workspace_id="ws-1", timestamp=old_ts
            ),
        )
        summary = m.archive_expired(now=datetime.now())
        assert summary["archived_count"] == 0
        assert _count_events(audit_db_path) == 1

    def test_minio_failure_does_not_corrupt_state(
        self, ret_module, audit_db_path, mock_minio
    ):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        # 模拟 MinIO 上传失败
        mock_minio.upload_object = MagicMock(
            return_value={"status": "error", "message": "boom"}
        )
        old_ts = datetime.now() - timedelta(days=200)
        for i in range(3):
            _insert_event(
                audit_db_path,
                _make_event(
                    event_id=f"f-{i}",
                    workspace_id="ws-1",
                    timestamp=old_ts,
                ),
            )
        summary = m.archive_expired(now=datetime.now())
        # MinIO 失败 -> 跳过 (不删除本地行)
        assert summary["archived_count"] == 0
        assert _count_events(audit_db_path) == 3

    def test_batch_size_respected(self, ret_module, audit_db_path, mock_minio):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        old_ts = datetime.now() - timedelta(days=200)
        for i in range(5):
            _insert_event(
                audit_db_path,
                _make_event(
                    event_id=f"b-{i}", workspace_id="ws-1", timestamp=old_ts
                ),
            )
        # batch_size=2: 5 个事件分 3 批 (2+2+1)
        m.archive_expired(now=datetime.now(), batch_size=2)
        assert mock_minio.upload_object.call_count == 3
        assert _count_events(audit_db_path) == 0


# ---------------------------------------------------------------------------
# TestQueryArchived
# ---------------------------------------------------------------------------


class TestQueryArchived:
    def test_query_returns_archived_events(
        self, ret_module, audit_db_path, mock_minio
    ):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        # 先归档
        old_ts = datetime.now() - timedelta(days=200)
        _insert_event(
            audit_db_path,
            _make_event(
                event_id="q-1", workspace_id="ws-1", timestamp=old_ts
            ),
        )
        m.archive_expired(now=datetime.now())

        # 重新设置 download_object 返回压缩 payload
        # 从上次 upload_object 抓取 data 作为回放
        upload_args, _ = mock_minio.upload_object.call_args
        data = upload_args[2] if len(upload_args) > 2 else _
        mock_minio.download_object = MagicMock(
            return_value={"status": "success", "data": data, "size": len(data)}
        )

        start = datetime.now() - timedelta(days=365)
        end = datetime.now() + timedelta(days=1)
        events = m.query_archived("ws-1", start, end)
        assert len(events) == 1
        assert events[0]["id"] == "q-1"

    def test_query_filters_by_workspace(
        self, ret_module, audit_db_path, mock_minio
    ):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        old_ts = datetime.now() - timedelta(days=200)
        _insert_event(
            audit_db_path,
            _make_event(
                event_id="w-1", workspace_id="ws-a", timestamp=old_ts
            ),
        )
        m.archive_expired(now=datetime.now())
        upload_args, _ = mock_minio.upload_object.call_args
        data = upload_args[2] if len(upload_args) > 2 else _
        mock_minio.download_object = MagicMock(
            return_value={"status": "success", "data": data, "size": len(data)}
        )
        events = m.query_archived(
            "ws-b", datetime.now() - timedelta(days=365), datetime.now()
        )
        assert events == []

    def test_query_time_range(
        self, ret_module, audit_db_path, mock_minio
    ):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        old_ts = datetime.now() - timedelta(days=200)
        _insert_event(
            audit_db_path,
            _make_event(
                event_id="t-1", workspace_id="ws-1", timestamp=old_ts
            ),
        )
        m.archive_expired(now=datetime.now())
        upload_args, _ = mock_minio.upload_object.call_args
        data = upload_args[2] if len(upload_args) > 2 else _
        mock_minio.download_object = MagicMock(
            return_value={"status": "success", "data": data, "size": len(data)}
        )
        # 时间范围在归档之前 -> 无结果
        events = m.query_archived(
            "ws-1",
            datetime(2000, 1, 1),
            datetime(2000, 12, 31),
        )
        assert events == []


# ---------------------------------------------------------------------------
# TestArchiveIndex
# ---------------------------------------------------------------------------


class TestArchiveIndex:
    def test_index_empty_for_unknown_workspace(
        self, ret_module, manager
    ):
        assert manager.get_archive_index("nonexistent") == []

    def test_index_lists_multiple_archives(
        self, ret_module, audit_db_path, mock_minio
    ):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        # 第一次归档: 插入一个过期事件并立即归档
        ts1 = datetime.now() - timedelta(days=400)
        _insert_event(
            audit_db_path,
            _make_event(event_id="a-1", workspace_id="ws-x", timestamp=ts1),
        )
        m.archive_expired(now=datetime.now() - timedelta(days=300))
        # 第二次归档: 插入另一个过期事件并归档
        ts2 = datetime.now() - timedelta(days=200)
        _insert_event(
            audit_db_path,
            _make_event(event_id="a-2", workspace_id="ws-x", timestamp=ts2),
        )
        m.archive_expired(now=datetime.now())
        index = m.get_archive_index("ws-x")
        assert len(index) == 2
        keys = {r["minio_key"] for r in index}
        assert len(keys) == 2


# ---------------------------------------------------------------------------
# TestPolicyUpsert
# ---------------------------------------------------------------------------


class TestPolicyUpsert:
    def test_upsert_replaces_existing(
        self, ret_module, audit_db_path, mock_minio
    ):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        p1 = ret_module.RetentionPolicy(
            ws_id="ws-1",
            classification="*",
            retention_days=10,
            action=ret_module.RetentionAction.HARD_DELETE,
            created_at=datetime.now(),
        )
        m.upsert_policy(p1)
        p2 = ret_module.RetentionPolicy(
            ws_id="ws-1",
            classification="*",
            retention_days=99,
            action=ret_module.RetentionAction.ARCHIVE_TO_MINIO,
            created_at=datetime.now(),
        )
        m.upsert_policy(p2)
        result = m.get_retention_policy("ws-1", "C")
        assert result.retention_days == 99
        assert result.action == ret_module.RetentionAction.ARCHIVE_TO_MINIO


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_default_now(self, ret_module, audit_db_path, mock_minio):
        m = ret_module.AuditRetentionManager(
            db_path=audit_db_path, minio_client=mock_minio
        )
        # 不传 now: 内部使用 datetime.now()，不应抛错
        summary = m.archive_expired()
        assert "archived_count" in summary

    def test_event_with_string_timestamp(
        self, ret_module, manager
    ):
        # DB 中 timestamp 是 ISO 字符串; is_expired 需兼容
        ev = {
            "id": "s-1",
            "timestamp": (datetime.now() - timedelta(days=200)).isoformat(),
            "event_type": "user.login",
            "severity": "info",
            "actor_type": "user",
            "actor_id": "u",
            "actor_name": "u",
            "action": "a",
            "resource_type": "r",
            "resource_id": "r",
            "result_status": "ok",
            "workspace_id": "default",
            "trace_id": "t",
            "context": "{}",
            "changes": "{}",
            "checksum": "x",
        }
        assert manager.is_expired(ev, datetime.now()) is True

    def test_event_with_datetime_timestamp(
        self, ret_module, manager
    ):
        ev = _make_event(timestamp=datetime.now() - timedelta(days=200))
        assert manager.is_expired(ev, datetime.now()) is True
