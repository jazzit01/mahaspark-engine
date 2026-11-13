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
import time
import wave
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from config import STORY_PATH, VOICEOVER_PATH, get_env_value
from editorial_prompts import AUDIO_MOODS, SYSTEM_INSTRUCTION, THEMES, build_user_prompt
from llm_providers import (
    ContentRejected,
    LLMUnavailableError,
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


class Scene(BaseModel):
    headline: str = ""
    description: str = ""
    tts_text: str = ""


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

MIN_SOURCE_CHARS = 200
MAX_HEADLINE_CHARS = 56
MAX_DESCRIPTION_CHARS = 92
MAX_CATEGORY_CHARS = 24
MIN_SCENES, MAX_SCENES = 3, 6
MIN_TOTAL_WORDS, MAX_TOTAL_WORDS = 60, 150
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
    text = str(text or "").replace("।", ".").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.])", r"\1", text)
    text = re.sub(r"([,.])(?=\S)", r"\1 ", text).strip()
    if text and text[-1] not in ".":
        text = text.rstrip(",") + "."
    return text


def source_numbers(text: str) -> set[str]:
    normalised = str(text or "").translate(_DEVANAGARI_DIGITS)
    return {m.replace(",", "") for m in _NUMBER.findall(normalised)}


def find_forbidden(text: str) -> str | None:
    lowered = str(text or "")
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            return phrase
    return None


