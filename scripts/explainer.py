"""MahaSpark explainer: ONE evergreen topic (Maharashtra history, geography, culture, institutions, civics, science,
India) explained in about three minutes, 16:9, with graphics that appear on the exact word the anchor says. It is NOT
about today's news.

    topic bank -> Wikipedia (Marathi + English reference text) -> explainer script (Gemini) -> one Gemini TTS clip per
        scene -> Whisper word times -> remotion/public/long.json -> Remotion "MahaSparkLong" -> YouTube -> Telegram link

``python scripts/explainer.py [--text "<title>\\n<reference text>" --url ...] [--skip-render] [--skip-upload] [--skip-telegram]``
Facts only: every figure, date and quote on screen must be in the reference text; the spoken text follows the same
phonetic rules as the reels.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

import drafts
import editorial_engine as ee
import factcheck
import geo
import longform
import manual_kit
import send_telegram
import shorts
import topic_bank
import topic_images
import wiki_sources
import youtube_upload
from bulletin_editorial import FACT_RULES, PHONETIC_RULES
from config import LONG_PATH
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
    "stat": (1, 1), "quote": (1, 1), "summary": (2, 4), "chart": (2, 5),
}
Kind = Literal["title", "points", "steps", "compare", "timeline", "stat", "quote", "summary", "chart"]
CHANNEL_HASHTAGS = "#MahaSpark #मराठीबातम्या #समजूनघ्या #MarathiNews #महाराष्ट्र"
EXPLAINER_THUMB_TAG = "समजून घ्या"

_MOODS = "\n".join(f"  - {n}: {u}" for n, u in AUDIO_MOODS.items())

EXPLAINER_INSTRUCTION = f"""
You are the explainer editor of MahaSpark, a No. 1 Marathi news channel. You turn ONE evergreen topic (not today's news) into a
calm, clear explainer of about three minutes (16:9) that a senior anchor reads aloud while graphics appear on screen
at the exact word that names them. Your output is machine-read: return exactly one JSON object that follows the
supplied schema, nothing else.

{FACT_RULES}

══════════ EXPLAINER FORMAT ══════════
Write 6 to 9 scenes. Each scene has a "kind", an on-screen "headline", optional "subtitle", "items" and the spoken
"tts_text" (25 to 70 words, short active sentences). Total spoken text: 260 to 560 words.
- Scene 1 is kind "title": the headline is the question or the story in one line (the viewer's reason to stay), tts_text is a
  3 to 4 second hook plus what this video explains. No items.
- Then a logical lesson: what it is, where and when it began, who is involved, the key numbers, how it works, why it
  matters for Maharashtra or India today (only what the reference text states). Use a variety of kinds:
  "points"   2-4 key facts. items: {{"label": short fact line}}
  "steps"    3-4 stages in order (process, procedure, sequence). items: {{"label": step}}
  "compare"  EXACTLY 2 items, two sides (before/after, claim/response). items: {{"label": heading, "value": text}}
  "timeline" 3-5 dated events in order. items: {{"label": date or time, "value": the event}}
  "chart"    2-5 comparable numbers as animated bars (heights, lengths, populations, years of change). All values share ONE unit.
             items: {{"label": what it is, "value": the figure with its unit, e.g. ८,८४८ मीटर}}
  "stat"     ONE key figure. items: [{{"label": what it measures, "value": the figure, e.g. ₹१,२०० कोटी}}]
  "quote"    ONE statement quoted word for word from the source (only if the reference text contains a quotation). items: [{{"label": speaker and role, "value": the quote}}]
  "summary"  the LAST scene: 2-4 takeaways. items: {{"label": takeaway}}
- Every item has a "cue": ONE word copied EXACTLY from that scene's tts_text (not a number) that the anchor speaks at the
  moment the item should appear on screen. Cues must follow the order in which the words are spoken.
- On-screen text (headline, subtitle, label, value) uses DEVANAGARI digits and symbols (१२, ८५%, ₹१,२०० कोटी, २७ नोव्हेंबर),
  never spelled-out numbers, no emoji, no English words, no quotation marks except inside a quote value.
  Headline at most {MAX_HEADLINE} characters, subtitle at most {MAX_SUBTITLE}, label at most {MAX_LABEL}, value at most {MAX_VALUE}.
  Every number, date and quote must be in the source.
- "thumb_text": 3 to 5 words, at most 30 characters, for the YouTube thumbnail: a curious question or the hook of the story
  (for example "पाणी योजना खरंच मंजूर?"); any number in it must be in the source.
- "title" (the video title, at most 95 characters, keyword first, a complete line), "social_caption" (2-3 sentences),
  "seo_keywords" (8-12, Marathi and English), "audio_mood" one of
{_MOODS}
- A timeless explainer: no "today", "this week", "recently" or news framing. Use the Marathi names and terms of the
  Marathi reference text when it is given. Neutral, factual, no opinion and no speculation. Allegations are attributed to the named person or institution.
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
    thumb_text: str = ""
    social_caption: str = ""
    seo_keywords: list[str] = Field(default_factory=list)
    audio_mood: str = "neutral"
    scenes: list[ExScene] = Field(default_factory=list)


def build_prompt(title: str, summary: str, article_text: str, source_url: str) -> str:
    return (
        "REFERENCE MATERIAL (the only facts you may use)\n"
        f"Reference URL: {source_url or 'not available'}\n"
        f"Topic: {title.strip()}\n"
        f"Category: {summary.strip() or 'not available'}\n"
        f'Reference text:\n"""\n{(article_text or "").strip()[:12000]}\n"""\n\n'
        "Write the evergreen explainer now. Set approved to false only if the reference text is not about the topic."
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
            if len(value) > MAX_VALUE or (kind in ("stat", "quote", "compare", "timeline", "chart") and not value):
                raise ValueError(f"Scene {n}: an item value is missing or longer than {MAX_VALUE} characters.")
            if kind == "chart" and not re.search(r"[0-9०-९]", value):
                raise ValueError(f"Scene {n}: every chart item needs a figure in its value (a number from the source).")
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
    thumb = words_to_digits(_clean(data.get("thumb_text")))
    if len(thumb) > 34 or any(n not in allowed for n in ee.source_numbers(thumb)):
        thumb = ""  # not worth a repair attempt: the thumbnail falls back to the hook headline
    return {
        "title": title,
        "thumb_text": thumb,
        "social_caption": _clean(data.get("social_caption"))[:400],
        "seo_keywords": ee.clean_keywords(data.get("seo_keywords", [])),
        "audio_mood": mood,
        "scenes": scenes,
    }


def write_explainer(title: str, summary: str, article_text: str, source_url: str) -> dict:
    """Write the script, then let an independent checker flag statements the reference text does not state.
    Flagged statements trigger ONE rewrite; anything still flagged is kept in ``fact_notes`` for the editor."""
    title, summary, article_text = (title or "").strip(), (summary or "").strip(), (article_text or "").strip()
    source_text = f"{title}\n{summary}\n{article_text}"
    if len(source_text) < MIN_SOURCE_CHARS:
        raise ContentRejected(f"Source has {len(source_text)} characters; an explainer needs {MIN_SOURCE_CHARS}.")
    prompt = build_prompt(title, summary, article_text, source_url)
    notes: list[str] = []
    for attempt in (1, 2):
        data = generate_json(
            system_instruction=EXPLAINER_INSTRUCTION,
            prompt=prompt,
            response_model=Explainer,
            validate=lambda d: validate_explainer(d, source_text),
        )
        try:
            notes = factcheck.unsupported_statements(data["scenes"], source_text)
        except (LLMUnavailableError, ContentFailed) as exc:
            print(f"⚠️ Fact-check pass unavailable ({str(exc)[:80]}); the script is unchecked.")
            notes = ["(the independent fact-check could not run; read every fact yourself)"]
            break
        if not notes:
            break
        print(f"🔎 Fact-check flagged {len(notes)} statement(s) (attempt {attempt}).")
        prompt = build_prompt(title, summary, article_text, source_url) + (
            "\n\nA fact-checker found these statements that the reference text does NOT support. Do not use them; "
            "write the scenes again using only what the reference text states:\n- " + "\n- ".join(notes[:8])
        )
    data["source"] = {"title": title, "url": source_url}
    data["fact_notes"] = notes
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
    urls = (ex.get("source") or {}).get("urls") or []
    if urls:
        lines += [wiki_sources.credit_line(urls), ""]
    if props.get("credits"):
        lines += ["🖼️ चित्रे (Wikimedia Commons, मुक्त परवाना):", *props["credits"], ""]
    lines += [youtube_upload.AI_NOTE, "", "🔔 MahaSpark ला फॉलो आणि सबस्क्राईब करा, रोज नवीन माहिती सोप्या भाषेत मिळवा.",
              "▶️ @MahaSparkOfficial", "", CHANNEL_HASHTAGS]
    return "\n".join(lines)


def build_tags(ex: dict) -> list[str]:
    return youtube_upload.clean_tags(["MahaSpark", "मराठी बातम्या", "Marathi News", "समजून घ्या", "Explained", *ex["seo_keywords"]])


def key_figure(ex: dict) -> str:
    stat = next((s for s in ex["scenes"] if s["kind"] == "stat"), None)
    return stat["items"][0]["value"] if stat else ""


# ----- run ---------------------------------------------------------------------------------------


def pick_story(known: set[str], deadline: float):
    """First unused topic of the bank (Maharashtra and general knowledge, categories rotating) whose Wikipedia text is
    rich enough to explain."""
    for _group, category, en_title in topic_bank.pick(None, known):
        if time.time() > deadline:
            break
        ref = wiki_sources.fetch_topic(en_title)
        if not ref or len(ref["text"]) < MIN_SOURCE_CHARS:
            print(f"⏭️ Too little reference text: {en_title}")
            continue
        try:
            ex = write_explainer(ref["title"], category, ref["text"], ref["url"])
        except (ContentRejected, ValueError, ContentFailed) as exc:
            print(f"⏭️ Not used ({str(exc)[:90]}): {en_title}")
            continue
        if ex.get("fact_notes"):
            print(f"⏭️ Not used (fact-check still flags: {ex['fact_notes'][0][:90]}): {en_title}")
            continue
        ex["source"]["urls"] = ref["urls"]
        ex["source"]["url"] = wiki_sources.page_url("en", en_title)  # the bank key, so a redirect never repeats a topic
        return ex
    return None


def finish(ex: dict, queue, skip_render: bool, skip_upload: bool, skip_telegram: bool) -> int:
    """Voice, render, upload and announce an explainer dict (written by the model OR approved by you from a .txt)."""
    try:
        scenes = longform.voice_all(ex["scenes"])
    except (LLMUnavailableError, ContentFailed, ContentRejected) as exc:
        print(f"❌ {exc}")
        if not skip_telegram:
            try:
                send_telegram.send_message("⚠️ व्हिडिओ अर्धवट राहिला: Gemini आवाजाची मर्यादा संपली. काही वेळाने 'produce' पुन्हा चालवा; आधी तयार झालेले आवाज पुन्हा वापरले जातील.")
            except Exception:  # noqa: BLE001
                pass
        return 1
    props = longform.assemble("explainer", ex["title"], scenes, ee.pick_hue(ex["title"]), ex["audio_mood"])
    if os.getenv("EXPLAINER_PHOTOS", "1") != "0":  # real, freely licensed photos of the topic behind the graphics
        urls = (ex.get("source") or {}).get("urls") or [u for u in str((ex.get("source") or {}).get("url", "")).split("\n") if u]
        longform.attach_photos(props, topic_images.fetch_images(urls))
    geo.attach_map(props, str((ex.get("source") or {}).get("url", "")))  # animated Maharashtra map for places
    longform.write_props(props)
    print(f"🧾 {props['total_seconds']:.0f} s")
    if skip_render:
        return 0
    try:
        longform.render()
    except RuntimeError as exc:
        print(f"❌ {exc}")
        return 1

    video_url, uploaded, fail_reason = None, False, ""
    if not skip_upload:
        try:
            video_url = youtube_upload.upload_video(LONG_PATH, ex["title"], build_description(ex, props), build_tags(ex))
            uploaded = True
            print(f"▶️ Uploaded: {video_url}")
            thumb = longform.render_thumbnail("explainer", ex.get("thumb_text") or scenes[0]["headline"], EXPLAINER_THUMB_TAG, key_figure(ex), props["bg_hue"])
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

    if not uploaded and not skip_upload:
        manual_kit.deliver("समजून घ्या", LONG_PATH, ex["title"], build_description(ex, props), build_tags(ex), fail_reason or "YouTube is not set up", send=not skip_telegram)

    if not skip_telegram:
        text = f"🧠 <b>MahaSpark समजून घ्या: {ex['title']}</b>\n" + (video_url or "(YouTube अपलोड झाला नाही; व्हिडिओ out/ फोल्डरमध्ये आहे.)")
        try:
            send_telegram.send_message(text)
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ Telegram notification failed: {exc}")
    shorts.run(props, ex["title"], "समजून घ्या", send=not skip_telegram)  # 9:16 clip for Telegram (LONG_SHORTS=0 turns it off)
    if queue is not None and (uploaded or skip_upload):
        try:
            queue.record_longform("explainer", ex["title"], (ex.get("source") or {}).get("url", ""), video_url or "")
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ Could not record the video in the Sheet: {exc}")
    return 0 if (uploaded or skip_upload or not _youtube_configured()) else 1


def _connect_log():
    from sheet_queue import SheetQueue

    try:
        queue = SheetQueue.connect()
        return queue, queue.longform_known_keys()
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ Long-video log unavailable, continuing without de-duplication: {exc}")
        return None, set()


def draft_main(argv: list[str]) -> int:
    """Write the script (for YOUR topic, or the next unused bank topic) to a .txt for you to edit and approve."""
    parser = argparse.ArgumentParser(prog="explainer.py draft", description="Write an explainer script as a .txt for approval.")
    parser.add_argument("--topic", default="", help="the topic in your words, e.g. 'पुणे मेट्रो विस्तार' (empty = next topic from the bank)")
    parser.add_argument("--url", action="append", default=[], help="a source article to use (repeat for more)")
    args = parser.parse_args(argv)
    topic = args.topic.strip()
    key_url = ""
    try:
        if topic:
            text, urls = drafts.topic_sources(topic, [u for u in args.url if u])
            if len(text) < MIN_SOURCE_CHARS // 2:
                print(f"❌ Found only {len(text)} characters of reference text about this topic. Add article links with --url.")
                return 1
            ex = write_explainer(topic, "", text, "\n".join(urls))
        else:
            known = _connect_log()[1]
            ex = None
            for _group, category, en_title in topic_bank.pick(None, known):
                ref = wiki_sources.fetch_topic(en_title)
                if not ref or len(ref["text"]) < MIN_SOURCE_CHARS:
                    continue
                try:
                    ex = write_explainer(ref["title"], category, ref["text"], ref["url"])
                except (ContentRejected, ValueError, ContentFailed) as exc:
                    print(f"⏭️ Not used ({str(exc)[:90]}): {en_title}")
                    continue
                key_url, urls = wiki_sources.page_url("en", en_title), ref["urls"]
                break
            if not ex:
                print("❌ No topic could be written right now. Run it again or give a --topic.")
                return 1
    except (LLMUnavailableError, ContentFailed, ContentRejected, ValueError) as exc:
        print(f"❌ {exc}")
        return 1
    sources = list(dict.fromkeys(([key_url] if key_url else []) + urls))
    path = drafts.new_draft_path("explainer")
    path.write_text(drafts.explainer_to_text(ex, sources), encoding="utf-8")
    print(f"📝 Script ready: {path}")
    if ex.get("fact_notes"):
        print("🔎 The fact-checker still flags these (they are marked in the file):\n  - " + "\n  - ".join(ex["fact_notes"]))
    drafts.announce("explainer", path, ex["title"])
    return 0


def produce_main(argv: list[str]) -> int:
    """Produce the video from an approved (or self-written) script .txt."""
    parser = argparse.ArgumentParser(prog="explainer.py produce", description="Make the video from an approved script file.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
    parser.add_argument("--skip-telegram", action="store_true")
    args = parser.parse_args(argv)
    try:
        ex = drafts.parse_explainer(args.file.read_text(encoding="utf-8"))
    except drafts.DraftError as exc:
        print("❌ Fix these lines in the script and run again:\n" + "\n".join(f"  • {p}" for p in exc.problems))
        return 1
    print(f"✅ Script accepted: {ex['title']} ({len(ex['scenes'])} scenes)")
    queue = _connect_log()[0]
    return finish(ex, queue, args.skip_render, args.skip_upload, args.skip_telegram)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "draft":
        return draft_main(argv[1:])
    if argv and argv[0] == "produce":
        return produce_main(argv[1:])

    parser = argparse.ArgumentParser(description="Build and publish one MahaSpark explainer video (automatic; use 'draft' / 'produce' for your own topic and approval).")
    parser.add_argument("--text", help='"<title>\\n<article>" for a local one-off (no Sheet, no RSS)')
    parser.add_argument("--url", default="")
    parser.add_argument("--auto", action="store_true", help="publish WITHOUT your approval (not recommended)")
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
    parser.add_argument("--skip-telegram", action="store_true")
    args = parser.parse_args(argv)
    if not args.auto and not args.text:
        print("ℹ️ No video is made without your approval: writing the script for you to check (use --auto to skip this).")
        return draft_main([])

    queue, known = (None, set()) if args.text else _connect_log()
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
    except (LLMUnavailableError, ContentFailed, ContentRejected) as exc:
        print(f"❌ {exc}")
        return 1
    return finish(ex, queue, args.skip_render, args.skip_upload, args.skip_telegram)


def _youtube_configured() -> bool:
    try:
        youtube_upload.credentials()
        return True
    except youtube_upload.YouTubeUnavailable:
        return False


if __name__ == "__main__":
    sys.exit(main())
