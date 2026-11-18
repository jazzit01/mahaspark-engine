import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import editorial_engine as ee  # noqa: E402
import make_beds  # noqa: E402
import marathi_numbers as mn  # noqa: E402


@pytest.mark.parametrize(
    "spoken,shown",
    [
        ("सत्तावीस नोव्हेंबर रोजी", "२७ नोव्हेंबर रोजी"),
        ("पंच्याऐंशी टक्के मतदान", "८५% मतदान"),
        ("एक हजार दोनशे कोटी रुपये मंजूर", "₹१,२०० कोटी मंजूर"),
        ("पाच हजार सहाशे पंच्याहत्तर कोटींच्या प्रकल्पाचा खर्च", "५,६७५ कोटींच्या प्रकल्पाचा खर्च"),
        ("दोन हजार सव्वीस मध्ये", "२०२६ मध्ये"),
        ("पाच लाख रुपये दिले, बारा जण", "₹५ लाख दिले, १२ जण"),
        ("12 वर्षांत ₹1,200 कोटी", "१२ वर्षांत ₹१,२०० कोटी"),
        ("एक आरोपी पकडला", "एक आरोपी पकडला"),  # a lone "one" stays a word
        ("एकही नाही", "एकही नाही"),
    ],
)
def test_words_become_devanagari_digits(spoken, shown):
    assert mn.words_to_digits(spoken) == shown


def test_unknown_number_words_stay_words():
    assert mn.words_to_digits("कोणतातरी आकडा हजार लोक") == "कोणतातरी आकडा हजार लोक"


def test_caption_words_merge_with_timings_and_keep_the_script():
    words = [
        {"text": "खर्च", "start": 0.0, "end": 0.4, "scene": 0},
        {"text": "एक", "start": 0.4, "end": 0.6, "scene": 0},
        {"text": "हजार", "start": 0.6, "end": 0.9, "scene": 0},
        {"text": "दोनशे", "start": 0.9, "end": 1.3, "scene": 0},
        {"text": "कोटी", "start": 1.3, "end": 1.6, "scene": 0},
        {"text": "रुपये.", "start": 1.6, "end": 2.0, "scene": 0},
    ]
    out = mn.caption_words(words)
    assert [w["text"] for w in out] == ["खर्च", "₹१,२०० कोटी."]
    assert out[1]["start"] == 0.4 and out[1]["end"] == 2.0
    assert [w["text"] for w in words][1] == "एक"  # the spoken words are untouched


def test_on_screen_numbers_in_source_words_are_accepted():
    assert "27" in ee.source_numbers("बैठक सत्तावीस नोव्हेंबर रोजी होईल")


def test_background_hue_varies_but_breaking_keeps_its_colours():
    hues = {ee.pick_hue(f"story {i}") for i in range(40)}
    assert len(hues) >= 5 and 0 not in hues
    assert ee.pick_hue("x", calm=False) == 0


def test_white_studio_is_retired():
    assert "EditorialDeskLight" not in ee.CALM_THEMES
    assert all(ee.pick_theme(None, "neutral", f"s{i}") != "EditorialDeskLight" for i in range(60))


@pytest.mark.parametrize("mood", sorted(make_beds.MOODS))
def test_beds_are_generated_loops(mood):
    audio = make_beds.build_bed(mood)
    bpm, chords, _ = make_beds.MOODS[mood]
    assert len(audio) == int(make_beds.SR * 60 / bpm) * 4 * len(chords)
    assert abs(audio).max() <= 0.86 and abs(audio).max() > 0.5
    assert (make_beds.BED_DIR / f"{mood}.mp3").exists()


# ----- YouTube upload of the 16:9 videos ------------------------------------------------------------

import youtube_upload as yt  # noqa: E402


def test_reel_upload_slots_respect_the_daily_quota():
    assert not yt.allowed_reel_uploads(11, 0)
    assert yt.allowed_reel_uploads(12, 0) and not yt.allowed_reel_uploads(13, 1)
    assert yt.allowed_reel_uploads(19, 1) and not yt.allowed_reel_uploads(23, 2)


def test_reel_description_has_cta_ai_note_and_no_source_link():
    story = {"social_caption": "पुणे महापालिकेची मोठी घोषणा.", "five_w_one_h": {"what": "तरतूद जाहीर"}, "hashtags": "#MahaSpark #पुणे"}
    text = yt.build_reel_description(story)
    assert "@MahaSparkOfficial" in text and yt.AI_NOTE in text and "http" not in text


