"""Visual validation using OpenCV, scikit-image, and Pillow."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


def _load_image(path: str) -> Optional[np.ndarray]:
    try:
        import cv2
        img = cv2.imread(path)
        if img is None:
            from PIL import Image
            pil = Image.open(path).convert("RGB")
            img = np.array(pil)[:, :, ::-1]  # RGB→BGR
        return img
    except Exception as e:
        logger.error(f"Failed to load image {path}: {e}")
        return None


def _to_gray(img: np.ndarray) -> np.ndarray:
    import cv2
    if len(img.shape) == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


class VisualValidator:
    """Performs image-level visual quality checks."""

    def detect_blur(self, image_path: str) -> Tuple[float, List[str]]:
        """Variance of Laplacian blur detection. Returns (score 0-100, issues)."""
        issues = []
        img = _load_image(image_path)
        if img is None:
            return 50.0, ["Could not load image for blur detection"]

        import cv2
        gray = _to_gray(img)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        if lap_var < 50:
            issues.append(f"Image is blurry (Laplacian variance: {lap_var:.1f})")
            score = max(0.0, lap_var * 2)
        elif lap_var < 100:
            issues.append(f"Slightly blurry (Laplacian variance: {lap_var:.1f})")
            score = 60.0 + (lap_var - 50) * 0.8
        else:
            score = min(100.0, 100.0 - max(0, (500 - lap_var)) * 0.01)

        return round(max(0.0, min(100.0, score)), 2), issues

    def detect_artifacts(
        self, original_path: str, translated_path: str
    ) -> Tuple[float, List[str]]:
        """SSIM + edge analysis artifact detection. Returns (score 0-100, issues)."""
        issues = []
        orig = _load_image(original_path)
        trans = _load_image(translated_path)

        if orig is None or trans is None:
            return 50.0, ["Could not load images for artifact detection"]

        try:
            from skimage.metrics import structural_similarity as ssim
            import cv2

            h = min(orig.shape[0], trans.shape[0])
            w = min(orig.shape[1], trans.shape[1])
            orig_r = cv2.resize(orig, (w, h))
            trans_r = cv2.resize(trans, (w, h))

            orig_g = _to_gray(orig_r)
            trans_g = _to_gray(trans_r)

            score_ssim, diff = ssim(orig_g, trans_g, full=True)

            diff_abs = np.abs(diff)
            artifact_ratio = float(np.mean(diff_abs > 0.3))

            if artifact_ratio > 0.3:
                issues.append(
                    f"High artifact level detected: {artifact_ratio:.0%} of pixels differ significantly"
                )
            elif artifact_ratio > 0.15:
                issues.append(f"Moderate artifacts detected: {artifact_ratio:.0%} pixel difference")

            score = score_ssim * 100
            return round(max(0.0, min(100.0, score)), 2), issues

        except Exception as e:
            logger.error(f"Artifact detection failed: {e}")
            return 60.0, [f"Artifact detection error: {str(e)[:80]}"]

    def detect_overflow(self, image_path: str, ocr_boxes: List[Dict]) -> Tuple[float, List[str]]:
        """Detect text overflowing outside image bounds. Returns (score, issues)."""
        issues = []
        img = _load_image(image_path)
        if img is None:
            return 80.0, ["Could not load image for overflow detection"]

        h, w = img.shape[:2]
        overflow_count = 0

        for box_info in ocr_boxes:
            bbox = box_info.get("bbox", [])
            if not bbox or len(bbox) < 4:
                continue
            try:
                points = np.array(bbox)
                xs = points[:, 0]
                ys = points[:, 1]
                if xs.min() < 0 or xs.max() > w or ys.min() < 0 or ys.max() > h:
                    overflow_count += 1
            except Exception:
                continue

        if overflow_count > 0:
            total = max(1, len(ocr_boxes))
            ratio = overflow_count / total
            issues.append(f"Text overflow detected in {overflow_count} text regions")
            score = max(0.0, 100.0 - ratio * 150)
        else:
            score = 100.0

        return round(score, 2), issues

    def detect_cropping(
        self, original_path: str, translated_path: str
    ) -> Tuple[float, List[str]]:
        """Detect cropping or truncation by comparing image dimensions."""
        issues = []
        orig = _load_image(original_path)
        trans = _load_image(translated_path)

        if orig is None or trans is None:
            return 80.0, ["Could not load images for cropping detection"]

        oh, ow = orig.shape[:2]
        th, tw = trans.shape[:2]

        h_ratio = min(oh, th) / max(oh, th) if max(oh, th) > 0 else 1.0
        w_ratio = min(ow, tw) / max(ow, tw) if max(ow, tw) > 0 else 1.0
        area_ratio = (th * tw) / (oh * ow) if (oh * ow) > 0 else 1.0

        score = min(h_ratio, w_ratio) * 100

        if area_ratio < 0.7:
            issues.append(
                f"Possible cropping: translated image is {area_ratio:.0%} of original area"
            )
            score = min(score, 50.0)
        elif area_ratio < 0.85:
            issues.append(f"Minor cropping detected: {area_ratio:.0%} area coverage")

        return round(score, 2), issues

    def check_background_preservation(
        self, original_path: str, translated_path: str
    ) -> Tuple[float, List[str]]:
        """Compare background regions between original and translated images."""
        issues = []
        orig = _load_image(original_path)
        trans = _load_image(translated_path)

        if orig is None or trans is None:
            return 80.0, ["Could not load images for background check"]

        try:
            import cv2
            h = min(orig.shape[0], trans.shape[0])
            w = min(orig.shape[1], trans.shape[1])
            orig_r = cv2.resize(orig, (w, h)).astype(float)
            trans_r = cv2.resize(trans, (w, h)).astype(float)

            diff = np.abs(orig_r - trans_r)
            mean_diff = float(np.mean(diff))

            if mean_diff > 50:
                issues.append(f"Significant background change (mean pixel diff: {mean_diff:.1f})")
                score = max(0.0, 100.0 - mean_diff)
            elif mean_diff > 25:
                issues.append(f"Moderate background change (mean pixel diff: {mean_diff:.1f})")
                score = max(50.0, 100.0 - mean_diff)
            else:
                score = max(60.0, 100.0 - mean_diff * 2)

            return round(score, 2), issues

        except Exception as e:
            logger.error(f"Background check failed: {e}")
            return 70.0, [f"Background check error: {str(e)[:80]}"]

    def compute_visual_similarity(
        self, original_path: str, translated_path: str
    ) -> Tuple[float, List[str]]:
        """Overall visual similarity using SSIM. Returns (score 0-100, issues)."""
        issues = []
        orig = _load_image(original_path)
        trans = _load_image(translated_path)

        if orig is None or trans is None:
            return 50.0, ["Could not load images for similarity check"]

        try:
            from skimage.metrics import structural_similarity as ssim
            import cv2

            h = min(orig.shape[0], trans.shape[0])
            w = min(orig.shape[1], trans.shape[1])
            orig_r = cv2.resize(orig, (w, h))
            trans_r = cv2.resize(trans, (w, h))

            orig_g = _to_gray(orig_r)
            trans_g = _to_gray(trans_r)

            score_val = ssim(orig_g, trans_g)
            score = max(0.0, min(100.0, score_val * 100))

            if score < 40:
                issues.append("Very low visual similarity")
            elif score < 60:
                issues.append("Low visual similarity detected")

            return round(score, 2), issues

        except Exception as e:
            logger.error(f"Visual similarity failed: {e}")
            return 50.0, [f"Similarity error: {str(e)[:80]}"]

    def compare_layout(
        self,
        orig_boxes: List[Dict],
        trans_boxes: List[Dict],
        orig_shape: Tuple[int, int],
        trans_shape: Tuple[int, int],
    ) -> Tuple[float, List[str]]:
        """Compare normalized bounding boxes for layout similarity."""
        issues = []
        if not orig_boxes or not trans_boxes:
            return 70.0, ["Insufficient bounding box data for layout comparison"]

        def normalize_boxes(boxes, shape):
            h, w = shape
            result = []
            for b in boxes:
                bbox = b.get("bbox", [])
                if not bbox or len(bbox) < 4:
                    continue
                try:
                    pts = np.array(bbox)
                    cx = float(pts[:, 0].mean()) / w
                    cy = float(pts[:, 1].mean()) / h
                    bw = float(pts[:, 0].max() - pts[:, 0].min()) / w
                    bh = float(pts[:, 1].max() - pts[:, 1].min()) / h
                    result.append([cx, cy, bw, bh])
                except Exception:
                    continue
            return result

        orig_norm = normalize_boxes(orig_boxes, orig_shape)
        trans_norm = normalize_boxes(trans_boxes, trans_shape)

        if not orig_norm or not trans_norm:
            return 70.0, ["Could not normalize bounding boxes"]

        n = min(len(orig_norm), len(trans_norm))
        if n == 0:
            return 70.0, issues

        diffs = []
        for i in range(n):
            diff = np.linalg.norm(np.array(orig_norm[i]) - np.array(trans_norm[i]))
            diffs.append(diff)

        mean_diff = float(np.mean(diffs))
        score = max(0.0, 100.0 - mean_diff * 200)

        if mean_diff > 0.3:
            issues.append(f"Significant layout shift detected (mean offset: {mean_diff:.3f})")
        elif mean_diff > 0.15:
            issues.append(f"Moderate layout shift (mean offset: {mean_diff:.3f})")

        return round(score, 2), issues

    def estimate_font_size_diff(
        self, orig_boxes: List[Dict], trans_boxes: List[Dict]
    ) -> Tuple[float, List[str]]:
        """Estimate font size difference via text box heights."""
        issues = []
        if not orig_boxes or not trans_boxes:
            return 80.0, []

        def avg_height(boxes):
            heights = []
            for b in boxes:
                bbox = b.get("bbox", [])
                if not bbox or len(bbox) < 4:
                    continue
                try:
                    pts = np.array(bbox)
                    h = float(pts[:, 1].max() - pts[:, 1].min())
                    heights.append(h)
                except Exception:
                    continue
            return np.mean(heights) if heights else 0.0

        orig_h = avg_height(orig_boxes)
        trans_h = avg_height(trans_boxes)

        if orig_h == 0 or trans_h == 0:
            return 80.0, []

        ratio = min(orig_h, trans_h) / max(orig_h, trans_h)
        score = ratio * 100

        if ratio < 0.6:
            issues.append(
                f"Significant font size difference: original avg height {orig_h:.1f}px vs translated {trans_h:.1f}px"
            )
        elif ratio < 0.8:
            issues.append(f"Moderate font size difference detected")

        return round(score, 2), issues

    def compute_contrast_ratio(self, image_path: str) -> Tuple[float, List[str]]:
        """Compute contrast ratio of the image."""
        issues = []
        img = _load_image(image_path)
        if img is None:
            return 70.0, ["Could not load image for contrast check"]

        gray = _to_gray(img)
        p2 = float(np.percentile(gray, 2))
        p98 = float(np.percentile(gray, 98))

        dynamic_range = p98 - p2
        score = min(100.0, (dynamic_range / 255) * 100)

        if dynamic_range < 50:
            issues.append(f"Low contrast image (dynamic range: {dynamic_range:.0f})")
        elif dynamic_range < 100:
            issues.append(f"Moderate contrast (dynamic range: {dynamic_range:.0f})")

        return round(score, 2), issues

    def generate_difference_heatmap(
        self, original_path: str, translated_path: str
    ) -> Optional[np.ndarray]:
        """Generate a heatmap highlighting differences between images."""
        orig = _load_image(original_path)
        trans = _load_image(translated_path)
        if orig is None or trans is None:
            return None

        try:
            import cv2
            h = min(orig.shape[0], trans.shape[0])
            w = min(orig.shape[1], trans.shape[1])
            orig_r = cv2.resize(orig, (w, h))
            trans_r = cv2.resize(trans, (w, h))

            orig_g = _to_gray(orig_r).astype(float)
            trans_g = _to_gray(trans_r).astype(float)

            diff = np.abs(orig_g - trans_g).astype(np.uint8)
            heatmap = cv2.applyColorMap(diff, cv2.COLORMAP_JET)
            return heatmap
        except Exception as e:
            logger.error(f"Heatmap generation failed: {e}")
            return None
