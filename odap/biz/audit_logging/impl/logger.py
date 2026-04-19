"""审计日志实现"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib
import json
from ..interfaces.logger import IAuditLogger
from ..interfaces.channel import IChannelManager
from ..models.log import AuditLog, LogLevel, LogType, LogStatus


class AuditLogger(IAuditLogger):
    """审计日志实现"""
    
    def __init__(self, channel_manager: IChannelManager = None):
        self.channel_manager = channel_manager
        self._logs: Dict[str, AuditLog] = {}
    
    def _compute_hash(self, log: AuditLog) -> str:
        """计算日志哈希"""
        content = f"{log.id}{log.timestamp}{log.level}{log.type}{log.service}{log.action}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def log(self, level: LogLevel, log_type: LogType, service: str, action: str, 
           details: Dict[str, Any] = None, user: str = None, resource: str = None) -> str:
        """记录日志"""
        log = AuditLog(
            level=level,
            type=log_type,
            service=service,
            action=action,
            details=details or {},
            user=user,
            resource=resource,
            status=LogStatus.PENDING
        )
        
        # 计算哈希
        log_hash = self._compute_hash(log)
        log.details["hash"] = log_hash
        
        # 保存日志
        self._logs[log.id] = log
        
        # 如果有通道管理器，则入队
        if self.channel_manager:
            self.channel_manager.enqueue("audit_logs", log.model_dump())
        
        return log.id
    
    def debug(self, service: str, action: str, details: Dict[str, Any] = None) -> str:
        """记录debug日志"""
        return self.log(LogLevel.DEBUG, LogType.AUDIT, service, action, details)
    
    def info(self, service: str, action: str, details: Dict[str, Any] = None) -> str:
        """记录info日志"""
        return self.log(LogLevel.INFO, LogType.AUDIT, service, action, details)
    
    def warning(self, service: str, action: str, details: Dict[str, Any] = None) -> str:
        """记录warning日志"""
        return self.log(LogLevel.WARNING, LogType.AUDIT, service, action, details)
    
    def error(self, service: str, action: str, error_message: str, 
             details: Dict[str, Any] = None) -> str:
        """记录error日志"""
        details = details or {}
        details["error_message"] = error_message
        return self.log(LogLevel.ERROR, LogType.ERROR, service, action, details)
    
    def critical(self, service: str, action: str, error_message: str, 
                details: Dict[str, Any] = None) -> str:
        """记录critical日志"""
        details = details or {}
        details["error_message"] = error_message
        return self.log(LogLevel.CRITICAL, LogType.ERROR, service, action, details)
    
    def get_log(self, log_id: str) -> Optional[AuditLog]:
        """获取日志"""
        return self._logs.get(log_id)
    
    def query_logs(self, filters: Dict[str, Any] = None, 
                  page: int = 1, page_size: int = 10) -> List[AuditLog]:
        """查询日志"""
        filters = filters or {}
        filtered_logs = list(self._logs.values())
        
        # 应用过滤
        if "level" in filters:
            filtered_logs = [l for l in filtered_logs if l.level == filters["level"]]
        if "type" in filters:
            filtered_logs = [l for l in filtered_logs if l.type == filters["type"]]
        if "service" in filters:
            filtered_logs = [l for l in filtered_logs if l.service == filters["service"]]
        if "user" in filters:
            filtered_logs = [l for l in filtered_logs if l.user == filters["user"]]
        if "status" in filters:
            filtered_logs = [l for l in filtered_logs if l.status == filters["status"]]
        
        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        return filtered_logs[start:end]
    
    def update_log_status(self, log_id: str, status: LogStatus) -> bool:
        """更新日志状态"""
        log = self._logs.get(log_id)
        if not log:
            return False
        log.status = status
        log.processed_at = datetime.now()
        return True
