"""Editorial writer for one bulletin item: a headline, ONE context line and the sentences the anchor reads.

The long 16:9 news bulletin is ten of these in a row. Facts discipline, phonetic TTS rules and banned phrases are
shared with the reel writer (``editorial_engine``); only the output shape is different.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

import editorial_engine as ee
from editorial_prompts import AUDIO_MOODS, SYSTEM_INSTRUCTION
from llm_providers import ContentRejected, generate_json

MAX_CONTEXT_CHARS = 100
MIN_ITEM_WORDS, MAX_ITEM_WORDS = 14, 42


def _section(start_marker: str, end_marker: str) -> str:
    a = SYSTEM_INSTRUCTION.index(start_marker)
    b = SYSTEM_INSTRUCTION.index(end_marker)
    return SYSTEM_INSTRUCTION[a:b].strip()


# The fact discipline and phonetic rules are reused word for word from the reel prompt, so they cannot drift apart.
FACT_RULES = _section("══════════ 1. FACT DISCIPLINE", "══════════ 2. 5W1H")
PHONETIC_RULES = _section("══════════ 5. PHONETIC RULES", "══════════ 6. PRODUCTION")

_MOOD_LINES = "\n".join(f"  - {name}: {use}" for name, use in AUDIO_MOODS.items())

BULLETIN_INSTRUCTION = f"""
You are the news editor of MahaSpark, a No. 1 Marathi news channel. You write ONE item of a spoken news bulletin:
a hard headline, ONE context line, and the two short sentences a composed senior anchor reads aloud. Your output is
machine-read: return exactly one JSON object that follows the supplied schema, nothing else.

{FACT_RULES}

══════════ ITEM FORMAT ══════════
- "headline": the on-screen headline, a complete, specific news line (subject + verb + fact) of at most 52
  characters, the way a news editor writes a top line. Never a label ("उड्डाणपूल बातमी"), no clickbait, no question.
- "context": ONE clean fact sentence of at most 95 characters that adds what the headline does not (who, where, how
  much, what next). It must not repeat the headline. Clean Marathi with sharp digits and symbols (85%, ₹1,200 कोटी);
  no hashtags, emoji, quotation marks or English words.
- "tts_text": what the anchor says: the headline's fact first, then the context, as two short sentences, 16 to 38
  words in total, written under the PHONETIC RULES below. Name the institution or leader inside the sentence.
- "category": a short Marathi category label (for example "पुणे", "राजकारण", "अर्थकारण", "क्रीडा").
- "audio_mood": one of
{_MOOD_LINES}
- "visual_query": 2 to 5 plain English words describing what a viewer should SEE (concrete and filmable, for example
  "flyover construction traffic", "court building", "heavy rain flooded street"). Generic only: never a person,
  party, brand or place name. "" if nothing sensible.
- "visual_place": English name of the city, district or landmark the story is set in (at most 3 words) or "".
- "public_figure": the English name of ONE well-known public figure ONLY when the item is about what that named
  person said or did in their public role, spelled as on Wikipedia. Otherwise "". NEVER for a victim, an accused or
  arrested person, a suspect, a minor, a private citizen, or any death, accident or crime item.
- "event_key": 3 to 6 lowercase English words naming the EVENT itself (what happened and where), for example
  "pune koyta gang guard attack". Any report of the same event must get the same words, so duplicates can be found.
- "seo_keywords": 3 to 6 search keywords, Marathi and English.

══════════ STYLE ══════════
Inverted pyramid, active voice, every word carries a fact, no filler, no adjectives the source does not use.
NEVER use agency clichés such as "अधिकृत माहितीनुसार", "वृत्तानुसार", "सूत्रांनी दिलेल्या माहितीनुसार",
"प्राप्त माहितीनुसार", "असे सांगण्यात आले", and no "जाणून घ्या" or "बघा काय घडले". No sign-off or call to action.

