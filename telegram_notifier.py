import os
import re
import time
import requests

# Reads from environment (Cloud/GitHub Actions), falls back to hardcoded string locally
BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN", "8980392198:AAHB-vpgw4RkNqmZS9fJy-SAQTvc6udpcsg"
)
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "935514943")


def clean_html_for_telegram(text: str) -> str:
  """Converts web HTML spans to Telegram-supported tags so captions never throw 400 errors."""
  if not text:
    return ""
  # Convert <span class="hl">word</span> to <b>word</b>
  text = re.sub(
      r'<span\s+class=["\']hl["\']>(.*?)</span>', r"<b>\1</b>", text, flags=re.I
  )
  # Strip any other unsupported HTML tags
  text = re.sub(r"</?(?!(b|i|a|code|pre|tg-spoiler)\b)[a-z0-9]+[^>]*>", "", text)
  return text


def send_news_post(image_path: str, pack: dict, max_retries: int = 3) -> bool:
  """Sends the rendered 1080x1920 graphic along with formatted captions to Telegram."""
  url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
  url_msg = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

  headline = (
      f"{pack.get('headline_part1', '')}"
      f" {pack.get('headline_part2', '')}".strip()
  )

  # Clean HTML tags inside bullets so Telegram accepts the caption[cite: 6]
  bullet_lines = []
  for b in pack.get("bullets", []):
    raw_text = b.get("text", "") if isinstance(b, dict) else str(b)
    clean_text = clean_html_for_telegram(raw_text)
    icon = b.get("icon", "⚡") if isinstance(b, dict) else "⚡"
    bullet_lines.append(f"{icon} {clean_text}")

  bullets_summary = "\n".join(bullet_lines)

  # 1. Primary Photo Caption[cite: 6]
  photo_caption = (
      f"🔥 <b>MAHASPARK BREAKING UPDATE</b> 🔥\n\n"
      f"📍 <b>{clean_html_for_telegram(headline)}</b>\n"
      f"🏷️ <i>{clean_html_for_telegram(pack.get('badge', ''))}</i> | ⚡"
      f" <i>{clean_html_for_telegram(pack.get('hook_pill', ''))}</i>\n\n"
      f"{bullets_summary}\n\n"
      f"🔗 @MAHASPARKOFFICIAL"
  )

  # 2. Formatted Copy Package for Social Distribution[cite: 6]
  full_copy_payload = (
      f"📱 <b>INSTAGRAM REEL / POST COPY:</b>\n"
      f"<code>{pack.get('ig_reels_caption', '')}\n\n{pack.get('ig_hashtags', '')}</code>\n\n"
      f"━━━━━━━━━━━━━━━━━━━━\n"
      f"▶️ <b>YOUTUBE SHORTS METADATA:</b>\n"
      f"<b>Title:</b>\n<code>{pack.get('yt_shorts_title', '')}</code>\n\n"
      f"<b>Description:</b>\n<code>{pack.get('yt_shorts_description', '')}</code>\n\n"
      f"<b>Tags:</b>\n<code>{pack.get('yt_shorts_tags', '')}</code>"
  )

  photo_delivered = False
  for attempt in range(1, max_retries + 1):
    try:
      with open(image_path, "rb") as img:
        resp1 = requests.post(
            url_photo,
            data={
                "chat_id": CHAT_ID,
                "caption": photo_caption[:1000],
                "parse_mode": "HTML",
            },
            files={"photo": img},
            timeout=60,
        )
      if resp1.status_code == 200:
        photo_delivered = True
        break
      else:
        print(
            f"⚠️ Telegram Photo Upload Status {resp1.status_code}: {resp1.text}"
        )
    except Exception as e:
      print(
          f"⚠️ Telegram upload attempt {attempt} failed ({e}). Retrying in"
          " 2s..."
      )
      time.sleep(2)

  try:
    requests.post(
        url_msg,
        data={
            "chat_id": CHAT_ID,
            "text": full_copy_payload,
            "parse_mode": "HTML",
        },
        timeout=30,
    )
  except Exception as e:
    print(f"⚠️ Telegram Text Dispatch Error: {e}")

  if photo_delivered:
    print("📲 Telegram dispatch completed successfully!")
    return True
  else:
    print("❌ Telegram photo delivery failed.")
    return False
