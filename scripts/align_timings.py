"""Word-level timing for the voiceover.

``faster-whisper`` (``small`` model, int8, CPU) transcribes ``voiceover.wav`` and returns timestamps
for the words it *heard*. Whisper's Marathi spelling often differs from the script, so its text is
never shown on screen. Instead its timestamps are fuzzy-aligned to the known words of
``tts_narration_script``: words that match get Whisper's exact times, words in between are
interpolated inside the gap. Captions and scene cuts therefore always use the clean script text.

Writes ``words`` (script word + start/end + scene), per-scene ``start``/``end`` and
``duration_seconds`` back into ``remotion/public/story.json``.
"""

from __future__ import annotations

import difflib
import json
import unicodedata
import wave
from dataclasses import dataclass
from pathlib import Path

from config import STORY_PATH, VOICEOVER_PATH

MATCH_THRESHOLD = 0.55
MIN_WORD_SECONDS = 0.06


@dataclass
class TimedWord:
    text: str
    start: float
    end: float


def audio_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / float(handle.getframerate())


def normalize_token(word: str) -> str:
    """Lower-case, NFC-normalise and strip punctuation, symbols and zero-width joiners."""
    word = unicodedata.normalize("NFC", word).lower()
    kept = [
        ch
        for ch in word
        if ch not in "‌‍" and not unicodedata.category(ch).startswith(("P", "S", "Z", "C"))
    ]
    return "".join(kept)


WHISPER_RATE = 16000


def load_audio_16k(path: Path):
    """Read a PCM WAV into the 16 kHz mono float32 array Whisper expects.

    Passing an array means faster-whisper never has to decode the file itself, which avoids its PyAV call
    (``av.open(..., metadata_errors=...)``) that crashes with some installed ``av`` versions."""
    import numpy as np

    with wave.open(str(path), "rb") as handle:
        channels, width, rate = handle.getnchannels(), handle.getsampwidth(), handle.getframerate()
        raw = handle.readframes(handle.getnframes())
    if width != 2:
        raise ValueError(f"Expected 16-bit PCM audio, got {width * 8}-bit.")
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if rate != WHISPER_RATE and len(samples) > 1:
        target = int(round(len(samples) * WHISPER_RATE / rate))
        samples = np.interp(np.linspace(0, len(samples) - 1, target), np.arange(len(samples)), samples).astype(np.float32)
    return samples


