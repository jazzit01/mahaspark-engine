"""End-to-end MahaSpark pipeline (one story per run).

RSS fetch -> Sheet queue -> prime-time 5W1H + phonetic TTS script -> Gemini voiceover ->
faster-whisper alignment -> Remotion render -> Telegram (+ optional Instagram).

Scheduled use (GitHub Actions):   python scripts/pipeline.py
Local one-off, no Sheet needed:   python scripts/pipeline.py --text "<article text>" --url <url> --skip-telegram
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time

import align_timings
import editorial_engine
import fetch_news
import send_telegram
from config import COMPOSITION_ID, OUT_DIR, REEL_PATH, REMOTION_DIR, STORY_PATH, VOICEOVER_PATH
from llm_providers import ContentRejected, LLMUnavailableError
from publish_instagram import instagram_enabled, post_reel_to_instagram
from sheet_queue import DONE, ERROR, PENDING, PROCESSING, REJECTED, SheetQueue

MAX_NEW_ITEMS_PER_RUN = 2
MAX_STORIES_PER_RUN = int(os.getenv("MAX_STORIES_PER_RUN", "1") or "1")


def queue_new_items(queue: SheetQueue, max_items: int = MAX_NEW_ITEMS_PER_RUN) -> int:
    known = queue.known_keys()
    added = 0
    print("🔍 Scanning RSS feeds for Maharashtra and national updates...")
    for candidate in fetch_news.iter_candidates():
        if added >= max_items:
            break
        raw = candidate.raw_input
        if raw.lower() in known or candidate.title.lower() in known:
            continue
        url = fetch_news.resolve_article_url(candidate.link)
        if url and url.lower() in known:
            continue
        queue.append_pending(raw, url)
        known.update({raw.lower(), candidate.title.lower(), url.lower()})
        added += 1
        print(f"📥 Queued: {candidate.title}")
    print(f"✅ Ingestion complete: {added} new item(s) queued.")
    return added


def render_reel(output=REEL_PATH) -> None:
    """Render the Remotion composition with the studio chosen by story.json's visual_theme."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        "npx",
        "remotion",
        "render",
        "src/index.ts",
        COMPOSITION_ID,
        str(output),
        "--props=public/story.json",
        "--codec=h264",
        "--crf=18",
        f"--concurrency={os.getenv('REMOTION_CONCURRENCY', '3')}",
    ]
    print("🎬 Rendering reel with Remotion...")
    result = subprocess.run(cmd, cwd=REMOTION_DIR)
    if result.returncode != 0 or not os.path.exists(output):
        raise RuntimeError(f"Remotion render failed with exit code {result.returncode}")


def produce_reel(title: str, summary: str, article_text: str, source_url: str) -> dict:
    """Script -> voiceover -> alignment -> render. Returns the final story dict."""
    story = editorial_engine.write_story(title, summary, article_text, source_url)
    editorial_engine.save_story(story)
    print(f"📝 Script ready ({story['visual_theme']}, {story['audio_mood']}): {story['scenes'][0]['headline']}")

    editorial_engine.synthesize_voiceover(story["tts_narration_script"], VOICEOVER_PATH)
    story = align_timings.main(STORY_PATH, VOICEOVER_PATH)
    render_reel()
    return story


def deliver(story: dict, source_url: str) -> str:
    """Send to Telegram, then Instagram when enabled. Returns the status text for the Sheet."""
    telegram_ok = send_telegram.send_reel(REEL_PATH, story, source_url)

    instagram_status = "OFF"
    if instagram_enabled():
        try:
            caption = f"{story.get('social_caption', '')}\n\n{story.get('hashtags', '')}".strip()
            post_reel_to_instagram(str(REEL_PATH), caption)
            instagram_status = "OK"
        except Exception as exc:  # noqa: BLE001
            instagram_status = "FAIL"
            print(f"⚠️ Instagram Reel error: {exc}")
    else:
        print("⏭️ Instagram posting is off (ENABLE_INSTAGRAM is not 'true'). Telegram only.")

    return f"SUCCESS - Telegram: {'OK' if telegram_ok else 'FAIL'} | IG Reel: {instagram_status}"


def run_scheduled() -> int:
    queue = SheetQueue.connect()
    try:
        queue_new_items(queue)
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ Ingestion error: {exc}")

    print("\n⚙️ Scanning the sheet for PENDING items...")
    processed = 0
    for row in queue.pending_rows():
        if processed >= MAX_STORIES_PER_RUN:
            break
        print(f"\n⚡ Processing row {row.index}: {row.raw_input[:70]}...")
        queue.set_status(row.index, PROCESSING)
        title, _, summary = row.raw_input.partition(" - ")

        try:
            article = fetch_news.fetch_article_text(row.source_url)
            if not article:
                print("ℹ️ No full article text available; using the RSS title and summary only.")
            story = produce_reel(title, summary, article, row.source_url)
            queue.write_story(row.index, story)
            status_note = deliver(story, row.source_url)
            queue.set_status(row.index, DONE, status_note)
            print(f"✅ Row {row.index} completed.")
            processed += 1

        except ContentRejected as exc:
            print(f"🚫 Row {row.index} rejected: {exc}")
            queue.set_status(row.index, REJECTED, f"Rejected: {str(exc)[:240]}")

        except LLMUnavailableError as exc:
            # The story is fine; no AI provider could be used. Requeue it (ERROR is never retried).
            print(f"⏸️ Row {row.index} returned to PENDING: {exc}")
            queue.set_status(row.index, PENDING, f"AI unavailable, will retry next run: {str(exc)[:220]}")
            print("❌ No AI provider could be used in this run. Check the API keys and model names above.")
            return 1

        except Exception as exc:  # noqa: BLE001
            message = f"{type(exc).__name__}: {str(exc)[:250]}"
            print(f"❌ Error on row {row.index}: {message}")
            queue.set_status(row.index, ERROR, message)

        time.sleep(2)

    if processed == 0:
        print("ℹ️ Nothing was published in this run.")
    return 0


def run_adhoc(text: str, url: str, skip_telegram: bool, skip_render: bool) -> int:
    """Local one-off run from pasted text; does not touch the Google Sheet."""
    title, _, rest = text.strip().partition("\n")
    story = editorial_engine.write_story(title, "", rest or title, url)
    editorial_engine.save_story(story)
    editorial_engine.synthesize_voiceover(story["tts_narration_script"], VOICEOVER_PATH)
    story = align_timings.main(STORY_PATH, VOICEOVER_PATH)
    if skip_render:
        print(f"✅ Script, voiceover and timings are ready in {STORY_PATH.parent}")
        return 0
    render_reel()
    if skip_telegram:
        print(f"✅ Reel rendered: {REEL_PATH}")
        return 0
    deliver(story, url)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MahaSpark prime-time reel pipeline")
    parser.add_argument("--text", help="Run once on this article text (first line = title); skips the Sheet.")
    parser.add_argument("--url", default="", help="Source URL for --text runs.")
    parser.add_argument("--skip-render", action="store_true", help="Stop after script, voiceover and timings.")
    parser.add_argument("--skip-telegram", action="store_true", help="Render but do not send.")
    args = parser.parse_args()

    if not args.skip_render and shutil.which("npx") is None:
        print("⚠️ npx not found; the Remotion render step will fail.")

    try:
        if args.text:
            return run_adhoc(args.text, args.url, args.skip_telegram, args.skip_render)
        return run_scheduled()
    except ContentRejected as exc:
        print(f"🚫 Story rejected: {exc}")
        return 2
    except LLMUnavailableError as exc:
        print(f"❌ AI unavailable: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
