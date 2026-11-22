"""Live check of "office + name" claims in a script, against the web as it is TODAY.

A model writes from memory and the source; neither tells it who holds an office today (Eknath Shinde was once मुख्यमंत्री and
is now उपमुख्यमंत्री; after the next change of government that moves again). So every script is checked live:

1. ``extract`` finds claims like "मुख्यमंत्री एकनाथ शिंदे" / "Chief Minister Eknath Shinde" (a title directly before a name;
   "माजी", "तत्कालीन", "भावी", "former" in front mean the person is NOT claimed to hold it now and are skipped).
2. ``verify`` asks Gemini with Google Search grounding who holds each office today and keeps the verdict only when the
   answer is backed by web sources (``grounding_chunks``). Results are cached for ``OFFICE_CACHE_HOURS`` (default 12).
3. ``problems`` turns a verdict "former / wrong_office / never" into a repair message for the writer model.

If the live check cannot run (no key, no quota, no network) it returns nothing and the caller falls back to the small
static table in ``content_rules`` (which expires on its own). ``OFFICE_LIVE_CHECK=0`` turns the live check off.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import OUT_DIR

CACHE_FILE = OUT_DIR / "office_cache.json"
IST = timezone(timedelta(hours=5, minutes=30))
BAD_STATUSES = {"former", "wrong_office", "never"}

OFFICES_MR = [
    "उपमुख्यमंत्री", "उप मुख्यमंत्री", "मुख्यमंत्री", "उपपंतप्रधान", "पंतप्रधान", "उपराष्ट्रपती", "राष्ट्रपती", "राज्यपाल",
    "सरन्यायाधीश", "गृहमंत्री", "अर्थमंत्री", "परराष्ट्रमंत्री", "संरक्षणमंत्री", "विरोधी पक्षनेते",
]
OFFICES_EN = (
    r"Deputy\s+Chief\s+Minister|Deputy\s+CM|Dy\.?\s*CM|Chief\s+Minister|CM|Prime\s+Minister|President|Vice\s+President|Governor|"
    r"Home\s+Minister|Finance\s+Minister|Defence\s+Minister|External\s+Affairs\s+Minister|Leader\s+of\s+Opposition|Chief\s+Justice"
)

# words that follow a title but are not a person's name
_STOP = {
    "यांनी", "यांचे", "यांची", "यांचा", "यांना", "यांच्या", "यांच्याकडे", "यांच्यावर", "यांच्याशी", "यांनीही", "यांसह", "यांसमवेत",
    "हे", "ही", "म्हणाले", "म्हणून", "सांगितले", "ने", "चे", "ची", "च्या", "आणि", "व", "तसेच", "कार्यालय", "कार्यालयाने",
    "कार्यालयाकडून", "कार्यालयातर्फे", "पदी", "पद", "पदाचा", "परिषद", "बैठक", "निवास", "निवासस्थान", "सचिव", "सचिवालय", "यांच्यासह",
    "आज", "काल", "उद्या", "यावेळी", "या", "त्या", "ते", "तर", "मात्र", "पण", "की", "होते", "आहेत", "आहे", "असे", "अशी", "अशा",
}
_DEV = r"[ऀ-ॿ]"
_MR_PREFIX = r"(?<!माजी )(?<!तत्कालीन )(?<!भावी )(?<!" + _DEV + r")"
_MR = re.compile(
    _MR_PREFIX + r"(" + "|".join(sorted((re.escape(o) for o in OFFICES_MR), key=len, reverse=True)) + r")(?:\s+श्री\.?)?(?=\s+" + _DEV + ")"
)
_EN = re.compile(
    r"(?<!former )(?<!ex-)(?<!ex )(?<![A-Za-z])(" + OFFICES_EN + r")\s+((?:[A-Z][a-z]+\.?\s*){1,3})"
)


@dataclass(frozen=True)
class Claim:
    office: str
    name: str

    @property
    def text(self) -> str:
        return f"{self.office} {self.name}"


@dataclass
class Verdict:
    office: str
    name: str
    status: str  # current | former | wrong_office | never | unknown
    current_holder: str = ""
    note: str = ""
    sources: list = field(default_factory=list)


def _clean_name(raw: str) -> str:
    """The first one or two words after a title that look like a name (a trailing verb or particle ends the name)."""
    words = []
    for word in raw.split():
        bare = word.strip(".,;:!?\"'()")
        if not bare or bare in _STOP or bare in OFFICES_MR or (len(bare) < 3 and words):
            break
        words.append(bare)
        if len(words) == 2 or word != bare:  # two words, or punctuation right after the word, end the name
            break
    return " ".join(words)


def extract(text: str) -> list[Claim]:
    """Distinct (office, name) claims in ``text``."""
    raw = re.sub(r"\s+", " ", str(text or ""))
    found: dict = {}
    for match in _MR.finditer(raw):
        # the name is read from the words after the title (so the next title is not swallowed by this one)
        name = _clean_name(" ".join(raw[match.end():].split()[:4]))
        if name and name.split()[0] not in _STOP and not any(name.startswith(o) for o in OFFICES_MR):
            found[Claim(re.sub(r"\s+", "", match.group(1)), name)] = None
    for match in _EN.finditer(raw):
        name = " ".join(match.group(2).split()).strip(".")
        if name:
            found[Claim(re.sub(r"\s+", " ", match.group(1)), name)] = None
    return list(found)


def today() -> str:
    return datetime.now(IST).date().isoformat()


# ----- cache -------------------------------------------------------------------------------------------------------

_MEMORY: dict = {}


def reset_cache() -> None:
    _MEMORY.clear()


def _cache_hours() -> float:
    try:
        return float(os.getenv("OFFICE_CACHE_HOURS", "12"))
    except ValueError:
        return 12.0


def _load_file() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _remember(claim: Claim, verdict: Verdict) -> None:
    _MEMORY[claim] = (time.time(), verdict)
    data = _load_file()
    data[claim.text] = {"t": time.time(), "v": verdict.__dict__}
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _recall(claim: Claim) -> Verdict | None:
    limit = _cache_hours() * 3600
    hit = _MEMORY.get(claim)
    if hit and time.time() - hit[0] < limit:
        return hit[1]
    entry = _load_file().get(claim.text)
    if entry and time.time() - float(entry.get("t", 0)) < limit:
        try:
            return Verdict(**entry["v"])
        except TypeError:
            return None
    return None


# ----- live lookup -------------------------------------------------------------------------------------------------

def _build_prompt(claims: list[Claim], context: str, day: str) -> str:
    listing = json.dumps([{"office": c.office, "name": c.name} for c in claims], ensure_ascii=False)
    return (
        f"Today is {day} (India). Using Google Search, check each claim taken from a Marathi news script. A claim is an office "
        f"title directly in front of a person's name. Judge it as of TODAY, not from memory.\n"
        f"status: \"current\" = that person holds that office today; \"former\" = held it before but not today; "
        f"\"wrong_office\" = holds a different office today; \"never\" = never held it; \"unknown\" = no reliable evidence.\n"
        f"current_holder = who holds that office today (English name). The news is about India; if the office is a state office the "
        f"context text tells which state (Maharashtra if unclear).\n\nCONTEXT (news text):\n{context[:1200]}\n\nCLAIMS:\n{listing}\n\n"
        f"Reply with ONLY a JSON array, one object per claim, in the same order: "
        f'[{{"office": "", "name": "", "status": "", "current_holder": "", "note": ""}}]'
    )


def _grounded_sources(response) -> list[str]:
    urls: list[str] = []
    for candidate in getattr(response, "candidates", None) or []:
        meta = getattr(candidate, "grounding_metadata", None)
        for chunk in getattr(meta, "grounding_chunks", None) or []:
            web = getattr(chunk, "web", None)
            title = getattr(web, "title", None) or getattr(web, "uri", None)
            if title:
                urls.append(str(title))
    return list(dict.fromkeys(urls))


def _ask_grounded(prompt: str) -> tuple[str, list[str]] | None:
    """One Gemini call with Google Search grounding. Returns (text, source titles) or None when it cannot run."""
    import llm_providers as lp

    if lp.genai is None or lp.types is None:
        return None
    keys = lp.gemini_keys()
    if not keys:
        return None
    models = [m for m in lp.candidate_gemini_models() if "pro" not in m][:3] or lp.candidate_gemini_models()[:2]
    config = lp.types.GenerateContentConfig(tools=[lp.types.Tool(google_search=lp.types.GoogleSearch())], temperature=0.0)
    for model in models:
        for key in keys:
            try:
                response = lp.genai.Client(api_key=key).models.generate_content(model=model, contents=prompt, config=config)
                return response.text or "", _grounded_sources(response)
            except Exception as exc:  # noqa: BLE001
                print(f"⚠️ Office check ({model}): {type(exc).__name__}: {str(exc)[:140]}")
    return None


def verify(claims: list[Claim], context: str = "", day: str | None = None) -> list[Verdict] | None:
    """Live verdicts for ``claims``; None when the live check is off or could not run (the caller then uses its fallback)."""
    if not claims or os.getenv("OFFICE_LIVE_CHECK", "1") == "0":
        return None
    day = day or today()
    known = {c: _recall(c) for c in claims}
    todo = [c for c, v in known.items() if v is None]
    if todo:
        answer = _ask_grounded(_build_prompt(todo, context, day))
        if answer is None:
            return None if len(todo) == len(claims) else [known[c] or Verdict(c.office, c.name, "unknown") for c in claims]
        text, sources = answer
        try:
            from llm_providers import parse_json

            start, end = text.find("["), text.rfind("]")
            rows = json.loads(text[start : end + 1]) if start != -1 and end > start else parse_json(text)
            rows = rows if isinstance(rows, list) else [rows]
        except (ValueError, TypeError):
            print("⚠️ Office check: the answer was not JSON; skipped.")
            return None
        for claim, row in zip(todo, rows):
            status = str(row.get("status", "unknown")).strip().lower()
            if status not in BAD_STATUSES | {"current"}:
                status = "unknown"
            if status in BAD_STATUSES and not sources:
                status = "unknown"  # a verdict against the script must be backed by web sources
            verdict = Verdict(claim.office, claim.name, status, str(row.get("current_holder", "")).strip(), str(row.get("note", "")).strip()[:200], sources[:3])
            known[claim] = verdict
            _remember(claim, verdict)
    return [known[c] or Verdict(c.office, c.name, "unknown") for c in claims]


def problems(verdicts: list[Verdict] | None, day: str | None = None) -> list[str]:
    """Repair messages for the verdicts that contradict the script."""
    day = day or today()
    out = []
    for v in verdicts or []:
        if v.status in BAD_STATUSES:
            holder = f" The current {v.office} is {v.current_holder}." if v.current_holder else ""
            where = f" (web sources: {', '.join(v.sources)})" if v.sources else ""
            out.append(
                f"'{v.office} {v.name}' is not right as of {day} ({v.status.replace('_', ' ')}).{holder}{where} "
                f"Write the title and name exactly as the source states them, use 'माजी' only for a former holder, and never "
                f"state an office from memory."
            )
    return out


def check(text: str, context: str = "", day: str | None = None) -> tuple[bool, list[str]]:
    """(live_check_ran, repair messages). ``live_check_ran`` False = nothing was verified online."""
    claims = extract(text)
    if not claims:
        return True, []
    verdicts = verify(claims, context, day)
    if verdicts is None:
        return False, []
    return True, problems(verdicts, day)
