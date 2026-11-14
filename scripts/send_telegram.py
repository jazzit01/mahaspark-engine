"""Telegram delivery: the finished reel, the 5W1H source summary and the original source URL.

The bot token comes only from the environment (TELEGRAM_BOT_TOKEN). The chat id defaults to the
channel this project has always posted to and can be overridden with TELEGRAM_CHAT_ID.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import time
from pathlib import Path

import requests

from config import REEL_PATH, STORY_PATH, get_env_value

DEFAULT_CHAT_ID = "935514943"  # previous working destination, kept as the default
CAPTION_LIMIT = 1000
MESSAGE_LIMIT = 4000
MAX_VIDEO_BYTES = 49 * 1024 * 1024  # Bot API upload limit is 50 MB

FIVE_W_LABELS = [
    ("what", "काय घडले"),
    ("when", "केव्हा"),
    ("who", "कोण"),
    ("where", "कुठे"),
    ("why", "का"),
    ("how", "कसे"),
]


def _credentials() -> tuple[str, str]:
    token = get_env_value("TELEGRAM_BOT_TOKEN")
    chat_id = get_env_value("TELEGRAM_CHAT_ID", DEFAULT_CHAT_ID)
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN must be set in the environment.")
    return token, chat_id


def build_caption(story: dict) -> str:
    headline = story["scenes"][0]["headline"] if story.get("scenes") else ""
    text = (
        f"🔴 <b>{html.escape(headline)}</b>\n"
        f"🏷️ <i>{html.escape(story.get('category', ''))}</i>\n\n"
        f"{html.escape(story.get('social_caption', ''))}\n\n"
        "🔗 @MAHASPARKOFFICIAL"
    )
    return text[:CAPTION_LIMIT]


def build_summary_message(story: dict, source_url: str) -> str:
    five = story.get("five_w_one_h", {})
    lines = ["<b>📋 5W1H सारांश</b>"]
    for key, label in FIVE_W_LABELS:
        lines.append(f"<b>{label}:</b> {html.escape(str(five.get(key, '—')))}")
    if story.get("audio") is False:
        lines.append("")
        lines.append("<b>🔇 व्हॉइसओव्हर उपलब्ध नव्हता:</b> हा रील आवाजाशिवाय तयार झाला आहे.")
    lines.append("")
    lines.append(f"<b>🌐 मूळ स्रोत:</b> {html.escape(source_url or 'उपलब्ध नाही')}")
    lines.append("")
    lines.append(f"<b>▶️ Title:</b>\n<code>{html.escape(story.get('social_title', ''))}</code>")
    lines.append(f"<b>Caption:</b>\n<code>{html.escape(story.get('social_caption', ''))}</code>")
    lines.append(f"<b>Tags:</b>\n<code>{html.escape(story.get('hashtags', ''))}</code>")
    return "\n".join(lines)[:MESSAGE_LIMIT]


def send_reel(video_path: Path, story: dict, source_url: str, max_retries: int = 3) -> bool:
    """Send the video, then the summary message. Returns True when the video was delivered."""
    token, chat_id = _credentials()
    video_path = Path(video_path)
    if not video_path.exists():
        print(f"❌ Telegram dispatch failed: video not found at {video_path}")
        return False
    if video_path.stat().st_size > MAX_VIDEO_BYTES:
        print(f"❌ Video is {video_path.stat().st_size // 1_048_576} MB, above the Telegram bot upload limit.")
        return False

    api = f"https://api.telegram.org/bot{token}"
    delivered = False
    for attempt in range(1, max_retries + 1):
        try:
            with open(video_path, "rb") as handle:
                resp = requests.post(
                    f"{api}/sendVideo",
                    data={
                        "chat_id": chat_id,
                        "caption": build_caption(story),
                        "parse_mode": "HTML",
                        "supports_streaming": "true",
                        "width": 1080,
                        "height": 1920,
                        "duration": int(round(story.get("duration_seconds", 0))) or None,
                    },
                    files={"video": handle},
                    timeout=180,
                )
            if resp.status_code == 200:
                delivered = True
                break
            print(f"⚠️ Telegram video upload HTTP {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as exc:
            print(f"⚠️ Telegram upload attempt {attempt} failed: {exc}")
        time.sleep(2 * attempt)

    try:
        requests.post(
            f"{api}/sendMessage",
            data={
                "chat_id": chat_id,
                "text": build_summary_message(story, source_url),
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"⚠️ Telegram summary message failed: {exc}")

    print("📲 Telegram delivery completed." if delivered else "❌ Telegram video delivery failed.")
    return delivered


def main() -> None:
    parser = argparse.ArgumentParser(description="Send out/mahaspark_reel.mp4 and its 5W1H summary to Telegram.")
    parser.add_argument("--video", type=Path, default=REEL_PATH)
    parser.add_argument("--story", type=Path, default=STORY_PATH)
    parser.add_argument("--source-url", default="")
    args = parser.parse_args()

    story = json.loads(args.story.read_text(encoding="utf-8"))
    source_url = args.source_url or story.get("source", {}).get("url", "")
    if not send_reel(args.video, story, source_url):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
