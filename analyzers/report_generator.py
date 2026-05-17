"""
PDF Report Generator for the Document Scanner Benchmark Tool.

Uses fpdf2 to produce a multi-page PDF summarising analysis results
across scanner apps and quality features.
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any


class ReportGenerator:
    """
    Generates a PDF report from benchmark analysis results.

    Usage::

        gen = ReportGenerator()
        pdf_bytes = gen.generate(results, app_names)

    Args (generate method):
        results: Nested dict ``{feature_name: {app_name: analysis_result_dict}}``.
            Each analysis_result_dict must contain keys: passed, score, confidence.
        app_names: Ordered list of scanner app names.

    Returns:
        bytes: Raw PDF content.
    """

    FEATURE_LABELS = {
        "finger_removal": "Finger Removal",
        "dog_ear_removal": "Dog-ear Removal",
        "warp_correction": "Warp Correction",
        "ocr_accuracy": "OCR Accuracy",
    }

    PAGE_W = 210   # A4 mm
    PAGE_H = 297
    MARGIN = 15
    COL_W = 42

    # Colours (R, G, B)
    COLOR_PASS = (30, 150, 60)
    COLOR_FAIL = (200, 40, 40)
    COLOR_HEADER = (30, 70, 130)
    COLOR_SUBHEADER = (70, 110, 180)
    COLOR_LIGHT_GRAY = (230, 230, 230)
    COLOR_WHITE = (255, 255, 255)
    COLOR_BLACK = (10, 10, 10)

    def generate(self, results: dict[str, dict[str, Any]], app_names: list[str]) -> bytes:
        """
        Build the PDF report and return it as bytes.

        Args:
            results: ``{feature: {app: result_dict}}``
            app_names: List of app names in desired display order.

        Returns:
            bytes: PDF bytes, or empty bytes if fpdf2 is not installed.
        """
        try:
            from fpdf import FPDF
        except ImportError:
            return b""

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=self.MARGIN)

        self._cover_page(pdf, app_names, results)
        for feature, feature_label in self.FEATURE_LABELS.items():
            if feature in results:
                self._feature_page(pdf, feature_label, results[feature], app_names)
        self._summary_page(pdf, results, app_names)

        # fpdf2: output() with dest='S' returns a string in older versions,
        # bytes in newer ones. Handle both.
        raw = pdf.output(dest="S")
        if isinstance(raw, str):
            return raw.encode("latin-1")
        return bytes(raw)

    # ------------------------------------------------------------------
    # Page builders
    # ------------------------------------------------------------------

    def _cover_page(self, pdf, app_names: list[str], results: dict) -> None:
        from fpdf import FPDF
        pdf.add_page()

        # Title block
        pdf.set_fill_color(*self.COLOR_HEADER)
        pdf.rect(0, 0, self.PAGE_W, 55, "F")
        pdf.set_text_color(*self.COLOR_WHITE)
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_y(14)
        pdf.cell(0, 12, "Document Scanner Benchmark Tool", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 13)
        pdf.cell(0, 8, "Automated Quality Analysis Report", align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.set_text_color(*self.COLOR_BLACK)
        pdf.set_y(65)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 8, f"Report date: {date.today().strftime('%B %d, %Y')}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Apps tested: {len(app_names)}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"Features analysed: {len(results)}", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Scanner Apps Included", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        for i, name in enumerate(app_names, 1):
            pdf.cell(0, 7, f"  {i}. {name}", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(8)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Features Tested", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        for feat_key, feat_label in self.FEATURE_LABELS.items():
            if feat_key in results:
                pdf.cell(0, 7, f"  • {feat_label}", new_x="LMARGIN", new_y="NEXT")

    def _feature_page(
        self,
        pdf,
        feature_label: str,
        feature_results: dict[str, Any],
        app_names: list[str],
    ) -> None:
        pdf.add_page()
        self._section_header(pdf, feature_label)

        # Table header
        self._table_header_row(pdf, ["App", "Score", "Pass/Fail", "Confidence"])

        fill = False
        for app in app_names:
            if app not in feature_results:
                continue
            res = feature_results[app]
            score = res.get("score", 0.0)
            passed = res.get("passed", False)
            conf = res.get("confidence", 0.0)

            self._table_data_row(
                pdf,
                [
                    app,
                    f"{score:.1f}",
                    "PASS" if passed else "FAIL",
                    f"{conf:.2f}",
                ],
                passed=passed,
                fill=fill,
            )
            fill = not fill

        # Stats block
        pdf.ln(6)
        scores = [
            feature_results[a]["score"]
            for a in app_names
            if a in feature_results and "score" in feature_results[a]
        ]
        passes = [
            feature_results[a]["passed"]
            for a in app_names
            if a in feature_results and "passed" in feature_results[a]
        ]

        if scores:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, "Summary Statistics", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 6, f"  Average score : {sum(scores)/len(scores):.1f}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 6, f"  Highest score : {max(scores):.1f}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 6, f"  Lowest score  : {min(scores):.1f}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 6, f"  Pass rate     : {sum(passes)}/{len(passes)} apps", new_x="LMARGIN", new_y="NEXT")

    def _summary_page(self, pdf, results: dict, app_names: list[str]) -> None:
        pdf.add_page()
        self._section_header(pdf, "Summary Dashboard")

        # Per-feature pass rate
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "Pass Rates by Feature", new_x="LMARGIN", new_y="NEXT")

        self._table_header_row(pdf, ["Feature", "Pass Rate", "Avg Score", "Best App"])
        fill = False
        for feat_key, feat_label in self.FEATURE_LABELS.items():
            if feat_key not in results:
                continue
            feat = results[feat_key]
            passes = [feat[a]["passed"] for a in app_names if a in feat]
            scores = [feat[a]["score"] for a in app_names if a in feat]
            if not passes:
                continue
            pass_rate = f"{sum(passes)}/{len(passes)}"
            avg_score = f"{sum(scores)/len(scores):.1f}" if scores else "N/A"
            best = max(
                (a for a in app_names if a in feat),
                key=lambda a: feat[a].get("score", 0),
                default="N/A",
            )
            self._table_data_row(
                pdf,
                [feat_label, pass_rate, avg_score, best],
                passed=sum(passes) == len(passes),
                fill=fill,
            )
            fill = not fill

        # Per-app overall score
        pdf.ln(8)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "Overall Scores by App", new_x="LMARGIN", new_y="NEXT")

        self._table_header_row(pdf, ["App", "Avg Score", "Features Passed", "Overall"])
        fill = False
        for app in app_names:
            app_scores = []
            app_passes = []
            for feat_key in self.FEATURE_LABELS:
                if feat_key in results and app in results[feat_key]:
                    r = results[feat_key][app]
                    app_scores.append(r.get("score", 0.0))
                    app_passes.append(r.get("passed", False))

            if not app_scores:
                continue

            avg = sum(app_scores) / len(app_scores)
            feat_passed = f"{sum(app_passes)}/{len(app_passes)}"
            overall_pass = sum(app_passes) == len(app_passes)
            self._table_data_row(
                pdf,
                [app, f"{avg:.1f}", feat_passed, "PASS" if overall_pass else "FAIL"],
                passed=overall_pass,
                fill=fill,
            )
            fill = not fill

    # ------------------------------------------------------------------
    # Table helpers
    # ------------------------------------------------------------------

    def _section_header(self, pdf, title: str) -> None:
        pdf.set_fill_color(*self.COLOR_SUBHEADER)
        pdf.set_text_color(*self.COLOR_WHITE)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*self.COLOR_BLACK)
        pdf.ln(3)

    def _table_header_row(self, pdf, cols: list[str]) -> None:
        pdf.set_fill_color(*self.COLOR_HEADER)
        pdf.set_text_color(*self.COLOR_WHITE)
        pdf.set_font("Helvetica", "B", 10)
        usable_w = self.PAGE_W - 2 * self.MARGIN
        col_w = usable_w / len(cols)
        for col in cols:
            pdf.cell(col_w, 8, col, border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_text_color(*self.COLOR_BLACK)

    def _table_data_row(
        self,
        pdf,
        cols: list[str],
        passed: bool = True,
        fill: bool = False,
    ) -> None:
        usable_w = self.PAGE_W - 2 * self.MARGIN
        col_w = usable_w / len(cols)

        if fill:
            pdf.set_fill_color(*self.COLOR_LIGHT_GRAY)
        else:
            pdf.set_fill_color(*self.COLOR_WHITE)

        pdf.set_font("Helvetica", "", 10)

        for i, col_text in enumerate(cols):
            # Colour the pass/fail cell
            if col_text in ("PASS", "FAIL"):
                color = self.COLOR_PASS if col_text == "PASS" else self.COLOR_FAIL
                pdf.set_text_color(*color)
                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(col_w, 7, col_text, border=1, fill=fill, align="C")
                pdf.set_text_color(*self.COLOR_BLACK)
                pdf.set_font("Helvetica", "", 10)
            else:
                pdf.cell(col_w, 7, col_text, border=1, fill=fill, align="C")

        pdf.ln()
