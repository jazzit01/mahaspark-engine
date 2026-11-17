"""Display-only number formatting for on-screen Marathi text.

The voice script (``tts_text``) spells every number out in words because the voice needs that. Viewers should read
numbers as Devanagari digits instead (``१२``, ``₹१,२००  कोटी``, ``८५%``). This module never touches ``tts_text``:

* ``dev_digits``       Latin digits to Devanagari digits (``27`` -> ``२७``).
* ``words_to_digits``  spelled-out numbers in on-screen text -> digits (safety net when the model writes words).
* ``caption_words``    the karaoke caption words of the spoken script, with spoken numbers merged into one digit
                       token that keeps the first word's start and the last word's end.

A number that cannot be parsed with certainty is left as words, so a wrong figure is never shown.
"""

from __future__ import annotations

import re

_UNITS = {
    "शून्य": 0, "एक": 1, "दोन": 2, "तीन": 3, "चार": 4, "पाच": 5, "सहा": 6, "सात": 7, "आठ": 8, "नऊ": 9,
    "दहा": 10, "अकरा": 11, "बारा": 12, "तेरा": 13, "चौदा": 14, "पंधरा": 15, "सोळा": 16, "सतरा": 17,
    "अठरा": 18, "एकोणीस": 19, "वीस": 20, "एकवीस": 21, "बावीस": 22, "तेवीस": 23, "चोवीस": 24,
    "पंचवीस": 25, "सव्वीस": 26, "सत्तावीस": 27, "सत्ताविस": 27, "अठ्ठावीस": 28, "अठ्ठाविस": 28,
    "एकोणतीस": 29, "तीस": 30, "एकतीस": 31, "बत्तीस": 32, "तेहेतीस": 33, "तेहतीस": 33, "चौतीस": 34,
    "पस्तीस": 35, "छत्तीस": 36, "सदतीस": 37, "अडतीस": 38, "एकोणचाळीस": 39, "चाळीस": 40,
    "एक्केचाळीस": 41, "बेचाळीस": 42, "त्रेचाळीस": 43, "चव्वेचाळीस": 44, "पंचेचाळीस": 45, "सेहेचाळीस": 46,
    "सत्तेचाळीस": 47, "अठ्ठेचाळीस": 48, "एकोणपन्नास": 49, "पन्नास": 50, "एक्कावन्न": 51, "बावन्न": 52,
    "त्रेपन्न": 53, "चोपन्न": 54, "पंचावन्न": 55, "छप्पन्न": 56, "सत्तावन्न": 57, "अठ्ठावन्न": 58,
    "एकोणसाठ": 59, "साठ": 60, "एकसष्ठ": 61, "बासष्ठ": 62, "त्रेसष्ठ": 63, "चौसष्ठ": 64, "पासष्ठ": 65,
    "सहासष्ठ": 66, "सदुसष्ठ": 67, "अडुसष्ठ": 68, "एकोणसत्तर": 69, "सत्तर": 70, "एक्काहत्तर": 71,
    "बाहत्तर": 72, "त्र्याहत्तर": 73, "चौऱ्याहत्तर": 74, "पंच्याहत्तर": 75, "शहात्तर": 76, "सत्त्याहत्तर": 77,
    "अठ्ठ्याहत्तर": 78, "एकोणऐंशी": 79, "ऐंशी": 80, "एक्क्याऐंशी": 81, "ब्याऐंशी": 82, "त्र्याऐंशी": 83,
    "चौऱ्याऐंशी": 84, "पंच्याऐंशी": 85, "शहाऐंशी": 86, "सत्त्याऐंशी": 87, "अठ्ठ्याऐंशी": 88,
    "एकोणनव्वद": 89, "नव्वद": 90, "एक्क्याण्णव": 91, "ब्याण्णव": 92, "त्र्याण्णव": 93, "चौऱ्याण्णव": 94,
    "पंच्याण्णव": 95, "शहाण्णव": 96, "सत्त्याण्णव": 97, "अठ्ठ्याण्णव": 98, "नव्व्याण्णव": 99,
}
_HUNDREDS = {
    "शंभर": 100, "एकशे": 100, "दोनशे": 200, "तीनशे": 300, "चारशे": 400, "पाचशे": 500, "सहाशे": 600, "सातशे": 700,
    "आठशे": 800, "नऊशे": 900,
}
_BIG = {"हजार": 1000}  # lakh and crore stay as unit words after the digits (५ लाख, १२ कोटी)
_TRAILING_UNITS = {"लाख", "कोटी"}
_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")
_LATIN_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_PUNCT = ".,;:!?\"'()"


