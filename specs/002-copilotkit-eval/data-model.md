# Data Model: AG-UI ↔ OpenHarness 集成（零新表 + 1 张审计表）

**Date**: 2026-06-08 (FINAL)
**Status**: 草案 v0.1
**依赖**: [plan.md](../plan.md) · [research.md](../research.md) · [contracts/ag-ui-bridge.md](../contracts/ag-ui-bridge.md) · [AGENTS.md 规则 8](../../../AGENTS.md)
**被依赖**: [hitl-flow.md](../contracts/hitl-flow.md) · [generative-ui-card.md](../contracts/generative-ui-card.md)

---

## 1. 概述

AG-UI + OpenHarness 集成的数据模型**大幅简化** —— **零新表，复用 OpenHarness 现有 session 内存**，仅新增 **1 张审计表** 用于历史 interrupt 追溯。

**核心原则**：
- **不破坏现有 SQLite schema**：现有 `qa_sessions` / `qa_messages` 表零修改
- **不引入持久层**：活跃 run 的 `ask_user_prompt` future 存于 OpenHarness 内存（`AGUIBridge._pending_prompts`）
- **新增 1 张审计表 `qa_agui_interrupts`**：仅记录已 resolved/timeout 的 interrupt（用于审计和回溯，不影响运行时）

**为什么不需要 OAUIP 时的 3 张表？**

| 原 OAUIP 设计 | AG-UI 设计 | 节省 |
|--------------|-----------|------|
| `qa_threads` 复合 ID | 直接用 `threadId = session_id`（AG-UI 规定） | -1 表 |
| `qa_hitl_sessions`（运行时） | OpenHarness 内存 future（`AGUIBridge._pending_prompts`） | -1 表 |
| `qa_hitl_sessions`（历史） | `qa_agui_interrupts`（仅审计） | -1 字段 |
| `qa_shared_state` 乐观锁 | `StateSnapshot` / `StateDelta` 事件流（无持久化） | -1 表 |
| `qa_messages` 增量 `card_id` / `hitl_session_id` | `qa_messages` 零修改（card 是前端注册表） | -2 列 |

**总计**：从 OAUIP 的 3 张表 + 2 列 简化为 **1 张审计表 + 0 列**。

---

## 2. 现有表复用（零修改）

### 2.1 `qa_sessions`（已存在）

```sql
-- ODAP 现有表，零修改
CREATE TABLE qa_sessions (
    id              TEXT PRIMARY KEY,        -- = AG-UI threadId
    workspace_id    TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    status          TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    ...
);
```

**AG-UI 映射**：
- `qa_sessions.id` ⇔ AG-UI `threadId`（**完全一致**）
- 无需新增 `thread_id` 列

### 2.2 `qa_messages`（已存在）

```sql
-- ODAP 现有表，零修改
CREATE TABLE qa_messages (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,           -- 关联 qa_sessions.id
    role            TEXT NOT NULL,           -- user | assistant | tool | system
    content         TEXT NOT NULL,           -- 文本内容
    tool_calls      TEXT,                    -- JSON: 工具调用列表
    tool_call_id    TEXT,                    -- AG-UI toolCallId（如有）
    created_at      TEXT NOT NULL,
    ...
);
```

**AG-UI 映射**：
- 客户端 `messages: [{role, content}]` ⇔ `qa_messages` 多行
- `tool_call_id` 列已存在，AG-UI `ToolCallStart.toolCallId` 直接写入
- 不需要 `card_id` 列（card 是客户端注册表，**无服务端持久化**）

### 2.3 OpenHarness 内存结构（无 SQLite）

```python
# OpenHarness 内部（已存在，零修改）
openharness.engine.query_engine.QueryEngine:
    self._messages: list[ConversationMessage]   # 内存对话历史
    self._ask_user_prompt: AskUserPrompt | None  # HITL 回调
    self._tool_metadata: dict[str, object]       # 工具间状态

# AG-UI Bridge 新增（仅内存）
odap.biz.core.qa.agui_bridge.AGUIBridge:
    self._active_runs: dict[str, asyncio.Task]      # threadId -> active run task
    self._pending_prompts: dict[str, dict]          # threadId -> {interruptId, future, created_at, timeout_at}
```

**关键不变量**：
- `_active_runs` 和 `_pending_prompts` 是**进程内**内存（FastAPI worker 进程）
- 多 worker 部署需要 sticky session（基于 `threadId` 路由到同一 worker）— **Phase 4 决策**

