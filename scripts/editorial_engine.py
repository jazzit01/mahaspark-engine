"""MahaSpark editorial engine: prime-time script writing and anchor voiceover.

1. ``write_story``        source text -> validated story JSON (5W1H, scenes, phonetic TTS script).
2. ``synthesize_voiceover`` ``tts_narration_script`` -> ``remotion/public/voiceover.wav``
   through Google AI Studio ``gemini-3.8-flash-tts`` (Interactions API).

Every editorial and phonetic rule in ``editorial_prompts.py`` is enforced again here by
deterministic checks, so a model slip (a digit in the speech text, a banned agency phrase, a number
that is not in the source) is caught and repaired instead of reaching the voice or the screen.
"""

from __future__ import annotations

import base64
import io
import json
import re
import zlib
import time
import wave
from pathlib import Path
from typing import Literal

import requests
from pydantic import BaseModel, Field

from config import STORY_PATH, VOICEOVER_PATH, get_env_value
from content_rules import office_error, plain_names
from fetch_news import THIN_SOURCE_CHARS
from marathi_numbers import numbers_to_words, words_to_digits
from editorial_prompts import AUDIO_MOODS, SYSTEM_INSTRUCTION, THEMES, build_user_prompt
from llm_providers import (
    ContentFailed,
    ContentRejected,
    LLMUnavailableError,
    gemini_keys,
    generate_json,
    is_auth_error,
    is_quota_error,
    is_transient_error,
)

# ----- schema ---------------------------------------------------------------------------------

ThemeName = Literal[
    "PrimeGridStudio",
    "BreakingNewsStudio",
    "EditorialDeskLight",
    "DataTelemetryStudio",
    "GlassNewsroomDepth",
]
MoodName = Literal["serious", "crime", "breaking", "upbeat", "neutral"]


class FiveWOneH(BaseModel):
    what: str = ""
    when: str = ""
    who: str = ""
    where: str = ""
    why: str = ""
    how: str = ""


class Motion(BaseModel):
    """Typed (not a free dict): Gemini's Developer API rejects the ``additionalProperties`` a dict[str, str] produces."""

    type: str = ""
    value: str = ""
    label: str = ""


class Scene(BaseModel):
    headline: str = ""
    description: str = ""
    tts_text: str = ""
    visual_query: str = ""
    motion: Motion = Field(default_factory=Motion)


class Story(BaseModel):
    approved: bool
    rejection_reason: str = ""
    category: str = ""
    visual_theme: ThemeName = "PrimeGridStudio"
    audio_mood: MoodName = "neutral"
    five_w_one_h: FiveWOneH = Field(default_factory=FiveWOneH)
    scenes: list[Scene] = Field(default_factory=list)
    social_title: str = ""
    social_caption: str = ""
    hashtags: str = ""
    seo_keywords: list[str] = Field(default_factory=list)
    public_figure: str = ""
    visual_place: str = ""


# ----- deterministic editorial rules ----------------------------------------------------------

FORBIDDEN_PHRASES = [
    # Stiff agency clichés: the institution or leader must be named inside the sentence instead.
    "अधिकृत माहितीनुसार",
    "वृत्तानुसार",
    "सूत्रांनी दिलेल्या माहितीनुसार",
    "सूत्रांच्या माहितीनुसार",
    "प्राप्त माहितीनुसार",
    "मिळालेल्या माहितीनुसार",
    "असे सांगण्यात आले",
    # Vague filler and clickbait inherited from the previous engine.
    "अचानक काहीतरी घडले",
    "टोकाचे पाऊल उचलले",
    "हळहळ व्यक्त होत आहे",
    "हवा आल्यासारखे",
    "बघा काय घडले",
    "महान परिणाम",
    "अशा प्रकारे",
    "जाणून घ्या",
    "तुम्हाला माहिती आहे का",
]

