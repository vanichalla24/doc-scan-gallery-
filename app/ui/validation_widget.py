"""Run Validation page — folder selection, engine choice, progress, live results."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from app.core.benchmark_engine import BenchmarkEngine, find_images
from app.database import db_manager
from app.models.data_models import AppSettings, ImageValidationResult, ScoringWeights, ValidationRun


LANGUAGES = [
    "English", "Korean", "Hindi", "Chinese", "Japanese", "French",
    "German", "Spanish", "Arabic", "Russian", "Portuguese", "Italian",
    "Dutch", "Thai", "Vietnamese",
]

DEFAULT_ENGINES = ["Google", "Papago", "Samsung", "Microsoft"]


class ValidationWorker(QThread):
    progress = Signal(int, int, str)
    result_ready = Signal(object)
    run_complete = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        root_folder: str,
        source_lang: str,
        target_lang: str,
        engines: List[str],
        settings: AppSettings,
    ):
        super().__init__()
        self.root_folder = root_folder
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.engines = engines
        self.settings = settings

    def run(self) -> None:
        try:
            engine = BenchmarkEngine(
                settings=self.settings,
                progress_callback=lambda d, t, m: self.progress.emit(d, t, m),
                result_callback=lambda r: self.result_ready.emit(r),
            )
            run = engine.run(
                root_folder=self.root_folder,
                source_language=self.source_lang,
                target_language=self.target_lang,
                selected_engines=self.engines if self.engines else None,
                weights=self.settings.scoring_weights,
            )
            self.run_complete.emit(run)
        except Exception as e:
            self.error.emit(str(e))


class ValidationWidget(QWidget):
    run_completed = Signal(object)

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._worker: Optional[ValidationWorker] = None
        self._detected_engines: List[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Run Validation")
        title.setObjectName("page_title")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left panel — controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(12)
        splitter.addWidget(left_panel)

        # Folder selection
        folder_group = QGroupBox("Input Folder")
        folder_group.setStyleSheet("QGroupBox { font-weight: 600; color: #cbd5e1; }")
        folder_layout = QVBoxLayout(folder_group)
        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("Select root folder containing Original/, Google/, Papago/ …")
        self._folder_edit.setText(self.settings.last_root_folder)
        self._folder_edit.textChanged.connect(self._on_folder_changed)
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("secondary_btn")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self._folder_edit)
        folder_row.addWidget(browse_btn)
        folder_layout.addLayout(folder_row)

        self._folder_info = QLabel("")
        self._folder_info.setStyleSheet("color: #64748b; font-size: 11px;")
        folder_layout.addWidget(self._folder_info)
        left_layout.addWidget(folder_group)

        # Language selection
        lang_group = QGroupBox("Language Pair")
        lang_group.setStyleSheet("QGroupBox { font-weight: 600; color: #cbd5e1; }")
        lang_form = QFormLayout(lang_group)
        self._src_combo = QComboBox()
        self._src_combo.addItems(LANGUAGES)
        self._src_combo.setCurrentText(self.settings.default_source_language)
        self._tgt_combo = QComboBox()
        self._tgt_combo.addItems(LANGUAGES)
        self._tgt_combo.setCurrentText(self.settings.default_target_language)
        lang_form.addRow("Source Language:", self._src_combo)
        lang_form.addRow("Target Language:", self._tgt_combo)
        left_layout.addWidget(lang_group)

        # Engine selection
        engine_group = QGroupBox("Translation Engines")
        engine_group.setStyleSheet("QGroupBox { font-weight: 600; color: #cbd5e1; }")
        engine_layout = QVBoxLayout(engine_group)

        engine_hint = QLabel("Detected engines will appear automatically when you select a folder.")
        engine_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        engine_hint.setWordWrap(True)
        engine_layout.addWidget(engine_hint)

        self._engine_list = QListWidget()
        self._engine_list.setMaximumHeight(130)
        engine_layout.addWidget(self._engine_list)

        engine_btn_row = QHBoxLayout()
        sel_all = QPushButton("Select All")
        sel_all.setObjectName("secondary_btn")
        sel_all.clicked.connect(self._select_all_engines)
        desel_all = QPushButton("Deselect All")
        desel_all.setObjectName("secondary_btn")
        desel_all.clicked.connect(self._deselect_all_engines)
        engine_btn_row.addWidget(sel_all)
        engine_btn_row.addWidget(desel_all)
        engine_btn_row.addStretch()
        engine_layout.addLayout(engine_btn_row)
        left_layout.addWidget(engine_group)

        # Start / Stop buttons
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("▶  Start Validation")
        self._start_btn.setObjectName("success_btn")
        self._start_btn.setFixedHeight(40)
        self._start_btn.clicked.connect(self._start_validation)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("danger_btn")
        self._stop_btn.setFixedHeight(40)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_validation)

        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        left_layout.addLayout(btn_row)

        # Progress
        progress_group = QGroupBox("Progress")
        progress_group.setStyleSheet("QGroupBox { font-weight: 600; color: #cbd5e1; }")
        progress_layout = QVBoxLayout(progress_group)
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        progress_layout.addWidget(self._progress_bar)
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        progress_layout.addWidget(self._status_label)
        left_layout.addWidget(progress_group)
        left_layout.addStretch()

        # Right panel — live log
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)
        splitter.addWidget(right_panel)

        log_label = QLabel("Live Output")
        log_label.setObjectName("section_title")
        right_layout.addWidget(log_label)

        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setStyleSheet(
            "background-color: #0a1628; color: #22c55e; font-family: monospace; font-size: 12px;"
        )
        right_layout.addWidget(self._log_text)

        clear_btn = QPushButton("Clear Log")
        clear_btn.setObjectName("secondary_btn")
        clear_btn.setFixedWidth(100)
        clear_btn.clicked.connect(self._log_text.clear)
        right_layout.addWidget(clear_btn, alignment=Qt.AlignRight)

        splitter.setSizes([420, 560])

        if self.settings.last_root_folder:
            self._on_folder_changed(self.settings.last_root_folder)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Root Folder")
        if folder:
            self._folder_edit.setText(folder)

    def _on_folder_changed(self, path: str) -> None:
        root = Path(path)
        if not root.exists():
            self._folder_info.setText("Folder not found.")
            self._engine_list.clear()
            return

        orig = root / "Original"
        if orig.exists():
            imgs = find_images(orig)
            self._folder_info.setText(f"Found {len(imgs)} images in Original/")
        else:
            self._folder_info.setText("'Original/' subfolder not found")

        self._engine_list.clear()
        self._detected_engines = []
        if root.exists():
            for item in sorted(root.iterdir()):
                if item.is_dir() and item.name.lower() != "original":
                    self._detected_engines.append(item.name)
                    list_item = QListWidgetItem(item.name)
                    list_item.setCheckState(Qt.Checked)
                    self._engine_list.addItem(list_item)

    def _select_all_engines(self) -> None:
        for i in range(self._engine_list.count()):
            self._engine_list.item(i).setCheckState(Qt.Checked)

    def _deselect_all_engines(self) -> None:
        for i in range(self._engine_list.count()):
            self._engine_list.item(i).setCheckState(Qt.Unchecked)

    def _get_selected_engines(self) -> List[str]:
        selected = []
        for i in range(self._engine_list.count()):
            item = self._engine_list.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected

    def _start_validation(self) -> None:
        root_folder = self._folder_edit.text().strip()
        if not root_folder or not Path(root_folder).exists():
            self._log("ERROR: Invalid root folder path.", "red")
            return

        engines = self._get_selected_engines()
        if not engines:
            self._log("ERROR: No engines selected.", "red")
            return

        self.settings.last_root_folder = root_folder
        db_manager.save_setting("last_root_folder", root_folder)

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._progress_bar.setValue(0)
        self._log_text.clear()
        self._log(f"Starting validation: {root_folder}", "#3b82f6")
        self._log(f"Engines: {', '.join(engines)}", "#94a3b8")
        self._log(f"Language: {self._src_combo.currentText()} → {self._tgt_combo.currentText()}", "#94a3b8")

        self._worker = ValidationWorker(
            root_folder=root_folder,
            source_lang=self._src_combo.currentText(),
            target_lang=self._tgt_combo.currentText(),
            engines=engines,
            settings=self.settings,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_result_ready)
        self._worker.run_complete.connect(self._on_run_complete)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _stop_validation(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._log("Validation stopped by user.", "#f59e0b")
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def _on_progress(self, done: int, total: int, msg: str) -> None:
        pct = int((done / total * 100)) if total > 0 else 0
        self._progress_bar.setValue(pct)
        self._status_label.setText(f"{done}/{total}  {msg}")
        self._log(f"[{done}/{total}] {msg}")

    def _on_result_ready(self, result: ImageValidationResult) -> None:
        color = "#22c55e" if result.overall_score >= 70 else "#ef4444"
        self._log(
            f"✓ {result.engine}/{result.image_name}  Score: {result.overall_score:.1f}  [{result.score_band}]",
            color
        )

    def _on_run_complete(self, run: ValidationRun) -> None:
        stats = run.get_overall_stats()
        self._log("", "")
        self._log("=" * 50, "#475569")
        self._log(f"Validation complete!", "#22c55e")
        self._log(f"Total images: {stats.get('total', 0)}", "#94a3b8")
        self._log(f"Average score: {stats.get('average_score', 0):.2f}", "#94a3b8")
        self._log(f"Pass rate: {stats.get('pass_rate', 0):.1f}%", "#94a3b8")
        self._progress_bar.setValue(100)
        self._status_label.setText("Complete")
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self.run_completed.emit(run)

    def _on_error(self, msg: str) -> None:
        self._log(f"ERROR: {msg}", "#ef4444")
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("Failed")

    def _log(self, text: str, color: str = "#e2e8f0") -> None:
        if color:
            self._log_text.append(f'<span style="color:{color};">{text}</span>')
        else:
            self._log_text.append("")
        sb = self._log_text.verticalScrollBar()
        sb.setValue(sb.maximum())
