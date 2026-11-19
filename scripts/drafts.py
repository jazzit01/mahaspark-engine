"""Script approval for the explainer and the quiz.

    draft    python scripts/explainer.py draft --topic "..." [--url ...]   ->  drafts/explainer-<time>.txt
             python scripts/quiz.py draft [--topic "..."]                  ->  drafts/quiz-<time>.txt
    approve  open the .txt, change anything you want, save it
    produce  python scripts/explainer.py produce drafts/<file>.txt         ->  voice, render, YouTube, Telegram

You can also write a .txt from scratch in the same format ("directly give my script"). A script you approved is NOT
fact-checked against sources again (you are the editor); only what would break the voice or the layout is refused, with
the line to fix. Numbers can be typed as digits: the voice spells them (``numbers_to_words``) and the screen shows
Devanagari digits.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import editorial_engine as ee
import fetch_news
import longform
from config import ROOT
from marathi_numbers import numbers_to_words, words_to_digits

DRAFT_DIR = ROOT / "drafts"
MOODS = ("neutral", "serious", "crime", "breaking", "upbeat")
EXPLAINER_KINDS = {  # kind -> (min items, max items)
    "title": (0, 0), "points": (0, 5), "steps": (0, 5), "compare": (0, 3), "timeline": (0, 6),
    "stat": (1, 1), "quote": (1, 1), "summary": (0, 5),
}


class DraftError(ValueError):
    """The approved .txt cannot be produced; ``problems`` lists every line to fix."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


# ----- sources for a topic -----------------------------------------------------------------------


def topic_reports(topic: str, urls: list[str] | None = None, limit: int = 4) -> list[tuple[str, str, str]]:
    """Reports about ``topic`` as (host, url, article text): the person's own URLs first, then a Google News search.
    Unreadable pages are skipped."""
    from urllib.parse import quote, urlparse

    import feedparser

    found: list[tuple[str, str, str]] = []
    hosts: set[str] = set()
    for url in urls or []:
        text = fetch_news.fetch_article_text(url)
        if text:
            found.append((urlparse(url).netloc, url, text))
            hosts.add(urlparse(url).netloc.lower())
    if len(found) < limit:
        feed = f"https://news.google.com/rss/search?q={quote(topic)}&hl=mr&gl=IN&ceid=IN:mr"
        try:
            entries = feedparser.parse(feed).entries[:14]
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ News search failed: {exc}")
            entries = []
        for entry in entries:
            if len(found) >= limit:
                break
            url = fetch_news.resolve_article_url((entry.get("link") or "").strip())
            host = urlparse(url).netloc.lower()
            if not url or host in hosts or "news.google.com" in host:
                continue
            text = fetch_news.fetch_article_text(url)
            if len(text) >= 500:
                hosts.add(host)
                found.append((host, url, text))
    return found


def topic_sources(topic: str, urls: list[str] | None = None, limit: int = 4) -> tuple[str, list[str]]:
    """The reports of ``topic_reports`` as one labelled text for the writer, and the urls used."""
    found = topic_reports(topic, urls, limit)
    combined = "\n\n".join(f"[Report {i} from {host}]\n{text}" for i, (host, _url, text) in enumerate(found, 1))
    return combined[: fetch_news.MAX_COMBINED_CHARS], [url for _h, url, _t in found]


# ----- files -------------------------------------------------------------------------------------


