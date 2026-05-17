"""
Warp Correction Analyzer.

Detects perspective distortion in scanned document images by finding the
largest 4-point polygon and measuring how close its interior angles are to 90°.
Falls back to Hough line angle analysis if no clear quadrilateral is found.
"""

import numpy as np
import cv2


class WarpCorrectionAnalyzer:
    """
    Analyzes a scanned document image for perspective warp distortion.

    The analyzer tries to locate the document boundary as a quadrilateral and
    measures angle deviation from perfect right angles. High deviation means
    the scan was not de-warped (or de-warping failed).
    """

    # Canny edge detection thresholds
    CANNY_LOW = 50
    CANNY_HIGH = 150

    # approxPolyDP epsilon fraction of perimeter
    POLY_EPSILON_FRACTION = 0.02

    # Minimum quad area as fraction of image area to be considered the document
    MIN_QUAD_AREA_FRACTION = 0.10

    # HoughLinesP parameters for fallback
    HOUGH_RHO = 1
    HOUGH_THETA = np.pi / 180
    HOUGH_THRESHOLD = 80
    HOUGH_MIN_LINE_LEN = 50
    HOUGH_MAX_LINE_GAP = 10

    def analyze(self, image: np.ndarray) -> dict:
        """
        Analyze an image for perspective warp distortion.

        Args:
            image: BGR numpy array. Grayscale images are handled automatically.

        Returns:
            dict with keys:
                passed (bool): True if score >= 80.
                score (float): 0-100 based on angle deviation from 90°.
                confidence (float): 0-1.
                details (dict): angle_deviation, quad_found, corner_angles, etc.
                visualization (np.ndarray): BGR image with annotations.
        """
        try:
            img = self._ensure_bgr(image)
            h, w = img.shape[:2]

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, self.CANNY_LOW, self.CANNY_HIGH)

            vis = img.copy()
            quad, angle_deviation, corner_angles, method = self._find_document_quad(
                edges, h, w
            )

            if quad is not None:
                score = max(0.0, 100.0 - angle_deviation * 2.0)
                confidence = 0.85
                cv2.drawContours(vis, [quad], -1, (255, 80, 0), 3)
                self._annotate_corners(vis, quad, corner_angles)
                method_used = "quad_detection"
            else:
                # Fallback: analyse line angle distribution
                angle_deviation, method_used = self._hough_line_analysis(edges)
                score = max(0.0, 100.0 - angle_deviation * 2.0)
                confidence = 0.65
                corner_angles = []

            passed = score >= 80.0

            # Draw score on image
            cv2.putText(
                vis,
                f"Warp score: {score:.1f}  method: {method_used}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 80, 0),
                2,
                cv2.LINE_AA,
            )

            details = {
                "score": round(score, 2),
                "angle_deviation": round(float(angle_deviation), 3),
                "method": method_used,
                "quad_found": quad is not None,
                "corner_angles": [round(float(a), 2) for a in corner_angles],
                "image_size": (h, w),
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
        if image.ndim == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        return image.copy()

    def _find_document_quad(self, edges: np.ndarray, h: int, w: int):
        """
        Find the largest 4-point contour approximating the document boundary.

        Returns (quad, angle_deviation, corner_angles, method) or
                (None, 0.0, [], 'none') if not found.
        """
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, 0.0, [], "none"

        # Sort by area descending
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        total_area = h * w

        for cnt in contours[:5]:
            area = cv2.contourArea(cnt)
            if area < total_area * self.MIN_QUAD_AREA_FRACTION:
                break

            hull = cv2.convexHull(cnt)
            peri = cv2.arcLength(hull, True)
            approx = cv2.approxPolyDP(hull, self.POLY_EPSILON_FRACTION * peri, True)

            if len(approx) == 4:
                pts = approx.reshape(4, 2).astype(np.float32)
                corner_angles = self._compute_corner_angles(pts)
                angle_deviation = float(np.mean(np.abs(np.array(corner_angles) - 90.0)))
                return approx, angle_deviation, corner_angles, "quad_detection"

        return None, 0.0, [], "none"

    def _compute_corner_angles(self, pts: np.ndarray) -> list:
        """
        Given 4 corners (sorted order), compute interior angle at each vertex.
        """
        # Order: TL, TR, BR, BL
        pts = self._order_points(pts)
        angles = []
        n = 4
        for i in range(n):
            p_prev = pts[(i - 1) % n]
            p_curr = pts[i]
            p_next = pts[(i + 1) % n]
            v1 = p_prev - p_curr
            v2 = p_next - p_curr
            cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
            cos_a = np.clip(cos_a, -1.0, 1.0)
            angles.append(float(np.degrees(np.arccos(cos_a))))
        return angles

    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        """Order 4 points as TL, TR, BR, BL."""
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]   # TL
        rect[2] = pts[np.argmax(s)]   # BR
        diff = np.diff(pts, axis=1).ravel()
        rect[1] = pts[np.argmin(diff)]  # TR
        rect[3] = pts[np.argmax(diff)]  # BL
        return rect

    def _hough_line_analysis(self, edges: np.ndarray):
        """
        Fallback: use HoughLinesP to get line angles and compute deviation
        from the dominant horizontal/vertical orientation.
        """
        lines = cv2.HoughLinesP(
            edges,
            self.HOUGH_RHO,
            self.HOUGH_THETA,
            self.HOUGH_THRESHOLD,
            minLineLength=self.HOUGH_MIN_LINE_LEN,
            maxLineGap=self.HOUGH_MAX_LINE_GAP,
        )

        if lines is None or len(lines) == 0:
            return 0.0, "hough_no_lines"

        line_angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            # Normalise to [-45, 45] by folding
            angle = angle % 90
            if angle > 45:
                angle -= 90
            line_angles.append(abs(angle))  # deviation from perfectly H or V

        if not line_angles:
            return 0.0, "hough_no_valid_lines"

        angle_deviation = float(np.mean(line_angles))
        return angle_deviation, "hough_lines"

    def _annotate_corners(self, vis: np.ndarray, quad: np.ndarray, angles: list):
        """Draw small circles and angle labels at each corner of the quad."""
        pts = quad.reshape(4, 2)
        labels = ["TL", "TR", "BR", "BL"]
        for i, (pt, angle) in enumerate(zip(pts, angles)):
            x, y = int(pt[0]), int(pt[1])
            cv2.circle(vis, (x, y), 8, (255, 80, 0), -1)
            offset_x = -50 if x > vis.shape[1] // 2 else 5
            offset_y = -10 if y > vis.shape[0] // 2 else 20
            cv2.putText(
                vis,
                f"{labels[i % len(labels)]}: {angle:.1f}deg",
                (x + offset_x, y + offset_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )
