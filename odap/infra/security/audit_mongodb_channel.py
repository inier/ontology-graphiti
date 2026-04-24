"""MongoDB 审计通道实现"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure

from .audit_models import AuditEvent, AuditFilter, AuditSeverity, AuditEventType
from .audit_sqlite_channel import AuditChannel


class MongoDBAuditChannel(AuditChannel):
    """MongoDB 审计通道实现

    特性：
    - 批量写入提高性能
    - TTL 索引自动过期数据
    - 支持复杂查询和聚合
    - 高并发写入支持
    """

    def __init__(self, connection_string: Optional[str] = None, db_name: str = "audit"):
        """初始化 MongoDB 审计通道

        Args:
            connection_string: MongoDB 连接字符串
            db_name: 数据库名称
        """
        self.connection_string = connection_string or os.getenv("MONGODB_URI", "mongodb://graphiti-mongodb:27017")
        self.db_name = db_name
        self.client: Optional[MongoClient] = None
        self.collection: Optional[Collection] = None
        self.batch_size = 100
        self.batch: List[Dict] = []

        try:
            self._connect()
            self._create_indexes()
        except Exception as e:
            print(f"MongoDB 审计通道初始化失败: {e}")

    def _connect(self):
        """建立 MongoDB 连接"""
        self.client = MongoClient(self.connection_string, serverSelectionTimeoutMS=5000)
        # 测试连接
        self.client.admin.command('ping')
        db = self.client[self.db_name]
        self.collection = db["audit_events"]

    def _create_indexes(self):
        """创建必要的索引"""
        if self.collection is not None:
            # 时间戳索引，用于排序和范围查询
            self.collection.create_index("timestamp")
            # 工作空间 ID 索引，用于按工作空间查询
            self.collection.create_index("workspace_id")
            # 事件类型索引
            self.collection.create_index("event_type")
            # 严重程度索引
            self.collection.create_index("severity")
            # 来源索引
            self.collection.create_index("source")
            # TTL 索引，自动过期 30 天前的数据
            self.collection.create_index(
                "timestamp",
                expireAfterSeconds=30 * 24 * 60 * 60  # 30 天
            )

    async def write(self, event: AuditEvent) -> None:
        """写入审计事件

        Args:
            event: 审计事件对象
        """
        try:
            if self.collection is None:
                self._connect()

            event_dict = self._event_to_dict(event)
            self.batch.append(event_dict)

            # 达到批量大小或遇到同步点时批量写入
            if len(self.batch) >= self.batch_size:
                self._flush_batch()

        except Exception as e:
            print(f"写入审计事件失败: {e}")

    async def write_batch(self, events: List[AuditEvent]) -> None:
        """批量写入审计事件

        Args:
            events: 审计事件列表
        """
        try:
            if self.collection is None:
                self._connect()

            event_dicts = [self._event_to_dict(event) for event in events]
            self.collection.insert_many(event_dicts)

        except Exception as e:
            print(f"批量写入审计事件失败: {e}")

    def _event_to_dict(self, event: AuditEvent) -> Dict[str, Any]:
        """将 AuditEvent 转换为字典

        Args:
            event: 审计事件对象

        Returns:
            Dict: 事件字典
        """
        return {
            "id": event.id,
            "event_type": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
            "severity": event.severity.value if hasattr(event.severity, "value") else str(event.severity),
            "actor": event.actor,
            "action": event.action,
            "resource": event.resource,
            "result": event.result,
            "timestamp": event.timestamp,
            "workspace_id": event.workspace_id,
            "source": event.source,
            "trace_id": event.trace_id,
            "context": event.context,
            "signature": event.signature
        }

    def _flush_batch(self):
        """批量写入事件"""
        if self.batch and self.collection is not None:
            try:
                self.collection.insert_many(self.batch)
                self.batch.clear()
            except Exception as e:
                print(f"批量写入审计事件失败: {e}")

    async def query(self, filter: AuditFilter) -> List[AuditEvent]:
        """查询审计事件

        Args:
            filter: 审计过滤器

        Returns:
            List[AuditEvent]: 审计事件列表
        """
        try:
            if self.collection is None:
                self._connect()

            query = {}

            # 构建查询条件
            if filter.event_type:
                query["event_type"] = filter.event_type.value if hasattr(filter.event_type, "value") else str(filter.event_type)

            if filter.severity:
                query["severity"] = filter.severity.value if hasattr(filter.severity, "value") else str(filter.severity)

            if filter.workspace_id:
                query["workspace_id"] = filter.workspace_id

            if filter.start_time:
                query["timestamp"] = {"$gte": filter.start_time}

            if filter.end_time:
                if "timestamp" in query:
                    query["timestamp"]["$lte"] = filter.end_time
                else:
                    query["timestamp"] = {"$lte": filter.end_time}

            if filter.source:
                query["source"] = filter.source

            # 执行查询
            cursor = self.collection.find(query)

            # 排序
            if filter.order_by:
                sort_direction = -1 if filter.order_desc else 1
                cursor = cursor.sort(filter.order_by, sort_direction)

            # 分页
            if filter.offset:
                cursor = cursor.skip(filter.offset)

            if filter.limit:
                cursor = cursor.limit(filter.limit)

            # 转换结果
            events = []
            for doc in cursor:
                event = self._dict_to_event(doc)
                if event:
                    events.append(event)

            return events
        except Exception as e:
            print(f"查询审计事件失败: {e}")
            return []

    def _dict_to_event(self, doc: Dict[str, Any]) -> Optional[AuditEvent]:
        """将字典转换为 AuditEvent

        Args:
            doc: 事件字典

        Returns:
            Optional[AuditEvent]: 审计事件对象
        """
        try:
            # 处理枚举类型
            try:
                event_type = AuditEventType(doc["event_type"])
            except ValueError:
                event_type = AuditEventType.OTHER

            try:
                severity = AuditSeverity(doc["severity"])
            except ValueError:
                severity = AuditSeverity.INFO

            return AuditEvent(
                id=doc.get("id"),
                event_type=event_type,
                severity=severity,
                actor=doc.get("actor", {}),
                action=doc.get("action", ""),
                resource=doc.get("resource", {}),
                result=doc.get("result", {}),
                timestamp=doc.get("timestamp"),
                workspace_id=doc.get("workspace_id"),
                source=doc.get("source"),
                trace_id=doc.get("trace_id"),
                context=doc.get("context", {}),
                signature=doc.get("signature")
            )
        except Exception as e:
            print(f"转换审计事件失败: {e}")
            return None

    def close(self):
        """关闭通道"""
        # 确保批量数据被写入
        self._flush_batch()

        if self.client:
            self.client.close()

    def close_sync(self):
        """同步关闭审计通道"""
        self.close()

    def get_stats(self, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """获取审计统计信息

        Args:
            workspace_id: 工作空间 ID

        Returns:
            Dict: 统计信息
        """
        try:
            if not self.collection:
                self._connect()

            query = {}
            if workspace_id:
                query["workspace_id"] = workspace_id

            # 统计事件总数
            total_events = self.collection.count_documents(query)

            # 按事件类型统计
            event_type_stats = list(self.collection.aggregate([
                {"$match": query},
                {"$group": {"_id": "$event_type", "count": {"$sum": 1}}}
            ]))

            # 按严重程度统计
            severity_stats = list(self.collection.aggregate([
                {"$match": query},
                {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
            ]))

            # 最近 24 小时的事件数
            last_24h = datetime.utcnow() - timedelta(hours=24)
            last_24h_query = query.copy()
            last_24h_query["timestamp"] = {"$gte": last_24h}
            last_24h_events = self.collection.count_documents(last_24h_query)

            return {
                "total_events": total_events,
                "event_type_stats": {item["_id"]: item["count"] for item in event_type_stats},
                "severity_stats": {item["_id"]: item["count"] for item in severity_stats},
                "last_24h_events": last_24h_events
            }
        except Exception as e:
            print(f"获取审计统计信息失败: {e}")
            return {
                "total_events": 0,
                "event_type_stats": {},
                "severity_stats": {},
                "last_24h_events": 0
            }


def get_audit_channel() -> AuditChannel:
    """获取审计通道实例

    Returns:
        AuditChannel: 审计通道实例
    """
    return MongoDBAuditChannel()