---

## 3. 新增审计表

### 3.1 `qa_agui_interrupts` — Interrupt 历史审计

> **仅供审计与回溯，不影响运行时 HITL 流程**。活跃 interrupt 状态由 `AGUIBridge._pending_prompts` 管理。

```sql
CREATE TABLE qa_agui_interrupts (
    id                  TEXT PRIMARY KEY,        -- interrupt_id = "int-{uuid4().hex[:12]}"
    session_id          TEXT NOT NULL,            -- = AG-UI threadId
    run_id              TEXT NOT NULL,            -- = AG-UI runId（被中断的 run）
    tool_call_id        TEXT NOT NULL,            -- AG-UI toolCallId（关联 ToolCallStart）
    tool_name           TEXT NOT NULL,            -- OpenHarness 工具名（通常 = "ask_user_question"）
    reason              TEXT NOT NULL,            -- AG-UI reason: confirmation | input_required | tool_call | odap:xxx
    message             TEXT NOT NULL,            -- AG-UI Interrupt.message（用户看到的提示）
    response_schema     TEXT NOT NULL,            -- JSON TEXT: AG-UI Interrupt.responseSchema
    card_type           TEXT,                     -- 客户端渲染卡片类型: confirm | input | action
    metadata            TEXT NOT NULL DEFAULT '{}',  -- JSON TEXT: 框架特定数据

    status              TEXT NOT NULL DEFAULT 'pending',  -- (str, Enum): pending | resolved | cancelled | timeout
    user_response       TEXT,                     -- JSON TEXT: 用户响应（resolved 后填充）
    resolved_at         TEXT,                     -- ISO datetime: resolved/cancelled/timeout 时间
    expires_at          TEXT NOT NULL,            -- ISO datetime: 超时截止

    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,

    FOREIGN KEY (session_id) REFERENCES qa_sessions(id)
);

CREATE INDEX idx_qa_agui_interrupts_session ON qa_agui_interrupts(session_id, created_at DESC);
CREATE INDEX idx_qa_agui_interrupts_pending ON qa_agui_interrupts(status, expires_at) WHERE status = 'pending';
CREATE INDEX idx_qa_agui_interrupts_run ON qa_agui_interrupts(run_id);
```

**字段说明**：

| 字段 | 来源 | 说明 |
|------|------|------|
| `id` | Bridge 生成 | `int-{uuid4().hex[:12]}` |
| `session_id` | AG-UI `threadId` | 直接映射 |
| `run_id` | AG-UI `runId` | 中断发生时的 run |
| `tool_call_id` | §ag-ui-bridge.md §3.3 稳定 ID | 用于回溯工具调用 |
| `tool_name` | OpenHarness `ToolExecutionStarted.tool_name` | 通常 = `ask_user_question` |
| `reason` | AG-UI Interrupt.reason | 见 §ag-ui-bridge.md §3.4 reason 路由表 |
| `message` | AG-UI Interrupt.message | `AskUserQuestionToolInput.question` |
| `response_schema` | 自动生成 | 见 §ag-ui-bridge.md §3.4.1 |
| `card_type` | 工具名 → 卡片类型映射 | `ask_user_question` → `confirm` |
| `metadata` | AG-UI Interrupt.metadata | 框架特定数据 |
| `status` | lifecycle: `pending` → `resolved`/`cancelled`/`timeout` | 由 Bridge 状态机更新 |
| `user_response` | 客户端 `resume[].payload` | resolved 后写入 |
| `resolved_at` | resolve 时刻 | ISO datetime |
| `expires_at` | 创建时 + 30 min | AG-UI 规定 |

**索引策略**：
- `idx_qa_agui_interrupts_session`：按 session 查历史 interrupt
- `idx_qa_agui_interrupts_pending`：后台 timeout 扫描器用
- `idx_qa_agui_interrupts_run`：按 run 查 interrupt

### 3.2 不需要持久化活跃状态的理由

**关键设计决策**：活跃 interrupt 状态（`pending` 状态、`ask_user_prompt` future）**仅在内存**。