MIN_SOURCE_CHARS = 60  # headline + whatever context exists; a fuller article is better but not required
MAX_HEADLINE_CHARS = 56
MAX_DESCRIPTION_CHARS = 92
MAX_CATEGORY_CHARS = 24
MIN_SCENES, MAX_SCENES = 2, 8
MIN_TOTAL_WORDS, MAX_TOTAL_WORDS = 25, 185  # 25 words is a very short story; about 165 words is a full minute
SHORT_MAX_WORDS, SHORT_MAX_SCENES = 100, 4  # a 9:16 Short: 25-100 words, hook + up to three scenes
REEL_MIN_WORDS = 140  # a 16:9 video is about one minute; a thinner story becomes a 9:16 Short instead
MAX_HOOK_WORDS = 14

# Anything outside Devanagari letters/signs, whitespace, comma and full stop is unsafe for the voice.
_ILLEGAL_TTS_CHARS = re.compile(r"[^ऀ-॥॰-ॿ‌‍\s,.]")
_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def tts_problems(text: str) -> list[str]:
    """Return human-readable reasons why ``text`` is not safe to send to the Marathi voice."""
    bad = sorted(set(_ILLEGAL_TTS_CHARS.findall(text)) | set(re.findall(r"[०-९]", text)))
    if not bad:
        return []
    shown = " ".join(repr(c) for c in bad[:8])
    return [f"tts_text contains characters that must be spelled out in Devanagari words: {shown}"]


def clean_tts_text(text: str) -> str:
    """Normalise spacing and punctuation of one scene's speech text."""
    text = plain_names(str(text or "")).replace("।", ".").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.])", r"\1", text)
    text = re.sub(r"([,.])(?=\S)", r"\1 ", text).strip()
    if text and text[-1] not in ".":
        text = text.rstrip(",") + "."
    return text


def source_numbers(text: str) -> set[str]:
    # numbers the source spells out in words count too (the on-screen text is converted to digits)
    normalised = words_to_digits(str(text or "")).translate(_DEVANAGARI_DIGITS)
    return {m.replace(",", "") for m in _NUMBER.findall(normalised)}


def check_offices(text: str) -> None:
    """Raise ValueError (the model's one repair) when a known leader is given the wrong office, e.g. Shinde as मुख्यमंत्री."""
    message = office_error(text)
    if message:
        raise ValueError(message)


def find_forbidden(text: str) -> str | None:
    lowered = str(text or "")
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            return phrase
    return None


AVOID_THEME: str | None = None  # studio of the previous reel; set by the pipeline so two reels in a row differ

CALM_THEMES = ["PrimeGridStudio", "DataTelemetryStudio", "GlassNewsroomDepth"]  # the white studio was retired on request


def set_avoid_theme(theme: str | None) -> None:
    global AVOID_THEME
    AVOID_THEME = theme if theme in THEMES else None


def clean_visual_query(value) -> str:
    """English search words for stock footage: Latin letters and spaces only, at most 6 words (else empty)."""
    words = re.sub(r"[^A-Za-z ]+", " ", str(value or "")).split()
    return " ".join(words[:6]).lower()


def clean_visual_place(value) -> str:
    """English place name (city or district, at most 3 words) that helps find a photo of the real location."""
    words = re.sub(r"[^A-Za-z ]+", " ", str(value or "")).split()
    return " ".join(words[:3])


def _squash(text: str) -> str:
    return re.sub(r"[\s\"'“”‘’]+", "", str(text or ""))


def clean_motion(raw, source_text: str) -> dict:
    """One animated graphic for a scene, or {} when it is not fully backed by the source.

    stat:  a figure that appears in the source (count-up / bar)      value="₹1,200 कोटी", label="मंजूर निधी"
    quote: a sentence quoted word for word from the source + speaker  value="...", label="speaker"
    The map-pin 'place' graphic was removed on request (it is dropped like any unknown type). Anything that does not check out is dropped silently, so the scene simply has no graphic."""
    if not isinstance(raw, dict):
        return {}
    kind = str(raw.get("type", "")).strip().lower()
    value = re.sub(r"\s+", " ", str(raw.get("value", ""))).strip()
    label = re.sub(r"\s+", " ", str(raw.get("label", ""))).strip()[:40]
    source = str(source_text or "")
    if kind == "stat":
        value = words_to_digits(value)
        numbers = source_numbers(value)
        if not numbers or len(value) > 24 or not numbers <= source_numbers(source):
            return {}
    elif kind == "quote":
        if not (10 <= len(value) <= 90) or _squash(value) not in _squash(source) or not label or label not in source:
            return {}
    else:
        return {}
    return {"type": kind, "value": value, "label": label}


