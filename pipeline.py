# =====================================================================
#  PIPELINE
#  Picks one unfinished Airtable row and drives it through all phases:
#    Phase 0   →  Generate Prompt (local Vision LLM / skipped if pre-filled)
#    Phase 1   →  Styled Photo    (Kie.ai text-to-image room backdrop)
#    Phase 2   →  Blend           (Styled Photo + Furniture Item)
#    Phase 3   →  Moodboard       (flat-lay collage from Blended Image)
#    Phase 4   →  Before Reels    (video from Styled Photo)
#    Phase 5   →  After Reels     (video from Blended Image)
#    Phase 6   →  Combined Reels  (Before + After stitched with music)
#    Phase 7   →  Closeup Photo   (Medium closeup of item from Blended Image)
#    Phase 8   →  Closeup Video   (video from Closeup Photo)
#    Phase 9   →  Combine Closeup Videos (After Reels + Closeup Video)
#    Phase 10  →  CTA             (Blended Image + "SHOP NOW" overlay)
#    Phase 11  →  Tips Reels      (stiching tips video segments + music)
#    Phase 12  →  Styled Stories  (9:16 story layout of Blended Image)
# =====================================================================

import os
import tempfile

from config.prompts import (
    MOODBOARD_PROMPT, BEFORE_REELS_PROMPT, AFTER_REELS_PROMPT,
    CLOSEUP_PROMPT_TEMPLATE, CLOSEUP_VIDEO_PROMPT, MUSIC_PROMPT,
    PRODUCT_CLOSEUP_FEEDS_PROMPT,
)
from config.settings import (
    SHOP_NOW_TEXT,
    BRAND_WATERMARK_ENABLED,
    BRAND_WATERMARK_PATH,
    BRAND_WATERMARK_LINE1,
    BRAND_WATERMARK_LINE2,
    BRAND_WATERMARK_WIDTH_RATIO,
    BRAND_WATERMARK_POSITION,
    BRAND_WATERMARK_HORIZONTAL_PADDING_RATIO,
    BRAND_WATERMARK_VERTICAL_PADDING_RATIO,
    BRAND_WATERMARK_OPACITY,
    BRAND_WATERMARK_JPEG_QUALITY,
)

from config.tables import TABLE_FIELD_MAPPINGS, DEFAULT_FIELD_MAPPING, AIRTABLE_TABLES
from services.airtable import (
    get_next_unfinished_row,
    refetch_record,
    update_status,
    update_field,
    update_attachment,
    upload_attachment_file,
)
from services.kie import (
    create_image_task, create_blend_task, create_video_task,
    create_music_task, poll_task_status
)
from services.zoho import upload_from_url, upload_local_file, upload_and_get_public_link, get_or_create_folder
from services.vision_llm import get_random_local_photo, generate_prompt
from services.fal_image import generate_room_interiors
from services.video import download, combine, add_audio_to_video, cleanup_temp_files
from services.image_overlay import make_shop_now_image, make_watermarked_image, fit_image_to_9_16


# ── Field Mapping & Cache Helpers ────────────────────────────────────

_URL_CACHE = {}

def get_field_mapping(table_id: str) -> dict:
    return TABLE_FIELD_MAPPINGS.get(table_id, DEFAULT_FIELD_MAPPING)

def get_table_config(table_id: str) -> dict:
    for t in AIRTABLE_TABLES:
        if t["id"] == table_id:
            return t
    return {}

def _get_mapped_field_val(record_id: str, fields: dict, field_key: str, table_id: str):
    """Gets the value of a field based on its mapped name for the table."""
    mapping = get_field_mapping(table_id)
    mapped_name = mapping.get(field_key)
    
    if not mapped_name:
        cached = _URL_CACHE.get((record_id, field_key))
        if cached:
            if isinstance(cached, str) and (cached.startswith("http://") or cached.startswith("https://")):
                return [{"url": cached}]
            return cached
        return None
        
    val = fields.get(mapped_name)
    if val:
        return val
        
    cached = _URL_CACHE.get((record_id, field_key))
    if cached:
        if isinstance(cached, str) and (cached.startswith("http://") or cached.startswith("https://")):
            return [{"url": cached}]
        return cached
    return None

def _update_mapped_field(table_id: str, record_id: str, field_key: str, value, silent: bool = False):
    """Updates a field on Airtable using its mapped name, and caches it locally."""
    _URL_CACHE[(record_id, field_key)] = value
    
    mapping = get_field_mapping(table_id)
    mapped_name = mapping.get(field_key)
    
    if not mapped_name:
        print(f"[INFO] Field '{field_key}' is not mapped to Airtable for table {table_id}. Saved to local cache.")
        return True
        
    return update_field(table_id, record_id, mapped_name, value, silent=silent)

def _update_mapped_attachment(table_id: str, record_id: str, field_key: str, url: str):
    """Updates an attachment field on Airtable using its mapped name, and caches it locally."""
    _URL_CACHE[(record_id, field_key)] = url
    
    mapping = get_field_mapping(table_id)
    mapped_name = mapping.get(field_key)
    
    if not mapped_name:
        print(f"[INFO] Attachment field '{field_key}' is not mapped to Airtable for table {table_id}. Saved to local cache.")
        return True
        
    return update_attachment(table_id, record_id, mapped_name, url)

def _upload_mapped_attachment_file(table_id: str, record_id: str, field_key: str, file_path: str, content_type: str = "image/jpeg"):
    """Uploads a local file to an attachment field on Airtable using its mapped name."""
    mapping = get_field_mapping(table_id)
    mapped_name = mapping.get(field_key)
    
    if not mapped_name:
        print(f"[INFO] Attachment file '{field_key}' is not mapped to Airtable for table {table_id}. Saved to local cache.")
        return False
        
    return upload_attachment_file(record_id, mapped_name, file_path, content_type=content_type)


# ── Helpers ─────────────────────────────────────────────────────────

def _apply_music(video_path: str, record_id: str, label: str) -> str:
    """Generates marketing music via Suno and applies it to the video."""
    print(f"[INFO] Generating background music for {label}...")

    music_task = create_music_task(MUSIC_PROMPT)
    if not music_task:
        print(f"[WARN] Failed to create music task for {label}. Skipping audio.")
        return video_path

    music_url = poll_task_status(music_task)
    if not music_url:
        print(f"[WARN] Failed to generate music for {label}. Skipping audio.")
        return video_path

    audio_path = download(music_url, f"{record_id}_{label.lower().replace(' ', '_')}_audio.mp3")
    if not audio_path:
        print(f"[WARN] Failed to download music for {label}. Skipping audio.")
        return video_path

    final_path = add_audio_to_video(video_path, audio_path, f"{record_id}_{label.lower().replace(' ', '_')}_with_music.mp4")

    # Cleanup temp audio
    cleanup_temp_files(audio_path)

    if final_path:
        # Return path to the new video with music
        return final_path

    return video_path


