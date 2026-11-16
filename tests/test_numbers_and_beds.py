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
    assert not yt.allowed_reel_uploads(6, 0)
    assert yt.allowed_reel_uploads(7, 0) and not yt.allowed_reel_uploads(8, 1)
    assert yt.allowed_reel_uploads(12, 1) and not yt.allowed_reel_uploads(13, 2)
    assert yt.allowed_reel_uploads(19, 2) and not yt.allowed_reel_uploads(23, 3)


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
