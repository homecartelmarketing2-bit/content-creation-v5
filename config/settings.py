import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_ROOT = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else PROJECT_ROOT
DATA_DIR = os.path.join(RUNTIME_ROOT, "data")

# =====================================================================
#  API KEYS & ENDPOINTS
#  Loaded from .env file — see .env.example for required variables.
# =====================================================================

# ── Kie.ai ──────────────────────────────────────────────────────────
KIE_API_KEY = os.environ["KIE_API_KEY"]
KIE_CREATE_TASK_URL = "https://api.kie.ai/api/v1/jobs/createTask"
KIE_QUERY_TASK_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"

# ── Suno / Music Generation (via Kie.ai) ───────────────────────────
SUNO_API_KEY = os.environ.get("SUNO_API_KEY", "")
SUNO_BASE_URL = "https://api.kie.ai"
SUNO_GENERATE_URL = f"{SUNO_BASE_URL}/api/v1/generate/sounds"
SUNO_DEFAULT_MODEL = os.environ.get("SUNO_MODEL", "V5")
SUNO_DEFAULT_TEMPO = int(os.environ.get("SUNO_TEMPO", "166"))
SUNO_DEFAULT_KEY = os.environ.get("SUNO_KEY", "D#m")
SUNO_SOUND_LOOP = _env_bool("SUNO_SOUND_LOOP", True)
SUNO_GRAB_LYRICS = _env_bool("SUNO_GRAB_LYRICS", True)

# ── Airtable ────────────────────────────────────────────────────────
AIRTABLE_TOKEN = os.environ["AIRTABLE_TOKEN"]
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "appHpj2rBo7IuojU6")

# ── Zoho WorkDrive ──────────────────────────────────────────────────
ZOHO_CLIENT_ID = os.environ["ZOHO_CLIENT_ID"]
ZOHO_CLIENT_SECRET = os.environ["ZOHO_CLIENT_SECRET"]
ZOHO_REFRESH_TOKEN = os.environ["ZOHO_REFRESH_TOKEN"]
ZOHO_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
ZOHO_UPLOAD_URL = "https://workdrive.zoho.com/api/v1/upload"

ZOHO_FOLDERS = {
    "Styled Photo": "s6v582b5a04cdd1574143b110a9ee16e91930",
    "Blended Image": "w3zku7ee0a7c3b0f54a66bc352f9ee4e5dd63",
    "Moodboard": "w3zkuf14199afe01c4301bfaaee09d38bbaf6",
    "Styled Reels": "s6v58a88f0b597b734dd69a758fefe1d95bca",
    "Before and After Reels": "w3zkuc243ae9fed1a4d9e83ffee0602aa1821",
    "Before and After Feeds": "s6v5867f60395d9704a70aec8867fda313f0d",
    "Before Reels": "s6v5802e5df0e935c4c6c8222459624cf9bf5",
    "After Reels": "s6v580943e57bab0f4d4786fe4aebcbff671e",
    "Closeup Photo One": "dp2c08f3af2dff1f8489ba0b8dd7b6b3a4e23",
    "Closeup Photo Two": "dp2c0db6c28ec7c70413db298737ef21245ec",
    "Closeup Photo One Video": "dp2c01030cd1615ee4f929299945a21767826",
    "Closeup Photo Two Video": "dp2c07273014cfd5242fc8b0aff6b5d7deaf1",
    "Combined Closeup Videos": "dp2c071305f65b3c14e7ba07da0e99ca8e15d",
}

# ── Vision LLM (local LM Studio) ───────────────────────────────────
VISION_LLM_MODEL = os.environ.get("VISION_LLM_MODEL", "zai-org/glm-4.6v-flash")
VISION_LLM_ENDPOINTS = os.environ.get(
    "VISION_LLM_ENDPOINTS",
    "http://127.0.0.1:1234/v1/chat/completions",
).split(",")
VISION_LLM_TIMEOUT = 120

# ── Local Photo Directory ───────────────────────────────────────────
MARKETING_PHOTO_DIR = os.environ.get(
    "MARKETING_PHOTO_DIR",
    r"C:\Users\oscar\OneDrive\Desktop\Marketing Photos",
)
LOCAL_PHOTO_DIR = MARKETING_PHOTO_DIR
PINTEREST_SEARCH_TERMS = _env_csv(
    "PINTEREST_SEARCH_TERMS",
    "interior design living room lighting, modern home lighting ideas, luxury interior lighting, cozy living room decor",
)
PINTEREST_MIN_PHOTOS = _env_int("PINTEREST_MIN_PHOTOS", 40)
PINTEREST_BATCH_SIZE = _env_int("PINTEREST_BATCH_SIZE", 30)
PINTEREST_MAX_SCROLLS = _env_int("PINTEREST_MAX_SCROLLS", 18)
PINTEREST_HEADLESS = _env_bool("PINTEREST_HEADLESS", False)
_PINTEREST_PROFILE_DIR_RAW = os.environ.get(
    "PINTEREST_PROFILE_DIR",
    os.path.join(DATA_DIR, "pinterest_profile"),
)
PINTEREST_PROFILE_DIR = (
    _PINTEREST_PROFILE_DIR_RAW
    if os.path.isabs(_PINTEREST_PROFILE_DIR_RAW)
    else os.path.join(RUNTIME_ROOT, _PINTEREST_PROFILE_DIR_RAW)
)
PINTEREST_BROWSER_EXECUTABLE = os.environ.get("PINTEREST_BROWSER_EXECUTABLE", "").strip() or None
PHOTO_USAGE_MANIFEST = os.environ.get(
    "PHOTO_USAGE_MANIFEST",
    os.path.join(DATA_DIR, "photo_usage.json"),
)

# =====================================================================
#  MODEL & GENERATION SETTINGS
# =====================================================================

# ── Image Generation (Kie.ai) ──────────────────────────────────────
IMAGE_MODEL = "nano-banana-pro"
IMAGE_ASPECT_RATIO = "9:16"
IMAGE_RESOLUTION = "2K"
IMAGE_FORMAT = "png"

# ── Video Generation (Kling v2.5 Turbo via Kie.ai) ─────────────────
VIDEO_MODEL = "kling/v2-5-turbo-image-to-video-pro"
VIDEO_DURATION = "5"
VIDEO_NEGATIVE_PROMPT = "blur, distort, and low quality"
VIDEO_CFG_SCALE = 0.5

# ── Polling ─────────────────────────────────────────────────────────
POLL_INTERVAL = 5  # seconds between status checks
POLL_MAX_WAIT = 600  # max seconds to wait per task (10 minutes)

# ── Main Loop ───────────────────────────────────────────────────────
IDLE_WAIT_SECONDS = 30   # wait time when all tables are clear
