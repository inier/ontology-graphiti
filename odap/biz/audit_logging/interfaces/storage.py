"""日志存储接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.log import AuditLog


class ILogStorage(ABC):
    """日志存储接口"""
    
    @abstractmethod
    def save_log(self, log: AuditLog) -> bool:
        """保存日志
        
        Args:
            log: 审计日志
            
        Returns:
            是否保存成功
        """
        pass
    
    @abstractmethod
    def save_logs_batch(self, logs: List[AuditLog]) -> int:
        """批量保存日志
        
        Args:
            logs: 审计日志列表
            
        Returns:
            保存成功的数量
        """
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
    def update_log(self, log_id: str, updates: Dict[str, Any]) -> bool:
        """更新日志
        
        Args:
            log_id: 日志ID
            updates: 更新内容
            
        Returns:
            是否更新成功
        """
        pass
    
    @abstractmethod
    def delete_log(self, log_id: str) -> bool:
        """删除日志
        
        Args:
            log_id: 日志ID
            
        Returns:
            是否删除成功
        """
        pass
    
    @abstractmethod
    def archive_logs(self, before_timestamp: str) -> int:
        """归档日志
        
        Args:
            before_timestamp: 时间戳
            
        Returns:
            归档的日志数量
        """
        pass
    
    @abstractmethod
    def get_log_stats(self, start_time: str = None, end_time: str = None) -> Dict[str, Any]:
        """获取日志统计
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            统计信息
        """
        pass
