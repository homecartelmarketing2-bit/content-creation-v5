import mimetypes
import os
import shutil
import sys
import time

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

import config.settings as settings
from services.airtable import (
    get_next_empty_reference_row,
    refetch_record,
    update_field,
    update_status,
    upload_attachment_file,
)
from services.image_overlay import make_watermarked_image
from services.fal_image import generate_room_interiors
from services.kie import create_gpt_image_task, query_task_once
from services.video import cleanup_temp_files, download
from services.pinterest_scraper import scrape_pinterest_photos
from services.vision_llm import evaluate_photo_quality, generate_prompt


TABLE_ID = "tblDDmCs4S2ePxIfQ"
BATCH_SIZE = 30
VALID_EXTS = (".jpg", ".jpeg", ".png", ".webp")
BLEND_PROMPT = (
    "Seamlessly blend and install the chandelier from the Furniture Item image into this Room Interior. "
    "Replace any existing chandelier, pendant, or ceiling fixture in the room. Keep the chandelier realistic, "
    "properly scaled for the room, securely connected to the ceiling, and matched to the room perspective, "
    "lighting, shadows, and color tone."
)


def _content_type(path: str) -> str:
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "image/jpeg"


def _move_unique(src_path: str, dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    filename = os.path.basename(src_path)
    base, ext = os.path.splitext(filename)
    dest_path = os.path.join(dest_dir, filename)
    counter = 1
    while os.path.exists(dest_path):
        dest_path = os.path.join(dest_dir, f"{base}_{counter}{ext}")
        counter += 1
    shutil.move(src_path, dest_path)
    return dest_path


def _append_blended_attachment(record_id: str, image_url: str, idx: int) -> bool:
    raw_path = download(image_url, f"{record_id}_blended_{idx}_raw.png")
    if not raw_path:
        print(f"[WARN] Could not download blend {idx}; attaching raw URL instead.")
        fields = refetch_record(TABLE_ID, record_id)
        existing = fields.get("Blended Image") or []
        return update_field(TABLE_ID, record_id, "Blended Image", existing + [{"url": image_url}])

    watermarked_path = make_watermarked_image(
        raw_path,
        record_id,
        output_basename=f"{record_id}_blended_{idx}",
        extension=".jpg",
        watermark_path=settings.BRAND_WATERMARK_PATH,
        line1=settings.BRAND_WATERMARK_LINE1,
        line2=settings.BRAND_WATERMARK_LINE2,
        width_ratio=settings.BRAND_WATERMARK_WIDTH_RATIO,
        position=settings.BRAND_WATERMARK_POSITION,
        horizontal_padding_ratio=settings.BRAND_WATERMARK_HORIZONTAL_PADDING_RATIO,
        vertical_padding_ratio=settings.BRAND_WATERMARK_VERTICAL_PADDING_RATIO,
        opacity=settings.BRAND_WATERMARK_OPACITY,
        jpeg_quality=settings.BRAND_WATERMARK_JPEG_QUALITY,
    )

    if not watermarked_path:
        print(f"[WARN] Could not watermark blend {idx}; attaching raw URL instead.")
        fields = refetch_record(TABLE_ID, record_id)
        existing = fields.get("Blended Image") or []
        cleanup_temp_files(raw_path)
        return update_field(TABLE_ID, record_id, "Blended Image", existing + [{"url": image_url}])

    attached = upload_attachment_file(
        record_id,
        "Blended Image",
        watermarked_path,
        content_type="image/jpeg",
    )
    cleanup_temp_files(raw_path, watermarked_path)
    return attached


def _run_blended_images(record_id: str, room_urls: list[str], furniture_url: str) -> bool:
    print(f"[INFO] Starting {len(room_urls)} GPT Image 2 blend task(s)...")
    pending: dict[str, int] = {}
    completed_count = 0

    for idx, room_url in enumerate(room_urls, start=1):
        task_id = create_gpt_image_task(
            [room_url, furniture_url],
            BLEND_PROMPT,
            aspect_ratio="3:4",
            resolution="1K",
        )
        if task_id:
            pending[task_id] = idx
            print(f"[OK] Blend task {idx} created: {task_id[:12]}")
        else:
            print(f"[WARN] Blend task {idx} could not be created.")

    if not pending:
        print("[STOP] No blend tasks were created.")
        return False

    start = time.time()
    while pending:
        for task_id, idx in list(pending.items()):
            state, url = query_task_once(task_id)
            if state == "pending" or state == "error":
                continue

            pending.pop(task_id, None)
            if state == "success" and url:
                if _append_blended_attachment(record_id, url, idx):
                    completed_count += 1
                    print(f"[OK] Blend task {idx} complete. Watermarked image attached to Blended Image ({completed_count}/{len(room_urls)}).")
                else:
                    print(f"[WARN] Blend task {idx} completed but Airtable upload failed.")
            else:
                print(f"[WARN] Blend task {idx} failed.")

        if pending:
            elapsed = int(time.time() - start)
            if elapsed >= settings.POLL_MAX_WAIT:
                print(f"[STOP] Blend polling timed out after {elapsed}s with {len(pending)} task(s) still pending.")
                break
            print(f"[WAIT] {len(pending)} blend task(s) still running ({elapsed}s elapsed)...")
            time.sleep(settings.POLL_INTERVAL)

    return completed_count == len(room_urls)


def _attach_approved_photo_to_airtable(photo_path: str) -> bool:
    print("[INFO] Generating Styled Photo Prompt from approved photo...")
    prompt = generate_prompt(photo_path)
    if not prompt:
        print("[STOP] Vision LLM could not describe this approved photo. Leaving it in Approved.")
        return False

    record_id, fields = get_next_empty_reference_row(TABLE_ID)
    if not record_id:
        print("[STOP] No empty Airtable row found with Furniture Item and empty output fields.")
        return False

    furniture_items = fields.get("Furniture Item") or []
    furniture_url = furniture_items[0].get("url") if furniture_items else None
    if not furniture_url:
        print("[STOP] Airtable row has no usable Furniture Item URL.")
        return False

    print(f"[INFO] Assigning approved photo to Airtable row {record_id}...")
    update_status(TABLE_ID, record_id, "Processing Adding a Prompt")

    if not upload_attachment_file(
        record_id,
        "Reference Photo",
        photo_path,
        content_type=_content_type(photo_path),
    ):
        update_status(TABLE_ID, record_id, "Standby")
        return False

    if not update_field(TABLE_ID, record_id, "Styled Photo Prompt", prompt):
        update_status(TABLE_ID, record_id, "Standby")
        return False

    print("[INFO] Generating 4 Room Interior images from Styled Photo Prompt...")
    urls = generate_room_interiors(prompt)
    if len(urls) < settings.FAL_NUM_IMAGES:
        print(f"[STOP] FAL returned {len(urls)} image(s); expected {settings.FAL_NUM_IMAGES}.")
        update_status(TABLE_ID, record_id, "Standby")
        return False

    if not update_field(TABLE_ID, record_id, "Room Interior", [{"url": url} for url in urls]):
        update_status(TABLE_ID, record_id, "Standby")
        return False

    if not _run_blended_images(record_id, urls, furniture_url):
        update_status(TABLE_ID, record_id, "Standby")
        print("[STOP] No Blended Image output completed for this row.")
        return False

    update_status(TABLE_ID, record_id, "Complete Adding a Prompt")
    print(f"[OK] Airtable row {record_id} now has Reference Photo, Styled Photo Prompt, Room Interior, and Blended Image.")
    return True


def run_scrape():
    load_dotenv(override=True)

    base_dir = os.path.join(settings.PROJECT_ROOT, "Chandelier Scrape")
    scrape_dir = os.path.join(base_dir, "Scrape Photos")
    approved_dir = os.path.join(base_dir, "Approved")
    disregard_dir = os.path.join(base_dir, "Disregard")

    os.makedirs(scrape_dir, exist_ok=True)
    os.makedirs(approved_dir, exist_ok=True)
    os.makedirs(disregard_dir, exist_ok=True)

    # Override settings so scraper uses the Chandelier-specific folder.
    import services.pinterest_scraper

    services.pinterest_scraper.MARKETING_PHOTO_DIR = scrape_dir
    settings.MARKETING_PHOTO_DIR = scrape_dir

    print("=== Running Chandelier Reference Pipeline ===")
    print(f"Method: {os.environ.get('PINTEREST_SCRAPER_METHOD')}")
    print(f"Keyword: {os.environ.get('PINTEREST_SEARCH_TERMS')}")
    print(f"Target scrape batch: {BATCH_SIZE} photos")
    print(f"Download Directory: {scrape_dir}")

    res = scrape_pinterest_photos(limit=BATCH_SIZE)
    print("\nScrape Result:", res)

    filenames = [
        filename for filename in sorted(os.listdir(scrape_dir))
        if filename.lower().endswith(VALID_EXTS)
    ][:BATCH_SIZE]

    if not filenames:
        print("[INFO] No scraped photos found to evaluate.")
        return

    print(f"\n=== Running Quality Evaluation on {len(filenames)} photo(s) ===")
    for filename in filenames:
        file_path = os.path.join(scrape_dir, filename)
        print(f"\nEvaluating: {filename}")

        eval_result = evaluate_photo_quality(file_path, item_name="Chandelier")
        if not eval_result:
            print("[STOP] LLM evaluation failed or timed out. Photo left in Scrape Photos.")
            return

        is_beautiful = bool(eval_result.get("is_beautiful", False))
        reason = eval_result.get("reason", "No reason provided")
        score = eval_result.get("aesthetic_score", "?")
        failed_step = eval_result.get("failed_step", "Unknown")

        print(f"  Result: {'APPROVED' if is_beautiful else 'REJECTED'}")
        print(f"  Score: {score}/10")
        print(f"  Failed Step: {failed_step}")
        print(f"  Reason: {reason}")

        if not is_beautiful:
            rejected_path = _move_unique(file_path, disregard_dir)
            print(f"  -> Moved to Disregard: {os.path.basename(rejected_path)}")
            continue

        approved_path = _move_unique(file_path, approved_dir)
        print(f"  -> Moved to Approved: {os.path.basename(approved_path)}")

        if not _attach_approved_photo_to_airtable(approved_path):
            print("[STOP] Approved photo was not fully processed into Airtable. Stopping for manual retry.")
            return


if __name__ == "__main__":
    run_scrape()
