"""MongoDB存储实现"""

from typing import Dict, Any, List, Optional
from pymongo import MongoClient
from pymongo.collection import Collection
from ..models.log import AuditLog


class MongoDBStorage:
    """MongoDB存储实现"""
    
    def __init__(self, connection_string: str = "mongodb://localhost:27017"):
        self.client = MongoClient(connection_string)
        self.db = self.client["audit_logging"]
        
        self.logs: Collection = self.db["logs"]
        self.blocks: Collection = self.db["blocks"]
        self.chains: Collection = self.db["chains"]
    
    def save_log(self, log: AuditLog) -> bool:
        """保存日志"""
        try:
            self.logs.insert_one(log.model_dump())
            return True
        except Exception:
            return False
    
    def get_log(self, log_id: str) -> Optional[AuditLog]:
        """获取日志"""
        data = self.logs.find_one({"id": log_id})
        return AuditLog(**data) if data else None
    
    def update_log(self, log_id: str, updates: Dict[str, Any]) -> bool:
        """更新日志"""
        result = self.logs.update_one({"id": log_id}, {"$set": updates})
        return result.modified_count > 0
    
    def query_logs(self, filters: Dict[str, Any] = None, 
                  page: int = 1, page_size: int = 10) -> List[AuditLog]:
        """查询日志"""
        query = filters or {}
        logs = self.logs.find(query).skip((page - 1) * page_size).limit(page_size)
        return [AuditLog(**log) for log in logs]
    
    def save_logs_batch(self, logs: List[AuditLog]) -> int:
        """批量保存日志"""
        try:
            result = self.logs.insert_many([log.model_dump() for log in logs])
            return len(result.inserted_ids)
        except Exception:
            return 0
