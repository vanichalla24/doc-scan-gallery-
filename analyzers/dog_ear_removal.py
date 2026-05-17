"""
Dog-ear Removal Analyzer.

Detects folded corner artifacts (dog-ears) in scanned document images.
A dog-ear appears as a dark triangular region in one or more corners of the page.
"""

import numpy as np
import cv2


class DogEarRemovalAnalyzer:
    """
    Analyzes a scanned document image for dog-ear (folded corner) artifacts.

    Each of the four corners is inspected independently. A dog-ear is flagged
    when a sufficiently large triangular dark region is found in that corner.
    """

    # Fraction of image dimensions used for the corner inspection region
    CORNER_FRACTION = 0.15

    # Minimum contour area as fraction of total image area
    MIN_CONTOUR_FRACTION = 0.003  # 0.3%

    # approxPolyDP epsilon as fraction of contour perimeter
    POLY_EPSILON_FRACTION = 0.04

    # Number of vertices for a triangle
    TRIANGLE_VERTICES = 3

    def analyze(self, image: np.ndarray) -> dict:
        """
        Analyze an image for dog-ear artifacts in its four corners.

        Args:
            image: BGR numpy array (H, W, 3). Grayscale images are converted.

        Returns:
            dict with keys:
                passed (bool): True if score > 0 (no severe dog-ears).
                score (float): 100 - 25 * num_dog_ears, clamped to [0, 100].
                confidence (float): 0.75-0.85 depending on clarity of detections.
                details (dict): Per-corner findings and overall counts.
                visualization (np.ndarray): BGR image with dog-ear regions highlighted.
        """
        try:
            img = self._ensure_bgr(image)
            h, w = img.shape[:2]

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            total_area = h * w
            corner_h = int(h * self.CORNER_FRACTION)
            corner_w = int(w * self.CORNER_FRACTION)

            corners = {
                "top_left":     (0,         0,         corner_h, corner_w),
                "top_right":    (0,         w - corner_w, corner_h, w),
                "bottom_left":  (h - corner_h, 0,       h,        corner_w),
                "bottom_right": (h - corner_h, w - corner_w, h,   w),
            }

            dog_ears = []
            corner_results = {}
            clear_triangles = 0
            ambiguous = 0

            vis = img.copy()

            for corner_name, (r0, c0, r1, c1) in corners.items():
                region = thresh[r0:r1, c0:c1]
                contours, _ = cv2.findContours(
                    region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )

                found_dog_ear = False
                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if area < total_area * self.MIN_CONTOUR_FRACTION:
                        continue

                    peri = cv2.arcLength(cnt, True)
                    approx = cv2.approxPolyDP(cnt, self.POLY_EPSILON_FRACTION * peri, True)

                    if len(approx) == self.TRIANGLE_VERTICES:
                        found_dog_ear = True
                        clear_triangles += 1
                        # Offset contour back to full-image coordinates for visualization
                        offset_cnt = cnt + np.array([[[c0, r0]]])
                        # Draw orange rectangle around the corner region
                        cv2.rectangle(vis, (c0, r0), (c1, r1), (0, 140, 255), 3)
                        cv2.putText(
                            vis,
                            f"Dog-ear: {corner_name.replace('_', ' ')}",
                            (c0 + 4, r0 + 20 if r0 == 0 else r1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (0, 140, 255),
                            2,
                            cv2.LINE_AA,
                        )
                        cv2.drawContours(vis, [offset_cnt], -1, (0, 80, 255), 2)
                        break
                    elif len(approx) in (4, 5):
                        # Quadrilateral in corner could be ambiguous folded corner
                        if area > total_area * self.MIN_CONTOUR_FRACTION * 2:
                            ambiguous += 1

                corner_results[corner_name] = found_dog_ear
                if found_dog_ear:
                    dog_ears.append(corner_name)

            num_dog_ears = len(dog_ears)
            score = float(max(0, 100 - num_dog_ears * 25))
            passed = score > 0  # any dog-ear is a failure

            # Confidence: start at 0.80, nudge based on evidence clarity
            confidence = 0.80
            if clear_triangles > 0:
                confidence = min(0.85, confidence + 0.05 * clear_triangles)
            if ambiguous > 0:
                confidence = max(0.75, confidence - 0.05)

            details = {
                "num_dog_ears": num_dog_ears,
                "dog_ear_corners": dog_ears,
                "corner_results": corner_results,
                "clear_triangle_count": clear_triangles,
                "ambiguous_count": ambiguous,
            }

            return {
                "passed": passed,
                "score": round(score, 2),
                "confidence": round(confidence, 3),
                "details": details,
                "visualization": vis,
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
        """Convert grayscale or BGRA to BGR."""
        if image.ndim == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        return image.copy()
