# =====================================================================
#  PIPELINE
#  Picks one unfinished Airtable row and drives it through all phases:
#    Phase 0   →  Generate Prompt (local Vision LLM)
#    Phase 1   →  Styled Photo   (Kie.ai text-to-image)
#    Phase 2   →  Blend          (Styled Photo + Furniture Items)
#    Phase 3   →  Moodboard      (from Blended Image)
#    Phase 4   →  Before Reels   (video from Styled Photo)
#    Phase 5   →  After Reels    (video from Blended Image)
#    Phase 6   →  Combined Reels (Before + After stitched)
#    Phase 7   →  Closeup Photo One  (from Blended Image)
#    Phase 8   →  Closeup Photo Two  (from Blended Image)
#    Phase 9   →  Closeup Photo One Video
#    Phase 10  →  Closeup Photo Two Video
#    Phase 11  →  Combine Closeup Videos (Closeup1 + Closeup2 + After Reels)
#    Phase 12  →  Shop Now Image (Blended Image + "SHOP NOW" overlay)
#    Phase 13  →  Polls and Slider (LLM-generated A/B poll, rendered by nano-banana)
# =====================================================================

from config.prompts import (
    MOODBOARD_PROMPT, BEFORE_REELS_PROMPT, AFTER_REELS_PROMPT,
    CLOSEUP_PROMPT_TEMPLATE, CLOSEUP_VIDEO_PROMPT, MUSIC_PROMPT,
    POLL_IMAGE_PROMPT_TEMPLATE,
)
from config.settings import SHOP_NOW_TEXT

from services.airtable import (
    get_next_unfinished_row,
    refetch_record,
    update_status,
    update_field,
    update_attachment,
)
from services.kie import (
    create_image_task, create_blend_task, create_video_task,
    create_music_task, poll_task_status
)
from services.zoho import upload_from_url, upload_and_get_public_link
from services.vision_llm import get_random_local_photo, generate_prompt, generate_poll
from services.pinterest_scraper import ensure_marketing_photos
from services.video import download, combine, add_audio_to_video, cleanup_temp_files
from services.image_overlay import make_shop_now_image


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


# ── Phase Runners ───────────────────────────────────────────────────
# Each phase returns the new status string so the pipeline can flow.

def _phase0_prompt(table_id: str, record_id: str, fields: dict, ui_callback=None) -> str | None:
    """Phase 0: Generate a styled-photo prompt via the local Vision LLM."""
    prompt = fields.get("Styled Photo Prompt", "")
    photo_path = None
    generated = None

    if not prompt:
        update_status(table_id, record_id, "Processing Adding a Prompt")
        print("[INFO] Preparing fresh Pinterest reference photos...")
        if ui_callback:
            ui_callback(
                "Phase 0: Preparing Pinterest photos",
                desc_text="Checking the marketing photo folder and scraping fresh Pinterest images if needed.",
            )

        scrape_result = ensure_marketing_photos()
        if scrape_result.get("scraped"):
            print(
                f"[OK] Pinterest scrape added {scrape_result.get('downloaded', 0)} "
                f"new photo(s). Folder now has {scrape_result.get('available', 0)} photo(s)."
            )
        elif scrape_result.get("error"):
            print(f"[WARN] Pinterest scrape warning: {scrape_result['error']}")

        print("[INFO] Generating prompt from marketing photo...")

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

        update_field(table_id, record_id, "Styled Photo Prompt", generated)

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
    prompt = fields.get("Styled Photo Prompt", "")

    if not prompt:
        update_status(table_id, record_id, "Error - No Prompt")
        return None

    update_status(table_id, record_id, "Processing")
    print("[INFO] Generating Styled Photo...")
    if ui_callback:
        ui_callback("⏳ Phase 1: Generating Styled Photo...", desc_text=f"Sending prompt to Kie.ai: {prompt[:80]}...")

    task_id = create_image_task(prompt)
    if not task_id:
        update_status(table_id, record_id, "Error - Styled Photo Task Failed")
        return None

    image_url = poll_task_status(task_id)
    if not image_url:
        update_status(table_id, record_id, "Error - Styled Photo Generation Failed")
        return None

    update_attachment(table_id, record_id, "Styled Photo", image_url)
    saved_path = f"{record_id}_styled_photo.png"
    upload_from_url(image_url, saved_path, "Styled Photo")
    print("[OK] Phase 1 (Styled Photo) done.")
    
    if ui_callback:
        # Assuming upload_from_url saves it locally first or we need to download it for UI.
        # Temp downlaod for UI since upload_from_url handles Zoho, we'll use requests quickly.
        import requests, os
        import tempfile
        tmp_img = os.path.join(tempfile.gettempdir(), saved_path)
        try:
             with open(tmp_img, 'wb') as f:
                 f.write(requests.get(image_url).content)
             ui_callback("Phase 1: Styled Photo", image_path=tmp_img)
        except:
             pass

    return "Processing"


