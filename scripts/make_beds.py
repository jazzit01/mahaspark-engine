"""Generate the five background beds in ``remotion/public/bed/`` from scratch.

Every note is synthesised here (sine stacks, filtered noise), so the beds are original and cannot trigger a
copyright claim. The committed mp3 files are this script's output; run it only to regenerate or retune them:
    python scripts/make_beds.py            (needs ffmpeg on PATH)
Each bed is a seamless loop: pads wrap around the end and the loop length is a whole number of bars.
"""

from __future__ import annotations

import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from config import PUBLIC_DIR

SR = 44100
BED_DIR = PUBLIC_DIR / "bed"


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _add_wrapped(buf: np.ndarray, start: int, seg: np.ndarray) -> None:
    idx = (start + np.arange(len(seg))) % len(buf)
    np.add.at(buf, idx, seg)


def pad(buf: np.ndarray, start: int, length: int, notes: list[int], gain: float) -> None:
    """Soft detuned sine pad with a Hann window spanning two bars, so neighbouring chords cross-fade."""
    span = length * 2
    t = np.arange(span) / SR
    win = np.hanning(span)
    seg = np.zeros(span)
    for n in notes:
        for detune in (-0.07, 0.0, 0.07):
            f = hz(n) * 2 ** (detune / 12)
            seg += np.sin(2 * np.pi * f * t) + 0.28 * np.sin(2 * np.pi * 2 * f * t) + 0.08 * np.sin(2 * np.pi * 3 * f * t)
    _add_wrapped(buf, start - length // 2, seg * win * gain / (len(notes) * 3))


def pluck(buf: np.ndarray, start: int, midi: int, gain: float, decay: float = 5.0, length: float = 0.6) -> None:
    n = int(SR * length)
    t = np.arange(n) / SR
    f = hz(midi)
    seg = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)) * np.exp(-decay * t)
    seg *= np.minimum(1.0, t / 0.004)
    _add_wrapped(buf, start, seg * gain)


def thump(buf: np.ndarray, start: int, gain: float) -> None:
    n = int(SR * 0.35)
    t = np.arange(n) / SR
    f = 52 + 70 * np.exp(-t * 28)
    seg = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-9 * t)
    _add_wrapped(buf, start, seg * gain)


def tick(buf: np.ndarray, start: int, gain: float, rng: np.random.Generator) -> None:
    n = int(SR * 0.05)
    t = np.arange(n) / SR
    seg = rng.standard_normal(n) * np.exp(-90 * t)
    seg = np.convolve(seg, np.ones(5) / 5, mode="same")  # take the hiss off
    _add_wrapped(buf, start, seg * gain)


MOODS = {
    # name: (bpm, chords as MIDI note lists, style)
    "neutral": (72, [[57, 60, 64], [53, 57, 60], [48, 55, 60], [55, 59, 62]] * 2, "calm"),
    "upbeat": (104, [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]] * 2, "bright"),
    "serious": (60, [[50, 53, 57], [46, 50, 53], [43, 46, 50], [45, 49, 52]] * 2, "slow"),
    "breaking": (118, [[52, 55, 59], [52, 55, 59], [48, 52, 55], [47, 50, 54]] * 2, "pulse"),
    "crime": (76, [[48, 51, 55], [44, 48, 51], [46, 50, 53], [43, 47, 50]] * 2, "heart"),
}


def build_bed(name: str) -> np.ndarray:
    bpm, chords, style = MOODS[name]
    rng = np.random.default_rng(sum(map(ord, name)))
    beat = int(SR * 60 / bpm)
    bar = beat * 4
    buf = np.zeros(bar * len(chords))
    for i, notes in enumerate(chords):
        s = i * bar
        pad(buf, s, bar, notes, 1.0 if style != "bright" else 0.8)
        root = notes[0] - 12
        if style == "calm":
            for b in (0, 2):
                pluck(buf, s + b * beat, root, 0.35, decay=3.0, length=1.2)
            for k, n in enumerate(notes + [notes[1] + 12]):
                pluck(buf, s + (k * 2 + 1) * beat // 2 + beat * 2, n + 12, 0.12, decay=4.0)
        elif style == "bright":
            for k in range(8):
                pluck(buf, s + k * beat // 2, notes[k % 3] + 12, 0.22, decay=7.0, length=0.35)
            pluck(buf, s, root, 0.4, decay=3.0, length=1.0)
            pluck(buf, s + 2 * beat, root, 0.3, decay=3.0, length=1.0)
        elif style == "slow":
            pluck(buf, s, root - 12, 0.45, decay=1.1, length=3.5)
            pluck(buf, s + 2 * beat, notes[2], 0.1, decay=2.0, length=2.0)
        elif style == "pulse":
            for k in range(8):
                pluck(buf, s + k * beat // 2, root, 0.3 if k % 2 == 0 else 0.18, decay=11.0, length=0.3)
            tick(buf, s + beat * 2, 0.5, rng)
            for k in range(4):
                tick(buf, s + k * beat, 0.12, rng)
        else:  # heart
            for b in range(4):
                thump(buf, s + b * beat, 0.55)
                thump(buf, s + b * beat + beat // 3, 0.3)
            pluck(buf, s, root, 0.3, decay=1.8, length=2.0)
    peak = float(np.max(np.abs(buf))) or 1.0
    return buf / peak * 0.85


def write_mp3(audio: np.ndarray, path: Path) -> None:
    pcm = (audio * 32767).astype("<i2")
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "bed.wav"
        with wave.open(str(wav), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(SR)
            handle.writeframes(pcm.tobytes())
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ac", "2", "-b:a", "128k", str(path)],
            check=True,
        )


def main() -> None:
    BED_DIR.mkdir(parents=True, exist_ok=True)
    for name in MOODS:
        audio = build_bed(name)
        write_mp3(audio, BED_DIR / f"{name}.mp3")
        print(f"Wrote {BED_DIR / (name + '.mp3')} ({len(audio) / SR:.1f}s)")


if __name__ == "__main__":
    main()
