"""Benchmark engine: orchestrates multi-engine, multi-image validation."""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from app.core.ocr_engine import OCREngine, LANGUAGE_MAP
from app.core.scoring_engine import ScoringEngine
from app.database import db_manager
from app.models.data_models import (
    AppSettings,
    EngineResult,
    ImageValidationResult,
    ScoringWeights,
    ValidationRun,
    ValidationStatus,
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}


def find_images(folder: Path) -> List[str]:
    """Return sorted image filenames in a folder (relative names only)."""
    if not folder.exists():
        return []
    return sorted(
        f.name for f in folder.iterdir()
        if f.suffix.lower() in IMAGE_EXTENSIONS
    )


class BenchmarkEngine:
    """
    Runs the full validation pipeline across multiple engines and images.
    Emits progress callbacks and saves results to the database.
    """

    def __init__(
        self,
        settings: AppSettings = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        result_callback: Optional[Callable[[ImageValidationResult], None]] = None,
    ):
        self.settings = settings or AppSettings()
        self.progress_callback = progress_callback
        self.result_callback = result_callback

    def _emit_progress(self, done: int, total: int, msg: str) -> None:
        if self.progress_callback:
            try:
                self.progress_callback(done, total, msg)
            except Exception:
                pass

    def discover_engines(self, root_folder: Path) -> List[str]:
        """Return engine folder names (exclude 'Original')."""
        engines = []
        for item in sorted(root_folder.iterdir()):
            if item.is_dir() and item.name.lower() != "original":
                engines.append(item.name)
        return engines

    def run(
        self,
        root_folder: str,
        source_language: str,
        target_language: str,
        selected_engines: Optional[List[str]] = None,
        weights: Optional[ScoringWeights] = None,
    ) -> ValidationRun:
        """Execute full benchmark run. Returns completed ValidationRun."""
        root = Path(root_folder)
        if not root.exists():
            raise FileNotFoundError(f"Root folder not found: {root_folder}")

        original_folder = root / "Original"
        if not original_folder.exists():
            raise FileNotFoundError("'Original' subfolder not found in root")

        original_images = find_images(original_folder)
        if not original_images:
            raise ValueError("No images found in 'Original' folder")

        engines = selected_engines or self.discover_engines(root)
        if not engines:
            raise ValueError("No engine folders found (expected Google, Papago, etc.)")

        run_id = str(uuid.uuid4())
        run = ValidationRun(
            run_id=run_id,
            root_folder=root_folder,
            source_language=source_language,
            target_language=target_language,
            engines=engines,
            status=ValidationStatus.RUNNING,
            scoring_weights=weights or self.settings.scoring_weights,
        )
        run.total_images = len(original_images) * len(engines)

        db_manager.save_run({
            "run_id": run_id,
            "root_folder": root_folder,
            "source_language": source_language,
            "target_language": target_language,
            "engines": engines,
            "status": ValidationStatus.RUNNING.value,
            "scoring_weights": run.scoring_weights.as_dict(),
            "start_time": run.start_time.isoformat(),
            "total_images": run.total_images,
        })

        ocr_lang = OCREngine.get_lang_code(target_language)
        scoring_engine = ScoringEngine(weights=run.scoring_weights)

        processed = 0
        total = run.total_images

        for engine_name in engines:
            engine_folder = root / engine_name
            engine_result = EngineResult(engine_name=engine_name)

            jobs = []
            for img_name in original_images:
                orig_path = str(original_folder / img_name)
                trans_path = str(engine_folder / img_name)
                if not Path(trans_path).exists():
                    logger.warning(f"Missing translated image: {trans_path}")
                jobs.append((img_name, orig_path, trans_path))

            with ThreadPoolExecutor(max_workers=self.settings.parallel_workers) as pool:
                futures = {
                    pool.submit(
                        scoring_engine.validate_image_pair,
                        orig_path, trans_path, img_name, engine_name,
                        source_language, target_language, ocr_lang,
                    ): img_name
                    for img_name, orig_path, trans_path in jobs
                }

                for future in as_completed(futures):
                    img_name = futures[future]
                    try:
                        result: ImageValidationResult = future.result()
                    except Exception as e:
                        logger.error(f"Job failed for {img_name}/{engine_name}: {e}")
                        result = ImageValidationResult(
                            image_name=img_name,
                            engine=engine_name,
                            original_path="",
                            translated_path="",
                            error=str(e),
                        )

                    engine_result.image_results.append(result)
                    processed += 1

                    db_manager.save_image_result({
                        "run_id": run_id,
                        "engine": engine_name,
                        "image_name": result.image_name,
                        "original_path": result.original_path,
                        "translated_path": result.translated_path,
                        "overall_score": result.overall_score,
                        "score_band": result.score_band,
                        "parameter_scores": {
                            k: {
                                "score": v.score,
                                "weight": v.weight,
                                "weighted_score": v.weighted_score,
                                "issues": v.issues,
                            }
                            for k, v in result.parameter_scores.items()
                        },
                        "issues": result.issues,
                        "original_ocr_text": result.original_ocr.text if result.original_ocr else "",
                        "translated_ocr_text": result.translated_ocr.text if result.translated_ocr else "",
                        "processing_time": result.processing_time,
                        "error": result.error,
                    })

                    if self.result_callback:
                        try:
                            self.result_callback(result)
                        except Exception:
                            pass

                    self._emit_progress(
                        processed, total,
                        f"[{engine_name}] {img_name} — Score: {result.overall_score:.1f}"
                    )

            engine_result.compute_stats()
            run.engine_results[engine_name] = engine_result

            db_manager.save_engine_summary({
                "run_id": run_id,
                "engine": engine_name,
                "average_score": engine_result.average_score,
                "pass_rate": engine_result.pass_rate,
                "total_images": engine_result.total_images,
                "processed_images": engine_result.processed_images,
            })

        run.status = ValidationStatus.COMPLETED
        run.end_time = datetime.now()
        run.processed_images = processed

        stats = run.get_overall_stats()
        db_manager.save_run({
            "run_id": run_id,
            "root_folder": root_folder,
            "source_language": source_language,
            "target_language": target_language,
            "engines": engines,
            "status": ValidationStatus.COMPLETED.value,
            "scoring_weights": run.scoring_weights.as_dict(),
            "start_time": run.start_time.isoformat(),
            "end_time": run.end_time.isoformat(),
            "total_images": run.total_images,
            "processed_images": processed,
            "average_score": stats.get("average_score", 0),
            "pass_rate": stats.get("pass_rate", 0),
        })

        self._emit_progress(total, total, "Validation complete!")
        logger.info(f"Run {run_id} completed: {processed}/{total} images")
        return run
