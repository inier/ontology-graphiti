"""
审计日志系统 v2
支持异步 Channel、批量落盘、CRITICAL 同步写入、防篡改校验链

功能：
- 异步 Channel + 批量落盘
- CRITICAL 级别同步写入
- 防篡改校验链（SHA-256 链式哈希）
- 时间线查询 API
"""

import sys
import os
import json
import time
import asyncio
import hashlib
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import deque
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AuditSeverityV2(Enum):
    """审计级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEventTypeV2(Enum):
    """审计事件类型"""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    DATA_ACCESS = "data_access"
    DATA_MODIFY = "data_modify"
    DATA_DELETE = "data_delete"
    PERMISSION_CHECK = "permission_check"
    PERMISSION_DENIED = "permission_denied"
    API_CALL = "api_call"
    WORKSPACE_CREATE = "workspace_create"
    WORKSPACE_DELETE = "workspace_delete"
    SCENARIO_CREATE = "scenario_create"
    SCENARIO_MODIFY = "scenario_modify"
    ONTOLOGY_COMMIT = "ontology_commit"
    SYSTEM_ERROR = "system_error"


@dataclass
class AuditEventV2:
    """审计事件"""
    event_id: str
    timestamp: str
    event_type: str
    severity: str
    actor_id: str
    actor_name: str
    action: str
    resource_type: str
    resource_id: str
    result: str
    message: str
    workspace_id: Optional[str] = None
    trace_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    duration_ms: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    previous_hash: Optional[str] = None
    current_hash: Optional[str] = None


@dataclass
class HashChainEntry:
    """哈希链条目"""
    event_id: str
    timestamp: str
    hash: str
    previous_hash: str
    sequence: int


class AsyncAuditChannelV2:
    """异步审计 Channel - 支持批量落盘"""

    def __init__(self, db_path: str = None, batch_size: int = 100, flush_interval_ms: int = 1000):
        self.db_path = db_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "audit_v2.db"
        )
        self.batch_size = batch_size
        self.flush_interval_ms = flush_interval_ms
        self._buffer: List[AuditEventV2] = []
        self._lock = threading.Lock()
        self._last_flush_time = time.time()
        self._running = True
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._init_db()
        self._start_flush_thread()

    def _init_db(self):
        """初始化数据库"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                actor_name TEXT,
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id TEXT,
                result TEXT NOT NULL,
                message TEXT,
                workspace_id TEXT,
                trace_id TEXT,
                parent_event_id TEXT,
                duration_ms INTEGER,
                metadata TEXT,
                previous_hash TEXT,
                current_hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_events(timestamp)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_workspace ON audit_events(workspace_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_event_type ON audit_events(event_type)
        ''')
        conn.commit()
        conn.close()

    def _start_flush_thread(self):
        """启动定期刷新线程"""
        def flush_loop():
            while self._running:
                time.sleep(self.flush_interval_ms / 1000.0)
                self._check_flush()
                if not self._running:
                    break

        thread = threading.Thread(target=flush_loop, daemon=True)
        thread.start()

    def _check_flush(self):
        """检查是否需要刷新"""
        with self._lock:
            if not self._buffer:
                return

            time_since_last = (time.time() - self._last_flush_time) * 1000
            if (len(self._buffer) >= self.batch_size or
                time_since_last >= self.flush_interval_ms):
                self._flush_buffer()

    def _flush_buffer(self):
        """刷新缓冲区到数据库"""
        if not self._buffer:
            return

        events_to_write = self._buffer.copy()
        self._buffer.clear()
        self._last_flush_time = time.time()

        self._executor.submit(self._write_to_db, events_to_write)

    def _write_to_db(self, events: List[AuditEventV2]):
        """写入数据库"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            for event in events:
                cursor.execute('''
                    INSERT OR REPLACE INTO audit_events
                    (event_id, timestamp, event_type, severity, actor_id, actor_name, action,
                     resource_type, resource_id, result, message, workspace_id, trace_id,
                     parent_event_id, duration_ms, metadata, previous_hash, current_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event.event_id,
                    event.timestamp,
                    event.event_type,
                    event.severity,
                    event.actor_id,
                    event.actor_name,
                    event.action,
                    event.resource_type,
                    event.resource_id,
                    event.result,
                    event.message,
                    event.workspace_id,
                    event.trace_id,
                    event.parent_event_id,
                    event.duration_ms,
                    json.dumps(event.metadata, default=str),
                    event.previous_hash,
                    event.current_hash
                ))
            conn.commit()
        except Exception as e:
            print(f"审计日志写入失败: {e}")
        finally:
            conn.close()

    def write(self, event: AuditEventV2):
        """写入事件"""
        with self._lock:
            if event.severity == AuditSeverityV2.CRITICAL.value:
                self._flush_buffer()
                self._write_to_db([event])
                return

            self._buffer.append(event)
            if len(self._buffer) >= self.batch_size:
                self._flush_buffer()

    def write_sync(self, event: AuditEventV2):
        """同步写入（用于 CRITICAL 级别）"""
        self._write_to_db([event])

    def flush(self):
        """强制刷新缓冲区"""
        with self._lock:
            self._flush_buffer()

    def query(self, filter: Dict) -> List[AuditEventV2]:
        """查询事件"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM audit_events WHERE 1=1"
        params = []

        if filter.get("start_time"):
            query += " AND timestamp >= ?"
            params.append(filter["start_time"])
        if filter.get("end_time"):
            query += " AND timestamp <= ?"
            params.append(filter["end_time"])
        if filter.get("workspace_id"):
            query += " AND workspace_id = ?"
            params.append(filter["workspace_id"])
        if filter.get("event_type"):
            query += " AND event_type = ?"
            params.append(filter["event_type"])
        if filter.get("severity"):
            query += " AND severity = ?"
            params.append(filter["severity"])

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(filter.get("limit", 1000))

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        events = []
        for row in rows:
            events.append(AuditEventV2(
                event_id=row[0], timestamp=row[1], event_type=row[2], severity=row[3],
                actor_id=row[4], actor_name=row[5], action=row[6], resource_type=row[7],
                resource_id=row[8], result=row[9], message=row[10], workspace_id=row[11],
                trace_id=row[12], parent_event_id=row[13], duration_ms=row[14],
                metadata=json.loads(row[15]) if row[15] else {},
                previous_hash=row[16], current_hash=row[17]
            ))
        return events

    def close(self):
        """关闭"""
        self._running = False
        self.flush()


class HashChainV2:
    """防篡改校验链"""

    def __init__(self, channel: AsyncAuditChannelV2):
        self.channel = channel
        self._last_hash: Optional[str] = None
        self._sequence = 0
        self._lock = threading.Lock()
        self._load_last_hash()

    def _load_last_hash(self):
        """加载上一个哈希"""
        events = self.channel.query({"limit": 1})
        if events:
            self._last_hash = events[0].current_hash
            self._sequence = int(events[0].event_id.split("-")[-1]) if "-" in events[0].event_id else 0

    def compute_hash(self, event: AuditEventV2) -> str:
        """计算事件哈希"""
        data = f"{event.event_id}|{event.timestamp}|{event.event_type}|{event.actor_id}|{event.action}|{event.result}|{self._last_hash or ''}"
        return hashlib.sha256(data.encode()).hexdigest()

    def add_event(self, event: AuditEventV2) -> AuditEventV2:
        """添加事件并计算哈希"""
        with self._lock:
            event.previous_hash = self._last_hash
            event.current_hash = self.compute_hash(event)
            self._last_hash = event.current_hash
            self._sequence += 1
            return event

    def verify_chain(self) -> Dict[str, Any]:
        """验证链完整性"""
        events = self.channel.query({"limit": 10000})
        if not events:
            return {"valid": True, "total_events": 0}

        valid = True
        last_hash = None
        broken_at = None

        for event in reversed(events):
            if last_hash is None:
                last_hash = event.current_hash
                continue

            if event.current_hash != last_hash:
                valid = False
                broken_at = event.event_id
                break
            last_hash = event.previous_hash

        return {
            "valid": valid,
            "total_events": len(events),
            "broken_at": broken_at,
            "first_event": events[0].event_id if events else None,
            "last_event": events[-1].event_id if events else None
        }

    def verify_event(self, event: AuditEventV2) -> bool:
        """验证单个事件"""
        expected_hash = self.compute_hash(event)
        return event.current_hash == expected_hash


class AuditTimelineV2:
    """审计时间线"""

    def __init__(self, channel: AsyncAuditChannelV2):
        self.channel = channel

    def get_timeline(self, workspace_id: Optional[str] = None,
                   start_time: Optional[str] = None,
                   end_time: Optional[str] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        """获取时间线"""
        filter = {"limit": limit}
        if workspace_id:
            filter["workspace_id"] = workspace_id
        if start_time:
            filter["start_time"] = start_time
        if end_time:
            filter["end_time"] = end_time

        events = self.channel.query(filter)

        timeline = []
        for event in events:
            timeline.append({
                "event_id": event.event_id,
                "timestamp": event.timestamp,
                "event_type": event.event_type,
                "severity": event.severity,
                "actor": {"id": event.actor_id, "name": event.actor_name},
                "action": event.action,
                "resource": {"type": event.resource_type, "id": event.resource_id},
                "result": event.result,
                "message": event.message,
                "duration_ms": event.duration_ms,
                "metadata": event.metadata
            })

        return timeline

    def get_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """获取追踪链"""
        events = self.channel.query({"trace_id": trace_id, "limit": 1000})
        return sorted([{
            "event_id": e.event_id,
            "timestamp": e.timestamp,
            "event_type": e.event_type,
            "actor_id": e.actor_id,
            "action": e.action,
            "result": e.result,
            "parent_event_id": e.parent_event_id
        } for e in events], key=lambda x: x["timestamp"])


class AuditLoggerV2:
    """
    审计日志系统 v2

    功能：
    - 异步 Channel + 批量落盘
    - CRITICAL 级别同步写入
    - 防篡改校验链（SHA-256）
    - 时间线查询 API
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = None):
        if hasattr(self, '_initialized'):
            return

        self._channel = AsyncAuditChannelV2(db_path)
        self._hash_chain = HashChainV2(self._channel)
        self._timeline = AuditTimelineV2(self._channel)
        self._initialized = True

    def log(self, event_type: str, action: str, actor_id: str,
           resource_type: str, resource_id: str, result: str,
           severity: str = "info", message: str = "",
           workspace_id: Optional[str] = None,
           trace_id: Optional[str] = None,
           parent_event_id: Optional[str] = None,
           duration_ms: Optional[int] = None,
           metadata: Optional[Dict] = None) -> AuditEventV2:
        """记录审计事件"""
        import uuid
        now = datetime.now(timezone.utc).isoformat()
        event_id = f"audit-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"

        event = AuditEventV2(
            event_id=event_id,
            timestamp=now,
            event_type=event_type,
            severity=severity,
            actor_id=actor_id,
            actor_name="",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            message=message,
            workspace_id=workspace_id,
            trace_id=trace_id,
            parent_event_id=parent_event_id,
            duration_ms=duration_ms,
            metadata=metadata or {}
        )

        event = self._hash_chain.add_event(event)

        self._channel.write(event)

        return event

    def log_critical(self, event_type: str, action: str, actor_id: str,
                    resource_type: str, resource_id: str, message: str,
                    **kwargs) -> AuditEventV2:
        """记录 CRITICAL 事件（同步写入）"""
        event = self.log(event_type, action, actor_id, resource_type, resource_id,
                         result="critical", severity="critical", message=message, **kwargs)
        self._channel.flush()
        return event

    def query(self, filter: Dict) -> List[AuditEventV2]:
        """查询事件"""
        return self._channel.query(filter)

    def get_timeline(self, **kwargs) -> List[Dict[str, Any]]:
        """获取时间线"""
        return self._timeline.get_timeline(**kwargs)

    def get_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """获取追踪链"""
        return self._timeline.get_trace(trace_id)

    def verify_integrity(self) -> Dict[str, Any]:
        """验证完整性"""
        return self._hash_chain.verify_chain()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        events = self._channel.query({"limit": 10000})
        severity_counts = {}
        event_type_counts = {}

        for e in events:
            severity_counts[e.severity] = severity_counts.get(e.severity, 0) + 1
            event_type_counts[e.event_type] = event_type_counts.get(e.event_type, 0) + 1

        return {
            "total_events": len(events),
            "severity_counts": severity_counts,
            "event_type_counts": event_type_counts,
            "integrity": self.verify_integrity()
        }

    def close(self):
        """关闭"""
        self._channel.close()


