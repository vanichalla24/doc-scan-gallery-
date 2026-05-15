"""Side-by-side synchronized image viewer with zoom, pan, and overlay/heatmap modes."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QPoint, QRectF, Signal, QTimer
from PySide6.QtGui import (
    QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent,
)
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSlider, QSplitter, QVBoxLayout, QWidget,
)


def numpy_to_qimage(arr: np.ndarray) -> QImage:
    if arr is None:
        return QImage()
    if len(arr.shape) == 2:
        h, w = arr.shape
        return QImage(arr.data, w, h, w, QImage.Format_Grayscale8)
    h, w, c = arr.shape
    if c == 3:
        rgb = arr[:, :, ::-1].copy()  # BGR→RGB
        return QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
    elif c == 4:
        return QImage(arr.data, w, h, w * 4, QImage.Format_RGBA8888)
    return QImage()


class ZoomableImageLabel(QLabel):
    """A QLabel that supports mouse-drag pan and scroll-wheel zoom."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(300, 250)
        self.setMouseTracking(True)
        self._zoom = 1.0
        self._offset = QPoint(0, 0)
        self._drag_start: Optional[QPoint] = None
        self._orig_pixmap: Optional[QPixmap] = None

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._orig_pixmap = pixmap
        self._zoom = 1.0
        self._offset = QPoint(0, 0)
        self._apply()

    def _apply(self) -> None:
        if self._orig_pixmap is None:
            return
        scaled = self._orig_pixmap.scaled(
            int(self._orig_pixmap.width() * self._zoom),
            int(self._orig_pixmap.height() * self._zoom),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        self._zoom = max(0.1, min(self._zoom * factor, 10.0))
        self._apply()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None:
            self._drag_start = event.position().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start = None
            self.setCursor(Qt.ArrowCursor)

    def reset_zoom(self) -> None:
        self._zoom = 1.0
        self._offset = QPoint(0, 0)
        self._apply()

    def zoom_in(self) -> None:
        self._zoom = min(self._zoom * 1.25, 10.0)
        self._apply()

    def zoom_out(self) -> None:
        self._zoom = max(self._zoom * 0.8, 0.1)
        self._apply()


class ImagePanel(QWidget):
    """Single image panel with label and controls."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #94a3b8;")
        layout.addWidget(self.title_label)

        self.image_label = ZoomableImageLabel()
        self.image_label.setFrameShape(QFrame.StyledPanel)
        self.image_label.setStyleSheet("background-color: #0f172a; border-radius: 8px;")

        scroll = QScrollArea()
        scroll.setWidget(self.image_label)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        layout.addWidget(scroll)

        ctrls = QHBoxLayout()
        for label, slot in [("−", self.image_label.zoom_out),
                             ("Reset", self.image_label.reset_zoom),
                             ("+", self.image_label.zoom_in)]:
            btn = QPushButton(label)
            btn.setFixedWidth(48)
            btn.setObjectName("secondary_btn")
            btn.clicked.connect(slot)
            ctrls.addWidget(btn)
        ctrls.addStretch()
        layout.addLayout(ctrls)

    def load_image(self, path: str) -> None:
        if not path or not Path(path).exists():
            self.image_label.setText(f"Image not found:\n{path}")
            return
        px = QPixmap(path)
        if px.isNull():
            self.image_label.setText("Cannot load image")
            return
        self.image_label.set_pixmap(px)

    def load_numpy(self, arr: np.ndarray) -> None:
        qimg = numpy_to_qimage(arr)
        if qimg.isNull():
            return
        self.image_label.set_pixmap(QPixmap.fromImage(qimg))


class ImageViewer(QWidget):
    """Side-by-side synchronized image viewer with overlay and heatmap modes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._orig_path: str = ""
        self._trans_path: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Side by Side", "Overlay", "Heatmap"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        toolbar.addWidget(QLabel("View:"))
        toolbar.addWidget(self.mode_combo)
        toolbar.addStretch()

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(50)
        self.opacity_slider.setFixedWidth(100)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self.opacity_label = QLabel("Opacity: 50%")
        self.opacity_slider.hide()
        self.opacity_label.hide()
        toolbar.addWidget(self.opacity_label)
        toolbar.addWidget(self.opacity_slider)
        layout.addLayout(toolbar)

        self.splitter = QSplitter(Qt.Horizontal)
        self.orig_panel = ImagePanel("Original")
        self.trans_panel = ImagePanel("Translated")
        self.splitter.addWidget(self.orig_panel)
        self.splitter.addWidget(self.trans_panel)
        self.splitter.setSizes([500, 500])
        layout.addWidget(self.splitter)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(self.info_label)

    def load_pair(self, original_path: str, translated_path: str) -> None:
        self._orig_path = original_path
        self._trans_path = translated_path
        self._render_current_mode()

        if original_path and Path(original_path).exists():
            import os
            size = os.path.getsize(original_path)
            self.info_label.setText(
                f"Original: {Path(original_path).name}  ({size // 1024} KB)   "
                f"Translated: {Path(translated_path).name}"
                if translated_path else ""
            )

    def _render_current_mode(self) -> None:
        mode = self.mode_combo.currentText()
        if mode == "Side by Side":
            self.orig_panel.load_image(self._orig_path)
            self.trans_panel.load_image(self._trans_path)
        elif mode == "Overlay":
            self._render_overlay()
        elif mode == "Heatmap":
            self._render_heatmap()

    def _on_mode_changed(self, mode: str) -> None:
        show_opacity = mode in ("Overlay",)
        self.opacity_slider.setVisible(show_opacity)
        self.opacity_label.setVisible(show_opacity)
        self._render_current_mode()

    def _on_opacity_changed(self, value: int) -> None:
        self.opacity_label.setText(f"Opacity: {value}%")
        if self.mode_combo.currentText() == "Overlay":
            self._render_overlay()

    def _render_overlay(self) -> None:
        try:
            import cv2
            orig = cv2.imread(self._orig_path)
            trans = cv2.imread(self._trans_path)
            if orig is None or trans is None:
                return
            h = min(orig.shape[0], trans.shape[0])
            w = min(orig.shape[1], trans.shape[1])
            orig = cv2.resize(orig, (w, h))
            trans = cv2.resize(trans, (w, h))
            alpha = self.opacity_slider.value() / 100.0
            blended = cv2.addWeighted(orig, 1 - alpha, trans, alpha, 0)
            self.orig_panel.load_numpy(blended[:, :, ::-1])
            self.trans_panel.load_numpy(blended[:, :, ::-1])
        except Exception as e:
            self.orig_panel.image_label.setText(f"Overlay error: {e}")

    def _render_heatmap(self) -> None:
        try:
            from app.core.visual_validator import VisualValidator
            vv = VisualValidator()
            heatmap = vv.generate_difference_heatmap(self._orig_path, self._trans_path)
            if heatmap is not None:
                self.orig_panel.load_image(self._orig_path)
                self.trans_panel.load_numpy(heatmap[:, :, ::-1])
        except Exception as e:
            self.trans_panel.image_label.setText(f"Heatmap error: {e}")
