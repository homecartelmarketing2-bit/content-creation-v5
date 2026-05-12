# =====================================================================
#  VIDEO SERVICE
#  Downloads, concatenates, and cleans up temporary video files.
# =====================================================================

import os
import tempfile

import requests

try:
    from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, afx
except ImportError:
    from moviepy import VideoFileClip, concatenate_videoclips, AudioFileClip, afx


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
    try:
        print(f"[INFO] Combining {len(video_paths)} videos with MoviePy...")
        for vp in video_paths:
            clips.append(VideoFileClip(vp))
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


# ── Audio ───────────────────────────────────────────────────────────

def add_audio_to_video(video_path: str, audio_path: str, output_filename: str) -> str | None:
    """Overlays an audio track onto a video, looping it if necessary."""
    output_path = os.path.join(tempfile.gettempdir(), output_filename)
    try:
        print(f"[INFO] Adding audio to video: {output_filename}...")
        video = VideoFileClip(video_path)
        audio = AudioFileClip(audio_path)

        # Loop or trim audio to match video duration
        looped_audio = afx.audio_loop(audio, duration=video.duration)
        
        final_video = video.set_audio(looped_audio)
        final_video.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
        
        video.close()
        audio.close()
        final_video.close()
        
        print(f"[OK] Audio added: {output_filename}")
        return output_path
    except Exception as e:
        print(f"[ERROR] Failed to add audio to video: {e}")
        return None


# ── Cleanup ─────────────────────────────────────────────────────────

def cleanup_temp_files(*filepaths: str):
    """Silently removes temporary files."""
    for fp in filepaths:
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
            except OSError:
                pass