def _phase2_blend(table_id: str, record_id: str, blend_prompt: str, ui_callback=None) -> None:
    """Phase 2: Blend the styled photo with furniture items."""
    fields = refetch_record(table_id, record_id)
    styled = fields.get("Styled Photo")
    furn1 = fields.get("Furniture Item")
    furn2 = fields.get("Furniture Item2")
    blended = fields.get("Blended Image")

    if blended:
        print("[INFO] Blended Image already exists. Skipping.")
        return
    if not (styled and furn1 and furn2):
        print("[WARN] Missing Styled Photo or Furniture Items. Skipping blend.")
        return

    print("[INFO] Blending images...")
    image_urls = [styled[0]["url"], furn1[0]["url"], furn2[0]["url"]]
    if ui_callback:
        ui_callback("⏳ Phase 2: Blending Images...", desc_text="Merging Styled Photo + 2 Furniture Items via Kie.ai...")

    task_id = create_blend_task(image_urls, blend_prompt)
    if not task_id:
        update_status(table_id, record_id, "Error - Blend Task Failed")
        return

    blended_url = poll_task_status(task_id)
    if not blended_url:
        update_status(table_id, record_id, "Error - Blend Generation Failed")
        return

    update_attachment(table_id, record_id, "Blended Image", blended_url)
    saved_path = f"{record_id}_blended.png"
    upload_from_url(blended_url, saved_path, "Blended Image")
    print("[OK] Phase 2 (Blend) done.")
    
    if ui_callback:
        import requests, os
        import tempfile
        tmp_img = os.path.join(tempfile.gettempdir(), saved_path)
        try:
             with open(tmp_img, 'wb') as f:
                 f.write(requests.get(blended_url).content)
             ui_callback("Phase 2: Blended Image", image_path=tmp_img)
        except:
             pass


def _phase3_moodboard(table_id: str, record_id: str, ui_callback=None) -> None:
    """Phase 3: Generate a moodboard from the blended image."""
    fields = refetch_record(table_id, record_id)
    blended = fields.get("Blended Image")
    moodboard = fields.get("Moodboard Image")

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

    task_id = create_blend_task([blended_url], MOODBOARD_PROMPT)
    if not task_id:
        update_status(table_id, record_id, "Error - Moodboard Task Failed")
        return

    moodboard_url = poll_task_status(task_id)
    if not moodboard_url:
        update_status(table_id, record_id, "Error - Moodboard Generation Failed")
        return

    update_attachment(table_id, record_id, "Moodboard Image", moodboard_url)
    saved_path = f"{record_id}_moodboard.png"
    upload_from_url(moodboard_url, saved_path, "Moodboard")
    print("[OK] Phase 3 (Moodboard) done.")
    
    if ui_callback:
        import requests, os
        import tempfile
        tmp_img = os.path.join(tempfile.gettempdir(), saved_path)
        try:
             with open(tmp_img, 'wb') as f:
                 f.write(requests.get(moodboard_url).content)
             ui_callback("Phase 3: Moodboard", image_path=tmp_img)
        except:
             pass


def _phase_video(table_id: str, record_id: str,
                 source_field: str, target_field: str,
                 prompt: str, zoho_folder: str, label: str,
                 apply_music: bool = True,
                 ui_callback=None) -> None:
    """Generic video-from-image phase (used for Before & After Reels).

    When `apply_music` is False the raw Kling video is uploaded as-is
    (no Suno track). Music is intentionally skipped for the per-item
    closeup videos so it can be applied later on the combined cut.
    """
    fields = refetch_record(table_id, record_id)
    source = fields.get(source_field)
    existing = fields.get(target_field)

    if existing:
        print(f"[INFO] {label} already exists. Skipping.")
        return
    if not source:
        return

    print(f"[INFO] Generating {label} video...")
    source_url = source[0]["url"]
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
            update_attachment(table_id, record_id, target_field, final_url)
        else:
            # Fallback to raw video if upload fails
            update_attachment(table_id, record_id, target_field, video_url)
            upload_from_url(video_url, f"{record_id}_{label.lower().replace(' ', '_')}.mp4", zoho_folder)
            
        # Cleanup
        cleanup_temp_files(temp_video, final_video_path if final_video_path != temp_video else None)
    else:
        # Fallback if download fails
        update_attachment(table_id, record_id, target_field, video_url)
        upload_from_url(video_url, f"{record_id}_{label.lower().replace(' ', '_')}.mp4", zoho_folder)

    print(f"[OK] {label} done.")
    
    if ui_callback:
        ui_callback(f"Phase Video: {label} Built", desc_text=f"Video generated successfully for {label}.")


