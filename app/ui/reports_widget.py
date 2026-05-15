"""Reports page — generate PPTX, Excel, CSV, HTML from completed runs."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from app.database import db_manager
from app.models.data_models import ValidationRun, EngineResult, ScoringWeights, ImageValidationResult
from app.models.data_models import ParameterScore, OCRResult


def _reconstruct_run(run_id: str) -> Optional[ValidationRun]:
    """Reconstruct a ValidationRun from database records."""
    import json
    from datetime import datetime
    from app.models.data_models import ValidationStatus

    run_row = db_manager.get_run(run_id)
    if not run_row:
        return None

    weights_dict = json.loads(run_row.get("scoring_weights") or "{}")
    weights = ScoringWeights.from_dict(weights_dict) if weights_dict else ScoringWeights()

    run = ValidationRun(
        run_id=run_id,
        root_folder=run_row["root_folder"],
        source_language=run_row["source_language"],
        target_language=run_row["target_language"],
        engines=json.loads(run_row.get("engines") or "[]"),
        status=ValidationStatus.COMPLETED,
        scoring_weights=weights,
        start_time=datetime.fromisoformat(run_row.get("start_time") or datetime.now().isoformat()),
        total_images=run_row.get("total_images", 0),
        processed_images=run_row.get("processed_images", 0),
    )

    image_rows = db_manager.get_image_results(run_id)
    engines_seen: dict[str, EngineResult] = {}

    for row in image_rows:
        engine = row["engine"]
        if engine not in engines_seen:
            engines_seen[engine] = EngineResult(engine_name=engine)

        param_scores = {}
        for k, v in row.get("parameter_scores", {}).items():
            if isinstance(v, dict):
                param_scores[k] = ParameterScore(
                    name=k.replace("_", " ").title(),
                    score=v.get("score", 0),
                    weight=v.get("weight", 0),
                    weighted_score=v.get("weighted_score", 0),
                    issues=v.get("issues", []),
                )

        img_result = ImageValidationResult(
            image_name=row["image_name"],
            engine=engine,
            original_path=row.get("original_path", ""),
            translated_path=row.get("translated_path", ""),
            overall_score=row.get("overall_score", 0.0),
            score_band=row.get("score_band", ""),
            parameter_scores=param_scores,
            issues=row.get("issues", []),
            original_ocr=OCRResult(text=row.get("original_ocr_text", ""), confidence=0),
            translated_ocr=OCRResult(text=row.get("translated_ocr_text", ""), confidence=0),
            processing_time=row.get("processing_time", 0),
            error=row.get("error"),
        )
        engines_seen[engine].image_results.append(img_result)

    for engine, er in engines_seen.items():
        er.compute_stats()
        run.engine_results[engine] = er

    return run


class ReportWorker(QThread):
    progress = Signal(str)
    done = Signal(str)
    error = Signal(str)

    def __init__(self, run_id: str, report_type: str, output_path: str):
        super().__init__()
        self.run_id = run_id
        self.report_type = report_type
        self.output_path = output_path

    def run(self) -> None:
        try:
            self.progress.emit(f"Reconstructing run data…")
            run = _reconstruct_run(self.run_id)
            if run is None:
                self.error.emit("Run not found in database")
                return

            from app.core.report_generator import ReportGenerator
            gen = ReportGenerator(run)

            self.progress.emit(f"Generating {self.report_type} report…")
            if self.report_type == "PPTX":
                gen.generate_pptx(self.output_path)
            elif self.report_type == "Excel":
                gen.generate_excel(self.output_path)
            elif self.report_type == "CSV":
                gen.generate_csv(self.output_path)
            elif self.report_type == "HTML":
                gen.generate_html(self.output_path)

            self.done.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))


class ReportsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[ReportWorker] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Reports")
        title.setObjectName("page_title")
        layout.addWidget(title)

        # Run selection
        run_group = QGroupBox("Select Run")
        run_group.setStyleSheet("QGroupBox { font-weight: 600; color: #cbd5e1; }")
        run_layout = QHBoxLayout(run_group)
        self._run_combo = QComboBox()
        self._run_combo.setMinimumWidth(320)
        run_layout.addWidget(QLabel("Run:"))
        run_layout.addWidget(self._run_combo)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondary_btn")
        refresh_btn.clicked.connect(self._load_runs)
        run_layout.addWidget(refresh_btn)
        run_layout.addStretch()
        layout.addWidget(run_group)

        # Export options
        export_group = QGroupBox("Export Options")
        export_group.setStyleSheet("QGroupBox { font-weight: 600; color: #cbd5e1; }")
        export_layout = QVBoxLayout(export_group)

        for fmt, ext, desc, color in [
            ("PPTX", ".pptx", "PowerPoint presentation with per-image slides and charts", "success_btn"),
            ("Excel", ".xlsx", "Detailed Excel workbook with parameter scores per image", "secondary_btn"),
            ("CSV", ".csv", "Raw data export for further analysis", "secondary_btn"),
            ("HTML", ".html", "Interactive HTML dashboard report", "secondary_btn"),
        ]:
            row = QHBoxLayout()
            btn = QPushButton(f"Export {fmt}")
            btn.setObjectName(color)
            btn.setFixedWidth(130)
            btn.clicked.connect(lambda checked, f=fmt, e=ext: self._export(f, e))
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
            row.addWidget(btn)
            row.addWidget(desc_lbl)
            row.addStretch()
            export_layout.addLayout(row)

        layout.addWidget(export_group)

        # Progress
        progress_group = QGroupBox("Progress")
        progress_group.setStyleSheet("QGroupBox { font-weight: 600; color: #cbd5e1; }")
        progress_layout = QVBoxLayout(progress_group)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.hide()
        progress_layout.addWidget(self._progress_bar)
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        progress_layout.addWidget(self._status_label)
        layout.addWidget(progress_group)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(160)
        self._log.setStyleSheet(
            "background-color: #0a1628; color: #94a3b8; font-family: monospace; font-size: 11px;"
        )
        layout.addWidget(self._log)
        layout.addStretch()

        self._load_runs()

    def _load_runs(self) -> None:
        runs = db_manager.list_runs(30)
        self._run_combo.clear()
        for run in runs:
            short = run["run_id"][:8]
            date = (run.get("start_time") or "")[:10]
            lang = f"{run.get('source_language','?')}→{run.get('target_language','?')}"
            avg = run.get("average_score", 0)
            label = f"{short} | {date} | {lang} | Score: {avg:.1f}"
            self._run_combo.addItem(label, run["run_id"])

    def _export(self, fmt: str, ext: str) -> None:
        run_id = self._run_combo.currentData()
        if not run_id:
            self._log.append('<span style="color:#ef4444;">No run selected.</span>')
            return

        short = run_id[:8]
        default_name = f"translingo_{short}_{fmt.lower()}{ext}"
        path, _ = QFileDialog.getSaveFileName(
            self, f"Save {fmt} Report", default_name,
            f"{fmt} Files (*{ext});;All Files (*.*)"
        )
        if not path:
            return

        self._status_label.setText(f"Generating {fmt}…")
        self._progress_bar.show()
        self._log.append(f'<span style="color:#3b82f6;">Exporting {fmt} to {path}…</span>')

        self._worker = ReportWorker(run_id, fmt, path)
        self._worker.progress.connect(lambda m: self._log.append(f'<span style="color:#94a3b8;">{m}</span>'))
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_done(self, path: str) -> None:
        self._progress_bar.hide()
        self._status_label.setText("Done")
        self._log.append(f'<span style="color:#22c55e;">✓ Report saved: {path}</span>')
        try:
            import subprocess
            import sys
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    def _on_error(self, msg: str) -> None:
        self._progress_bar.hide()
        self._status_label.setText("Failed")
        self._log.append(f'<span style="color:#ef4444;">ERROR: {msg}</span>')
