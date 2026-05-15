"""Settings page — scoring weights, OCR thresholds, theme, workers."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QSlider, QSpinBox,
    QVBoxLayout, QWidget,
)

from app.database import db_manager
from app.models.data_models import AppSettings, ScoringWeights


WEIGHT_FIELDS = [
    ("semantic_similarity", "Semantic Similarity", 0, 50),
    ("ocr_accuracy", "OCR Accuracy", 0, 50),
    ("character_coverage", "Character Coverage", 0, 30),
    ("layout_similarity", "Layout Similarity", 0, 30),
    ("font_consistency", "Font Consistency", 0, 30),
    ("artifact_detection", "Artifact Detection", 0, 30),
    ("blur_detection", "Blur Detection", 0, 20),
    ("overflow_detection", "Overflow Detection", 0, 20),
    ("background_preservation", "Background Preservation", 0, 30),
]


class WeightSliderRow(QWidget):
    value_changed = Signal(str, float)

    def __init__(self, field: str, label: str, min_val: int, max_val: int, value: float):
        super().__init__()
        self.field = field

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(10)

        lbl = QLabel(label)
        lbl.setFixedWidth(195)
        lbl.setStyleSheet("color: #cbd5e1;")
        layout.addWidget(lbl)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(int(min_val * 10), int(max_val * 10))
        self._slider.setValue(int(value * 10))
        self._slider.setFixedWidth(200)
        layout.addWidget(self._slider)

        self._spinbox = QDoubleSpinBox()
        self._spinbox.setRange(min_val, max_val)
        self._spinbox.setSingleStep(0.5)
        self._spinbox.setDecimals(1)
        self._spinbox.setValue(value)
        self._spinbox.setFixedWidth(70)
        layout.addWidget(self._spinbox)

        layout.addStretch()

        self._slider.valueChanged.connect(
            lambda v: self._spinbox.setValue(v / 10.0)
        )
        self._spinbox.valueChanged.connect(
            lambda v: self._slider.setValue(int(v * 10))
        )
        self._spinbox.valueChanged.connect(
            lambda v: self.value_changed.emit(self.field, v)
        )

    def get_value(self) -> float:
        return self._spinbox.value()

    def set_value(self, v: float) -> None:
        self._spinbox.setValue(v)


class SettingsWidget(QWidget):
    settings_changed = Signal(object)

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._weight_rows: dict[str, WeightSliderRow] = {}

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

        title = QLabel("Settings")
        title.setObjectName("page_title")
        layout.addWidget(title)

        # Appearance
        appear_group = QGroupBox("Appearance")
        appear_group.setStyleSheet("QGroupBox { font-weight: 600; color: #cbd5e1; }")
        appear_form = QFormLayout(appear_group)
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["dark", "light"])
        self._theme_combo.setCurrentText(settings.theme)
        self._theme_combo.currentTextChanged.connect(self._on_theme_changed)
        appear_form.addRow("Theme:", self._theme_combo)
        layout.addWidget(appear_group)

        # OCR
        ocr_group = QGroupBox("OCR Settings")
        ocr_group.setStyleSheet("QGroupBox { font-weight: 600; color: #cbd5e1; }")
        ocr_form = QFormLayout(ocr_group)

        self._ocr_threshold = QDoubleSpinBox()
        self._ocr_threshold.setRange(0.1, 1.0)
        self._ocr_threshold.setSingleStep(0.05)
        self._ocr_threshold.setDecimals(2)
        self._ocr_threshold.setValue(settings.ocr_confidence_threshold)
        ocr_form.addRow("OCR Confidence Threshold:", self._ocr_threshold)

        self._workers_spin = QSpinBox()
        self._workers_spin.setRange(1, 16)
        self._workers_spin.setValue(settings.parallel_workers)
        ocr_form.addRow("Parallel Workers:", self._workers_spin)

        self._thumbnail_spin = QSpinBox()
        self._thumbnail_spin.setRange(100, 500)
        self._thumbnail_spin.setSingleStep(50)
        self._thumbnail_spin.setValue(settings.thumbnail_size)
        ocr_form.addRow("Thumbnail Size (px):", self._thumbnail_spin)
        layout.addWidget(ocr_group)

        # Scoring weights
        weights_group = QGroupBox("Scoring Weights  (must sum to 100)")
        weights_group.setStyleSheet("QGroupBox { font-weight: 600; color: #cbd5e1; }")
        weights_layout = QVBoxLayout(weights_group)

        self._total_label = QLabel()
        self._total_label.setStyleSheet("font-size: 12px; color: #f59e0b; font-weight: 600;")
        weights_layout.addWidget(self._total_label)

        w = settings.scoring_weights
        for field, label, mn, mx in WEIGHT_FIELDS:
            row = WeightSliderRow(field, label, mn, mx, getattr(w, field))
            row.value_changed.connect(self._on_weight_changed)
            self._weight_rows[field] = row
            weights_layout.addWidget(row)

        reset_weights_btn = QPushButton("Reset to Defaults")
        reset_weights_btn.setObjectName("secondary_btn")
        reset_weights_btn.setFixedWidth(160)
        reset_weights_btn.clicked.connect(self._reset_weights)
        weights_layout.addWidget(reset_weights_btn)
        layout.addWidget(weights_group)

        self._update_total_label()

        # Save / cancel
        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self._save)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _on_theme_changed(self, theme: str) -> None:
        self.settings.theme = theme
        self.settings_changed.emit(self.settings)

    def _on_weight_changed(self, field: str, value: float) -> None:
        setattr(self.settings.scoring_weights, field, value)
        self._update_total_label()

    def _update_total_label(self) -> None:
        total = sum(row.get_value() for row in self._weight_rows.values())
        color = "#22c55e" if abs(total - 100) < 0.1 else "#ef4444"
        self._total_label.setText(f"Total weight: {total:.1f}")
        self._total_label.setStyleSheet(f"font-size: 12px; color: {color}; font-weight: 600;")

    def _reset_weights(self) -> None:
        defaults = ScoringWeights()
        for field, row in self._weight_rows.items():
            row.set_value(getattr(defaults, field))
        self.settings.scoring_weights = defaults
        self._update_total_label()

    def _save(self) -> None:
        self.settings.theme = self._theme_combo.currentText()
        self.settings.ocr_confidence_threshold = self._ocr_threshold.value()
        self.settings.parallel_workers = self._workers_spin.value()
        self.settings.thumbnail_size = self._thumbnail_spin.value()

        for field, row in self._weight_rows.items():
            setattr(self.settings.scoring_weights, field, row.get_value())

        db_manager.save_setting("theme", self.settings.theme)
        db_manager.save_setting("ocr_confidence_threshold", self.settings.ocr_confidence_threshold)
        db_manager.save_setting("parallel_workers", self.settings.parallel_workers)
        db_manager.save_setting("thumbnail_size", self.settings.thumbnail_size)
        db_manager.save_setting("scoring_weights", self.settings.scoring_weights.as_dict())

        self.settings_changed.emit(self.settings)
        self._update_total_label()
