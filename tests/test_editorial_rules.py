import copy

import pytest

import editorial_engine as ee
from helpers import SOURCE_TEXT, valid_story
from llm_providers import ContentRejected


def validate(story):
    return ee.validate_story(story, SOURCE_TEXT)


def test_valid_story_passes_and_builds_dual_text():
    result = validate(valid_story())
    assert result["tts_narration_script"].startswith("पुणे महापालिकेने,")
    assert result["scenes"][1]["headline"] == "प्रकल्पासाठी 120 कोटींची तरतूद"  # sharp digits on screen
    assert len(result["tts_narration_script"].split()) == sum(len(s["tts_text"].split()) for s in result["scenes"])
    assert result["visual_theme"] == "PrimeGridStudio"


def test_rejected_story_raises_content_rejected():
    story = valid_story()
    story.update(approved=False, rejection_reason="Unverified rumour")
    with pytest.raises(ContentRejected, match="Unverified rumour"):
        validate(story)


@pytest.mark.parametrize("bad", ["120", "₹", "%", "A", "१२०", "-", "?", "!"])
def test_tts_text_rejects_digits_latin_and_symbols(bad):
    story = valid_story()
    story["scenes"][1]["tts_text"] = f"प्रकल्पासाठी, {bad} कोटी रुपयांची तरतूद करण्यात आली आहे."
    with pytest.raises(ValueError, match="tts_text|characters"):
        validate(story)


def test_forbidden_agency_cliche_is_rejected():
    story = valid_story()
    story["scenes"][2]["tts_text"] = "अधिकृत माहितीनुसार, काम पुढील महिन्यात सुरू होईल. नागरिक त्रस्त होते."
    with pytest.raises(ValueError, match="अधिकृत माहितीनुसार"):
        validate(story)


def test_headline_number_must_exist_in_source():
    story = valid_story()
    story["scenes"][1]["headline"] = "प्रकल्पासाठी 999 कोटींची तरतूद"
    with pytest.raises(ValueError, match="999"):
        validate(story)


def test_missing_five_w_one_h_field_is_rejected():
    story = valid_story()
    story["five_w_one_h"]["why"] = ""
    with pytest.raises(ValueError, match="why"):
        validate(story)


def test_overlong_hook_is_rejected():
    story = valid_story()
    story["scenes"][0]["tts_text"] = " ".join(["शब्द"] * 20) + "."
    with pytest.raises(ValueError, match="hook"):
        validate(story)


def test_unknown_theme_and_mood_fall_back_to_defaults():
    story = copy.deepcopy(valid_story())
    story["visual_theme"], story["audio_mood"] = "Nope", "weird"
    result = validate(story)
    assert (result["visual_theme"], result["audio_mood"]) == ("PrimeGridStudio", "neutral")


def test_clean_tts_text_fixes_spacing_and_end_stop():
    assert ee.clean_tts_text("पुणे ,  मेट्रो सुरू झाली") == "पुणे, मेट्रो सुरू झाली."
    assert ee.clean_tts_text("आज, बैठक झाली।") == "आज, बैठक झाली."


def test_thin_source_is_rejected_before_calling_any_model():
    with pytest.raises(ContentRejected):
        ee.write_story("शीर्षक", "थोडे", "", "")


def test_synthesize_voiceover_refuses_unsafe_script(tmp_path):
    with pytest.raises(ValueError):
        ee.synthesize_voiceover("आज 5 जण जखमी झाले.", tmp_path / "v.wav")


# ----- voiceover model chain ------------------------------------------------------------------

import wave  # noqa: E402

from llm_providers import LLMUnavailableError  # noqa: E402

GOOD_SCRIPT = "पुणे महापालिकेने, उड्डाणपुलाला मंजुरी दिली आहे."


def fake_wav(seconds=1.0):
    import io

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x01" * int(24000 * seconds))
    return buf.getvalue()


def test_missing_tts_model_falls_back_to_next_model(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_TTS_MODEL", raising=False)
    tried = []

    def fake(script, model):
        tried.append(model)
        if model == "gemini-3.8-flash-tts":
            raise RuntimeError("Error code: 404 - Model 'gemini-3.8-flash-tts' not found")
        return fake_wav()

    monkeypatch.setattr(ee, "_request_tts_audio", fake)
    out = ee.synthesize_voiceover(GOOD_SCRIPT, tmp_path / "v.wav")
    assert tried == ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"]  # no retries on a 404
    assert out.exists()


def test_all_tts_models_failing_requeues_instead_of_erroring(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_TTS_MODEL", raising=False)
    monkeypatch.setattr(ee, "_request_tts_audio", lambda s, m: (_ for _ in ()).throw(RuntimeError("404 not found")))
    with pytest.raises(LLMUnavailableError, match="stays queued"):
        ee.synthesize_voiceover(GOOD_SCRIPT, tmp_path / "v.wav")


def test_transient_tts_error_is_retried_on_same_model(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_TTS_MODEL", raising=False)
    monkeypatch.setattr(ee.time, "sleep", lambda _s: None)
    calls = []

    def fake(script, model):
        calls.append(model)
        if len(calls) == 1:
            raise RuntimeError("503 UNAVAILABLE overloaded")
        return fake_wav()

    monkeypatch.setattr(ee, "_request_tts_audio", fake)
    ee.synthesize_voiceover(GOOD_SCRIPT, tmp_path / "v.wav")
    assert calls == ["gemini-3.8-flash-tts", "gemini-3.8-flash-tts"]


def test_quota_or_auth_error_stops_the_chain(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_TTS_MODEL", raising=False)
    tried = []

    def fake(script, model):
        tried.append(model)
        raise RuntimeError("429 RESOURCE_EXHAUSTED quota")

    monkeypatch.setattr(ee, "_request_tts_audio", fake)
    with pytest.raises(LLMUnavailableError):
        ee.synthesize_voiceover(GOOD_SCRIPT, tmp_path / "v.wav")
    assert len(tried) == 1


def test_configured_tts_model_is_tried_first(monkeypatch):
    monkeypatch.setenv("GEMINI_TTS_MODEL", "my-model, gemini-3.8-flash-lite-tts")
    chain = ee.tts_model_chain()
    assert chain[:2] == ["my-model", "gemini-3.8-flash-lite-tts"]
    assert chain.count("gemini-3.8-flash-lite-tts") == 1 and "gemini-3.8-flash-tts" in chain


def test_25_tts_models_use_generate_content():
    assert ee._uses_generate_content("gemini-2.5-flash-preview-tts")
    assert not ee._uses_generate_content("gemini-3.8-flash-tts")