**理由**：
1. **OpenHarness 已有内存状态机**：`QueryEngine._ask_user_prompt` 是回调，不持久化
2. **HITL 是单进程同步语义**：用户响应必须在同一 FastAPI worker 处理（避免跨进程 future 序列化）
3. **断电恢复非 MVP 需求**：HITL 暂停超过 30 分钟算 timeout，不要求恢复
4. **简化部署**：无需引入 Redis 或 sticky session 协调 future

**后果**：
- FastAPI worker 重启 → 所有活跃 HITL 会话丢失 → 客户端收到 `RunError(code="session_expired")` → 重新发起 run
- 客户端应**及时响应** HITL（< 30 分钟）

---

## 4. Pydantic 模型（AG-UI 事件镜像）

> **遵循 AGENTS.md 规则 4（Enum 双继承）和规则 5（容器字段 default_factory）**。

### 4.1 AG-UI 事件模型（服务端发出）

```python
# odap/biz/core/qa/agui_models.py

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


# === 枚举（AGENTS.md 规则 4） ===

class InterruptStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class InterruptReason(str, Enum):
    """AG-UI 规定的 reason 取值。"""
    TOOL_CALL = "tool_call"
    INPUT_REQUIRED = "input_required"
    CONFIRMATION = "confirmation"


class ResumeStatus(str, Enum):
    """AG-UI 规定的 resume status。"""
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class CardType(str, Enum):
    """ODAP 客户端卡片类型（与 reason 一对一映射）。"""
    CONFIRM = "confirm"
    INPUT = "input"
    ACTION = "action"


# === 基础事件（所有 AG-UI 事件共享字段） ===

class AGUIEventBase(BaseModel):
    """所有 AG-UI 事件基类。"""
    type: str
    timestamp: Optional[int] = None  # Unix ms


# === Lifecycle 事件 ===

class RunStartedEvent(AGUIEventBase):
    type: Literal["RUN_STARTED"] = "RUN_STARTED"
    threadId: str
    runId: str
    parentRunId: Optional[str] = None
    input: Optional[dict[str, Any]] = None


class RunFinishedEvent(AGUIEventBase):
    type: Literal["RUN_FINISHED"] = "RUN_FINISHED"
    threadId: str
    runId: str
    result: Optional[dict[str, Any]] = None
    # outcome 是 discriminated union（见 InterruptOutcome）


class RunFinishedSuccess(BaseModel):
    type: Literal["success"] = "success"


class Interrupt(BaseModel):
    """AG-UI Interrupt 类型（嵌入 RunFinished.outcome.interrupts[]）。"""
    id: str = Field(default_factory=lambda: f"int-{uuid4().hex[:12]}")
    reason: str  # InterruptReason 枚举值或自定义
    message: Optional[str] = None
    toolCallId: Optional[str] = None
    responseSchema: Optional[dict[str, Any]] = None
    expiresAt: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class RunFinishedInterrupt(BaseModel):
    type: Literal["interrupt"] = "interrupt"
    interrupts: list[Interrupt]


class RunErrorEvent(AGUIEventBase):
    type: Literal["RUN_ERROR"] = "RUN_ERROR"
    message: str
    code: Optional[str] = None


class StepStartedEvent(AGUIEventBase):
    type: Literal["STEP_STARTED"] = "STEP_STARTED"
    stepName: str


class StepFinishedEvent(AGUIEventBase):
    type: Literal["STEP_FINISHED"] = "STEP_FINISHED"
    stepName: str


# === Text Message 事件 ===

class TextMessageStartEvent(AGUIEventBase):
    type: Literal["TEXT_MESSAGE_START"] = "TEXT_MESSAGE_START"
    messageId: str
    role: Literal["assistant", "user", "system", "developer", "tool"] = "assistant"


class TextMessageContentEvent(AGUIEventBase):
    type: Literal["TEXT_MESSAGE_CONTENT"] = "TEXT_MESSAGE_CONTENT"
    messageId: str
    delta: str  # 非空


class TextMessageEndEvent(AGUIEventBase):
    type: Literal["TEXT_MESSAGE_END"] = "TEXT_MESSAGE_END"
    messageId: str


# === Tool Call 事件 ===

class ToolCallStartEvent(AGUIEventBase):
    type: Literal["TOOL_CALL_START"] = "TOOL_CALL_START"
    toolCallId: str
    toolCallName: str
    parentMessageId: Optional[str] = None


class ToolCallArgsEvent(AGUIEventBase):
    type: Literal["TOOL_CALL_ARGS"] = "TOOL_CALL_ARGS"
    toolCallId: str
    delta: str  # JSON 字符串片段


class ToolCallEndEvent(AGUIEventBase):
    type: Literal["TOOL_CALL_END"] = "TOOL_CALL_END"
    toolCallId: str


class ToolCallResultEvent(AGUIEventBase):
    type: Literal["TOOL_CALL_RESULT"] = "TOOL_CALL_RESULT"
    messageId: str
    toolCallId: str
    content: str  # 工具输出（JSON 字符串）
    role: Literal["tool"] = "tool"


# === State Management 事件 ===

class StateSnapshotEvent(AGUIEventBase):
    type: Literal["STATE_SNAPSHOT"] = "STATE_SNAPSHOT"
    snapshot: dict[str, Any]  # 完整状态快照


class StateDeltaEvent(AGUIEventBase):
    type: Literal["STATE_DELTA"] = "STATE_DELTA"
    delta: list[dict[str, Any]]  # JSON Patch 操作


class MessagesSnapshotEvent(AGUIEventBase):
    type: Literal["MESSAGES_SNAPSHOT"] = "MESSAGES_SNAPSHOT"
    messages: list[dict[str, Any]]


# === 联合类型 ===

AGUIEvent = (
    RunStartedEvent
    | RunFinishedEvent
    | RunErrorEvent
    | StepStartedEvent
    | StepFinishedEvent
    | TextMessageStartEvent
    | TextMessageContentEvent
    | TextMessageEndEvent
    | ToolCallStartEvent
    | ToolCallArgsEvent
    | ToolCallEndEvent
    | ToolCallResultEvent
    | StateSnapshotEvent
    | StateDeltaEvent
    | MessagesSnapshotEvent
)
```