def clean_public_figure(value, mood: str) -> str:
    """English name of the public figure the story is about, for a Wikimedia Commons photo lookup.

    Never used for grave or crime stories (victims, accused and the dead must not get a stock face)."""
    if mood in ("serious", "crime", "breaking"):
        return ""
    name = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z .'-]+", " ", str(value or ""))).strip()
    return name if 2 <= len(name.split()) <= 5 and len(name) <= 60 else ""


def clean_keywords(value) -> list[str]:
    """6-12 distinct SEO keywords (Marathi and English), trimmed."""
    items = value if isinstance(value, list) else re.split(r"[,\n]", str(value or ""))
    seen, out = set(), []
    for item in items:
        word = re.sub(r"\s+", " ", str(item)).strip(" #,.")
        if 2 <= len(word) <= 40 and word.lower() not in seen:
            seen.add(word.lower())
            out.append(word)
    return out[:12]


def clean_hashtags(value) -> str:
    """Up to 15 distinct hashtags, always starting with #MahaSpark."""
    tags = ["#MahaSpark"]
    for raw in re.split(r"\s+", str(value or "")):
        tag = "#" + re.sub(r"[^\w\u0900-\u097F]", "", raw.lstrip("#"))
        if len(tag) > 2 and tag.lower() not in {t.lower() for t in tags}:
            tags.append(tag)
    if len(tags) == 1:
        tags += ["#मराठीबातम्या", "#महाराष्ट्र"]
    return " ".join(tags[:15])


def pick_theme(model_choice: str | None, mood: str, seed_text: str) -> str:
    """Studio for the reel. Grave moods (or the model asking for the breaking studio) get BreakingNewsStudio.
    Everything else rotates over all four other studios from a hash of the story, skipping the studio the
    previous reel used, so videos do not all share one background. The model's own pick is not trusted for
    variety: it kept choosing the same studio."""
    if mood in ("serious", "breaking") or model_choice == "BreakingNewsStudio":
        return "BreakingNewsStudio"
    pool = [t for t in CALM_THEMES if t != AVOID_THEME] or CALM_THEMES
    if mood == "crime":
        pool = [t for t in pool if t != "GlassNewsroomDepth"] or pool
    return pool[zlib.crc32(seed_text.encode("utf-8")) % len(pool)]


HUES = [-60, -35, -15, 20, 40, 65, 95, 140]  # degrees; 0 (the studio's own colours) is only used for Breaking


def pick_hue(seed_text: str, calm: bool = True) -> int:
    """Per-video hue rotation of the background, from a hash of the story, so every video looks different."""
    if not calm:
        return 0
    return HUES[zlib.crc32(("hue" + seed_text).encode("utf-8")) % len(HUES)]


TITLE_SUFFIXES = (" | MahaSpark मराठी बातम्या", " | MahaSpark")
MAX_TITLE_CHARS = 100  # YouTube Shorts limit


def polish_title(title: str) -> str:
    """Tidy the model's social title and add the channel suffix when it still fits in 100 characters."""
    title = re.sub(r"[#\"“”‘’]|[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", str(title or ""))
    title = re.sub(r"\s+", " ", title).strip(" .|-–—")
    title = re.sub(r"\s*\|\s*MahaSpark.*$", "", title)  # a suffix the model added itself
    title = re.sub(r"\s+MahaSpark$", "", title).strip(" .|-–—")
    for suffix in TITLE_SUFFIXES:
        if title and len(title) + len(suffix) <= MAX_TITLE_CHARS:
            return title + suffix
    return title[:MAX_TITLE_CHARS].rstrip()


