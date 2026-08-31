import os
import subprocess
import imageio_ffmpeg

MOOD_AUDIO_MAP = {
    "serious": "assets/audio/serious.mp3",
    "crime": "assets/audio/crime.mp3",
    "breaking": "assets/audio/breaking.mp3",
    "upbeat": "assets/audio/upbeat.mp3",
    "neutral": "assets/audio/neutral.mp3",
}

def create_news_reel(image_path: str, mood: str, output_video_path: str, duration: int = 6) -> str:
    """Combines the 1080x1920 news card image and mood-based audio into a Reels-ready MP4."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found at: {image_path}")

    audio_path = MOOD_AUDIO_MAP.get(mood, "assets/audio/neutral.mp3")
    if not os.path.exists(audio_path):
        audio_files = [f for f in os.listdir("assets/audio") if f.endswith(".mp3")]
        if not audio_files:
            raise FileNotFoundError("No .mp3 audio files found in assets/audio/")
        audio_path = os.path.join("assets/audio", audio_files[0])

    os.makedirs(os.path.dirname(output_video_path), exist_ok=True)
    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()

    print(f"🎬 Rendering Reel with audio mood: [{mood}] -> {audio_path}")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-r", "30",                         # Force constant 30 fps
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2", # Strictly 9:16
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",                     # Standard 44.1kHz audio sampling
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",          # Moves moov atom to front for web/Meta streaming
        "-t", str(duration),
        "-shortest",
        output_video_path
    ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"✅ Reel video ready: {output_video_path}")
    return output_video_path