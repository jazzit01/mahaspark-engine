import json
import os
import time
import gspread
from image_generator import generate_ai_background
from instagram_publisher import post_reel_to_facebook, post_reel_to_instagram
from news_fetcher import fetch_and_queue_news
from news_writer import generate_news_content
from renderer import render_news_tile
from telegram_notifier import send_news_video
from video_renderer import create_news_reel

SHEET_ID = os.getenv(
    "GOOGLE_SHEET_ID", "1Hoq6Qshq7RZNh3cV7AmmUqVbF1ULnwXqf1uaU4_FlC4"
)
CREDS_FILE = "credentials.json"


def get_sheet_client():
  gc = gspread.service_account(filename=CREDS_FILE)
  return gc.open_by_key(SHEET_ID).sheet1


def run_autonomous_pipeline():
  # 1. Ingest breaking news
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
      sheet.update_cell(i, 1, "PROCESSING")

      try:
        # Step A: Copywriting via Gemini
        pack = generate_news_content(raw_input)

        # Step B: Background Visual via Flux AI Generator
        entity_q = pack.get("person_or_event_query", "")
        bg_path = generate_ai_background(
            pack.get("visual_prompt", ""), entity_query=entity_q
        )
        pack["background_path"] = bg_path

        # Step C: Rendering Graphic Card via Playwright
        output_path = f"output/post_row_{i}.png"
        final_image = render_news_tile(pack, output_path)

        # Step D: Single Batch Update for Columns C to K (Cols 3 to 11)
        full_headline = (
            f"{pack.get('headline_part1', '')}"
            f" {pack.get('headline_part2', '')}"
        ).strip()
        caption_text = (
            f"{pack.get('ig_reels_caption', '')}\n\n{pack.get('ig_hashtags', '')}"
        )

        content_row = [
            pack.get("badge", ""),
            full_headline,
            pack.get("hook_pill", ""),
            json.dumps(pack.get("bullets", []), ensure_ascii=False),
            pack.get("yt_shorts_title", ""),
            pack.get("yt_shorts_description", ""),
            pack.get("yt_shorts_tags", ""),
            caption_text,
            os.path.abspath(final_image),
        ]
        sheet.update(range_name=f"C{i}:K{i}", values=[content_row])

        # Step E: Build the 6-second mood-matched video
        mood = pack.get("audio_mood", "neutral")
        video_path = f"output/reel_{i}.mp4"
        create_news_reel(
            image_path=final_image, mood=mood, output_video_path=video_path
        )

        # Step F: Dispatch Video to Telegram
        tg_success = send_news_video(video_path, pack)

        # Step G: Publish to Instagram Reels + Facebook Reels
        ig_success = False
        fb_success = False

        try:
          post_reel_to_instagram(video_path, caption_text)
          ig_success = True
        except Exception as ig_err:
          print(f"⚠️ Instagram Reel error (non-fatal): {ig_err}")

        try:
          post_reel_to_facebook(video_path, caption_text)
          fb_success = True
        except Exception as fb_err:
          print(f"⚠️ Facebook Reel error (non-fatal): {fb_err}")

        # Step H: Mark Success & Log Outcome (Col A and M)
        sheet.update_cell(i, 1, "DONE")
        status_msg = (
            f"SUCCESS - Telegram Video: {'OK' if tg_success else 'FAIL'} | IG"
            f" Reel: {'OK' if ig_success else 'FAIL'} | FB Reel:"
            f" {'OK' if fb_success else 'FAIL'}"
        )
        sheet.update_cell(i, 13, status_msg)

        print(f"✅ Row {i} processed successfully!")

      except Exception as e:
        err_msg = f"{type(e).__name__}: {str(e)[:250]}"
        print(f"❌ Error on row {i}: {err_msg}")
        sheet.update_cell(i, 1, "ERROR")
        sheet.update_cell(i, 13, err_msg)

      # Pacing delay between rows
      time.sleep(4)


if __name__ == "__main__":
  run_autonomous_pipeline()