# =====================================================================
#  VISION LLM SERVICE
#  Generates creative interior-design prompts from reference photos
#  using a local LM Studio vision model.
# =====================================================================

import os
import io
import re
import random
import base64
import json

import requests
from PIL import Image

from config.settings import (
    VISION_LLM_MODEL,
    VISION_LLM_ENDPOINTS,
    VISION_LLM_TIMEOUT,
    LOCAL_PHOTO_DIR,
    PHOTO_USAGE_MANIFEST,
    PROJECT_ROOT,
)
from config.prompts import (
    VISION_LLM_SYSTEM_PROMPT,
    build_vision_user_prompt,
    POLL_VISION_SYSTEM_PROMPT,
    build_poll_user_prompt,
)


# ── Image Encoding ──────────────────────────────────────────────────

def _encode_image(image_path: str, max_size: int = 800) -> str:
    """Resizes and base64-encodes an image for the vision model."""
    img = Image.open(image_path)
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    img.thumbnail((max_size, max_size))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


# ── Photo Selection ─────────────────────────────────────────────────

def _load_photo_usage() -> set[str]:
    try:
        if os.path.exists(PHOTO_USAGE_MANIFEST):
            with open(PHOTO_USAGE_MANIFEST, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return set(data.get("used", []))
    except Exception as exc:
        print(f"[WARN] Could not read photo usage manifest: {exc}")
    return set()


def _save_photo_usage(used: set[str]) -> None:
    try:
        os.makedirs(os.path.dirname(PHOTO_USAGE_MANIFEST), exist_ok=True)
        with open(PHOTO_USAGE_MANIFEST, "w", encoding="utf-8") as fh:
            json.dump({"used": sorted(used)}, fh, indent=2)
    except Exception as exc:
        print(f"[WARN] Could not save photo usage manifest: {exc}")


def get_random_local_photo() -> str | None:
    """Picks a not-recently-used photo from the reference directory."""
    if not os.path.exists(LOCAL_PHOTO_DIR):
        print(f"[ERROR] Directory not found: {LOCAL_PHOTO_DIR}")
        return None

    valid_ext = (".jpg", ".jpeg", ".png", ".webp")
    photos = [
        os.path.join(LOCAL_PHOTO_DIR, f)
        for f in os.listdir(LOCAL_PHOTO_DIR)
        if f.lower().endswith(valid_ext)
    ]

    if not photos:
        print(f"[ERROR] No photos found in {LOCAL_PHOTO_DIR}")
        return None

    used = _load_photo_usage()
    available = [p for p in photos if os.path.abspath(p) not in used]
    if not available:
        used = set()
        available = photos

    choice = random.choice(available)
    used.add(os.path.abspath(choice))
    _save_photo_usage(used)
    return choice


# ── Prompt Cleanup ────────────────────────────────────────────────

def _clean_prompt(raw: str) -> str:
    """Strips unwanted formatting from LLM output to produce a clean prompt."""
    text = raw.strip()
    # Remove wrapping quotes
    if (text.startswith('"') and text.endswith('"')) or \
       (text.startswith("'") and text.endswith("'")):
        text = text[1:-1]
    # Remove backslash escapes (e.g. \", \n, \\)
    text = text.replace('\\"', '"').replace("\\'", "'")
    text = text.replace("\\n", " ").replace("\\t", " ")
    text = text.replace("\\", "")
    # Remove markdown-style formatting
    text = re.sub(r'\*+', '', text)           # bold/italic markers
    text = re.sub(r'^[-•]\s*', '', text, flags=re.MULTILINE)  # bullet points
    # Collapse newlines and extra spaces into single spaces
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove any remaining leading/trailing quotes
    text = text.strip('"').strip("'").strip()
    return text


# ── Prompt Generation ───────────────────────────────────────────────

def generate_prompt(image_path: str) -> str | None:
    """
    Sends a reference photo to the local vision LLM and returns a
    creative interior-design prompt. Tries each configured endpoint
    in order (fallback chain).
    """
    base64_image = _encode_image(image_path)

    payload = {
        "model": VISION_LLM_MODEL,
        "messages": [
            {"role": "system", "content": VISION_LLM_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": build_vision_user_prompt()},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            },
        ],
        "max_tokens": 500,
        "temperature": 1.0,
    }

    headers = {"Content-Type": "application/json"}

    for attempt in range(3):
        for endpoint in VISION_LLM_ENDPOINTS:
            try:
                resp = requests.post(endpoint, headers=headers, json=payload, timeout=VISION_LLM_TIMEOUT)
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    raw = choices[0]["message"]["content"]
                    cleaned = _clean_prompt(raw)
                    return cleaned
            except requests.RequestException:
                continue  # try next endpoint

    print("[ERROR] Vision LLM generation failed")
    return None


# ── Poll Generation (Phase 13) ──────────────────────────────────────

def _extract_json_blob(raw: str) -> str | None:
    """Pulls the first {...} JSON object out of an LLM response."""
    if not raw:
        return None
    # Strip markdown code fences if present
    fenced = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).replace("```", "")
    match = re.search(r"\{.*\}", fenced, flags=re.DOTALL)
    return match.group(0) if match else None


def generate_poll(context: str = "") -> dict | None:
    """
    Asks the LLM to produce a poll with a question + A/B choices.

    This is a TEXT-ONLY call — no reference image is sent. The optional
    ``context`` argument should be a short text description of the room,
    lighting, or fixture combo so the poll feels relevant. Returns a
    dict shaped like ``{"question": str, "choice_a": str, "choice_b": str}``
    or None on failure.
    """
    payload = {
        "model": VISION_LLM_MODEL,
        "messages": [
            {"role": "system", "content": POLL_VISION_SYSTEM_PROMPT},
            {"role": "user", "content": build_poll_user_prompt(context)},
        ],
        "max_tokens": 300,
        "temperature": 0.9,
    }

    headers = {"Content-Type": "application/json"}

    for attempt in range(3):
        for endpoint in VISION_LLM_ENDPOINTS:
            try:
                resp = requests.post(
                    endpoint, headers=headers, json=payload,
                    timeout=VISION_LLM_TIMEOUT,
                )
                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    continue

                raw = choices[0]["message"]["content"]
                blob = _extract_json_blob(raw)
                if not blob:
                    print(f"[WARN] Poll LLM response had no JSON object: {raw[:200]}")
                    continue

                try:
                    parsed = json.loads(blob)
                except json.JSONDecodeError as exc:
                    print(f"[WARN] Poll LLM JSON parse failed ({exc}): {blob[:200]}")
                    continue

                question = str(parsed.get("question", "")).strip()
                choice_a = str(parsed.get("choice_a", "")).strip()
                choice_b = str(parsed.get("choice_b", "")).strip()

                if not (question and choice_a and choice_b):
                    print(f"[WARN] Poll LLM returned incomplete fields: {parsed}")
                    continue

                return {
                    "question": question,
                    "choice_a": choice_a,
                    "choice_b": choice_b,
                }

            except requests.RequestException:
                continue  # try next endpoint

    print("[ERROR] Poll generation via Vision LLM failed")
    return None


def generate_product_closeup_caption(image_path: str) -> str:
    """
    Sends a reference photo to the local vision LLM and returns a
    short, catchy product caption.
    """
    if not os.path.exists(image_path):
        print(f"[WARN] Closeup caption source missing: {image_path}. Using fallback.")
        return "Elevate your space with this stunning centerpiece"

    try:
        base64_image = _encode_image(image_path)
    except Exception as e:
        print(f"[WARN] Base64 image encoding failed: {e}. Using fallback.")
        return "Modern luxury meets timeless design"

    system_prompt = (
        "You are an expert luxury home decor copywriter. Look at the "
        "provided room/chandelier photo and generate a short, catchy, "
        "and premium caption (3 to 8 words) for a product catalog. "
        "Output ONLY the raw caption text, without any quotation marks, "
        "brackets, or introductory text."
    )

    user_prompt = "Give me a short, catchy, luxury product caption for this interior lighting piece."

    payload = {
        "model": VISION_LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            },
        ],
        "max_tokens": 30,
        "temperature": 0.8,
    }

    headers = {"Content-Type": "application/json"}

    for attempt in range(3):
        for endpoint in VISION_LLM_ENDPOINTS:
            try:
                resp = requests.post(endpoint, headers=headers, json=payload, timeout=VISION_LLM_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        raw = choices[0]["message"]["content"]
                        cleaned = _clean_prompt(raw)
                        if cleaned:
                            return cleaned
            except requests.RequestException:
                continue

    print("[WARN] Vision LLM closeup caption generation failed. Using default.")
    fallbacks = [
        "Elevate your space with this stunning centerpiece",
        "Modern luxury meets timeless design",
        "Illuminate your home with elegance",
        "A bold statement for modern living",
        "Sophisticated lighting for your dream space"
    ]
    return random.choice(fallbacks)


def generate_styling_tip(image_path: str, context: str = "") -> str:
    """
    Sends a reference photo to the local vision LLM and returns a
    creative interior-design tip of 6-to-12 words.
    """
    if not os.path.exists(image_path):
        print(f"[WARN] Styling tip source missing: {image_path}. Using fallback.")
        return "Layer lighting with floor lamps to add warmth and depth"

    try:
        base64_image = _encode_image(image_path)
    except Exception as e:
        print(f"[WARN] Base64 image encoding failed: {e}. Using fallback.")
        return "Position lighting at eye level for a cozy ambiance"

    system_prompt = (
        "You are an expert interior designer and stylist. Your job is to look at "
        "the provided room and lighting setup, and generate a brief, catchy styling tip "
        "of exactly 6 to 12 words. Focus on a specific design tip related to "
        "lighting, space, or decor harmony. Output ONLY the raw styling tip, without "
        "any quotation marks, punctuation at the end, introductory text, or formatting."
    )

    user_prompt = (
        "Analyze this interior design image. Give me a 6-to-12 word styling tip. "
        "Focus on lighting or fixture layout. Return only the tip text."
    )
    if context:
        user_prompt += f"\nContext: {context}"

    payload = {
        "model": VISION_LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            },
        ],
        "max_tokens": 50,
        "temperature": 0.8,
    }

    headers = {"Content-Type": "application/json"}

    for attempt in range(3):
        for endpoint in VISION_LLM_ENDPOINTS:
            try:
                resp = requests.post(endpoint, headers=headers, json=payload, timeout=VISION_LLM_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        raw = choices[0]["message"]["content"]
                        cleaned = _clean_prompt(raw)
                        if cleaned:
                            return cleaned
            except requests.RequestException:
                continue  # try next endpoint

    print("[WARN] Vision LLM styling tip generation failed. Using default tip.")
    fallbacks = [
        "Position lighting at eye level for a cozy ambiance",
        "Layer lighting with floor lamps to add warmth and depth",
        "Highlight cozy corners using warm ceiling light highlights",
        "Combine pendant lights with ambient bulbs for chic vibes",
        "Mix metals in fixtures to create modern design interest",
    ]
    return random.choice(fallbacks)


def evaluate_photo_quality(image_path: str, item_name: str = "") -> dict | None:
    """
    Evaluates whether a scraped photo is suitable for the Chandelier workflow.
    Returns the parsed LLM JSON, or None if the LLM cannot produce a decision.
    """
    if not os.path.exists(image_path):
        print(f"[ERROR] Evaluation image missing: {image_path}")
        return None

    try:
        base64_image = _encode_image(image_path)
    except Exception as e:
        print(f"[ERROR] Base64 image encoding failed for evaluation: {e}")
        return None

    prompt_path = os.path.join(PROJECT_ROOT, "chandelier_prompt_with_designer_rules.json")
    if item_name.lower() == "chandelier" and os.path.exists(prompt_path):
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()
        except Exception as e:
            print(f"[WARN] Failed to read chandelier prompt file: {e}")
            system_prompt = (
                "You are a strict image quality checker. Return only JSON with "
                "is_beautiful, aesthetic_score, failed_step, and reason."
            )
    else:
        system_prompt = (
            "You are a strict image quality checker for premium interior photos. "
            "Reject blurry, low quality, watermarked, cluttered, badly lit, or off-topic images. "
            "Return only JSON with is_beautiful, aesthetic_score, failed_step, and reason."
        )

    payload = {
        "model": VISION_LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Evaluate this image using the quality guidelines and return only the required JSON.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            },
        ],
        "max_tokens": 500,
        "temperature": 0.1,
    }

    headers = {"Content-Type": "application/json"}

    for attempt in range(3):
        for endpoint in VISION_LLM_ENDPOINTS:
            try:
                resp = requests.post(endpoint, headers=headers, json=payload, timeout=VISION_LLM_TIMEOUT)
                if resp.status_code != 200:
                    print(f"[WARN] Vision LLM returned status code {resp.status_code}")
                    continue

                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    continue

                raw = choices[0]["message"]["content"]
                blob = _extract_json_blob(raw)
                if not blob:
                    print(f"[WARN] Evaluation LLM response had no JSON object: {raw[:200]}")
                    continue

                try:
                    parsed = json.loads(blob)
                except json.JSONDecodeError as exc:
                    print(f"[WARN] Evaluation LLM JSON parse failed ({exc}): {blob[:200]}")
                    continue

                if "is_beautiful" in parsed and "reason" in parsed:
                    return parsed
                print(f"[WARN] Evaluation LLM JSON missing required fields: {parsed}")
            except requests.RequestException as e:
                print(f"[WARN] Vision LLM request exception: {e}")
                continue

    print("[ERROR] Photo evaluation via Vision LLM failed")
    return None
