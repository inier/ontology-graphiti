"""DocumentParser unit tests.

Covers:
- test_parse_txt_file: real .txt file with tmp_path
- test_parse_csv_file: real .csv file with tmp_path
- test_parse_json_file: real .json file with tmp_path
- test_parse_xml_file: real .xml file with tmp_path
- test_parse_unsupported_format_raises: ValueError for .xyz
- test_parse_nonexistent_file_raises: FileNotFoundError for missing file
- test_chunk_text_short_text: single chunk for short text
- test_chunk_text_long_text: multiple chunks for long text
- test_chunk_text_respects_paragraph_breaks: split at paragraph boundaries
- test_parse_pdf_fallback_to_pypdf2: PDFProcessor fails, PyPDF2 succeeds
- test_parse_docx_fallback_to_python_docx: WordProcessor fails, python-docx succeeds
- test_parse_image_fallback_to_pytesseract: OCRProcessor fails, pytesseract succeeds
- test_parse_excel_with_openpyxl: real .xlsx with tmp_path
- test_parse_routes_by_extension: .md routes to _parse_txt, .xls routes to _parse_excel

Rules (AGENTS.md):
- Uses tmp_path fixture for real file creation (NOT MagicMock for storage)
- Mock external processors (PDFProcessor, WordProcessor, OCRProcessor) but NOT DocumentParser itself
- Import DocumentParser inside fixtures to avoid import errors
"""

import json
import os
import sys

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def parser():
    from odap.biz.core.ontology.extraction.impl.document_parser import DocumentParser
    return DocumentParser()


