"""
Finger Removal Analyzer.

Detects skin-colored regions in the border margins of a document scan
to identify if fingers are intruding into the image frame.
"""

import numpy as np
import cv2


class FingerRemovalAnalyzer:
    """
    Analyzes a scanned document image to detect finger intrusion in border regions.

    Fingers are typically present at the edges of scanned documents when users
    hold the document flat against a scanner bed. This analyzer checks a 20%
    border margin for skin-colored blobs using HSV color space.
    """

    # HSV ranges that capture human skin tones across various ethnicities
    SKIN_H_LOW1 = 0
    SKIN_H_HIGH1 = 20
    SKIN_H_LOW2 = 170
    SKIN_H_HIGH2 = 180
    SKIN_S_LOW = 20
    SKIN_S_HIGH = 255
    SKIN_V_LOW = 70
    SKIN_V_HIGH = 255

    # Border margin fraction to inspect
    MARGIN_FRACTION = 0.20

    # Minimum contour area as fraction of total image area to be considered a blob
    MIN_BLOB_FRACTION = 0.005  # 0.5%

    def analyze(self, image: np.ndarray) -> dict:
        """
        Analyze an image for finger presence in the border region.

        Args:
            image: BGR numpy array (H, W, 3). Grayscale images are converted.

        Returns:
            dict with keys:
                passed (bool): True if score >= 70 (acceptable finger removal).
                score (float): 0-100 numeric score.
                confidence (float): 0-1 confidence in the result.
                details (dict): Breakdown info including skin_ratio, blob_count.
                visualization (np.ndarray): BGR image with annotations.
        """
        try:
            img = self._ensure_bgr(image)
            h, w = img.shape[:2]

            # Build the border mask (20% margin)
            border_mask = self._build_border_mask(h, w)

            # Detect skin in the border region
            skin_mask = self._detect_skin(img)
            border_skin_mask = cv2.bitwise_and(skin_mask, border_mask)

            # Find contours of significant skin blobs
            total_area = h * w
            contours, _ = cv2.findContours(
                border_skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            significant_contours = [
                c for c in contours
                if cv2.contourArea(c) > total_area * self.MIN_BLOB_FRACTION
            ]

            skin_pixel_count = int(np.sum(border_skin_mask > 0))
            skin_ratio = skin_pixel_count / total_area  # fraction of full image

            score = self._compute_score(skin_ratio)
            confidence = self._compute_confidence(skin_ratio)
            passed = score >= 70

            details = {
                "skin_ratio": round(skin_ratio, 4),
                "skin_pixel_count": skin_pixel_count,
                "significant_blob_count": len(significant_contours),
                "image_area": total_area,
                "margin_fraction": self.MARGIN_FRACTION,
            }

            visualization = self._build_visualization(
                img, border_mask, border_skin_mask, significant_contours
            )

            return {
                "passed": passed,
                "score": round(score, 2),
                "confidence": round(confidence, 3),
                "details": details,
                "visualization": visualization,
            }

        except Exception as exc:
            blank = image.copy() if image is not None else np.zeros((100, 100, 3), dtype=np.uint8)
            return {
                "passed": False,
                "score": 0.0,
                "confidence": 0.0,
                "details": {"error": str(exc)},
                "visualization": blank,
            }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_bgr(self, image: np.ndarray) -> np.ndarray:
        """Convert grayscale to BGR if necessary."""
        if image.ndim == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        return image.copy()

    def _build_border_mask(self, h: int, w: int) -> np.ndarray:
        """Create a binary mask covering only the border margin."""
        mask = np.zeros((h, w), dtype=np.uint8)
        mh = int(h * self.MARGIN_FRACTION)
        mw = int(w * self.MARGIN_FRACTION)
        # Top band
        mask[:mh, :] = 255
        # Bottom band
        mask[h - mh:, :] = 255
        # Left band
        mask[:, :mw] = 255
        # Right band
        mask[:, w - mw:] = 255
        return mask

    def _detect_skin(self, bgr_image: np.ndarray) -> np.ndarray:
        """Return binary mask of skin-colored pixels."""
        hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)

        lower1 = np.array([self.SKIN_H_LOW1, self.SKIN_S_LOW, self.SKIN_V_LOW])
        upper1 = np.array([self.SKIN_H_HIGH1, self.SKIN_S_HIGH, self.SKIN_V_HIGH])
        mask1 = cv2.inRange(hsv, lower1, upper1)

        lower2 = np.array([self.SKIN_H_LOW2, self.SKIN_S_LOW, self.SKIN_V_LOW])
        upper2 = np.array([self.SKIN_H_HIGH2, self.SKIN_S_HIGH, self.SKIN_V_HIGH])
        mask2 = cv2.inRange(hsv, lower2, upper2)

        skin_mask = cv2.bitwise_or(mask1, mask2)

        # Morphological cleanup to remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_DILATE, kernel)
        return skin_mask

    def _compute_score(self, skin_ratio: float) -> float:
        """
        Compute 0-100 score based on how much skin is in the border.
          skin_ratio < 2%  -> 95-100
          skin_ratio < 5%  -> 70-95
          otherwise        -> drops toward 0
        """
        if skin_ratio < 0.02:
            # Linearly map [0, 0.02) → [100, 95]
            score = 100 - (skin_ratio / 0.02) * 5
        elif skin_ratio < 0.05:
            # Linearly map [0.02, 0.05) → [95, 70]
            score = 95 - ((skin_ratio - 0.02) / 0.03) * 25
        else:
            # Drops steeply from 70 to 0 as skin_ratio → 0.20+
            score = max(0.0, 70 - ((skin_ratio - 0.05) / 0.15) * 70)
        return float(score)

    def _compute_confidence(self, skin_ratio: float) -> float:
        """
        Compute confidence in the detection.
        Formula: min(0.95, abs(skin_ratio - 0.05) * 10 + 0.5), clamped [0.5, 0.95].
        """
        raw = abs(skin_ratio - 0.05) * 10 + 0.5
        return float(max(0.5, min(0.95, raw)))

    def _build_visualization(
        self,
        img: np.ndarray,
        border_mask: np.ndarray,
        skin_mask: np.ndarray,
        contours: list,
    ) -> np.ndarray:
        """
        Annotate the image:
          - Green tint on border margin.
          - Red contours on significant skin blobs.
        """
        vis = img.copy()

        # Apply a subtle green tint to the border margin
        green_overlay = vis.copy()
        green_overlay[border_mask > 0] = (
            green_overlay[border_mask > 0] * 0.6 + np.array([0, 80, 0], dtype=np.float32)
        ).clip(0, 255).astype(np.uint8)
        cv2.addWeighted(green_overlay, 0.4, vis, 0.6, 0, vis)

        # Draw red contours around detected skin blobs
        cv2.drawContours(vis, contours, -1, (0, 0, 255), 2)

        # Label the image
        label = f"Skin in border: {int(np.sum(skin_mask > 0))} px"
        cv2.putText(
            vis, label, (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA
        )
        return vis
