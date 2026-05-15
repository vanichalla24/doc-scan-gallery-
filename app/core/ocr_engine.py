"""OCR engine using PaddleOCR with multilingual support."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from app.models.data_models import OCRResult


LANGUAGE_MAP = {
    "English": "en",
    "Korean": "korean",
    "Chinese": "ch",
    "Japanese": "japan",
    "Hindi": "hi",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Arabic": "ar",
    "Russian": "ru",
    "Portuguese": "pt",
    "Italian": "it",
    "Dutch": "nl",
    "Thai": "th",
    "Vietnamese": "vi",
}


class OCREngine:
    """Wrapper around PaddleOCR providing multilingual text extraction."""

    _instances: Dict[str, Any] = {}

    def __init__(self, language: str = "en", confidence_threshold: float = 0.6):
        self.language = language
        self.confidence_threshold = confidence_threshold
        self._ocr = None

    def _get_ocr(self):
        if self.language not in OCREngine._instances:
            try:
                from paddleocr import PaddleOCR
                logger.info(f"Initializing PaddleOCR for language: {self.language}")
                OCREngine._instances[self.language] = PaddleOCR(
                    use_angle_cls=True,
                    lang=self.language,
                    show_log=False,
                    use_gpu=False,
                )
            except ImportError:
                logger.warning("PaddleOCR not available, using fallback OCR")
                OCREngine._instances[self.language] = None
            except Exception as e:
                logger.error(f"Failed to initialize PaddleOCR: {e}")
                OCREngine._instances[self.language] = None
        return OCREngine._instances[self.language]

    def extract_text(self, image_path: str) -> OCRResult:
        """Extract text from an image file."""
        start = time.time()
        ocr = self._get_ocr()

        if ocr is None:
            return self._fallback_ocr(image_path)

        try:
            result = ocr.ocr(image_path, cls=True)
            return self._parse_paddle_result(result, time.time() - start)
        except Exception as e:
            logger.error(f"OCR failed for {image_path}: {e}")
            return OCRResult(text="", confidence=0.0)

    def extract_text_from_array(self, image_array: np.ndarray) -> OCRResult:
        """Extract text from a numpy image array."""
        ocr = self._get_ocr()
        if ocr is None:
            return OCRResult(text="", confidence=0.0)
        try:
            result = ocr.ocr(image_array, cls=True)
            return self._parse_paddle_result(result)
        except Exception as e:
            logger.error(f"OCR from array failed: {e}")
            return OCRResult(text="", confidence=0.0)

    def _parse_paddle_result(self, result: Any, elapsed: float = 0.0) -> OCRResult:
        if not result or result[0] is None:
            return OCRResult(text="", confidence=0.0)

        texts = []
        confidences = []
        bboxes = []

        for page in result:
            if page is None:
                continue
            for line in page:
                if not line or len(line) < 2:
                    continue
                bbox, (text, conf) = line
                if conf >= self.confidence_threshold:
                    texts.append(text)
                    confidences.append(conf)
                    bboxes.append({
                        "text": text,
                        "confidence": conf,
                        "bbox": bbox,
                    })

        full_text = " ".join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            bounding_boxes=bboxes,
            language_detected=self.language,
        )

    def _fallback_ocr(self, image_path: str) -> OCRResult:
        """Simple fallback when PaddleOCR is unavailable."""
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            return OCRResult(text=text.strip(), confidence=0.5)
        except Exception:
            logger.warning(f"Fallback OCR also failed for {image_path}")
            return OCRResult(text="[OCR unavailable]", confidence=0.0)

    @staticmethod
    def get_lang_code(language_name: str) -> str:
        return LANGUAGE_MAP.get(language_name, "en")

    def compute_ocr_accuracy(
        self, original_text: str, translated_text: str
    ) -> Tuple[float, List[str]]:
        """
        Compute OCR accuracy score comparing text presence/quality.
        Returns (score 0-100, list of issues).
        """
        issues = []

        if not original_text and not translated_text:
            return 50.0, ["Both images produced no OCR text"]

        if not translated_text:
            issues.append("No text detected in translated image")
            return 0.0, issues

        if not original_text:
            return 70.0, []

        orig_words = set(original_text.lower().split())
        trans_words = set(translated_text.lower().split())

        orig_len = len(original_text)
        trans_len = len(translated_text)

        length_ratio = min(orig_len, trans_len) / max(orig_len, trans_len) if max(orig_len, trans_len) > 0 else 0
        score = min(100.0, length_ratio * 80 + 20)

        if trans_len < orig_len * 0.3:
            issues.append("Translated text significantly shorter than original")
            score = min(score, 40.0)

        return round(score, 2), issues
