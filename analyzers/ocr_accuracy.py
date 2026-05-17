"""
OCR Accuracy Analyzer.

Uses pytesseract to assess the quality of text recognition on a scanned document.
Words with high OCR confidence indicate that the document scan is clear and legible.
"""

import numpy as np
import cv2


class OCRAccuracyAnalyzer:
    """
    Analyzes a scanned document image for OCR readability using pytesseract.

    pytesseract returns per-word confidence scores (0-100). The average of
    these scores is used as the overall scan quality proxy.
    """

    # Minimum pytesseract confidence for a word to be considered "good"
    GOOD_WORD_THRESHOLD = 70

    # Fixed analyzer confidence (tesseract confidence is well-calibrated)
    ANALYZER_CONFIDENCE = 0.9

    def analyze(self, image: np.ndarray) -> dict:
        """
        Analyze an image for OCR readability.

        Args:
            image: BGR numpy array. Grayscale images are converted automatically.

        Returns:
            dict with keys:
                passed (bool): True if score >= 70.
                score (float): 0-100, equal to avg pytesseract word confidence.
                confidence (float): Fixed at 0.9.
                details (dict): word_count, avg_confidence, good_word_count, etc.
                visualization (np.ndarray): BGR image with bounding boxes.
        """
        try:
            import pytesseract
            from pytesseract import Output
            pytesseract_available = True
        except ImportError:
            pytesseract_available = False

        if not pytesseract_available:
            blank = image.copy() if image is not None else np.zeros((100, 100, 3), dtype=np.uint8)
            return {
                "passed": False,
                "score": 0.0,
                "confidence": 0.0,
                "details": {
                    "error": "pytesseract is not installed. Install it with: pip install pytesseract",
                    "tesseract_installed": False,
                },
                "visualization": blank,
            }

        try:
            img = self._ensure_bgr(image)
            vis = img.copy()

            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DATAFRAME)

            # Filter: keep only rows with valid confidence and non-empty text
            valid = data[(data["conf"] > 0) & (data["text"].str.strip() != "")]

            if valid.empty:
                score = 0.0
                avg_confidence = 0.0
                word_count = 0
                good_word_count = 0
            else:
                avg_confidence = float(valid["conf"].mean())
                word_count = len(valid)
                good_word_count = int((valid["conf"] >= self.GOOD_WORD_THRESHOLD).sum())
                score = avg_confidence  # already 0-100

            passed = score >= 70.0

            # Draw bounding boxes
            if not valid.empty:
                vis = self._draw_word_boxes(vis, valid)

            # Add score label
            cv2.putText(
                vis,
                f"OCR avg conf: {avg_confidence:.1f}  words: {word_count}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 200, 0) if passed else (0, 0, 200),
                2,
                cv2.LINE_AA,
            )

            details = {
                "avg_confidence": round(avg_confidence, 2),
                "word_count": word_count,
                "good_word_count": good_word_count,
                "good_word_ratio": round(good_word_count / max(word_count, 1), 3),
                "tesseract_installed": True,
            }

            return {
                "passed": passed,
                "score": round(score, 2),
                "confidence": self.ANALYZER_CONFIDENCE,
                "details": details,
                "visualization": vis,
            }

        except Exception as exc:
            blank = image.copy() if image is not None else np.zeros((100, 100, 3), dtype=np.uint8)
            return {
                "passed": False,
                "score": 0.0,
                "confidence": 0.0,
                "details": {"error": str(exc)},
                "visualization": blank,
            }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_bgr(self, image: np.ndarray) -> np.ndarray:
        """Convert grayscale or BGRA to BGR."""
        if image.ndim == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        return image.copy()

    def _draw_word_boxes(self, vis: np.ndarray, data) -> np.ndarray:
        """
        Draw green bounding boxes for high-confidence words,
        red boxes for low-confidence words.
        """
        for _, row in data.iterrows():
            try:
                x = int(row["left"])
                y = int(row["top"])
                w = int(row["width"])
                h = int(row["height"])
                conf = float(row["conf"])

                if w <= 0 or h <= 0:
                    continue

                color = (0, 200, 0) if conf >= self.GOOD_WORD_THRESHOLD else (0, 0, 200)
                cv2.rectangle(vis, (x, y), (x + w, y + h), color, 1)
            except (ValueError, TypeError):
                continue

        return vis