def _phase6_combine_reels(table_id: str, record_id: str, ui_callback=None) -> None:
    """Phase 6: Stitch Before + After Reels into one video."""
    fields = refetch_record(table_id, record_id)
    before = fields.get("Before Reels")
    after = fields.get("After Reels")
    combined = fields.get("Combine Video Before and After")

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

    combined_url = upload_and_get_public_link(final_combined_path, "Before and After Reels")
    if combined_url:
        update_attachment(table_id, record_id, "Combine Video Before and After", combined_url)
        print("[OK] Phase 6 (Combined Reels) done.")
        if ui_callback:
            ui_callback("Phase 6: Combined Reels Compiled", desc_text="Final stitched reels video with music has been uploaded.")
    else:
        print("[WARN] Could not upload combined video. Skipping.")

    cleanup_temp_files(before_path, after_path, combined_path, 
                       final_combined_path if final_combined_path != combined_path else None)


# ── Closeup Phases ─────────────────────────────────────────────────

def _phase_closeup_photo(table_id: str, record_id: str,
                         item_name: str, target_field: str,
                         label: str, ui_callback=None) -> None:
    """Generates a closeup photo of an item from the Blended Image."""
    fields = refetch_record(table_id, record_id)
    blended = fields.get("Blended Image")
    existing = fields.get(target_field)

    if existing:
        print(f"[INFO] {label} already exists. Skipping.")
        return
    if not blended:
        print(f"[WARN] No Blended Image found. Cannot generate {label}.")
        return

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

    update_attachment(table_id, record_id, target_field, photo_url)
    saved_path = f"{record_id}_{target_field.lower().replace(' ', '_')}.png"
    upload_from_url(photo_url, saved_path, target_field)
    print(f"[OK] {label} done.")

    if ui_callback:
        import requests, os, tempfile
        tmp_img = os.path.join(tempfile.gettempdir(), saved_path)
        try:
            with open(tmp_img, 'wb') as f:
                f.write(requests.get(photo_url).content)
            ui_callback(f"{label} Generated", image_path=tmp_img)
        except:
            pass


def _phase_combine_closeups(table_id: str, record_id: str, ui_callback=None) -> None:
    """Phase 11: Combine Closeup One Video + Closeup Two Video + After Reels."""
    fields = refetch_record(table_id, record_id)
    cu1_video = fields.get("Closeup Photo One Video")
    cu2_video = fields.get("Closeup Photo Two Video")
    after = fields.get("After Reels")
    combined = fields.get("Combine Video Closeups")

    if combined:
        print("[INFO] Combine Video Closeups already exists. Skipping.")
        return
    if not (cu1_video and cu2_video and after):
        print("[WARN] Missing one or more videos for closeup combination. Skipping.")
        return

    print("[INFO] Combining Closeup Videos + After Reels...")
    if ui_callback:
        ui_callback("⏳ Phase 11: Combining Closeup Videos...",
                     desc_text="Stitching Closeup One + Closeup Two + After Reels...")

    cu1_path = download(cu1_video[0]["url"], f"{record_id}_closeup1.mp4")
    cu2_path = download(cu2_video[0]["url"], f"{record_id}_closeup2.mp4")
    after_path = download(after[0]["url"], f"{record_id}_after_for_closeup.mp4")

    paths = [cu1_path, cu2_path, after_path]
    if not all(paths):
        print("[WARN] Could not download all videos for closeup combination. Skipping.")
        cleanup_temp_files(*paths)
        return

    combined_path = combine(paths, f"{record_id}_combined_closeups_raw.mp4")
    if not combined_path:
        print("[WARN] Closeup video combination failed. Skipping.")
        cleanup_temp_files(*paths)
        return

    # Apply music to the combined closeup video
    final_combined_path = _apply_music(combined_path, record_id, "Combined Closeup Videos")

    combined_url = upload_and_get_public_link(final_combined_path, folder_key="Combined Closeup Videos")
    if combined_url:
        update_attachment(table_id, record_id, "Combine Video Closeups", combined_url)
        print("[OK] Phase 11 (Combine Video Closeups) done.")
        if ui_callback:
            ui_callback("Phase 11: Closeup Videos Combined",
                         desc_text="Combined closeup + after reels video with music has been uploaded.")
    else:
        print("[WARN] Could not upload combined closeup video. Skipping.")

    cleanup_temp_files(*paths, combined_path, 
                       final_combined_path if final_combined_path != combined_path else None)