{PHONETIC_RULES}
""".strip()

MoodName = Literal["serious", "crime", "breaking", "upbeat", "neutral"]


class BulletinItem(BaseModel):
    approved: bool = True
    rejection_reason: str = ""
    category: str = ""
    headline: str = ""
    context: str = ""
    tts_text: str = ""
    audio_mood: MoodName = "neutral"
    visual_query: str = ""
    visual_place: str = ""
    public_figure: str = ""
    event_key: str = ""
    seo_keywords: list[str] = Field(default_factory=list)


def build_item_prompt(title: str, summary: str, article_text: str, source_url: str) -> str:
    article = (article_text or "").strip()
    return (
        "SOURCE MATERIAL (the only facts you may use)\n"
        f"Source URL: {source_url or 'not available'}\n"
        f"Source title: {title.strip()}\n"
        f"Source summary: {summary.strip() or 'not available'}\n"
        "Full article text:\n"
        f'"""\n{article[:6000] or "NOT AVAILABLE - only the title and summary above exist."}\n"""\n\n'
        "Write the bulletin item now. Set approved to false only for a rumour, an unattributed leak or an opinion piece."
    )


def validate_item(data: dict, source_text: str) -> dict:
    """Deterministic checks for one item. Raises ContentRejected (not approved) or ValueError (model gets one repair)."""
    if not data.get("approved", True):
        raise ContentRejected(str(data.get("rejection_reason") or "Not approved by the editorial model."))

    headline = re.sub(r"\s+", " ", str(data.get("headline", ""))).strip()
    context = re.sub(r"\s+", " ", str(data.get("context", ""))).strip()
    tts_text = ee.clean_tts_text(data.get("tts_text", ""))
    category = re.sub(r"\s+", " ", str(data.get("category", ""))).strip()[: ee.MAX_CATEGORY_CHARS] or "मोठी बातमी"
    mood = data.get("audio_mood") if data.get("audio_mood") in AUDIO_MOODS else "neutral"

    banned = ee.find_forbidden(f"{headline} {context} {tts_text}")
    if banned:
        raise ValueError(f"The phrase '{banned}' is banned. Name the institution or person inside the sentence instead.")
    if len(headline) < 6:
        raise ValueError("headline is missing or too short.")
    if len(headline) > ee.MAX_HEADLINE_CHARS:
        raise ValueError(f"headline has {len(headline)} characters; the limit is {ee.MAX_HEADLINE_CHARS}. Shorten it.")
    if len(context) < 10:
        raise ValueError("context is missing or too short.")
    if len(context) > MAX_CONTEXT_CHARS:
        raise ValueError(f"context has {len(context)} characters; the limit is {MAX_CONTEXT_CHARS}. Shorten it.")
    words = len(tts_text.split())
    if not (MIN_ITEM_WORDS <= words <= MAX_ITEM_WORDS):
        raise ValueError(f"tts_text has {words} words; it must be between {MIN_ITEM_WORDS} and {MAX_ITEM_WORDS}.")
    problems = ee.tts_problems(tts_text)
    if problems:
        raise ValueError(problems[0])

    allowed = ee.source_numbers(source_text)
    if allowed:
        for number in ee.source_numbers(f"{headline} {context}"):
            if number not in allowed:
                raise ValueError(f"The on-screen text shows the number {number}, which is not in the source.")

    return {
        "category": category,
        "headline": headline,
        "context": context,
        "tts_text": tts_text,
        "audio_mood": mood,
        "visual_query": ee.clean_visual_query(data.get("visual_query", "")),
        "visual_place": ee.clean_visual_place(data.get("visual_place", "")),
        "public_figure": ee.clean_public_figure(data.get("public_figure", ""), mood),
        "event_key": " ".join(re.sub(r"[^a-z ]", " ", str(data.get("event_key", "")).lower()).split()[:6]),
        "seo_keywords": ee.clean_keywords(data.get("seo_keywords", []))[:6],
    }


def write_item(title: str, summary: str, article_text: str, source_url: str) -> dict:
    """Write one validated bulletin item. Raises ContentRejected / LLMUnavailableError."""
    title, summary, article_text = (title or "").strip(), (summary or "").strip(), (article_text or "").strip()
    if len(title) + len(summary) + len(article_text) < ee.MIN_SOURCE_CHARS:
        raise ContentRejected("Source has almost no text; nothing can be written from it.")
    source_text = f"{title}\n{summary}\n{article_text}"
    item = generate_json(
        system_instruction=BULLETIN_INSTRUCTION,
        prompt=build_item_prompt(title, summary, article_text, source_url),
        response_model=BulletinItem,
        validate=lambda data: validate_item(data, source_text),
    )
    item["source"] = {"title": title, "url": source_url}
    return item


def same_event(a: dict, b: dict) -> bool:
    """True when two items report the same event (shared words of the model's English ``event_key``)."""
    wa = {w for w in a.get("event_key", "").split() if len(w) >= 3}
    wb = {w for w in b.get("event_key", "").split() if len(w) >= 3}
    shared = len(wa & wb)
    return bool(wa and wb) and (shared >= 3 or shared / min(len(wa), len(wb)) >= 0.6)
