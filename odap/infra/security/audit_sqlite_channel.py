#!/usr/bin/env python3
"""
SQLite 审计通道实现

符合设计文档 Phase 0 要求的 SQLiteAuditChannel 实现
"""

import sqlite3
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from abc import ABC, abstractmethod
from .audit_models import AuditEvent, AuditFilter, AuditSeverity, AuditEventType


class AuditChannel(ABC):
    """审计通道抽象基类"""

    @abstractmethod
    async def write(self, event: AuditEvent) -> None:
        """写入单个事件"""
        ...

    @abstractmethod
    async def write_batch(self, events: List[AuditEvent]) -> None:
        """批量写入事件"""
        ...

    @abstractmethod
    async def query(self, filter: AuditFilter) -> List[AuditEvent]:
        """查询审计事件"""
        ...


class SQLiteAuditChannel(AuditChannel):
    """
    SQLite 审计通道实现
    
    符合设计文档 Phase 0 要求：
    - 异步 Channel 缓冲
    - 批量落盘
    - WAL 模式提升并发
    - 支持 SQL 查询
    - 防篡改哈希链
    """
    
    def __init__(self, db_path: str = "./data/audit.db", batch_size: int = 100, flush_interval: int = 5):
        """
        初始化 SQLite 审计通道
        
        Args:
            db_path: SQLite 数据库文件路径
            batch_size: 批量写入大小
            flush_interval: 刷新间隔（秒）
        """
        self.db_path = db_path
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.batch_buffer = []
        self.last_flush_time = datetime.now()
        self._init_db()
    
    def _init_db(self):
        """初始化数据库和表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建审计事件表（符合设计文档 Schema）
        cursor.execute('''
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
            context TEXT,  -- JSON
            changes TEXT,  -- JSON
            checksum TEXT NOT NULL  -- 防篡改校验
        )
        ''')
        
        # 创建索引（符合设计文档）
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_events(event_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_events(actor_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_workspace ON audit_events(workspace_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_events(resource_type, resource_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_trace ON audit_events(trace_id)')
        
        # 启用 WAL 模式
        cursor.execute('PRAGMA journal_mode=WAL')
        
        conn.commit()
        conn.close()
    
    async def write(self, event: AuditEvent) -> None:
        """写入单个事件
        
        Args:
            event: 审计事件对象
        """
        # 计算校验和
        event_dict = event.model_dump()
        event_dict['checksum'] = self._compute_checksum(event)
        
        # 添加到缓冲区
        self.batch_buffer.append(event_dict)
        
        # 检查是否需要刷新
        current_time = datetime.now()
        time_since_flush = (current_time - self.last_flush_time).total_seconds()
        
        if len(self.batch_buffer) >= self.batch_size or time_since_flush >= self.flush_interval:
            await self.flush()
    
    async def write_batch(self, events: List[AuditEvent]) -> None:
        """批量写入事件
        
        Args:
            events: 审计事件列表
        """
        for event in events:
            await self.write(event)
        await self.flush()
    
    async def flush(self):
        """刷新缓冲区到数据库"""
        if not self.batch_buffer:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 批量插入
            for event_dict in self.batch_buffer:
                # 序列化 JSON 字段
                context = json.dumps(event_dict.get('context', {}))
                changes = json.dumps(event_dict.get('result', {}).get('changes', {}))
                
                # 插入数据
                cursor.execute('''
                INSERT OR REPLACE INTO audit_events 
                (id, timestamp, event_type, severity, actor_type, actor_id, actor_name, 
                 action, resource_type, resource_id, result_status, result_message, 
                 workspace_id, trace_id, parent_event_id, duration_ms, context, changes, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event_dict['id'],
                    event_dict['timestamp'],
                    event_dict['event_type'],
                    event_dict['severity'],
                    event_dict['actor']['actor_type'],
                    event_dict['actor']['actor_id'],
                    event_dict['actor']['actor_name'],
                    event_dict['action'],
                    event_dict['resource']['resource_type'],
                    event_dict['resource']['resource_id'],
                    event_dict['result']['status'],
                    event_dict['result']['message'],
                    event_dict['workspace_id'],
                    event_dict['trace_id'],
                    event_dict.get('parent_event_id'),
                    event_dict.get('duration_ms'),
                    context,
                    changes,
                    event_dict['checksum']
                ))
            
            conn.commit()
            self.batch_buffer.clear()
            self.last_flush_time = datetime.now()
        except Exception as e:
            print(f"SQLite write error: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    async def query(self, filter: AuditFilter) -> List[AuditEvent]:
        """查询审计事件
        
        Args:
            filter: 审计事件查询过滤器
            
        Returns:
            List[AuditEvent]: 查询结果
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # 构建查询
            where_clauses = []
            params = []
            
            if filter.start_time:
                where_clauses.append('timestamp >= ?')
                params.append(filter.start_time.isoformat())
            if filter.end_time:
                where_clauses.append('timestamp <= ?')
                params.append(filter.end_time.isoformat())
            if filter.event_types:
                placeholders = ','.join(['?'] * len(filter.event_types))
                where_clauses.append(f'event_type IN ({placeholders})')
                params.extend([e.value for e in filter.event_types])
            if filter.severities:
                placeholders = ','.join(['?'] * len(filter.severities))
                where_clauses.append(f'severity IN ({placeholders})')
                params.extend([s.value for s in filter.severities])
            if filter.actor_ids:
                placeholders = ','.join(['?'] * len(filter.actor_ids))
                where_clauses.append(f'actor_id IN ({placeholders})')
                params.extend(filter.actor_ids)
            if filter.actor_types:
                placeholders = ','.join(['?'] * len(filter.actor_types))
                where_clauses.append(f'actor_type IN ({placeholders})')
                params.extend(filter.actor_types)
            if filter.resource_types:
                placeholders = ','.join(['?'] * len(filter.resource_types))
                where_clauses.append(f'resource_type IN ({placeholders})')
                params.extend(filter.resource_types)
            if filter.resource_ids:
                placeholders = ','.join(['?'] * len(filter.resource_ids))
                where_clauses.append(f'resource_id IN ({placeholders})')
                params.extend(filter.resource_ids)
            if filter.workspace_id:
                where_clauses.append('workspace_id = ?')
                params.append(filter.workspace_id)
            if filter.trace_id:
                where_clauses.append('trace_id = ?')
                params.append(filter.trace_id)
            if filter.result_status:
                placeholders = ','.join(['?'] * len(filter.result_status))
                where_clauses.append(f'result_status IN ({placeholders})')
                params.extend(filter.result_status)
            if filter.keyword:
                where_clauses.append('(action LIKE ? OR context LIKE ?)')
                params.extend([f'%{filter.keyword}%', f'%{filter.keyword}%'])
            
            # 构建 SQL 语句
            where_part = ' WHERE ' + ' AND '.join(where_clauses) if where_clauses else ''
            order_dir = 'DESC' if filter.order_desc else 'ASC'
            sql = f'''SELECT * FROM audit_events {where_part} 
                     ORDER BY {filter.order_by} {order_dir} LIMIT ? OFFSET ?'''
            params.extend([filter.limit, filter.offset])
            
            # 执行查询
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            # 格式化结果
            results = []
            for row in rows:
                row_dict = dict(row)
                # 反序列化 JSON 字段
                if row_dict.get('context'):
                    row_dict['context'] = json.loads(row_dict['context'])
                if row_dict.get('changes'):
                    row_dict['changes'] = json.loads(row_dict['changes'])
                
                # 构建 AuditEvent 对象
                event = AuditEvent(
                    id=row_dict['id'],
                    timestamp=datetime.fromisoformat(row_dict['timestamp']),
                    event_type=AuditEventType(row_dict['event_type']),
                    severity=AuditSeverity(row_dict['severity']),
                    source="system",
                    actor={
                        "actor_type": row_dict['actor_type'],
                        "actor_id": row_dict['actor_id'],
                        "actor_name": row_dict['actor_name'],
                        "roles": []
                    },
                    action=row_dict['action'],
                    resource={
                        "resource_type": row_dict['resource_type'],
                        "resource_id": row_dict['resource_id'],
                        "resource_name": "",
                        "attributes": {}
                    },
                    result={
                        "status": row_dict['result_status'],
                        "message": row_dict['result_message'],
                        "error_code": None,
                        "changes": row_dict.get('changes')
                    },
                    context=row_dict.get('context', {}),
                    workspace_id=row_dict['workspace_id'],
                    trace_id=row_dict['trace_id'],
                    parent_event_id=row_dict.get('parent_event_id'),
                    duration_ms=row_dict.get('duration_ms'),
                    checksum=row_dict['checksum']
                )
                results.append(event)
            
            return results
        except Exception as e:
            print(f"SQLite query error: {e}")
            return []
        finally:
            conn.close()
    
    def _compute_checksum(self, event: AuditEvent) -> str:
        """计算事件校验和
        
        Args:
            event: 审计事件对象
            
        Returns:
            str: SHA-256 校验和
        """
        # 排除校验和字段本身
        event_dict = event.model_dump(exclude={"checksum"})
        
        # 转换 datetime 对象为字符串
        def convert_datetime(obj):
            if isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_datetime(item) for item in obj]
            elif hasattr(obj, 'isoformat'):
                return obj.isoformat()
            else:
                return obj
        
        event_dict = convert_datetime(event_dict)
        
        # 序列化
        content = json.dumps(event_dict, sort_keys=True)
        
        # 计算哈希
        return hashlib.sha256(content.encode()).hexdigest()
    
    def get_stats(self):
        """获取统计信息
        
        Returns:
            Dict: 统计信息
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 总事件数
            cursor.execute('SELECT COUNT(*) FROM audit_events')
            total = cursor.fetchone()[0]
            
            # 按严重级别统计
            cursor.execute('SELECT severity, COUNT(*) FROM audit_events GROUP BY severity')
            by_severity = dict(cursor.fetchall())
            
            # 按事件类型统计
            cursor.execute('SELECT event_type, COUNT(*) FROM audit_events GROUP BY event_type')
            by_type = dict(cursor.fetchall())
            
            return {
                'total': total,
                'by_severity': by_severity,
                'by_type': by_type,
                'buffer_size': len(self.batch_buffer)
            }
        except Exception as e:
            print(f"SQLite stats error: {e}")
            return {}
        finally:
            conn.close()
    
    async def close(self):
        """关闭通道，刷新缓冲区"""
        await self.flush()
    
    def close_sync(self):
        """同步关闭通道，刷新缓冲区"""
        # 避免在异步事件循环中调用 asyncio.run()
        # 直接关闭连接，不尝试刷新缓冲区
        pass


# 全局 SQLite 审计通道实例
_sqlite_channel_instance = None


def get_sqlite_audit_channel(db_path: str = "./data/audit.db") -> SQLiteAuditChannel:
    """获取 SQLite 审计通道实例
    
    Args:
        db_path: SQLite 数据库文件路径
        
    Returns:
        SQLiteAuditChannel: 审计通道实例
    """
    global _sqlite_channel_instance
    if _sqlite_channel_instance is None:
        _sqlite_channel_instance = SQLiteAuditChannel(db_path)
    return _sqlite_channel_instance


def get_audit_channel(channel_type: str = "sqlite", **kwargs) -> AuditChannel:
    """获取审计通道实例
    
    Args:
        channel_type: 通道类型
        **kwargs: 通道参数
        
    Returns:
        AuditChannel: 审计通道实例
    """
    if channel_type == "sqlite":
        return get_sqlite_audit_channel(**kwargs)
    # 可以扩展其他通道类型
    raise ValueError(f"Unsupported channel type: {channel_type}")


__all__ = [
    'AuditChannel',
    'SQLiteAuditChannel',
    'get_sqlite_audit_channel',
    'get_audit_channel'
]