def transcribe_words(path: Path) -> list[TimedWord]:
    """Run faster-whisper (small, int8, CPU) and return the heard words with timestamps."""
    from faster_whisper import WhisperModel  # lazy: heavy import, not needed by unit tests

    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _info = model.transcribe(load_audio_16k(path), language="mr", word_timestamps=True, beam_size=5)
    words = []
    for segment in segments:
        for w in segment.words or []:
            text = w.word.strip()
            if text:
                words.append(TimedWord(text, float(w.start), float(w.end)))
    return words


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _anchors(script_norm: list[str], heard_norm: list[str]) -> list[tuple[int, int]]:
    """Order-preserving fuzzy matching (LCS weighted by similarity). Returns (script_i, heard_j)."""
    n, m = len(script_norm), len(heard_norm)
    sim = [[0.0] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            score = _similarity(script_norm[i], heard_norm[j])
            sim[i][j] = score if score >= MATCH_THRESHOLD else 0.0

    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best = max(dp[i - 1][j], dp[i][j - 1])
            if sim[i - 1][j - 1] > 0:
                best = max(best, dp[i - 1][j - 1] + sim[i - 1][j - 1])
            dp[i][j] = best

    pairs: list[tuple[int, int]] = []
    i, j = n, m
    while i > 0 and j > 0:
        if sim[i - 1][j - 1] > 0 and abs(dp[i][j] - (dp[i - 1][j - 1] + sim[i - 1][j - 1])) < 1e-9:
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return pairs


def _spread(words: list[str], start: float, end: float) -> list[tuple[float, float]]:
    """Share [start, end] between ``words`` in proportion to their length."""
    if not words:
        return []
    span = max(end - start, MIN_WORD_SECONDS * len(words))
    weights = [len(normalize_token(w)) + 1 for w in words]
    total = float(sum(weights))
    out, cursor = [], start
    for weight in weights:
        step = span * weight / total
        out.append((cursor, cursor + step))
        cursor += step
    return out


def align_script_to_audio(script_words: list[str], heard: list[TimedWord], duration: float) -> tuple[list[TimedWord], float]:
    """Give every script word a start/end. Returns (words, fraction_of_script_words_matched)."""
    n = len(script_words)
    if n == 0:
        return [], 0.0

    speech_start = heard[0].start if heard else 0.0
    last_heard_end = heard[-1].end if heard else duration
    speech_end = min(duration, max(last_heard_end, duration - 0.25))

    pairs = _anchors(
        [normalize_token(w) for w in script_words],
        [normalize_token(h.text) for h in heard],
    )

    times: list[tuple[float, float] | None] = [None] * n
    for i, j in pairs:
        times[i] = (heard[j].start, max(heard[j].end, heard[j].start + MIN_WORD_SECONDS))

    # Interpolate every run of unmatched words between its neighbouring anchors.
    i = 0
    while i < n:
        if times[i] is not None:
            i += 1
            continue
        run_start = i
        while i < n and times[i] is None:
            i += 1
        left = times[run_start - 1][1] if run_start > 0 else speech_start
        right = times[i][0] if i < n else speech_end
        for offset, span in enumerate(_spread(script_words[run_start:i], left, right)):
            times[run_start + offset] = span

    # Enforce strictly ordered, non-overlapping times inside [0, duration].
    out: list[TimedWord] = []
    cursor = 0.0
    for word, span in zip(script_words, times):
        start = min(max(span[0], cursor), duration)
        end = min(max(span[1], start + MIN_WORD_SECONDS), duration)
        out.append(TimedWord(word, round(start, 3), round(end, 3)))
        cursor = start
    for k in range(len(out) - 1):  # a word never ends after the next one starts
        if out[k].end > out[k + 1].start:
            out[k].end = max(out[k].start, out[k + 1].start)

    return out, len(pairs) / n


def build_story_timings(story: dict, heard: list[TimedWord], duration: float) -> dict:
    """Return ``story`` with ``words``, per-scene ``start``/``end`` and ``duration_seconds``."""
    script_words = story["tts_narration_script"].split()
    counts = [len(s["tts_text"].split()) for s in story["scenes"]]
    if sum(counts) != len(script_words):
        raise ValueError("Scene speech texts do not add up to tts_narration_script; refusing to align.")

    timed, matched = align_script_to_audio(script_words, heard, duration)

    words, scene_first_index, cursor = [], [], 0
    for scene_idx, count in enumerate(counts):
        scene_first_index.append(cursor)
        for _ in range(count):
            w = timed[cursor]
            words.append({"text": w.text, "start": w.start, "end": w.end, "scene": scene_idx})
            cursor += 1

    scenes = []
    for idx, scene in enumerate(story["scenes"]):
        start = 0.0 if idx == 0 else words[scene_first_index[idx]]["start"]
        end = duration if idx == len(story["scenes"]) - 1 else words[scene_first_index[idx + 1]]["start"]
        scenes.append({**scene, "start": round(start, 3), "end": round(end, 3)})

    return {**story, "scenes": scenes, "words": words, "duration_seconds": round(duration, 3), "alignment_match": round(matched, 3)}


# Voiceless fallback: pace of a calm prime-time anchor, used only when no voiceover could be generated.
WORDS_PER_SECOND = 2.4
COMMA_PAUSE_SECONDS = 0.18
STOP_PAUSE_SECONDS = 0.40
MIN_VOICELESS_SECONDS = 15.0


def estimate_duration(script: str) -> float:
    """Estimated reading time of ``script`` at anchor pace (words plus breaths at commas and full stops)."""
    seconds = len(script.split()) / WORDS_PER_SECOND + script.count(",") * COMMA_PAUSE_SECONDS + script.count(".") * STOP_PAUSE_SECONDS
    return max(MIN_VOICELESS_SECONDS, round(seconds + 0.6, 2))


def main_voiceless(story_path: Path = STORY_PATH) -> dict:
    """Time captions and scene cuts from the script alone and mark the story ``audio: false``.

    Every other element of the reel (studio, cards, karaoke captions, SFX, bed) renders exactly as usual."""
    story = json.loads(story_path.read_text(encoding="utf-8"))
    duration = estimate_duration(story["tts_narration_script"])
    updated = build_story_timings(story, [], duration)
    updated["audio"] = False
    story_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"🔇 Voiceless story: {len(updated['words'])} words timed over an estimated {duration:.1f}s")
    return updated


def main(story_path: Path = STORY_PATH, audio_path: Path = VOICEOVER_PATH) -> dict:
    story = json.loads(story_path.read_text(encoding="utf-8"))
    duration = audio_duration(audio_path)

    try:
        heard = transcribe_words(audio_path)
    except Exception as exc:  # noqa: BLE001 - captions can still be timed proportionally
        print(f"⚠️ faster-whisper failed ({exc}); falling back to proportional timing.")
        heard = []

    updated = build_story_timings(story, heard, duration)
    updated["audio"] = True
    story_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"⏱️ Aligned {len(updated['words'])} words over {duration:.2f}s "
        f"({updated['alignment_match']:.0%} matched to Whisper)"
    )
    return updated


if __name__ == "__main__":
    main()