def test_synthetic_flag_is_opt_in(monkeypatch):
    monkeypatch.delenv("YOUTUBE_SYNTHETIC_FLAG", raising=False)
    assert "containsSyntheticMedia" not in yt.build_metadata("t", "d", [])["status"]
    monkeypatch.setenv("YOUTUBE_SYNTHETIC_FLAG", "1")
    assert yt.build_metadata("t", "d", [])["status"]["containsSyntheticMedia"] is True


def test_pipeline_upload_is_skipped_without_credentials(monkeypatch):
    import pipeline

    for key in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    assert pipeline.upload_reel_to_youtube(object(), {"scenes": [{"headline": "x"}]}) == ""


# ----- one-minute minimum and extra sources -----------------------------------------------------

import fetch_news  # noqa: E402
from llm_providers import ContentRejected  # noqa: E402


def _capture(monkeypatch, outcomes):
    """Replace the model call; ``outcomes`` is a list of dicts (a story) or exceptions to raise, one per call."""
    calls = []

    def fake_write(title, summary, article_text, source_url, source_text, short):
        calls.append(short)
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return dict(outcome)

    monkeypatch.setattr(ee, "_write", fake_write)
    return calls


def test_thin_source_becomes_a_9x16_short(monkeypatch):
    calls = _capture(monkeypatch, [{"scenes": []}])
    story = ee.write_story("पुणे महापालिकेची मोठी घोषणा आज झाली", "तपशील " * 15, "थोडा मजकूर", "https://x")
    assert calls == [True] and story["format"] == "portrait"  # no long attempt at all


def test_rich_source_stays_a_long_16x9_video(monkeypatch):
    calls = _capture(monkeypatch, [{"scenes": []}])
    story = ee.write_story("पुणे महापालिकेची मोठी घोषणा आज झाली", "तपशील", "म " * 1500, "https://x")
    assert calls == [False] and story["format"] == "landscape"


def test_rich_source_that_still_comes_out_short_falls_back_to_a_short(monkeypatch):
    calls = _capture(monkeypatch, [ValueError("Narration has 90 words; it must be between 140 and 185."), {"scenes": []}])
    story = ee.write_story("पुणे महापालिकेची मोठी घोषणा आज झाली", "तपशील", "म " * 1500, "https://x")
    assert calls == [False, True] and story["format"] == "portrait"


def test_all_models_failing_the_long_checks_falls_back_to_a_short(monkeypatch):
    from llm_providers import ContentFailed

    failure = ContentFailed("Content generation failed on every configured provider.", ["Scene 1 description has 111 characters"])
    calls = _capture(monkeypatch, [failure, {"scenes": []}])
    story = ee.write_story("पुणे महापालिकेची मोठी घोषणा आज झाली", "तपशील", "म " * 1500, "https://x")
    assert calls == [False, True] and story["format"] == "portrait"


def test_unavailable_providers_are_not_swallowed(monkeypatch):
    from llm_providers import LLMUnavailableError

    _capture(monkeypatch, [LLMUnavailableError("no key")])
    with pytest.raises(LLMUnavailableError):
        ee.write_story("पुणे महापालिकेची मोठी घोषणा आज झाली", "तपशील", "म " * 1500, "https://x")


def test_short_limits_are_looser_on_length_but_tighter_on_scenes():
    assert ee.SHORT_MAX_WORDS < ee.MAX_TOTAL_WORDS and ee.SHORT_MAX_SCENES < ee.MAX_SCENES
    assert "SHORT vertical (9:16)" in ee.build_user_prompt("t", "s", "a", "u", short=True)
    assert "SHORT vertical" not in ee.build_user_prompt("t", "s", "a", "u")


def test_shorts_render_the_short_composition_and_skip_youtube():
    import pipeline

    assert pipeline.is_short({"format": "portrait"}) and not pipeline.is_short({"format": "landscape"}) and not pipeline.is_short({})
    assert pipeline.upload_reel_to_youtube(object(), {"format": "portrait", "scenes": [{"headline": "x"}]}) == ""


def test_reels_need_a_minute_but_other_callers_keep_the_old_minimum():
    assert ee.REEL_MIN_WORDS == 140 and ee.MIN_TOTAL_WORDS < ee.REEL_MIN_WORDS


def test_rich_source_is_not_enriched(monkeypatch):
    monkeypatch.setattr(fetch_news, "related_sources", lambda *a, **k: pytest.fail("must not search"))
    assert fetch_news.enrich_thin_source("शीर्षक", "सारांश", "म" * 3000, "https://a.in/x") == "म" * 3000


def test_thin_source_gets_other_reports_labelled(monkeypatch):
    monkeypatch.setattr(fetch_news, "related_sources", lambda *a, **k: [("दुसरी बातमी", "https://b.in/y", "दुसऱ्या वृत्ताचा मजकूर")])
    out = fetch_news.enrich_thin_source("शीर्षक", "सारांश", "थोडा मजकूर", "https://a.in/x")
    assert out.startswith("थोडा मजकूर") and "b.in" in out and "दुसऱ्या वृत्ताचा मजकूर" in out


