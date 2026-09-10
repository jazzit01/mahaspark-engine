import os
import random
import subprocess

AUDIO_MOOD_MAP = {
    "serious": "assets/audio/serious.mp3",
    "crime": "assets/audio/crime.mp3",
    "breaking": "assets/audio/breaking.mp3",
    "upbeat": "assets/audio/upbeat.mp3",
    "neutral": "assets/audio/neutral.mp3",
}

DURATION_POOL = [5.9, 8.15, 6.6, 7.12, 8.12, 7.2, 6.9,8.5, 9.0, 7.8, 6.5, 8.0, 7.5, 6.8, 7.0, 8.3, 9.1, 7.4, 6.7, 8.2]


def get_mood_timing(mood: str) -> float:
  mood_key = str(mood or "neutral").lower()
  durations = {
      "serious": 12.2,
      "crime": 11.4,
      "breaking": 10.6,
      "upbeat": 9.8,
      "neutral": 10.8,
  }
  return durations.get(mood_key, 10.8)


def create_news_reel(
    layers: dict,
    mood: str = "neutral",
    theme: str = "yellow",
    output_video_path: str = "output/reel.mp4",
) -> str:
  raw_bg = layers.get("raw_bg")
  frame_img = layers.get("frame")
  hl_img = layers.get("hl")
  pill_img = layers.get("pill")
  b1_img = layers.get("b1")
  b2_img = layers.get("b2")

  for name, p in [
      ("raw_bg", raw_bg),
      ("frame", frame_img),
      ("hl", hl_img),
      ("pill", pill_img),
      ("b1", b1_img),
      ("b2", b2_img),
  ]:
    if not p or not os.path.exists(p):
      raise FileNotFoundError(f"Missing required layer plate '{name}': {p}")

  os.makedirs(os.path.dirname(output_video_path), exist_ok=True)

  duration = get_mood_timing(mood)
  fps = 30
  total_frames = int(duration * fps)

  audio_path = AUDIO_MOOD_MAP.get(mood.lower(), AUDIO_MOOD_MAP["neutral"])
  has_audio = os.path.exists(audio_path)

  # Dynamic Zoom: Starts slightly faster, then slows down for a "hook" effect
  # Also reduced blur slightly for better clarity on high-end devices
  zoom_filter = (
      f"scale=3840:-2,"
      f"boxblur=1:1,"
      f"zoompan=z='min(zoom+0.0006,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1080x1920:fps={fps},"
      f"format=yuva420p"
  )

  # Simplified, extremely compatible filtergraph
  filter_complex = (
      f"[0:v]{zoom_filter}[zoomed_bg];"
      f"[1:v]format=yuva420p[static_frame];"
      f"[2:v]format=yuva420p,fade=t=in:st=0.4:d=0.2:alpha=1[hl];"
      f"[3:v]format=yuva420p,fade=t=in:st=1.2:d=0.2:alpha=1[pill];"
      f"[4:v]format=yuva420p,fade=t=in:st=2.3:d=0.2:alpha=1[b1];"
      f"[5:v]format=yuva420p,fade=t=in:st=3.6:d=0.2:alpha=1[b2];"
      f"[zoomed_bg][static_frame]overlay=0:0[base];"
      f"[base][hl]overlay=0:0[s1];"
      f"[s1][pill]overlay=0:0[s2];"
      f"[s2][b1]overlay=0:0[s3];"
      f"[s3][b2]overlay=0:0[v_stacked];"
      f"[v_stacked]vignette=angle=0.3[v_vignette];"
      f"[v_vignette]eq=contrast=1.1:brightness=-0.05:saturation=1.1[v]"
  )

  cmd = [
      "ffmpeg",
      "-y",
      "-loop",
      "1",
      "-i",
      raw_bg,
      "-loop",
      "1",
      "-i",
      frame_img,
      "-loop",
      "1",
      "-i",
      hl_img,
      "-loop",
      "1",
      "-i",
      pill_img,
      "-loop",
      "1",
      "-i",
      b1_img,
      "-loop",
      "1",
      "-i",
      b2_img,
  ]

  if has_audio:
    fade_start = max(0.0, duration - 0.8)
    audio_filter = f"afade=t=out:st={fade_start:.2f}:d=0.8"
    cmd += [
        "-stream_loop",
        "-1",
        "-i",
        audio_path,
        "-filter_complex",
        f"{filter_complex};[6:a]{audio_filter}[a]",
        "-map",
        "[v]",
        "-map",
        "[a]",
    ]
  else:
    cmd += [
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
    ]

  cmd += [
      "-t",
      str(duration),
      "-c:v",
      "libx264",
      "-preset",
      "fast",
      "-crf",
      "19",
      "-pix_fmt",
      "yuv420p",
      "-c:a",
      "aac",
      "-b:a",
      "192k",
      "-movflags",
      "+faststart",
      output_video_path,
  ]

  print(f"🎬 Rendering Reel ({duration}s, mood: {mood}, theme: {theme})...")
  res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  if res.returncode != 0:
    raise RuntimeError(
        f"FFmpeg error: {res.stderr.decode('utf-8', errors='ignore')[-400:]}"
    )

  thumb_path = output_video_path.replace(".mp4", "_thumb.jpg")
  thumb_cmd = [
      "ffmpeg",
      "-y",
      "-ss",
      "00:00:05.200",
      "-i",
      output_video_path,
      "-vframes",
      "1",
      "-q:v",
      "2",
      thumb_path,
  ]
  subprocess.run(thumb_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  print(f"✅ Finished reel: {output_video_path} (Duration: {duration}s)")
  return os.path.abspath(output_video_path)