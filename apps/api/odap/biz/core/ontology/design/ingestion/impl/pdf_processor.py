import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False


class PDFProcessor:
    def extract_text(self, file_path_or_bytes: Union[str, bytes]) -> Dict[str, Any]:
        if not PDFPLUMBER_AVAILABLE:
            return self._fallback_extract_text(file_path_or_bytes)

        try:
            if isinstance(file_path_or_bytes, bytes):
                import io
                source = io.BytesIO(file_path_or_bytes)
            else:
                source = file_path_or_bytes

            pages_text = []
            with pdfplumber.open(source) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    pages_text.append(text)

            full_text = "\n\n".join(pages_text)
            return {
                "status": "success",
                "text": full_text,
                "page_count": len(pages_text),
                "source_type": "pdf",
            }
        except Exception as e:
            logger.warning("PDF text extraction failed: %s", e)
            return self._fallback_extract_text(file_path_or_bytes)

    def extract_tables(self, file_path_or_bytes: Union[str, bytes]) -> Dict[str, Any]:
        if not PDFPLUMBER_AVAILABLE:
            return {"status": "fallback", "tables": [], "message": "pdfplumber not available"}

        try:
            if isinstance(file_path_or_bytes, bytes):
                import io
                source = io.BytesIO(file_path_or_bytes)
            else:
                source = file_path_or_bytes

            all_tables = []
            with pdfplumber.open(source) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    for table_idx, table in enumerate(tables):
                        if table and len(table) > 0:
                            headers = table[0] if table else []
                            rows = table[1:] if len(table) > 1 else []
                            all_tables.append({
                                "page": page_idx + 1,
                                "table_index": table_idx + 1,
                                "headers": headers,
                                "rows": rows,
                                "row_count": len(rows),
                            })

            return {
                "status": "success",
                "tables": all_tables,
                "table_count": len(all_tables),
                "source_type": "pdf",
            }
        except Exception as e:
            logger.warning("PDF table extraction failed: %s", e)
            return {"status": "error", "tables": [], "message": str(e)}

    def _fallback_extract_text(self, file_path_or_bytes: Union[str, bytes]) -> Dict[str, Any]:
        if isinstance(file_path_or_bytes, bytes):
            try:
                text = file_path_or_bytes.decode("utf-8", errors="replace")
                return {
                    "status": "fallback",
                    "text": text,
                    "page_count": 1,
                    "source_type": "pdf",
                    "message": "pdfplumber not available, raw bytes decoded",
                }
            except Exception:
                return {"status": "error", "text": "", "page_count": 0, "source_type": "pdf", "message": "pdfplumber not available and bytes decode failed"}

        try:
            with open(file_path_or_bytes, "rb") as f:
                raw = f.read()
            text = raw.decode("utf-8", errors="replace")
            return {
                "status": "fallback",
                "text": text,
                "page_count": 1,
                "source_type": "pdf",
                "message": "pdfplumber not available, raw file decoded",
            }
        except Exception as e:
            return {"status": "error", "text": "", "page_count": 0, "source_type": "pdf", "message": str(e)}
