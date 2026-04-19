"""数据摄入审计实现"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from ..interfaces.audit import IDataIngestAudit
from ..models.audit import DataIngestRecord, AuditLog, DataSource, ProcessingStatus
from ..storage.mongodb_storage import MongoDBStorage


class DataIngestAudit(IDataIngestAudit):
    """数据摄入审计实现"""
    
    def __init__(self):
        self.storage = MongoDBStorage()
    
    def start_ingest(self, source: DataSource, source_details: Dict[str, Any]) -> str:
        """开始数据摄入"""
        record = DataIngestRecord(
            source=source,
            source_details=source_details
        )
        self.storage.save_ingest_record(record)
        return record.id
    
    def record_progress(self, ingest_id: str, processed_count: int, failed_count: int) -> None:
        """记录处理进度"""
        record = self.storage.get_ingest_record(ingest_id)
        if record:
            record.processed_count = processed_count
            record.failed_count = failed_count
            record.status = ProcessingStatus.PROCESSING
            self.storage.update_ingest_record(record)
    
    def complete_ingest(self, ingest_id: str, status: ProcessingStatus, 
                       errors: List[Dict[str, Any]] = None, 
                       quality_metrics: Dict[str, float] = None) -> None:
        """完成数据摄入"""
        record = self.storage.get_ingest_record(ingest_id)
        if record:
            record.status = status
            record.end_time = datetime.now()
            record.duration_seconds = (record.end_time - record.start_time).total_seconds()
            if errors:
                record.errors = errors
            if quality_metrics:
                record.quality_metrics = quality_metrics
            self.storage.update_ingest_record(record)
    
    def log_audit_event(self, ingest_id: str, level: str, message: str, 
                       details: Dict[str, Any] = None, actor: str = "system") -> None:
        """记录审计事件"""
        log = AuditLog(
            ingest_id=ingest_id,
            level=level,
            message=message,
            details=details or {},
            actor=actor
        )
        self.storage.save_audit_log(log)
    
    def get_ingest_record(self, ingest_id: str) -> Optional[DataIngestRecord]:
        """获取摄入记录"""
        return self.storage.get_ingest_record(ingest_id)
    
    def list_ingest_records(self, filters: Dict[str, Any] = None, 
                           page: int = 1, page_size: int = 10) -> List[DataIngestRecord]:
        """列出摄入记录"""
        return self.storage.list_ingest_records(filters, page, page_size)
    
    def get_audit_logs(self, ingest_id: str, 
                      start_time: Optional[str] = None, 
                      end_time: Optional[str] = None) -> List[AuditLog]:
        """获取审计日志"""
        return self.storage.get_audit_logs(ingest_id, start_time, end_time)
