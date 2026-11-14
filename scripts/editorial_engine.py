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

import requests
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

STYLE_PREFIX = (
    "Say as a composed, authoritative senior prime-time Marathi news anchor, at a measured pace, "
    "with a short breath at every comma and a longer pause at every full stop:"
)


def discover_tts_models() -> list[str]:
    """Ask Google which TTS models THIS API key can see (model ids containing "tts")."""
    api_key = get_env_value("GEMINI_API_KEY")
    if not api_key:
        return []
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


def _tts_interactions(model: str, script: str, voice: str, api_key: str) -> bytes:
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
                        "annotations": [{"type": "speech_metadata", "style": ANCHOR_STYLE}],
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


def _tts_generate_content(model: str, script: str, voice: str, api_key: str) -> bytes:
    """Route 2: classic generateContent TTS over plain REST (the 2.5 and 3.1 flash TTS models)."""
    body = {
        "contents": [{"parts": [{"text": f"{STYLE_PREFIX}\n\n{script}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    resp = requests.post(
        f"{API_BASE}/models/{model}:generateContent",
        headers={"x-goog-api-key": api_key},
        json=body,
        timeout=180,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        inline = resp.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
        pcm = base64.b64decode(inline["data"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError(f"unexpected generateContent response: {resp.text[:160]}") from exc
    rate = re.search(r"rate=(\d+)", str(inline.get("mimeType", "")))
    return _wav_from_pcm(pcm, int(rate.group(1)) if rate else TTS_SAMPLE_RATE)


def _request_tts_audio(script: str, model: str) -> bytes:
    """Try both call routes for one model. Quota, key and transient errors are left to the caller."""
    api_key = get_env_value("GEMINI_API_KEY")
    if not api_key:
        raise LLMUnavailableError("GEMINI_API_KEY is not set; the Gemini voice cannot be used.")
    voice = get_env_value("GEMINI_TTS_VOICE", TTS_VOICE_DEFAULT)

    errors = []
    for name, route in (("interactions", _tts_interactions), ("generateContent", _tts_generate_content)):
        try:
            return route(model, script, voice, api_key)
        except Exception as exc:  # noqa: BLE001
            if _is_bad_key(exc) or is_quota_error(exc) or is_transient_error(exc):
                raise
            errors.append(f"{name}: {type(exc).__name__}: {str(exc)[:120]}")
    raise RuntimeError(" | ".join(errors))


def synthesize_voiceover(script: str, out_path: Path = VOICEOVER_PATH, attempts: int = TTS_ATTEMPTS_PER_MODEL) -> Path:
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

    for model in chain:
        for attempt in range(1, attempts + 1):
            try:
                wav = _request_tts_audio(script, model)
                if len(wav) < 4000:
                    raise RuntimeError("TTS returned an empty or truncated audio file.")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(wav)
                print(f"✅ Voiceover written by {model}: {out_path} ({len(wav) // 1024} KB)")
                return out_path
            except LLMUnavailableError:
                raise
            except Exception as exc:  # noqa: BLE001
                if _is_bad_key(exc):
                    raise LLMUnavailableError(f"Gemini API key rejected: {exc}") from exc
                message = f"{type(exc).__name__}: {str(exc)[:200]}"
                print(f"⚠️ TTS {model} attempt {attempt}/{attempts} failed: {message}")
                if is_transient_error(exc) and attempt < attempts:
                    time.sleep(3 * attempt)
                    continue
                errors.append(f"{model}: {message}")
                break  # quota, missing model or request error: try the next model

    raise LLMUnavailableError(
        f"No Gemini TTS model worked (google-genai {_sdk_version()}). " + " | ".join(errors)
    )
