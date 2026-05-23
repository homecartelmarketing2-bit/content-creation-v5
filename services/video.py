# =====================================================================
#  VIDEO SERVICE
#  Downloads, concatenates, and cleans up temporary video files.
# =====================================================================

import os
import tempfile
import subprocess
import requests
import imageio_ffmpeg

try:
    from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, afx, ImageClip, CompositeVideoClip, CompositeAudioClip
except ImportError:
    from moviepy import VideoFileClip, concatenate_videoclips, AudioFileClip, afx, ImageClip, CompositeVideoClip, CompositeAudioClip


def _strip_chapters_and_metadata(video_path: str) -> str:
    """Creates a temporary copy of the video with chapters and metadata stripped
    to bypass MoviePy parsing bugs with newer FFmpeg versions.
    """
    if not video_path or not os.path.exists(video_path):
        return video_path
    
    temp_dir = tempfile.gettempdir()
    out_name = f"stripped_{hash(video_path) & 0xffffffff}_{os.path.basename(video_path)}"
    out_path = os.path.join(temp_dir, out_name)
    
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg_exe, "-y", "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-map_metadata", "-1",
            "-map_chapters", "-1",
            "-c", "copy",
            out_path
        ]
        subprocess.run(cmd, check=True)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
    except Exception as e:
        print(f"[WARN] Failed to strip metadata/chapters for {video_path}: {e}")
        
    return video_path



# ── Download ────────────────────────────────────────────────────────

def download(url: str, filename: str) -> str | None:
    """Downloads a file (video or audio) from a URL to a temp directory."""
    filepath = os.path.join(tempfile.gettempdir(), filename)
    try:
        print(f"[INFO] Downloading: {filename}...")
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"[OK] Downloaded: {filename}")
        return filepath
    except requests.RequestException as e:
        print(f"[ERROR] Failed to download: {e}")
        return None


# ── Combine ─────────────────────────────────────────────────────────

def combine(video_paths: list[str], output_filename: str) -> str | None:
    """Concatenates a list of videos into one using MoviePy."""
    output_path = os.path.join(tempfile.gettempdir(), output_filename)
    clips = []
    stripped_paths = []
    try:
        print(f"[INFO] Combining {len(video_paths)} videos with MoviePy...")
        for vp in video_paths:
            s_path = _strip_chapters_and_metadata(vp)
            stripped_paths.append(s_path)
            clips.append(VideoFileClip(s_path))
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
        final.close()
        for c in clips:
            c.close()
        print(f"[OK] Videos combined: {output_filename}")
        return output_path
    except Exception as e:
        print(f"[ERROR] Failed to combine videos: {e}")
        for c in clips:
            try:
                c.close()
            except Exception:
                pass
        return None
    finally:
        for vp, s_path in zip(video_paths, stripped_paths):
            if s_path != vp:
                cleanup_temp_files(s_path)


# ── Audio ───────────────────────────────────────────────────────────

def add_audio_to_video(video_path: str, audio_path: str, output_filename: str) -> str | None:
    """Overlays an audio track onto a video, looping it if necessary."""
    output_path = os.path.join(tempfile.gettempdir(), output_filename)
    stripped_video_path = None
    try:
        print(f"[INFO] Adding audio to video: {output_filename}...")
        stripped_video_path = _strip_chapters_and_metadata(video_path)
        video = VideoFileClip(stripped_video_path)
        audio = AudioFileClip(audio_path)

        # Loop or trim audio to match video duration
        looped_audio = audio.with_effects([afx.AudioLoop(duration=video.duration)])
        
        final_video = video.with_audio(looped_audio)
        final_video.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
        
        video.close()
        audio.close()
        final_video.close()
        
        print(f"[OK] Audio added: {output_filename}")
        return output_path
    except Exception as e:
        print(f"[ERROR] Failed to add audio to video: {e}")
        return None
    finally:
        if stripped_video_path and stripped_video_path != video_path:
            cleanup_temp_files(stripped_video_path)


# ── Cleanup ─────────────────────────────────────────────────────────

def cleanup_temp_files(*filepaths: str):
    """Silently removes temporary files."""
    for fp in filepaths:
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
            except OSError:
                pass