def dev_digits(text: str) -> str:
    """Latin digits to Devanagari digits. Everything else (commas, %, ₹) is kept."""
    return str(text or "").translate(_DIGITS)


def _group(value: int) -> str:
    """Western thousands grouping for 1,000-1,999 and ordinary numbers; years are not grouped."""
    if 1900 <= value <= 2100:
        return str(value)
    return f"{value:,}"


def _split(token: str) -> tuple[str, str, str]:
    """(leading punctuation, core, trailing punctuation) of a caption token."""
    core = token.strip(_PUNCT)
    if not core:
        return token, "", ""
    start = token.index(core)
    return token[:start], core, token[start + len(core):]


def _value_of(run: list[str]) -> int | None:
    """Value of a run of number words (hundreds and thousands only), or None when it is not a clean number."""
    total, group, seen_big = 0, 0, False
    for word in run:
        if word in _BIG:
            if group == 0 and total == 0 and not seen_big:
                return None
            total += (group or 1) * _BIG[word]
            group, seen_big = 0, True
        elif word in _HUNDREDS:
            if group >= 100:
                return None
            group += _HUNDREDS[word]
        elif word in _UNITS:
            if group % 100:
                return None
            group += _UNITS[word]
        else:
            return None
    return total + group


def convert_tokens(tokens: list[str]) -> list[tuple[str, int, int]]:
    """Group ``tokens`` into display items ``(text, first_index, last_index)`` with spoken numbers as digits."""
    items: list[tuple[str, int, int]] = []
    i, n = 0, len(tokens)
    while i < n:
        lead, core, trail = _split(tokens[i])
        if core not in _UNITS and core not in _HUNDREDS and core not in _BIG:
            items.append((tokens[i], i, i))
            i += 1
            continue
        # collect a run of number words; punctuation inside the run breaks it
        j, run = i, []
        while j < n:
            l2, c2, t2 = _split(tokens[j])
            if c2 in _UNITS or c2 in _HUNDREDS or c2 in _BIG:
                run.append(c2)
                j += 1
                if t2 or l2:  # a comma or full stop ends the number
                    break
            else:
                break
        last = j - 1
        end_trail = _split(tokens[last])[2]
        value = _value_of(run)
        nxt = _split(tokens[j])[1] if j < n and not end_trail else ""
        # a lone "एक" is usually the word "one" in a sentence; only turn it into a digit before a unit
        bare_one = run == ["एक"] and nxt not in ({"टक्के", "रुपये"} | _TRAILING_UNITS | _BIG.keys())
        if value is None or bare_one or (len(run) == 1 and run[0] in _BIG):
            items.append((tokens[i], i, i))
            i += 1
            continue
        text = dev_digits(_group(value))
        consumed_to = last
        # percent and rupees
        if nxt in ("टक्के", "टक्का"):
            text += "%"
            consumed_to = j
            end_trail = _split(tokens[j])[2]
        elif nxt in _TRAILING_UNITS:
            text += " " + nxt
            consumed_to = j
            end_trail = _split(tokens[j])[2]
            if j + 1 < n and not end_trail and _split(tokens[j + 1])[1] == "रुपये":
                text = "₹" + text
                consumed_to = j + 1
                end_trail = _split(tokens[j + 1])[2]
        elif nxt == "रुपये":
            text = "₹" + text
            consumed_to = j
            end_trail = _split(tokens[j])[2]
        items.append((lead + text + end_trail, i, consumed_to))
        i = consumed_to + 1
    return items


def words_to_digits(text: str) -> str:
    """Safety net for on-screen text: spelled-out numbers become digits; existing digits become Devanagari."""
    tokens = str(text or "").split()
    return dev_digits(" ".join(t for t, _, _ in convert_tokens(tokens)))


def caption_words(words: list[dict]) -> list[dict]:
    """Karaoke words for the screen. Spoken numbers merge into one digit token spanning their timings."""
    tokens = [str(w.get("text", "")) for w in words]
    out: list[dict] = []
    for text, a, b in convert_tokens(tokens):
        first, last = words[a], words[b]
        out.append({**first, "text": text, "end": last["end"]})
    return out