def _upload_image_output(
    table_id: str,
    record_id: str,
    airtable_field: str,
    zoho_folder: str,
    source_url: str,
    output_basename: str,
) -> str | None:
    """Uploads an image output, watermarking it first when enabled."""
    raw_path = None
    watermarked_path = None

    if BRAND_WATERMARK_ENABLED:
        raw_path = download(source_url, f"{output_basename}_raw.png")
        if raw_path:
            watermarked_path = make_watermarked_image(
                raw_path,
                record_id,
                output_basename=output_basename,
                extension=".jpg",
                watermark_path=BRAND_WATERMARK_PATH,
                line1=BRAND_WATERMARK_LINE1,
                line2=BRAND_WATERMARK_LINE2,
                width_ratio=BRAND_WATERMARK_WIDTH_RATIO,
                position=BRAND_WATERMARK_POSITION,
                horizontal_padding_ratio=BRAND_WATERMARK_HORIZONTAL_PADDING_RATIO,
                vertical_padding_ratio=BRAND_WATERMARK_VERTICAL_PADDING_RATIO,
                opacity=BRAND_WATERMARK_OPACITY,
                jpeg_quality=BRAND_WATERMARK_JPEG_QUALITY,
            )

    if watermarked_path:
        attached = _upload_mapped_attachment_file(
            table_id,
            record_id,
            airtable_field,
            watermarked_path,
            content_type="image/jpeg",
        )
        if not attached:
            print(
                f"[WARN] Watermarked {airtable_field} upload to Airtable failed; "
                "falling back to raw URL."
            )
            _update_mapped_attachment(table_id, record_id, airtable_field, source_url)

        try:
            upload_local_file(
                watermarked_path,
                f"{output_basename}.jpg",
                zoho_folder,
            )
        except Exception as e:
            print(f"[WARN] Zoho upload of watermarked {airtable_field} failed: {e}")

        cleanup_temp_files(raw_path)
        return watermarked_path

    if BRAND_WATERMARK_ENABLED:
        print(f"[WARN] Watermarking failed for {airtable_field}; uploading raw image.")
    _update_mapped_attachment(table_id, record_id, airtable_field, source_url)
    upload_from_url(source_url, f"{output_basename}.png", zoho_folder)
    cleanup_temp_files(raw_path)
    return None


def _phase0_prompt(table_id: str, record_id: str, fields: dict, ui_callback=None) -> str | None:
    """Phase 0: Generate a styled-photo prompt via the local Vision LLM."""
    prompt = _get_mapped_field_val(record_id, fields, "Styled Photo Prompt", table_id) or ""
    photo_path = None
    generated = None

    if not prompt:
        update_status(table_id, record_id, "Processing Adding a Prompt")
        print("[INFO] Generating prompt from marketing photo (skipping Pinterest scraping)...")

        photo_path = get_random_local_photo()
        if not photo_path:
            print("[ERROR] No local photos found. Reverting to Standby.")
            update_status(table_id, record_id, "Standby")
            return None

        # ── Show the photo in UI with "AI scanning" indicator ──
        if ui_callback:
            ui_callback("🔍 Phase 0: AI Scanning Photo...",
                        desc_text="Analyzing reference photo with Vision LLM. Please wait...",
                        image_path=photo_path,
                        scanning=True)

        generated = generate_prompt(photo_path)
        if not generated:
            print("[ERROR] LLM prompt generation failed. Reverting to Standby.")
            update_status(table_id, record_id, "Standby")
            if ui_callback:
                ui_callback("❌ Phase 0: Prompt Generation Failed",
                            desc_text="The Vision LLM could not generate a prompt for this photo.")
            return None

        _update_mapped_field(table_id, record_id, "Styled Photo Prompt", generated)

        # ── Show generated prompt result in UI ──
        if ui_callback:
            ui_callback("✅ Phase 0: Prompt Generated!",
                        desc_text=generated,
                        image_path=photo_path,
                        scanning=False)
    else:
        print("[INFO] Row already has a prompt. Skipping generation.")
        if ui_callback:
            ui_callback("✅ Phase 0: Prompt Already Exists",
                        desc_text=prompt)

    update_status(table_id, record_id, "Complete Adding a Prompt")
    print("[OK] Phase 0 (Prompt) done.")

    return "Complete Adding a Prompt"


def _phase1_styled_photo(table_id: str, record_id: str, ui_callback=None) -> str | None:
    """Phase 1: Generate a styled photo from the prompt via Kie.ai."""
    fields = refetch_record(table_id, record_id)
    prompt = _get_mapped_field_val(record_id, fields, "Styled Photo Prompt", table_id) or ""

    if not prompt:
        update_status(table_id, record_id, "Error - No Prompt")
        return None

    update_status(table_id, record_id, "Processing")
    print("[INFO] Generating Styled Photo...")
    if ui_callback:
        ui_callback("⏳ Phase 1: Generating Styled Photo...", desc_text=f"Sending prompt to Kie.ai: {prompt[:80]}...")

    cfg = get_table_config(table_id)
    ar = cfg.get("aspect_ratio")
    res = cfg.get("resolution")

    task_id = create_image_task(prompt, aspect_ratio=ar, resolution=res)
    if not task_id:
        update_status(table_id, record_id, "Error - Styled Photo Task Failed")
        return None

    image_url = poll_task_status(task_id)
    if not image_url:
        update_status(table_id, record_id, "Error - Styled Photo Generation Failed")
        return None

    # Persist the raw (un-watermarked) Kie.ai URL
    _update_mapped_field(table_id, record_id, "Styled Photo Raw URL", image_url, silent=True)
    _update_mapped_field(table_id, record_id, "Styled Photo URL", image_url, silent=True)

    if ui_callback and BRAND_WATERMARK_ENABLED:
        ui_callback(
            "⏳ Phase 1: Stamping Watermark...",
            desc_text="Adding the HomeCartel brand watermark to the Styled Photo...",
        )

    ui_image_path = _upload_image_output(
        table_id,
        record_id,
        "Styled Photo",
        "Styled Photo",
        image_url,
        f"{record_id}_styled_photo",
    )
    print("[OK] Phase 1 (Styled Photo) done.")

    if ui_callback:
        if ui_image_path and os.path.exists(ui_image_path):
            ui_callback("Phase 1: Styled Photo", image_path=ui_image_path)
        else:
            import requests
            tmp_img = os.path.join(tempfile.gettempdir(), f"{record_id}_styled_photo.png")
            try:
                with open(tmp_img, 'wb') as f:
                    f.write(requests.get(image_url).content)
                ui_callback("Phase 1: Styled Photo", image_path=tmp_img)
            except Exception:
                pass

    return "Processing"


def _phase_room_interior(table_id: str, record_id: str, fields: dict, ui_callback=None) -> str | None:
    """Generate and attach Room Interior images for the Chandelier table."""
    prompt = _get_mapped_field_val(record_id, fields, "Styled Photo Prompt", table_id) or ""
    existing = _get_mapped_field_val(record_id, fields, "Room Interior", table_id)

    if not prompt:
        print("[INFO] No Styled Photo Prompt. Skipping Room Interior generation.")
        return None
    if existing:
        print("[INFO] Room Interior already has attachments. Skipping fal.ai generation.")
        return "Complete"

    if ui_callback:
        ui_callback("Phase: Room Interior", desc_text=f"Generating 4 fal.ai images: {prompt[:80]}...")

    urls = generate_room_interiors(prompt)
    if not urls:
        update_status(table_id, record_id, "Standby")
        return None

    _update_mapped_field(
        table_id,
        record_id,
        "Room Interior",
        [{"url": url} for url in urls],
    )
    print(f"[OK] Room Interior uploaded with {len(urls)} generated image(s).")
    return "Complete"


