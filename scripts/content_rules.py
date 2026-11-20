"""Owner's content rules (one place, used by every pipeline).

1. Savarkar is written plainly: "सावरकर", never "स्वातंत्र्यवीर सावरकर" / "वीर सावरकर" (``plain_names``). It is applied to
   every string a model returns (``llm_providers.generate_json``), to approved draft files and to every spoken/on-screen text.
2. Quizzes never ask about, or show as an option, Savarkar, the RSS or Godse (``blocked_in_quiz``), and the topic bank
   never offers them as a topic (``blocked_topic``).
3. News (reels, bulletin) whose headline or summary names Savarkar is skipped (``skip_news``); set ``SAVARKAR_NEWS=plain``
   to publish such news with the plain name instead.
"""

from __future__ import annotations

import os
import re

_HONORIFICS = r"(?:स्वातंत्र्यवीर|स्वातंत्र्य\s*वीर|वीर|क्रांतिवीर|तात्याराव|Swatantrya\s*Veer|Swatantryaveer|Veer)"
_NAME = r"(?:विनायक\s+दामोदर\s+)?(?:सावरकर|Savarkar)"
_HONORIFIC_BEFORE = re.compile(rf"{_HONORIFICS}\s+({_NAME})", re.IGNORECASE)
_STANDALONE = re.compile(r"स्वातंत्र्य\s*वीर")

# Savarkar, the RSS and Godse, and the organisations tied to them. Latin words match whole words only.
_BLOCKED_DEVANAGARI = [
    "सावरकर", "गोडसे", "नथुराम", "नाथूराम", "आरएसएस", "आर एस एस", "आर.एस.एस", "राष्ट्रीय स्वयंसेवक", "स्वयंसेवक संघ",
    "अभिनव भारत", "मित्रमेळा", "हिंदू महासभा", "हिंदुमहासभा",
]
_BLOCKED_LATIN = re.compile(r"\b(?:savarkar|godse|godase|nathuram|rss|r\.s\.s|abhinav\s+bharat|hindu\s+mahasabha)\b", re.IGNORECASE)


def plain_names(text: str) -> str:
    """Remove honorifics in front of Savarkar's name (and a lone "स्वातंत्र्यवीर")."""
    if not text or ("वीर" not in text and "eer" not in text.lower()):
        return text
    text = _HONORIFIC_BEFORE.sub(r"\1", text)
    return _STANDALONE.sub("सावरकर", text)


def plain_names_deep(value):
    """``plain_names`` on every string of a nested dict/list (a model reply)."""
    if isinstance(value, str):
        return plain_names(value)
    if isinstance(value, list):
        return [plain_names_deep(v) for v in value]
    if isinstance(value, dict):
        return {k: plain_names_deep(v) for k, v in value.items()}
    return value


def blocked_term(text: str) -> str | None:
    """The first blocked name found in ``text`` (compared without spaces for the Devanagari ones), else None."""
    raw = str(text or "")
    squashed = re.sub(r"\s+", "", raw)
    for term in _BLOCKED_DEVANAGARI:
        if re.sub(r"\s+", "", term) in squashed:
            return term
    found = _BLOCKED_LATIN.search(raw)
    return found.group(0) if found else None


def blocked_in_quiz(*parts: str) -> str | None:
    return blocked_term(" ".join(str(p or "") for p in parts))


def blocked_topic(title: str) -> bool:
    return blocked_term(title) is not None


def mentions_savarkar(text: str) -> bool:
    return "सावरकर" in str(text or "") or "savarkar" in str(text or "").lower()


def skip_news(title: str, summary: str = "") -> bool:
    """True when this news item must not be made into a video."""
    if os.getenv("SAVARKAR_NEWS", "skip").strip().lower() == "plain":
        return False
    return mentions_savarkar(f"{title}\n{summary}")
