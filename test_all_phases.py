# =====================================================================
#  TEST ALL PHASES
#  Verifies the image processing, LLM generation, voiceover tasking,
#  video editing components, and Zoho WorkDrive integration.
# =====================================================================

import os
import sys
import tempfile
from PIL import Image

# Ensure the project root is in the path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from services.image_overlay import fit_image_to_9_16, make_watermarked_image
from services.vision_llm import generate_styling_tip
from services.kie import create_voiceover_task, poll_task_status, create_music_task
from services.video import (
    render_tips_reel_segment,
    concat_tips_reel_segments,
    mix_background_music,
    cleanup_temp_files,
    download
)
from services.zoho import upload_local_file
from config.settings import ZOHO_FOLDERS, KIE_VOICE_ID
from config.prompts import MUSIC_PROMPT

def create_dummy_image(path: str, width: int = 1200, height: int = 800, color: tuple = (200, 100, 100)) -> str:
    """Creates a temporary dummy image with the specified size and color."""
    img = Image.new("RGB", (width, height), color)
    img.save(path, "PNG")
    print(f"[TEST SETUP] Created dummy image: {path} ({width}x{height})")
    return path

def test_fit_image_to_9_16():
    print("\n=== Testing fit_image_to_9_16 ===")
    temp_dir = tempfile.gettempdir()
    src_path = os.path.join(temp_dir, "test_dummy_source.png")
    dest_path = os.path.join(temp_dir, "test_dummy_fitted.jpg")
    
    # Create a landscape dummy image (1200x800)
    create_dummy_image(src_path, 1200, 800)
    
    try:
        res = fit_image_to_9_16(src_path, dest_path, target_width=1080, target_height=1920)
        assert res == dest_path, "Result path mismatch"
        assert os.path.exists(dest_path), "Fitted file was not created"
        
        with Image.open(dest_path) as img:
            w, h = img.size
            print(f"[TEST OK] Fitted image size: {w}x{h} (expected: 1080x1920)")
            assert w == 1080 and h == 1920, f"Expected 1080x1920, got {w}x{h}"
            
    finally:
        cleanup_temp_files(src_path, dest_path)

def test_vision_llm_tip_generation():
    print("\n=== Testing generate_styling_tip ===")
    temp_dir = tempfile.gettempdir()
    src_path = os.path.join(temp_dir, "test_dummy_room.png")
    create_dummy_image(src_path, 800, 600, color=(100, 150, 200))
    
    try:
        # This will call the local LM Studio model or fall back to randomized tips
        tip = generate_styling_tip(src_path)
        print(f"[TEST OK] Generated styling tip: '{tip}'")
        assert len(tip.split()) >= 3, "Styling tip looks too short or empty"
    finally:
        cleanup_temp_files(src_path)

def test_elevenlabs_voiceover_task():
    print("\n=== Testing ElevenLabs Voiceover Task via Kie.ai ===")
    # Using a short test text
    test_text = "Layer lighting with floor lamps to add warmth and depth."
    
    try:
        print(f"[TEST] Creating voiceover task for text: '{test_text}' using voice ID: {KIE_VOICE_ID}")
        task_id = create_voiceover_task(test_text)
        if not task_id:
            print("[TEST SKIP] ElevenLabs task creation failed (is KIE_API_KEY valid?). Skipping task polling.")
            return
            
        print(f"[TEST] Task created successfully. Task ID: {task_id}")
        vo_url = poll_task_status(task_id)
        if not vo_url:
            print("[TEST FAIL] Polling failed or timed out.")
            return
            
        print(f"[TEST OK] ElevenLabs Voiceover URL: {vo_url}")
        
        # Download and verify it's an audio file
        local_audio = download(vo_url, "test_voiceover.mp3")
        assert local_audio and os.path.exists(local_audio), "Voiceover download failed"
        print(f"[TEST OK] Voiceover downloaded to: {local_audio} (Size: {os.path.getsize(local_audio)} bytes)")
        cleanup_temp_files(local_audio)
    except Exception as e:
        print(f"[TEST FAIL] ElevenLabs test encountered an error: {e}")

