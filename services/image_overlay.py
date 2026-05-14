# =====================================================================
#  IMAGE OVERLAY SERVICE
#  Adds text overlays (e.g. "SHOP NOW") and brand watermarks to images
#  using Pillow.
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


# Regular-weight font fallbacks for the lighter "Home" line of the
# brand watermark. Falls through to bold if no regular font is found.
_REGULAR_FONT_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]


def _load_font(size: int, *, bold: bool = True) -> ImageFont.ImageFont:
    """Returns a TrueType font at the requested size, or PIL's default.

    When ``bold`` is False, prefers a regular-weight font and falls
    back to the bold list if no regular font is available.
    """
    candidates = _FONT_CANDIDATES if bold else _REGULAR_FONT_CANDIDATES + _FONT_CANDIDATES
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    print("[WARN] No suitable TrueType font found — using PIL default (text may be small).")
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
    """Convenience wrapper used by the pipeline.

    Writes the overlay as a high-quality JPEG so the resulting file
    stays comfortably under Airtable's 5 MB direct-upload limit (the
    Blended Image is typically ~6 MB as PNG; the same content as JPEG
    quality 95 is ~1 MB).
    """
    filename = f"{record_id}_shop_now.jpg"
    output_path = os.path.join(tempfile.gettempdir(), filename)
    return add_bottom_center_text(input_path, output_path, text=text)


# ── Brand Watermark ─────────────────────────────────────────────────

def _render_brand_watermark(
    box_size: int,
    line1: str = "Home",
    line2: str = "Cartel",
) -> Image.Image:
    """Renders the default "Home / Cartel" black-square logo at the
    requested pixel size. Returns an RGBA image.

    Layout:
      - Solid black background.
      - ``line1`` (lighter, smaller) sits in the upper third.
      - ``line2`` (bold, larger) sits in the lower two thirds.
    Both lines are horizontally centered and white.
    """
    box_size = max(40, int(box_size))
    badge = Image.new("RGBA", (box_size, box_size), (0, 0, 0, 255))
    draw = ImageDraw.Draw(badge)

    # ── Pick font sizes that fit the box with comfortable padding ──
    h_padding = max(2, int(box_size * 0.10))
    inner_w = box_size - 2 * h_padding

    def _fit(text: str, target_w: int, bold: bool) -> ImageFont.ImageFont:
        lo, hi = 6, max(8, box_size)
        best = _load_font(lo, bold=bold)
        while lo <= hi:
            mid = (lo + hi) // 2
            font = _load_font(mid, bold=bold)
            w, _ = _measure_text(draw, text, font)
            if w <= target_w:
                best = font
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    font1 = _fit(line1, int(inner_w * 0.70), bold=False)
    font2 = _fit(line2, inner_w, bold=True)

    w1, h1 = _measure_text(draw, line1, font1)
    w2, h2 = _measure_text(draw, line2, font2)

    # Stack the two lines vertically with a small gap, centered as a
    # block within the badge.
    gap = max(2, int(box_size * 0.04))
    block_h = h1 + gap + h2
    y_start = (box_size - block_h) // 2

    x1 = (box_size - w1) // 2
    x2 = (box_size - w2) // 2
    draw.text((x1, y_start), line1, font=font1, fill=(255, 255, 255, 255))
    draw.text((x2, y_start + h1 + gap), line2, font=font2,
              fill=(255, 255, 255, 255))

    return badge


def _load_watermark(
    box_size: int,
    watermark_path: str | None = None,
    line1: str = "Home",
    line2: str = "Cartel",
) -> Image.Image:
    """Loads the brand watermark.

    If ``watermark_path`` points at an existing image, it is opened,
    converted to RGBA, and resized so its longest edge equals
    ``box_size``. Otherwise the watermark is rendered programmatically
    via ``_render_brand_watermark``.
    """
    if watermark_path and os.path.isfile(watermark_path):
        try:
            with Image.open(watermark_path) as wm_src:
                wm = wm_src.convert("RGBA")
            scale = box_size / max(wm.size)
            new_size = (max(1, int(wm.size[0] * scale)),
                        max(1, int(wm.size[1] * scale)))
            return wm.resize(new_size, Image.LANCZOS)
        except Exception as e:
            print(f"[WARN] Could not load watermark '{watermark_path}': {e}. "
                  "Falling back to programmatic render.")

    return _render_brand_watermark(box_size, line1=line1, line2=line2)


