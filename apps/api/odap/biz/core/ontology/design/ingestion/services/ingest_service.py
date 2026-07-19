import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from ..impl.pdf_processor import PDFProcessor
from ..impl.word_processor import WordProcessor
from ..impl.ocr_processor import OCRProcessor
from ..impl.batch_importer import BatchImporter
from ..storage import Storage

logger = logging.getLogger(__name__)


class IngestService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.storage = Storage()
        self.pdf_processor = PDFProcessor()
        self.word_processor = WordProcessor()
        self.ocr_processor = OCRProcessor()
        self.batch_importer = BatchImporter(storage=None)
        self._initialized = True

    def upload_file(self, file_name: str, file_data: bytes, workspace_id: str, content_type: str = "application/octet-stream") -> Dict[str, Any]:
        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        file_type = self._detect_file_type(file_name)

        storage_key = None
        try:
            from odap.infra.storage.minio_client import get_minio_client
            minio = get_minio_client()
            if minio.available:
                bucket = "odap-ingestion"
                minio.ensure_bucket(bucket)
                key = f"{workspace_id}/{task_id}/{file_name}"
                upload_result = minio.upload_object(bucket, key, file_data, content_type=content_type)
                if upload_result.get("status") == "success":
                    storage_key = key
        except Exception as e:
            logger.warning("MinIO upload failed, file stored in task only: %s", e)

        task = {
            "task_id": task_id,
            "workspace_id": workspace_id,
            "file_name": file_name,
            "file_type": file_type,
            "storage_key": storage_key,
            "status": "uploaded",
            "source": "upload",
            "process_steps": [{"step": "upload", "status": "success", "timestamp": now}],
            "transform_rules": [],
            "created_at": now,
            "updated_at": now,
        }
        self.storage.save_task(task)

        return {
            "task_id": task_id,
            "workspace_id": workspace_id,
            "file_name": file_name,
            "file_type": file_type,
            "storage_key": storage_key,
            "status": "uploaded",
            "created_at": now,
        }

    def process_file(self, task_id: str) -> Dict[str, Any]:
        task = self.storage.get_task(task_id)
        if not task:
            return {"status": "error", "message": f"Task {task_id} not found"}

        if task.get("status") not in ("uploaded", "pending"):
            return {"status": "error", "message": f"Task {task_id} is in status '{task.get('status')}', cannot process"}

        file_type = task.get("file_type", "")
        file_data = self._retrieve_file_data(task)
        process_steps = task.get("process_steps", [])
        extracted_text = ""
        extracted_tables = []

        try:
            self.storage.update_task(task_id, {"status": "processing"})

            if file_type == "pdf":
                result = self.pdf_processor.extract_text(file_data or b"")
                if result.get("status") in ("success", "fallback"):
                    extracted_text = result.get("text", "")
                    process_steps.append({"step": "pdf_text_extract", "status": result.get("status"), "timestamp": datetime.now().isoformat()})

                table_result = self.pdf_processor.extract_tables(file_data or b"")
                if table_result.get("status") == "success":
                    extracted_tables = table_result.get("tables", [])
                    process_steps.append({"step": "pdf_table_extract", "status": "success", "table_count": len(extracted_tables), "timestamp": datetime.now().isoformat()})

            elif file_type in ("word", "docx"):
                result = self.word_processor.extract_text(file_data or b"")
                if result.get("status") in ("success", "fallback"):
                    extracted_text = result.get("text", "")
                    process_steps.append({"step": "word_text_extract", "status": result.get("status"), "timestamp": datetime.now().isoformat()})

                table_result = self.word_processor.extract_tables(file_data or b"")
                if table_result.get("status") == "success":
                    extracted_tables = table_result.get("tables", [])
                    process_steps.append({"step": "word_table_extract", "status": "success", "table_count": len(extracted_tables), "timestamp": datetime.now().isoformat()})

            elif file_type in ("image", "png", "jpg", "jpeg", "tiff", "bmp"):
                result = self.ocr_processor.extract_text(file_data or b"")
                if result.get("status") in ("success", "fallback"):
                    extracted_text = result.get("text", "")
                    process_steps.append({"step": "ocr_extract", "status": result.get("status"), "engine": result.get("engine"), "timestamp": datetime.now().isoformat()})
            else:
                extracted_text = file_data.decode("utf-8", errors="replace") if file_data else ""
                process_steps.append({"step": "raw_text_decode", "status": "success", "timestamp": datetime.now().isoformat()})

            self.storage.update_task(task_id, {
                "status": "completed",
                "extracted_text": extracted_text,
                "extracted_tables": extracted_tables,
                "process_steps": process_steps,
            })

            return {
                "task_id": task_id,
                "status": "completed",
                "extracted_text_length": len(extracted_text),
                "table_count": len(extracted_tables),
                "process_steps": process_steps,
            }
        except Exception as e:
            logger.error("File processing failed for task %s: %s", task_id, e)
            self.storage.update_task(task_id, {
                "status": "failed",
                "error_message": str(e),
                "process_steps": process_steps,
            })
            return {"status": "error", "message": str(e), "task_id": task_id}

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        task = self.storage.get_task(task_id)
        if not task:
            return {"status": "error", "message": f"Task {task_id} not found"}
        return task

    def batch_import(self, entity_type_id: str, data: Any, format: str, workspace_id: str) -> Dict[str, Any]:
        if format == "csv":
            result = self.batch_importer.import_csv(entity_type_id, data, workspace_id)
        elif format == "json":
            result = self.batch_importer.import_json(entity_type_id, data, workspace_id)
        else:
            return {"status": "error", "message": f"Unsupported format: {format}"}

        try:
            from odap.biz.core.ontology.design.engine.impl.audit_recorder_impl import AuditRecorderImpl
            recorder = AuditRecorderImpl()
            recorder.record_ingest(
                entity_type_id=entity_type_id,
                source=f"batch_import_{format}",
                process_steps=[{"step": "batch_import", "format": format, "success_count": result.get("success_count", 0), "fail_count": result.get("fail_count", 0)}],
                transform_rules=[],
                result=result.get("status", "unknown"),
            )
        except Exception as e:
            logger.warning("Audit recording failed for batch import: %s", e)

        return result

    def _detect_file_type(self, file_name: str) -> str:
        if not file_name:
            return "unknown"
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        mapping = {
            "pdf": "pdf",
            "doc": "word", "docx": "word",
            "png": "image", "jpg": "image", "jpeg": "image", "tiff": "image", "bmp": "image", "gif": "image",
            "txt": "text", "csv": "csv", "json": "json",
        }
        return mapping.get(ext, "unknown")

    def _retrieve_file_data(self, task: Dict[str, Any]) -> Optional[bytes]:
        storage_key = task.get("storage_key")
        if not storage_key:
            return None

        try:
            from odap.infra.storage.minio_client import get_minio_client
            minio = get_minio_client()
            if minio.available:
                result = minio.download_object("odap-ingestion", storage_key)
                if result.get("status") == "success":
                    return result.get("data")
        except Exception as e:
            logger.warning("MinIO download failed: %s", e)

        return None


# 向后兼容 — 代理到 construction/ingestion/
# IngestService（单例）保留原类代码不变，仅新增此桥接说明
# 新代码请使用 odap.biz.core.ontology.construction.ingestion.UnifiedIngestionService
