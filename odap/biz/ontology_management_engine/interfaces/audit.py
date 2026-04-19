"""数据摄入审计接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.audit import DataIngestRecord, AuditLog, DataSource, ProcessingStatus


class IDataIngestAudit(ABC):
    """数据摄入审计接口"""
    
    @abstractmethod
    def start_ingest(self, source: DataSource, source_details: Dict[str, Any]) -> str:
        """开始数据摄入
        
        Args:
            source: 数据来源
            source_details: 数据源详细信息
            
        Returns:
            摄入任务ID
        """
        pass
    
    @abstractmethod
    def record_progress(self, ingest_id: str, processed_count: int, failed_count: int) -> None:
        """记录处理进度
        
        Args:
            ingest_id: 摄入任务ID
            processed_count: 已处理数量
            failed_count: 失败数量
        """
        pass
    
    @abstractmethod
    def complete_ingest(self, ingest_id: str, status: ProcessingStatus, 
                       errors: List[Dict[str, Any]] = None, 
                       quality_metrics: Dict[str, float] = None) -> None:
        """完成数据摄入
        
        Args:
            ingest_id: 摄入任务ID
            status: 处理状态
            errors: 错误信息列表
            quality_metrics: 质量指标
        """
        pass
    
    @abstractmethod
    def log_audit_event(self, ingest_id: str, level: str, message: str, 
                       details: Dict[str, Any] = None, actor: str = "system") -> None:
        """记录审计事件
        
        Args:
            ingest_id: 摄入任务ID
            level: 日志级别
            message: 日志消息
            details: 详细信息
            actor: 操作人
        """
        pass
    
    @abstractmethod
    def get_ingest_record(self, ingest_id: str) -> Optional[DataIngestRecord]:
        """获取摄入记录
        
        Args:
            ingest_id: 摄入任务ID
            
        Returns:
            摄入记录
        """
        pass
    
    @abstractmethod
    def list_ingest_records(self, filters: Dict[str, Any] = None, 
                           page: int = 1, page_size: int = 10) -> List[DataIngestRecord]:
        """列出摄入记录
        
        Args:
            filters: 过滤条件
            page: 页码
            page_size: 每页数量
            
        Returns:
            摄入记录列表
        """
        pass
    
    @abstractmethod
    def get_audit_logs(self, ingest_id: str, 
                      start_time: Optional[str] = None, 
                      end_time: Optional[str] = None) -> List[AuditLog]:
        """获取审计日志
        
        Args:
            ingest_id: 摄入任务ID
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            审计日志列表
        """
        pass
