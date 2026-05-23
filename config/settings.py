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


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


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
SUNO_QUERY_TASK_URL = f"{SUNO_BASE_URL}/api/v1/generate/record-info"
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
    "Styled Photo": "w3zku7ee0a7c3b0f54a66bc352f9ee4e5dd63",
    "Blended Image": "w3zku7ee0a7c3b0f54a66bc352f9ee4e5dd63",
    "Moodboard": "w3zkuf14199afe01c4301bfaaee09d38bbaf6",
    "Styled Reels": "ambg5a9cd6c71a8ae44448c105f0913c389eb",
    "Before and After Reels": "w3zku2c37afa890e347ce8b3e9b39df7b4745",
    "Before and After Feeds": "w71jrff1ea9e28789472cadbde915bd67fd08",
    "Before Reels": "s6v5802e5df0e935c4c6c8222459624cf9bf5",
    "After Reels": "s6v580943e57bab0f4d4786fe4aebcbff671e",
    "Closeup Photo One": "dp2c08f3af2dff1f8489ba0b8dd7b6b3a4e23",
    "Closeup Photo Two": "dp2c0db6c28ec7c70413db298737ef21245ec",
    "Closeup Photo One Video": "ambg57d6506c1975f41fabba6bb9d1c10a2f5",
    "Closeup Photo Two Video": "dp2c07273014cfd5242fc8b0aff6b5d7deaf1",
    "Combined Closeup Videos": "ambg5989559df124d4a5ab129f2e97346e7b0",
    "Product Closeup Photos": "w71jr25f4c097c98647f190f790ba29dc3a3d",
    # Final-phase outputs. Hardcoded to the user's Zoho folders; the
    # matching env vars still override if explicitly set and not empty.
    "CTA": os.environ.get("ZOHO_FOLDER_CTA", "").strip() or "h8atd1190158bb68e4930be8974c9abbe88c0",
    "Polls and Slider": os.environ.get("ZOHO_FOLDER_POLLS_AND_SLIDER", "").strip() or "h8atddf8980c8b6be40fb84d65e46b0ca4d61",
    "Styled Stories": os.environ.get("ZOHO_FOLDER_STYLED_STORIES", "").strip() or "w71jrded080384fb44802b449d10beb2ca3dc",
    "Sliders": os.environ.get("ZOHO_FOLDER_SLIDERS", "").strip() or "w71jr23767b7a3e3d48f282529d084d342542",
    "Tips Reels": os.environ.get("ZOHO_FOLDER_TIPS_REELS", "").strip() or "bhqwjef405f146ae042968a4028c97ff9584c",
}

# ── ElevenLabs Voiceover (Phase 14: Tips Reels) ────────────────────
KIE_VOICE_ID = os.environ.get("KIE_VOICE_ID", "").strip() or "EkK5I93UQWFDigLMpZcX"
KIE_STABILITY = _env_float("KIE_STABILITY", 0.5)

# ── Shop Now Overlay (Phase 12) ────────────────────────────────────
SHOP_NOW_TEXT = os.environ.get("SHOP_NOW_TEXT", "SHOP NOW")

# ── Brand Watermark (Phase 2: Blended Image) ───────────────────────
# Stamps the HomeCartel logo onto the Blended Image so all derived
# outputs (Moodboard, After Reels, Closeups, CTA) inherit the brand
# mark. Set BRAND_WATERMARK_ENABLED=false to skip the stamp.
BRAND_WATERMARK_ENABLED = _env_bool("BRAND_WATERMARK_ENABLED", True)
# Path to the watermark PNG to composite. Defaults to the bundled
# HomeCartel brand asset; set BRAND_WATERMARK_PATH=/some/other.png to
# override. If the resolved path doesn't exist, the watermark is
# rendered programmatically using BRAND_WATERMARK_LINE1 / LINE2.
_DEFAULT_WATERMARK = os.path.join(PROJECT_ROOT, "assets", "brand_watermark.png")
BRAND_WATERMARK_PATH = (
    os.environ.get("BRAND_WATERMARK_PATH", "").strip()
    or (_DEFAULT_WATERMARK if os.path.isfile(_DEFAULT_WATERMARK) else None)
)
BRAND_WATERMARK_LINE1 = os.environ.get("BRAND_WATERMARK_LINE1", "Home")
BRAND_WATERMARK_LINE2 = os.environ.get("BRAND_WATERMARK_LINE2", "Cartel")
# Width of the watermark as a fraction of the source image width. The
# bundled square HomeCartel badge reads cleanly at ~10% of the photo
# width.
BRAND_WATERMARK_WIDTH_RATIO = _env_float("BRAND_WATERMARK_WIDTH_RATIO", 0.10)
# Anchor: top-left, top-center, top-right, bottom-left, bottom-center,
# bottom-right, or center.
BRAND_WATERMARK_POSITION = os.environ.get("BRAND_WATERMARK_POSITION", "top-center")
BRAND_WATERMARK_HORIZONTAL_PADDING_RATIO = _env_float(
    "BRAND_WATERMARK_HORIZONTAL_PADDING_RATIO", 0.03,
)
BRAND_WATERMARK_VERTICAL_PADDING_RATIO = _env_float(
    "BRAND_WATERMARK_VERTICAL_PADDING_RATIO", 0.0,
)
BRAND_WATERMARK_OPACITY = _env_float("BRAND_WATERMARK_OPACITY", 1.0)
BRAND_WATERMARK_JPEG_QUALITY = _env_int("BRAND_WATERMARK_JPEG_QUALITY", 95)

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
PINTEREST_SCRAPER_METHOD = os.environ.get("PINTEREST_SCRAPER_METHOD", "requests").strip().lower()
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
