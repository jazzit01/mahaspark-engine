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

DURATION_POOL = [9.9, 10.15, 11.6, 12.12, 13.0, 14.2, 14.9]


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

  # Ken Burns micro-zoom strictly on the raw background photo
  zoom_filter = (
      f"boxblur=2:1,"
      f"scale=4320:-2,"
      f"zoompan=z='min(zoom+0.0003,1.035)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1080x1920:fps={fps},"
      f"format=yuva420p"
  )

  # Multi-plate stacking:
  # [0:v] raw photo zooms
    # [1:v] frame (logo + badge) stays 100% locked
  # [2:v] to [5:v] text overlays stack cumulatively
  filter_complex = (
      f"[0:v]{zoom_filter}[zoomed_bg];"
      f"[1:v]format=yuva420p[static_frame];"
      f"[2:v]format=yuva420p,fade=t=in:st=0.6:d=0.35:alpha=1[hl];"
      f"[3:v]format=yuva420p,fade=t=in:st=1.6:d=0.35:alpha=1[pill];"
      f"[4:v]format=yuva420p,fade=t=in:st=3.0:d=0.35:alpha=1[b1];"
      f"[5:v]format=yuva420p,fade=t=in:st=4.6:d=0.35:alpha=1[b2];"
      f"[zoomed_bg][static_frame]overlay=0:0:eof_action=pass:repeatlast=1[base];"
      f"[base][hl]overlay=0:0:eof_action=pass:repeatlast=1[s1];"
      f"[s1][pill]overlay=0:0:eof_action=pass:repeatlast=1[s2];"
      f"[s2][b1]overlay=0:0:eof_action=pass:repeatlast=1[s3];"
      f"[s3][b2]overlay=0:0:eof_action=pass:repeatlast=1[v]"
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