def get_audit_logger_v2(db_path: str = None) -> AuditLoggerV2:
    """获取审计日志器实例"""
    return AuditLoggerV2(db_path)


if __name__ == "__main__":
    logger = get_audit_logger_v2()

    print("审计日志系统 v2 初始化完成")

    print("\n测试记录事件:")
    event1 = logger.log(
        event_type="user_login",
        action="login",
        actor_id="user001",
        resource_type="session",
        resource_id="session123",
        result="success",
        message="用户登录成功",
        workspace_id="ws001",
        severity="info"
    )
    print(f"  记录事件: {event1.event_id}")
    print(f"  哈希: {event1.current_hash[:16]}...")

    event2 = logger.log(
        event_type="data_modify",
        action="update",
        actor_id="user001",
        resource_type="document",
        resource_id="doc001",
        result="success",
        message="文档更新",
        workspace_id="ws001",
        trace_id=event1.event_id,
        severity="warning"
    )

    logger.log_critical(
        event_type="permission_denied",
        action="delete",
        actor_id="user002",
        resource_type="workspace",
        resource_id="ws001",
        message="权限不足",
        workspace_id="ws001"
    )

    print("\n测试时间线:")
    timeline = logger.get_timeline(workspace_id="ws001", limit=10)
    print(f"  时间线事件数: {len(timeline)}")

    print("\n测试完整性验证:")
    integrity = logger.verify_integrity()
    print(f"  完整链: {integrity['valid']}")
    print(f"  总事件数: {integrity['total_events']}")

    print("\n测试统计:")
    stats = logger.get_stats()
    print(f"  总事件数: {stats['total_events']}")
    print(f"  严重级别分布: {stats['severity_counts']}")

    logger.close()
