"""Unit tests for visual validator."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _create_test_image(path: str, color=(200, 200, 200), text: bool = False) -> str:
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (640, 480), color)
        if text:
            draw = ImageDraw.Draw(img)
            draw.rectangle([50, 50, 300, 100], fill=(0, 0, 0))
            draw.text((60, 60), "Test Translation Text", fill=(255, 255, 255))
        img.save(path)
        return path
    except ImportError:
        import struct, zlib

        def png_chunk(name, data):
            c = zlib.crc32(name + data) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + name + data + struct.pack(">I", c)

        w, h = 100, 100
        raw = b"".join(
            b"\x00" + bytes([color[0], color[1], color[2]] * w) for _ in range(h)
        )
        idat = zlib.compress(raw)
        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = png_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        idat_chunk = png_chunk(b"IDAT", idat)
        iend = png_chunk(b"IEND", b"")
        with open(path, "wb") as f:
            f.write(sig + ihdr + idat_chunk + iend)
        return path


class TestVisualValidator(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.orig_path = str(Path(self._tmp) / "orig.png")
        self.trans_path = str(Path(self._tmp) / "trans.png")
        _create_test_image(self.orig_path, (200, 200, 200))
        _create_test_image(self.trans_path, (195, 200, 205))

    def test_blur_detection_sharp_image(self):
        try:
            from app.core.visual_validator import VisualValidator
            vv = VisualValidator()
            score, issues = vv.detect_blur(self.orig_path)
            self.assertIsInstance(score, float)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 100.0)
        except ImportError:
            self.skipTest("OpenCV not available")

    def test_background_preservation(self):
        try:
            from app.core.visual_validator import VisualValidator
            vv = VisualValidator()
            score, issues = vv.check_background_preservation(
                self.orig_path, self.trans_path
            )
            self.assertIsInstance(score, float)
            self.assertGreater(score, 50.0)
        except ImportError:
            self.skipTest("OpenCV not available")

    def test_detect_cropping_same_size(self):
        try:
            from app.core.visual_validator import VisualValidator
            vv = VisualValidator()
            score, issues = vv.detect_cropping(self.orig_path, self.trans_path)
            self.assertGreater(score, 90.0)
        except ImportError:
            self.skipTest("OpenCV not available")

    def test_missing_image_returns_fallback(self):
        try:
            from app.core.visual_validator import VisualValidator
            vv = VisualValidator()
            score, issues = vv.detect_blur("/nonexistent/image.png")
            self.assertEqual(score, 50.0)
            self.assertTrue(len(issues) > 0)
        except ImportError:
            self.skipTest("OpenCV not available")

    def test_overflow_no_boxes(self):
        try:
            from app.core.visual_validator import VisualValidator
            vv = VisualValidator()
            score, issues = vv.detect_overflow(self.orig_path, [])
            self.assertEqual(score, 100.0)
        except ImportError:
            self.skipTest("OpenCV not available")

    def test_contrast_ratio(self):
        try:
            from app.core.visual_validator import VisualValidator
            vv = VisualValidator()
            score, issues = vv.compute_contrast_ratio(self.orig_path)
            self.assertIsInstance(score, float)
        except ImportError:
            self.skipTest("OpenCV not available")


if __name__ == "__main__":
    unittest.main(verbosity=2)
