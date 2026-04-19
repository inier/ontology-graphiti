"""审计日志接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.log import AuditLog, LogLevel, LogType, LogStatus


class IAuditLogger(ABC):
    """审计日志接口"""
    
    @abstractmethod
    def log(self, level: LogLevel, log_type: LogType, service: str, action: str, 
           details: Dict[str, Any] = None, user: str = None, resource: str = None) -> str:
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
            日志ID
        """
        pass
    
    @abstractmethod
    def debug(self, service: str, action: str, details: Dict[str, Any] = None) -> str:
        """记录debug日志"""
        pass
    
    @abstractmethod
    def info(self, service: str, action: str, details: Dict[str, Any] = None) -> str:
        """记录info日志"""
        pass
    
    @abstractmethod
    def warning(self, service: str, action: str, details: Dict[str, Any] = None) -> str:
        """记录warning日志"""
        pass
    
    @abstractmethod
    def error(self, service: str, action: str, error_message: str, 
             details: Dict[str, Any] = None) -> str:
        """记录error日志"""
        pass
    
    @abstractmethod
    def critical(self, service: str, action: str, error_message: str, 
                details: Dict[str, Any] = None) -> str:
        """记录critical日志"""
        pass
    
    @abstractmethod
    def get_log(self, log_id: str) -> Optional[AuditLog]:
        """获取日志
        
        Args:
            log_id: 日志ID
            
        Returns:
            审计日志
        """
        pass
    
    @abstractmethod
    def query_logs(self, filters: Dict[str, Any] = None, 
                  page: int = 1, page_size: int = 10) -> List[AuditLog]:
        """查询日志
        
        Args:
            filters: 过滤条件
            page: 页码
            page_size: 每页数量
            
        Returns:
            日志列表
        """
        pass
    
    @abstractmethod
    def update_log_status(self, log_id: str, status: LogStatus) -> bool:
        """更新日志状态
        
        Args:
            log_id: 日志ID
            status: 新状态
            
        Returns:
            是否更新成功
        """
        pass
