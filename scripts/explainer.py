"""MahaSpark explainer: ONE fresh news story explained in about three minutes, 16:9, with graphics that appear on the
exact word the anchor says (points, steps, timeline, comparison, key figure, quote).

    RSS -> a story with a rich source -> explainer script (Gemini) -> one Gemini TTS clip per scene -> Whisper word times
        -> remotion/public/long.json -> Remotion "MahaSparkLong" -> YouTube -> Telegram link

``python scripts/explainer.py [--text "<title>\\n<article>" --url ...] [--skip-render] [--skip-upload] [--skip-telegram]``
Facts only: every figure, date and quote on screen must be in the source text; the spoken text follows the same
phonetic rules as the reels.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from typing import Literal

from pydantic import BaseModel, Field

import editorial_engine as ee
import fetch_news
import longform
import send_telegram
import youtube_upload
from bulletin_editorial import FACT_RULES, PHONETIC_RULES
from config import LONG_PATH, LONG_THUMB_PATH
from editorial_prompts import AUDIO_MOODS
from llm_providers import ContentFailed, ContentRejected, LLMUnavailableError, generate_json
from marathi_numbers import numbers_to_words, words_to_digits

MIN_SOURCE_CHARS = 2400  # below this the story cannot fill about three minutes with facts
MIN_SCENES, MAX_SCENES = 5, 10
MIN_SCENE_WORDS, MAX_SCENE_WORDS = 18, 80
MIN_TOTAL_WORDS, MAX_TOTAL_WORDS = 230, 620
MAX_HEADLINE, MAX_SUBTITLE, MAX_LABEL, MAX_VALUE = 56, 92, 56, 64
ITEM_COUNTS = {  # kind -> (min items, max items)
    "title": (0, 0), "points": (2, 4), "steps": (3, 4), "compare": (2, 2), "timeline": (3, 5),
    "stat": (1, 1), "quote": (1, 1), "summary": (2, 4),
}
Kind = Literal["title", "points", "steps", "compare", "timeline", "stat", "quote", "summary"]
CHANNEL_HASHTAGS = "#MahaSpark #मराठीबातम्या #समजूनघ्या #MarathiNews #महाराष्ट्र"
EXPLAINER_THUMB_TAG = "समजून घ्या"

_MOODS = "\n".join(f"  - {n}: {u}" for n, u in AUDIO_MOODS.items())

EXPLAINER_INSTRUCTION = f"""
You are the explainer editor of MahaSpark, a No. 1 Marathi news channel. You turn ONE verified news story into a
calm, clear explainer of about three minutes (16:9) that a senior anchor reads aloud while graphics appear on screen
at the exact word that names them. Your output is machine-read: return exactly one JSON object that follows the
supplied schema, nothing else.

{FACT_RULES}

