# =====================================================================
#  KIE.AI SERVICE
#  Handles image generation, blending, video creation, and task polling.
# =====================================================================

import json
import time
import requests

from config.settings import (
    KIE_API_KEY,
    KIE_CREATE_TASK_URL,
    KIE_QUERY_TASK_URL,
    IMAGE_MODEL,
    IMAGE_ASPECT_RATIO,
    IMAGE_RESOLUTION,
    IMAGE_FORMAT,
    VIDEO_MODEL,
    VIDEO_DURATION,
    VIDEO_NEGATIVE_PROMPT,
    VIDEO_CFG_SCALE,
    POLL_INTERVAL,
    POLL_MAX_WAIT,
    SUNO_GENERATE_URL,
    SUNO_DEFAULT_MODEL,
    SUNO_DEFAULT_TEMPO,
    SUNO_DEFAULT_KEY,
    SUNO_SOUND_LOOP,
    SUNO_GRAB_LYRICS,
)


# ── Helpers ─────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {KIE_API_KEY}",
    }


def _create_task(payload: dict) -> str | None:
    """Posts a task to Kie.ai and returns the taskId or None."""
    try:
        resp = requests.post(KIE_CREATE_TASK_URL, headers=_headers(), json=payload)
        data = resp.json()
        if data.get("code") == 200:
            return data["data"]["taskId"]
        print(f"[ERROR] Kie.ai: {data.get('message')}")
    except requests.RequestException as e:
        print(f"[ERROR] Creating Kie.ai task: {e}")
    return None


# ── Task Creators ───────────────────────────────────────────────────

def create_image_task(prompt: str) -> str | None:
    """Creates a text-to-image task and returns the taskId."""
    return _create_task({
        "model": IMAGE_MODEL,
        "input": {
            "prompt": prompt,
            "aspect_ratio": IMAGE_ASPECT_RATIO,
            "resolution": IMAGE_RESOLUTION,
            "output_format": IMAGE_FORMAT,
        },
    })


def create_blend_task(image_urls: list[str], prompt: str) -> str | None:
    """Creates an image-blend task and returns the taskId."""
    return _create_task({
        "model": IMAGE_MODEL,
        "input": {
            "prompt": prompt,
            "aspect_ratio": IMAGE_ASPECT_RATIO,
            "resolution": IMAGE_RESOLUTION,
            "output_format": IMAGE_FORMAT,
            "image_input": image_urls,
        },
    })


def create_video_task(image_url: str, prompt: str) -> str | None:
    """Creates an image-to-video task (Kling v2.5 Turbo) and returns the taskId."""
    return _create_task({
        "model": VIDEO_MODEL,
        "input": {
            "prompt": prompt,
            "image_url": image_url,
            "duration": VIDEO_DURATION,
            "negative_prompt": VIDEO_NEGATIVE_PROMPT,
            "cfg_scale": VIDEO_CFG_SCALE,
        },
    })


def create_music_task(prompt: str) -> str | None:
    """Creates a music generation task (Suno) and returns the taskId."""
    # Note: Using the provided SUNO_GENERATE_URL which might be a createTask variant
    return _create_task({
        "model": SUNO_DEFAULT_MODEL,
        "input": {
            "prompt": prompt,
            "instrumental": True,
            "tempo": SUNO_DEFAULT_TEMPO,
            "key": SUNO_DEFAULT_KEY,
            "loop": SUNO_SOUND_LOOP,
            "grab_lyrics": SUNO_GRAB_LYRICS,
        },
    })


# ── Polling ─────────────────────────────────────────────────────────

def poll_task_status(task_id: str) -> str | None:
    """
    Polls until the task succeeds, fails, or times out.
    Returns the first result URL (image/video/audio) on success, or None on failure/timeout.
    """
    print(f"[WAIT] Polling task {task_id[:12]}... (waiting indefinitely until success or fail)")
    start = time.time()

    while True:
        elapsed = int(time.time() - start)
        try:
            resp = requests.get(
                KIE_QUERY_TASK_URL,
                headers=_headers(),
                params={"taskId": task_id},
                timeout=30,
            )
            data = resp.json()

            if data.get("code") != 200:
                print(f"[ERROR] Kie.ai poll returned code {data.get('code')}: {data.get('message', 'Unknown')}")
                return None

            state = data["data"].get("state", "").lower()
            status = data["data"].get("status", "").upper()

            if state == "success" or status == "SUCCESS":
                print(f"\n[OK] Task {task_id[:12]} completed in {elapsed}s")
                
                # Check for Suno audio URL in response
                response_data = data["data"].get("response", {})
                if isinstance(response_data, dict) and "sunoData" in response_data:
                    suno_list = response_data["sunoData"]
                    if suno_list and isinstance(suno_list, list):
                        return suno_list[0].get("audioUrl")

                # Check for standard resultUrls
                result = data["data"].get("resultJson", {})
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except json.JSONDecodeError:
                        result = {}
                urls = result.get("resultUrls", [])
                return urls[0] if urls else None

            if state in ["failed", "fail"] or status in ["FAILED", "FAIL"]:
                print(f"\n[ERROR] Task failed after {elapsed}s: {data['data'].get('failMsg', 'Unknown')}")
                return None

            mins, secs = divmod(elapsed, 60)
            time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
            print(f"\r[WAIT] Task {task_id[:12]} state='{state}' (Elapsed: {time_str})        ", end="", flush=True)

        except requests.RequestException as e:
            print(f"\n[WARN] Poll network error ({elapsed}s elapsed): {e}")

        time.sleep(POLL_INTERVAL)