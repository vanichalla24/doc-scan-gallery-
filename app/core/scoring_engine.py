"""Weighted scoring engine for TransLingo QA Studio."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from loguru import logger

from app.models.data_models import (
    ImageValidationResult,
    OCRResult,
    ParameterScore,
    ScoreBand,
    ScoringWeights,
)
from app.core.ocr_engine import OCREngine
from app.core.semantic_validator import SemanticValidator
from app.core.visual_validator import VisualValidator


class ScoringEngine:
    """Orchestrates all validation checks and computes a weighted final score."""

    def __init__(self, weights: ScoringWeights = None):
        self.weights = weights or ScoringWeights()
        self.ocr_engine = OCREngine()
        self.semantic_validator = SemanticValidator()
        self.visual_validator = VisualValidator()

    def validate_image_pair(
        self,
        original_path: str,
        translated_path: str,
        image_name: str,
        engine_name: str,
        source_lang: str = "English",
        target_lang: str = "Korean",
        ocr_lang: str = "en",
    ) -> ImageValidationResult:
        """Run all validation checks and return a scored result."""
        import time
        start = time.time()

        result = ImageValidationResult(
            image_name=image_name,
            engine=engine_name,
            original_path=original_path,
            translated_path=translated_path,
        )

        try:
            self.ocr_engine.language = ocr_lang
            orig_ocr = self.ocr_engine.extract_text(original_path)
            trans_ocr = self.ocr_engine.extract_text(translated_path)

            result.original_ocr = orig_ocr
            result.translated_ocr = trans_ocr

            params = {}

            # 1. OCR Accuracy
            ocr_score, ocr_issues = self.ocr_engine.compute_ocr_accuracy(
                orig_ocr.text, trans_ocr.text
            )
            params["ocr_accuracy"] = ParameterScore(
                name="OCR Accuracy",
                score=ocr_score,
                weight=self.weights.ocr_accuracy,
                weighted_score=ocr_score * self.weights.ocr_accuracy / 100,
                issues=ocr_issues,
            )

            # 2. Semantic Similarity
            sem_score, sem_issues = self.semantic_validator.compute_similarity(
                orig_ocr.text, trans_ocr.text
            )
            params["semantic_similarity"] = ParameterScore(
                name="Semantic Similarity",
                score=sem_score,
                weight=self.weights.semantic_similarity,
                weighted_score=sem_score * self.weights.semantic_similarity / 100,
                issues=sem_issues,
            )

            # 3. Character Coverage
            cov_score, cov_issues = self.semantic_validator.compute_character_coverage(
                orig_ocr.text, trans_ocr.text
            )
            params["character_coverage"] = ParameterScore(
                name="Character Coverage",
                score=cov_score,
                weight=self.weights.character_coverage,
                weighted_score=cov_score * self.weights.character_coverage / 100,
                issues=cov_issues,
            )

            # 4. Untranslated Text Detection
            unt_score, unt_issues = self.semantic_validator.detect_untranslated_text(
                orig_ocr.text, trans_ocr.text, source_lang, target_lang
            )

            # 5. Partial Translation
            part_score, part_issues = self.semantic_validator.detect_partial_translation(
                orig_ocr.text, trans_ocr.text
            )

            # 6. Blur Detection
            blur_score, blur_issues = self.visual_validator.detect_blur(translated_path)
            params["blur_detection"] = ParameterScore(
                name="Blur Detection",
                score=blur_score,
                weight=self.weights.blur_detection,
                weighted_score=blur_score * self.weights.blur_detection / 100,
                issues=blur_issues,
            )

            # 7. Artifact Detection
            art_score, art_issues = self.visual_validator.detect_artifacts(
                original_path, translated_path
            )
            params["artifact_detection"] = ParameterScore(
                name="Artifact Detection",
                score=art_score,
                weight=self.weights.artifact_detection,
                weighted_score=art_score * self.weights.artifact_detection / 100,
                issues=art_issues,
            )

            # 8. Overflow Detection
            overflow_score, overflow_issues = self.visual_validator.detect_overflow(
                translated_path, trans_ocr.bounding_boxes
            )
            params["overflow_detection"] = ParameterScore(
                name="Overflow Detection",
                score=overflow_score,
                weight=self.weights.overflow_detection,
                weighted_score=overflow_score * self.weights.overflow_detection / 100,
                issues=overflow_issues,
            )

            # 9. Cropping/Truncation
            crop_score, crop_issues = self.visual_validator.detect_cropping(
                original_path, translated_path
            )

            # 10. Background Preservation
            bg_score, bg_issues = self.visual_validator.check_background_preservation(
                original_path, translated_path
            )
            params["background_preservation"] = ParameterScore(
                name="Background Preservation",
                score=bg_score,
                weight=self.weights.background_preservation,
                weighted_score=bg_score * self.weights.background_preservation / 100,
                issues=bg_issues,
            )

            # 11. Layout Similarity
            import cv2 as _cv2
            import numpy as _np

            def _img_shape(p):
                img = _cv2.imread(p)
                return img.shape[:2] if img is not None else (0, 0)

            orig_shape = _img_shape(original_path)
            trans_shape = _img_shape(translated_path)

            layout_score, layout_issues = self.visual_validator.compare_layout(
                orig_ocr.bounding_boxes,
                trans_ocr.bounding_boxes,
                orig_shape,
                trans_shape,
            )
            params["layout_similarity"] = ParameterScore(
                name="Layout Similarity",
                score=layout_score,
                weight=self.weights.layout_similarity,
                weighted_score=layout_score * self.weights.layout_similarity / 100,
                issues=layout_issues,
            )

            # 12. Font Consistency
            font_score, font_issues = self.visual_validator.estimate_font_size_diff(
                orig_ocr.bounding_boxes, trans_ocr.bounding_boxes
            )
            params["font_consistency"] = ParameterScore(
                name="Font Consistency",
                score=font_score,
                weight=self.weights.font_consistency,
                weighted_score=font_score * self.weights.font_consistency / 100,
                issues=font_issues,
            )

            # Collect all issues
            all_issues = []
            for p in params.values():
                all_issues.extend(p.issues)
            all_issues.extend(unt_issues + part_issues + crop_issues)

            # Compute weighted total
            total_weight = sum(p.weight for p in params.values())
            weighted_sum = sum(p.weighted_score for p in params.values())
            overall = (weighted_sum / total_weight * 100) if total_weight > 0 else 0

            result.parameter_scores = params
            result.overall_score = round(max(0.0, min(100.0, overall)), 2)
            result.score_band = result.get_score_band().value
            result.issues = all_issues

        except Exception as e:
            logger.error(f"Scoring failed for {image_name}/{engine_name}: {e}")
            result.error = str(e)
            result.overall_score = 0.0
            result.score_band = ScoreBand.NEEDS_REVIEW.value

        result.processing_time = time.time() - start
        return result

    @staticmethod
    def get_score_band(score: float) -> str:
        if score >= 95:
            return ScoreBand.EXCELLENT.value
        elif score >= 85:
            return ScoreBand.GOOD.value
        elif score >= 70:
            return ScoreBand.ACCEPTABLE.value
        return ScoreBand.NEEDS_REVIEW.value

    @staticmethod
    def get_band_color(band: str) -> str:
        colors = {
            ScoreBand.EXCELLENT.value: "#22c55e",
            ScoreBand.GOOD.value: "#3b82f6",
            ScoreBand.ACCEPTABLE.value: "#f59e0b",
            ScoreBand.NEEDS_REVIEW.value: "#ef4444",
        }
        return colors.get(band, "#6b7280")