def _phase2_blend(table_id: str, record_id: str, blend_prompt: str, ui_callback=None) -> None:
    """Phase 2: Blend the styled photo with furniture items."""
    fields = refetch_record(table_id, record_id)
    styled = _get_mapped_field_val(record_id, fields, "Styled Photo", table_id)
    furn1 = _get_mapped_field_val(record_id, fields, "Furniture Item", table_id)
    furn2 = _get_mapped_field_val(record_id, fields, "Furniture Item2", table_id)
    blended = _get_mapped_field_val(record_id, fields, "Blended Image", table_id)

    if blended:
        print("[INFO] Blended Image already exists. Skipping.")
        return

    mapping = get_field_mapping(table_id)
    has_furn2 = mapping.get("Furniture Item2") is not None

    if not (styled and furn1):
        print("[WARN] Missing Styled Photo or Furniture Item. Skipping blend.")
        return
    if has_furn2 and not furn2:
        print("[WARN] Missing second Furniture Item for 2-item table. Skipping blend.")
        return

    print("[INFO] Blending images...")
    image_urls = [styled[0]["url"], furn1[0]["url"]]
    if has_furn2 and furn2:
        image_urls.append(furn2[0]["url"])

    if ui_callback:
        ui_callback("⏳ Phase 2: Blending Images...", desc_text="Merging room + Chandelier / Furniture items...")

    cfg = get_table_config(table_id)
    ar = cfg.get("aspect_ratio")
    res = cfg.get("resolution")

    task_id = create_blend_task(image_urls, blend_prompt, aspect_ratio=ar, resolution=res)
    if not task_id:
        update_status(table_id, record_id, "Error - Blend Task Failed")
        return

    blended_url = poll_task_status(task_id)
    if not blended_url:
        update_status(table_id, record_id, "Error - Blend Generation Failed")
        return

    # Persist raw blended URL
    _update_mapped_field(table_id, record_id, "Blended Image Raw URL", blended_url, silent=True)

    raw_path = None
    watermarked_path = None
    ui_image_path = None

    if BRAND_WATERMARK_ENABLED:
        if ui_callback:
            ui_callback(
                "⏳ Phase 2: Stamping Watermark...",
                desc_text="Adding the HomeCartel brand watermark to the Blended Image...",
            )

        raw_path = download(blended_url, f"{record_id}_blended_raw.png")
        if raw_path:
            watermarked_path = make_watermarked_image(
                raw_path,
                record_id,
                output_basename=f"{record_id}_blended",
                extension=".jpg",
                watermark_path=BRAND_WATERMARK_PATH,
                line1=BRAND_WATERMARK_LINE1,
                line2=BRAND_WATERMARK_LINE2,
                width_ratio=BRAND_WATERMARK_WIDTH_RATIO,
                position=BRAND_WATERMARK_POSITION,
                horizontal_padding_ratio=BRAND_WATERMARK_HORIZONTAL_PADDING_RATIO,
                vertical_padding_ratio=BRAND_WATERMARK_VERTICAL_PADDING_RATIO,
                opacity=BRAND_WATERMARK_OPACITY,
                jpeg_quality=BRAND_WATERMARK_JPEG_QUALITY,
            )

    if watermarked_path:
        attached = _upload_mapped_attachment_file(
            table_id,
            record_id,
            "Blended Image",
            watermarked_path,
            content_type="image/jpeg",
        )
        if not attached:
            print("[WARN] Watermarked Blended Image upload to Airtable failed; falling back to raw URL.")
            _update_mapped_attachment(table_id, record_id, "Blended Image", blended_url)

        try:
            upload_local_file(
                watermarked_path,
                f"{record_id}_blended.jpg",
                "Blended Image",
            )
        except Exception as e:
            print(f"[WARN] Zoho upload of watermarked Blended Image failed: {e}")

        ui_image_path = watermarked_path
    else:
        if BRAND_WATERMARK_ENABLED:
            print("[WARN] Watermarking failed; uploading the raw Blended Image.")
        _update_mapped_attachment(table_id, record_id, "Blended Image", blended_url)
        upload_from_url(blended_url, f"{record_id}_blended.png", "Blended Image")

    print("[OK] Phase 2 (Blend) done.")

    if ui_callback:
        if ui_image_path and os.path.exists(ui_image_path):
            ui_callback("Phase 2: Blended Image", image_path=ui_image_path)
        else:
            import requests
            tmp_img = os.path.join(tempfile.gettempdir(), f"{record_id}_blended.png")
            try:
                with open(tmp_img, 'wb') as f:
                    f.write(requests.get(blended_url).content)
                ui_callback("Phase 2: Blended Image", image_path=tmp_img)
            except Exception:
                pass

    cleanup_temp_files(raw_path)


def _phase2_5_before_after_feeds(table_id: str, record_id: str, ui_callback=None) -> None:
    """Phase 2.5: Immediately attach Styled Photo and Blended Image to Before and After Feeds field."""
    fields = refetch_record(table_id, record_id)
    mapping = get_field_mapping(table_id)
    feed_field = mapping.get("Before and After Feeds")
    
    if not feed_field:
        return
        
    existing_feeds = fields.get(feed_field)
    if existing_feeds:
        return

    styled_photos = _get_mapped_field_val(record_id, fields, "Styled Photo", table_id)
    blended_images = _get_mapped_field_val(record_id, fields, "Blended Image", table_id)

    attachments = []
    if styled_photos and isinstance(styled_photos, list):
        attachments.append({"url": styled_photos[0]["url"]})
    if blended_images and isinstance(blended_images, list):
        attachments.append({"url": blended_images[0]["url"]})
        
    if attachments:
        _update_mapped_field(table_id, record_id, "Before and After Feeds", attachments)
        print("[INFO] Populated Before and After Feeds with Styled Photo & Blended Image.")


def _phase3_moodboard(table_id: str, record_id: str, ui_callback=None) -> None:
    """Phase 3: Generate a moodboard from the blended image."""
    fields = refetch_record(table_id, record_id)
    blended = _get_mapped_field_val(record_id, fields, "Blended Image", table_id)
    moodboard = _get_mapped_field_val(record_id, fields, "Moodboard Image", table_id)

    if moodboard:
        print("[INFO] Moodboard already exists. Skipping.")
        return
    if not blended:
        print("[WARN] No Blended Image found. Cannot generate Moodboard.")
        return

    print("[INFO] Generating Moodboard...")
    blended_url = blended[0]["url"]
    if ui_callback:
        ui_callback("⏳ Phase 3: Generating Moodboard...", desc_text="Creating moodboard layout from blended image...")

    cfg = get_table_config(table_id)
    ar = cfg.get("aspect_ratio")
    res = cfg.get("resolution")

    task_id = create_blend_task([blended_url], MOODBOARD_PROMPT, aspect_ratio=ar, resolution=res)
    if not task_id:
        update_status(table_id, record_id, "Error - Moodboard Task Failed")
        return

    moodboard_url = poll_task_status(task_id)
    if not moodboard_url:
        update_status(table_id, record_id, "Error - Moodboard Generation Failed")
        return

    ui_image_path = _upload_image_output(
        table_id,
        record_id,
        "Moodboard Image",
        "Moodboard",
        moodboard_url,
        f"{record_id}_moodboard",
    )
    print("[OK] Phase 3 (Moodboard) done.")

    if ui_callback:
        if ui_image_path and os.path.exists(ui_image_path):
            ui_callback("Phase 3: Moodboard", image_path=ui_image_path)
        else:
            import requests
            tmp_img = os.path.join(tempfile.gettempdir(), f"{record_id}_moodboard.png")
            try:
                with open(tmp_img, 'wb') as f:
                    f.write(requests.get(moodboard_url).content)
                ui_callback("Phase 3: Moodboard", image_path=tmp_img)
            except Exception:
                pass



