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


# ---- chart scenes, style packs, loops, thumbnail swap ----

import pytest  # noqa: E402

import drafts  # noqa: E402
import explainer  # noqa: E402
import thumb_ab  # noqa: E402
from test_longform import SOURCE, good_explainer, good_scene  # noqa: E402


def test_chart_scene_needs_figures_in_the_source():
    data = good_explainer()
    items = [{"label": "मंजूर निधी", "value": "₹१,२०० कोटी", "cue": "योजना"}, {"label": "पूर्वीचा निधी", "value": "₹१,२०० कोटी", "cue": "गळती"}]
    data["scenes"][1] = good_scene("chart", items)
    assert explainer.validate_explainer(data, SOURCE)["scenes"][1]["kind"] == "chart"
    data["scenes"][1] = good_scene("chart", [{**items[0]}, {"label": "दुसरे", "value": "खूप", "cue": "गळती"}])
    with pytest.raises(ValueError, match="figure"):
        explainer.validate_explainer(data, SOURCE)
    data["scenes"][1] = good_scene("chart", [{**items[0]}, {"label": "दुसरे", "value": "₹९९९ कोटी", "cue": "गळती"}])
    with pytest.raises(ValueError, match="not in the source"):
        explainer.validate_explainer(data, SOURCE)


def test_chart_scene_in_a_hand_written_script():
    text = """
TITLE: माझी स्वतःची पुणे पाणी योजना माहिती
=== SCENE 1 | title ===
HEADLINE: पुण्याची नवी पाणी योजना
SPEECH: पुणे महापालिकेने 1200 कोटी रुपयांची पाणी योजना मंजूर केली आहे.
=== SCENE 2 | chart ===
HEADLINE: निधी तुलना
SPEECH: मंजूर निधी 1200 कोटी आणि पूर्वीचा निधी 800 कोटी होता.
ITEMS:
- मंजूर निधी | ₹1200 कोटी | मंजूर
- पूर्वीचा निधी | ₹800 कोटी | पूर्वीचा
"""
    assert drafts.parse_explainer(text)["scenes"][1]["kind"] == "chart"
    with pytest.raises(Exception):
        drafts.parse_explainer(text.replace("₹800 कोटी", "कमी"))


def test_pack_and_loop(tmp_path):
    assert longform.pick_pack("explainer") == "knowledge" and longform.pick_pack("quiz") == "quiz"
    assert longform.pick_loop("x", tmp_path) is None
    (tmp_path / "b.mp4").write_bytes(b"0")
    (tmp_path / "a.mp4").write_bytes(b"0")
    assert longform.pick_loop("x", tmp_path) in ("loops/a.mp4", "loops/b.mp4")
    assert longform.pick_loop("x", tmp_path) == longform.pick_loop("x", tmp_path)
    props = longform.assemble("quiz", "t", [{"seconds": 5.0}], 3)
    assert props["pack"] == "quiz" and "loop" in props


def test_thumb_swap_rotates_and_parses_video_ids(tmp_path):
    files = [tmp_path / f"long-explainer-{s}.jpg" for s in ("bold", "figure", "question")]
    for f in files:
        f.write_bytes(b"x")
    found = thumb_ab.variants("long-explainer", tmp_path)
    assert [p.name for p in found] == sorted(p.name for p in files)
    assert thumb_ab.next_variant(found, found[0].name) == found[1]
    assert thumb_ab.next_variant(found, found[-1].name) == found[0]
    assert thumb_ab.next_variant(found, None) == found[0] and thumb_ab.next_variant([], None) is None
    for ref in ("abc123", "https://youtu.be/abc123", "https://www.youtube.com/watch?v=abc123&t=5"):
        assert thumb_ab.video_ref(ref) == "https://www.youtube.com/watch?v=abc123"
