"""Clean the END of a voice clip (WAV, 16-bit PCM).

Gemini TTS sometimes appends a tiny burst after the last word (a click or a radio-like "chirr"), and a clip that
stops on a non-zero sample clicks too. This module only touches the tail, never the voice itself:

1. find where the real speech ends;
2. drop a short, noisy or tiny burst that follows a gap after the last word;
3. cut the silence/noise after the speech (keeping ``PAD_MS`` of room) and fade the end out over ``FADE_MS``.

``trim_tail`` is idempotent, so a clip taken from the voice cache can be cleaned again safely. It never makes a
clip shorter than the speech it found, and leaves silent, empty or very short files alone.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

FRAME_MS = 10
GAP_MS = 50            # quiet this long = a break between words/sentences
MAX_ARTIFACT_MS = 350  # a trailing burst longer than this is treated as a real word
TINY_MS = 60           # no spoken word is this short: it is a click
PAD_MS = 120           # room kept after the last word
FADE_MS = 40
NOISE_ZCR = 0.20       # mean zero-crossing rate per sample: voiced speech is far lower, hiss/static far higher
MIN_CLIP_MS = 500
# Measured on real clips by the owner: the chirr starts about 470-480 ms after the speech ends. A short isolated
# segment in that window is an artifact unless it clearly is speech (strong AND low-pitched AND not tiny).
SIGNATURE_GAP_MS = (300, 700)
SPEECH_LEVEL = 0.30     # share of the clip's 95th-percentile level a real last word reaches
SPEECH_CENTROID_HZ = 1800.0
SPEECH_MIN_MS = 150


def _segments(active: np.ndarray, gap_frames: int) -> list[list[int]]:
    """[first, last] frame of each run of active frames; runs closer than ``gap_frames`` are merged."""
    runs: list[list[int]] = []
    start = None
    for i, on in enumerate(active):
        if on and start is None:
            start = i
        elif not on and start is not None:
            runs.append([start, i - 1])
            start = None
    if start is not None:
        runs.append([start, len(active) - 1])
    merged: list[list[int]] = []
    for run in runs:
        if merged and run[0] - merged[-1][1] - 1 < gap_frames:
            merged[-1][1] = run[1]
        else:
            merged.append(run)
    return merged


def _centroid_hz(seg: np.ndarray, rate: int) -> float:
    """Spectral centroid of a segment: voiced speech sits low (a few hundred Hz to ~1.5 kHz), a radio chirp/hiss high."""
    x = seg[:8192] * np.hanning(min(len(seg), 8192))
    spectrum = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(len(x), 1.0 / rate)
    total = float(spectrum.sum())
    return float((freqs * spectrum).sum() / total) if total > 0 else 0.0


def analyse(samples: np.ndarray, rate: int) -> dict:
    """Where speech ends and whether a trailing artifact follows it. ``samples``: int16, shape (n, channels)."""
    mono = np.abs(samples.astype(np.float32)).mean(axis=1)
    frame = max(1, rate * FRAME_MS // 1000)
    n_frames = len(mono) // frame
    if n_frames < MIN_CLIP_MS // FRAME_MS:
        return {"keep_to": len(mono), "artifact_ms": 0, "speech_found": False}
    rms = np.sqrt((mono[: n_frames * frame].reshape(n_frames, frame) ** 2).mean(axis=1))
    peak = float(np.percentile(rms, 95))
    if peak < 50:  # silence (or a voiceless test file)
        return {"keep_to": len(mono), "artifact_ms": 0, "speech_found": False}
    threshold = max(0.04 * peak, 30.0)
    segments = _segments(rms > threshold, GAP_MS // FRAME_MS)
    if not segments:
        return {"keep_to": len(mono), "artifact_ms": 0, "speech_found": False}

    artifact_ms = 0
    detail: dict = {}
    last = segments[-1]
    if len(segments) >= 2:
        previous = segments[-2]
        gap_ms = (last[0] - previous[1] - 1) * FRAME_MS
        length_ms = (last[1] - last[0] + 1) * FRAME_MS
        seg = samples[last[0] * frame:(last[1] + 1) * frame, 0].astype(np.float32)
        zcr = float((np.diff(np.signbit(seg).astype(np.int8)) != 0).mean()) if len(seg) > 1 else 0.0
        level = float(rms[last[0]:last[1] + 1].max()) / peak
        faint = level < 0.12
        centroid = _centroid_hz(seg, rate)
        in_window = SIGNATURE_GAP_MS[0] <= gap_ms <= SIGNATURE_GAP_MS[1]
        real_word = level >= SPEECH_LEVEL and centroid < SPEECH_CENTROID_HZ and length_ms >= SPEECH_MIN_MS
        old_rule = length_ms < TINY_MS or zcr > NOISE_ZCR or faint
        verdict = gap_ms >= GAP_MS and length_ms <= MAX_ARTIFACT_MS and (old_rule or (in_window and not real_word))
        detail = {"gap_ms": gap_ms, "length_ms": length_ms, "level": round(level, 2), "centroid_hz": round(centroid), "zcr": round(zcr, 2)}
        if verdict:
            artifact_ms = length_ms
            segments = segments[:-1]
    end_frame = segments[-1][1] + 1
    return {"keep_to": min(len(mono), end_frame * frame + rate * PAD_MS // 1000), "artifact_ms": artifact_ms, "speech_found": True, "tail": detail}


def trim_tail(path: Path) -> dict:
    """Clean the tail of the WAV at ``path`` in place. Returns {"trimmed_ms", "artifact_ms", "changed"}."""
    path = Path(path)
    try:
        with wave.open(str(path), "rb") as handle:
            channels, width, rate = handle.getnchannels(), handle.getsampwidth(), handle.getframerate()
            raw = handle.readframes(handle.getnframes())
    except (wave.Error, EOFError, OSError):
        return {"trimmed_ms": 0, "artifact_ms": 0, "changed": False}
    if width != 2 or not raw:
        return {"trimmed_ms": 0, "artifact_ms": 0, "changed": False}
    samples = np.frombuffer(raw, dtype="<i2").reshape(-1, channels)
    info = analyse(samples, rate)
    if not info["speech_found"]:
        return {"trimmed_ms": 0, "artifact_ms": 0, "changed": False}
    keep_to = int(info["keep_to"])
    out = samples[:keep_to].astype(np.float32)
    fade = min(len(out), max(1, rate * FADE_MS // 1000))
    out[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)[:, None]
    trimmed_ms = round((len(samples) - keep_to) * 1000 / rate)
    out_i16 = np.clip(np.round(out), -32768, 32767).astype("<i2")
    if np.array_equal(out_i16, samples):
        return {"trimmed_ms": 0, "artifact_ms": 0, "changed": False}
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(out_i16.tobytes())
    return {"trimmed_ms": trimmed_ms, "artifact_ms": info["artifact_ms"], "changed": True, "tail": info.get("tail", {})}