def new_draft_path(kind: str, directory: Path = DRAFT_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{kind}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _meta(text: str, key: str) -> str:
    match = re.search(rf"^{key}\s*:\s*(.*)$", text, flags=re.M)
    return _clean(match.group(1)) if match else ""


def _header(text: str) -> dict:
    mood = _meta(text, "MOOD").lower()
    return {
        "title": _meta(text, "TITLE"),
        "thumb_text": words_to_digits(_meta(text, "THUMB")),
        "social_caption": _meta(text, "CAPTION")[:400],
        "seo_keywords": [k.strip() for k in re.split(r"[,،]", _meta(text, "KEYWORDS")) if k.strip()],
        "audio_mood": mood if mood in MOODS else "neutral",
        "sources": [u.strip() for u in re.split(r"\s*\|\s*|\s+", _meta(text, "SOURCES")) if u.strip().startswith("http")],
    }


def _speech(text: str, label: str, problems: list[str]) -> str:
    spoken = ee.clean_tts_text(numbers_to_words(text))
    bad = ee.tts_problems(spoken)
    if bad:
        problems.append(f"{label}: the voice can only read Devanagari words (no English letters or symbols). {bad[0]}")
    return spoken


# ----- explainer ---------------------------------------------------------------------------------

EXPLAINER_HELP = """# MahaSpark explainer script. Edit anything, save, then run:
#   python scripts/explainer.py produce <this file>
# Lines starting with # are ignored. Each scene:
#   THUMB (top of file): 3-5 punchy words for the YouTube thumbnail, for example a question
#   HEADLINE: big text on screen        SUBTITLE: small line under it (optional)
#   SPEECH: what the anchor says (digits are fine; the voice spells them in Marathi)
#   ITEMS: one per line:  - text on screen | value (optional) | word to appear on (optional)
# Scene kinds: title, points, steps, compare, timeline, stat, quote, summary.
#   stat and quote need exactly one item with a value. timeline/compare items use the value for the event/detail.
# Delete a whole scene (from === to its last line) to drop it, or copy one to add one."""


def explainer_to_text(ex: dict, sources: list[str]) -> str:
    out = [EXPLAINER_HELP, "", f"TITLE: {ex['title']}", f"THUMB: {ex.get('thumb_text', '')}", f"CAPTION: {ex.get('social_caption', '')}",
           f"KEYWORDS: {', '.join(ex.get('seo_keywords', []))}", f"MOOD: {ex.get('audio_mood', 'neutral')}",
           f"SOURCES: {' | '.join(sources)}", ""]
    for n, scene in enumerate(ex["scenes"], 1):
        out += [f"=== SCENE {n} | {scene['kind']} ===", f"HEADLINE: {scene['headline']}"]
        if scene.get("subtitle"):
            out.append(f"SUBTITLE: {scene['subtitle']}")
        out.append(f"SPEECH: {scene['tts_text']}")
        if scene["items"]:
            out.append("ITEMS:")
            for it in scene["items"]:
                out.append("- " + " | ".join([it["label"], it.get("value", ""), it.get("cue", "")]).rstrip(" |"))
        out.append("")
    return "\n".join(out)


def _auto_cue(label: str, speech: str) -> str:
    spoken = [w.strip(".,") for w in speech.split()]
    spoken_norm = {longform.norm(w) for w in spoken}
    for token in label.split():
        if len(longform.norm(token)) >= 3 and longform.norm(token) in spoken_norm:
            return next(w for w in spoken if longform.norm(w) == longform.norm(token))
    return ""


def parse_explainer(text: str) -> dict:
    problems: list[str] = []
    head = _header(text)
    title = words_to_digits(head["title"])
    if not 8 <= len(title) <= 100:
        problems.append("TITLE: needs 8 to 100 characters.")
    blocks = re.split(r"^===\s*SCENE\s*\d*\s*\|\s*(\w+)\s*===\s*$", text, flags=re.M)
    scenes: list[dict] = []
    for n, (kind, body) in enumerate(zip(blocks[1::2], blocks[2::2]), 1):
        kind = kind.strip().lower()
        label = f"Scene {n}"
        if kind not in EXPLAINER_KINDS:
            problems.append(f"{label}: unknown kind '{kind}' (use {', '.join(EXPLAINER_KINDS)}).")
            continue
        fields: dict[str, str] = {}
        items_raw: list[str] = []
        current = ""
        for line in body.splitlines():
            if line.lstrip().startswith("#") or not line.strip():
                continue
            m = re.match(r"^(HEADLINE|SUBTITLE|SPEECH|ITEMS)\s*:\s*(.*)$", line)
            if m:
                current = m.group(1)
                if current != "ITEMS":
                    fields[current] = m.group(2).strip()
                continue
            if current == "ITEMS" and line.lstrip().startswith("-"):
                items_raw.append(line.lstrip()[1:].strip())
            elif current in ("HEADLINE", "SUBTITLE", "SPEECH"):
                fields[current] += " " + line.strip()
        headline = words_to_digits(_clean(fields.get("HEADLINE")))
        subtitle = words_to_digits(_clean(fields.get("SUBTITLE")))
        if not 3 <= len(headline) <= 80:
            problems.append(f"{label}: HEADLINE needs 3 to 80 characters (it is {len(headline)}).")
        if len(subtitle) > 110:
            problems.append(f"{label}: SUBTITLE is {len(subtitle)} characters; the limit is 110.")
        speech = _speech(fields.get("SPEECH", ""), f"{label} SPEECH", problems)
        if len(speech.split()) < 4:
            problems.append(f"{label}: SPEECH is missing or too short.")
        items = []
        for raw in items_raw:
            parts = [p.strip() for p in raw.split("|")] + ["", ""]
            lab, val, cue = words_to_digits(parts[0]), words_to_digits(parts[1]), parts[2]
            if not lab or len(lab) > 70 or len(val) > 90:
                problems.append(f"{label}: an item needs text (up to 70 characters) and a value of up to 90: '{raw[:40]}'.")
                continue
            items.append({"label": lab, "value": val, "cue": cue or _auto_cue(lab, speech)})
        lo, hi = EXPLAINER_KINDS[kind]
        if not lo <= len(items) <= hi:
            problems.append(f"{label} ({kind}): needs {lo} to {hi} items, has {len(items)}.")
        if kind in ("stat", "quote") and items and not items[0]["value"]:
            problems.append(f"{label} ({kind}): the item needs a value after the first |.")
        scenes.append({"kind": kind, "headline": headline, "subtitle": subtitle, "items": items, "tts_text": speech})
    if not scenes:
        problems.append("No scenes found. Each scene starts with a line like: === SCENE 1 | title ===")
    elif sum(len(s["tts_text"].split()) for s in scenes) < 20:
        problems.append("The whole script is under 20 spoken words.")
    banned = ee.find_forbidden(" ".join(s["tts_text"] for s in scenes))
    if banned:
        print(f"⚠️ Note: the phrase '{banned}' is on the banned list for news copy. Kept because you approved the script.")
    if problems:
        raise DraftError(problems)
    return {**{k: v for k, v in head.items() if k != "sources"}, "title": ee.polish_title(title), "scenes": scenes,
            "source": {"title": title, "url": "\n".join(head["sources"])}}


# ----- quiz --------------------------------------------------------------------------------------

QUIZ_HELP = """# MahaSpark quiz script. Edit anything, save, then run:
#   python scripts/quiz.py produce <this file>
# Each question:  Q: question   A) B) C) D) four options   ANSWER: A, B, C or D   WHY: one-line explanation
# Optional, only when the voice must say something different from the screen (for example an acronym spelled
# out): QSPEECH:, ASPEECH: BSPEECH: CSPEECH: DSPEECH:, WHYSPEECH:   (Devanagari words only)
# Lines starting with # are ignored. Delete a whole question block to drop it."""

LETTERS = "ABCD"


def quiz_to_text(quiz: dict, sources: list[str]) -> str:
    out = [QUIZ_HELP, "", f"TITLE: {quiz['title']}", f"CAPTION: {quiz.get('social_caption', '')}",
           f"KEYWORDS: {', '.join(quiz.get('seo_keywords', []))}", f"SOURCES: {' | '.join(sources)}", ""]
    for n, q in enumerate(quiz["questions"], 1):
        out += [f"=== Q{n} ===", f"Q: {q['question']}"]
        if _clean(q["question_tts"]) != _clean(ee.clean_tts_text(numbers_to_words(q["question"]))):
            out.append(f"QSPEECH: {q['question_tts']}")
        for k in range(4):
            out.append(f"{LETTERS[k]}) {q['options'][k]}")
            if _clean(q["options_tts"][k]) != _clean(ee.clean_tts_text(numbers_to_words(q["options"][k])).rstrip(".")):
                out.append(f"{LETTERS[k]}SPEECH: {q['options_tts'][k]}")
        out += [f"ANSWER: {LETTERS[q['correct']]}", f"WHY: {q['explanation']}"]
        if _clean(q["explanation_tts"]) != _clean(ee.clean_tts_text(numbers_to_words(q["explanation"]))):
            out.append(f"WHYSPEECH: {q['explanation_tts']}")
        out.append("")
    return "\n".join(out)


def parse_quiz(text: str) -> dict:
    problems: list[str] = []
    head = _header(text)
    title = words_to_digits(head["title"])
    if not 8 <= len(title) <= 100:
        problems.append("TITLE: needs 8 to 100 characters.")
    questions = []
    for n, body in enumerate(re.split(r"^===\s*Q\s*\d*\s*===\s*$", text, flags=re.M)[1:], 1):
        label = f"Q{n}"
        f: dict[str, str] = {}
        current = ""
        for line in body.splitlines():
            if line.lstrip().startswith("#") or not line.strip():
                continue
            m = re.match(r"^(Q|QSPEECH|WHY|WHYSPEECH|ANSWER|[A-D]SPEECH)\s*:\s*(.*)$", line) or re.match(r"^([A-D])\s*\)\s*(.*)$", line)
            if m:
                current = m.group(1)
                f[current] = m.group(2).strip()
            elif current:
                f[current] += " " + line.strip()
        question = words_to_digits(_clean(f.get("Q")))
        options = [words_to_digits(_clean(f.get(c))) for c in LETTERS]
        why = words_to_digits(_clean(f.get("WHY")))
        answer = _clean(f.get("ANSWER")).upper()[:1]
        if not 8 <= len(question) <= 120:
            problems.append(f"{label}: Q needs 8 to 120 characters.")
        if any(not o or len(o) > 44 for o in options) or len({longform.squash(o) for o in options}) != 4:
            problems.append(f"{label}: needs four different options A) B) C) D), each up to 44 characters.")
        if answer not in LETTERS:
            problems.append(f"{label}: ANSWER must be A, B, C or D.")
        if not 8 <= len(why) <= 130:
            problems.append(f"{label}: WHY needs 8 to 130 characters.")
        q_tts = _speech(f.get("QSPEECH") or question, f"{label} question", problems)
        o_tts = [_speech(f.get(f"{c}SPEECH") or o, f"{label} option {c}", problems).rstrip(".") for c, o in zip(LETTERS, options)]
        w_tts = _speech(f.get("WHYSPEECH") or why, f"{label} WHY", problems)
        questions.append({"question": question, "options": options, "correct": LETTERS.find(answer), "explanation": why,
                          "question_tts": q_tts, "options_tts": o_tts, "explanation_tts": w_tts})
    if len(questions) < 3:
        problems.append("A quiz needs at least 3 questions (each starts with a line like: === Q1 ===).")
    if problems:
        raise DraftError(problems)
    return {"title": ee.polish_title(title), "social_caption": head["social_caption"], "seo_keywords": head["seo_keywords"],
            "questions": questions, "sources": head["sources"]}
