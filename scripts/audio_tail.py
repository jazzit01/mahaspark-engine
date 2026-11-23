"""Remove the noise burst Gemini TTS sometimes appends to the end of a voice clip.

Measured on a real 264 s quiz voice track: 14 clips ended with a burst of exactly 161 ms (peak 0 dBFS, about -6 dB RMS,
broadband hiss) that starts 200-400 ms of near-silence after the last word and is followed by digital silence. It is
the radio "chirr" heard after a spoken line. It is loud, so a "trim the quiet tail" cleaner never saw it.

Rule (deliberately narrow, so speech is never cut): the LAST loud stretch of the clip is removed only when it is
140-180 ms long, at least 150 ms of near-silence precedes it and the clip is silent after it.
"""
from __future__ import annotations

import io
import wave

import numpy as np

LOUD_DB = -20.0        # a millisecond counts as loud above this peak level
QUIET_DB = -45.0       # ... and as near-silence below this one
SILENT_DB = -80.0      # the clip must be this quiet right after the burst
JOIN_MS = 40           # loud stretches closer than this are one stretch
MIN_BURST_MS, MAX_BURST_MS = 140, 180
MIN_QUIET_BEFORE_MS = 150
FADE_MS = 5


def burst_start_ms(samples: np.ndarray, rate: int) -> int | None:
    """Millisecond at which a trailing noise burst starts, or None when the clip ends normally."""
    step = rate // 1000
    count = len(samples) // step
    if count < MIN_QUIET_BEFORE_MS + MIN_BURST_MS:
        return None
    peaks = 20 * np.log10(np.abs(samples[: count * step]).reshape(count, step).max(axis=1) + 1e-9)
    loud = np.where(peaks > LOUD_DB)[0]
    if not len(loud):
        return None
    end = int(loud[-1]) + 1                      # last loud millisecond + 1
    # walk back to the first loud ms of this stretch (gaps shorter than JOIN_MS belong to it)
    idx = int(np.searchsorted(loud, end - 1))
    first = int(loud[idx])
    for ms in loud[idx::-1]:
        if first - int(ms) > JOIN_MS:
            break
        first = int(ms)
    length = end - first
    if not (MIN_BURST_MS <= length <= MAX_BURST_MS):
        return None
    quiet = 0
    k = first - 1
    while k >= 0 and peaks[k] < QUIET_DB:
        quiet += 1
        k -= 1
    if quiet < MIN_QUIET_BEFORE_MS:
        return None
    after = peaks[end + JOIN_MS: end + JOIN_MS + 20]
    if len(after) and not (after < SILENT_DB).all():
        return None
    return first


def clean_wav_bytes(wav: bytes) -> tuple[bytes, int]:
    """Return (cleaned WAV bytes, ms removed). Anything not 16-bit PCM, or without a burst, comes back unchanged."""
    try:
        with wave.open(io.BytesIO(wav)) as src:
            channels, width, rate, frames = src.getnchannels(), src.getsampwidth(), src.getframerate(), src.readframes(src.getnframes())
    except (wave.Error, EOFError):
        return wav, 0
    if width != 2 or channels != 1:
        return wav, 0
    data = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    start_ms = burst_start_ms(data, rate)
    if start_ms is None:
        return wav, 0
    cut = start_ms * (rate // 1000)
    out = data[:cut].copy()
    fade = min(len(out), FADE_MS * (rate // 1000))
    if fade:
        out[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    removed_ms = int(round((len(data) - cut) * 1000 / rate))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as dst:
        dst.setnchannels(1)
        dst.setsampwidth(2)
        dst.setframerate(rate)
        dst.writeframes((np.clip(out, -1, 1) * 32767).astype("<i2").tobytes())
    return buffer.getvalue(), removed_ms