# ── Phase 12: Shop Now Image ────────────────────────────────

def _phase12_shop_now(table_id: str, record_id: str, ui_callback=None) -> None:
    """Phase 12: Stamp 'SHOP NOW' at the bottom-center of the Blended Image."""
    fields = refetch_record(table_id, record_id)
    blended = fields.get("Blended Image")
    existing = fields.get("Shop Now Image")

    if existing:
        print("[INFO] Shop Now Image already exists. Skipping.")
        return
    if not blended:
        print("[WARN] No Blended Image found. Cannot generate Shop Now Image.")
        return

    blended_url = blended[0]["url"]
    print(f"[INFO] Generating Shop Now Image (text='{SHOP_NOW_TEXT}')...")
    if ui_callback:
        ui_callback(
            "⏳ Phase 12: Adding SHOP NOW...",
            desc_text="Drawing the SHOP NOW label onto the Blended Image...",
        )

    blended_path = download(blended_url, f"{record_id}_blended_for_shopnow.png")
    if not blended_path:
        print("[WARN] Could not download Blended Image. Skipping Shop Now Image.")
        return

    overlay_path = make_shop_now_image(blended_path, record_id, text=SHOP_NOW_TEXT)
    if not overlay_path:
        print("[WARN] SHOP NOW overlay failed. Skipping Shop Now Image.")
        cleanup_temp_files(blended_path)
        return

    public_url = upload_and_get_public_link(overlay_path, folder_key="Shop Now Image")
    if public_url:
        update_attachment(table_id, record_id, "Shop Now Image", public_url)
        print("[OK] Phase 12 (Shop Now Image) done.")
        if ui_callback:
            ui_callback(
                "Phase 12: Shop Now Image Built",
                desc_text="Final image with SHOP NOW overlay uploaded to Airtable.",
                image_path=overlay_path,
            )
    else:
        print("[WARN] Could not upload Shop Now Image to Zoho — "
              "attaching local file is not possible. Configure the "
              "'Shop Now Image' Zoho folder to enable this phase.")
        if ui_callback:
            ui_callback(
                "Phase 12: Shop Now Image Built (local only)",
                desc_text="Overlay rendered but Zoho upload failed; Airtable not updated.",
                image_path=overlay_path,
            )

    cleanup_temp_files(blended_path, overlay_path)


# ── Phase 13: Polls and Slider ─────────────────────────

