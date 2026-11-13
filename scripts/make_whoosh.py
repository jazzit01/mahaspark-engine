"""Generate ``remotion/public/whoosh.wav``: a short broadcast transition sweep.

The repository ships the generated file; run this script only to regenerate or retune it:
    python scripts/make_whoosh.py
"""

from __future__ import annotations

import wave

import numpy as np

from config import PUBLIC_DIR

SAMPLE_RATE = 44100
DURATION = 0.55


def build_whoosh(seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(SAMPLE_RATE * DURATION)
    t = np.linspace(0.0, 1.0, n, endpoint=False)

    noise = rng.standard_normal(n)

    # Band-pass the noise with a centre frequency that sweeps upward, via a moving-average
    # difference (cheap, deterministic and good enough for a transition sweep).
    low = np.convolve(noise, np.ones(48) / 48, mode="same")
    high = np.convolve(noise, np.ones(6) / 6, mode="same")
    sweep = (1 - t) * low + t * (high - low)

    # Rising tone under the noise gives the sweep a clear direction.
    freq = 180.0 + 1400.0 * t**2
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    tone = 0.25 * np.sin(phase)

    # Fast swell in, slightly slower fall out.
    envelope = np.sin(np.pi * np.clip(t, 0, 1) ** 0.7) ** 2
    signal = (sweep * 0.9 + tone) * envelope

    peak = float(np.max(np.abs(signal))) or 1.0
    return signal / peak * 0.8


def main() -> None:
    audio = build_whoosh()
    pcm = (audio * 32767).astype("<i2")
    out = PUBLIC_DIR / "whoosh.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())
    print(f"Wrote {out} ({DURATION:.2f}s)")


if __name__ == "__main__":
    main()