def _resolve_position(
    position: str,
    img_w: int,
    img_h: int,
    wm_w: int,
    wm_h: int,
    h_padding: int,
    v_padding: int,
) -> tuple[int, int]:
    """Returns the (x, y) top-left coordinates for a watermark.

    ``position`` is one of: top-left, top-center, top-right,
    bottom-left, bottom-center, bottom-right, center.
    """
    pos = (position or "top-center").strip().lower().replace("_", "-")
    parts = pos.split("-")

    vert = parts[0] if parts else "top"
    horiz = parts[1] if len(parts) > 1 else "center"

    if pos == "center":
        vert, horiz = "center", "center"

    if horiz == "left":
        x = h_padding
    elif horiz == "right":
        x = img_w - wm_w - h_padding
    else:  # center
        x = (img_w - wm_w) // 2

    if vert == "top":
        y = v_padding
    elif vert == "bottom":
        y = img_h - wm_h - v_padding
    else:  # center
        y = (img_h - wm_h) // 2

    return x, y


def add_watermark(
    input_path: str,
    output_path: str,
    *,
    watermark_path: str | None = None,
    line1: str = "Home",
    line2: str = "Cartel",
    width_ratio: float = 0.10,
    position: str = "top-center",
    horizontal_padding_ratio: float = 0.03,
    vertical_padding_ratio: float = 0.0,
    opacity: float = 1.0,
    jpeg_quality: int = 95,
) -> str | None:
    """Composites a brand watermark onto ``input_path`` and writes the
    result to ``output_path``. Returns ``output_path`` on success or
    None on failure.

    The watermark is auto-sized so its width equals ``width_ratio`` of
    the image width.
    """
    if not os.path.exists(input_path):
        print(f"[ERROR] Watermark source missing: {input_path}")
        return None

    try:
        with Image.open(input_path) as src:
            base = src.convert("RGBA")
    except Exception as e:
        print(f"[ERROR] Could not open image for watermark: {e}")
        return None

    img_w, img_h = base.size
    box_size = max(32, int(img_w * width_ratio))

    watermark = _load_watermark(box_size, watermark_path=watermark_path,
                                line1=line1, line2=line2)

    # Apply opacity if requested.
    if opacity < 1.0:
        alpha = watermark.split()[-1].point(lambda v: int(v * opacity))
        watermark.putalpha(alpha)

    wm_w, wm_h = watermark.size
    h_pad = int(img_w * horizontal_padding_ratio)
    v_pad = int(img_h * vertical_padding_ratio)
    x, y = _resolve_position(position, img_w, img_h, wm_w, wm_h, h_pad, v_pad)

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    overlay.paste(watermark, (x, y), watermark)
    out = Image.alpha_composite(base, overlay)

    ext = os.path.splitext(output_path)[1].lower()
    try:
        if ext in {".jpg", ".jpeg"}:
            out.convert("RGB").save(output_path, "JPEG", quality=jpeg_quality)
        else:
            out.save(output_path)
        print(f"[OK] Brand watermark written: {output_path}")
        return output_path
    except Exception as e:
        print(f"[ERROR] Saving watermarked image: {e}")
        return None
    finally:
        out.close()


def make_watermarked_image(
    input_path: str,
    record_id: str,
    *,
    output_basename: str | None = None,
    extension: str = ".jpg",
    watermark_path: str | None = None,
    line1: str = "Home",
    line2: str = "Cartel",
    width_ratio: float = 0.10,
    position: str = "top-center",
    horizontal_padding_ratio: float = 0.03,
    vertical_padding_ratio: float = 0.0,
    opacity: float = 1.0,
    jpeg_quality: int = 95,
) -> str | None:
    """Pipeline-friendly wrapper around :func:`add_watermark`.

    Writes the watermarked image to the system temp directory using a
    deterministic filename derived from ``record_id`` and returns its
    path (or ``None`` on failure). Defaults to JPEG quality 95 so the
    output stays under Airtable's 5 MB direct-upload ceiling for
    typical Kie.ai blends.
    """
    basename = output_basename or f"{record_id}_blended_wm"
    filename = f"{basename}{extension}"
    output_path = os.path.join(tempfile.gettempdir(), filename)
    return add_watermark(
        input_path,
        output_path,
        watermark_path=watermark_path,
        line1=line1,
        line2=line2,
        width_ratio=width_ratio,
        position=position,
        horizontal_padding_ratio=horizontal_padding_ratio,
        vertical_padding_ratio=vertical_padding_ratio,
        opacity=opacity,
        jpeg_quality=jpeg_quality,
    )