def test_thin_source_without_extras_is_unchanged(monkeypatch):
    monkeypatch.setattr(fetch_news, "related_sources", lambda *a, **k: [])
    assert fetch_news.enrich_thin_source("शीर्षक", "सारांश", "थोडा", "https://a.in/x") == "थोडा"


def test_reel_thumbnail_props_use_hook_headline_tag_and_key_figure():
    import pipeline

    story = {
        "visual_theme": "PrimeGridStudio",
        "scenes": [{"headline": "पुण्यात ११ वाहनांची तोडफोड", "description": "कोयता गँगची दहशत"}],
    }
    props = pipeline.reel_thumbnail_props(story)
    assert props["headline"] == "पुण्यात ११ वाहनांची तोडफोड" and props["tag"] == "ताजी बातमी" and props["figure"] == "११"
    story["visual_theme"] = "BreakingNewsStudio"
    assert pipeline.reel_thumbnail_props(story)["tag"] == "ब्रेकिंग"


# ----- the voice script spells numbers out in code, not in the model -------------------------------

import bulletin_editorial as be  # noqa: E402
from helpers import valid_story  # noqa: E402


@pytest.mark.parametrize(
    "written,spoken",
    [
        ("35000 कामगार", "पस्तीस हजार कामगार"),  # the bug: it was read as "तीस पॉइंट पाच हजार"
        ("₹35,000 कोटी", "पस्तीस हजार कोटी रुपये"),
        ("₹1,200 कोटी रुपये", "एक हजार दोनशे कोटी रुपये"),
        ("85% मतदान", "पंच्याऐंशी टक्के मतदान"),
        ("13 नोव्हेंबर 2026 रोजी", "तेरा नोव्हेंबर दोन हजार सव्वीस रोजी"),
        ("3,50,000 जण", "तीन लाख पन्नास हजार जण"),
        ("१२० जण", "एकशे वीस जण"),
        ("शंभर जण 100 जण", "शंभर जण शंभर जण"),
        ("1.5 लाख, 2.5 लाख, 3.5 लाख", "दीड लाख, अडीच लाख, साडेतीन लाख"),
        ("2.7 टक्के", "दोन पूर्णांक सात टक्के"),
        ("5675 कोटी", "पाच हजार सहाशे पंच्याहत्तर कोटी"),
        ("काही आकडा नाही", "काही आकडा नाही"),
    ],
)
def test_digits_are_spelled_as_correct_marathi(written, spoken):
    assert mn.numbers_to_words(written) == spoken


def test_every_number_up_to_a_thousand_round_trips_through_the_reader():
    for n in range(0, 1000):
        words = mn.int_to_words(n)
        assert mn.words_to_digits(words) == ("एक" if n == 1 else mn.dev_digits(str(n))), (n, words)


def test_times_are_left_for_the_validator_to_reject():
    assert "10:30" in mn.numbers_to_words("सकाळी 10:30 वाजता")


def test_story_voice_script_has_no_digits_after_conversion():
    story = valid_story()
    story["scenes"][1]["tts_text"] = "प्रकल्पासाठी, ₹1,200 कोटी रुपयांची तरतूद करण्यात आली आहे."
    out = ee.validate_story(story, "प्रकल्प 1,200 कोटी तरतूद 120 दोन वर्षांत")
    assert "एक हजार दोनशे कोटी रुपये" in out["scenes"][1]["tts_text"] and not ee.tts_problems(out["scenes"][1]["tts_text"])


def test_bulletin_item_voice_script_is_converted_too():
    data = {
        "approved": True, "headline": "पुण्यात 35000 कामगार संपावर", "context": "कंपनीतील कामगारांनी संप पुकारला आहे.",
        "tts_text": "पुण्यातील 35000 कामगार संपावर गेले आहेत, त्यामुळे कंपनीतील कामकाज पूर्णपणे ठप्प झाले आहे, असे कामगार संघटनेने सांगितले.", "category": "पुणे", "audio_mood": "neutral",
        "event_key": "pune strike", "photo_query": "", "photo_keywords": [],
    }
    out = be.validate_item(data, "पुण्यात 35000 कामगार संपावर गेले. कंपनीतील कामकाज ठप्प झाले. कामगार संघटनेने हे सांगितले.")
    assert "पस्तीस हजार" in out["tts_text"] and out["headline"] == "पुण्यात ३५,००० कामगार संपावर".replace("३५,०००", "३५०००")
