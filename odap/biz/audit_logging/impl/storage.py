"""日志存储实现"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from ..interfaces.storage import ILogStorage
from ..models.log import AuditLog


class LogStorage(ILogStorage):
    """日志存储实现"""
    
    def __init__(self):
        self._logs: Dict[str, AuditLog] = {}
    
    def save_log(self, log: AuditLog) -> bool:
        """保存日志"""
        self._logs[log.id] = log
        return True
    
    def save_logs_batch(self, logs: List[AuditLog]) -> int:
        """批量保存日志"""
        count = 0
        for log in logs:
            if self.save_log(log):
                count += 1
        return count
    
    def get_log(self, log_id: str) -> Optional[AuditLog]:
        """获取日志"""
        return self._logs.get(log_id)
    
    def query_logs(self, filters: Dict[str, Any] = None, 
                  page: int = 1, page_size: int = 10) -> List[AuditLog]:
        """查询日志"""
        filters = filters or {}
        filtered_logs = list(self._logs.values())
        
        if "level" in filters:
            filtered_logs = [l for l in filtered_logs if l.level.value == filters["level"]]
        if "type" in filters:
            filtered_logs = [l for l in filtered_logs if l.type.value == filters["type"]]
        if "service" in filters:
            filtered_logs = [l for l in filtered_logs if l.service == filters["service"]]
        if "user" in filters:
            filtered_logs = [l for l in filtered_logs if l.user == filters["user"]]
        if "status" in filters:
            filtered_logs = [l for l in filtered_logs if l.status.value == filters["status"]]
        
        start = (page - 1) * page_size
        end = start + page_size
        return filtered_logs[start:end]
    
    def update_log(self, log_id: str, updates: Dict[str, Any]) -> bool:
        """更新日志"""
        log = self._logs.get(log_id)
        if not log:
            return False
        
        for key, value in updates.items():
            if hasattr(log, key):
                setattr(log, key, value)
        return True
    
    def delete_log(self, log_id: str) -> bool:
        """删除日志"""
        if log_id in self._logs:
            del self._logs[log_id]
            return True
        return False
    
    def archive_logs(self, before_timestamp: str) -> int:
        """归档日志"""
        before_dt = datetime.fromisoformat(before_timestamp.replace("Z", "+00:00"))
        logs_to_archive = [
            log_id for log_id, log in self._logs.items() 
            if log.timestamp < before_dt
        ]
        
        for log_id in logs_to_archive:
            self._logs[log_id].status = "archived"
        
        return len(logs_to_archive)
    
    def get_log_stats(self, start_time: str = None, end_time: str = None) -> Dict[str, Any]:
        """获取日志统计"""
        logs = list(self._logs.values())
        
        if start_time:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            logs = [l for l in logs if l.timestamp >= start_dt]
        if end_time:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            logs = [l for l in logs if l.timestamp <= end_dt]
        
        stats = {
            "total_count": len(logs),
            "by_level": {},
            "by_type": {},
            "by_status": {},
            "by_service": {}
        }
        
        for log in logs:
            level = log.level.value
            log_type = log.type.value
            status = log.status.value
            service = log.service
            
            stats["by_level"][level] = stats["by_level"].get(level, 0) + 1
            stats["by_type"][log_type] = stats["by_type"].get(log_type, 0) + 1
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            stats["by_service"][service] = stats["by_service"].get(service, 0) + 1
        
        return stats
