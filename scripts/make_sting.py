"""Generate ``remotion/public/sting.wav``: the 1.4 s signature sound hit on the opening logo of every long video.

Original synthesis (no samples): a low sub swell, a bright two-note chime and a short airy tail. The repository ships
the generated file; run this script only to regenerate or retune it:
    python scripts/make_sting.py
"""

from __future__ import annotations

import wave

import numpy as np

from config import PUBLIC_DIR

SAMPLE_RATE = 44100
DURATION = 1.4


def build_sting(seed: int = 11) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(SAMPLE_RATE * DURATION)
    t = np.arange(n) / SAMPLE_RATE

    sub = np.sin(2 * np.pi * 55.0 * t) * np.exp(-t * 2.2) * (1 - np.exp(-t * 40))  # impact under the logo
    signal = 0.55 * sub

    for start, freq, gain in ((0.12, 880.0, 0.32), (0.30, 1318.5, 0.30)):  # A5 then E6 chime
        local = np.clip(t - start, 0, None)
        env = np.where(t >= start, np.exp(-local * 4.0) * (1 - np.exp(-local * 120)), 0.0)
        signal += gain * env * (np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 2.01 * t))

    air = np.convolve(rng.standard_normal(n), np.ones(5) / 5, mode="same")  # soft noise tail
    signal += 0.05 * air * np.exp(-t * 3.0) * (t > 0.05)

    signal *= np.minimum(1.0, (DURATION - t) / 0.25)  # fade out the last quarter second
    peak = float(np.max(np.abs(signal))) or 1.0
    return signal / peak * 0.8


def main() -> None:
    pcm = (build_sting() * 32767).astype("<i2")
    out = PUBLIC_DIR / "sting.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())
    print(f"Wrote {out} ({DURATION:.1f}s)")


if __name__ == "__main__":
    main()
