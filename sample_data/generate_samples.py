#!/usr/bin/env python3
"""
Generate synthetic sample screenshots for TransLingo QA Studio testing.

Creates:
  sample_data/
    Original/    image001.png … image010.png
    Google/      image001.png … image010.png
    Papago/      image001.png … image010.png
    Samsung/     image001.png … image010.png
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

SAMPLE_DIR = Path(__file__).parent

ORIGINALS = [
    ("Settings", "Language", "Display", "Notifications", "Privacy", "Security",
     "Accounts", "Storage", "Battery", "About"),
    ("Search settings", "Search…", "Quick settings", "Device info",
     "Connected devices", "Apps", "Wallpaper", "Lock screen", "Accessibility",
     "Digital Wellbeing"),
]

TRANSLATIONS = {
    "Google": [
        ("설정", "언어", "디스플레이", "알림", "개인 정보", "보안",
         "계정", "저장소", "배터리", "정보"),
        ("설정 검색", "검색…", "빠른 설정", "기기 정보",
         "연결된 기기", "앱", "배경화면", "잠금 화면", "접근성",
         "디지털 웰빙"),
    ],
    "Papago": [
        ("설정", "언어", "화면", "알림", "프라이버시", "보안",
         "계정", "저장공간", "배터리", "정보"),
        ("설정 검색", "검색…", "빠른 설정", "기기 정보",
         "연결된 장치", "앱", "바탕 화면", "잠금 화면", "접근성",
         "디지털 건강"),
    ],
    "Samsung": [
        ("설정", "언어 및 입력", "화면", "알림", "보안 및 개인정보",
         "잠금화면", "계정", "저장공간", "배터리 및 기기케어", "휴대전화 정보"),
        ("설정 검색", "Search…", "빠른 패널", "기기 정보",
         "연결", "앱", "배경화면 및 스타일", "잠금화면", "접근성",
         "디지털 웰빙 및 자녀 보호"),
    ],
}


def make_ui_screenshot(
    items: tuple,
    title: str = "Settings",
    bg_color: tuple = (30, 30, 40),
    accent: tuple = (59, 130, 246),
    width: int = 400,
    height: int = 720,
    blur: bool = False,
    artifact: bool = False,
) -> Image.Image:
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_item = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except Exception:
        font_title = ImageFont.load_default()
        font_item = font_title
        font_small = font_title

    # Status bar
    draw.rectangle([0, 0, width, 28], fill=(20, 20, 30))
    draw.text((10, 6), "9:41", fill=(220, 220, 220), font=font_small)
    draw.text((width - 50, 6), "100%", fill=(220, 220, 220), font=font_small)

    # Title bar
    draw.rectangle([0, 28, width, 72], fill=(25, 35, 55))
    draw.text((16, 38), title, fill=(255, 255, 255), font=font_title)

    # Search bar
    draw.rectangle([12, 80, width - 12, 110], fill=(45, 55, 75), outline=(70, 90, 120))
    draw.text((24, 89), "Search…", fill=(120, 130, 150), font=font_item)

    # List items
    y = 128
    for i, item in enumerate(items):
        if y + 52 > height - 20:
            break
        is_selected = (i == 2)
        bg = (40, 60, 100) if is_selected else (35, 45, 65)
        draw.rectangle([0, y, width, y + 48], fill=bg)

        icon_color = accent if is_selected else (80, 100, 130)
        draw.rectangle([14, y + 12, 38, y + 36], fill=icon_color, outline=icon_color)

        draw.text((52, y + 14), item, fill=(230, 235, 245) if is_selected else (200, 210, 225),
                  font=font_item)

        draw.rectangle([0, y + 47, width, y + 48], fill=(45, 55, 70))
        y += 52

    # Bottom bar
    draw.rectangle([0, height - 40, width, height], fill=(20, 25, 40))

    if artifact:
        import random
        rng = random.Random(42)
        for _ in range(30):
            x = rng.randint(0, width - 5)
            yy = rng.randint(0, height - 5)
            r = rng.randint(2, 8)
            draw.ellipse([x, yy, x + r, yy + r], fill=(200, 50, 50))

    if blur:
        try:
            from PIL import ImageFilter
            img = img.filter(ImageFilter.GaussianBlur(3))
        except Exception:
            pass

    return img


def generate_all(n_images: int = 10) -> None:
    engines = list(TRANSLATIONS.keys())
    subdirs = ["Original"] + engines

    for sub in subdirs:
        (SAMPLE_DIR / sub).mkdir(exist_ok=True)

    print(f"Generating {n_images} image sets…")

    for idx in range(n_images):
        group = idx % len(ORIGINALS)
        orig_items = ORIGINALS[group]
        img_name = f"image{idx + 1:03d}.png"

        # Original (English)
        orig_img = make_ui_screenshot(
            orig_items, title="Settings",
            bg_color=(30, 30, 40), accent=(59, 130, 246)
        )
        orig_img.save(str(SAMPLE_DIR / "Original" / img_name))

        for engine in engines:
            trans_items = TRANSLATIONS[engine][group]
            blur = (engine == "Samsung" and idx % 5 == 0)
            artifact = (engine == "Google" and idx % 7 == 0)
            trans_img = make_ui_screenshot(
                trans_items, title=trans_items[0],
                bg_color=(28, 32, 45), accent=(99, 102, 241),
                blur=blur, artifact=artifact,
            )
            trans_img.save(str(SAMPLE_DIR / engine / img_name))

        print(f"  [✓] {img_name}")

    print(f"\nSample data generated in: {SAMPLE_DIR}")
    print("\nFolder structure:")
    for sub in subdirs:
        files = list((SAMPLE_DIR / sub).glob("*.png"))
        print(f"  {sub}/  ({len(files)} images)")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate sample images for TransLingo QA Studio")
    parser.add_argument("-n", "--count", type=int, default=10, help="Number of images to generate")
    args = parser.parse_args()
    generate_all(args.count)
