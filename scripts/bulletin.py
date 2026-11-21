"""MahaSpark news bulletin: ten fresh stories as one 16:9 video for YouTube.

    RSS -> ten items (headline + one context line + spoken sentences) -> per-item Gemini TTS -> Commons photos
        -> remotion/public/bulletin.json -> Remotion "MahaSparkBulletin" (one render) -> YouTube -> Telegram link

Run ``python scripts/bulletin.py`` (scheduled, 07:00 and 17:00 IST) or with ``--skip-render`` / ``--skip-upload`` /
``--skip-telegram`` for a local trial. Every story is a real, fresh feed item; nothing is invented.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import align_timings
import bulletin_editorial
import editorial_engine
import fetch_news
import media_fetch
import send_telegram
import manual_kit
import youtube_upload
from config import (
    BULLETIN_COMPOSITION_ID,
    BULLETIN_DIR,
    BULLETIN_JSON,
    BULLETIN_PATH,
    OUT_DIR,
    REMOTION_DIR,
    THUMB_JSON,
    THUMB_PATH,
)
from llm_providers import ContentRejected, LLMUnavailableError
from sheet_queue import IST, SheetQueue

TARGET_ITEMS = int(os.getenv("BULLETIN_ITEMS", "10") or "10")
MIN_ITEMS = 5  # fewer good stories than this: no bulletin is published
PER_FEED = 8
MAX_CANDIDATES = 45
SIMILAR_TITLE = 0.75
LEAD_SECONDS, TAIL_SECONDS, MIN_ITEM_SECONDS = 0.5, 0.9, 10.0  # 10 s keeps every YouTube chapter valid
OUTRO_SECONDS = 8.0
MIN_CHAPTER_SECONDS = 10
RUN_BUDGET_SECONDS = int(os.getenv("BULLETIN_BUDGET_SECONDS", "1500") or "1500")
CHANNEL_HASHTAGS = "#MahaSpark #मराठीबातम्या #MarathiNews #ताज्याबातम्या #महाराष्ट्र"
BASE_TAGS = ["MahaSpark", "मराठी बातम्या", "Marathi News", "ताज्या बातम्या", "महाराष्ट्र बातम्या", "Maharashtra News", "बातम्या", "Marathi News Today"]


# ----- helpers ---------------------------------------------------------------------------------


def slot_for(now: datetime | None = None) -> tuple[str, str]:
    """(label used in titles, short slot id) from the IST clock: morning before noon, evening after."""
    now = now or datetime.now(IST)
    return ("सकाळच्या", "morning") if now.hour < 12 else ("संध्याकाळच्या", "evening")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def is_duplicate(title: str, seen_titles: list[str], known: set[str]) -> bool:
    low = title.strip().lower()
    if low in known:
        return True
    norm = _norm(title)
    return any(difflib.SequenceMatcher(None, norm, _norm(other)).ratio() >= SIMILAR_TITLE for other in seen_titles)


def interleave(batches: list[list]) -> list:
    """Round-robin merge so one feed cannot fill the whole bulletin."""
    out, i = [], 0
    while any(i < len(b) for b in batches):
        out.extend(b[i] for b in batches if i < len(b))
        i += 1
    return out


def gather_candidates(feeds: list[str] | None = None) -> list:
    feeds = feeds or fetch_news.rss_feeds()
    batches = [list(fetch_news.iter_candidates([feed], per_feed=PER_FEED)) for feed in feeds]
    return interleave(batches)


# ----- 1. items --------------------------------------------------------------------------------


def collect_items(known: set[str], candidates: list, want: int = TARGET_ITEMS, deadline: float | None = None) -> list[dict]:
    """Write items from fresh candidates until ``want`` exist. Rejections and unreadable sources are skipped."""
    items: list[dict] = []
    seen_titles: list[str] = []
    checked = 0
    for cand in candidates:
        if len(items) >= want or checked >= MAX_CANDIDATES or (deadline and time.time() > deadline):
            break
        if is_duplicate(cand.title, seen_titles, known):
            continue
        checked += 1
        url = fetch_news.resolve_article_url(cand.link)
        if url and url.lower() in known:
            continue
        article = fetch_news.fetch_article_text(url)
        try:
            item = bulletin_editorial.write_item(cand.title, cand.summary, article, url)
        except ContentRejected as exc:
            print(f"⏭️ Not used ({str(exc)[:80]}): {cand.title[:60]}")
            continue
        except ValueError as exc:  # repair attempt also failed: skip this story, keep the bulletin going
            print(f"⏭️ Could not write a valid item ({str(exc)[:80]}): {cand.title[:60]}")
            continue
        twin = next((i for i in items if bulletin_editorial.same_event(item, i)), None)
        if twin:
            print(f"⏭️ Same event as '{twin['headline'][:40]}', skipped: {item['headline'][:50]}")
            seen_titles.append(cand.title)
            continue
        seen_titles.append(cand.title)
        known.update({cand.title.lower(), item["headline"].lower(), (url or "").lower()} - {""})
        items.append(item)
        print(f"📰 {len(items)}/{want}: {item['headline']}")
    return items


# ----- 2. voice --------------------------------------------------------------------------------


def add_voices(items: list[dict], tts=editorial_engine.synthesize_voiceover, out_dir: Path = BULLETIN_DIR) -> list[dict]:
    """Voice every item. When the voice quota runs out the bulletin keeps the items voiced so far."""
    out_dir.mkdir(parents=True, exist_ok=True)
    voiced: list[dict] = []
    for i, item in enumerate(items):
        path = out_dir / f"item-{i}.wav"
        try:
            tts(item["tts_text"], path)
        except LLMUnavailableError as exc:
            print(f"⚠️ Voice unavailable after {len(voiced)} item(s): {exc}")
            break
        except Exception as exc:  # noqa: BLE001 - one bad clip must not lose the whole bulletin
            print(f"⚠️ Voice failed for item {i + 1}: {exc}")
            continue
        seconds = align_timings.audio_duration(path)
        item["audio"] = f"bulletin/{path.name}"
        item["audio_seconds"] = round(seconds, 2)
        item["seconds"] = round(max(MIN_ITEM_SECONDS, LEAD_SECONDS + seconds + TAIL_SECONDS), 2)
        voiced.append(item)
    return voiced


# ----- 3. photos -------------------------------------------------------------------------------


_NUMBER = re.compile(r"[₹$]?\s?[\d०-९][\d०-९,\.]*\s?(?:%|टक्के|कोटी|लाख|हजार|हेक्टर|एकर|किलोमीटर|किमी|मतांनी|जागा|जागां|वर्षे|वर्ष)?")


def highlight_for(item: dict) -> str:
    """The key figure of the item for the no-photo panel (for example '५० लाख' or '85%'), or ''."""
    for text in (item["headline"], item["context"]):
        match = _NUMBER.search(text)
        if match and len(match.group(0).strip()) >= 2:
            return match.group(0).strip()[:14]
    return ""


PHOTO_PAUSE_SECONDS = 1.5  # Wikimedia rate-limits fast bursts from CI IPs (HTTP 429)
PHOTO_RETRY_WAITS = (8, 20)


def _with_backoff(lookup, *args, sleep=time.sleep):
    """Run a Commons lookup; on HTTP 429 wait and retry (two retries), then give up with the original error."""
    for wait in (*PHOTO_RETRY_WAITS, None):
        try:
            return lookup(*args)
        except Exception as exc:  # noqa: BLE001
            if wait is None or "429" not in str(exc):
                raise
            sleep(wait)


def add_photos(items: list[dict], out_dir: Path = BULLETIN_DIR) -> list[str]:
    """A free Commons photo per item where one exists (never a face for victims/accused; see clean_public_figure).
    Items without a photo keep the animated panel. Returns the credit lines."""
    out_dir.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    credits: list[str] = []
    for i, item in enumerate(items):
        found = None
        if i:
            time.sleep(PHOTO_PAUSE_SECONDS)
        try:
            if item.get("public_figure"):
                found = _with_backoff(media_fetch.search_commons_photo, item["public_figure"])
            if not found and item.get("photo_query") and item.get("photo_keywords"):
                # The story's own subject (an IndiGo aircraft, a railway station, a landmark): the file name must
                # contain every keyword, so a loosely related picture is never used.
                found = _with_backoff(
                    media_fetch.search_commons_topic, item["photo_query"], "", used, tuple(item["photo_keywords"])
                )
        except Exception as exc:  # noqa: BLE001 - network/API failures just mean no photo
            print(f"⚠️ Photo lookup failed for item {i + 1}: {exc}")
            continue
        if not found:
            continue
        dest = out_dir / f"photo-{i}.jpg"
        if not media_fetch.download(found["url"], dest):
            continue
        used.add(found.get("title", found["url"]))
        item["photo"] = {
            "src": f"bulletin/{dest.name}",
            "width": found.get("width", 0),
            "height": found.get("height", 0),
            "credit": found["credit"],
            "is_figure": bool(item.get("public_figure")),
        }
        credits.append(found["credit"])
    return credits


# ----- 4. bulletin.json ------------------------------------------------------------------------


def assemble(items: list[dict], credits: list[str]) -> dict:
    """The props for the Remotion composition. Every start time is derived from the item durations."""
    cursor, entries = 0.0, []
    for item in items:
        entries.append(
            {
                "category": item["category"],
                "headline": item["headline"],
                "context": item["context"],
                "audio": item["audio"],
                "seconds": item["seconds"],
                "start": round(cursor, 2),
                "lead_seconds": LEAD_SECONDS,
                "photo": item.get("photo"),
                "highlight": highlight_for(item),
            }
        )
        cursor += item["seconds"]
    return {
        "items": entries,
        "outro_seconds": OUTRO_SECONDS,
        "bg_hue": editorial_engine.pick_hue(" ".join(e["headline"] for e in entries), calm=True),
        "outro_start": round(cursor, 2),
        "total_seconds": round(cursor + OUTRO_SECONDS, 2),
        "credits": credits,
    }


def write_props(props: dict, path: Path = BULLETIN_JSON) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")


# ----- 5. YouTube metadata ---------------------------------------------------------------------


def timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"


def build_title(items: list[dict], slot_label: str) -> str:
    tail = f" | {slot_label} {len(items)} मोठ्या बातम्या | MahaSpark"
    room = youtube_upload.MAX_TITLE - len(tail)
    head = items[0]["headline"]
    if len(head) > room:
        head = head[: room - 1].rstrip() + "…"
    return head + tail


def build_description(items: list[dict], props: dict, slot_label: str) -> str:
    lines = [f"MahaSpark मराठी बातम्या: {slot_label} {len(items)} ताज्या आणि महत्त्वाच्या बातम्या एकाच बुलेटिनमध्ये.", "", "⏱️ बातम्या (Chapters)"]
    chapters = [(e["start"], e["headline"]) for e in props["items"]] + [(props["outro_start"], "MahaSpark फॉलो करा")]
    for start, text in chapters:
        lines.append(f"{timestamp(start)} {text}")
    lines += ["", "📰 बातमीतील मुख्य मुद्दे"]
    for it in items:
        lines.append(f"• {it['headline']}: {it['context']}")
    if props.get("credits"):
        lines += ["", "🖼️ चित्रे: प्रातिनिधिक छायाचित्रे; घटनेचे थेट चित्र असेलच असे नाही.", *sorted(set(props["credits"]))]
    lines += ["", youtube_upload.AI_NOTE, "", "🔔 MahaSpark ला फॉलो आणि सबस्क्राईब करा, रोज ताज्या बातम्या मिळवा.", "▶️ @MahaSparkOfficial", "", CHANNEL_HASHTAGS]
    return "\n".join(lines)


def build_tags(items: list[dict]) -> list[str]:
    tags = list(BASE_TAGS)
    for it in items:
        tags.append(it["category"])
        tags.extend(it.get("seo_keywords", []))
    return youtube_upload.clean_tags(tags)


def build_telegram_text(items: list[dict], slot_label: str, video_url: str | None, uploaded: bool) -> str:
    head = f"📺 <b>MahaSpark बुलेटिन तयार: {slot_label} {len(items)} बातम्या</b>"
    if video_url:
        head += f"\n{video_url}"
    elif not uploaded:
        head += "\n(YouTube अपलोड झाला नाही; व्हिडिओ GitHub Actions artifact मध्ये आहे.)"
    body = "\n".join(f"{i + 1}. {it['headline']}" for i, it in enumerate(items))
    return f"{head}\n\n{body}"


# ----- 6. render -------------------------------------------------------------------------------


def render(output: Path = BULLETIN_PATH, crf: int = 22) -> None:
    from pipeline import render_concurrency  # same core-count cap as the reel render

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        "npx", "remotion", "render", "src/index.ts", BULLETIN_COMPOSITION_ID, str(output),
        "--props=public/bulletin.json", "--codec=h264", f"--crf={crf}", f"--concurrency={render_concurrency()}",
    ]
    print("🎬 Rendering the bulletin with Remotion (one job)...")
    result = subprocess.run(cmd, cwd=REMOTION_DIR)
    if result.returncode != 0 or not os.path.exists(output):
        raise RuntimeError(f"Remotion bulletin render failed with exit code {result.returncode}")


def thumbnail_props(props: dict) -> dict:
    """The top story, preferring the first item that has a photo (a face or place sells the click)."""
    items = props["items"]
    pick = next((it for it in items if it.get("photo")), items[0])
    return {"headline": items[0]["headline"], "count": len(items), "photo": pick.get("photo")}


def render_thumbnail(props: dict) -> Path | None:
    """Thumbnail variants for the bulletin (thumbnails.py); returns the one to upload, or None. Failure never stops it."""
    import thumbnails

    try:
        pick = thumbnail_props(props)
        photo = (pick.get("photo") or {}).get("src") if pick.get("photo") else None
        made = thumbnails.render_variants(
            "bulletin", pick["headline"], f"आजच्या {pick['count']} मोठ्या बातम्या", "", photo, props.get("bg_hue", 0), name="bulletin"
        )
        return made[0] if made else None
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ Thumbnail render failed: {exc}")
        return None


# ----- main ------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and publish the MahaSpark news bulletin.")
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
    parser.add_argument("--skip-telegram", action="store_true")
    args = parser.parse_args(argv)

    deadline = time.time() + RUN_BUDGET_SECONDS
    slot_label, slot_id = slot_for()
    queue = None
    try:
        queue = SheetQueue.connect()
        known = queue.bulletin_known_keys()
    except Exception as exc:  # noqa: BLE001 - no Sheet means no cross-run de-duplication, not no bulletin
        print(f"⚠️ Bulletin log unavailable, continuing without de-duplication: {exc}")
        known = set()

    print("🔍 Collecting fresh stories...")
    try:
        items = collect_items(known, gather_candidates(), TARGET_ITEMS, deadline)
        if len(items) < MIN_ITEMS:
            print(f"❌ Only {len(items)} usable stories; at least {MIN_ITEMS} are needed.")
            return 1
        items = add_voices(items)
    except LLMUnavailableError as exc:
        print(f"❌ No AI provider is usable right now: {exc}")
        return 1
    if len(items) < MIN_ITEMS:
        print(f"❌ Only {len(items)} item(s) could be voiced; at least {MIN_ITEMS} are needed.")
        return 1

    credits = add_photos(items)
    props = assemble(items, credits)
    write_props(props)
    print(f"🧾 Bulletin: {len(items)} items, {props['total_seconds']:.0f} s")
    if args.skip_render:
        return 0

    try:
        render()
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1

    video_url, uploaded, fail_reason = None, False, ""
    if not args.skip_upload:
        try:
            video_url = youtube_upload.upload_video(
                BULLETIN_PATH, build_title(items, slot_label), build_description(items, props, slot_label), build_tags(items)
            )
            uploaded = True
            print(f"▶️ Uploaded: {video_url}")
            thumb = render_thumbnail(props)
            if thumb:
                try:
                    youtube_upload.set_thumbnail(video_url, thumb)
                except Exception as exc:  # noqa: BLE001
                    print(f"⚠️ Thumbnail upload failed: {exc}")
        except youtube_upload.YouTubeUnavailable as exc:
            print(f"⏭️ YouTube upload skipped: {exc}")
            fail_reason = str(exc)
        except Exception as exc:  # noqa: BLE001
            print(f"❌ YouTube upload failed: {exc}")
            fail_reason = str(exc)

    if not uploaded and not args.skip_upload:
        manual_kit.deliver("बुलेटिन", BULLETIN_PATH, build_title(items, slot_label), build_description(items, props, slot_label), build_tags(items), fail_reason or "YouTube is not set up", send=not args.skip_telegram)

    if not args.skip_telegram:
        try:
            send_telegram.send_message(build_telegram_text(items, slot_label, video_url, uploaded))
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ Telegram notification failed: {exc}")

    if queue is not None and (uploaded or args.skip_upload):
        try:
            queue.record_bulletin(slot_id, items, video_url or "")
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ Could not record the bulletin in the Sheet: {exc}")

    return 0 if (uploaded or args.skip_upload or not youtube_upload_configured()) else 1


def youtube_upload_configured() -> bool:
    try:
        youtube_upload.credentials()
        return True
    except youtube_upload.YouTubeUnavailable:
        return False


if __name__ == "__main__":
    sys.exit(main())
