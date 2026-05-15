"""Semantic similarity validator using SentenceTransformers."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class SemanticValidator:
    """Computes semantic similarity between original and translated text."""

    MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
    _model = None

    def __init__(self):
        self._model_loaded = False

    def _get_model(self):
        if SemanticValidator._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading SentenceTransformer: {self.MODEL_NAME}")
                SemanticValidator._model = SentenceTransformer(self.MODEL_NAME)
                self._model_loaded = True
                logger.info("SentenceTransformer loaded successfully")
            except ImportError:
                logger.warning("sentence-transformers not available")
                SemanticValidator._model = "unavailable"
            except Exception as e:
                logger.error(f"Failed to load SentenceTransformer: {e}")
                SemanticValidator._model = "unavailable"
        return SemanticValidator._model

    def compute_similarity(
        self, text1: str, text2: str
    ) -> Tuple[float, List[str]]:
        """
        Compute cosine similarity between two texts.
        Returns (score 0-100, issues).
        """
        issues = []

        if not text1 or not text2:
            if not text1 and not text2:
                return 50.0, ["No text available from either image"]
            issues.append("One of the images produced no text for comparison")
            return 20.0, issues

        model = self._get_model()
        if model == "unavailable" or model is None:
            return self._heuristic_similarity(text1, text2)

        try:
            embeddings = model.encode([text1, text2], normalize_embeddings=True)
            similarity = float(np.dot(embeddings[0], embeddings[1]))
            score = max(0.0, min(100.0, similarity * 100))

            if score < 30:
                issues.append("Very low semantic similarity — possible mistranslation")
            elif score < 50:
                issues.append("Low semantic similarity detected")

            return round(score, 2), issues

        except Exception as e:
            logger.error(f"Semantic similarity computation failed: {e}")
            return self._heuristic_similarity(text1, text2)

    def _heuristic_similarity(
        self, text1: str, text2: str
    ) -> Tuple[float, List[str]]:
        """Fallback heuristic when model is unavailable."""
        issues = ["Semantic model unavailable, using heuristic similarity"]

        len1, len2 = len(text1), len(text2)
        if max(len1, len2) == 0:
            return 50.0, issues

        length_ratio = min(len1, len2) / max(len1, len2)
        words1 = set(re.findall(r"\w+", text1.lower()))
        words2 = set(re.findall(r"\w+", text2.lower()))

        if words1 and words2:
            overlap = len(words1 & words2) / len(words1 | words2)
        else:
            overlap = 0.0

        score = (length_ratio * 40 + overlap * 60)
        return round(score, 2), issues

    def detect_untranslated_text(
        self,
        source_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
    ) -> Tuple[float, List[str]]:
        """
        Detect if source-language text appears in the translated image.
        Returns (score 0-100, issues).
        """
        issues = []
        if not source_text or not translated_text:
            return 85.0, issues

        source_words = set(re.findall(r"\w{3,}", source_text.lower()))
        trans_words = set(re.findall(r"\w{3,}", translated_text.lower()))

        if not source_words:
            return 90.0, issues

        common = source_words & trans_words
        untranslated_ratio = len(common) / len(source_words)

        if untranslated_ratio > 0.5:
            issues.append(
                f"High untranslated text ratio: {untranslated_ratio:.0%} of source words found in translation"
            )
            score = max(0.0, 100 - untranslated_ratio * 100)
        elif untranslated_ratio > 0.3:
            issues.append(
                f"Partial untranslated text detected: {untranslated_ratio:.0%}"
            )
            score = max(50.0, 100 - untranslated_ratio * 80)
        else:
            score = 100.0 - untranslated_ratio * 40

        return round(score, 2), issues

    def detect_partial_translation(
        self, source_text: str, translated_text: str
    ) -> Tuple[float, List[str]]:
        """Detect partial translation (coverage below threshold)."""
        issues = []
        if not source_text:
            return 85.0, issues
        if not translated_text:
            issues.append("No translated text detected")
            return 0.0, issues

        coverage = min(1.0, len(translated_text) / max(len(source_text), 1))

        if coverage < 0.3:
            issues.append(f"Very low translation coverage: {coverage:.0%}")
            return round(coverage * 100, 2), issues
        elif coverage < 0.6:
            issues.append(f"Partial translation detected: {coverage:.0%} coverage")

        score = min(100.0, coverage * 100)
        return round(score, 2), issues

    def compute_character_coverage(
        self, source_text: str, translated_text: str
    ) -> Tuple[float, List[str]]:
        """Check character/script coverage."""
        issues = []
        if not source_text:
            return 90.0, issues
        if not translated_text:
            issues.append("No translated text for coverage check")
            return 0.0, issues

        src_chars = len(source_text.replace(" ", ""))
        tgt_chars = len(translated_text.replace(" ", ""))

        if src_chars == 0:
            return 90.0, issues

        ratio = tgt_chars / src_chars
        if ratio < 0.2:
            issues.append("Very few characters in translation")
            score = 10.0
        elif ratio < 0.5:
            issues.append("Low character count in translation")
            score = ratio * 100
        elif ratio > 3.0:
            issues.append("Unusually many characters in translation")
            score = 70.0
        else:
            score = min(100.0, 100 - abs(1 - ratio) * 20)

        return round(score, 2), issues
