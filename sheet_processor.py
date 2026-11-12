import glob
import json
import os
import sys
import time
import gspread

from image_generator import generate_ai_background
from news_fetcher import fetch_and_queue_news
from news_writer import LLMUnavailableError, generate_news_content
from renderer import render_news_tile
from video_renderer import create_news_reel
from telegram_notifier import send_news_video

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1Hoq6Qshq7RZNh3cV7AmmUqVbF1ULnwXqf1uaU4_FlC4")
CREDS_FILE = "credentials.json"


def get_sheet_client():
    gc = gspread.service_account(filename=CREDS_FILE)
    return gc.open_by_key(SHEET_ID).sheet1


def instagram_enabled() -> bool:
    """Instagram auto-posting is opt-in. Anything other than 'true' keeps it off."""
    return os.getenv("ENABLE_INSTAGRAM", "").strip().lower() == "true"


def cleanup_temp_outputs(row_index: int):
    """Deletes temporary PNG plates and MP4 video once published to save disk storage."""
    patterns = [
        f"output/post_row_{row_index}*.png",
        f"output/reel_{row_index}*.mp4",
        f"output/reel_{row_index}*.jpg",
    ]
    for pattern in patterns:
        for file_path in glob.glob(pattern):
            try:
                os.remove(file_path)
            except OSError:
                pass


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
    
    # Read rows directly by index to avoid header duplicate errors
    all_rows = sheet.get_all_values()
    if not all_rows or len(all_rows) < 2:
        print("ℹ️ No rows found to process.")
        return

    headers = [h.strip() for h in all_rows[0]]
    status_col_idx = headers.index("Status") if "Status" in headers else 0
    raw_col_idx = headers.index("Raw_News_Input") if "Raw_News_Input" in headers else 1

    providers_unavailable = False

    for i, row in enumerate(all_rows[1:], start=2):
        status = row[status_col_idx].strip().upper() if len(row) > status_col_idx else ""
        raw_input = row[raw_col_idx].strip() if len(row) > raw_col_idx else ""

        if status == "PENDING" and raw_input:
            print(f"\n⚡ Processing Row {i}: {raw_input[:60]}...")
            sheet.update_cell(i, 1, "PROCESSING")

            try:
                # Step A: Copywriting via Gemini
                pack = generate_news_content(raw_input)

                # Step B: Pick asset background
                bg_path = generate_ai_background()
                pack["background_path"] = bg_path

                # Step C: Render graphic plates
                output_path = f"output/post_row_{i}.png"
                rendered_layers = render_news_tile(pack, output_path)
                final_image = rendered_layers["full"]

                # Step D: Save copywriting and tags to Sheet
                full_headline = f"{pack.get('headline_part1', '')} {pack.get('headline_part2', '')}".strip()
                caption_text = f"{pack.get('ig_reels_caption', '')}\n\n{pack.get('ig_hashtags', '')}"

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

                # Step E: Render video with timeline transitions
                mood = pack.get("audio_mood", "neutral")
                video_path = f"output/reel_{i}.mp4"
                create_news_reel(layers=rendered_layers, mood=mood, output_video_path=video_path)

                # Step F: Dispatch to Telegram
                tg_success = send_news_video(video_path, pack)

                # Step G: Publish to Instagram Reels (OFF by default: Telegram only).
                # Turn it back on with the repository variable ENABLE_INSTAGRAM=true.
                ig_status = "OFF"
                if instagram_enabled():
                    try:
                        from instagram_publisher import post_reel_to_instagram

                        post_reel_to_instagram(video_path, caption_text)
                        ig_status = "OK"
                    except Exception as ig_err:
                        ig_status = "FAIL"
                        print(f"⚠️ Instagram Reel error: {ig_err}")
                else:
                    print("⏭️ Instagram posting is off (ENABLE_INSTAGRAM is not 'true'). Telegram only.")

                # Step H: Update Status in Sheet
                sheet.update_cell(i, 1, "DONE")
                status_msg = f"SUCCESS - Telegram: {'OK' if tg_success else 'FAIL'} | IG Reel: {ig_status}"
                sheet.update_cell(i, 13, status_msg)

                # Step I: Delete temp images and video immediately after dispatch
                cleanup_temp_outputs(i)
                print(f"🧹 Cleaned up temporary files for row {i}")
                print(f"✅ Row {i} completed!")

            except LLMUnavailableError as e:
                # The story is fine, no AI provider could be used. Put it back in the queue (not
                # ERROR, which is never retried) and stop: every other row would fail the same way.
                err_msg = f"AI unavailable, will retry next run: {str(e)[:220]}"
                print(f"⏸️ Row {i} returned to PENDING. {err_msg}")
                sheet.update_cell(i, 1, "PENDING")
                sheet.update_cell(i, 13, err_msg)
                providers_unavailable = True
                break

            except Exception as e:
                err_msg = f"{type(e).__name__}: {str(e)[:250]}"
                print(f"❌ Error on row {i}: {err_msg}")
                sheet.update_cell(i, 1, "ERROR")
                sheet.update_cell(i, 13, err_msg)

            time.sleep(4)

    if providers_unavailable:
        # Make the GitHub Actions run show as failed (and email you) instead of a misleading green tick.
        print("❌ No AI provider could be used in this run. Check the API keys and model names above.")
        sys.exit(1)


if __name__ == "__main__":
    run_autonomous_pipeline()