"""Dashboard page showing metrics, charts, and run history."""
from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from app.database import db_manager


class MetricCard(QFrame):
    def __init__(self, label: str, value: str, color: str = "#3b82f6", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumWidth(150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        num = QLabel(value)
        num.setObjectName("metric_num")
        num.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {color};")
        layout.addWidget(num)

        lbl = QLabel(label.upper())
        lbl.setObjectName("metric_label")
        layout.addWidget(lbl)

        self._num_label = num

    def set_value(self, value: str) -> None:
        self._num_label.setText(value)


class DashboardWidget(QWidget):
    open_run_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        container = QWidget()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(20)

        title = QLabel("Dashboard")
        title.setObjectName("page_title")
        layout.addWidget(title)

        self._metrics_layout = QHBoxLayout()
        self._metrics_layout.setSpacing(12)
        layout.addLayout(self._metrics_layout)

        self._card_total = MetricCard("Total Images", "—")
        self._card_pass = MetricCard("Pass Rate", "—", "#22c55e")
        self._card_avg = MetricCard("Avg Score", "—", "#3b82f6")
        self._card_runs = MetricCard("Total Runs", "—", "#8b5cf6")
        self._card_engines = MetricCard("Engines", "—", "#f59e0b")

        for card in [self._card_total, self._card_pass, self._card_avg,
                     self._card_runs, self._card_engines]:
            self._metrics_layout.addWidget(card)
        self._metrics_layout.addStretch()

        lbl_hist = QLabel("Recent Runs")
        lbl_hist.setObjectName("section_title")
        layout.addWidget(lbl_hist)

        self._runs_table = QTableWidget(0, 6)
        self._runs_table.setHorizontalHeaderLabels([
            "Run ID", "Date", "Source→Target", "Engines", "Avg Score", "Pass Rate"
        ])
        self._runs_table.horizontalHeader().setStretchLastSection(True)
        self._runs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._runs_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._runs_table.setAlternatingRowColors(True)
        self._runs_table.verticalHeader().setVisible(False)
        self._runs_table.doubleClicked.connect(self._on_run_double_click)
        layout.addWidget(self._runs_table)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondary_btn")
        refresh_btn.setFixedWidth(100)
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn, alignment=Qt.AlignRight)

    def refresh(self) -> None:
        runs = db_manager.list_runs(20)
        total_images = 0
        total_score = 0.0
        scored_runs = 0

        self._runs_table.setRowCount(0)

        for run in runs:
            row = self._runs_table.rowCount()
            self._runs_table.insertRow(row)

            run_id_short = run["run_id"][:8]
            date_str = (run.get("start_time") or "")[:16].replace("T", " ")
            lang_pair = f"{run.get('source_language','?')}→{run.get('target_language','?')}"
            import json
            engines = ", ".join(json.loads(run.get("engines", "[]")))
            avg = run.get("average_score", 0.0)
            pass_rate = run.get("pass_rate", 0.0)
            n = run.get("total_images", 0)

            cells = [run_id_short, date_str, lang_pair, engines,
                     f"{avg:.1f}", f"{pass_rate:.1f}%"]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, run["run_id"])
                self._runs_table.setItem(row, col, item)

            if n:
                total_images += n
                total_score += avg
                scored_runs += 1

        self._card_total.set_value(str(total_images))
        self._card_runs.set_value(str(len(runs)))
        avg_all = total_score / scored_runs if scored_runs else 0
        self._card_avg.set_value(f"{avg_all:.1f}")

        pass_total = sum(r.get("pass_rate", 0) for r in runs)
        avg_pass = pass_total / len(runs) if runs else 0
        self._card_pass.set_value(f"{avg_pass:.1f}%")

        all_engines: set = set()
        for r in runs:
            import json
            all_engines.update(json.loads(r.get("engines", "[]")))
        self._card_engines.set_value(str(len(all_engines)))

        self._runs_table.resizeColumnsToContents()

    def _on_run_double_click(self, index) -> None:
        item = self._runs_table.item(index.row(), 0)
        if item:
            run_id = item.data(Qt.UserRole)
            if run_id:
                self.open_run_requested.emit(run_id)
