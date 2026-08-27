import json
import os
import time
import gspread
from image_generator import generate_ai_background
from news_fetcher import fetch_and_queue_news
from news_writer import generate_news_content
from renderer import render_news_tile
from telegram_notifier import send_news_post

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1Hoq6Qshq7RZNh3cV7AmmUqVbF1ULnwXqf1uaU4_FlC4")
CREDS_FILE = "credentials.json"


def get_sheet_client():
  gc = gspread.service_account(filename=CREDS_FILE)
  return gc.open_by_key(SHEET_ID).sheet1


def run_autonomous_pipeline():
  # 1. Fetch breaking news and record initial creation time
  print("📡 [1/2] Fetching live Marathi breaking news...")
  try:
    fetch_and_queue_news(max_items_per_run=2)
  except Exception as e:
    print(f"⚠️ Ingestion error: {e}")

  # 2. Process Pending Queue
  print("\n⚙️ [2/2] Scanning sheet for PENDING items...")
  sheet = get_sheet_client()
  records = sheet.get_all_records()

  for i, row in enumerate(records, start=2):
    status = str(row.get("Status", "")).strip().upper()
    raw_input = str(row.get("Raw_News_Input", "")).strip()

    if status == "PENDING" and raw_input:
      print(f"\n⚡ Processing Row {i}: {raw_input[:60]}...")

      # Update status to PROCESSING (Col L Created_At is NOT modified)
      sheet.update_cell(i, 1, "PROCESSING")

      try:
        # Step A: Copywriting via Gemini
        pack = generate_news_content(raw_input)

        # Step B: Background via Free Flux
        bg_path = generate_ai_background(pack["visual_prompt"])
        pack["background_path"] = bg_path

        # Step C: Rendering via Playwright
        output_path = f"output/post_row_{i}.png"
        final_image = render_news_tile(pack, output_path)

        # Step D: Update Data Columns (Cols 3 through 11)
        sheet.update_cell(i, 3, pack.get("badge", ""))
        sheet.update_cell(
            i,
            4,
            f"{pack.get('headline_part1', '')} {pack.get('headline_part2', '')}",
        )
        sheet.update_cell(i, 5, pack.get("hook_pill", ""))
        sheet.update_cell(
            i, 6, json.dumps(pack.get("bullets", []), ensure_ascii=False)
        )
        sheet.update_cell(i, 7, pack.get("yt_shorts_title", ""))
        sheet.update_cell(i, 8, pack.get("yt_shorts_description", ""))
        sheet.update_cell(i, 9, pack.get("yt_shorts_tags", ""))
        sheet.update_cell(
            i,
            10,
            f"{pack.get('ig_reels_caption', '')}\n\n{pack.get('ig_hashtags', '')}",
        )
        sheet.update_cell(i, 11, os.path.abspath(final_image))

        # Step E: Dispatch to Telegram
        send_news_post(final_image, pack)

        # Step F: Mark Success & Log Outcome (Col M)
        sheet.update_cell(i, 1, "DONE")
        sheet.update_cell(i, 13, "SUCCESS - Delivered to Telegram")
        print(f"✅ Row {i} processed and delivered!")

      except Exception as e:
        err_msg = f"{type(e).__name__}: {str(e)[:250]}"
        print(f"❌ Error on row {i}: {err_msg}")
        sheet.update_cell(i, 1, "ERROR")
        sheet.update_cell(i, 13, err_msg)  # Col M: Error_Log

      # Pacing delay between rows to respect API rate limits
      time.sleep(4)


if __name__ == "__main__":
  run_autonomous_pipeline()
