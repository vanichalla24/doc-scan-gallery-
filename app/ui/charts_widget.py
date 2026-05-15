"""Embeddable matplotlib charts for engine comparison and score distribution."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

try:
    import matplotlib
    matplotlib.use("Qt5Agg")
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    HAS_MPL = True
except Exception:
    HAS_MPL = False


DARK_PARAMS = {
    "figure.facecolor": "#1e293b",
    "axes.facecolor": "#0f172a",
    "axes.edgecolor": "#334155",
    "axes.labelcolor": "#94a3b8",
    "text.color": "#e2e8f0",
    "xtick.color": "#94a3b8",
    "ytick.color": "#94a3b8",
    "grid.color": "#1e293b",
}

LIGHT_PARAMS = {
    "figure.facecolor": "#ffffff",
    "axes.facecolor": "#f8fafc",
    "axes.edgecolor": "#e2e8f0",
    "axes.labelcolor": "#374151",
    "text.color": "#0f172a",
    "xtick.color": "#374151",
    "ytick.color": "#374151",
    "grid.color": "#e2e8f0",
}

ENGINE_COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4"]


class ChartCanvas(QWidget):
    def __init__(self, parent=None, theme: str = "dark"):
        super().__init__(parent)
        self.theme = theme
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._canvas = None

    def _rc(self) -> Dict:
        return DARK_PARAMS if self.theme == "dark" else LIGHT_PARAMS

    def _make_canvas(self, figsize=(8, 4)) -> "FigureCanvas":
        if not HAS_MPL:
            return None
        with matplotlib.rc_context(self._rc()):
            fig = Figure(figsize=figsize, tight_layout=True)
        canvas = FigureCanvas(fig)
        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return canvas, fig

    def _replace_canvas(self, canvas) -> None:
        if self._canvas:
            self._layout.removeWidget(self._canvas)
            self._canvas.deleteLater()
        self._canvas = canvas
        self._layout.addWidget(canvas)


class EngineBarChart(ChartCanvas):
    """Vertical bar chart comparing average scores per engine."""

    def plot(self, engine_scores: Dict[str, float]) -> None:
        if not HAS_MPL or not engine_scores:
            return
        result = self._make_canvas((7, 3.5))
        if result is None:
            return
        canvas, fig = result

        with matplotlib.rc_context(self._rc()):
            ax = fig.add_subplot(111)
            engines = list(engine_scores.keys())
            scores = list(engine_scores.values())
            colors = [
                "#22c55e" if s >= 85 else "#f59e0b" if s >= 70 else "#ef4444"
                for s in scores
            ]
            bars = ax.bar(engines, scores, color=colors, edgecolor="#334155", linewidth=0.5)
            ax.set_ylim(0, 105)
            ax.set_ylabel("Score")
            ax.set_title("Average Score by Engine")
            ax.axhline(85, linestyle="--", color="#22c55e", linewidth=0.8, alpha=0.6, label="Good threshold")
            ax.axhline(70, linestyle="--", color="#f59e0b", linewidth=0.8, alpha=0.6, label="Acceptable threshold")
            ax.legend(fontsize=8)
            for bar, score in zip(bars, scores):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 1.5,
                    f"{score:.1f}", ha="center", fontsize=9,
                )
            canvas.draw()

        self._replace_canvas(canvas)


class ScoreDistributionChart(ChartCanvas):
    """Histogram of overall scores across all results."""

    def plot(self, scores: List[float]) -> None:
        if not HAS_MPL or not scores:
            return
        result = self._make_canvas((7, 3))
        if result is None:
            return
        canvas, fig = result

        with matplotlib.rc_context(self._rc()):
            ax = fig.add_subplot(111)
            ax.hist(scores, bins=20, range=(0, 100), color="#3b82f6", edgecolor="#0f172a")
            ax.axvline(70, linestyle="--", color="#f59e0b", linewidth=1, label="Acceptable (70)")
            ax.axvline(85, linestyle="--", color="#22c55e", linewidth=1, label="Good (85)")
            ax.set_xlabel("Score")
            ax.set_ylabel("Count")
            ax.set_title("Score Distribution")
            ax.legend(fontsize=8)
            canvas.draw()

        self._replace_canvas(canvas)


class RadarChart(ChartCanvas):
    """Radar / spider chart showing parameter scores per engine."""

    def plot(self, engine_params: Dict[str, Dict[str, float]]) -> None:
        if not HAS_MPL or not engine_params:
            return
        result = self._make_canvas((6, 5))
        if result is None:
            return
        canvas, fig = result

        import numpy as np
        all_params = []
        for params in engine_params.values():
            all_params = list(params.keys())
            break

        if not all_params:
            return

        N = len(all_params)
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        angles += angles[:1]

        with matplotlib.rc_context(self._rc()):
            ax = fig.add_subplot(111, polar=True)
            ax.set_facecolor(self._rc()["axes.facecolor"])

            for idx, (engine, params) in enumerate(engine_params.items()):
                values = [params.get(p, 0) for p in all_params]
                values += values[:1]
                color = ENGINE_COLORS[idx % len(ENGINE_COLORS)]
                ax.plot(angles, values, "o-", linewidth=1.5, color=color, label=engine)
                ax.fill(angles, values, alpha=0.1, color=color)

            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(
                [p.replace("_", "\n").title() for p in all_params],
                fontsize=7,
            )
            ax.set_ylim(0, 100)
            ax.set_title("Parameter Comparison by Engine", pad=20)
            ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=8)
            canvas.draw()

        self._replace_canvas(canvas)


class IssueFrequencyChart(ChartCanvas):
    """Horizontal bar chart showing most common issues."""

    def plot(self, issue_counts: Dict[str, int]) -> None:
        if not HAS_MPL or not issue_counts:
            return
        result = self._make_canvas((7, 3.5))
        if result is None:
            return
        canvas, fig = result

        top = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        labels, counts = zip(*top) if top else ([], [])
        short_labels = [l[:40] + "…" if len(l) > 40 else l for l in labels]

        with matplotlib.rc_context(self._rc()):
            ax = fig.add_subplot(111)
            ax.barh(short_labels[::-1], list(counts)[::-1], color="#ef4444", edgecolor="#0f172a")
            ax.set_xlabel("Occurrences")
            ax.set_title("Most Common Issues")
            canvas.draw()

        self._replace_canvas(canvas)