def _phase_video(table_id: str, record_id: str,
                 source_field: str, target_field: str,
                 prompt: str, zoho_folder: str, label: str,
                 apply_music: bool = True,
                 source_url_field: str | None = None,
                 ui_callback=None) -> None:
    """Generic video-from-image phase (used for Before & After Reels)."""
    # Resolve dynamic Zoho folder using the mapped target field name if it exists in ZOHO_FOLDERS
    from config.settings import ZOHO_FOLDERS
    mapping = TABLE_FIELD_MAPPINGS.get(table_id, DEFAULT_FIELD_MAPPING)
    mapped_target_field = mapping.get(target_field, target_field)
    if mapped_target_field in ZOHO_FOLDERS:
        zoho_folder = mapped_target_field

    fields = refetch_record(table_id, record_id)

    source = _get_mapped_field_val(record_id, fields, source_field, table_id)
    existing = _get_mapped_field_val(record_id, fields, target_field, table_id)

    if existing:
        print(f"[INFO] {label} already exists. Skipping.")
        return

    source_url = None
    if source_url_field:
        raw_value = _get_mapped_field_val(record_id, fields, source_url_field, table_id)
        if isinstance(raw_value, str) and raw_value.strip():
            source_url = raw_value.strip()
            print(f"[INFO] Using raw (un-watermarked) source URL from '{source_url_field}' for {label}.")

    if not source_url:
        if not source:
            return
        source_url = source[0]["url"]
        if source_url_field:
            print(f"[WARN] '{source_url_field}' empty; falling back to watermarked attachment for {label}.")

    print(f"[INFO] Generating {label} video...")
    if ui_callback:
        ui_callback(f"⏳ Phase Video: Generating {label}...", desc_text=f"Creating video from {source_field}...")

    task_id = create_video_task(source_url, prompt)
    if not task_id:
        update_status(table_id, record_id, f"Error - {label} Task Failed")
        return

    video_url = poll_task_status(task_id)
    if not video_url:
        update_status(table_id, record_id, f"Error - {label} Generation Failed")
        return

    # Download video (and optionally apply music)
    temp_video = download(video_url, f"{record_id}_{label.lower().replace(' ', '_')}_raw.mp4")
    if temp_video:
        if apply_music:
            final_video_path = _apply_music(temp_video, record_id, label)
        else:
            print(f"[INFO] Skipping background music for {label} (silent video).")
            final_video_path = temp_video

        # Upload final video to Zoho and get public link for Airtable
        final_url = upload_and_get_public_link(final_video_path, zoho_folder)
        if final_url:
            _update_mapped_attachment(table_id, record_id, target_field, final_url)
        else:
            # Fallback to raw video if upload fails
            _update_mapped_attachment(table_id, record_id, target_field, video_url)
            upload_from_url(video_url, f"{record_id}_{label.lower().replace(' ', '_')}.mp4", zoho_folder)
            
        # Cleanup
        cleanup_temp_files(temp_video, final_video_path if final_video_path != temp_video else None)
    else:
        # Fallback if download fails
        _update_mapped_attachment(table_id, record_id, target_field, video_url)
        upload_from_url(video_url, f"{record_id}_{label.lower().replace(' ', '_')}.mp4", zoho_folder)

    print(f"[OK] {label} done.")
    
    if ui_callback:
        ui_callback(f"Phase Video: {label} Built", desc_text=f"Video generated successfully for {label}.")


def _phase6_combine_reels(table_id: str, record_id: str, ui_callback=None) -> None:
    """Phase 6: Stitch Before + After Reels into one video."""
    fields = refetch_record(table_id, record_id)
    before = _get_mapped_field_val(record_id, fields, "Before Reels", table_id)
    after = _get_mapped_field_val(record_id, fields, "After Reels", table_id)
    combined = _get_mapped_field_val(record_id, fields, "Combine Video Before and After", table_id)

    if combined:
        print("[INFO] Combined Reels already exists. Skipping.")
        return
    if not (before and after):
        return

    print("[INFO] Combining Before + After Reels...")
    if ui_callback:
        ui_callback("⏳ Phase 6: Combining Reels...", desc_text="Stitching Before + After videos together...")
    before_path = download(before[0]["url"], f"{record_id}_before.mp4")
    after_path = download(after[0]["url"], f"{record_id}_after.mp4")

    if not (before_path and after_path):
        print("[WARN] Could not download one or both videos. Skipping.")
        cleanup_temp_files(before_path, after_path)
        return

    combined_path = combine([before_path, after_path], f"{record_id}_combined_raw.mp4")
    if not combined_path:
        print("[WARN] Video combination failed. Skipping.")
        cleanup_temp_files(before_path, after_path)
        return

    # Apply music to the combined video
    final_combined_path = _apply_music(combined_path, record_id, "Before and After Reels")

    suffix = _get_record_suffix(record_id, fields)
    filename = f"combined_reels_{suffix}.mp4"

    # Upload to Zoho Drive (local file upload instead of upload_and_get_public_link)
    upload_ok = upload_local_file(final_combined_path, filename, "Before and After Reels")
    
    if upload_ok:
        # Upload directly to Airtable using the content API
        attached = _upload_mapped_attachment_file(
            table_id,
            record_id,
            "Combine Video Before and After",
            final_combined_path,
            content_type="video/mp4"
        )
        if attached:
            print("[OK] Phase 6 (Combined Reels) done.")
            if ui_callback:
                ui_callback("Phase 6: Combined Reels Compiled", desc_text="Final stitched reels video with music has been uploaded.")
        else:
            print("[WARN] Could not attach combined video to Airtable.")
    else:
        print("[WARN] Could not upload combined video to Zoho. Skipping Airtable attachment.")

    cleanup_temp_files(before_path, after_path, combined_path, 
                       final_combined_path if final_combined_path != combined_path else None)


# ── Closeup Phases ─────────────────────────────────────────────────

