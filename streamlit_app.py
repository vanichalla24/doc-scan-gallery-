"""
Document Scanner Benchmark Tool — Streamlit entry point.

Tabs: Finger Removal | Dog-ear Removal | Warp Correction | OCR Accuracy | Summary Dashboard
"""

from __future__ import annotations

import io
import os
from typing import Any

import numpy as np
import streamlit as st
from PIL import Image

from analyzers.finger_removal import FingerRemovalAnalyzer
from analyzers.dog_ear_removal import DogEarRemovalAnalyzer
from analyzers.warp_correction import WarpCorrectionAnalyzer
from analyzers.ocr_accuracy import OCRAccuracyAnalyzer
from analyzers.report_generator import ReportGenerator
from utils.image_utils import load_image, create_side_by_side

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Document Scanner Benchmark Tool",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_APPS = 5
FEATURE_KEYS = ["finger_removal", "dog_ear_removal", "warp_correction", "ocr_accuracy"]
FEATURE_LABELS = {
    "finger_removal":  "Finger Removal",
    "dog_ear_removal": "Dog-ear Removal",
    "warp_correction": "Warp Correction",
    "ocr_accuracy":    "OCR Accuracy",
}

# Colour helpers (HTML)
_PASS_BADGE = "background:#27ae60;color:#fff;padding:3px 10px;border-radius:4px;font-weight:bold"
_FAIL_BADGE = "background:#c0392b;color:#fff;padding:3px 10px;border-radius:4px;font-weight:bold"


def _badge(passed: bool) -> str:
    style = _PASS_BADGE if passed else _FAIL_BADGE
    text  = "PASS" if passed else "FAIL"
    return f'<span style="{style}">{text}</span>'


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def _init_state():
    if "results" not in st.session_state:
        # {feature_key: {app_name: result_dict}}
        st.session_state["results"] = {k: {} for k in FEATURE_KEYS}
    if "app_images" not in st.session_state:
        # {app_name: [np.ndarray, ...]}
        st.session_state["app_images"] = {}


def _cache_key(app_name: str, feature: str) -> str:
    return f"{app_name}__{feature}"


# ---------------------------------------------------------------------------
# Sidebar — upload images per app
# ---------------------------------------------------------------------------

def render_sidebar() -> dict[str, list[np.ndarray]]:
    st.sidebar.title("📂 Upload Scanner Outputs")
    st.sidebar.markdown("Upload images from up to **5 scanner apps** for comparison.")

    app_images: dict[str, list[np.ndarray]] = {}

    for i in range(1, MAX_APPS + 1):
        with st.sidebar.expander(f"App {i}", expanded=(i == 1)):
            app_name = st.text_input(
                "App name", value=f"Scanner App {i}", key=f"app_name_{i}"
            )
            uploaded = st.file_uploader(
                "Images",
                type=["png", "jpg", "jpeg", "bmp", "tiff", "webp"],
                accept_multiple_files=True,
                key=f"upload_{i}",
            )
            if uploaded and app_name.strip():
                images = []
                for uf in uploaded:
                    try:
                        img = load_image(uf)
                        images.append(img)
                    except Exception as e:
                        st.sidebar.warning(f"Could not load {uf.name}: {e}")
                if images:
                    app_images[app_name.strip()] = images

    return app_images


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

ANALYZERS = {
    "finger_removal":  FingerRemovalAnalyzer,
    "dog_ear_removal": DogEarRemovalAnalyzer,
    "warp_correction": WarpCorrectionAnalyzer,
    "ocr_accuracy":    OCRAccuracyAnalyzer,
}


