from __future__ import annotations

import os

from config.settings import (
    FAL_ACCELERATION,
    FAL_IMAGE_SIZE,
    FAL_KEY,
    FAL_MODEL,
    FAL_NUM_IMAGES,
    FAL_OUTPUT_FORMAT,
)


def generate_room_interiors(prompt: str) -> list[str]:
    """Generate room interior images with fal.ai and return image URLs."""
    if not FAL_KEY:
        print("[ERROR] FAL_KEY is not configured.")
        return []

    os.environ["FAL_KEY"] = FAL_KEY

    try:
        import fal_client
    except ImportError:
        print("[ERROR] Missing dependency: fal-client. Run: pip install -r requirements.txt")
        return []

    print(f"[INFO] Generating {FAL_NUM_IMAGES} room interior image(s) with {FAL_MODEL}...")
    try:
        result = fal_client.subscribe(
            FAL_MODEL,
            arguments={
                "prompt": prompt,
                "image_size": FAL_IMAGE_SIZE,
                "num_images": FAL_NUM_IMAGES,
                "output_format": FAL_OUTPUT_FORMAT,
                "acceleration": FAL_ACCELERATION,
            },
            with_logs=True,
        )
    except Exception as exc:
        print(f"[ERROR] fal.ai generation failed: {exc}")
        return []

    images = result.get("images", []) if isinstance(result, dict) else []
    urls = [
        image.get("url")
        for image in images
        if isinstance(image, dict) and image.get("url")
    ]

    if len(urls) != FAL_NUM_IMAGES:
        print(f"[WARN] fal.ai returned {len(urls)} image URL(s); expected {FAL_NUM_IMAGES}.")

    return urls