def _phase_closeup_photo(table_id: str, record_id: str,
                         item_name: str, target_field: str,
                         label: str, ui_callback=None,
                         closeup_idx: int = 1) -> None:
    """Generates a closeup photo of an item from the Blended Image."""
    fields = refetch_record(table_id, record_id)
    blended = _get_mapped_field_val(record_id, fields, "Blended Image", table_id)
    existing = _get_mapped_field_val(record_id, fields, target_field, table_id)

    if existing:
        if isinstance(existing, list) and len(existing) >= closeup_idx:
            print(f"[INFO] {label} already exists (have {len(existing)} closeups). Skipping.")
            return
        elif not isinstance(existing, list):
            print(f"[INFO] {label} already exists. Skipping.")
            return
            
    if not blended:
        print(f"[WARN] No Blended Image found. Cannot generate {label}.")
        return

    if table_id == "tblDDmCs4S2ePxIfQ":
        # Custom logic for Chandelier table:
        # Generate medium closeup shot, watermark it, upload to Zoho parent folder "Product Closeup Photos",
        # and attach BOTH Blended Image URL and Closeup URL to Airtable "Product Closeup Feeds" field.
        print(f"[INFO] Generating Phase 7: Closeup Photo (Product Closeup Feeds)")
        if ui_callback:
            ui_callback("⏳ Phase 7: Generating Closeup...", desc_text=f"Generating medium closeup of {item_name} from Blended Image using reference layout...")

        blended_url = blended[0]["url"]
        
        # Download blended image temporarily to generate the caption
        blended_path = download(blended_url, f"{record_id}_blended_for_caption.png")
        generated_caption = "HomeCartel Luxury Chandelier"
        if blended_path:
            from services.vision_llm import generate_product_closeup_caption
            generated_caption = generate_product_closeup_caption(blended_path)
            print(f"[INFO] Generated caption for closeup: {generated_caption}")
            # cleanup
            cleanup_temp_files(blended_path)

        # Inject the generated caption into the prompt
        final_prompt = PRODUCT_CLOSEUP_FEEDS_PROMPT.format(caption=generated_caption)
        
        # We need to upload the reference photo to get a public URL for Kie.ai
        reference_photo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "suno ai generation", "ADS STORY FOR MAY.png")
        reference_url = None
        
        if os.path.exists(reference_photo_path):
            print("[INFO] Uploading reference photo to Zoho temporarily to get public URL...")
            from services.zoho import upload_and_get_public_link
            # We can upload it to the same destination folder or CTA temporarily
            reference_url = upload_and_get_public_link(reference_photo_path, "Product Closeup Photos")
        
        if not reference_url:
            print("[ERROR] Could not generate public URL for reference photo. Cannot proceed with Phase 7.")
            update_status(table_id, record_id, "Error - Phase 7 Closeup Task Failed")
            return

        from services.kie import create_gpt_image_task
        # Pass [reference_url, blended_url] to create_gpt_image_task
        task_id = create_gpt_image_task([reference_url, blended_url], final_prompt)
        if not task_id:
            update_status(table_id, record_id, "Error - Phase 7 Closeup Task Failed")
            return

        photo_url = poll_task_status(task_id)
        if not photo_url:
            update_status(table_id, record_id, "Error - Phase 7 Closeup Generation Failed")
            return

        # Persist raw closeup URL
        _update_mapped_field(table_id, record_id, "Closeup Photo One Raw URL", photo_url, silent=True)

        # Watermark closeup
        output_basename = f"{record_id}_closeup_one"
        raw_path = download(photo_url, f"{output_basename}_raw.png")
        watermarked_path = None
        if raw_path and BRAND_WATERMARK_ENABLED:
            watermarked_path = make_watermarked_image(
                raw_path,
                record_id,
                output_basename=output_basename,
                extension=".jpg",
                watermark_path=BRAND_WATERMARK_PATH,
                line1=BRAND_WATERMARK_LINE1,
                line2=BRAND_WATERMARK_LINE2,
                width_ratio=BRAND_WATERMARK_WIDTH_RATIO,
                position=BRAND_WATERMARK_POSITION,
                horizontal_padding_ratio=BRAND_WATERMARK_HORIZONTAL_PADDING_RATIO,
                vertical_padding_ratio=BRAND_WATERMARK_VERTICAL_PADDING_RATIO,
                opacity=BRAND_WATERMARK_OPACITY,
                jpeg_quality=BRAND_WATERMARK_JPEG_QUALITY,
            )

        closeup_to_upload = watermarked_path if watermarked_path else raw_path

        # Upload both to Zoho
        suffix = _get_record_suffix(record_id, fields)
        folder_name = f"productcloseupphotos{suffix}"
        parent_key = "Product Closeup Photos"

        subfolder_id = get_or_create_folder(folder_name, parent_key)
        if subfolder_id:
            # Upload Blended Image to Zoho
            blended_filename = f"{record_id}_blended.jpg"
            upload_from_url(blended_url, blended_filename, subfolder_id)

            # Upload Closeup to Zoho and get public URL
            closeup_filename = f"{record_id}_closeup_one.jpg"
            closeup_public_url = upload_and_get_public_link(closeup_to_upload, subfolder_id)
        else:
            print(f"[ERROR] Failed to get or create Zoho subfolder '{folder_name}' under '{parent_key}'")
            closeup_public_url = photo_url

        # Upload both to Airtable Product Closeup Feeds
        attachments = [{"url": blended_url}, {"url": closeup_public_url}]
        _update_mapped_field(table_id, record_id, "Closeup Photo One", attachments)

        cleanup_temp_files(raw_path, watermarked_path)
        print("[OK] Phase 7 Closeup done.")

        if ui_callback:
            if watermarked_path and os.path.exists(watermarked_path):
                ui_callback("Phase 7: Closeup Generated", image_path=watermarked_path)
            else:
                ui_callback("Phase 7: Closeup Generated", image_path=raw_path)
        return

    # Standard two-item table logic below
    closeup_prompt = CLOSEUP_PROMPT_TEMPLATE.format(item=item_name)
    print(f"[INFO] Generating {label}: {closeup_prompt}")
    if ui_callback:
        ui_callback(f"⏳ {label}...", desc_text=f"Generating closeup of {item_name} from Blended Image...")

    blended_url = blended[0]["url"]
    task_id = create_blend_task([blended_url], closeup_prompt)
    if not task_id:
        update_status(table_id, record_id, f"Error - {label} Task Failed")
        return

    photo_url = poll_task_status(task_id)
    if not photo_url:
        update_status(table_id, record_id, f"Error - {label} Generation Failed")
        return

    # Persist raw closeup URL
    _update_mapped_field(table_id, record_id, f"{target_field} Raw URL", photo_url, silent=True)

    output_basename = f"{record_id}_{target_field.lower().replace(' ', '_')}"
    ui_image_path = _upload_image_output(
        table_id,
        record_id,
        target_field,
        target_field,
        photo_url,
        output_basename,
    )
    print(f"[OK] {label} done.")

    if ui_callback:
        if ui_image_path and os.path.exists(ui_image_path):
            ui_callback(f"{label} Generated", image_path=ui_image_path)
        else:
            import requests
            tmp_img = os.path.join(tempfile.gettempdir(), f"{output_basename}.png")
            try:
                with open(tmp_img, 'wb') as f:
                    f.write(requests.get(photo_url).content)
                ui_callback(f"{label} Generated", image_path=tmp_img)
            except Exception:
                pass



def _phase_combine_closeups(table_id: str, record_id: str, ui_callback=None) -> None:
    """Phase 9: Combine After Reels + Closeup One Video + Closeup Two Video."""
    fields = refetch_record(table_id, record_id)
    cu1_video = _get_mapped_field_val(record_id, fields, "Closeup Photo One Video", table_id)
    cu2_video = _get_mapped_field_val(record_id, fields, "Closeup Photo Two Video", table_id)
    after = _get_mapped_field_val(record_id, fields, "After Reels", table_id)
    combined = _get_mapped_field_val(record_id, fields, "Combine Video Closeups", table_id)

    if combined:
        print("[INFO] Combine Video Closeups already exists. Skipping.")
        return

    mapping = get_field_mapping(table_id)
    has_item2 = mapping.get("Furniture Item2") is not None

    if not (after and cu1_video):
        print("[WARN] Missing After Reels or Closeup One Video for combination. Skipping.")
        return
    if has_item2 and not cu2_video:
        print("[WARN] Missing Closeup Two Video for 2-item combination. Skipping.")
        return

    print("[INFO] Combining After Reels + Closeup Videos...")
    if ui_callback:
        ui_callback("⏳ Phase 9: Combining Closeup Videos...",
                     desc_text="Stitching After Reels + Closeup Videos...")

    cu1_path = download(cu1_video[0]["url"], f"{record_id}_closeup1.mp4")
    after_path = download(after[0]["url"], f"{record_id}_after_for_closeup.mp4")
    download_paths = [after_path, cu1_path]

    if has_item2:
        cu2_path = download(cu2_video[0]["url"], f"{record_id}_closeup2.mp4")
        if cu2_path:
            download_paths.append(cu2_path)

    if not all(download_paths):
        print("[WARN] Could not download all videos for closeup combination. Skipping.")
        cleanup_temp_files(*download_paths)
        return

    combined_path = combine(download_paths, f"{record_id}_combined_closeups_raw.mp4")
    if not combined_path:
        print("[WARN] Closeup video combination failed. Skipping.")
        cleanup_temp_files(*download_paths)
        return

    # Apply music to the combined closeup video
    final_combined_path = _apply_music(combined_path, record_id, "Combined Closeup Videos")

    combined_url = upload_and_get_public_link(final_combined_path, folder_key="Combined Closeup Videos")
    if combined_url:
        _update_mapped_attachment(table_id, record_id, "Combine Video Closeups", combined_url)
        print("[OK] Phase 9 (Combine Video Closeups) done.")
        if ui_callback:
            ui_callback("Phase 9: Closeup Videos Combined",
                         desc_text="Combined closeup + after reels video with music has been uploaded.")
    else:
        print("[WARN] Could not upload combined closeup video. Skipping.")

    cleanup_temp_files(*download_paths, combined_path,
                       final_combined_path if final_combined_path != combined_path else None)


# ── Phase 12: CTA ───────────────────────────────────────────

