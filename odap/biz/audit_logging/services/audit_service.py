"""审计日志服务"""

from typing import Dict, Any, List, Optional
from ..impl.logger import AuditLogger
from ..impl.channel import ChannelManager
from ..impl.storage import LogStorage
from ..models.log import LogLevel, LogType, LogStatus


class AuditService:
    """审计日志服务"""
    
    def __init__(self):
        self.channel_manager = ChannelManager()
        self.logger = AuditLogger(channel_manager=self.channel_manager)
        self.storage = LogStorage()
    
    def log(self, level: LogLevel, log_type: LogType, service: str, action: str, 
           details: Dict[str, Any] = None, user: str = None, resource: str = None) -> Dict[str, Any]:
        """记录日志
        
        Args:
            level: 日志级别
            log_type: 日志类型
            service: 服务名称
            action: 操作名称
            details: 详细信息
            user: 用户
            resource: 资源
            
        Returns:
            日志信息
        """
        log_id = self.logger.log(level, log_type, service, action, details, user, resource)
        
        return {
            "log_id": log_id,
            "level": level.value,
            "type": log_type.value,
            "service": service,
            "action": action,
            "status": "pending"
        }
    
    def debug(self, service: str, action: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
        """记录debug日志"""
        return self.log(LogLevel.DEBUG, LogType.AUDIT, service, action, details)
    
    def info(self, service: str, action: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
        """记录info日志"""
        return self.log(LogLevel.INFO, LogType.AUDIT, service, action, details)
    
    def warning(self, service: str, action: str, details: Dict[str, Any] = None) -> Dict[str, Any]:
        """记录warning日志"""
        return self.log(LogLevel.WARNING, LogType.AUDIT, service, action, details)
    
    def error(self, service: str, action: str, error_message: str, 
             details: Dict[str, Any] = None) -> Dict[str, Any]:
        """记录error日志"""
        return self.log(LogLevel.ERROR, LogType.ERROR, service, action, details, error_message=error_message)
    
    def critical(self, service: str, action: str, error_message: str, 
                details: Dict[str, Any] = None) -> Dict[str, Any]:
        """记录critical日志"""
        return self.log(LogLevel.CRITICAL, LogType.ERROR, service, action, details, error_message=error_message)
    
    def get_log(self, log_id: str) -> Dict[str, Any]:
        """获取日志"""
        log = self.logger.get_log(log_id)
        if not log:
            return {"status": "error", "message": "Log not found"}
        
        return {
            "log_id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "level": log.level.value,
            "type": log.type.value,
            "service": log.service,
            "action": log.action,
            "user": log.user,
            "resource": log.resource,
            "status": log.status.value,
            "details": log.details
        }
    
    def query_logs(self, filters: Dict[str, Any] = None, 
                  page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """查询日志"""
        logs = self.logger.query_logs(filters, page, page_size)
        
        log_list = []
        for log in logs:
            log_list.append({
                "log_id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "level": log.level.value,
                "type": log.type.value,
                "service": log.service,
                "action": log.action,
                "user": log.user,
                "status": log.status.value
            })
        
        return {
            "logs": log_list,
            "page": page,
            "page_size": page_size,
            "total": len(log_list)
        }
    
    def get_stats(self, start_time: str = None, end_time: str = None) -> Dict[str, Any]:
        """获取日志统计"""
        return self.storage.get_log_stats(start_time, end_time)
