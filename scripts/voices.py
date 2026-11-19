"""Voice roles for the long videos: the same Gemini TTS, a different voice and delivery per job.

    explainer   warm, measured presenter that explains (voice: GEMINI_TTS_VOICE, default Kore)
    quote       a different, deeper voice for a quoted statement (QUOTE_TTS_VOICE, default Charon)
    quiz_read   friendly quiz host reading a question and its options clearly (QUIZ_TTS_VOICE, default Puck)
    quiz_cheer  the same host, livelier: intro, the reveal of the answer, the closing (same voice)

News reels and bulletins keep the plain anchor. Voices and styles are overridable with environment variables
(EXPLAINER_TTS_VOICE, QUOTE_TTS_VOICE, QUIZ_TTS_VOICE and EXPLAINER_TTS_STYLE, QUOTE_TTS_STYLE, QUIZ_READ_TTS_STYLE,
QUIZ_CHEER_TTS_STYLE). Run ``python scripts/voice_samples.py`` and listen before changing a voice: how a voice sounds
in Marathi can only be judged by ear. The style text is an instruction to the model, never spoken.
"""

from __future__ import annotations

from config import get_env_value

DEFAULT_VOICES = {"explainer": "", "quote": "Charon", "quiz_read": "Puck", "quiz_cheer": "Puck"}
ENV_VOICE = {"explainer": "EXPLAINER_TTS_VOICE", "quote": "QUOTE_TTS_VOICE", "quiz_read": "QUIZ_TTS_VOICE", "quiz_cheer": "QUIZ_TTS_VOICE"}
ENV_STYLE = {"explainer": "EXPLAINER_TTS_STYLE", "quote": "QUOTE_TTS_STYLE", "quiz_read": "QUIZ_READ_TTS_STYLE", "quiz_cheer": "QUIZ_CHEER_TTS_STYLE"}

STYLES = {
    "explainer": (
        "Speak in clear, natural Marathi as a warm, trustworthy presenter on a leading Marathi news channel who is explaining "
        "a story to a curious viewer. Measured pace, slightly slower than a bulletin. Lean on key names and figures, pause "
        "briefly at commas and between sentences, lift the voice gently on the first sentence of a topic. Calm, no theatrics."
    ),
    "quote": (
        "Speak in clear Marathi. Read this as a short statement by a public figure being quoted: a firm, serious, slightly "
        "deeper and more personal delivery than a newsreader, steady pace, no drama."
    ),
    "quiz_read": (
        "Speak in clear, natural Marathi as a friendly, confident quiz host reading a question to the audience. Medium "
        "pace, very clear diction, a short pause after the question and between the four options, the same even tone for each option."
    ),
    "quiz_cheer": (
        "Speak in clear, natural Marathi as a warm, upbeat quiz host: lively and encouraging but never shouting, a little "
        "faster than a newsreader, a smile in the voice. For an answer: confident and satisfying."
    ),
}

SCENE_ROLE = {"quote": "quote", "question": "quiz_read", "answer": "quiz_cheer", "quiz_intro": "quiz_cheer", "quiz_end": "quiz_cheer"}


def role_for_scene(kind: str) -> str:
    return SCENE_ROLE.get(kind, "explainer")


def role_kwargs(role: str) -> dict:
    """``voice`` (None = the default Gemini voice) and ``style`` for ``synthesize_voiceover``."""
    voice = (get_env_value(ENV_VOICE[role]) or DEFAULT_VOICES[role]).strip() or None
    style = (get_env_value(ENV_STYLE[role]) or STYLES[role]).strip()
    return {"voice": voice, "style": style}