def validate_story(data: dict, source_text: str = "") -> dict:
    """Validate and normalise a generated story. Raises ValueError (repairable) or ContentRejected."""
    if not isinstance(data, dict):
        raise ValueError("Generated content is not a JSON object.")

    if data.get("approved") is not True:
        raise ContentRejected(str(data.get("rejection_reason") or "Rejected by the editorial model.").strip())

    five = data.get("five_w_one_h") or {}
    for key in ("what", "when", "who", "where", "why", "how"):
        if len(str(five.get(key, "")).strip()) < 3:
            raise ValueError(f"five_w_one_h.{key} is missing; every script must answer What, When, Who, Where, Why and How.")

    scenes_in = data.get("scenes") or []
    if not (MIN_SCENES <= len(scenes_in) <= MAX_SCENES):
        raise ValueError(f"Expected {MIN_SCENES} to {MAX_SCENES} scenes, got {len(scenes_in)}.")

    allowed_numbers = source_numbers(source_text)
    scenes = []
    for idx, raw in enumerate(scenes_in, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Scene {idx} is not an object.")
        headline = re.sub(r"\s+", " ", str(raw.get("headline", ""))).strip()
        description = re.sub(r"\s+", " ", str(raw.get("description", ""))).strip()
        tts_text = clean_tts_text(raw.get("tts_text", ""))

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

        scenes.append({"headline": headline, "description": description, "tts_text": tts_text})

    category = re.sub(r"\s+", " ", str(data.get("category", ""))).strip()
    if not category:
        raise ValueError("category is missing.")
    if len(category) > MAX_CATEGORY_CHARS:
        raise ValueError(f"category is longer than {MAX_CATEGORY_CHARS} characters.")

    social_title = str(data.get("social_title", "")).strip() or scenes[0]["headline"]
    social_caption = str(data.get("social_caption", "")).strip() or scenes[0]["description"]
    hashtags = str(data.get("hashtags", "")).strip() or "#MahaSpark #मराठीबातम्या #महाराष्ट्र"

    visible = " ".join(
        [category, social_title, social_caption]
        + [f"{s['headline']} {s['description']} {s['tts_text']}" for s in scenes]
        + [str(v) for v in five.values()]
    )
    banned = find_forbidden(visible)
    if banned:
        raise ValueError(f'The phrase "{banned}" is forbidden. Name the actual institution, leader or department instead.')

    narration = " ".join(s["tts_text"] for s in scenes)
    total_words = len(narration.split())
    if not (MIN_TOTAL_WORDS <= total_words <= MAX_TOTAL_WORDS):
        raise ValueError(
            f"Narration has {total_words} words; it must be between {MIN_TOTAL_WORDS} and {MAX_TOTAL_WORDS}."
        )
    hook_words = len(scenes[0]["tts_text"].split())
    if hook_words > MAX_HOOK_WORDS:
        raise ValueError(f"The hook has {hook_words} words; it must be a 3 to 4 second line of at most {MAX_HOOK_WORDS} words.")

    theme = data.get("visual_theme")
    mood = str(data.get("audio_mood", "")).strip().lower()

    return {
        "approved": True,
        "category": category,
        "visual_theme": theme if theme in THEMES else "PrimeGridStudio",
        "audio_mood": mood if mood in AUDIO_MOODS else "neutral",
        "five_w_one_h": {k: str(five.get(k, "")).strip() for k in ("what", "when", "who", "where", "why", "how")},
        "tts_narration_script": narration,
        "scenes": scenes,
        "social_title": social_title,
        "social_caption": social_caption,
        "hashtags": hashtags,
    }


def write_story(title: str, summary: str, article_text: str, source_url: str) -> dict:
    """Write one validated prime-time story. Raises ContentRejected / LLMUnavailableError."""
    title, summary, article_text = (title or "").strip(), (summary or "").strip(), (article_text or "").strip()
    if len(summary) + len(article_text) < MIN_SOURCE_CHARS:
        raise ContentRejected(
            "Source is too thin to answer What, When, Who, Where, Why and How from verified facts."
        )

    source_text = f"{title}\n{summary}\n{article_text}"
    story = generate_json(
        system_instruction=SYSTEM_INSTRUCTION,
        prompt=build_user_prompt(title, summary, article_text, source_url),
        response_model=Story,
        validate=lambda data: validate_story(data, source_text),
    )
    story["source"] = {"title": title, "url": source_url}
    return story


def save_story(story: dict, path: Path = STORY_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ----- anchor voiceover -----------------------------------------------------------------------

TTS_MODEL_DEFAULT = "gemini-3.8-flash-tts"
TTS_VOICE_DEFAULT = "Kore"
TTS_SAMPLE_RATE = 24000

ANCHOR_STYLE = (
    "Speak in Marathi as a seasoned, composed senior prime-time news anchor on a leading Marathi "
    "television channel. Crisp, precise Devanagari pronunciation of every word, including borrowed "
    "words that are written in Devanagari. Calm, authoritative and steady cadence at a measured "
    "broadcast pace, never rushed. Take a short natural breath at every comma and a slightly longer "
    "pause at every full stop. Neutral and serious in tone, with no theatrics, no excitement and no "
    "smiling voice. Open the first sentence with weight and gravity."
)


def _wav_from_pcm(pcm: bytes, sample_rate: int = TTS_SAMPLE_RATE) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return buffer.getvalue()


def _request_tts_audio(script: str) -> bytes:
    from google import genai  # imported lazily so script-only tests need no SDK

    api_key = get_env_value("GEMINI_API_KEY")
    if not api_key:
        raise LLMUnavailableError("GEMINI_API_KEY is not set; the Gemini voice cannot be used.")

    client = genai.Client(api_key=api_key)
    interaction = client.interactions.create(
        model=get_env_value("GEMINI_TTS_MODEL", TTS_MODEL_DEFAULT),
        input=[
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": script,
                        "annotations": [{"type": "speech_metadata", "style": ANCHOR_STYLE}],
                    }
                ],
            }
        ],
        response_format={"type": "audio"},
        generation_config={"speech_config": [{"voice": get_env_value("GEMINI_TTS_VOICE", TTS_VOICE_DEFAULT)}]},
    )
    audio = base64.b64decode(interaction.output_audio.data)
    # Unary responses are WAV (RIFF) at 24 kHz mono; wrap raw PCM defensively if headerless.
    return audio if audio[:4] == b"RIFF" else _wav_from_pcm(audio)


def synthesize_voiceover(script: str, out_path: Path = VOICEOVER_PATH, attempts: int = 3) -> Path:
    """Render ``script`` (the phonetic ``tts_narration_script``) to a WAV file."""
    problems = tts_problems(script)
    if problems:
        raise ValueError(problems[0])

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            wav = _request_tts_audio(script)
            if len(wav) < 4000:
                raise RuntimeError("TTS returned an empty or truncated audio file.")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(wav)
            print(f"🎙️ Voiceover written: {out_path} ({len(wav) // 1024} KB)")
            return out_path
        except LLMUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if is_auth_error(exc) or is_quota_error(exc):
                raise LLMUnavailableError(f"Gemini TTS unavailable: {exc}") from exc
            print(f"⚠️ TTS attempt {attempt}/{attempts} failed: {exc}")
            if attempt < attempts:
                time.sleep(3 * attempt)

    if last_error is not None and is_transient_error(last_error):
        raise LLMUnavailableError(f"Gemini TTS unavailable after {attempts} attempts: {last_error}")
    raise RuntimeError(f"Gemini TTS failed after {attempts} attempts: {last_error}")
