import time
import feedparser
import gspread

SHEET_ID = "1Hoq6Qshq7RZNh3cV7AmmUqVbF1ULnwXqf1uaU4_FlC4"
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

        # Append row to Google Sheets
        row_data = [
            "PENDING",  # Col A: Status
            full_text_clean,  # Col B: Raw_News_Input
        ]

        sheet.append_row(row_data)
        existing_headlines.add(title.lower())
        existing_headlines.add(full_text_clean.lower())
        new_entries_added += 1
        print(f"📥 Queued new story: {title}")

        if new_entries_added >= max_items_per_run:
          break

    except Exception as e:
      print(f"⚠️ Failed reading feed {feed_url}: {e}")

  print(f"✅ News Ingestion Complete: {new_entries_added} new items queued.")


if __name__ == "__main__":
  fetch_and_queue_news()
