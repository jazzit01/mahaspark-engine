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
