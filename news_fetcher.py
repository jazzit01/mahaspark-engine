from datetime import datetime
import os
import time
import zoneinfo
import feedparser
import gspread

SHEET_ID = os.getenv(
    "GOOGLE_SHEET_ID", "1Hoq6Qshq7RZNh3cV7AmmUqVbF1ULnwXqf1uaU4_FlC4"
)
CREDS_FILE = "credentials.json"

# Curated High-Authority RSS Feeds for Maharashtra & Breaking News
RSS_FEEDS = [
    # Google News - Marathi Top Stories (Location-tuned)
    "https://news.google.com/rss/headlines/section/topic/NATION?hl=mr&gl=IN&ceid=IN:mr",
    # Google News - Maharashtra Regional Focus
    "https://news.google.com/rss/search?q=Maharashtra+OR+Pune+when:12h&hl=mr&gl=IN&ceid=IN:mr",
    # Lokmat Maharashtra Live RSS
    "https://www.lokmat.com/rss/maharashtra.xml",
]


def get_current_ist_time() -> str:
  """Returns the exact current IST timestamp when the story is queued."""
  ist_zone = zoneinfo.ZoneInfo("Asia/Kolkata")
  return datetime.now(ist_zone).strftime("%d-%m-%Y %I:%M:%S %p")


def get_sheet():
  gc = gspread.service_account(filename=CREDS_FILE)
  return gc.open_by_key(SHEET_ID).sheet1


def fetch_and_queue_news(max_items_per_run: int = 3):
  sheet = get_sheet()
  records = sheet.get_all_records()

  # Collect all existing headlines to prevent duplicates
  existing_headlines = set()
  for r in records:
    raw = str(r.get("Raw_News_Input", "")).strip().lower()
    if raw:
      existing_headlines.add(raw)

  print(
      f"🔍 Scanning RSS feeds for breaking Maharashtra & national updates..."
  )
  new_entries_added = 0

  for feed_url in RSS_FEEDS:
    if new_entries_added >= max_items_per_run:
      break

    try:
      parsed = feedparser.parse(feed_url)
      for entry in parsed.entries[:5]:  # Check the top 5 latest items
        title = entry.get("title", "").strip()
        summary = entry.get("summary", "").strip()

        # Combine title and snippet for full context
        full_text = f"{title} - {summary}" if summary else title
        full_text_clean = " ".join(full_text.split())[:300]

        # Deduplication check
        if (
            not title
            or title.lower() in existing_headlines
            or full_text_clean.lower() in existing_headlines
        ):
          continue

        # Get the creation timestamp
        added_time = get_current_ist_time()

        # Build full 13-column array to lock timestamp into Col L (index 12)
        row_data = [
            "PENDING",  # Col A (1): Status
            full_text_clean,  # Col B (2): Raw_News_Input
            "",  # Col C (3): Badge
            "",  # Col D (4): Headline
            "",  # Col E (5): Hook_Pill
            "",  # Col F (6): Bullets
            "",  # Col G (7): YT_Title
            "",  # Col H (8): YT_Desc
            "",  # Col I (9): YT_Tags
            "",  # Col J (10): IG_Caption
            "",  # Col K (11): Image_Path
            added_time,  # Col L (12): Created_At
            "",  # Col M (13): Error_Log
        ]

        sheet.append_row(row_data)
        existing_headlines.add(title.lower())
        existing_headlines.add(full_text_clean.lower())
        new_entries_added += 1
        print(f"📥 Queued new story ({added_time}): {title}")

        if new_entries_added >= max_items_per_run:
          break

    except Exception as e:
      print(f"⚠️ Failed reading feed {feed_url}: {e}")

  print(f"✅ News Ingestion Complete: {new_entries_added} new items queued.")


if __name__ == "__main__":
  fetch_and_queue_news()
