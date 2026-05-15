"""Unit tests for the scoring and validation logic."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import numpy  # noqa: F401
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from app.models.data_models import ScoringWeights, ScoreBand, AppSettings


class TestScoringWeights(unittest.TestCase):
    def test_default_weights(self):
        w = ScoringWeights()
        self.assertAlmostEqual(w.total(), 100.0, places=1)

    def test_as_dict_roundtrip(self):
        w = ScoringWeights()
        d = w.as_dict()
        w2 = ScoringWeights.from_dict(d)
        self.assertEqual(w.semantic_similarity, w2.semantic_similarity)
        self.assertEqual(w.ocr_accuracy, w2.ocr_accuracy)

    def test_custom_weights(self):
        w = ScoringWeights(semantic_similarity=50, ocr_accuracy=50,
                           character_coverage=0, layout_similarity=0,
                           font_consistency=0, artifact_detection=0,
                           blur_detection=0, overflow_detection=0,
                           background_preservation=0)
        self.assertAlmostEqual(w.total(), 100.0, places=1)


@unittest.skipUnless(HAS_NUMPY, "numpy not installed")
class TestScoreBand(unittest.TestCase):
    def test_excellent_band(self):
        from app.core.scoring_engine import ScoringEngine
        band = ScoringEngine.get_score_band(97)
        self.assertEqual(band, ScoreBand.EXCELLENT.value)

    def test_good_band(self):
        from app.core.scoring_engine import ScoringEngine
        band = ScoringEngine.get_score_band(88)
        self.assertEqual(band, ScoreBand.GOOD.value)

    def test_acceptable_band(self):
        from app.core.scoring_engine import ScoringEngine
        band = ScoringEngine.get_score_band(75)
        self.assertEqual(band, ScoreBand.ACCEPTABLE.value)

    def test_needs_review_band(self):
        from app.core.scoring_engine import ScoringEngine
        band = ScoringEngine.get_score_band(50)
        self.assertEqual(band, ScoreBand.NEEDS_REVIEW.value)

    def test_boundary_values(self):
        from app.core.scoring_engine import ScoringEngine
        self.assertEqual(ScoringEngine.get_score_band(95), ScoreBand.EXCELLENT.value)
        self.assertEqual(ScoringEngine.get_score_band(94.9), ScoreBand.GOOD.value)
        self.assertEqual(ScoringEngine.get_score_band(85), ScoreBand.GOOD.value)
        self.assertEqual(ScoringEngine.get_score_band(70), ScoreBand.ACCEPTABLE.value)
        self.assertEqual(ScoringEngine.get_score_band(69.9), ScoreBand.NEEDS_REVIEW.value)


@unittest.skipUnless(HAS_NUMPY, "numpy not installed")
class TestSemanticValidator(unittest.TestCase):
    def setUp(self):
        from app.core.semantic_validator import SemanticValidator
        self.validator = SemanticValidator()

    def test_empty_texts(self):
        score, issues = self.validator.compute_similarity("", "")
        self.assertEqual(score, 50.0)
        self.assertGreater(len(issues), 0)

    def test_one_empty(self):
        score, issues = self.validator.compute_similarity("Hello world", "")
        self.assertLess(score, 50.0)
        self.assertGreater(len(issues), 0)

    def test_identical_texts(self):
        text = "The quick brown fox"
        score, _ = self.validator._heuristic_similarity(text, text)
        self.assertGreater(score, 70.0)

    def test_detect_untranslated(self):
        score, issues = self.validator.detect_untranslated_text(
            "hello world", "hello world", "English", "Korean"
        )
        self.assertLess(score, 70.0)

    def test_partial_translation(self):
        score, issues = self.validator.detect_partial_translation(
            "A " * 100, "A"
        )
        self.assertLess(score, 30.0)
        self.assertGreater(len(issues), 0)

    def test_character_coverage(self):
        score, issues = self.validator.compute_character_coverage(
            "Hello World Test", "Hello World Test"
        )
        self.assertGreater(score, 80.0)


class TestAppSettings(unittest.TestCase):
    def test_defaults(self):
        s = AppSettings()
        self.assertEqual(s.theme, "dark")
        self.assertEqual(s.parallel_workers, 4)
        self.assertAlmostEqual(s.ocr_confidence_threshold, 0.6)

    def test_scoring_weights_instance(self):
        s = AppSettings()
        self.assertIsInstance(s.scoring_weights, ScoringWeights)


if __name__ == "__main__":
    unittest.main(verbosity=2)