def _phase13_poll(table_id: str, record_id: str,
                  item1: str = "", item2: str = "",
                  ui_callback=None) -> None:
    """Phase 13: Generate an A/B poll graphic.

    The poll copy (question + two choices) is auto-generated by the
    LLM with text-only context (fixture combo + the row's styled-photo
    prompt). The graphic itself is rendered by Kie.ai nano-banana-pro
    using a fixed layout prompt with the copy substituted in.

    This phase does NOT depend on the Blended Image — it can run on
    any row that has reached the end of the pipeline.
    """
    fields = refetch_record(table_id, record_id)
    if fields.get("Polls and Slider"):
        print("[INFO] 'Polls and Slider' already populated. Skipping Phase 13.")
        return

    # Build a small text-only context for the LLM so polls vary per row.
    style_prompt = (fields.get("Styled Photo Prompt") or "").strip()
    context_parts = []
    if item1 or item2:
        pair = " + ".join(p for p in (item1, item2) if p)
        if pair:
            context_parts.append(f"Lighting / fixture combo: {pair}")
    if style_prompt:
        context_parts.append(f"Room style direction: {style_prompt}")
    context = "\n".join(context_parts)

    if ui_callback:
        ui_callback(
            "⏳ Phase 13: Writing poll copy...",
            desc_text="LLM is drafting a poll question + A/B choices.",
        )

    poll = generate_poll(context)
    if not poll:
        print("[WARN] LLM did not return a poll. Skipping Phase 13.")
        return

    print(
        f"[INFO] Poll copy → Q: {poll['question']!r} | "
        f"A: {poll['choice_a']!r} | B: {poll['choice_b']!r}"
    )

    # Persist the raw poll copy as text fields so it can be reused as a
    # social caption. These writes silently no-op if the fields don't
    # exist in Airtable.
    update_field(table_id, record_id, "Poll Question", poll["question"])
    update_field(table_id, record_id, "Poll Choice A", poll["choice_a"])
    update_field(table_id, record_id, "Poll Choice B", poll["choice_b"])

    # Build the nano-banana prompt (fixed layout, dynamic copy) and
    # generate the poll image.
    image_prompt = POLL_IMAGE_PROMPT_TEMPLATE.format(
        question=poll["question"],
        choice_a=poll["choice_a"],
        choice_b=poll["choice_b"],
    )

    if ui_callback:
        ui_callback(
            "⏳ Phase 13: Rendering poll image...",
            desc_text=f"nano-banana is drawing the poll graphic.\nQ: {poll['question']}",
        )

    task_id = create_image_task(image_prompt)
    if not task_id:
        update_status(table_id, record_id, "Error - Polls and Slider Task Failed")
        return

    poll_url = poll_task_status(task_id)
    if not poll_url:
        update_status(table_id, record_id, "Error - Polls and Slider Generation Failed")
        return

    # Attach to the 'Polls and Slider' Airtable attachment field +
    # best-effort backup to Zoho.
    update_attachment(table_id, record_id, "Polls and Slider", poll_url)
    upload_from_url(poll_url, f"{record_id}_polls_and_slider.png", "Polls and Slider")
    print("[OK] Phase 13 ('Polls and Slider') done.")

    if ui_callback:
        ui_callback(
            "Phase 13: Polls and Slider Built",
            desc_text=(
                f"Q: {poll['question']}\n"
                f"A: {poll['choice_a']}\n"
                f"B: {poll['choice_b']}"
            ),
        )


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

    # Phases 2–6 only run when status is "Processing"
    if status == "Processing":
        if ui_callback:
            ui_callback("Processing Video & Blends", desc_text="Starting the blend & video rendering phases...")
        _phase2_blend(table_id, record_id, blend_prompt, ui_callback)
        _phase3_moodboard(table_id, record_id, ui_callback)

        _phase_video(
            table_id, record_id,
            source_field="Styled Photo", target_field="Before Reels",
            prompt=BEFORE_REELS_PROMPT, zoho_folder="Before Reels",
            label="Before Reels",
            ui_callback=ui_callback
        )
        _phase_video(
            table_id, record_id,
            source_field="Blended Image", target_field="After Reels",
            prompt=AFTER_REELS_PROMPT, zoho_folder="After Reels",
            label="After Reels",
            ui_callback=ui_callback
        )

        _phase6_combine_reels(table_id, record_id, ui_callback)

        # Phase 7: Closeup Photo One
        if item1:
            _phase_closeup_photo(
                table_id, record_id,
                item_name=item1, target_field="Closeup Photo One",
                label="Phase 7: Closeup Photo One",
                ui_callback=ui_callback
            )

        # Phase 8: Closeup Photo Two
        if item2:
            _phase_closeup_photo(
                table_id, record_id,
                item_name=item2, target_field="Closeup Photo Two",
                label="Phase 8: Closeup Photo Two",
                ui_callback=ui_callback
            )

        # Phase 9: Closeup Photo One Video (silent — music applied on the combined cut)
        _phase_video(
            table_id, record_id,
            source_field="Closeup Photo One", target_field="Closeup Photo One Video",
            prompt=CLOSEUP_VIDEO_PROMPT, zoho_folder="Closeup Photo One Video",
            label="Closeup Photo One Video",
            apply_music=False,
            ui_callback=ui_callback
        )

        # Phase 10: Closeup Photo Two Video (silent — music applied on the combined cut)
        _phase_video(
            table_id, record_id,
            source_field="Closeup Photo Two", target_field="Closeup Photo Two Video",
            prompt=CLOSEUP_VIDEO_PROMPT, zoho_folder="Closeup Photo Two Video",
            label="Closeup Photo Two Video",
            apply_music=False,
            ui_callback=ui_callback
        )

        # Phase 11: Combine Closeup Videos
        _phase_combine_closeups(table_id, record_id, ui_callback)

        # Phase 12: Shop Now Image (Blended Image + SHOP NOW overlay)
        _phase12_shop_now(table_id, record_id, ui_callback)

        # Phase 13: Polls and Slider (LLM-generated A/B poll, final phase)
        _phase13_poll(table_id, record_id, item1=item1, item2=item2,
                      ui_callback=ui_callback)

    # Mark complete
    update_status(table_id, record_id, "Complete")
    print(f"[DONE] Record {record_id} fully completed!")
    return True
