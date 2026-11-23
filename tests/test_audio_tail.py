import io
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audio_tail  # noqa: E402

RATE = 24000


def _wav(parts):
    data = np.concatenate(parts)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes((data * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def _speech(ms):
    t = np.arange(RATE * ms // 1000) / RATE
    return (0.6 * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t))).astype(np.float32)


def _quiet(ms):
    return np.full(RATE * ms // 1000, 0.0003, dtype=np.float32)


def _silence(ms):
    return np.zeros(RATE * ms // 1000, dtype=np.float32)


def _burst(ms):
    rng = np.random.default_rng(1)
    return np.clip(rng.normal(0, 0.5, RATE * ms // 1000), -1, 1).astype(np.float32)


def _frames(wav):
    with wave.open(io.BytesIO(wav)) as w:
        return w.getnframes()


def test_burst_after_gap_is_removed():
    wav = _wav([_speech(1000), _quiet(300), _burst(161), _silence(400)])
    out, removed = audio_tail.clean_wav_bytes(wav)
    assert removed >= 560
    assert _frames(out) * 1000 // RATE <= 1310


def test_normal_ending_is_untouched():
    wav = _wav([_speech(1000), _quiet(300), _silence(400)])
    assert audio_tail.clean_wav_bytes(wav) == (wav, 0)


def test_last_word_after_a_pause_is_kept():
    # a real final word (400 ms) after a pause is longer than a burst
    wav = _wav([_speech(1000), _quiet(300), _speech(400), _silence(400)])
    assert audio_tail.clean_wav_bytes(wav) == (wav, 0)


def test_short_final_sound_without_gap_is_kept():
    wav = _wav([_speech(1000), _burst(161), _silence(400)])
    assert audio_tail.clean_wav_bytes(wav) == (wav, 0)


def test_garbage_input_is_returned_unchanged():
    assert audio_tail.clean_wav_bytes(b"not a wav") == (b"not a wav", 0)