def validate_story(
    data: dict,
    source_text: str = "",
    min_words: int = MIN_TOTAL_WORDS,
    max_words: int = MAX_TOTAL_WORDS,
    max_scenes: int = MAX_SCENES,
) -> dict:
    """Validate and normalise a generated story. Raises ValueError (repairable) or ContentRejected."""
    if not isinstance(data, dict):
        raise ValueError("Generated content is not a JSON object.")

    if data.get("approved") is not True:
        raise ContentRejected(str(data.get("rejection_reason") or "Rejected by the editorial model.").strip())

    five = data.get("five_w_one_h") or {}
    # Only "what" must be answered. When the source does not give when/who/where/why/how, those stay empty:
    # the script is still written from the headline and context, and nothing is invented to fill them.
    if len(str(five.get("what", "")).strip()) < 3:
        raise ValueError("five_w_one_h.what is missing; state in one sentence what happened.")

    scenes_in = data.get("scenes") or []
    if not (MIN_SCENES <= len(scenes_in) <= max_scenes):
        raise ValueError(f"Expected {MIN_SCENES} to {max_scenes} scenes, got {len(scenes_in)}.")

    allowed_numbers = source_numbers(source_text)
    scenes = []
    for idx, raw in enumerate(scenes_in, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Scene {idx} is not an object.")
        # on-screen text shows digits (१२, ₹१,२०० कोटी), never spelled-out numbers
        headline = words_to_digits(re.sub(r"\s+", " ", str(raw.get("headline", ""))).strip())
        description = words_to_digits(re.sub(r"\s+", " ", str(raw.get("description", ""))).strip())
        # the voice script is spoken Marathi: digits the model wrote are spelled out here, deterministically
        tts_text = clean_tts_text(numbers_to_words(raw.get("tts_text", "")))

        if len(headline) < 6:
            raise ValueError(f"Scene {idx} headline is missing or too short.")
        if len(headline) > MAX_HEADLINE_CHARS:
            raise ValueError(f"Scene {idx} headline has {len(headline)} characters; the limit is {MAX_HEADLINE_CHARS}. Shorten it.")
        if len(description) < 10:
            raise ValueError(f"Scene {idx} description is missing or too short.")
        if len(description) > MAX_DESCRIPTION_CHARS:
            raise ValueError(f"Scene {idx} description has {len(description)} characters; the limit is {MAX_DESCRIPTION_CHARS}. Shorten it.")
        if len(tts_text.split()) < 4:
            raise ValueError(f"Scene {idx} tts_text is too short.")

        problems = tts_problems(tts_text)
        if problems:
            raise ValueError(f"Scene {idx}: {problems[0]}")

        if allowed_numbers:
            for number in source_numbers(f"{headline} {description}"):
                if number not in allowed_numbers:
                    raise ValueError(
                        f"Scene {idx} shows the number {number}, which is not in the source. Use only numbers from the source."
                    )

        scenes.append(
            {
                "headline": headline,
                "description": description,
                "tts_text": tts_text,
                "visual_query": clean_visual_query(raw.get("visual_query", "")),
                "motion": clean_motion(raw.get("motion"), source_text),
            }
        )

    category = re.sub(r"\s+", " ", str(data.get("category", ""))).strip()
    if not category:
        raise ValueError("category is missing.")
    if len(category) > MAX_CATEGORY_CHARS:
        raise ValueError(f"category is longer than {MAX_CATEGORY_CHARS} characters.")

    social_title = polish_title(str(data.get("social_title", "")).strip() or scenes[0]["headline"])
    social_caption = str(data.get("social_caption", "")).strip() or scenes[0]["description"]
    hashtags = clean_hashtags(data.get("hashtags", ""))
    keywords = clean_keywords(data.get("seo_keywords", []))

    visible = " ".join(
        [category, social_title, social_caption]
        + [f"{s['headline']} {s['description']} {s['tts_text']}" for s in scenes]
        + keywords
        + [str(v) for v in five.values()]
    )
    check_offices(visible)
    banned = find_forbidden(visible)
    if banned:
        raise ValueError(f'The phrase "{banned}" is forbidden. Name the actual institution, leader or department instead.')

    narration = " ".join(s["tts_text"] for s in scenes)
    total_words = len(narration.split())
    if not (min_words <= total_words <= max_words):
        raise ValueError(
            f"Narration has {total_words} words; it must be between {min_words} and {max_words}."
            " Add more verified facts from the source (never invent or repeat) or shorten it."
        )
    hook_words = len(scenes[0]["tts_text"].split())
    if hook_words > MAX_HOOK_WORDS:
        raise ValueError(f"The hook has {hook_words} words; it must be a 3 to 4 second line of at most {MAX_HOOK_WORDS} words.")

    theme = data.get("visual_theme")
    mood = str(data.get("audio_mood", "")).strip().lower()

    return {
        "approved": True,
        "category": category,
        "visual_theme": (chosen_theme := pick_theme(theme, mood, source_text or narration)),
        "bg_hue": pick_hue(source_text or narration, calm=chosen_theme != "BreakingNewsStudio"),
        "audio_mood": mood if mood in AUDIO_MOODS else "neutral",
        "five_w_one_h": {k: str(five.get(k, "")).strip() for k in ("what", "when", "who", "where", "why", "how")},
        "tts_narration_script": narration,
        "scenes": scenes,
        "social_title": social_title,
        "social_caption": social_caption,
        "hashtags": hashtags,
        "seo_keywords": keywords,
        "public_figure": clean_public_figure(data.get("public_figure", ""), mood),
        "visual_place": clean_visual_place(data.get("visual_place", "")),
    }


def _write(title: str, summary: str, article_text: str, source_url: str, source_text: str, short: bool) -> dict:
    return generate_json(
        system_instruction=SYSTEM_INSTRUCTION,
        prompt=build_user_prompt(title, summary, article_text, source_url, short=short),
        response_model=Story,
        validate=lambda data: validate_story(
            data,
            source_text,
            min_words=MIN_TOTAL_WORDS if short else REEL_MIN_WORDS,
            max_words=SHORT_MAX_WORDS if short else MAX_TOTAL_WORDS,
            max_scenes=SHORT_MAX_SCENES if short else MAX_SCENES,
        ),
    )


def write_story(title: str, summary: str, article_text: str, source_url: str) -> dict:
    """Write one validated prime-time story: a one-minute 16:9 video when the sources are rich enough, otherwise a
    9:16 Short (``story["format"] == "portrait"``). Raises ContentRejected / LLMUnavailableError."""
    title, summary, article_text = (title or "").strip(), (summary or "").strip(), (article_text or "").strip()
    if len(summary) + len(article_text) < MIN_SOURCE_CHARS:
        raise ContentRejected(
            "Source has almost no text (under 60 characters of headline and context); nothing can be written from it."
        )

    source_text = f"{title}\n{summary}\n{article_text}"
    story = None
    if len(source_text) >= THIN_SOURCE_CHARS:  # enough facts for a full minute: try the long video first
        try:
            story = _write(title, summary, article_text, source_url, source_text, short=False)
            story["format"] = "landscape"
        except (ValueError, ContentFailed) as exc:
            # Every model failed the one-minute checks (usually too few facts for 140 words, sometimes a slip in a
            # long script). A Short is far easier to write correctly than losing the story.
            print(f"ℹ️ No valid one-minute script ({str(exc)[:160]}); writing a 9:16 Short instead.")
    if story is None:
        story = _write(title, summary, article_text, source_url, source_text, short=True)
        story["format"] = "portrait"
    story["source"] = {"title": title, "url": source_url}
    return story


def save_story(story: dict, path: Path = STORY_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ----- anchor voiceover -----------------------------------------------------------------------

# Tried in order. The first two are the current Interactions-API models (Google's docs list them with
# google-genai >= 2.25.0); the 3.1 preview and the 2.5 preview models are older fallbacks that may still be
# enabled for a key when the newest one is not (a 404 "model not found" means THIS key can't use that model).
TTS_MODELS_DEFAULT = [
    "gemini-3.8-flash-tts",
    "gemini-3.8-flash-lite-tts",
    "gemini-3.1-flash-tts-preview",
    "gemini-2.5-pro-preview-tts",
    "gemini-2.5-flash-preview-tts",
]
TTS_VOICE_DEFAULT = "Kore"
TTS_SAMPLE_RATE = 24000
TTS_ATTEMPTS_PER_MODEL = 2

ANCHOR_STYLE = (
    "Speak in Marathi as a seasoned, composed senior prime-time news anchor on a leading Marathi "
    "television channel. Crisp, precise Devanagari pronunciation of every word, including borrowed "
    "words that are written in Devanagari. Calm, authoritative and steady cadence at a measured "
    "broadcast pace, never rushed. Take a short natural breath at every comma and a slightly longer "
    "pause at every full stop. Neutral and serious in tone, with no theatrics, no excitement and no "
    "smiling voice. Open the first sentence with weight and gravity."
)


API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def discover_tts_models() -> list[str]:
    """Ask Google which TTS models the first API key can see (model ids containing "tts")."""
    keys = gemini_keys()
    if not keys:
        return []
    api_key = keys[0]
    try:
        resp = requests.get(f"{API_BASE}/models", params={"pageSize": 1000}, headers={"x-goog-api-key": api_key}, timeout=20)
        if resp.status_code != 200:
            print(f"⚠️ Could not list models (HTTP {resp.status_code}); using the built-in TTS model list.")
            return []
        names = [str(m.get("name", "")).removeprefix("models/") for m in resp.json().get("models", [])]
    except (requests.RequestException, ValueError) as exc:
        print(f"⚠️ Could not list models ({exc}); using the built-in TTS model list.")
        return []
    return [n for n in names if "tts" in n.lower()]


def tts_model_chain(discovered: list[str] | None = None) -> list[str]:
    """Models to try, in order: ``GEMINI_TTS_MODEL`` (one name or a comma list), then the known models this
    key can see, then any other TTS model it can see, then the remaining built-in names as a last resort."""
    configured = [m.strip() for m in get_env_value("GEMINI_TTS_MODEL").split(",") if m.strip()]
    found = list(discovered or [])
    known_visible = [m for m in TTS_MODELS_DEFAULT if m in found]
    other_visible = [m for m in found if m not in TTS_MODELS_DEFAULT]
    return list(dict.fromkeys(configured + known_visible + other_visible + TTS_MODELS_DEFAULT))


def _sdk_version() -> str:
    try:
        from importlib.metadata import version

        return version("google-genai")
    except Exception:  # noqa: BLE001
        return "unknown"


def _wav_from_pcm(pcm: bytes, sample_rate: int = TTS_SAMPLE_RATE) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return buffer.getvalue()


def _is_bad_key(exc: Exception) -> bool:
    """An invalid key stops the whole chain. A 403 for one model does not: other models may still be allowed."""
    text = str(exc).upper()
    return any(t in text for t in ("API KEY NOT VALID", "API_KEY_INVALID", "INVALID API KEY", "UNAUTHENTICATED", "HTTP 401"))


def _tts_interactions(model: str, script: str, voice: str, api_key: str, style: str | None = None) -> bytes:
    """Route 1: Interactions API (documented for the Gemini 3.x TTS models)."""
    from google import genai  # imported lazily so script-only tests need no SDK

    client = genai.Client(api_key=api_key)
    interaction = client.interactions.create(
        model=model,
        input=[
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": script,
                        "annotations": [{"type": "speech_metadata", "style": style or ANCHOR_STYLE}],
                    }
                ],
            }
        ],
        response_format={"type": "audio"},
        generation_config={"speech_config": [{"voice": voice}]},
    )
    audio = base64.b64decode(interaction.output_audio.data)
    # Unary responses are WAV (RIFF) at 24 kHz mono; wrap raw PCM defensively if headerless.
    return audio if audio[:4] == b"RIFF" else _wav_from_pcm(audio)