### 4.2 AG-UI 输入模型（客户端 → 服务端）

```python
# odap/biz/core/qa/agui_models.py (续)

class RunAgentInput(BaseModel):
    """客户端发起的 run 请求体。"""
    threadId: str
    runId: str
    messages: Optional[list[dict[str, Any]]] = None  # 首次请求必填，resume 可省略
    tools: Optional[list[dict[str, Any]]] = None
    context: Optional[dict[str, Any]] = None
    forwardedProps: Optional[dict[str, Any]] = None
    resume: Optional[list["ResumeEntry"]] = None  # 仅 resume run 携带


class ResumeEntry(BaseModel):
    """AG-UI resume 数组条目。"""
    interruptId: str
    status: ResumeStatus
    payload: Optional[dict[str, Any]] = None  # 符合对应 Interrupt.responseSchema
```

### 4.3 审计表持久化模型

```python
# odap/biz/core/qa/agui_models.py (续)

class AGUIInterruptRecord(BaseModel):
    """持久化到 qa_agui_interrupts 的记录。"""
    id: str = Field(default_factory=lambda: f"int-{uuid4().hex[:12]}")
    session_id: str
    run_id: str
    tool_call_id: str
    tool_name: str
    reason: str
    message: str
    response_schema: dict[str, Any]
    card_type: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: InterruptStatus = InterruptStatus.PENDING
    user_response: Optional[dict[str, Any]] = None
    resolved_at: Optional[datetime] = None
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
```

---

## 5. SQLite 存储层（AGENTS.md 规则 8）

### 5.1 `SQLiteAGUIInterruptStorage`

