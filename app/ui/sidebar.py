"""Sidebar navigation component."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget,
)


NAV_ITEMS = [
    ("dashboard", "Dashboard", "📊"),
    ("validation", "Run Validation", "▶"),
    ("results", "Results", "📋"),
    ("reports", "Reports", "📄"),
    ("settings", "Settings", "⚙"),
]


class SidebarButton(QPushButton):
    def __init__(self, page_id: str, icon: str, label: str):
        super().__init__(f"  {icon}  {label}")
        self.page_id = page_id
        self.setCheckable(True)
        self.setFixedHeight(44)
        self.setCursor(Qt.PointingHandCursor)


class Sidebar(QWidget):
    page_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 16)
        layout.setSpacing(4)

        logo = QLabel("TransLingo")
        logo.setObjectName("sidebar_logo")
        layout.addWidget(logo)

        version = QLabel("QA Studio v1.0")
        version.setObjectName("sidebar_version")
        layout.addWidget(version)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #1e293b;")
        layout.addWidget(sep)
        layout.addSpacing(8)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, SidebarButton] = {}

        for page_id, label, icon in NAV_ITEMS:
            btn = SidebarButton(page_id, icon, label)
            self._group.addButton(btn)
            self._buttons[page_id] = btn
            layout.addWidget(btn)
            btn.clicked.connect(lambda checked, pid=page_id: self.page_changed.emit(pid))

        layout.addStretch()

        self._buttons["dashboard"].setChecked(True)

    def set_page(self, page_id: str) -> None:
        if page_id in self._buttons:
            self._buttons[page_id].setChecked(True)
