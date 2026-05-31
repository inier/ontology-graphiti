import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from PIL import Image
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False


class OCRProcessor:
    _paddle_instance = None

    def extract_text(self, image_bytes: bytes) -> Dict[str, Any]:
        if PYTESSERACT_AVAILABLE:
            return self._extract_with_tesseract(image_bytes)

        if PADDLEOCR_AVAILABLE:
            return self._extract_with_paddle(image_bytes)

        return self._fallback_extract(image_bytes)

    def _extract_with_tesseract(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            import io
            from PIL import Image

            image = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(image, lang="chi_sim+eng")

            return {
                "status": "success",
                "text": text,
                "engine": "tesseract",
                "source_type": "ocr",
            }
        except Exception as e:
            logger.warning("Tesseract OCR failed: %s", e)
            if PADDLEOCR_AVAILABLE:
                return self._extract_with_paddle(image_bytes)
            return self._fallback_extract(image_bytes)

    def _extract_with_paddle(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            import io
            from PIL import Image

            if OCRProcessor._paddle_instance is None:
                OCRProcessor._paddle_instance = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)

            image = Image.open(io.BytesIO(image_bytes))
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                image.save(tmp, format="PNG")
                tmp_path = tmp.name

            try:
                result = OCRProcessor._paddle_instance.ocr(tmp_path, cls=True)
                texts = []
                if result and result[0]:
                    for line in result[0]:
                        if line and len(line) >= 2:
                            texts.append(line[1][0])
                full_text = "\n".join(texts)
            finally:
                os.unlink(tmp_path)

            return {
                "status": "success",
                "text": full_text,
                "engine": "paddleocr",
                "source_type": "ocr",
            }
        except Exception as e:
            logger.warning("PaddleOCR failed: %s", e)
            return self._fallback_extract(image_bytes)

    def _fallback_extract(self, image_bytes: bytes) -> Dict[str, Any]:
        return {
            "status": "fallback",
            "text": "",
            "engine": "none",
            "source_type": "ocr",
            "message": "No OCR engine available (pytesseract/PaddleOCR not installed)",
        }
