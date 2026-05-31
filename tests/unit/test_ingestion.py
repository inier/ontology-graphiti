import pytest
import json
from unittest.mock import patch, MagicMock


class TestPDFProcessor:
    @pytest.fixture
    def processor(self):
        from odap.biz.core.ontology.ingestion.impl.pdf_processor import PDFProcessor
        return PDFProcessor()

    def test_pdf_processor_extract_text_fallback(self, processor):
        result = processor.extract_text(b"sample text content")
        assert result["source_type"] == "pdf"
        assert "status" in result
        if result["status"] == "fallback":
            assert "text" in result

    def test_pdf_processor_fallback_with_bytes(self, processor):
        text_bytes = "Hello PDF World".encode("utf-8")
        result = processor._fallback_extract_text(text_bytes)
        assert result["status"] == "fallback"
        assert result["text"] == "Hello PDF World"
        assert result["source_type"] == "pdf"

    def test_pdf_processor_fallback_with_invalid_bytes(self, processor):
        invalid_bytes = b"\xff\xfe\x00\x01"
        result = processor._fallback_extract_text(invalid_bytes)
        assert result["source_type"] == "pdf"

    def test_pdf_processor_extract_text_with_path(self, processor, tmp_path):
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"dummy pdf content")
        result = processor._fallback_extract_text(str(test_file))
        assert result["source_type"] == "pdf"

    def test_pdf_processor_extract_tables_fallback(self, processor):
        result = processor.extract_tables(b"sample")
        assert "tables" in result


class TestWordProcessor:
    @pytest.fixture
    def processor(self):
        from odap.biz.core.ontology.ingestion.impl.word_processor import WordProcessor
        return WordProcessor()

    def test_word_processor_extract_text_fallback(self, processor):
        text_bytes = "Hello Word Document".encode("utf-8")
        result = processor.extract_text(text_bytes)
        assert result["source_type"] == "word"
        assert "status" in result
        if result["status"] == "fallback":
            assert result["text"] == "Hello Word Document"

    def test_word_processor_fallback_with_bytes(self, processor):
        text_bytes = "Word content here".encode("utf-8")
        result = processor._fallback_extract_text(text_bytes)
        assert result["status"] == "fallback"
        assert result["text"] == "Word content here"
        assert result["source_type"] == "word"

    def test_word_processor_fallback_with_invalid_bytes(self, processor):
        invalid_bytes = b"\xff\xfe\x00\x01"
        result = processor._fallback_extract_text(invalid_bytes)
        assert result["source_type"] == "word"

    def test_word_processor_extract_tables_fallback(self, processor):
        result = processor.extract_tables(b"sample")
        assert "tables" in result


class TestOCRProcessor:
    @pytest.fixture
    def processor(self):
        from odap.biz.core.ontology.ingestion.impl.ocr_processor import OCRProcessor
        return OCRProcessor()

    def test_ocr_processor_extract_text(self, processor):
        result = processor.extract_text(b"\x89PNG\r\n\x1a\n")
        assert result["source_type"] == "ocr"
        assert "status" in result

    def test_ocr_processor_fallback(self, processor):
        result = processor._fallback_extract(b"fake image data")
        assert result["status"] == "fallback"
        assert result["text"] == ""
        assert result["engine"] == "none"
        assert result["source_type"] == "ocr"


class TestBatchImporter:
    @pytest.fixture
    def importer(self):
        from odap.biz.core.ontology.ingestion.impl.batch_importer import BatchImporter
        return BatchImporter()

    def test_batch_import_csv(self, importer):
        csv_data = "name,value,category\nAlpha,100,A\nBeta,200,B\nGamma,300,C"
        result = importer.import_csv("et-1", csv_data, "ws-1")
        assert result["status"] == "success"
        assert result["success_count"] == 3
        assert result["fail_count"] == 0
        assert result["format"] == "csv"

    def test_batch_import_csv_empty(self, importer):
        csv_data = ""
        result = importer.import_csv("et-1", csv_data, "ws-1")
        assert result["status"] == "success"
        assert result["success_count"] == 0

    def test_batch_import_json(self, importer):
        json_data = json.dumps([
            {"name": "Alpha", "value": 100},
            {"name": "Beta", "value": 200},
        ])
        result = importer.import_json("et-1", json_data, "ws-1")
        assert result["status"] == "success"
        assert result["success_count"] == 2
        assert result["format"] == "json"

    def test_batch_import_json_single_object(self, importer):
        json_data = json.dumps({"name": "Alpha", "value": 100})
        result = importer.import_json("et-1", json_data, "ws-1")
        assert result["status"] == "success"
        assert result["success_count"] == 1

    def test_batch_import_json_invalid_items(self, importer):
        json_data = json.dumps([{"name": "Alpha"}, "not_a_dict", 42])
        result = importer.import_json("et-1", json_data, "ws-1")
        assert result["success_count"] == 1
        assert result["fail_count"] == 2

    def test_batch_import_json_invalid_json_string(self, importer):
        result = importer.import_json("et-1", "not valid json{{{", "ws-1")
        assert result["status"] == "error"

    def test_batch_import_validation(self, importer):
        json_data = json.dumps([
            {"name": "Valid", "id": "inst-1"},
            {"name": "NoId"},
        ])
        result = importer.import_json("et-1", json_data, "ws-1")
        assert result["success_count"] == 2
        assert all(item.get("id") for item in [{"id": "inst-1"}, {"id": "auto"}])


