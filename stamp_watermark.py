# =====================================================================
#  STAMP WATERMARK CLI
#  Standalone runner for the "Stamp HomeCartel watermark on the
#  Styled Photo" step from Phase 1. Lets you watermark any local image
#  with the same code path the pipeline uses, without touching Kie.ai,
#  Airtable, or Zoho.
#
#  Usage:
#      python stamp_watermark.py path/to/styled_photo.png
#      python stamp_watermark.py input.png -o branded.jpg
#      python stamp_watermark.py input.png --position bottom-right --width-ratio 0.12
#
#  Settings default to the BRAND_WATERMARK_* values from your .env
#  (same as the pipeline). CLI flags override individual settings for
#  one-off experiments.
# =====================================================================

import argparse
import os
import sys

# Ensure the project root is on sys.path so `services` is importable
# whether the script is run from the repo root or elsewhere.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv is optional for this script; if missing, just use
    # whatever is already in the environment.
    pass

from services.image_overlay import add_watermark


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _default_watermark_path() -> str | None:
    """Resolves the watermark PNG to composite.

    Order:
      1. BRAND_WATERMARK_PATH env var, if set and non-empty.
      2. Bundled assets/brand_watermark.png, if it exists.
      3. None — the overlay service then renders a "Home / Cartel"
         badge programmatically.
    """
    override = os.environ.get("BRAND_WATERMARK_PATH", "").strip()
    if override:
        return override
    bundled = os.path.join(PROJECT_ROOT, "assets", "brand_watermark.png")
    if os.path.isfile(bundled):
        return bundled
    return None


def _default_output_path(input_path: str) -> str:
    """Mirrors the pipeline's `_wm.jpg` naming convention."""
    base, _ = os.path.splitext(input_path)
    return f"{base}_wm.jpg"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stamp the HomeCartel brand watermark on a local image. "
            "Uses the same overlay code as Phase 1 of the pipeline."
        ),
    )
    parser.add_argument(
        "input",
        help="Path to the source image to watermark (PNG/JPG).",
    )
    parser.add_argument(
        "-o", "--output",
        help=(
            "Output path. Defaults to <input>_wm.jpg next to the input "
            "file. JPEG is recommended to keep the file under "
            "Airtable's 5 MB direct-upload ceiling."
        ),
    )
    parser.add_argument(
        "--watermark-path",
        default=None,
        help=(
            "Override BRAND_WATERMARK_PATH. Path to an RGBA PNG. If "
            "neither this nor the bundled asset is found, a 'Home / "
            "Cartel' badge is rendered programmatically."
        ),
    )
    parser.add_argument("--line1", default=None,
                        help="Top line of the programmatic badge (default 'Home').")
    parser.add_argument("--line2", default=None,
                        help="Bottom line of the programmatic badge (default 'Cartel').")
    parser.add_argument("--width-ratio", type=float, default=None,
                        help="Watermark width as a fraction of the image width (e.g. 0.10).")
    parser.add_argument("--position", default=None,
                        help=(
                            "Anchor: top-left, top-center, top-right, "
                            "bottom-left, bottom-center, bottom-right, or center."
                        ))
    parser.add_argument("--horizontal-padding-ratio", type=float, default=None,
                        help="Horizontal padding from the anchor edge (e.g. 0.03).")
    parser.add_argument("--vertical-padding-ratio", type=float, default=None,
                        help="Vertical padding from the anchor edge (e.g. 0.0).")
    parser.add_argument("--opacity", type=float, default=None,
                        help="0.0 = invisible, 1.0 = fully opaque.")
    parser.add_argument("--jpeg-quality", type=int, default=None,
                        help="JPEG quality 1-100 (default 95).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    input_path = os.path.abspath(args.input)
    if not os.path.isfile(input_path):
        print(f"[ERROR] Input image not found: {input_path}")
        return 2

    output_path = os.path.abspath(args.output or _default_output_path(input_path))
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    watermark_path = args.watermark_path or _default_watermark_path()
    line1 = args.line1 if args.line1 is not None else os.environ.get("BRAND_WATERMARK_LINE1", "Home")
    line2 = args.line2 if args.line2 is not None else os.environ.get("BRAND_WATERMARK_LINE2", "Cartel")
    width_ratio = (
        args.width_ratio
        if args.width_ratio is not None
        else _env_float("BRAND_WATERMARK_WIDTH_RATIO", 0.10)
    )
    position = args.position or os.environ.get("BRAND_WATERMARK_POSITION", "top-center")
    horizontal_padding_ratio = (
        args.horizontal_padding_ratio
        if args.horizontal_padding_ratio is not None
        else _env_float("BRAND_WATERMARK_HORIZONTAL_PADDING_RATIO", 0.03)
    )
    vertical_padding_ratio = (
        args.vertical_padding_ratio
        if args.vertical_padding_ratio is not None
        else _env_float("BRAND_WATERMARK_VERTICAL_PADDING_RATIO", 0.0)
    )
    opacity = (
        args.opacity
        if args.opacity is not None
        else _env_float("BRAND_WATERMARK_OPACITY", 1.0)
    )
    jpeg_quality = (
        args.jpeg_quality
        if args.jpeg_quality is not None
        else _env_int("BRAND_WATERMARK_JPEG_QUALITY", 95)
    )

    print(f"[INFO] Stamping watermark on {input_path}")
    if watermark_path:
        print(f"[INFO] Using watermark asset: {watermark_path}")
    else:
        print(f"[INFO] No watermark asset found; rendering '{line1} / {line2}' badge.")
    print(
        f"[INFO] position={position} width_ratio={width_ratio} "
        f"opacity={opacity} jpeg_quality={jpeg_quality}"
    )

    result = add_watermark(
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

    if not result:
        print("[ERROR] Watermarking failed.")
        return 1

    print(f"[OK] Watermarked image saved to: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
