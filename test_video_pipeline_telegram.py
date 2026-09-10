"""Run one production-format video pipeline pass and deliver it to Telegram only."""

import argparse
import os

from image_generator import generate_ai_background
from news_writer import generate_news_content
from renderer import render_news_tile
from telegram_notifier import send_news_video
from video_renderer import create_news_reel


DEFAULT_NEWS_INPUT = (
    "महाराष्ट्रातील सर्व सरकारी कार्यालयांमध्ये 5 दिवसांचा आठवडा कायम राहणार, "
    "सामान्य प्रशासन विभागाचे स्पष्टीकरण"
)


def run_telegram_video_test(
    news_input: str = DEFAULT_NEWS_INPUT,
    output_video_path: str = "output/test_reel_telegram.mp4",
) -> str:
  """Render one reel with production code and send it only to Telegram."""
  if not os.getenv("TELEGRAM_BOT_TOKEN") or not os.getenv("TELEGRAM_CHAT_ID"):
    print(
        "⚠️ Telegram credentials are not set; telegram_notifier.py will use its"
        " configured fallback values."
    )

  print("🧪 Generating test news package...")
  pack = generate_news_content(news_input)

  print("🎨 Generating custom AI background asset...")
  pack["background_path"] = generate_ai_background(pack.get("visual_prompt", ""))

  preview_path = output_video_path.replace(".mp4", ".png")
  layers = render_news_tile(pack, preview_path)

  print("🎬 Rendering test reel with the production FFmpeg filtergraph...")
  video_path = create_news_reel(
      layers=layers,
      mood=pack.get("audio_mood", "neutral"),
      theme=pack.get("headline_theme", "yellow"),
      output_video_path=output_video_path,
  )

  print("📲 Sending generated video and metadata to Telegram only...")
  if not send_news_video(video_path, pack):
    raise RuntimeError("Telegram delivery failed")

  print(f"✅ Telegram-only video test completed: {video_path}")
  return video_path


def main() -> None:
  parser = argparse.ArgumentParser(
      description="Render one production-format reel and send it only to Telegram."
  )
  parser.add_argument(
      "--news",
      default=DEFAULT_NEWS_INPUT,
      help="Raw news input to send to the production content generator.",
  )
  parser.add_argument(
      "--output",
      default="output/test_reel_telegram.mp4",
      help="Output MP4 path; the preview and layer plates use the same stem.",
  )
  args = parser.parse_args()
  run_telegram_video_test(args.news, args.output)


if __name__ == "__main__":
  main()