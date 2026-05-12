import hashlib
import json
import os
import random
import re
import time
from urllib.parse import quote_plus

import requests
from PIL import Image

from config.settings import (
    MARKETING_PHOTO_DIR,
    PINTEREST_BATCH_SIZE,
    PINTEREST_BROWSER_EXECUTABLE,
    PINTEREST_HEADLESS,
    PINTEREST_MAX_SCROLLS,
    PINTEREST_MIN_PHOTOS,
    PINTEREST_PROFILE_DIR,
    PINTEREST_SEARCH_TERMS,
    RUNTIME_ROOT,
)


VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
MIN_IMAGE_WIDTH = 500
MIN_IMAGE_HEIGHT = 500
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MANIFEST_NAME = ".pinterest_scrape_manifest.json"


def count_available_photos(folder: str = MARKETING_PHOTO_DIR) -> int:
    if not os.path.isdir(folder):
        return 0
    return sum(1 for name in os.listdir(folder) if name.lower().endswith(VALID_EXTENSIONS))


def ensure_marketing_photos() -> dict:
    os.makedirs(MARKETING_PHOTO_DIR, exist_ok=True)
    available = count_available_photos()
    if available >= PINTEREST_MIN_PHOTOS:
        return {"scraped": False, "downloaded": 0, "available": available}

    needed = max(PINTEREST_BATCH_SIZE, PINTEREST_MIN_PHOTOS - available)
    try:
        result = scrape_pinterest_photos(limit=needed)
    except Exception as exc:
        return {
            "scraped": False,
            "downloaded": 0,
            "available": count_available_photos(),
            "error": str(exc),
        }

    result["available"] = count_available_photos()
    return result


def scrape_pinterest_photos(limit: int = PINTEREST_BATCH_SIZE) -> dict:
    os.makedirs(MARKETING_PHOTO_DIR, exist_ok=True)
    os.makedirs(PINTEREST_PROFILE_DIR, exist_ok=True)

    manifest = _load_manifest()
    urls_seen = set(manifest.get("urls", []))
    hashes_seen = set(manifest.get("hashes", []))
    downloaded = 0
    candidates = []

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        launch_kwargs = {
            "headless": PINTEREST_HEADLESS,
            "viewport": {"width": 1365, "height": 900},
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        browser_path = _browser_executable()
        if browser_path:
            launch_kwargs["executable_path"] = browser_path

        context = p.chromium.launch_persistent_context(
            user_data_dir=PINTEREST_PROFILE_DIR,
            **launch_kwargs,
        )
        page = context.pages[0] if context.pages else context.new_page()

        terms = list(PINTEREST_SEARCH_TERMS)
        random.shuffle(terms)
        for term in terms:
            if downloaded >= limit:
                break

            search_url = f"https://www.pinterest.com/search/pins/?q={quote_plus(term)}"
            print(f"[INFO] Scraping Pinterest search: {term}")
            page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)

            for _ in range(PINTEREST_MAX_SCROLLS):
                candidates.extend(_extract_image_urls(page))
                random.shuffle(candidates)

                while candidates and downloaded < limit:
                    image_url = candidates.pop()
                    if image_url in urls_seen:
                        continue
                    saved = _download_image(image_url, urls_seen, hashes_seen, manifest)
                    urls_seen.add(image_url)
                    if saved:
                        downloaded += 1
                        print(f"[OK] Saved Pinterest photo: {os.path.basename(saved)}")

                if downloaded >= limit:
                    break

                page.mouse.wheel(0, 2400)
                page.wait_for_timeout(1500)

        context.close()

    _save_manifest(manifest)
    return {"scraped": True, "downloaded": downloaded, "available": count_available_photos()}


def _extract_image_urls(page) -> list[str]:
    items = page.locator("img").evaluate_all(
        """imgs => imgs.map(img => ({
            src: img.currentSrc || img.src || "",
            srcset: img.getAttribute("srcset") || "",
            width: img.naturalWidth || 0,
            height: img.naturalHeight || 0
        }))"""
    )

    urls = []
    for item in items:
        url = _best_src(item.get("src", ""), item.get("srcset", ""))
        if _is_usable_pinimg_url(url, item.get("width", 0), item.get("height", 0)):
            urls.append(url)
    return list(dict.fromkeys(urls))


