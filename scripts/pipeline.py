"""End-to-end MahaSpark pipeline (one story per run).

RSS fetch -> Sheet queue -> prime-time 5W1H + phonetic TTS script -> Gemini voiceover ->
faster-whisper alignment -> Remotion render -> Telegram.

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
import media_fetch
import send_telegram
from config import COMPOSITION_ID, OUT_DIR, REEL_PATH, REMOTION_DIR, STORY_PATH, VOICEOVER_PATH
from llm_providers import ContentRejected, LLMUnavailableError
from sheet_queue import DONE, ERROR, PENDING, PROCESSING, REJECTED, SheetQueue

MAX_NEW_ITEMS_PER_RUN = 2
MIN_CONTEXT_CHARS = 80  # title + RSS summary needed when the article page cannot be read
MAX_CANDIDATES_TO_CHECK = 15  # feed items inspected per run while looking for readable articles
MAX_STORIES_PER_RUN = int(os.getenv("MAX_STORIES_PER_RUN", "2") or "2")  # matches the 2 items queued per run
RUN_BUDGET_SECONDS = int(os.getenv("RUN_BUDGET_SECONDS", "1800") or "1800")  # no new story is started after this


def queue_new_items(queue: SheetQueue, max_items: int = MAX_NEW_ITEMS_PER_RUN) -> int:
    known = queue.known_keys()
    added = checked = 0
    print("🔍 Scanning RSS feeds for Maharashtra and national updates...")
    for candidate in fetch_news.iter_candidates():
        if added >= max_items or checked >= MAX_CANDIDATES_TO_CHECK:
            break
        raw = candidate.raw_input
        if raw.lower() in known or candidate.title.lower() in known:
            continue
        checked += 1
        url = fetch_news.resolve_article_url(candidate.link)
        if url and url.lower() in known:
            continue
        # A story can be written from the headline and RSS summary alone, so an unreadable publisher page is
        # no longer a reason to skip it. Only items with almost no text at all are left out.
        if not fetch_news.fetch_article_text(url) and len(candidate.title) + len(candidate.summary) < MIN_CONTEXT_CHARS:
            print(f"⏭️ Skipped, too little text to write from: {candidate.title[:70]}")
            continue
        queue.append_pending(raw, url)
        known.update({raw.lower(), candidate.title.lower(), url.lower()})
        added += 1
        print(f"📥 Queued: {candidate.title}")
    print(f"✅ Ingestion complete: {added} new item(s) queued.")
    return added


def render_concurrency() -> int:
    """Remotion refuses a concurrency above the CPU core count (GitHub runners have only 2 cores)."""
    cores = max(1, os.cpu_count() or 1)
    try:
        wanted = int(os.getenv("REMOTION_CONCURRENCY", "") or cores)
    except ValueError:
        wanted = cores
    return max(1, min(wanted, cores))


def render_reel(output=REEL_PATH, crf: int = 18) -> None:
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
        f"--crf={crf}",
        f"--concurrency={render_concurrency()}",
    ]
    print("🎬 Rendering reel with Remotion...")
    result = subprocess.run(cmd, cwd=REMOTION_DIR)
    if result.returncode != 0 or not os.path.exists(output):
        raise RuntimeError(f"Remotion render failed with exit code {result.returncode}")


def add_voice_and_timings(story: dict) -> dict:
    """Voiceover + word timings. If no TTS model works, fall back to a voiceless story (never lose the post)."""
    try:
        editorial_engine.synthesize_voiceover(story["tts_narration_script"], VOICEOVER_PATH)
        return align_timings.main(STORY_PATH, VOICEOVER_PATH)
    except LLMUnavailableError as exc:
        print(f"🔇 Voiceover unavailable, rendering a voiceless reel instead: {str(exc)[:300]}")
        VOICEOVER_PATH.unlink(missing_ok=True)
        return align_timings.main_voiceless(STORY_PATH)


def add_visuals(story: dict) -> dict:
    """Per-scene stock footage / public-figure photo. Any failure just leaves the studio backgrounds."""
    try:
        return media_fetch.attach_media(story)
    except Exception as exc:  # noqa: BLE001
        print(f"ℹ️ Visuals skipped: {type(exc).__name__}: {str(exc)[:120]}")
        return story


def reel_crf(story: dict) -> int:
    """Footage is busier than the studios; a slightly higher CRF keeps the file under Telegram's 50 MB limit."""
    return 21 if media_fetch.has_media(story) else 18


def produce_reel(title: str, summary: str, article_text: str, source_url: str) -> dict:
    """Script -> voiceover -> alignment -> render. Returns the final story dict."""
    story = editorial_engine.write_story(title, summary, article_text, source_url)
    editorial_engine.save_story(story)
    print(f"📝 Script ready ({story['visual_theme']}, {story['audio_mood']}): {story['scenes'][0]['headline']}")

    story = add_voice_and_timings(story)
    story = add_visuals(story)
    render_reel(crf=reel_crf(story))
    return story


def deliver(story: dict, source_url: str) -> str:
    """Send to Telegram. Returns the status text for the Sheet."""
    telegram_ok = send_telegram.send_reel(REEL_PATH, story, source_url)
    voice = " (voiceless)" if story.get("audio") is False else ""
    return f"SUCCESS{voice} - Telegram: {'OK' if telegram_ok else 'FAIL'}"


def run_scheduled() -> int:
    queue = SheetQueue.connect()
    try:
        queue_new_items(queue)
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ Ingestion error: {exc}")

    try:
        editorial_engine.set_avoid_theme(queue.last_theme())
    except Exception as exc:  # noqa: BLE001 - variety is a nicety, never a blocker
        print(f"ℹ️ Could not read the previous studio: {exc}")

    print("\n⚙️ Scanning the sheet for PENDING items...")
    processed = published = 0  # processed counts every story attempted, so failures also respect the limit
    started = time.monotonic()
    for row in queue.pending_rows():
        if processed >= MAX_STORIES_PER_RUN:
            break
        if processed and time.monotonic() - started > RUN_BUDGET_SECONDS:
            print("⏱️ Run time budget used; the remaining stories stay PENDING for the next run.")
            break
        print(f"\n⚡ Processing row {row.index}: {row.raw_input[:70]}...")
        queue.set_status(row.index, PROCESSING)
        title, _, summary = row.raw_input.partition(" - ")

        try:
            # Older rows may still hold an unresolved Google News link, so resolve it again here.
            source_url = fetch_news.resolve_article_url(row.source_url)
            article = fetch_news.fetch_article_text(source_url)
            if not article:
                print("ℹ️ No full article text available; using the RSS title and summary only.")
            story = produce_reel(title, summary, article, source_url)
            queue.write_story(row.index, story)
            status_note = deliver(story, source_url)
            queue.set_status(row.index, DONE, status_note)
            print(f"✅ Row {row.index} completed.")
            processed += 1
            published += 1

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
            processed += 1

        time.sleep(2)

    if published == 0:
        print("ℹ️ Nothing was published in this run.")
        if processed > 0:
            return 1  # a story was attempted and failed: make the workflow run show as failed
    return 0


def run_adhoc(text: str, url: str, skip_telegram: bool, skip_render: bool) -> int:
    """Local one-off run from pasted text; does not touch the Google Sheet."""
    title, _, rest = text.strip().partition("\n")
    story = editorial_engine.write_story(title, "", rest or title, url)
    editorial_engine.save_story(story)
    story = add_voice_and_timings(story)
    story = add_visuals(story)
    if skip_render:
        print(f"✅ Script, voiceover and timings are ready in {STORY_PATH.parent}")
        return 0
    render_reel(crf=reel_crf(story))
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
