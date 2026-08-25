import json
import os
import time
import gspread
from image_generator import generate_ai_background
from news_fetcher import fetch_and_queue_news
from news_writer import generate_news_content
from renderer import render_news_tile
from telegram_notifier import send_news_post

SHEET_ID = "1Hoq6Qshq7RZNh3cV7AmmUqVbF1ULnwXqf1uaU4_FlC4"
CREDS_FILE = "credentials.json"


def get_sheet_client(max_retries: int = 3):
  for attempt in range(1, max_retries + 1):
    try:
      gc = gspread.service_account(filename=CREDS_FILE)
      return gc.open_by_key(SHEET_ID).sheet1
    except Exception as e:
      if attempt == max_retries:
        raise e
      print(
          f"⚠️ Network handshake failed. Retrying connection"
          f" ({attempt}/{max_retries})..."
      )
      time.sleep(2)


def process_pending_news():
  # 1. Fetch live RSS news and append to sheet first
  try:
    fetch_and_queue_news(max_items_per_run=2)
  except Exception as e:
    print(f"⚠️ Auto-fetch error (continuing with existing queue): {e}")

  # 2. Process all pending items
  sheet = get_sheet_client()
  records = sheet.get_all_records()
  print("📊 Scanning sheet for PENDING news items...")

  for i, row in enumerate(records, start=2):
    status = str(row.get("Status", "")).strip().upper()
    raw_input = str(row.get("Raw_News_Input", "")).strip()

    if status == "PENDING" and raw_input:
      print("\n" + "=" * 60)
      print(f"⚡ Processing Row {i}: {raw_input[:60]}...")
      print("=" * 60)

      sheet.update_cell(i, 1, "PROCESSING")

      try:
        pack = generate_news_content(raw_input)
        bg_path = generate_ai_background(pack["visual_prompt"])
        pack["background_path"] = bg_path

        output_path = f"output/post_row_{i}.png"
        final_image = render_news_tile(pack, output_path)

        sheet.update_cell(i, 3, pack["badge"])
        sheet.update_cell(
            i, 4, f"{pack['headline_part1']} {pack['headline_part2']}"
        )
        sheet.update_cell(i, 5, pack["hook_pill"])
        sheet.update_cell(
            i, 6, json.dumps(pack["bullets"], ensure_ascii=False)
        )
        sheet.update_cell(i, 7, pack["yt_shorts_title"])
        sheet.update_cell(i, 8, pack["yt_shorts_description"])
        sheet.update_cell(i, 9, pack["yt_shorts_tags"])
        sheet.update_cell(
            i, 10, f"{pack['ig_reels_caption']}\n\n{pack['ig_hashtags']}"
        )
        sheet.update_cell(i, 11, os.path.abspath(final_image))

        send_news_post(final_image, pack)
        sheet.update_cell(i, 1, "DONE")
        print(f"✅ Row {i} Processed & Dispatched!")

      except Exception as e:
        print(f"❌ Error processing row {i}: {e}")
        sheet.update_cell(i, 1, "ERROR")


if __name__ == "__main__":
  process_pending_news()