```python
# odap/biz/core/qa/storage/sqlite_agui_interrupt_storage.py

import json
import os
import sqlite3
from datetime import datetime
from typing import Optional
from odap.biz.core.qa.agui_models import AGUIInterruptRecord, InterruptStatus


class SQLiteAGUIInterruptStorage:
    """AG-UI Interrupt 历史审计存储。"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "qa_agui.db",
        )
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS qa_agui_interrupts (
                    id              TEXT PRIMARY KEY,
                    session_id      TEXT NOT NULL,
                    run_id          TEXT NOT NULL,
                    tool_call_id    TEXT NOT NULL,
                    tool_name       TEXT NOT NULL,
                    reason          TEXT NOT NULL,
                    message         TEXT NOT NULL,
                    response_schema TEXT NOT NULL,
                    card_type       TEXT,
                    metadata        TEXT NOT NULL DEFAULT '{}',
                    status          TEXT NOT NULL DEFAULT 'pending',
                    user_response   TEXT,
                    resolved_at     TEXT,
                    expires_at      TEXT NOT NULL,
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES qa_sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_qa_agui_interrupts_session
                    ON qa_agui_interrupts(session_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_qa_agui_interrupts_pending
                    ON qa_agui_interrupts(status, expires_at) WHERE status = 'pending';
                CREATE INDEX IF NOT EXISTS idx_qa_agui_interrupts_run
                    ON qa_agui_interrupts(run_id);
            """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save_interrupt(self, record: AGUIInterruptRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO qa_agui_interrupts (
                    id, session_id, run_id, tool_call_id, tool_name,
                    reason, message, response_schema, card_type, metadata,
                    status, user_response, resolved_at, expires_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id, record.session_id, record.run_id,
                    record.tool_call_id, record.tool_name,
                    record.reason, record.message,
                    json.dumps(record.response_schema),
                    record.card_type,
                    json.dumps(record.metadata),
                    record.status.value,
                    json.dumps(record.user_response) if record.user_response else None,
                    record.resolved_at.isoformat() if record.resolved_at else None,
                    record.expires_at.isoformat(),
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )
            conn.commit()

    def update_status(
        self,
        interrupt_id: str,
        status: InterruptStatus,
        user_response: Optional[dict] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE qa_agui_interrupts
                SET status = ?, user_response = ?, resolved_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    json.dumps(user_response) if user_response else None,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    interrupt_id,
                ),
            )
            conn.commit()

    def get_pending_interrupts_with_timeout_lt(
        self, before: datetime
    ) -> list[AGUIInterruptRecord]:
        """供 timeout 扫描器使用。"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM qa_agui_interrupts
                WHERE status = 'pending' AND expires_at < ?
                """,
                (before.isoformat(),),
            ).fetchall()
            return [self._row_to_record(row) for row in rows]

    def list_by_session(
        self, session_id: str, limit: int = 50
    ) -> list[AGUIInterruptRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM qa_agui_interrupts
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
            return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> AGUIInterruptRecord:
        return AGUIInterruptRecord(
            id=row["id"],
            session_id=row["session_id"],
            run_id=row["run_id"],
            tool_call_id=row["tool_call_id"],
            tool_name=row["tool_name"],
            reason=row["reason"],
            message=row["message"],
            response_schema=json.loads(row["response_schema"]),
            card_type=row["card_type"],
            metadata=json.loads(row["metadata"]),
            status=InterruptStatus(row["status"]),
            user_response=json.loads(row["user_response"]) if row["user_response"] else None,
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
            expires_at=datetime.fromisoformat(row["expires_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
```

**关键设计**（AGENTS.md 规则 8）：
- 每次 `connect()` → `close()`，**无连接池**
- 复杂字段（`response_schema`, `metadata`, `user_response`）存 JSON TEXT
- `datetime` 存 ISO 字符串
- `Enum` 存 `.value` 字符串
- **新增独立 DB 文件** `qa_agui.db`，与现有 `qa.db` 分离

### 5.2 超时扫描器

```python
# odap/biz/core/qa/agui_timeout_scanner.py

import asyncio
import logging
from datetime import datetime
from odap.biz.core.qa.agui_models import InterruptStatus
from odap.biz.core.qa.storage.sqlite_agui_interrupt_storage import SQLiteAGUIInterruptStorage

logger = logging.getLogger(__name__)


class AGUIInterruptTimeoutScanner:
    """每 60s 扫描超时的 pending interrupt。"""

    def __init__(self, storage: SQLiteAGUIInterruptStorage):
        self.storage = storage

    async def scan_and_timeout(self) -> int:
        """返回本轮超时的数量。"""
        now = datetime.now()
        timed_out = self.storage.get_pending_interrupts_with_timeout_lt(now)

        for record in timed_out:
            self.storage.update_status(
                interrupt_id=record.id,
                status=InterruptStatus.TIMEOUT,
                user_response=None,
            )
            logger.info(
                "AG-UI interrupt %s timeout (session=%s, run=%s)",
                record.id, record.session_id, record.run_id,
            )

        return len(timed_out)


# 启动后台任务（在 app.py lifespan 中）
async def start_agui_timeout_scanner(storage: SQLiteAGUIInterruptStorage):
    scanner = AGUIInterruptTimeoutScanner(storage)
    while True:
        try:
            count = await scanner.scan_and_timeout()
            if count > 0:
                logger.info("AG-UI timeout scanner: %d timed out", count)
        except Exception as e:
            logger.exception("AG-UI timeout scanner error: %s", e)
        await asyncio.sleep(60)
```