# ----- digits -> spoken Marathi words (voice script) --------------------------------------------------
# The model is error-prone with Marathi numbers 11-99, so for the VOICE it writes plain digits and this code
# spells them out. ``numbers_to_words`` is deterministic and covers integers up to 99 crore, rupees, percent,
# halves (1.5 दीड, 2.5 अडीच, 3.5 साडेतीन) and other decimals ("पूर्णांक").

_CANON: dict[int, str] = {}
for _word, _value in _UNITS.items():
    _CANON.setdefault(_value, _word)  # the first spelling listed above is the canonical spoken one
_HUNDRED_WORDS = {1: "एकशे", 2: "दोनशे", 3: "तीनशे", 4: "चारशे", 5: "पाचशे", 6: "सहाशे", 7: "सातशे", 8: "आठशे", 9: "नऊशे"}
_MAX_SPOKEN = 99_99_99_999  # 99 crore and change; anything larger is left for the validator to reject
_NUM = r"\d[\d,]*"
_UNIT_WORD = r"(?:कोटी|लाख|हजार)"
_LATIN = str.maketrans("०१२३४५६७८९", "0123456789")


def int_to_words(n: int) -> str:
    """Standard spoken Marathi for 0 <= n <= 99 crore (35000 -> पस्तीस हजार)."""
    if n < 0 or n > _MAX_SPOKEN:
        raise ValueError(n)
    if n < 100:
        return _CANON[n]
    parts: list[str] = []
    crore, lakh, thousand = n // 10_000_000, (n // 100_000) % 100, (n // 1000) % 100
    hundred, rest = (n // 100) % 10, n % 100
    if crore:
        parts.append(f"{int_to_words(crore)} कोटी")
    if lakh:
        parts.append(f"{_CANON[lakh]} लाख")
    if thousand:
        parts.append(f"{_CANON[thousand]} हजार")
    if hundred:
        parts.append("शंभर" if hundred == 1 and rest == 0 else _HUNDRED_WORDS[hundred])
    if rest:
        parts.append(_CANON[rest])
    return " ".join(parts)


def _clean_int(text: str) -> int | None:
    digits = text.replace(",", "")
    return int(digits) if digits.isdigit() and int(digits) <= _MAX_SPOKEN else None


def _half(whole: int) -> str:
    return {0: "अर्धा", 1: "दीड", 2: "अडीच"}.get(whole) or f"साडे{int_to_words(whole)}"


def _decimal_words(whole: str, frac: str) -> str | None:
    w = _clean_int(whole)
    if w is None:
        return None
    if frac == "5":
        return _half(w)
    return f"{int_to_words(w)} पूर्णांक " + " ".join(_CANON[int(d)] for d in frac)


def numbers_to_words(text: str) -> str:
    """Spell every number in ``text`` as Marathi words: ₹ amounts, percent, decimals, dates and years included.
    Text without digits is returned unchanged. A number that cannot be spoken safely is left as digits so the
    validator rejects it (never a wrong word)."""
    s = str(text or "").translate(_LATIN)
    if not re.search(r"\d", s):
        return s

    def whole(m: re.Match) -> str:
        n = _clean_int(m.group(0))
        return int_to_words(n) if n is not None else m.group(0)

    # rupees: ₹1,200 कोटी  /  ₹35,000  /  ₹ 2.5 लाख
    def rupees(m: re.Match) -> str:
        amount, unit = m.group(1), m.group(2) or ""
        spoken = _amount_words(amount)
        return f"{spoken}{' ' + unit if unit else ''} रुपये" if spoken else m.group(0)

    def _amount_words(amount: str) -> str | None:
        if "." in amount:
            w, f = amount.split(".", 1)
            return _decimal_words(w, f)
        n = _clean_int(amount)
        return int_to_words(n) if n is not None else None

    s = re.sub(rf"₹\s*({_NUM}(?:\.\d+)?)(?:\s*({_UNIT_WORD}))?(?:\s*रुपये)?", rupees, s)
    s = re.sub(
        rf"({_NUM}(?:\.\d+)?)\s*%",
        lambda m: f"{_amount_words(m.group(1)) or m.group(1)} टक्के",
        s,
    )
    s = re.sub(rf"(?<![\d,.])(\d+)\.(\d+)(?!\d)", lambda m: _decimal_words(m.group(1), m.group(2)) or m.group(0), s)
    s = re.sub(rf"(?<![\d,])(?<!\d:){_NUM}(?<!,)(?!\d|:\d)", whole, s)  # times like 10:30 stay digits (rejected later)
    return re.sub(r"\s{2,}", " ", s)
