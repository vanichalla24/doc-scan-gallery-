"""Results page — per-image issue table, image viewer, charts."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.database import db_manager
from app.ui.image_viewer import ImageViewer
from app.core.scoring_engine import ScoringEngine


SCORE_COLORS = {
    "Excellent": "#22c55e",
    "Good": "#3b82f6",
    "Acceptable": "#f59e0b",
    "Needs Review": "#ef4444",
}


class ScoreBadge(QLabel):
    def __init__(self, band: str, score: float, parent=None):
        super().__init__(parent)
        color = SCORE_COLORS.get(band, "#6b7280")
        self.setText(f"{score:.1f}")
        self.setStyleSheet(
            f"background-color: {color}22; color: {color}; font-weight: 700; "
            f"border: 1px solid {color}; border-radius: 6px; padding: 2px 8px;"
        )
        self.setAlignment(Qt.AlignCenter)


class ParameterScoreBar(QWidget):
    """Small horizontal bar showing a parameter score."""

    def __init__(self, name: str, score: float, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel(name)
        label.setFixedWidth(170)
        label.setStyleSheet("font-size: 11px; color: #94a3b8;")
        layout.addWidget(label)

        bar = QProgressBar()
        bar.setMinimum(0)
        bar.setMaximum(100)
        bar.setValue(int(score))
        bar.setFixedHeight(8)
        bar.setTextVisible(False)
        color = "#22c55e" if score >= 85 else "#f59e0b" if score >= 70 else "#ef4444"
        bar.setStyleSheet(
            f"QProgressBar {{ background: #1e293b; border-radius: 4px; border: none; }}"
            f"QProgressBar::chunk {{ background: {color}; border-radius: 4px; }}"
        )
        layout.addWidget(bar)

        score_lbl = QLabel(f"{score:.0f}")
        score_lbl.setFixedWidth(32)
        score_lbl.setStyleSheet(f"font-size: 11px; color: {color}; font-weight: 600;")
        layout.addWidget(score_lbl)


class ResultsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_run_id: Optional[str] = None
        self._results: List[Dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(12)

        # Header row
        header = QHBoxLayout()
        title = QLabel("Results")
        title.setObjectName("page_title")
        header.addWidget(title)
        header.addStretch()

        self._run_combo = QComboBox()
        self._run_combo.setMinimumWidth(200)
        self._run_combo.currentIndexChanged.connect(self._load_selected_run)
        header.addWidget(QLabel("Run:"))
        header.addWidget(self._run_combo)

        self._engine_combo = QComboBox()
        self._engine_combo.setMinimumWidth(140)
        self._engine_combo.addItem("All Engines")
        self._engine_combo.currentTextChanged.connect(self._filter_results)
        header.addWidget(QLabel("Engine:"))
        header.addWidget(self._engine_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondary_btn")
        refresh_btn.clicked.connect(self.refresh_runs)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        # Main splitter: table | detail
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left: results table
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(left)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Image", "Engine", "Score", "Band", "Issues"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.currentRowChanged.connect(self._on_row_selected)
        left_layout.addWidget(self._table)

        summary_row = QHBoxLayout()
        self._summary_label = QLabel("No results loaded")
        self._summary_label.setStyleSheet("color: #64748b; font-size: 11px;")
        summary_row.addWidget(self._summary_label)
        summary_row.addStretch()
        left_layout.addLayout(summary_row)

        # Right: detail panel
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(12)
        splitter.addWidget(right)

        self._image_viewer = ImageViewer()
        self._image_viewer.setMinimumHeight(300)
        right_layout.addWidget(self._image_viewer)

        # Parameter scores panel
        param_scroll = QScrollArea()
        param_scroll.setWidgetResizable(True)
        param_scroll.setMaximumHeight(220)
        param_scroll.setStyleSheet("border: none;")
        self._param_container = QWidget()
        self._param_layout = QVBoxLayout(self._param_container)
        self._param_layout.setContentsMargins(0, 0, 0, 0)
        self._param_layout.setSpacing(4)
        param_scroll.setWidget(self._param_container)
        right_layout.addWidget(param_scroll)

        # Issues list
        self._issues_label = QLabel("")
        self._issues_label.setWordWrap(True)
        self._issues_label.setStyleSheet("color: #fca5a5; font-size: 11px;")
        right_layout.addWidget(self._issues_label)

        splitter.setSizes([550, 650])

        self.refresh_runs()

    def refresh_runs(self) -> None:
        runs = db_manager.list_runs(30)
        self._run_combo.blockSignals(True)
        self._run_combo.clear()
        for run in runs:
            short = run["run_id"][:8]
            date = (run.get("start_time") or "")[:10]
            lang = f"{run.get('source_language','?')}→{run.get('target_language','?')}"
            label = f"{short} | {date} | {lang} | {run.get('average_score', 0):.1f}"
            self._run_combo.addItem(label, run["run_id"])
        self._run_combo.blockSignals(False)
        if self._run_combo.count():
            self._load_selected_run(0)

    def load_run(self, run_id: str) -> None:
        for i in range(self._run_combo.count()):
            if self._run_combo.itemData(i) == run_id:
                self._run_combo.setCurrentIndex(i)
                return
        self.refresh_runs()

    def _load_selected_run(self, index: int) -> None:
        run_id = self._run_combo.itemData(index)
        if not run_id:
            return
        self._current_run_id = run_id
        self._results = db_manager.get_image_results(run_id)

        engines = sorted({r["engine"] for r in self._results})
        self._engine_combo.blockSignals(True)
        self._engine_combo.clear()
        self._engine_combo.addItem("All Engines")
        for eng in engines:
            self._engine_combo.addItem(eng)
        self._engine_combo.blockSignals(False)

        self._filter_results(self._engine_combo.currentText())

    def _filter_results(self, engine_filter: str) -> None:
        if engine_filter == "All Engines" or not engine_filter:
            filtered = self._results
        else:
            filtered = [r for r in self._results if r["engine"] == engine_filter]

        self._table.setRowCount(0)
        for r in sorted(filtered, key=lambda x: x["overall_score"]):
            row = self._table.rowCount()
            self._table.insertRow(row)

            items = [
                QTableWidgetItem(r["image_name"]),
                QTableWidgetItem(r["engine"]),
                QTableWidgetItem(f"{r['overall_score']:.1f}"),
                QTableWidgetItem(r.get("score_band", "")),
                QTableWidgetItem(str(len(r.get("issues", [])))),
            ]
            items[0].setData(Qt.UserRole, r)

            band = r.get("score_band", "")
            color = SCORE_COLORS.get(band, "#6b7280")
            items[2].setForeground(Qt.GlobalColor.white)
            items[2].setBackground(Qt.transparent)
            items[3].setForeground(Qt.GlobalColor.white)

            for col, item in enumerate(items):
                self._table.setItem(row, col, item)

        total = len(filtered)
        passed = sum(1 for r in filtered if r["overall_score"] >= 70)
        avg = sum(r["overall_score"] for r in filtered) / total if total else 0
        self._summary_label.setText(
            f"{total} results  |  Pass rate: {passed/total*100:.1f}%  |  Avg: {avg:.1f}"
            if total else "No results"
        )
        self._table.resizeColumnsToContents()

    def _on_row_selected(self, row: int) -> None:
        if row < 0:
            return
        item = self._table.item(row, 0)
        if item is None:
            return
        result = item.data(Qt.UserRole)
        if not result:
            return

        self._image_viewer.load_pair(
            result.get("original_path", ""),
            result.get("translated_path", ""),
        )

        # Clear old parameter bars
        while self._param_layout.count():
            child = self._param_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        param_scores = result.get("parameter_scores", {})
        for key, val in param_scores.items():
            score = val.get("score", 0) if isinstance(val, dict) else 0
            name = key.replace("_", " ").title()
            bar = ParameterScoreBar(name, score)
            self._param_layout.addWidget(bar)
        self._param_layout.addStretch()

        issues = result.get("issues", [])
        if issues:
            self._issues_label.setText("Issues:  " + "  •  ".join(issues[:6]))
        else:
            self._issues_label.setText("No issues detected.")
