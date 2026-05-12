# =====================================================================
#  IMAGE OVERLAY SERVICE
#  Adds text overlays (e.g. "SHOP NOW") to images using Pillow.
# =====================================================================

import os
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont


# ── Font Discovery ──────────────────────────────────────────────────
# Try common bold fonts shipped on Windows / macOS / Linux. Falls back
# to PIL's default bitmap font if none are found.

_FONT_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\impact.ttf",
    r"C:\Windows\Fonts\Arial Bold.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    # Linux (Debian/Ubuntu)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def _load_font(size: int) -> ImageFont.ImageFont:
    """Returns a bold TrueType font at the requested size, or PIL's default."""
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    print("[WARN] No bold TrueType font found — using PIL default (text may be small).")
    return ImageFont.load_default()


def _measure_text(draw: ImageDraw.ImageDraw, text: str,
                  font: ImageFont.ImageFont) -> tuple[int, int]:
    """Returns the (width, height) of `text` as it will be rendered."""
    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right - left, bottom - top
    except AttributeError:
        # Pillow < 8 fallback
        return draw.textsize(text, font=font)


# ── Public API ──────────────────────────────────────────────────────

def add_bottom_center_text(
    input_path: str,
    output_path: str,
    text: str = "SHOP NOW",
    *,
    text_color: tuple = (255, 255, 255, 255),
    stroke_color: tuple = (0, 0, 0, 255),
    width_ratio: float = 0.55,
    bottom_padding_ratio: float = 0.06,
    stroke_ratio: float = 0.06,
) -> str | None:
    """
    Renders `text` centered along the bottom of the image at `input_path`
    and writes the result to `output_path`. Returns `output_path` on
    success or None on failure.

    The text is auto-scaled so it occupies roughly `width_ratio` of the
    image width, with a contrasting outline for readability on any
    background. `bottom_padding_ratio` controls the gap between the text
    baseline and the bottom edge (as a fraction of image height).
    """
    if not os.path.exists(input_path):
        print(f"[ERROR] Overlay source missing: {input_path}")
        return None

    try:
        with Image.open(input_path) as src:
            base = src.convert("RGBA")
    except Exception as e:
        print(f"[ERROR] Could not open image for overlay: {e}")
        return None

    img_w, img_h = base.size
    target_text_w = max(1, int(img_w * width_ratio))

    # ── Binary-search a font size that fits the target width ──
    draw_probe = ImageDraw.Draw(base)
    lo, hi = 10, max(20, img_h)  # font size in px
    best_font = _load_font(lo)
    while lo <= hi:
        mid = (lo + hi) // 2
        font = _load_font(mid)
        text_w, _ = _measure_text(draw_probe, text, font)
        if text_w <= target_text_w:
            best_font = font
            lo = mid + 1
        else:
            hi = mid - 1

    text_w, text_h = _measure_text(draw_probe, text, best_font)
    font_px = getattr(best_font, "size", max(text_h, 12))
    stroke_w = max(2, int(font_px * stroke_ratio))

    x = (img_w - text_w) // 2
    y = img_h - text_h - int(img_h * bottom_padding_ratio) - stroke_w

    # ── Draw onto a transparent overlay so we can composite cleanly ──
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    try:
        overlay_draw.text(
            (x, y),
            text,
            font=best_font,
            fill=text_color,
            stroke_width=stroke_w,
            stroke_fill=stroke_color,
        )
    except TypeError:
        # Pillow < 8.0 has no stroke kwargs — emulate with neighbor draws
        for dx in range(-stroke_w, stroke_w + 1):
            for dy in range(-stroke_w, stroke_w + 1):
                if dx or dy:
                    overlay_draw.text((x + dx, y + dy), text,
                                      font=best_font, fill=stroke_color)
        overlay_draw.text((x, y), text, font=best_font, fill=text_color)

    out = Image.alpha_composite(base, overlay)

    # ── Save in the original format where possible ──
    ext = os.path.splitext(output_path)[1].lower()
    try:
        if ext in {".jpg", ".jpeg"}:
            out.convert("RGB").save(output_path, "JPEG", quality=95)
        else:
            out.save(output_path)
        print(f"[OK] SHOP NOW overlay written: {output_path}")
        return output_path
    except Exception as e:
        print(f"[ERROR] Saving overlay image: {e}")
        return None
    finally:
        out.close()


def make_shop_now_image(input_path: str, record_id: str,
                        text: str = "SHOP NOW") -> str | None:
    """Convenience wrapper used by the pipeline."""
    filename = f"{record_id}_shop_now.png"
    output_path = os.path.join(tempfile.gettempdir(), filename)
    return add_bottom_center_text(input_path, output_path, text=text)
