# ADR-042: 审计日志存储查询

## 状态
已接受

## 上下文

ODAP 审计日志需要记录所有用户操作、Agent 行为和系统事件（FR-700），支持时间线回溯和合规审计。存储选型需要平衡以下需求：

1. **写入性能**：审计日志高频写入，不能影响业务请求延迟
2. **防篡改**：日志不可修改，支持校验链验证
3. **查询能力**：按时间、操作者、工作空间、事件类型过滤
4. **存储成本**：长期归档，冷热分层
5. **部署简单**：符合模块化单体部署约束（ADR-046）

### 选型对比

| 方案 | 写入性能 | 查询能力 | 防篡改 | 部署复杂度 | 存储成本 |
|------|---------|---------|--------|-----------|---------|
| **A. SQLite** | 高（本地写入） | 中（SQL 查询） | 中（文件级） | 低（零部署） | 低 |
| **B. 文件（JSON/CSV）** | 最高（追加写入） | 低（需扫描） | 高（哈希链锚点） | 最低 | 最低 |
| **C. PostgreSQL** | 中（网络写入） | 高（全文索引） | 中（表级权限） | 高（额外容器） | 中 |
| **D. Neo4j** | 低（图写入） | 高（图遍历） | 中 | 零（已有） | 高 |

### 约束

- ADR-046 决策：Docker Compose 三容器（主进程 + Neo4j + OPA），不引入额外数据库
- 审计日志已实现异步 Channel + 批量落盘（audit_log/DESIGN.md）
- 日志量预估：日常 < 1 万条/天，峰值 < 10 万条/天

## 决策

**采用方案 A：SQLite 作为主存储，文件作为哈希链锚点**。

### 存储架构

```
AuditEvent → Channel (async) → SQLiteWriter → SQLite DB
                                              │
                                              └──→ HashChain → 锚点文件（JSON Lines）
```

1. **热存储**：SQLite（WAL 模式），支持 SQL 查询、时间范围过滤、分页
2. **校验层**：SHA-256 哈希链，每 N 条事件计算一次锚点写入文件
3. **冷归档**：超过保留期的日志导出为 JSON Lines 文件压缩存储

### SQLite Schema（核心表）

```sql
CREATE TABLE audit_events (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    workspace_id TEXT NOT NULL,
    trace_id TEXT,
    parent_event_id TEXT,
    result TEXT,
    context TEXT,  -- JSON
    hash TEXT NOT NULL,  -- SHA-256(event + prev_hash)
    created_at TEXT NOT NULL
);

CREATE INDEX idx_audit_timestamp ON audit_events(timestamp);
CREATE INDEX idx_audit_workspace ON audit_events(workspace_id);
CREATE INDEX idx_audit_actor ON audit_events(actor_id);
CREATE INDEX idx_audit_type ON audit_events(event_type);
CREATE INDEX idx_audit_trace ON audit_events(trace_id);
```

### 防篡改机制

```python
class HashChain:
    """SHA-256 链式哈希 — 每 1000 条事件锚定一次"""

    async def append(self, event: AuditEvent) -> str:
        event.hash = sha256(f"{event.id}{event.timestamp}{self.prev_hash}")
        self.prev_hash = event.hash
        self.count += 1
        if self.count % 1000 == 0:
            await self._write_anchor()  # 写入锚点文件
        return event.hash

    async def verify(self, start_id: str, end_id: str) -> bool:
        """验证两个锚点之间的事件链完整性"""
        ...
```

### 数据生命周期

| 严重级别 | 保留期 | 存储位置 |
|---------|--------|---------|
| DEBUG | 7 天 | SQLite（自动清理） |
| INFO | 90 天 | SQLite + 归档 |
| WARN | 180 天 | SQLite + 归档 |
| ERROR/CRITICAL | 永久 | SQLite + 归档 + 异地备份 |

## 后果

### 变得更容易

- **零额外部署**：SQLite 是 Python 标准库，无需新增容器
- **写入性能**：WAL 模式 + 批量写入，10 万条/天无压力
- **SQL 查询**：时间范围、操作者、类型等过滤直接用 SQL
- **文件可移植**：SQLite 单文件，可直接复制/备份

### 变得更难

- **并发写入**：SQLite 单写者，但审计日志已通过 Channel 串行化，无冲突
- **全文搜索**：SQLite FTS5 可用但不如 PostgreSQL 全文索引
- **水平扩展**：SQLite 不支持多进程写入，但模块化单体内只有单进程，无此问题

### 风险与缓解

| 风险 | 缓解 |
|------|------|
| SQLite 文件损坏 | WAL 模式 + 定期 checkpoint + 自动备份 |
| 单文件体积过大 | 按工作空间/月份分库 + 归档清理 |
| 未来需要全文搜索 | SQLite FTS5 虚拟表，或升级到 PostgreSQL |

## 可逆性

**高**。SQLite → PostgreSQL 迁移路径清晰：Schema 兼容，只需替换 Writer 实现。审计日志接口（IAuditLogger）已抽象，存储后端可插拔。

## 关联

- 关联 ADR-008（审计日志完整记录）
- 关联 ADR-046（模块化单体部署 — 不引入额外数据库）
- 关联 M-07 DESIGN.md
- 关闭 ANOMALY_REPORT I-22（审计日志存储选型 → SQLite + 文件锚点）
- 影响 WR-05（审计日志系统）
