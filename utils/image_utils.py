"""
Image utility functions for the Document Scanner Benchmark Tool.

Provides helpers for converting between PIL Images, OpenCV numpy arrays,
and Streamlit UploadedFile objects.
"""

import io
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def load_image(uploaded_file) -> np.ndarray:
    """
    Load a Streamlit UploadedFile into a BGR numpy array.

    Args:
        uploaded_file: A streamlit.runtime.uploaded_file_manager.UploadedFile object.

    Returns:
        np.ndarray: BGR image array with dtype uint8.

    Raises:
        ValueError: If the file cannot be decoded as an image.
    """
    if uploaded_file is None:
        raise ValueError("uploaded_file is None")

    raw_bytes = uploaded_file.read()
    pil_image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    return pil_to_cv2(pil_image)


def pil_to_cv2(img: Image.Image) -> np.ndarray:
    """
    Convert a PIL Image to a BGR numpy array (OpenCV format).

    Args:
        img: PIL Image in any mode. Will be converted to RGB first.

    Returns:
        np.ndarray: BGR uint8 array of shape (H, W, 3).
    """
    rgb = np.array(img.convert("RGB"), dtype=np.uint8)
    # Flip channels: RGB -> BGR
    bgr = rgb[:, :, ::-1].copy()
    return bgr


def cv2_to_pil(img: np.ndarray) -> Image.Image:
    """
    Convert an OpenCV BGR numpy array to a PIL Image (RGB).

    Args:
        img: np.ndarray of shape (H, W, 3) in BGR or (H, W) grayscale.

    Returns:
        PIL.Image.Image in RGB mode.
    """
    if img.ndim == 2:
        # Grayscale
        return Image.fromarray(img, mode="L").convert("RGB")

    if img.shape[2] == 4:
        # BGRA -> RGBA
        rgba = img[:, :, [2, 1, 0, 3]]
        return Image.fromarray(rgba, mode="RGBA").convert("RGB")

    # BGR -> RGB
    rgb = img[:, :, ::-1].copy()
    return Image.fromarray(rgb, mode="RGB")


def create_side_by_side(
    original: np.ndarray,
    annotated: np.ndarray,
    label1: str = "Original",
    label2: str = "Analyzed",
    label_height: int = 32,
    gap: int = 10,
    background_color: tuple = (240, 240, 240),
) -> Image.Image:
    """
    Combine two BGR images side-by-side with labels into a single PIL image.

    Both images are resized to the same height while preserving aspect ratio.
    A small gap and a label strip are added.

    Args:
        original: BGR numpy array – the unmodified scan.
        annotated: BGR numpy array – the result of analysis with overlays.
        label1: Caption for the left image.
        label2: Caption for the right image.
        label_height: Pixel height of the label strip below each image.
        gap: Pixel width of the gap between the two images.
        background_color: RGB tuple for the background.

    Returns:
        PIL.Image.Image: Side-by-side composite.
    """
    pil_orig = cv2_to_pil(original)
    pil_ann = cv2_to_pil(annotated)

    # Unify heights
    target_h = max(pil_orig.height, pil_ann.height)
    target_h = min(target_h, 600)  # cap for display

    def _resize_to_height(img: Image.Image, h: int) -> Image.Image:
        scale = h / img.height
        new_w = max(1, int(img.width * scale))
        return img.resize((new_w, h), Image.LANCZOS)

    pil_orig = _resize_to_height(pil_orig, target_h)
    pil_ann = _resize_to_height(pil_ann, target_h)

    total_w = pil_orig.width + gap + pil_ann.width
    total_h = target_h + label_height

    canvas = Image.new("RGB", (total_w, total_h), color=background_color)
    canvas.paste(pil_orig, (0, 0))
    canvas.paste(pil_ann, (pil_orig.width + gap, 0))

    draw = ImageDraw.Draw(canvas)

    # Try to use a reasonable font; fall back to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except (IOError, OSError):
        font = ImageFont.load_default()

    def _draw_label(text: str, x_center: int, y: int):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((x_center - tw // 2, y), text, fill=(30, 30, 30), font=font)

    _draw_label(label1, pil_orig.width // 2, target_h + 6)
    _draw_label(label2, pil_orig.width + gap + pil_ann.width // 2, target_h + 6)

    return canvas
