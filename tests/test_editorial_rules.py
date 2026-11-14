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


@pytest.fixture(autouse=True)
def no_network_model_listing(monkeypatch):
    monkeypatch.setattr(ee, "discover_tts_models", lambda: [])


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
    with pytest.raises(LLMUnavailableError, match="No Gemini TTS model worked"):
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


def test_quota_on_one_model_moves_to_the_next_model(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_TTS_MODEL", raising=False)
    tried = []

    def fake(script, model):
        tried.append(model)
        if model != "gemini-2.5-flash-preview-tts":
            raise RuntimeError("HTTP 429 RESOURCE_EXHAUSTED quota")
        return fake_wav()

    monkeypatch.setattr(ee, "_request_tts_audio", fake)
    assert ee.synthesize_voiceover(GOOD_SCRIPT, tmp_path / "v.wav").exists()
    assert tried[-1] == "gemini-2.5-flash-preview-tts" and len(tried) == len(ee.TTS_MODELS_DEFAULT)


def test_invalid_api_key_stops_the_chain(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_TTS_MODEL", raising=False)
    tried = []

    def fake(script, model):
        tried.append(model)
        raise RuntimeError("400 API key not valid. Please pass a valid API key.")

    monkeypatch.setattr(ee, "_request_tts_audio", fake)
    with pytest.raises(LLMUnavailableError, match="key rejected"):
        ee.synthesize_voiceover(GOOD_SCRIPT, tmp_path / "v.wav")
    assert len(tried) == 1


def test_models_visible_to_the_key_are_tried_first(monkeypatch):
    monkeypatch.delenv("GEMINI_TTS_MODEL", raising=False)
    chain = ee.tts_model_chain(["gemini-2.5-flash-preview-tts", "gemini-9-new-tts", "gemini-3.1-flash-tts-preview"])
    assert chain[:3] == ["gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts", "gemini-9-new-tts"]
    assert set(ee.TTS_MODELS_DEFAULT) <= set(chain) and len(chain) == len(set(chain))


def test_second_route_is_used_when_the_first_is_rejected(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    calls = []

    def interactions(model, script, voice, key):
        calls.append("interactions")
        raise RuntimeError("Error code: 404 - Model not found")

    def generate_content(model, script, voice, key):
        calls.append("generateContent")
        return b"wav"

    monkeypatch.setattr(ee, "_tts_interactions", interactions)
    monkeypatch.setattr(ee, "_tts_generate_content", generate_content)
    assert ee._request_tts_audio(GOOD_SCRIPT, "gemini-2.5-flash-preview-tts") == b"wav"
    assert calls == ["interactions", "generateContent"]


def test_both_routes_failing_reports_both_reasons(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(ee, "_tts_interactions", lambda *a: (_ for _ in ()).throw(RuntimeError("404 nf")))
    monkeypatch.setattr(ee, "_tts_generate_content", lambda *a: (_ for _ in ()).throw(RuntimeError("HTTP 400 bad field")))
    with pytest.raises(RuntimeError, match="interactions.*generateContent"):
        ee._request_tts_audio(GOOD_SCRIPT, "m")


def test_generate_content_route_decodes_pcm_into_wav(monkeypatch):
    import base64

    pcm = b"\x01\x00" * 24000
    payload = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;codec=pcm;rate=24000", "data": base64.b64encode(pcm).decode()}}]}}]}
    posted = {}

    class Resp:
        status_code = 200
        text = ""

        def json(self):
            return payload

    def fake_post(url, headers, json, timeout):
        posted.update(url=url, body=json)
        return Resp()

    monkeypatch.setattr(ee.requests, "post", fake_post)
    wav = ee._tts_generate_content("gemini-2.5-flash-preview-tts", GOOD_SCRIPT, "Kore", "k")
    assert wav[:4] == b"RIFF" and len(wav) > 40000
    assert posted["url"].endswith("/models/gemini-2.5-flash-preview-tts:generateContent")
    assert posted["body"]["generationConfig"]["responseModalities"] == ["AUDIO"]
    # Only the script may be in the spoken text part; the style is a separate instruction.
    assert posted["body"]["contents"][0]["parts"][0]["text"] == GOOD_SCRIPT


def test_generate_content_retries_without_style_on_400(monkeypatch):
    import base64

    pcm = base64.b64encode(b"\x01\x00" * 100).decode()
    bodies = []

    class Resp:
        def __init__(self, code):
            self.status_code, self.text = code, "bad"

        def json(self):
            return {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;rate=24000", "data": pcm}}]}}]}

    def fake_post(url, headers, json, timeout):
        bodies.append(json)
        return Resp(400 if "systemInstruction" in json else 200)

    monkeypatch.setattr(ee.requests, "post", fake_post)
    ee._tts_generate_content("gemini-2.5-flash-preview-tts", GOOD_SCRIPT, "Kore", "k")
    assert len(bodies) == 2 and "systemInstruction" not in bodies[1]
    assert all(b["contents"][0]["parts"][0]["text"] == GOOD_SCRIPT for b in bodies)


def test_configured_tts_model_is_tried_first(monkeypatch):
    monkeypatch.setenv("GEMINI_TTS_MODEL", "my-model, gemini-3.8-flash-lite-tts")
    chain = ee.tts_model_chain()
    assert chain[:2] == ["my-model", "gemini-3.8-flash-lite-tts"]
    assert chain.count("gemini-3.8-flash-lite-tts") == 1 and "gemini-3.8-flash-tts" in chain
