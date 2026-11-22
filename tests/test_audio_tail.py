import wave

import numpy as np

import audio_tail

SR = 24000
rng = np.random.default_rng(1)


def voiced(ms, amp=8000):
    t = np.arange(SR * ms // 1000) / SR
    return amp * np.sin(2 * np.pi * 140 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t))


def silence(ms):
    return np.zeros(SR * ms // 1000)


def write(path, *parts):
    pcm = np.concatenate(parts).astype("<i2")
    with wave.open(str(path), "wb") as h:
        h.setnchannels(1), h.setsampwidth(2), h.setframerate(SR)
        h.writeframes(pcm.tobytes())


def read(path):
    with wave.open(str(path), "rb") as h:
        return np.frombuffer(h.readframes(h.getnframes()), dtype="<i2")


SPEECH = [voiced(600), silence(120), voiced(500), silence(150), voiced(700)]


def test_noise_burst_after_the_last_word_is_removed_and_the_voice_is_untouched(tmp_path):
    p = tmp_path / "a.wav"
    burst = rng.standard_normal(SR * 160 // 1000) * 5000
    write(p, *SPEECH, silence(110), burst, silence(300))
    before = read(p)
    info = audio_tail.trim_tail(p)
    after = read(p)
    assert info["changed"] and info["artifact_ms"] >= 150
    speech_len = sum(len(x) for x in SPEECH)
    assert speech_len < len(after) <= speech_len + SR * 130 // 1000  # speech kept, only ~120 ms of room after it
    assert np.array_equal(after[: speech_len - 2000], before[: speech_len - 2000])  # voice samples unchanged
    assert abs(int(after[-1])) < 50  # faded out: no click at the end


def test_a_single_sample_click_is_removed(tmp_path):
    p = tmp_path / "b.wav"
    click = np.zeros(SR * 5 // 1000)
    click[:40] = 20000
    write(p, *SPEECH, silence(200), click, silence(300))
    assert audio_tail.trim_tail(p)["artifact_ms"] > 0


def test_a_real_short_last_word_is_kept(tmp_path):
    p = tmp_path / "c.wav"
    write(p, voiced(600), silence(120), voiced(500), silence(100), voiced(260), silence(400))  # "आहे." after a gap
    before_len = len(read(p))
    info = audio_tail.trim_tail(p)
    assert info["artifact_ms"] == 0
    assert len(read(p)) > before_len - SR * 400 // 1000 + SR * 100 // 1000  # the last word is still there


def test_clean_clip_gets_only_a_fade_and_cleaning_twice_changes_nothing(tmp_path):
    p = tmp_path / "d.wav"
    write(p, *SPEECH, silence(500))
    assert audio_tail.trim_tail(p)["artifact_ms"] == 0
    once = read(p).copy()
    assert audio_tail.trim_tail(p)["changed"] is False
    assert np.array_equal(read(p), once)


def test_silent_or_tiny_files_are_left_alone(tmp_path):
    p = tmp_path / "e.wav"
    write(p, silence(2000))
    assert audio_tail.trim_tail(p)["changed"] is False
    q = tmp_path / "f.wav"
    write(q, voiced(200))
    assert audio_tail.trim_tail(q)["changed"] is False
    assert audio_tail.trim_tail(tmp_path / "missing.wav")["changed"] is False