class TestIngestService:
    @pytest.fixture
    def service(self, tmp_path):
        from odap.biz.core.ontology.ingestion.storage.sqlite_ingest_storage import SQLiteIngestTaskStorage
        from odap.biz.core.ontology.ingestion.services.ingest_service import IngestService
        IngestService._instance = None
        storage = SQLiteIngestTaskStorage(db_path=str(tmp_path / "ingest_test.db"))
        svc = IngestService.__new__(IngestService)
        svc.storage = storage
        from odap.biz.core.ontology.ingestion.impl.pdf_processor import PDFProcessor
        from odap.biz.core.ontology.ingestion.impl.word_processor import WordProcessor
        from odap.biz.core.ontology.ingestion.impl.ocr_processor import OCRProcessor
        from odap.biz.core.ontology.ingestion.impl.batch_importer import BatchImporter
        svc.pdf_processor = PDFProcessor()
        svc.word_processor = WordProcessor()
        svc.ocr_processor = OCRProcessor()
        svc.batch_importer = BatchImporter()
        svc._initialized = True
        IngestService._instance = svc
        return svc

    def test_ingest_service_upload(self, service):
        result = service.upload_file("test.pdf", b"pdf content", "ws-1", "application/pdf")
        assert "task_id" in result
        assert result["file_name"] == "test.pdf"
        assert result["file_type"] == "pdf"
        assert result["status"] == "uploaded"

    def test_ingest_service_process(self, service):
        upload = service.upload_file("test.txt", b"hello world", "ws-1")
        task_id = upload["task_id"]
        result = service.process_file(task_id)
        assert result["task_id"] == task_id

    def test_ingest_service_process_not_found(self, service):
        result = service.process_file("nonexistent")
        assert result.get("status") == "error"

    def test_ingest_service_task_status(self, service):
        upload = service.upload_file("test.pdf", b"content", "ws-1")
        task_id = upload["task_id"]
        result = service.get_task_status(task_id)
        assert result["task_id"] == task_id
        assert result["status"] == "uploaded"

    def test_ingest_service_task_status_not_found(self, service):
        result = service.get_task_status("nonexistent")
        assert result.get("status") == "error"

    def test_ingest_service_detect_file_type(self, service):
        assert service._detect_file_type("doc.pdf") == "pdf"
        assert service._detect_file_type("doc.docx") == "word"
        assert service._detect_file_type("img.png") == "image"
        assert service._detect_file_type("data.csv") == "csv"
        assert service._detect_file_type("unknown.xyz") == "unknown"
        assert service._detect_file_type("") == "unknown"

    def test_ingest_service_batch_import_csv(self, service):
        csv_data = "name,value\nAlpha,100"
        result = service.batch_import("et-1", csv_data, "csv", "ws-1")
        assert result["status"] == "success"
        assert result["format"] == "csv"

    def test_ingest_service_batch_import_json(self, service):
        json_data = json.dumps([{"name": "Alpha"}])
        result = service.batch_import("et-1", json_data, "json", "ws-1")
        assert result["status"] == "success"
        assert result["format"] == "json"

    def test_ingest_service_batch_import_unsupported(self, service):
        result = service.batch_import("et-1", "", "xml", "ws-1")
        assert result.get("status") == "error"


class TestSQLiteIngestTaskStorage:
    @pytest.fixture
    def storage(self, tmp_path):
        from odap.biz.core.ontology.ingestion.storage.sqlite_ingest_storage import SQLiteIngestTaskStorage
        return SQLiteIngestTaskStorage(db_path=str(tmp_path / "ingest_storage_test.db"))

    def test_save_and_get_task(self, storage):
        task = {
            "task_id": "t-1",
            "workspace_id": "ws-1",
            "file_name": "test.pdf",
            "file_type": "pdf",
            "status": "uploaded",
            "source": "upload",
            "process_steps": [{"step": "upload", "status": "success"}],
            "transform_rules": [],
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
        storage.save_task(task)
        result = storage.get_task("t-1")
        assert result is not None
        assert result["task_id"] == "t-1"
        assert len(result["process_steps"]) == 1

    def test_get_task_not_found(self, storage):
        result = storage.get_task("nonexistent")
        assert result is None

    def test_update_task(self, storage):
        task = {
            "task_id": "t-1",
            "workspace_id": "ws-1",
            "status": "uploaded",
            "process_steps": [],
            "transform_rules": [],
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
        storage.save_task(task)
        storage.update_task("t-1", {"status": "completed", "extracted_text": "hello"})
        result = storage.get_task("t-1")
        assert result["status"] == "completed"
        assert result["extracted_text"] == "hello"

    def test_list_tasks(self, storage):
        for i in range(3):
            storage.save_task({
                "task_id": f"t-{i}",
                "workspace_id": "ws-1",
                "status": "uploaded",
                "process_steps": [],
                "transform_rules": [],
                "created_at": f"2026-01-0{i+1}T00:00:00",
                "updated_at": f"2026-01-0{i+1}T00:00:00",
            })
        results = storage.list_tasks(workspace_id="ws-1")
        assert len(results) == 3
