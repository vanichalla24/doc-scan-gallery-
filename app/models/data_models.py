"""Data models for TransLingo QA Studio."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ScoreBand(Enum):
    EXCELLENT = "Excellent"
    GOOD = "Good"
    ACCEPTABLE = "Acceptable"
    NEEDS_REVIEW = "Needs Review"


class ValidationStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ScoringWeights:
    semantic_similarity: float = 25.0
    ocr_accuracy: float = 15.0
    character_coverage: float = 10.0
    layout_similarity: float = 10.0
    font_consistency: float = 10.0
    artifact_detection: float = 10.0
    blur_detection: float = 5.0
    overflow_detection: float = 5.0
    background_preservation: float = 10.0

    def as_dict(self) -> Dict[str, float]:
        return {
            "semantic_similarity": self.semantic_similarity,
            "ocr_accuracy": self.ocr_accuracy,
            "character_coverage": self.character_coverage,
            "layout_similarity": self.layout_similarity,
            "font_consistency": self.font_consistency,
            "artifact_detection": self.artifact_detection,
            "blur_detection": self.blur_detection,
            "overflow_detection": self.overflow_detection,
            "background_preservation": self.background_preservation,
        }

    def total(self) -> float:
        return sum(self.as_dict().values())

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> ScoringWeights:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ParameterScore:
    name: str
    score: float          # 0–100
    weight: float
    weighted_score: float
    details: str = ""
    issues: List[str] = field(default_factory=list)


@dataclass
class OCRResult:
    text: str
    confidence: float
    bounding_boxes: List[Dict[str, Any]] = field(default_factory=list)
    language_detected: str = ""


@dataclass
class ImageValidationResult:
    image_name: str
    engine: str
    original_path: str
    translated_path: str
    overall_score: float = 0.0
    score_band: str = ScoreBand.NEEDS_REVIEW.value
    parameter_scores: Dict[str, ParameterScore] = field(default_factory=dict)
    original_ocr: Optional[OCRResult] = None
    translated_ocr: Optional[OCRResult] = None
    issues: List[str] = field(default_factory=list)
    processing_time: float = 0.0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def get_score_band(self) -> ScoreBand:
        if self.overall_score >= 95:
            return ScoreBand.EXCELLENT
        elif self.overall_score >= 85:
            return ScoreBand.GOOD
        elif self.overall_score >= 70:
            return ScoreBand.ACCEPTABLE
        return ScoreBand.NEEDS_REVIEW


@dataclass
class EngineResult:
    engine_name: str
    image_results: List[ImageValidationResult] = field(default_factory=list)
    average_score: float = 0.0
    pass_rate: float = 0.0
    total_images: int = 0
    processed_images: int = 0

    def compute_stats(self) -> None:
        valid = [r for r in self.image_results if r.error is None]
        if not valid:
            return
        self.total_images = len(self.image_results)
        self.processed_images = len(valid)
        self.average_score = sum(r.overall_score for r in valid) / len(valid)
        passed = sum(1 for r in valid if r.overall_score >= 70)
        self.pass_rate = (passed / len(valid)) * 100


@dataclass
class ValidationRun:
    run_id: str
    root_folder: str
    source_language: str
    target_language: str
    engines: List[str]
    status: ValidationStatus = ValidationStatus.PENDING
    engine_results: Dict[str, EngineResult] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_images: int = 0
    processed_images: int = 0
    scoring_weights: ScoringWeights = field(default_factory=ScoringWeights)

    def get_overall_stats(self) -> Dict[str, Any]:
        all_results = []
        for er in self.engine_results.values():
            all_results.extend(er.image_results)
        valid = [r for r in all_results if r.error is None]
        if not valid:
            return {}
        avg = sum(r.overall_score for r in valid) / len(valid)
        passed = sum(1 for r in valid if r.overall_score >= 70)
        return {
            "total": len(all_results),
            "processed": len(valid),
            "average_score": avg,
            "pass_rate": (passed / len(valid)) * 100 if valid else 0,
            "engine_averages": {
                name: er.average_score for name, er in self.engine_results.items()
            },
        }


@dataclass
class AppSettings:
    theme: str = "dark"
    scoring_weights: ScoringWeights = field(default_factory=ScoringWeights)
    ocr_confidence_threshold: float = 0.6
    parallel_workers: int = 4
    ocr_language: str = "en"
    enable_back_translation: bool = False
    google_translate_api_key: str = ""
    default_source_language: str = "English"
    default_target_language: str = "Korean"
    last_root_folder: str = ""
    auto_save_results: bool = True
    thumbnail_size: int = 200