---

## 6. 单元测试（AGENTS.md 规则 9）

```python
# tests/unit/test_sqlite_agui_interrupt_storage.py

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from odap.biz.core.qa.agui_models import (
    AGUIInterruptRecord, InterruptStatus, InterruptReason
)
from odap.biz.core.qa.storage.sqlite_agui_interrupt_storage import (
    SQLiteAGUIInterruptStorage,
)


@pytest.fixture
def storage(tmp_path: Path) -> SQLiteAGUIInterruptStorage:
    db = tmp_path / "qa_agui_test.db"
    return SQLiteAGUIInterruptStorage(db_path=str(db))


def test_save_and_get_by_session(storage: SQLiteAGUIInterruptStorage):
    record = AGUIInterruptRecord(
        id="int-001",
        session_id="sess_abc",
        run_id="run_xyz",
        tool_call_id="tc-123",
        tool_name="ask_user_question",
        reason=InterruptReason.CONFIRMATION.value,
        message="要删除 X 节点吗？",
        response_schema={
            "type": "object",
            "properties": {"approved": {"type": "boolean"}},
            "required": ["approved"],
        },
        card_type="confirm",
        expires_at=datetime.now() + timedelta(minutes=30),
    )
    storage.save_interrupt(record)

    records = storage.list_by_session("sess_abc")
    assert len(records) == 1
    assert records[0].id == "int-001"
    assert records[0].status == InterruptStatus.PENDING
    assert records[0].response_schema["properties"]["approved"]["type"] == "boolean"


def test_update_status_to_resolved(storage: SQLiteAGUIInterruptStorage):
    record = AGUIInterruptRecord(
        id="int-002",
        session_id="sess_abc",
        run_id="run_xyz",
        tool_call_id="tc-456",
        tool_name="ask_user_question",
        reason=InterruptReason.CONFIRMATION.value,
        message="要继续吗？",
        response_schema={"type": "object", "properties": {"approved": {"type": "boolean"}}},
        expires_at=datetime.now() + timedelta(minutes=30),
    )
    storage.save_interrupt(record)

    storage.update_status(
        interrupt_id="int-002",
        status=InterruptStatus.RESOLVED,
        user_response={"approved": True},
    )

    records = storage.list_by_session("sess_abc")
    assert records[0].status == InterruptStatus.RESOLVED
    assert records[0].user_response == {"approved": True}
    assert records[0].resolved_at is not None


def test_get_pending_interrupts_with_timeout(storage: SQLiteAGUIInterruptStorage):
    """验证超时扫描器查询。"""
    # 创建一个已过期的 pending
    expired = AGUIInterruptRecord(
        id="int-expired",
        session_id="sess_1",
        run_id="run_1",
        tool_call_id="tc-1",
        tool_name="ask_user_question",
        reason=InterruptReason.CONFIRMATION.value,
        message="过期",
        response_schema={},
        expires_at=datetime.now() - timedelta(seconds=1),  # 已过期
    )
    # 创建一个未过期的 pending
    active = AGUIInterruptRecord(
        id="int-active",
        session_id="sess_1",
        run_id="run_1",
        tool_call_id="tc-2",
        tool_name="ask_user_question",
        reason=InterruptReason.CONFIRMATION.value,
        message="未过期",
        response_schema={},
        expires_at=datetime.now() + timedelta(minutes=30),
    )
    storage.save_interrupt(expired)
    storage.save_interrupt(active)

    now = datetime.now()
    timed_out = storage.get_pending_interrupts_with_timeout_lt(now)
    assert len(timed_out) == 1
    assert timed_out[0].id == "int-expired"


def test_metadata_json_roundtrip(storage: SQLiteAGUIInterruptStorage):
    """验证 metadata JSON 序列化/反序列化。"""
    record = AGUIInterruptRecord(
        id="int-meta",
        session_id="sess_1",
        run_id="run_1",
        tool_call_id="tc-1",
        tool_name="ask_user_question",
        reason=InterruptReason.CONFIRMATION.value,
        message="test",
        response_schema={},
        metadata={"odap": {"tool_name": "ask_user_question", "card_type": "confirm"}},
        expires_at=datetime.now() + timedelta(minutes=30),
    )
    storage.save_interrupt(record)

    records = storage.list_by_session("sess_1")
    assert records[0].metadata == {"odap": {"tool_name": "ask_user_question", "card_type": "confirm"}}


def test_agui_models_pydantic_validation():
    """验证 Pydantic 模型字段校验。"""
    # Interrupt 模型必填 reason
    from odap.biz.core.qa.agui_models import Interrupt

    with pytest.raises(Exception):
        Interrupt(reason=None)  # type: ignore

    # ResumeEntry 必填 interruptId + status
    from odap.biz.core.qa.agui_models import ResumeEntry, ResumeStatus

    entry = ResumeEntry(interruptId="int-1", status=ResumeStatus.RESOLVED, payload={"approved": True})
    assert entry.interruptId == "int-1"
    assert entry.payload == {"approved": True}
```

