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
    SUNO_QUERY_TASK_URL,
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
        msg = data.get("msg") or data.get("message") or "Unknown error"
        print(f"[ERROR] Kie.ai: {msg}")
    except requests.RequestException as e:
        print(f"[ERROR] Creating Kie.ai task: {e}")
    return None


# ── Task Creators ───────────────────────────────────────────────────

def create_image_task(prompt: str, aspect_ratio: str = None, resolution: str = None) -> str | None:
    """Creates a text-to-image task and returns the taskId."""
    from config.settings import IMAGE_ASPECT_RATIO, IMAGE_RESOLUTION
    ar = aspect_ratio or IMAGE_ASPECT_RATIO
    res = resolution or IMAGE_RESOLUTION
    return _create_task({
        "model": IMAGE_MODEL,
        "input": {
            "prompt": prompt,
            "aspect_ratio": ar,
            "resolution": res,
            "output_format": IMAGE_FORMAT,
        },
    })


def create_blend_task(image_urls: list[str], prompt: str, aspect_ratio: str = None, resolution: str = None) -> str | None:
    """Creates an image-blend task and returns the taskId."""
    from config.settings import IMAGE_ASPECT_RATIO, IMAGE_RESOLUTION
    ar = aspect_ratio or IMAGE_ASPECT_RATIO
    res = resolution or IMAGE_RESOLUTION
    return _create_task({
        "model": IMAGE_MODEL,
        "input": {
            "prompt": prompt,
            "aspect_ratio": ar,
            "resolution": res,
            "output_format": IMAGE_FORMAT,
            "image_input": image_urls,
        },
    })


def create_gpt_image_task(
    image_urls: list[str],
    prompt: str,
    aspect_ratio: str = "auto",
    resolution: str | None = None,
) -> str | None:
    """Creates an image task using the gpt-image-2-image-to-image model."""
    task_input = {
        "prompt": prompt,
        "input_urls": image_urls,
        "aspect_ratio": aspect_ratio,
    }
    if resolution:
        task_input["resolution"] = resolution

    return _create_task({
        "model": "gpt-image-2-image-to-image",
        "input": task_input,
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
    try:
        payload = {
            "prompt": prompt,
            "model": SUNO_DEFAULT_MODEL,
            "soundLoop": SUNO_SOUND_LOOP,
            "soundTempo": SUNO_DEFAULT_TEMPO,
            "soundKey": SUNO_DEFAULT_KEY,
            "grabLyrics": SUNO_GRAB_LYRICS
        }
        resp = requests.post(SUNO_GENERATE_URL, headers=_headers(), json=payload)
        data = resp.json()
        
        # Check if we successfully got a taskId inside the data object
        task_id = data.get("data", {}).get("taskId")
        if task_id:
            return f"suno:{task_id}"

            
        msg = data.get("msg") or data.get("message") or "Unknown error"
        print(f"[ERROR] Kie.ai sound generation: {msg}")
    except Exception as e:
        print(f"[ERROR] Creating Kie.ai music task: {e}")
    return None



def create_voiceover_task(text: str, voice_id: str = None) -> str | None:
    """Creates an ElevenLabs text-to-speech voiceover task and returns the taskId."""
    from config.settings import KIE_VOICE_ID, KIE_STABILITY
    if not voice_id:
        voice_id = KIE_VOICE_ID
    return _create_task({
        "model": "elevenlabs/text-to-dialogue-v3",
        "input": {
            "dialogue": [
                {
                    "text": text,
                    "voice": voice_id,
                }
            ],
            "stability": KIE_STABILITY,
        }
    })


# ── Polling ─────────────────────────────────────────────────────────

def query_task_once(task_id: str) -> tuple[str, str | None]:
    """Returns (pending|success|failed|error, result_url)."""
    try:
        resp = requests.get(
            KIE_QUERY_TASK_URL,
            headers=_headers(),
            params={"taskId": task_id},
            timeout=30,
        )
        data = resp.json()

        if data.get("code") != 200:
            msg = data.get("msg") or data.get("message") or "Unknown error"
            print(f"[ERROR] Kie.ai poll returned code {data.get('code')}: {msg}")
            return "error", None

        task_data = data.get("data", {})
        state = task_data.get("state", "").lower()
        status = task_data.get("status", "").upper()

        if state == "success" or status == "SUCCESS":
            result = task_data.get("resultJson", {})
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    result = {}
            urls = result.get("resultUrls", [])
            return "success", urls[0] if urls else None

        if state in ["failed", "fail"] or status in ["FAILED", "FAIL"]:
            print(f"[ERROR] Kie.ai task failed: {task_data.get('failMsg', 'Unknown')}")
            return "failed", None

        return "pending", None
    except requests.RequestException as e:
        print(f"[WARN] Kie.ai poll network error: {e}")
        return "error", None


def poll_task_status(task_id: str) -> str | None:
    """
    Polls until the task succeeds, fails, or times out.
    Returns the first result URL (image/video/audio) on success, or None on failure/timeout.
    """
    is_suno = False
    display_id = task_id
    query_url = KIE_QUERY_TASK_URL

    if task_id.startswith("suno:"):
        is_suno = True
        task_id = task_id.split("suno:", 1)[1]
        display_id = task_id
        query_url = SUNO_QUERY_TASK_URL

    print(f"[WAIT] Polling task {display_id[:12]}... (waiting indefinitely until success or fail)")
    start = time.time()

    while True:
        elapsed = int(time.time() - start)
        try:
            resp = requests.get(
                query_url,
                headers=_headers(),
                params={"taskId": task_id},
                timeout=30,
            )
            data = resp.json()

            if data.get("code") != 200:
                msg = data.get("msg") or data.get("message") or "Unknown error"
                print(f"[ERROR] Kie.ai poll returned code {data.get('code')}: {msg}")
                return None

            state = data["data"].get("state", "").lower()
            status = data["data"].get("status", "").upper()

            if state == "success" or status == "SUCCESS":
                print(f"\n[OK] Task {display_id[:12]} completed in {elapsed}s")
                
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
            # Use status if state is empty (Suno tasks do not return state)
            print(f"\r[WAIT] Task {display_id[:12]} state='{state or status.lower()}' (Elapsed: {time_str})        ", end="", flush=True)

        except requests.RequestException as e:
            print(f"\n[WARN] Poll network error ({elapsed}s elapsed): {e}")

        time.sleep(POLL_INTERVAL)
