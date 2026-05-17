"""
Analyzers package for Document Scanner Benchmark Tool.
"""

from .finger_removal import FingerRemovalAnalyzer
from .dog_ear_removal import DogEarRemovalAnalyzer
from .warp_correction import WarpCorrectionAnalyzer
from .ocr_accuracy import OCRAccuracyAnalyzer
from .report_generator import ReportGenerator

__all__ = [
    "FingerRemovalAnalyzer",
    "DogEarRemovalAnalyzer",
    "WarpCorrectionAnalyzer",
    "OCRAccuracyAnalyzer",
    "ReportGenerator",
]