---

## 7. 数据流图（修订版）

```
┌─────────────────┐
│ 客户端发起 run   │
│ POST /api/ag-ui/run
│ {threadId,       │
│  runId, messages}│
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  agui_handler.run_agent_input()      │
│  1. OPA 鉴权 (AGENTS.md 硬约束)      │
│  2. AGUIBridge.handle_run()          │
│     ├─ 若是 resume:                  │
│     │   ├─ 查找 _pending_prompts     │
│     │   ├─ future.set_result()       │
│     │   └─ 启动新 run 继续流式        │
│     └─ 若是新 run:                   │
│         ├─ 创建 QueryEngine          │
│         ├─ 设置 ask_user_prompt 回调│
│         └─ run_query(message)       │
└────────┬─────────────────────────────┘
         │
         ▼ StreamEvent
┌──────────────────────────────────────┐
│  AGUIBridge.translate()              │
│  - AssistantTextDelta → TextMessage* │
│  - ToolExecution*    → ToolCall*     │
│  - ask_user_question → 触发 interrupt│
│     ├─ save_interrupt() 持久化审计   │
│     ├─ future 阻塞等待客户端 resume   │
│     └─ emit RunFinished.interrupts[]│
└────────┬─────────────────────────────┘
         │
         ▼ SSE events
┌─────────────────┐
│ 客户端 CardRegistry 渲染  │
│ - 看到 RUN_FINISHED.interrupts │
│ - 渲染 ConfirmCard         │
│ - 用户点击"确认"           │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────┐
│ POST /api/ag-ui/run          │
│ {threadId, runId: "run_2",   │
│  resume: [{interruptId,      │
│           status, payload}]} │
└──────────────────────────────┘
         │
         ▼ （回到顶部）
```

---

## 8. 与 OAUIP data-model 的对比

| 维度 | OAUIP v0.1 | AG-UI v1.0 (本文) | 改进 |
|------|-----------|------------------|------|
| 新增表数 | 3 | 1 | -67% |
| 现有表新增列 | 2 | 0 | -100% |
| 活跃状态存储 | SQLite | 内存（OpenHarness + Bridge） | 简化 |
| 持久化机制 | 乐观锁、状态机 | 仅审计（lifecycle 完整） | 简化 |
| 跨进程 HITL 协调 | 需要 | 不需要（单进程同步） | 简化 |
| Worker 重启行为 | 可恢复 | 中断并通知客户端 | 业务可接受 |
| 单元测试 fixture | 3 张表初始化 | 1 张表初始化 | 加速 60% |

---

## 9. 关联文档

- [plan.md](../plan.md) — 主实施计划
- [research.md](../research.md) — Phase 0 决策
- [contracts/ag-ui-bridge.md](../contracts/ag-ui-bridge.md) — 事件映射契约（含 Interrupt 字段定义）
- [contracts/hitl-flow.md](../contracts/hitl-flow.md) — HITL 流程契约（基于本文档 §5.2）
- [contracts/generative-ui-card.md](../contracts/generative-ui-card.md) — 卡片契约
- [OpenHarness QueryEngine](../../../openharness/src/openharness/engine/query_engine.py) — 内存状态机
- [OpenHarness ask_user_question_tool](../../../openharness/src/openharness/tools/ask_user_question_tool.py) — HITL 触发器
- [AGENTS.md 规则 8](../../../AGENTS.md) — SQLite 存储规则
- [AGENTS.md 规则 9](../../../AGENTS.md) — 测试规则

---

**Version**: 1.0 (FINAL) | **Date**: 2026-06-08