def _phase10_shop_now(table_id: str, record_id: str, ui_callback=None) -> None:
    """Phase 10: Stamp 'SHOP NOW' on the Blended Image and attach as 'CTA'."""
    fields = refetch_record(table_id, record_id)
    blended = _get_mapped_field_val(record_id, fields, "Blended Image", table_id)
    existing = _get_mapped_field_val(record_id, fields, "CTA", table_id)

    if existing:
        print("[INFO] CTA already populated. Skipping Phase 10.")
        return
    if not blended:
        print("[WARN] No Blended Image found. Cannot generate CTA.")
        return

    # Use the unwatermarked raw URL if available, fallback to the watermarked attachment
    raw_url_val = _get_mapped_field_val(record_id, fields, "Blended Image Raw URL", table_id)
    if raw_url_val and isinstance(raw_url_val, str) and raw_url_val.strip():
        blended_url = raw_url_val.strip()
    else:
        blended_url = blended[0]["url"]

    print(f"[INFO] Generating CTA image (text='{SHOP_NOW_TEXT}')...")
    if ui_callback:
        ui_callback(
            "⏳ Phase 10: Adding SHOP NOW...",
            desc_text="Drawing the SHOP NOW label onto the Blended Image...",
        )

    blended_path = download(blended_url, f"{record_id}_blended_for_cta.png")
    if not blended_path:
        print("[WARN] Could not download Blended Image. Skipping CTA.")
        return

    # Just add "SHOP NOW" directly to the Blended Image (no 9:16 crop)
    overlay_path = make_shop_now_image(blended_path, record_id, text=SHOP_NOW_TEXT)
    if not overlay_path:
        print("[WARN] SHOP NOW overlay failed. Skipping CTA.")
        cleanup_temp_files(blended_path)
        return

    final_cta_path = overlay_path


    # Attach the file directly to Airtable via the content API.
    attached = _upload_mapped_attachment_file(
        table_id,
        record_id,
        "CTA",
        final_cta_path,
        content_type="image/jpeg",
    )

    # Best-effort Zoho backup so the user still has a copy in the CTA folder.
    try:
        upload_local_file(final_cta_path, f"{record_id}_cta.jpg", "CTA")
    except Exception as e:
        print(f"[WARN] Zoho backup of CTA failed: {e}")

    if attached:
        print("[OK] Phase 10 (CTA) done.")
        if ui_callback:
            ui_callback(
                "Phase 10: CTA Built",
                desc_text="Final CTA image with SHOP NOW overlay uploaded to Airtable.",
                image_path=final_cta_path,
            )
    else:
        print("[WARN] CTA attachment upload to Airtable failed.")
        if ui_callback:
            ui_callback(
                "Phase 10: CTA Built (local only)",
                desc_text="Overlay rendered but Airtable upload failed.",
                image_path=final_cta_path,
            )

    cleanup_temp_files(blended_path, overlay_path, final_cta_path if final_cta_path != overlay_path else None)



# Phase 13: Polls and Slider deleted


def _get_recent_completed_records(table_id: str, exclude_record_id: str, limit: int = 2) -> list[dict]:
    """Retrieves up to `limit` completed records (having an 'After Reels' attachment) from the table, excluding the current record."""
    from services.airtable import list_records
    mapping = get_field_mapping(table_id)
    after_reels_field = mapping.get("After Reels", "After Reels")
    completed = []
    for rec in list_records(table_id):
        rec_id = rec.get("id")
        fields = rec.get("fields", {})
        if rec_id == exclude_record_id:
            continue
        if fields.get("Status") == "Complete" and fields.get(after_reels_field):
            completed.append(rec)
    return completed[-limit:]


def _phase11_tips_reels(table_id: str, record_id: str, fields: dict, ui_callback=None) -> None:
    """Phase 11: Generate a Tips Reels video and upload to Zoho."""
    print("[INFO] Skipping Phase 11: Tips Reels (temporarily disabled).")
    return

    print("[INFO] Starting Phase 11: Tips Reels...")
    
    # Check if Tips Reels already exists to support idempotency/skipping
    existing = _get_mapped_field_val(record_id, fields, "Tips Reels", table_id)
    if existing:
        print("[INFO] Phase 11: Tips Reels already exists. Skipping.")
        return

    # Use 'After Reels' mapped field (which is Styled Reels for this table)
    after_reels = _get_mapped_field_val(record_id, fields, "After Reels", table_id)
    blended = _get_mapped_field_val(record_id, fields, "Blended Image", table_id)
    
    if not after_reels or not blended:
        print(f"[WARN] Record {record_id} is missing Styled Reels (After Reels) or Blended Image. Skipping Phase 11.")
        return

    temp_files_to_cleanup = []
    
    after_reels_url = after_reels[0]["url"]
    blended_url = blended[0]["url"]

    if ui_callback:
        ui_callback("⏳ Phase 11: Gathering assets...", desc_text="Downloading video and image...")

    video_path = download(after_reels_url, f"{record_id}_styled_reels.mp4")
    blended_path = download(blended_url, f"{record_id}_blended.png")
    
    if not video_path or not blended_path:
        print("[ERROR] Phase 11 failed to download required assets.")
        cleanup_temp_files(video_path, blended_path)
        return
        
    temp_files_to_cleanup.extend([video_path, blended_path])

    if ui_callback:
        ui_callback(
            "⏳ Phase 11: Generating tip...",
            desc_text="Analyzing image with Vision LLM...",
            image_path=blended_path
        )
        
    from services.vision_llm import generate_styling_tip
    tip_text = generate_styling_tip(blended_path)
    print(f"[INFO] Tip generated: {tip_text}")

    voiceover_path = None
    if ui_callback:
        ui_callback(
            "⏳ Phase 11: Generating voiceover...",
            desc_text=f"TTS prompt: '{tip_text}' (Filipino Female Voice)"
        )
        
    from services.kie import create_voiceover_task
    # "ZnJRwODXspYo4KLSFKFc" is the ElevenLabs Voice ID for 'Carmela' (Filipino Female)
    filipino_voice_id = "ZnJRwODXspYo4KLSFKFc"
    vo_task = create_voiceover_task(tip_text, voice_id=filipino_voice_id)
    if vo_task:
        vo_url = poll_task_status(vo_task)
        if vo_url:
            voiceover_path = download(vo_url, f"{record_id}_tip_vo.mp3")
            if voiceover_path:
                temp_files_to_cleanup.append(voiceover_path)

    segment_out = os.path.join(tempfile.gettempdir(), f"{record_id}_tips_reel.mp4")
    from services.video import render_tips_reel_segment
    rendered_path = render_tips_reel_segment(video_path, segment_out, tip_text, voiceover_path)
    
    if not rendered_path:
        print("[ERROR] Failed to render tips reel.")
        cleanup_temp_files(*temp_files_to_cleanup)
        return
        
    temp_files_to_cleanup.append(rendered_path)

    # Optional: Add background music
    if ui_callback:
        ui_callback("⏳ Phase 11: Generating Suno background music...", desc_text="Creating a background music loop...")
        
    final_output_path = os.path.join(tempfile.gettempdir(), f"{record_id}_tips_reel_final.mp4")
    music_task = create_music_task(MUSIC_PROMPT)
    music_mixed = False
    if music_task:
        music_url = poll_task_status(music_task)
        if music_url:
            music_path = download(music_url, f"{record_id}_tips_music.mp3")
            if music_path:
                temp_files_to_cleanup.append(music_path)
                if ui_callback:
                    ui_callback("⏳ Phase 11: Mixing audio...", desc_text="Mixing voiceover with music at 15% volume...")
                from services.video import mix_background_music
                if mix_background_music(rendered_path, music_path, final_output_path, music_volume=0.15):
                    music_mixed = True
                    temp_files_to_cleanup.append(final_output_path)

    if not music_mixed:
        print("[WARN] Background music mix failed or skipped. Using un-mixed video as final.")
        final_output_path = rendered_path

    suffix = _get_record_suffix(record_id, fields)
    filename = f"tips_reel_{suffix}.mp4"
    if ui_callback:
        ui_callback("⏳ Phase 11: Uploading to Zoho...", desc_text=f"Filename: {filename}")
        
    upload_local_file(final_output_path, filename, "Tips Reels")
    
    # Upload to Airtable Tips Reels
    _upload_mapped_attachment_file(table_id, record_id, "Tips Reels", final_output_path, content_type="video/mp4")

    cleanup_temp_files(*temp_files_to_cleanup)
    print(f"[OK] Phase 11 (Tips Reels) done. Video uploaded: {filename}")
    if ui_callback:
        ui_callback("Phase 11: Tips Reels Uploaded", desc_text=f"Video uploaded to Zoho: {filename}")


