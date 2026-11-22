"""Maharashtra map pins (geo.py) and the Shorts clip picker (shorts.py)."""

import geo
import shorts
import topic_bank


def scene(kind, seconds, start):
    return {"kind": kind, "seconds": seconds, "start": start}


def props(kind, kinds_seconds):
    scenes, cursor = [], 0.0
    for k, sec in kinds_seconds:
        scenes.append(scene(k, sec, cursor))
        cursor += sec
    return {"kind": kind, "scenes": scenes}


def test_pin_for_title_url_and_key():
    assert geo.pin_for("Raigad Fort")["label"] == "रायगड"
    assert geo.pin_for("https://en.wikipedia.org/wiki/Raigad_Fort")["label"] == "रायगड"
    assert geo.pin_for("https://en.wikipedia.org/wiki/Siddhivinayak_Temple,_Mumbai")["label"] == "सिद्धिविनायक"
    assert geo.pin_for("Photosynthesis") is None
    assert geo.pin_for("") is None


def test_pins_lie_inside_the_map_frame():
    for title, (lat, lon, label) in geo.PLACES.items():
        assert 15.4 <= lat <= 22.3 and 72.4 <= lon <= 81.2, title
        assert label.strip()


def test_places_are_topics_of_the_bank():
    bank = {t.lower() for _, _, t in topic_bank.BANK}
    assert set(geo.PLACES) <= bank


def test_attach_map_only_for_places():
    assert "map" in geo.attach_map({}, "https://en.wikipedia.org/wiki/Sinhagad")
    assert "map" not in geo.attach_map({}, "https://en.wikipedia.org/wiki/Gravity")


def test_explainer_clip_prefers_the_hook_and_fits_the_window():
    p = props("explainer", [("title", 9), ("points", 14), ("stat", 12), ("compare", 15), ("timeline", 16), ("summary", 12)])
    clip = shorts.pick_clip(p)
    assert clip and clip["first"] == 0
    assert shorts.MIN_SECONDS <= clip["end"] - clip["start"] <= shorts.MAX_SECONDS


def test_quiz_clip_starts_on_a_question_and_ends_on_its_answer():
    p = props("quiz", [("quiz_intro", 8)] + [(k, s) for _ in range(5) for k, s in (("question", 17), ("answer", 9))] + [("quiz_end", 8)])
    clip = shorts.pick_clip(p)
    assert clip
    assert p["scenes"][clip["first"]]["kind"] == "question" and p["scenes"][clip["last"]]["kind"] == "answer"
    assert shorts.MIN_SECONDS <= clip["end"] - clip["start"] <= shorts.MAX_SECONDS


def test_no_clip_when_too_short_or_too_long():
    assert shorts.pick_clip(props("explainer", [("title", 8), ("points", 10)])) is None
    assert shorts.pick_clip(props("explainer", [("stat", 70)])) is None


def test_run_is_off_with_env(monkeypatch):
    monkeypatch.setenv("LONG_SHORTS", "0")
    assert shorts.run({"scenes": []}, "t", "l", send=False) is None


# ---- voice quota: wait out per-minute limits, resume with cached scene voices ----

import editorial_engine as ee  # noqa: E402
import longform  # noqa: E402
from llm_providers import LLMUnavailableError  # noqa: E402

GOOD = "हा एक चाचणी मजकूर आहे."


def _one_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k1")
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
    monkeypatch.setattr(ee, "discover_tts_models", lambda: [])
    monkeypatch.setattr(ee, "tts_model_chain", lambda d=None: ["m"])
    ee.reset_tts_state()


def test_quota_cooldown_reads_retry_delay_and_daily_limits():
    assert ee.quota_cooldown(RuntimeError('HTTP 429: {"retryDelay": "17s"}')) == 19.0
    assert ee.quota_cooldown(RuntimeError("HTTP 429: exceeded your current quota")) == ee.TTS_COOLDOWN_DEFAULT
    assert ee.quota_cooldown(RuntimeError("429 GenerateRequestsPerDayPerProjectPerModel-FreeTier")) is None
    assert ee.quota_cooldown(RuntimeError("429 quota metric ... limit: 0")) is None


def test_tts_waits_for_a_per_minute_limit_then_succeeds(monkeypatch, tmp_path):
    _one_model(monkeypatch)
    sleeps, calls = [], []
    monkeypatch.setattr(ee.time, "sleep", lambda s: sleeps.append(s))
    clock = {"t": 1000.0}
    monkeypatch.setattr(ee.time, "monotonic", lambda: clock["t"] + sum(sleeps))

    def fake(script, model, key=None):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("HTTP 429: You exceeded your current quota")
        return b"\0" * 5000

    monkeypatch.setattr(ee, "_request_tts_audio", fake)
    ee.allow_tts_wait(300)
    out = ee.synthesize_voiceover(GOOD, tmp_path / "v.wav")
    assert out.exists() and len(calls) == 2 and sleeps and sleeps[0] >= 60
    ee.reset_tts_state()


def test_tts_fails_fast_without_a_wait_budget(monkeypatch, tmp_path):
    _one_model(monkeypatch)
    monkeypatch.setattr(ee.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("slept")))
    monkeypatch.setattr(ee, "_request_tts_audio", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("HTTP 429: quota")))
    try:
        ee.synthesize_voiceover(GOOD, tmp_path / "v.wav")
        raise AssertionError("should fail")
    except LLMUnavailableError:
        pass


def test_scene_voice_is_reused_from_the_cache(tmp_path, monkeypatch):
    made = []

    def fake_tts(text, path, **kw):
        made.append(text)
        path.write_bytes(b"\0" * 5000)

    monkeypatch.setattr(longform.align_timings, "audio_duration", lambda p: 2.0)
    longform.voice_scene(GOOD, 0, fake_tts, tmp_path, "question")
    (tmp_path / "scene-0.wav").unlink()
    longform.voice_scene(GOOD, 0, fake_tts, tmp_path, "question")
    assert made == [GOOD] and (tmp_path / "scene-0.wav").exists()