def run_analysis(
    feature: str,
    app_name: str,
    images: list[np.ndarray],
) -> dict[str, Any]:
    """Run the analyzer for *feature* on all images of one app; return aggregate result."""
    analyzer = ANALYZERS[feature]()
    per_image = []
    for img in images:
        try:
            r = analyzer.analyze(img)
            per_image.append(r)
        except Exception as e:
            per_image.append({
                "passed": False, "score": 0.0, "confidence": 0.0,
                "details": {"error": str(e)}, "visualization": img,
            })

    if not per_image:
        return {"passed": False, "score": 0.0, "confidence": 0.0,
                "details": {}, "visualization": images[0] if images else np.zeros((100,100,3),np.uint8),
                "per_image": []}

    avg_score = float(np.mean([r["score"] for r in per_image]))
    avg_conf  = float(np.mean([r["confidence"] for r in per_image]))
    passed    = avg_score >= 70.0

    return {
        "passed":      passed,
        "score":       round(avg_score, 2),
        "confidence":  round(avg_conf, 3),
        "details":     per_image[0]["details"],
        "visualization": per_image[0]["visualization"],
        "per_image":   per_image,
    }


# ---------------------------------------------------------------------------
# AI Explanation
# ---------------------------------------------------------------------------

def _ai_explanation(feature_label: str, app_name: str, result: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "(Set ANTHROPIC_API_KEY to enable AI explanations.)"
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            f"You are a document scanning quality expert. "
            f"Explain the following scan quality result in plain English (2-3 sentences). "
            f"Feature: {feature_label}. App: {app_name}. "
            f"Score: {result['score']}/100. "
            f"Pass: {result['passed']}. Confidence: {result['confidence']}. "
            f"Details: {result['details']}."
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"(AI explanation unavailable: {e})"


# ---------------------------------------------------------------------------
# Per-feature tab renderer
# ---------------------------------------------------------------------------

def render_feature_tab(feature: str, app_images: dict[str, list[np.ndarray]]):
    feature_label = FEATURE_LABELS[feature]
    st.header(feature_label)

    if not app_images:
        st.info("Upload images in the sidebar to begin analysis.")
        return

    run_btn = st.button(f"▶ Analyse {feature_label}", key=f"run_{feature}")

    results_store = st.session_state["results"][feature]

    if run_btn:
        for app_name, images in app_images.items():
            with st.spinner(f"Analysing {app_name} …"):
                result = run_analysis(feature, app_name, images)
                results_store[app_name] = result

    if not results_store:
        st.caption("Press the button above to run the analysis.")
        return

    # ---- Results grid ----
    apps = list(results_store.keys())
    cols = st.columns(min(len(apps), 3))

    for idx, app_name in enumerate(apps):
        result = results_store[app_name]
        col = cols[idx % len(cols)]

        with col:
            st.subheader(app_name)
            st.markdown(_badge(result["passed"]), unsafe_allow_html=True)
            st.metric("Score", f"{result['score']:.1f} / 100")
            st.metric("Confidence", f"{result['confidence']:.2f}")

            # Side-by-side comparison
            orig_images = app_images.get(app_name, [])
            if orig_images:
                vis = result["visualization"]
                side = create_side_by_side(orig_images[0], vis)
                st.image(side, use_container_width=True)

            # Details expander
            with st.expander("Details"):
                for k, v in result["details"].items():
                    st.write(f"**{k}**: {v}")

            # AI explanation expander
            with st.expander("AI Explanation"):
                explanation = _ai_explanation(feature_label, app_name, result)
                st.write(explanation)

    # ---- Per-image results (if multiple images uploaded) ----
    for app_name in apps:
        per = results_store[app_name].get("per_image", [])
        if len(per) > 1:
            with st.expander(f"All {len(per)} images — {app_name}"):
                img_cols = st.columns(min(len(per), 4))
                orig_list = app_images.get(app_name, [])
                for j, pr in enumerate(per):
                    with img_cols[j % 4]:
                        if j < len(orig_list):
                            side = create_side_by_side(orig_list[j], pr["visualization"])
                            st.image(side, use_container_width=True)
                        st.markdown(_badge(pr["passed"]), unsafe_allow_html=True)
                        st.caption(f"Score: {pr['score']:.1f}")


# ---------------------------------------------------------------------------
# Summary Dashboard tab
# ---------------------------------------------------------------------------

def render_summary(app_images: dict[str, list[np.ndarray]]):
    st.header("Summary Dashboard")

    results_store = st.session_state["results"]
    app_names = list(app_images.keys()) if app_images else []

    if not app_names:
        st.info("Upload images in the sidebar to begin.")
        return

    # --- Run all features button ---
    if st.button("▶ Run All Features"):
        for feature in FEATURE_KEYS:
            for app_name, images in app_images.items():
                with st.spinner(f"{FEATURE_LABELS[feature]} — {app_name} …"):
                    results_store[feature][app_name] = run_analysis(feature, app_name, images)

    any_results = any(results_store[f] for f in FEATURE_KEYS)
    if not any_results:
        st.caption("Run individual feature tabs or click 'Run All Features' above.")
        return

    # --- Score matrix table ---
    st.subheader("Score Matrix")
    import pandas as pd

    rows = []
    for app in app_names:
        row = {"App": app}
        for fk in FEATURE_KEYS:
            r = results_store[fk].get(app)
            row[FEATURE_LABELS[fk]] = f"{r['score']:.0f}" if r else "—"
        rows.append(row)
    df = pd.DataFrame(rows).set_index("App")
    st.dataframe(df, use_container_width=True)

    # --- Bar chart ---
    st.subheader("Scores by Feature")
    chart_data: dict[str, list] = {"App": []}
    for fk in FEATURE_KEYS:
        chart_data[FEATURE_LABELS[fk]] = []
    for app in app_names:
        chart_data["App"].append(app)
        for fk in FEATURE_KEYS:
            r = results_store[fk].get(app)
            chart_data[FEATURE_LABELS[fk]].append(r["score"] if r else 0.0)

    chart_df = pd.DataFrame(chart_data).set_index("App")
    st.bar_chart(chart_df)

    # --- Pass rate summary ---
    st.subheader("Pass Rate by Feature")
    for fk in FEATURE_KEYS:
        fr = results_store[fk]
        if not fr:
            continue
        passes = sum(1 for a in app_names if fr.get(a, {}).get("passed", False))
        total  = sum(1 for a in app_names if a in fr)
        pct    = int(100 * passes / total) if total else 0
        label  = FEATURE_LABELS[fk]
        st.progress(pct / 100, text=f"{label}: {passes}/{total} apps passed ({pct}%)")

    # --- PDF Report ---
    st.subheader("Export Report")
    if st.button("Generate PDF Report"):
        with st.spinner("Building PDF …"):
            gen = ReportGenerator()
            nested = {FEATURE_LABELS[fk]: results_store[fk] for fk in FEATURE_KEYS if results_store[fk]}
            pdf_bytes = gen.generate(nested, app_names)
        if pdf_bytes:
            st.download_button(
                label="⬇ Download PDF",
                data=pdf_bytes,
                file_name="scanner_benchmark_report.pdf",
                mime="application/pdf",
            )
        else:
            st.error("PDF generation failed. Make sure fpdf2 is installed: pip install fpdf2")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _init_state()
    st.title("🔍 Document Scanner Benchmark Tool")
    st.caption(
        "Upload scanned document images from multiple scanner apps, "
        "then evaluate each quality feature independently."
    )

    app_images = render_sidebar()

    tabs = st.tabs([
        "Finger Removal",
        "Dog-ear Removal",
        "Warp Correction",
        "OCR Accuracy",
        "Summary Dashboard",
    ])

    with tabs[0]:
        render_feature_tab("finger_removal", app_images)
    with tabs[1]:
        render_feature_tab("dog_ear_removal", app_images)
    with tabs[2]:
        render_feature_tab("warp_correction", app_images)
    with tabs[3]:
        render_feature_tab("ocr_accuracy", app_images)
    with tabs[4]:
        render_summary(app_images)


if __name__ == "__main__":
    main()