def create_text_overlay_image(video_w: int, video_h: int, text: str) -> str:
    """Generates a transparent PNG image with the tip text inside a rounded dark box."""
    from PIL import Image, ImageDraw
    from services.image_overlay import _load_font, _measure_text
    
    overlay = Image.new("RGBA", (video_w, video_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    font_size = max(28, int(video_w * 0.045))
    font = _load_font(font_size, bold=True)
    
    max_text_width = int(video_w * 0.8)
    lines = []
    words = text.split()
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        w, _ = _measure_text(draw, test_line, font)
        if w <= max_text_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
        
    line_heights = []
    line_widths = []
    for line in lines:
        w, h = _measure_text(draw, line, font)
        line_widths.append(w)
        line_heights.append(h)
        
    total_text_h = sum(line_heights) + (len(lines) - 1) * 10
    max_line_w = max(line_widths) if line_widths else 0
    
    padding_x = 40
    padding_y = 30
    box_w = max_line_w + 2 * padding_x
    box_h = total_text_h + 2 * padding_y
    
    box_x = (video_w - box_w) // 2
    box_y = int(video_h * 0.70) - box_h // 2
    
    draw.rounded_rectangle(
        [box_x, box_y, box_x + box_w, box_y + box_h],
        radius=20,
        fill=(0, 0, 0, 166)
    )
    
    current_y = box_y + padding_y
    for i, line in enumerate(lines):
        line_w = line_widths[i]
        line_h = line_heights[i]
        text_x = box_x + (box_w - line_w) // 2
        draw.text(
            (text_x, current_y),
            line,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=2,
            stroke_fill=(0, 0, 0, 255)
        )
        current_y += line_h + 10
        
    temp_dir = tempfile.gettempdir()
    overlay_path = os.path.join(temp_dir, f"text_overlay_{hash(text) & 0xffffffff}.png")
    overlay.save(overlay_path, "PNG")
    return overlay_path


def render_tips_reel_segment(video_path: str, output_path: str, tip_text: str, voiceover_path: str = None) -> str | None:
    """Overlays tip text and applies voiceover audio to a video clip."""
    stripped_video_path = None
    try:
        stripped_video_path = _strip_chapters_and_metadata(video_path)
        video = VideoFileClip(stripped_video_path)
        w, h = video.size
        
        overlay_img_path = create_text_overlay_image(w, h, tip_text)
        overlay_clip = (ImageClip(overlay_img_path)
                        .with_duration(video.duration)
                        .with_position(("center", "center")))
        
        composited = CompositeVideoClip([video, overlay_clip])
        
        if voiceover_path and os.path.exists(voiceover_path):
            audio = AudioFileClip(voiceover_path)
            # Clip/loop voiceover if needed, or simply assign it
            # We want to assign the voiceover audio directly
            composited = composited.with_audio(audio)
            
        composited.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            logger=None
        )
        
        composited.close()
        video.close()
        if voiceover_path and os.path.exists(voiceover_path):
            audio.close()
            
        cleanup_temp_files(overlay_img_path)
        print(f"[OK] Tips Reels segment rendered: {output_path}")
        return output_path
    except Exception as e:
        print(f"[ERROR] Failed to render tips reel segment: {e}")
        return None
    finally:
        if stripped_video_path and stripped_video_path != video_path:
            cleanup_temp_files(stripped_video_path)


def concat_tips_reel_segments(segment_paths: list[str], output_path: str) -> bool:
    """Concatenates multiple video segments into one file."""
    clips = []
    stripped_paths = []
    try:
        print(f"[INFO] Concatenating {len(segment_paths)} segments...")
        for sp in segment_paths:
            s_path = _strip_chapters_and_metadata(sp)
            stripped_paths.append(s_path)
            clips.append(VideoFileClip(s_path))
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
        final.close()
        for c in clips:
            c.close()
        print(f"[OK] Concatenated video written: {output_path}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to concatenate segments: {e}")
        for c in clips:
            try:
                c.close()
            except Exception:
                pass
        return False
    finally:
        for sp, s_path in zip(segment_paths, stripped_paths):
            if s_path != sp:
                cleanup_temp_files(s_path)


def mix_background_music(video_path: str, music_path: str, output_path: str, music_volume: float = 0.15) -> str | None:
    """Mixes a background music track (at music_volume) with existing voiceover/audio in a video."""
    stripped_video_path = None
    try:
        stripped_video_path = _strip_chapters_and_metadata(video_path)
        video = VideoFileClip(stripped_video_path)
        original_audio = video.audio
        
        bg_music = AudioFileClip(music_path)
        looped_bg = bg_music.with_effects([afx.AudioLoop(duration=video.duration)])
        scaled_bg = looped_bg.with_volume_scaled(music_volume)
        
        if original_audio:
            mixed_audio = CompositeAudioClip([original_audio, scaled_bg])
        else:
            mixed_audio = scaled_bg
            
        final_video = video.with_audio(mixed_audio)
        final_video.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
        
        video.close()
        bg_music.close()
        final_video.close()
        print(f"[OK] Background music mixed successfully: {output_path}")
        return output_path
    except Exception as e:
        print(f"[ERROR] Failed to mix background music: {e}")
        return None
    finally:
        if stripped_video_path and stripped_video_path != video_path:
            cleanup_temp_files(stripped_video_path)