def _best_src(src: str, srcset: str) -> str:
    choices = []
    for part in srcset.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        width = 0
        if len(bits) > 1 and bits[1].endswith("w"):
            try:
                width = int(bits[1][:-1])
            except ValueError:
                width = 0
        choices.append((width, bits[0]))
    if choices:
        return max(choices, key=lambda item: item[0])[1]
    return src


def _is_usable_pinimg_url(url: str, width: int, height: int) -> bool:
    if not url or "pinimg.com" not in url:
        return False
    if any(part in url.lower() for part in ("/avatars/", "/rs/", "75x75")):
        return False
    return width >= 120 and height >= 120


def _download_image(url: str, urls_seen: set[str], hashes_seen: set[str], manifest: dict) -> str | None:
    for candidate_url in _candidate_download_urls(url):
        try:
            resp = requests.get(
                candidate_url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://www.pinterest.com/",
                },
                timeout=30,
            )
            if resp.status_code >= 400 or not resp.content:
                continue
            if len(resp.content) > MAX_IMAGE_BYTES:
                continue

            digest = hashlib.sha256(resp.content).hexdigest()
            if digest in hashes_seen:
                urls_seen.add(candidate_url)
                return None

            image_info = _validate_image(resp.content)
            if not image_info:
                continue

            ext, width, height = image_info
            if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                continue

            filename = f"pinterest_{int(time.time())}_{digest[:12]}.{ext}"
            path = os.path.join(MARKETING_PHOTO_DIR, filename)
            with open(path, "wb") as fh:
                fh.write(resp.content)

            hashes_seen.add(digest)
            manifest.setdefault("urls", []).append(candidate_url)
            manifest.setdefault("hashes", []).append(digest)
            manifest.setdefault("files", []).append({
                "file": filename,
                "url": candidate_url,
                "hash": digest,
                "width": width,
                "height": height,
            })
            return path
        except requests.RequestException:
            continue
    return None


def _candidate_download_urls(url: str) -> list[str]:
    urls = [url]
    upgraded = re.sub(r"/\d+x/", "/originals/", url)
    if upgraded != url:
        urls.insert(0, upgraded)
    return list(dict.fromkeys(urls))


def _validate_image(content: bytes) -> tuple[str, int, int] | None:
    try:
        from io import BytesIO
        with Image.open(BytesIO(content)) as img:
            width, height = img.size
            fmt = (img.format or "JPEG").lower()
            if fmt == "jpeg":
                fmt = "jpg"
            if fmt not in {"jpg", "png", "webp"}:
                return None
            img.verify()
            return fmt, width, height
    except Exception:
        return None


def _manifest_path() -> str:
    return os.path.join(MARKETING_PHOTO_DIR, MANIFEST_NAME)


def _load_manifest() -> dict:
    path = _manifest_path()
    if not os.path.exists(path):
        return {"urls": [], "hashes": [], "files": []}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        data.setdefault("urls", [])
        data.setdefault("hashes", [])
        data.setdefault("files", [])
        return data
    except Exception:
        return {"urls": [], "hashes": [], "files": []}


def _save_manifest(manifest: dict) -> None:
    path = _manifest_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    os.replace(tmp, path)


def _browser_executable() -> str | None:
    if PINTEREST_BROWSER_EXECUTABLE and os.path.exists(PINTEREST_BROWSER_EXECUTABLE):
        return PINTEREST_BROWSER_EXECUTABLE

    candidates = [
        os.path.join(RUNTIME_ROOT, "chromium", "chrome.exe"),
        os.path.join(RUNTIME_ROOT, "chromium", "chrome-win64", "chrome.exe"),
        os.path.join(RUNTIME_ROOT, "chromium", "chrome-win", "chrome.exe"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None