══════════ EXPLAINER FORMAT ══════════
Write 6 to 9 scenes. Each scene has a "kind", an on-screen "headline", optional "subtitle", "items" and the spoken
"tts_text" (25 to 70 words, short active sentences). Total spoken text: 260 to 560 words.
- Scene 1 is kind "title": the headline is the question or the story in one line (the viewer's reason to stay), tts_text is a
  3 to 4 second hook plus what this video explains. No items.
- Then a logical story: what happened, who is involved, the numbers, how it works or what changes, what happens next
  (only what the source states). Use a variety of kinds:
  "points"   2-4 key facts. items: {{"label": short fact line}}
  "steps"    3-4 stages in order (process, procedure, sequence). items: {{"label": step}}
  "compare"  EXACTLY 2 items, two sides (before/after, claim/response). items: {{"label": heading, "value": text}}
  "timeline" 3-5 dated events in order. items: {{"label": date or time, "value": the event}}
  "stat"     ONE key figure. items: [{{"label": what it measures, "value": the figure, e.g. ₹१,२०० कोटी}}]
  "quote"    ONE statement quoted word for word from the source. items: [{{"label": speaker and role, "value": the quote}}]
  "summary"  the LAST scene: 2-4 takeaways. items: {{"label": takeaway}}
- Every item has a "cue": ONE word copied EXACTLY from that scene's tts_text (not a number) that the anchor speaks at the
  moment the item should appear on screen. Cues must follow the order in which the words are spoken.
- On-screen text (headline, subtitle, label, value) uses DEVANAGARI digits and symbols (१२, ८५%, ₹१,२०० कोटी, २७ नोव्हेंबर),
  never spelled-out numbers, no emoji, no English words, no quotation marks except inside a quote value.
  Headline at most {MAX_HEADLINE} characters, subtitle at most {MAX_SUBTITLE}, label at most {MAX_LABEL}, value at most {MAX_VALUE}.
  Every number, date and quote must be in the source.
- "title" (the video title, at most 95 characters, keyword first, a complete line), "social_caption" (2-3 sentences),
  "seo_keywords" (8-12, Marathi and English), "audio_mood" one of
{_MOODS}
- Neutral, factual, no opinion and no speculation. Allegations are attributed to the named person or institution.
  No sign-off line, no "like and subscribe".

{PHONETIC_RULES}
""".strip()


class ExItem(BaseModel):
    label: str = ""
    value: str = ""
    cue: str = ""


class ExScene(BaseModel):
    kind: Kind = "points"
    headline: str = ""
    subtitle: str = ""
    items: list[ExItem] = Field(default_factory=list)
    tts_text: str = ""


class Explainer(BaseModel):
    approved: bool = True
    rejection_reason: str = ""
    title: str = ""
    social_caption: str = ""
    seo_keywords: list[str] = Field(default_factory=list)
    audio_mood: str = "neutral"
    scenes: list[ExScene] = Field(default_factory=list)


def build_prompt(title: str, summary: str, article_text: str, source_url: str) -> str:
    return (
        "SOURCE MATERIAL (the only facts you may use)\n"
        f"Source URL: {source_url or 'not available'}\n"
        f"Source title: {title.strip()}\n"
        f"Source summary: {summary.strip() or 'not available'}\n"
        f'Full article text:\n"""\n{(article_text or "").strip()[:9000]}\n"""\n\n'
        "Write the explainer now. Set approved to false only for a rumour, an unattributed leak or an opinion piece."
    )


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def validate_explainer(data: dict, source_text: str) -> dict:
    """Deterministic checks. Raises ContentRejected (not approved) or ValueError (the model gets one repair attempt)."""
    if not data.get("approved", True):
        raise ContentRejected(str(data.get("rejection_reason") or "Not approved by the editorial model."))
    scenes_in = data.get("scenes") or []
    if not (MIN_SCENES <= len(scenes_in) <= MAX_SCENES):
        raise ValueError(f"Expected {MIN_SCENES} to {MAX_SCENES} scenes, got {len(scenes_in)}.")

    allowed = ee.source_numbers(source_text)
    scenes, total_words = [], 0
    for n, raw in enumerate(scenes_in, 1):
        kind = str(raw.get("kind", "")).strip()
        if kind not in ITEM_COUNTS:
            raise ValueError(f"Scene {n}: unknown kind '{kind}'.")
        if (n == 1) != (kind == "title"):
            raise ValueError("Only scene 1 may (and must) be kind 'title'.")
        if (n == len(scenes_in)) != (kind == "summary"):
            raise ValueError("Only the last scene may (and must) be kind 'summary'.")
        headline = words_to_digits(_clean(raw.get("headline")))
        subtitle = words_to_digits(_clean(raw.get("subtitle")))
        tts_text = ee.clean_tts_text(numbers_to_words(raw.get("tts_text", "")))
        if not 6 <= len(headline) <= MAX_HEADLINE:
            raise ValueError(f"Scene {n} headline has {len(headline)} characters; it must be 6 to {MAX_HEADLINE}.")
        if len(subtitle) > MAX_SUBTITLE:
            raise ValueError(f"Scene {n} subtitle has {len(subtitle)} characters; the limit is {MAX_SUBTITLE}.")
        words = len(tts_text.split())
        if not MIN_SCENE_WORDS <= words <= MAX_SCENE_WORDS:
            raise ValueError(f"Scene {n} tts_text has {words} words; it must be {MIN_SCENE_WORDS} to {MAX_SCENE_WORDS}.")
        problems = ee.tts_problems(tts_text)
        if problems:
            raise ValueError(f"Scene {n}: {problems[0]}")
        banned = ee.find_forbidden(f"{headline} {subtitle} {tts_text}")
        if banned:
            raise ValueError(f"Scene {n}: the phrase '{banned}' is banned. Name the institution or person instead.")

        items = []
        lo, hi = ITEM_COUNTS[kind]
        raw_items = raw.get("items") or []
        if not lo <= len(raw_items) <= hi:
            raise ValueError(f"Scene {n} (kind {kind}) needs {lo} to {hi} items, got {len(raw_items)}.")
        spoken = {longform.norm(w) for w in tts_text.split()}
        for it in raw_items:
            label, value = words_to_digits(_clean(it.get("label"))), words_to_digits(_clean(it.get("value")))
            cue = _clean(it.get("cue")).split(" ")[0] if _clean(it.get("cue")) else ""
            if not label or len(label) > MAX_LABEL:
                raise ValueError(f"Scene {n}: an item label is empty or longer than {MAX_LABEL} characters.")
            if len(value) > MAX_VALUE or (kind in ("stat", "quote", "compare", "timeline") and not value):
                raise ValueError(f"Scene {n}: an item value is missing or longer than {MAX_VALUE} characters.")
            if kind == "stat" and len(value) > 24:
                raise ValueError(f"Scene {n}: the key figure '{value}' is too long for the big number (24 characters).")
            if kind == "quote" and (not 10 <= len(value) <= MAX_VALUE + 30 or longform.squash(value) not in longform.squash(source_text)):
                raise ValueError(f"Scene {n}: the quote is not word for word in the source.")
            for number in ee.source_numbers(f"{label} {value}"):
                if allowed and number not in allowed:
                    raise ValueError(f"Scene {n} shows the number {number}, which is not in the source. Use only numbers from the source.")
            if not allowed and ee.source_numbers(f"{label} {value}"):
                raise ValueError(f"Scene {n} shows a number but the source has none.")
            items.append({"label": label, "value": value, "cue": cue if longform.norm(cue) in spoken else ""})
        for number in ee.source_numbers(f"{headline} {subtitle}"):
            if allowed and number not in allowed:
                raise ValueError(f"Scene {n} headline shows the number {number}, which is not in the source.")
        total_words += words
        scenes.append({"kind": kind, "headline": headline, "subtitle": subtitle, "items": items, "tts_text": tts_text})

    if not MIN_TOTAL_WORDS <= total_words <= MAX_TOTAL_WORDS:
        raise ValueError(f"The explainer has {total_words} spoken words; it must be {MIN_TOTAL_WORDS} to {MAX_TOTAL_WORDS}.")

    title = ee.polish_title(_clean(data.get("title")))
    if not 20 <= len(title) <= 95:
        raise ValueError(f"title has {len(title)} characters; it must be 20 to 95.")
    mood = data.get("audio_mood") if data.get("audio_mood") in AUDIO_MOODS else "neutral"
    return {
        "title": title,
        "social_caption": _clean(data.get("social_caption"))[:400],
        "seo_keywords": ee.clean_keywords(data.get("seo_keywords", [])),
        "audio_mood": mood,
        "scenes": scenes,
    }


def write_explainer(title: str, summary: str, article_text: str, source_url: str) -> dict:
    title, summary, article_text = (title or "").strip(), (summary or "").strip(), (article_text or "").strip()
    source_text = f"{title}\n{summary}\n{article_text}"
    if len(source_text) < MIN_SOURCE_CHARS:
        raise ContentRejected(f"Source has {len(source_text)} characters; an explainer needs {MIN_SOURCE_CHARS}.")
    data = generate_json(
        system_instruction=EXPLAINER_INSTRUCTION,
        prompt=build_prompt(title, summary, article_text, source_url),
        response_model=Explainer,
        validate=lambda d: validate_explainer(d, source_text),
    )
    data["source"] = {"title": title, "url": source_url}
    return data


# ----- metadata ----------------------------------------------------------------------------------


def build_description(ex: dict, props: dict) -> str:
    lines = [ex["social_caption"] or ex["title"], ""]
    marks = longform.chapters(props, [s["headline"] for s in ex["scenes"]])
    if marks:
        lines += ["⏱️ अध्याय (Chapters)", *[f"{longform.timestamp(t)} {label}" for t, label in marks], ""]
    summary = next((s for s in ex["scenes"] if s["kind"] == "summary"), None)
    if summary:
        lines += ["📌 मुख्य मुद्दे", *[f"• {it['label']}" for it in summary["items"]], ""]
    lines += [youtube_upload.AI_NOTE, "", "🔔 MahaSpark ला फॉलो आणि सबस्क्राईब करा, रोज ताज्या बातम्या आणि समजून घ्यायला सोपी माहिती मिळवा.",
              "▶️ @MahaSparkOfficial", "", CHANNEL_HASHTAGS]
    return "\n".join(lines)


def build_tags(ex: dict) -> list[str]:
    return youtube_upload.clean_tags(["MahaSpark", "मराठी बातम्या", "Marathi News", "समजून घ्या", "Explained", *ex["seo_keywords"]])


def key_figure(ex: dict) -> str:
    stat = next((s for s in ex["scenes"] if s["kind"] == "stat"), None)
    return stat["items"][0]["value"] if stat else ""


# ----- run ---------------------------------------------------------------------------------------


def pick_story(known: set[str], deadline: float):
    """First fresh story whose sources (publisher article plus other reports) are rich enough to explain."""
    import bulletin

    for cand in bulletin.gather_candidates():
        if time.time() > deadline:
            break
        if bulletin.is_duplicate(cand.title, [], known):
            continue
        url = fetch_news.resolve_article_url(cand.link)
        if url and url.lower() in known:
            continue
        article = fetch_news.enrich_thin_source(cand.title, cand.summary, fetch_news.fetch_article_text(url), url)
        if len(cand.title) + len(cand.summary) + len(article) < MIN_SOURCE_CHARS:
            print(f"⏭️ Too little text to explain: {cand.title[:60]}")
            continue
        try:
            return write_explainer(cand.title, cand.summary, article, url)
        except (ContentRejected, ValueError, ContentFailed) as exc:
            print(f"⏭️ Not used ({str(exc)[:90]}): {cand.title[:60]}")
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and publish one MahaSpark explainer video.")
    parser.add_argument("--text", help='"<title>\\n<article>" for a local one-off (no Sheet, no RSS)')
    parser.add_argument("--url", default="")
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
    parser.add_argument("--skip-telegram", action="store_true")
    args = parser.parse_args(argv)

    from sheet_queue import SheetQueue

    queue, known = None, set()
    if not args.text:
        try:
            queue = SheetQueue.connect()
            known = queue.longform_known_keys()
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ Long-video log unavailable, continuing without de-duplication: {exc}")
    try:
        if args.text:
            head, _, body = args.text.partition("\n")
            ex = write_explainer(head, "", body, args.url)
        else:
            ex = pick_story(known, time.time() + 1200)
        if not ex:
            print("❌ No story with enough verified text to explain right now.")
            return 1
        print(f"🧠 Explainer: {ex['title']} ({len(ex['scenes'])} scenes)")
        scenes = longform.voice_all(ex["scenes"])
    except (LLMUnavailableError, ContentFailed, ContentRejected) as exc:
        print(f"❌ {exc}")
        return 1

    props = longform.assemble("explainer", ex["title"], scenes, ee.pick_hue(ex["title"]), ex["audio_mood"])
    longform.write_props(props)
    print(f"🧾 {props['total_seconds']:.0f} s")
    if args.skip_render:
        return 0
    try:
        longform.render()
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1

    video_url, uploaded = None, False
    if not args.skip_upload:
        try:
            video_url = youtube_upload.upload_video(LONG_PATH, ex["title"], build_description(ex, props), build_tags(ex))
            uploaded = True
            print(f"▶️ Uploaded: {video_url}")
            if longform.render_thumbnail(scenes[0]["headline"], EXPLAINER_THUMB_TAG, key_figure(ex)):
                try:
                    youtube_upload.set_thumbnail(video_url, LONG_THUMB_PATH)
                except Exception as exc:  # noqa: BLE001
                    print(f"⚠️ Thumbnail upload failed: {exc}")
        except youtube_upload.YouTubeUnavailable as exc:
            print(f"⏭️ YouTube upload skipped: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"❌ YouTube upload failed: {exc}")

    if not args.skip_telegram:
        text = f"🧠 <b>MahaSpark समजून घ्या: {ex['title']}</b>\n" + (video_url or "(YouTube अपलोड झाला नाही; व्हिडिओ GitHub Actions artifact मध्ये आहे.)")
        try:
            send_telegram.send_message(text)
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ Telegram notification failed: {exc}")
    if queue is not None and (uploaded or args.skip_upload):
        try:
            queue.record_longform("explainer", ex["title"], (ex.get("source") or {}).get("url", ""), video_url or "")
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ Could not record the video in the Sheet: {exc}")
    return 0 if (uploaded or args.skip_upload or not _youtube_configured()) else 1


def _youtube_configured() -> bool:
    try:
        youtube_upload.credentials()
        return True
    except youtube_upload.YouTubeUnavailable:
        return False


if __name__ == "__main__":
    sys.exit(main())