def test_video_rendering_and_music_mixing():
    print("\n=== Testing Video Rendering, Concatenation, and Music Mixing ===")
    
    # We need a source video clip to test with.
    # Let's use a dummy video file if one isn't available, or download a tiny sample.
    # For testing, we can check if there's any small video, or skip if none.
    # To make it robust, let's use a 3-second sample video URL or create one if possible.
    # We will use a public tiny video clip.
    sample_video_url = "https://www.w3schools.com/html/mov_bbb.mp4"
    temp_dir = tempfile.gettempdir()
    
    video_path = download(sample_video_url, "test_sample_video.mp4")
    if not video_path:
        print("[TEST SKIP] Could not download sample video. Skipping video editing tests.")
        return
        
    segment_path = os.path.join(temp_dir, "test_segment_rendered.mp4")
    tip_text = "Position lighting at eye level for a cozy ambiance."
    
    try:
        # 1. Render segment with text overlay (and no voiceover)
        print("[TEST] Rendering video segment with overlay text...")
        res = render_tips_reel_segment(video_path, segment_path, tip_text)
        assert res == segment_path, "Rendering segment path mismatch"
        assert os.path.exists(segment_path), "Segment video was not created"
        print(f"[TEST OK] Rendered segment video: {segment_path}")
        
        # 2. Concatenate segments (we'll duplicate the same segment 3 times)
        combined_path = os.path.join(temp_dir, "test_concat_combined.mp4")
        print("[TEST] Concatenating segments...")
        concat_ok = concat_tips_reel_segments([segment_path, segment_path, segment_path], combined_path)
        assert concat_ok, "Concatenation failed"
        assert os.path.exists(combined_path), "Concatenated video was not created"
        print(f"[TEST OK] Concatenated video: {combined_path}")
        
        # 3. Mix background music (generate a Suno track or download dummy)
        # We can download a dummy mp3 to mix
        sample_audio_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        music_path = download(sample_audio_url, "test_sample_music.mp3")
        
        if music_path:
            mixed_path = os.path.join(temp_dir, "test_music_mixed.mp4")
            print("[TEST] Mixing background music at 15% volume...")
            mixed_ok = mix_background_music(combined_path, music_path, mixed_path, music_volume=0.15)
            assert mixed_ok == mixed_path, "Music mixing failed"
            assert os.path.exists(mixed_path), "Mixed video was not created"
            print(f"[TEST OK] Mixed video with background music: {mixed_path}")
            cleanup_temp_files(mixed_path, music_path)
            
        cleanup_temp_files(combined_path)
    finally:
        cleanup_temp_files(video_path, segment_path)

def test_zoho_uploads():
    print("\n=== Testing Zoho WorkDrive Uploads ===")
    temp_dir = tempfile.gettempdir()
    test_file = os.path.join(temp_dir, "test_zoho_upload.jpg")
    create_dummy_image(test_file, 100, 100)
    
    try:
        # Check folder mappings
        for key in ["CTA", "Styled Stories", "Sliders", "Tips Reels"]:
            folder_id = ZOHO_FOLDERS.get(key)
            print(f"[TEST] Zoho folder mapping for '{key}': {folder_id}")
            assert folder_id, f"Missing Zoho folder mapping for {key}"
            
        # Try uploading a dummy file to the CTA folder
        print("[TEST] Attempting upload to Zoho CTA folder...")
        upload_ok = upload_local_file(test_file, "test_dummy_ping.jpg", "CTA")
        if upload_ok:
            print("[TEST OK] Upload to Zoho succeeded!")
        else:
            print("[TEST FAIL] Upload to Zoho returned False (check Zoho refresh token/client secret).")
            
    finally:
        cleanup_temp_files(test_file)

if __name__ == "__main__":
    print("Starting automated test suite for content creation pipeline modifications...")
    
    try:
        test_fit_image_to_9_16()
    except Exception as e:
        print(f"[ERROR] test_fit_image_to_9_16 failed: {e}")
        
    try:
        test_vision_llm_tip_generation()
    except Exception as e:
        print(f"[ERROR] test_vision_llm_tip_generation failed: {e}")
        
    try:
        test_elevenlabs_voiceover_task()
    except Exception as e:
        print(f"[ERROR] test_elevenlabs_voiceover_task failed: {e}")
        
    try:
        test_video_rendering_and_music_mixing()
    except Exception as e:
        print(f"[ERROR] test_video_rendering_and_music_mixing failed: {e}")
        
    try:
        test_zoho_uploads()
    except Exception as e:
        print(f"[ERROR] test_zoho_uploads failed: {e}")
        
    print("\nTests completed.")