class TestDocumentParser:

    def test_parse_txt_file(self, parser, tmp_path):
        txt_file = tmp_path / "sample.txt"
        txt_file.write_text("Hello world\nSecond line", encoding="utf-8")
        result = parser.parse(str(txt_file))
        assert result == "Hello world\nSecond line"

    def test_parse_csv_file(self, parser, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("name,age\nAlice,30\nBob,25", encoding="utf-8")
        result = parser.parse(str(csv_file))
        lines = result.split("\n")
        assert lines[0] == "name, age"
        assert lines[1] == "Alice, 30"
        assert lines[2] == "Bob, 25"

    def test_parse_json_file(self, parser, tmp_path):
        json_file = tmp_path / "config.json"
        data = {"key": "value", "count": 42, "nested": {"a": 1}}
        json_file.write_text(json.dumps(data), encoding="utf-8")
        result = parser.parse(str(json_file))
        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["count"] == 42
        assert parsed["nested"]["a"] == 1

    def test_parse_xml_file(self, parser, tmp_path):
        xml_file = tmp_path / "doc.xml"
        xml_content = "<root><title>Hello</title><desc>World</desc></root>"
        xml_file.write_text(xml_content, encoding="utf-8")
        result = parser.parse(str(xml_file))
        assert "title: Hello" in result
        assert "desc: World" in result

    def test_parse_unsupported_format_raises(self, parser, tmp_path):
        xyz_file = tmp_path / "unknown.xyz"
        xyz_file.write_text("data", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported file format"):
            parser.parse(str(xyz_file))

    def test_parse_nonexistent_file_raises(self, parser):
        with pytest.raises(FileNotFoundError, match="File not found"):
            parser.parse("/nonexistent/path/file.txt")

    def test_chunk_text_short_text(self, parser):
        text = "Short text"
        chunks = parser.chunk_text(text, max_tokens=4000)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_text_long_text(self, parser):
        max_tokens = 100
        max_chars = max_tokens * 2
        text = "a" * (max_chars + 500)
        chunks = parser.chunk_text(text, max_tokens=max_tokens)
        assert len(chunks) > 1
        assert "".join(chunks) == text

    def test_chunk_text_respects_paragraph_breaks(self, parser):
        max_tokens = 50
        max_chars = max_tokens * 2
        para1 = "a" * (max_chars - 10)
        para2 = "b" * (max_chars - 10)
        text = para1 + "\n\n" + para2
        chunks = parser.chunk_text(text, max_tokens=max_tokens)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= max_chars + 2

    def test_parse_pdf_fallback_to_pypdf2(self, parser, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        mock_reader_cls = MagicMock()
        mock_reader_instance = MagicMock()
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 text"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2 text"
        mock_reader_instance.pages = [mock_page1, mock_page2]
        mock_reader_cls.return_value = mock_reader_instance

        fake_pypdf2 = MagicMock()
        fake_pypdf2.PdfReader = mock_reader_cls

        with patch.dict(sys.modules, {
            "odap.biz.core.ontology.design.ingestion.impl.pdf_processor": None,
            "PyPDF2": fake_pypdf2,
        }):
            result = parser._parse_pdf(str(pdf_file))
            assert "Page 1 text" in result
            assert "Page 2 text" in result
            mock_reader_cls.assert_called_once_with(str(pdf_file))

    def test_parse_docx_fallback_to_python_docx(self, parser, tmp_path):
        docx_file = tmp_path / "test.docx"
        docx_file.write_bytes(b"PK fake docx")

        mock_document_cls = MagicMock()
        mock_doc_instance = MagicMock()
        mock_para1 = MagicMock()
        mock_para1.text = "Paragraph 1"
        mock_para2 = MagicMock()
        mock_para2.text = "Paragraph 2"
        mock_doc_instance.paragraphs = [mock_para1, mock_para2]
        mock_document_cls.return_value = mock_doc_instance

        fake_docx = MagicMock()
        fake_docx.Document = mock_document_cls

        with patch.dict(sys.modules, {
            "odap.biz.core.ontology.design.ingestion.impl.word_processor": None,
            "docx": fake_docx,
        }):
            result = parser._parse_docx(str(docx_file))
            assert "Paragraph 1" in result
            assert "Paragraph 2" in result
            mock_document_cls.assert_called_once_with(str(docx_file))

    def test_parse_image_fallback_to_pytesseract(self, parser, tmp_path):
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0 fake jpeg")

        mock_image_cls = MagicMock()
        mock_img_instance = MagicMock()
        mock_image_cls.return_value = mock_img_instance

        mock_pytesseract = MagicMock()
        mock_pytesseract.image_to_string.return_value = "Extracted OCR text"

        fake_pil = MagicMock()
        fake_pil.Image = MagicMock(open=mock_image_cls)

        with patch.dict(sys.modules, {
            "odap.biz.core.ontology.design.ingestion.impl.ocr_processor": None,
            "pytesseract": mock_pytesseract,
            "PIL": fake_pil,
            "PIL.Image": fake_pil.Image,
        }):
            result = parser._parse_image(str(img_file))
            assert "Extracted OCR text" in result
            mock_pytesseract.image_to_string.assert_called_once()

    def test_parse_excel_with_openpyxl(self, parser, tmp_path):
        try:
            from openpyxl import Workbook
        except ImportError:
            pytest.skip("openpyxl not installed")

        xlsx_file = tmp_path / "data.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(["Name", "Score"])
        ws.append(["Alice", 95])
        ws.append(["Bob", 87])
        wb.save(str(xlsx_file))
        wb.close()

        result = parser.parse(str(xlsx_file))
        assert "Name" in result
        assert "Alice" in result
        assert "87" in result

    def test_parse_routes_by_extension(self, parser, tmp_path):
        md_file = tmp_path / "readme.md"
        md_file.write_text("# Title\nSome markdown", encoding="utf-8")
        with patch.object(parser, "_parse_txt", wraps=parser._parse_txt) as spy_txt:
            result = parser.parse(str(md_file))
            spy_txt.assert_called_once_with(str(md_file))
            assert "Some markdown" in result

        xls_file = tmp_path / "legacy.xls"
        xls_file.write_bytes(b"\xd0\xcf\x11\xe0 fake xls")
        with patch.object(parser, "_parse_excel") as mock_excel:
            mock_excel.return_value = "Excel content"
            result = parser.parse(str(xls_file))
            mock_excel.assert_called_once_with(str(xls_file))