def _phase12_styled_stories(table_id: str, record_id: str, ui_callback=None) -> None:
    """Phase 12: Fit Blended Image to 9:16 layout, add brand watermark, and upload to Zoho."""
    fields = refetch_record(table_id, record_id)
    blended = _get_mapped_field_val(record_id, fields, "Blended Image", table_id)
    if not blended:
        print("[WARN] No Blended Image found. Cannot generate Styled Stories.")
        return

    blended_url = blended[0]["url"]
    print("[INFO] Generating Styled Stories image...")
    if ui_callback:
        ui_callback("⏳ Phase 12: Processing Styled Stories...", desc_text="Cropping Blended Image to 9:16 & watermarking...")

    blended_path = download(blended_url, f"{record_id}_blended_for_styled_stories.png")
    if not blended_path:
        print("[WARN] Could not download Blended Image. Skipping Styled Stories.")
        return

    suffix = _get_record_suffix(record_id, fields)
    temp_dir = tempfile.gettempdir()
    fitted_path = os.path.join(temp_dir, f"{record_id}_styled_stories_fitted.png")

    if not fit_image_to_9_16(blended_path, fitted_path):
        print("[ERROR] Failed to fit image to 9:16 for Styled Stories")
        cleanup_temp_files(blended_path)
        return

    watermarked_path = make_watermarked_image(
        fitted_path,
        record_id,
        output_basename=f"{record_id}_styled_stories",
        extension=".jpg",
        watermark_path=BRAND_WATERMARK_PATH,
        line1=BRAND_WATERMARK_LINE1,
        line2=BRAND_WATERMARK_LINE2,
        width_ratio=BRAND_WATERMARK_WIDTH_RATIO,
        position=BRAND_WATERMARK_POSITION,
        horizontal_padding_ratio=BRAND_WATERMARK_HORIZONTAL_PADDING_RATIO,
        vertical_padding_ratio=BRAND_WATERMARK_VERTICAL_PADDING_RATIO,
        opacity=BRAND_WATERMARK_OPACITY,
        jpeg_quality=BRAND_WATERMARK_JPEG_QUALITY,
    )

    if watermarked_path:
        filename = f"styled_stories_{suffix}.jpg"
        upload_local_file(watermarked_path, filename, "Styled Stories")
        
        # Upload to Airtable Styled Stories
        _upload_mapped_attachment_file(table_id, record_id, "Tips and Edu Stories", watermarked_path, content_type="image/jpeg")

        if ui_callback:
            ui_callback("Phase 12: Styled Stories Complete", image_path=watermarked_path)
    else:
        print("[WARN] Watermarking failed for Styled Stories.")

    cleanup_temp_files(blended_path, fitted_path, watermarked_path)


# Phase 16: Sliders deleted


def _get_record_suffix(record_id: str, fields: dict) -> str:
    """Helper to extract a zero-padded/formatted folder name suffix from Airtable ID or fallback."""
    id_val = fields.get("ID")
    suffix = ""
    if id_val is not None:
        try:
            int_id = int(float(id_val))
            if int_id >= 0:
                suffix = str(int_id).zfill(2) if int_id < 10 else str(int_id)
            else:
                suffix = str(int_id)
        except (ValueError, TypeError):
            suffix = str(id_val).strip()

    if not suffix:
        suffix = record_id
    return suffix


def _mirror_before_after_feeds(table_id: str, record_id: str, fields: dict, ui_callback=None) -> None:
    """
    Creates a subfolder named 'beforeandafter{suffix}' under the 'Before and After Feeds' parent folder,
    and uploads 'Styled Photo' and 'Blended Image' into it. Also uploads them to Airtable Before and After Feeds field.
    """
    suffix = _get_record_suffix(record_id, fields)
    folder_name = f"beforeandafter{suffix}"
    parent_key = "Before and After Feeds"

    if ui_callback:
        ui_callback(f"⏳ Mirroring to '{folder_name}'...", desc_text="Checking/creating Zoho subfolder...")

    subfolder_id = get_or_create_folder(folder_name, parent_key)
    if not subfolder_id:
        print(f"[ERROR] Failed to get or create Zoho subfolder '{folder_name}' under '{parent_key}'")
        return

    styled_photos = _get_mapped_field_val(record_id, fields, "Styled Photo", table_id)
    blended_images = _get_mapped_field_val(record_id, fields, "Blended Image", table_id)

    # ── Upload to Airtable Before and After Feeds attachment field side-by-side ──
    mapping = get_field_mapping(table_id)
    feed_field = mapping.get("Before and After Feeds")
    if feed_field:
        existing_feeds = fields.get(feed_field)
        if not existing_feeds:
            attachments = []
            if styled_photos:
                attachments.append({"url": styled_photos[0]["url"]})
            if blended_images:
                attachments.append({"url": blended_images[0]["url"]})
            if attachments:
                _update_mapped_field(table_id, record_id, "Before and After Feeds", attachments)

    if not styled_photos:
        print(f"[WARN] No 'Styled Photo' attachment found in fields for record {record_id}")
    else:
        for idx, item in enumerate(styled_photos):
            url = item.get("url")
            filename = item.get("filename") or f"{record_id}_styled_photo.jpg"
            if len(styled_photos) > 1:
                base, ext = os.path.splitext(filename)
                filename = f"{base}_{idx}{ext}"
            if url:
                if ui_callback:
                    ui_callback(f"⏳ Uploading Styled Photo to '{folder_name}'...", desc_text=f"Filename: {filename}")
                upload_from_url(url, filename, subfolder_id)

    if not blended_images:
        print(f"[WARN] No 'Blended Image' attachment found in fields for record {record_id}")
    else:
        for idx, item in enumerate(blended_images):
            url = item.get("url")
            filename = item.get("filename") or f"{record_id}_blended.jpg"
            if len(blended_images) > 1:
                base, ext = os.path.splitext(filename)
                filename = f"{base}_{idx}{ext}"
            if url:
                if ui_callback:
                    ui_callback(f"⏳ Uploading Blended Image to '{folder_name}'...", desc_text=f"Filename: {filename}")
                upload_from_url(url, filename, subfolder_id)