def _tts_generate_content(model: str, script: str, voice: str, api_key: str, style: str | None = None) -> bytes:
    """Route 2: classic generateContent TTS over plain REST.

    The ``text`` part is ONLY the script: anything placed there is read aloud by the voice. The anchor
    style travels in ``systemInstruction`` instead; if a model rejects that field (HTTP 400) the request is
    repeated without it, so the voice never speaks an instruction."""
    body = {
        "contents": [{"parts": [{"text": script}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }

    def post(payload: dict):
        return requests.post(
            f"{API_BASE}/models/{model}:generateContent",
            headers={"x-goog-api-key": api_key},
            json=payload,
            timeout=180,
        )

    resp = post({**body, "systemInstruction": {"parts": [{"text": style or ANCHOR_STYLE}]}})
    if resp.status_code == 400:
        print(f"ℹ️ {model} does not accept a style instruction; sending the script alone.")
        resp = post(body)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        inline = resp.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
        pcm = base64.b64decode(inline["data"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError(f"unexpected generateContent response: {resp.text[:160]}") from exc
    rate = re.search(r"rate=(\d+)", str(inline.get("mimeType", "")))
    return _wav_from_pcm(pcm, int(rate.group(1)) if rate else TTS_SAMPLE_RATE)


# (model, key) pairs whose DAILY quota is spent and keys Google rejected: skipped for the rest of the run. A per-minute
# limit (the usual free-tier 429) only cools the pair down in ``_TTS_COOLDOWN`` (pair -> time it may be used again),
# so a long video does not die at scene 17 of 18 because the minute's requests were used up.
_TTS_SPENT: set = set()
_TTS_COOLDOWN: dict = {}
_TTS_BAD_KEYS: set = set()
TTS_COOLDOWN_DEFAULT = 65.0
_TTS_WAIT = {"left": 0.0}  # seconds the whole run may still spend waiting for per-minute limits (0 = fail fast, as reels do)


def allow_tts_wait(seconds: float) -> None:
    """Long videos and bulletins call this so a per-minute 429 is waited out instead of losing the video."""
    _TTS_WAIT["left"] = max(0.0, float(seconds))


def reset_tts_state() -> None:
    _TTS_SPENT.clear()
    _TTS_COOLDOWN.clear()
    _TTS_BAD_KEYS.clear()
    _TTS_WAIT['left'] = 0.0


def quota_cooldown(exc: Exception) -> float | None:
    """Seconds until a 429 clears, or None when it will not clear soon (daily quota used up, or a limit of 0)."""
    text = str(exc)
    if re.search(r"PerDay|per day|daily|limit:\s*0\b", text, re.IGNORECASE):
        return None
    found = re.search(r"retryDelay\W+(\d+(?:\.\d+)?)s", text)
    if found:
        return min(120.0, float(found.group(1)) + 2.0)
    return TTS_COOLDOWN_DEFAULT


def _request_tts_audio(script: str, model: str, api_key: str | None = None, voice: str | None = None, style: str | None = None) -> bytes:
    """Try both call routes for one model with one key. Quota, key and transient errors are left to the caller."""
    api_key = api_key or (gemini_keys() or [""])[0]
    if not api_key:
        raise LLMUnavailableError("GEMINI_API_KEY is not set; the Gemini voice cannot be used.")
    voice = voice or get_env_value("GEMINI_TTS_VOICE", TTS_VOICE_DEFAULT)

    errors = []
    for name, route in (("interactions", _tts_interactions), ("generateContent", _tts_generate_content)):
        try:
            audio = route(model, script, voice, api_key) if style is None else route(model, script, voice, api_key, style)
            print(f"🎙️ {model} voiced via {name}.")
            return audio
        except Exception as exc:  # noqa: BLE001
            if _is_bad_key(exc) or is_quota_error(exc) or is_transient_error(exc):
                raise
            errors.append(f"{name}: {type(exc).__name__}: {str(exc)[:120]}")
    raise RuntimeError(" | ".join(errors))


def clean_voice_tail(path: Path) -> None:
    """Drop a click / radio-like burst after the last word and fade the clip end (audio_tail.py). Never fails a voiceover."""
    try:
        import audio_tail

        info = audio_tail.trim_tail(path)
        if info["changed"]:
            note = f", incl. a {info['artifact_ms']} ms burst after the last word" if info["artifact_ms"] else ""
            print(f"🧹 Voice tail cleaned: {info['trimmed_ms']} ms removed{note}.")
        if info.get("tail"):  # numbers of the last segment after a pause: lets the first real run show what the chirr looks like
            print(f"   last sound after a pause: {info['tail']} -> {'removed' if info['artifact_ms'] else 'kept'}")
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ Could not clean the voice tail ({type(exc).__name__}: {exc}); using the clip as it is.")


def synthesize_voiceover(script: str, out_path: Path = VOICEOVER_PATH, attempts: int = TTS_ATTEMPTS_PER_MODEL,
                         voice: str | None = None, style: str | None = None) -> Path:
    """Render ``script`` (the phonetic ``tts_narration_script``) to a WAV file.

    Walks the model chain. A missing model, a request error or an exhausted per-model quota moves on to
    the next model; transient errors are retried on the same model; only an invalid API key stops
    everything. If no model works, ``LLMUnavailableError`` is raised and the pipeline falls back to a
    voiceless video instead of losing the story.
    """
    problems = tts_problems(script)
    if problems:
        raise ValueError(problems[0])

    discovered = discover_tts_models()
    chain = tts_model_chain(discovered)
    print(f"🔎 TTS models visible to this API key: {', '.join(discovered) if discovered else '(none listed)'}")
    print(f"🎙️ Gemini TTS (google-genai {_sdk_version()}), models to try: {', '.join(chain)}")
    errors: list[str] = []

    keys = gemini_keys()
    if not keys:
        raise LLMUnavailableError("GEMINI_API_KEY is not set; the Gemini voice cannot be used.")

    # Model-major: the preferred model is tried with every key before falling back to the next model.
    # When every pair is only cooling down (per-minute limit) the call waits for the earliest one instead of failing.
    while True:
        for model in chain:
            for number, key in enumerate(keys, start=1):
                if key in _TTS_BAD_KEYS or (model, key) in _TTS_SPENT or _TTS_COOLDOWN.get((model, key), 0.0) > time.monotonic():
                    continue
                label = f"{model} (key {number})" if len(keys) > 1 else model
                for attempt in range(1, attempts + 1):
                    try:
                        wav = (_request_tts_audio(script, model, key) if voice is None and style is None
                               else _request_tts_audio(script, model, key, voice=voice, style=style))
                        if len(wav) < 4000:
                            raise RuntimeError("TTS returned an empty or truncated audio file.")
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        out_path.write_bytes(wav)
                        clean_voice_tail(out_path)
                        print(f"✅ Voiceover written by {label}: {out_path} ({len(wav) // 1024} KB)")
                        return out_path
                    except LLMUnavailableError:
                        raise
                    except Exception as exc:  # noqa: BLE001
                        if _is_bad_key(exc):
                            _TTS_BAD_KEYS.add(key)
                            errors.append(f"key {number}: rejected")
                            print(f"🔑 Gemini key {number} was rejected; using the other keys.")
                            break
                        message = f"{type(exc).__name__}: {str(exc)[:200]}"
                        print(f"⚠️ TTS {label} attempt {attempt}/{attempts} failed: {message}")
                        if is_transient_error(exc) and attempt < attempts:
                            time.sleep(3 * attempt)
                            continue
                        if is_quota_error(exc):
                            cooldown = quota_cooldown(exc)
                            if cooldown is None:
                                _TTS_SPENT.add((model, key))
                            else:
                                _TTS_COOLDOWN[(model, key)] = time.monotonic() + cooldown
                        errors.append(f"{label}: {message}")
                        break  # quota, missing model or request error: next key, then next model

        now = time.monotonic()
        pending = [t - now for (m, k), t in _TTS_COOLDOWN.items() if t > now and k not in _TTS_BAD_KEYS and (m, k) not in _TTS_SPENT and m in chain]
        if not pending or min(pending) + 1.0 > _TTS_WAIT['left']:
            break
        pause = max(1.0, min(pending)) + 1.0
        print(f"⏳ Every Gemini voice is at its per-minute limit; waiting {pause:.0f}s for it to reset.")
        time.sleep(pause)
        _TTS_WAIT['left'] -= pause

    if keys and all(k in _TTS_BAD_KEYS for k in keys):
        raise LLMUnavailableError("Gemini API key rejected: every configured key was refused.")
    raise LLMUnavailableError(
        f"No Gemini TTS model worked (google-genai {_sdk_version()}). " + " | ".join(errors)
    )
