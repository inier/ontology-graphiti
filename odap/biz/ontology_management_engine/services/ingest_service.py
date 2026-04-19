"""数据摄入服务"""

from typing import Dict, Any, List, Optional
from ..impl.audit import DataIngestAudit
from ..models.audit import DataSource, ProcessingStatus


class DataIngestService:
    """数据摄入服务"""
    
    def __init__(self):
        self.audit = DataIngestAudit()
    
    def ingest_data(self, source: DataSource, source_details: Dict[str, Any], 
                   data: Dict[str, Any]) -> str:
        """摄入数据
        
        Args:
            source: 数据来源
            source_details: 数据源详细信息
            data: 要摄入的数据
            
        Returns:
            摄入任务ID
        """
        # 开始摄入
        ingest_id = self.audit.start_ingest(source, source_details)
        
        # 记录开始事件
        self.audit.log_audit_event(
            ingest_id=ingest_id,
            level="info",
            message="Data ingestion started",
            details={"source": source.value, "record_count": len(data.get("records", []))}
        )
        
        # 处理数据
        processed_count = 0
        failed_count = 0
        errors = []
        
        try:
            # 这里实现数据处理逻辑
            records = data.get("records", [])
            for i, record in enumerate(records):
                try:
                    # 处理单条记录
                    # 实际项目中可能会进行数据清洗、转换等操作
                    processed_count += 1
                    
                    # 记录进度
                    if (i + 1) % 100 == 0:
                        self.audit.record_progress(ingest_id, processed_count, failed_count)
                        self.audit.log_audit_event(
                            ingest_id=ingest_id,
                            level="info",
                            message=f"Processed {processed_count} records",
                            details={"progress": processed_count / len(records) * 100}
                        )
                except Exception as e:
                    failed_count += 1
                    errors.append({
                        "record_index": i,
                        "error": str(e)
                    })
            
            # 计算质量指标
            total_records = len(records)
            success_rate = processed_count / total_records if total_records > 0 else 1.0
            
            quality_metrics = {
                "success_rate": success_rate,
                "processed_count": processed_count,
                "failed_count": failed_count,
                "total_count": total_records
            }
            
            # 完成摄入
            status = ProcessingStatus.COMPLETED if failed_count == 0 else ProcessingStatus.FAILED
            self.audit.complete_ingest(
                ingest_id=ingest_id,
                status=status,
                errors=errors,
                quality_metrics=quality_metrics
            )
            
            # 记录完成事件
            self.audit.log_audit_event(
                ingest_id=ingest_id,
                level="info" if status == ProcessingStatus.COMPLETED else "error",
                message=f"Data ingestion completed with status: {status.value}",
                details=quality_metrics
            )
            
        except Exception as e:
            # 记录错误
            self.audit.log_audit_event(
                ingest_id=ingest_id,
                level="error",
                message=f"Data ingestion failed: {str(e)}",
                details={"error": str(e)}
            )
            
            # 标记为失败
            self.audit.complete_ingest(
                ingest_id=ingest_id,
                status=ProcessingStatus.FAILED,
                errors=[{"error": str(e)}]
            )
        
        return ingest_id
    
    def get_ingest_status(self, ingest_id: str) -> Dict[str, Any]:
        """获取摄入状态
        
        Args:
            ingest_id: 摄入任务ID
            
        Returns:
            摄入状态信息
        """
        record = self.audit.get_ingest_record(ingest_id)
        if not record:
            return {"status": "not_found"}
        
        return {
            "ingest_id": record.id,
            "source": record.source.value,
            "status": record.status.value,
            "processed_count": record.processed_count,
            "failed_count": record.failed_count,
            "total_count": record.record_count,
            "start_time": record.start_time.isoformat(),
            "end_time": record.end_time.isoformat() if record.end_time else None,
            "duration_seconds": record.duration_seconds,
            "quality_metrics": record.quality_metrics
        }
    
    def list_ingest_jobs(self, filters: Dict[str, Any] = None, 
                        page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """列出摄入任务
        
        Args:
            filters: 过滤条件
            page: 页码
            page_size: 每页数量
            
        Returns:
            摄入任务列表和分页信息
        """
        records = self.audit.list_ingest_records(filters, page, page_size)
        
        jobs = []
        for record in records:
            jobs.append({
                "ingest_id": record.id,
                "source": record.source.value,
                "status": record.status.value,
                "processed_count": record.processed_count,
                "failed_count": record.failed_count,
                "start_time": record.start_time.isoformat(),
                "end_time": record.end_time.isoformat() if record.end_time else None
            })
        
        return {
            "jobs": jobs,
            "page": page,
            "page_size": page_size,
            "total": len(records)  # 实际项目中应该返回总记录数
        }
