"""Main application window for TransLingo QA Studio."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget,
)

from app.database import db_manager
from app.models.data_models import AppSettings, ScoringWeights, ValidationRun
from app.ui.sidebar import Sidebar
from app.ui.dashboard_widget import DashboardWidget
from app.ui.validation_widget import ValidationWidget
from app.ui.results_widget import ResultsWidget
from app.ui.reports_widget import ReportsWidget
from app.ui.settings_widget import SettingsWidget


RESOURCES = Path(__file__).parent.parent / "resources"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        db_manager.initialize_database()
        self.settings = self._load_settings()

        self.setWindowTitle("TransLingo QA Studio")
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)

        self._apply_theme(self.settings.theme)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.page_changed.connect(self._navigate_to)
        root_layout.addWidget(self.sidebar)

        # Content area
        self._stack = QStackedWidget()
        self._stack.setObjectName("content_panel")
        root_layout.addWidget(self._stack)

        # Pages
        self.dashboard = DashboardWidget()
        self.validation = ValidationWidget(self.settings)
        self.results = ResultsWidget()
        self.reports = ReportsWidget()
        self.settings_page = SettingsWidget(self.settings)

        for widget in [self.dashboard, self.validation, self.results, self.reports, self.settings_page]:
            self._stack.addWidget(widget)

        # Wire up signals
        self.dashboard.open_run_requested.connect(self._open_run_in_results)
        self.validation.run_completed.connect(self._on_run_completed)
        self.settings_page.settings_changed.connect(self._on_settings_changed)

        self._navigate_to("dashboard")
        self.dashboard.refresh()

    def _navigate_to(self, page_id: str) -> None:
        page_map = {
            "dashboard": self.dashboard,
            "validation": self.validation,
            "results": self.results,
            "reports": self.reports,
            "settings": self.settings_page,
        }
        widget = page_map.get(page_id)
        if widget:
            self._stack.setCurrentWidget(widget)
            self.sidebar.set_page(page_id)

    def _on_run_completed(self, run: ValidationRun) -> None:
        self.dashboard.refresh()
        self.results.refresh_runs()
        self.results.load_run(run.run_id)
        self._navigate_to("results")

    def _open_run_in_results(self, run_id: str) -> None:
        self.results.refresh_runs()
        self.results.load_run(run_id)
        self._navigate_to("results")

    def _on_settings_changed(self, settings: AppSettings) -> None:
        self.settings = settings
        self._apply_theme(settings.theme)

    def _apply_theme(self, theme: str) -> None:
        qss_path = RESOURCES / "styles" / f"{theme}_theme.qss"
        if qss_path.exists():
            with open(qss_path, "r") as f:
                QApplication.instance().setStyleSheet(f.read())

    def _load_settings(self) -> AppSettings:
        saved = db_manager.load_all_settings()
        settings = AppSettings()
        if "theme" in saved:
            settings.theme = saved["theme"]
        if "ocr_confidence_threshold" in saved:
            settings.ocr_confidence_threshold = saved["ocr_confidence_threshold"]
        if "parallel_workers" in saved:
            settings.parallel_workers = saved["parallel_workers"]
        if "thumbnail_size" in saved:
            settings.thumbnail_size = saved["thumbnail_size"]
        if "last_root_folder" in saved:
            settings.last_root_folder = saved["last_root_folder"]
        if "scoring_weights" in saved:
            try:
                settings.scoring_weights = ScoringWeights.from_dict(saved["scoring_weights"])
            except Exception:
                pass
        return settings