def _mirror_product_closeup_photos(table_id: str, record_id: str, fields: dict, ui_callback=None) -> None:
    """
    Creates a subfolder named 'productcloseupphotos{suffix}' under the 'Product Closeup Photos' parent folder,
    and uploads closeup photos and Blended Image into it.
    """
    if table_id == "tblDDmCs4S2ePxIfQ":
        # Already handled directly inside Phase 7 closeup photo phase
        return

    suffix = _get_record_suffix(record_id, fields)
    folder_name = f"productcloseupphotos{suffix}"
    parent_key = "Product Closeup Photos"

    if ui_callback:
        ui_callback(f"⏳ Mirroring to '{folder_name}'...", desc_text="Checking/creating Zoho subfolder...")

    subfolder_id = get_or_create_folder(folder_name, parent_key)
    if not subfolder_id:
        print(f"[ERROR] Failed to get or create Zoho subfolder '{folder_name}' under '{parent_key}'")
        return

    closeup_one = _get_mapped_field_val(record_id, fields, "Closeup Photo One", table_id)
    closeup_two = _get_mapped_field_val(record_id, fields, "Closeup Photo Two", table_id)
    blended_images = _get_mapped_field_val(record_id, fields, "Blended Image", table_id)

    mapping = get_field_mapping(table_id)
    cu1_field = mapping.get("Closeup Photo One")
    cu2_field = mapping.get("Closeup Photo Two")

    if cu1_field and cu1_field == cu2_field:
        # Shared closeup field (e.g. Product Closeup Feeds)
        if closeup_one:
            for idx, item in enumerate(closeup_one):
                url = item.get("url")
                filename = f"{record_id}_closeup_{idx+1}.jpg"
                if url:
                    if ui_callback:
                        ui_callback(f"⏳ Uploading Closeup {idx+1} to '{folder_name}'...", desc_text=f"Filename: {filename}")
                    upload_from_url(url, filename, subfolder_id)
    else:
        # Separate fields
        if not closeup_one:
            print(f"[WARN] No 'Closeup Photo One' attachment found in fields for record {record_id}")
        else:
            for idx, item in enumerate(closeup_one):
                url = item.get("url")
                filename = item.get("filename") or f"{record_id}_closeup_one.jpg"
                if len(closeup_one) > 1:
                    base, ext = os.path.splitext(filename)
                    filename = f"{base}_{idx}{ext}"
                if url:
                    if ui_callback:
                        ui_callback(f"⏳ Uploading Closeup Photo One to '{folder_name}'...", desc_text=f"Filename: {filename}")
                    upload_from_url(url, filename, subfolder_id)

        if not closeup_two:
            print(f"[WARN] No 'Closeup Photo Two' attachment found in fields for record {record_id}")
        else:
            for idx, item in enumerate(closeup_two):
                url = item.get("url")
                filename = item.get("filename") or f"{record_id}_closeup_two.jpg"
                if len(closeup_two) > 1:
                    base, ext = os.path.splitext(filename)
                    filename = f"{base}_{idx}{ext}"
                if url:
                    if ui_callback:
                        ui_callback(f"⏳ Uploading Closeup Photo Two to '{folder_name}'...", desc_text=f"Filename: {filename}")
                    upload_from_url(url, filename, subfolder_id)

    if not blended_images:
        print(f"[WARN] No 'Blended Image' attachment found in fields for record {record_id}")
    else:
        for idx, item in enumerate(blended_images):
            url = item.get("url")
            filename = item.get("filename") or f"{record_id}_blended.jpg"
            if len(blended_images) > 1:
                base, ext = os.path.splitext(filename)
                filename = f"{base}_{idx}{ext}"
            if url:
                if ui_callback:
                    ui_callback(f"⏳ Uploading Blended Image to '{folder_name}'...", desc_text=f"Filename: {filename}")
                upload_from_url(url, filename, subfolder_id)


# ── Main Orchestrator ───────────────────────────────────────────────

def process_one_row(table_id: str, blend_prompt: str,
                    item1: str = "", item2: str = "",
                    ui_callback=None) -> bool:
    """
    Picks the next unfinished row and runs all phases sequentially.
    Returns True if a row was processed, False if no work was found.
    """
    record_id, fields = get_next_unfinished_row(table_id)
    if not record_id:
        return False

    status = fields.get("Status", "")
    print(f"\n[ROW] Processing {record_id} (status: {status})")
    if ui_callback:
        ui_callback(f"📌 Record Found: {record_id}", desc_text=f"Current status: {status}. Starting pipeline...")

    if table_id == "tblDDmCs4S2ePxIfQ":
        _phase_room_interior(table_id, record_id, fields, ui_callback)
        return True

    # Phase 0: Prompt Generation
    if status == "Standby":
        status = _phase0_prompt(table_id, record_id, fields, ui_callback)
        if not status:
            return True  # row was touched but errored

    # Phase 1: Styled Photo
    if status == "Complete Adding a Prompt":
        status = _phase1_styled_photo(table_id, record_id, ui_callback)
        if not status:
            return True

    # Phases 2–16 only run when status is "Processing"
    if status == "Processing":
        if ui_callback:
            ui_callback("Processing Video & Blends", desc_text="Starting the blend & video rendering phases...")
        _phase2_blend(table_id, record_id, blend_prompt, ui_callback)
        _phase2_5_before_after_feeds(table_id, record_id, ui_callback)
        _phase3_moodboard(table_id, record_id, ui_callback)

        _phase_video(
            table_id, record_id,
            source_field="Styled Photo", target_field="Before Reels",
            prompt=BEFORE_REELS_PROMPT, zoho_folder="Before Reels",
            label="Before Reels",
            apply_music=False,
            source_url_field="Styled Photo Raw URL",
            ui_callback=ui_callback
        )
        _phase_video(
            table_id, record_id,
            source_field="Blended Image", target_field="After Reels",
            prompt=AFTER_REELS_PROMPT, zoho_folder="After Reels",
            label="After Reels",
            source_url_field="Blended Image Raw URL",
            ui_callback=ui_callback
        )

        _phase6_combine_reels(table_id, record_id, ui_callback)

        # Phase 7: Closeup Photo One
        if item1:
            _phase_closeup_photo(
                table_id, record_id,
                item_name=item1, target_field="Closeup Photo One",
                label="Phase 7: Closeup Photo One",
                ui_callback=ui_callback,
                closeup_idx=1
            )

        # Phase 7 (optional Closeup Photo Two for standard tables)
        if item2:
            _phase_closeup_photo(
                table_id, record_id,
                item_name=item2, target_field="Closeup Photo Two",
                label="Phase 7: Closeup Photo Two",
                ui_callback=ui_callback,
                closeup_idx=2
            )

        # Phase 8: Closeup Photo One Video
        _phase_video(
            table_id, record_id,
            source_field="Closeup Photo One", target_field="Closeup Photo One Video",
            prompt=CLOSEUP_VIDEO_PROMPT, zoho_folder="Closeup Photo One Video",
            label="Phase 8: Closeup Photo One Video",
            apply_music=False,
            source_url_field="Closeup Photo One Raw URL",
            ui_callback=ui_callback
        )

        # Phase 8 (optional Closeup Photo Two Video for standard tables)
        if item2:
            _phase_video(
                table_id, record_id,
                source_field="Closeup Photo Two", target_field="Closeup Photo Two Video",
                prompt=CLOSEUP_VIDEO_PROMPT, zoho_folder="Closeup Photo Two Video",
                label="Phase 8: Closeup Photo Two Video",
                apply_music=False,
                source_url_field="Closeup Photo Two Raw URL",
                ui_callback=ui_callback
            )

        # Phase 9: Combine Closeup Videos
        _phase_combine_closeups(table_id, record_id, ui_callback)

        # Phase 10: CTA (Blended Image + SHOP NOW overlay)
        _phase10_shop_now(table_id, record_id, ui_callback)

        # Phase 11: Tips Reels
        _phase11_tips_reels(table_id, record_id, fields, ui_callback)

        # Phase 12: Styled Stories
        _phase12_styled_stories(table_id, record_id, ui_callback)

        # Refetch final record fields to ensure we get all completed attachments (with public URLs)
        final_fields = refetch_record(table_id, record_id)
        if final_fields:
            if ui_callback:
                ui_callback("⏳ Mirroring files to Zoho folders...", desc_text="Starting Zoho subfolder mirroring...")
            _mirror_product_closeup_photos(table_id, record_id, final_fields, ui_callback=ui_callback)

    # Mark complete
    update_status(table_id, record_id, "Complete")
    print(f"[DONE] Record {record_id} fully completed!")
    return True
