import json

import pytest

import editorial_engine as ee
import media_fetch as mf
import send_telegram as tg
from helpers import SOURCE_TEXT, valid_story


@pytest.fixture(autouse=True)
def no_network_topic_photos(monkeypatch):
    monkeypatch.setattr(mf, "search_commons_topic", lambda q, place, used: None)


# ----- schema / validator -------------------------------------------------------------------------


def test_visual_query_is_cleaned_to_english_words():
    assert ee.clean_visual_query("Flyover, construction!! पुणे traffic night shot extra words here") == "flyover construction traffic night shot extra"
    assert ee.clean_visual_query("फक्त मराठी") == ""


def test_public_figure_is_dropped_for_grave_or_crime_stories():
    assert ee.clean_public_figure("Devendra Fadnavis", "neutral") == "Devendra Fadnavis"
    for mood in ("serious", "crime", "breaking"):
        assert ee.clean_public_figure("Devendra Fadnavis", mood) == ""
    assert ee.clean_public_figure("Madonna", "neutral") == ""  # one word: too ambiguous to look up
    assert ee.clean_public_figure("पंतप्रधान", "neutral") == ""


def test_validate_story_carries_visuals_and_seo_fields():
    story = valid_story()
    story["public_figure"] = "Ajit Pawar"
    story["seo_keywords"] = ["Pune flyover", "पुणे उड्डाणपूल", "pune flyover", "Maharashtra news"]
    story["hashtags"] = "#Pune पुणे #PuneFlyover"
    story["scenes"][0]["visual_query"] = "flyover construction traffic"
    result = ee.validate_story(story, SOURCE_TEXT)
    assert result["public_figure"] == "Ajit Pawar"
    assert result["seo_keywords"] == ["Pune flyover", "पुणे उड्डाणपूल", "Maharashtra news"]
    assert result["hashtags"].startswith("#MahaSpark #Pune")
    assert result["scenes"][0]["visual_query"] == "flyover construction traffic"


def test_hashtags_are_capped_and_always_start_with_mahaspark():
    tags = ee.clean_hashtags(" ".join(f"#tag{i}" for i in range(30)))
    assert tags.split()[0] == "#MahaSpark" and len(tags.split()) == 15
    assert ee.clean_hashtags("").startswith("#MahaSpark #")


# ----- Pexels -------------------------------------------------------------------------------------


def video(id_, dur=10, files=None):
    return {
        "id": id_,
        "duration": dur,
        "user": {"name": "Asha"},
        "video_files": files
        or [
            {"link": "https://v/low.mp4", "file_type": "video/mp4", "width": 540, "height": 960},
            {"link": "https://v/hd.mp4", "file_type": "video/mp4", "width": 1080, "height": 1920},
            {"link": "https://v/uhd.mp4", "file_type": "video/mp4", "width": 2160, "height": 3840},
        ],
    }


def test_best_file_is_the_smallest_one_tall_enough():
    assert mf.pick_video_file(video(1))["link"] == "https://v/hd.mp4"


class FakeResp:
    def __init__(self, payload=None, code=200):
        self.payload, self.status_code, self.text = payload or {}, code, "x"

    def json(self):
        return self.payload


def test_pexels_skips_used_and_too_long_clips(monkeypatch):
    payload = {"videos": [video(1), video(2, dur=120), video(3)]}
    monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp(payload))
    clip = mf.search_pexels("rain", "key", exclude_ids={1})
    assert clip["id"] == 3 and clip["credit"] == "Video: Asha / Pexels"


# ----- Wikimedia Commons --------------------------------------------------------------------------


def commons_page(title, licence, width=1200, index=1):
    return {
        "title": title,
        "index": index,
        "imageinfo": [
            {
                "thumburl": "https://c/x.jpg",
                "width": width,
                "extmetadata": {"LicenseShortName": {"value": licence}, "Artist": {"value": "<a href='#'>Some  Author</a>"}},
            }
        ],
    }


def test_commons_requires_free_licence_and_surname_in_title(monkeypatch):
    pages = {
        "1": commons_page("File:Random crowd.jpg", "CC BY 4.0", index=1),
        "2": commons_page("File:Ajit Pawar fair.jpg", "Fair use", index=2),
        "3": commons_page("File:Ajit Pawar 2023.jpg", "CC BY-SA 4.0", index=3),
    }
    monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp({"query": {"pages": pages}}))
    found = mf.search_commons_photo("Ajit Pawar")
    assert found["credit"] == "Photo: Some Author, CC BY-SA 4.0, Wikimedia Commons"


def test_commons_returns_none_when_nothing_qualifies(monkeypatch):
    pages = {"1": commons_page("File:Ajit Pawar small.jpg", "CC BY 4.0", width=200)}
    monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp({"query": {"pages": pages}}))
    assert mf.search_commons_photo("Ajit Pawar") is None


# ----- attach_media -------------------------------------------------------------------------------


def make_story(figure=""):
    story = valid_story()
    story["public_figure"] = figure
    story["visual_theme"] = "EditorialDeskLight"
    story["scenes"] = [dict(s, visual_query=f"scene {i} words") for i, s in enumerate(story["scenes"])]
    return story


def test_scenes_get_footage_and_the_figure_photo_replaces_hook_and_closer(monkeypatch, tmp_path):
    monkeypatch.setenv("PEXELS_API_KEY", "key")
    counter = iter(range(100, 200))
    monkeypatch.setattr(mf, "search_pexels", lambda q, k, used: {"id": next(counter), "url": "u", "duration": 9.0, "credit": "Video: A / Pexels"})
    monkeypatch.setattr(mf, "search_commons_photo", lambda n: {"url": "p", "credit": "Photo: B, CC BY 4.0, Wikimedia Commons"})
    monkeypatch.setattr(mf, "download", lambda url, dest: dest.write_bytes(b"x" * 10) or True)
    story = make_story("Ajit Pawar")
    out = mf.attach_media(story, tmp_path / "story.json", tmp_path / "media")
    kinds = [s["media"]["type"] for s in out["scenes"]]
    assert kinds[0] == "image" and kinds[-1] == "image" and set(kinds[1:-1]) == {"video"}
    assert out["visual_theme"] == "GlassNewsroomDepth"  # the light studio is swapped for a dark one under footage
    assert "Photo: B, CC BY 4.0, Wikimedia Commons" in out["media_credits"]
    assert json.loads((tmp_path / "story.json").read_text(encoding="utf-8"))["scenes"][1]["media"]["file"] == "media/scene-1.mp4"


def test_nothing_is_attached_without_key_or_figure_and_the_story_survives(monkeypatch, tmp_path):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    out = mf.attach_media(make_story(), tmp_path / "story.json", tmp_path / "media")
    assert not mf.has_media(out) and out["visual_theme"] == "EditorialDeskLight"


def test_lookup_errors_never_break_the_run(monkeypatch, tmp_path):
    monkeypatch.setenv("PEXELS_API_KEY", "key")

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(mf, "search_pexels", boom)
    monkeypatch.setattr(mf, "search_commons_photo", boom)
    out = mf.attach_media(make_story("Ajit Pawar"), tmp_path / "story.json", tmp_path / "media")
    assert not mf.has_media(out)


def test_failed_download_leaves_that_scene_on_the_studio(monkeypatch, tmp_path):
    monkeypatch.setenv("PEXELS_API_KEY", "key")
    monkeypatch.setattr(mf, "search_pexels", lambda q, k, used: {"id": 1, "url": "u", "duration": 9.0, "credit": "c"})
    monkeypatch.setattr(mf, "download", lambda url, dest: False)
    assert not mf.has_media(mf.attach_media(make_story(), tmp_path / "story.json", tmp_path / "media"))


# ----- Telegram SEO output ------------------------------------------------------------------------


def test_telegram_shows_seo_title_keywords_tags_and_visual_credits():
    story = valid_story()
    story.update(
        social_title="पुणे उड्डाणपूल मंजुरी: नगर रस्त्यावरील प्रकल्प दोन वर्षांत खुला होणार",
        seo_keywords=["Pune flyover", "पुणे उड्डाणपूल"],
        hashtags="#MahaSpark #Pune #PuneFlyover",
        media_credits=["Video: Asha / Pexels", "Photo: B, CC BY 4.0, Wikimedia Commons"],
    )
    text = tg.build_summary_message(story, "https://example.com")
    assert "Pune flyover, पुणे उड्डाणपूल" in text and "Video: Asha / Pexels" in text and "not footage of the event" in text
    assert "#PuneFlyover" in text and "<code>पुणे उड्डाणपूल मंजुरी" in text  # title, description, keywords, tags stay in the message


def test_pipeline_visuals_hook_is_failure_proof_and_picks_crf(monkeypatch):
    import pipeline

    monkeypatch.setattr(pipeline.media_fetch, "attach_media", lambda story: (_ for _ in ()).throw(RuntimeError("x")))
    story = {"scenes": [{}]}
    assert pipeline.add_visuals(story) is story
    assert pipeline.reel_crf(story) == 18
    assert pipeline.reel_crf({"scenes": [{"media": {"type": "video"}}]}) == 21


# ----- motion graphics ----------------------------------------------------------------------------

MOTION_SOURCE = "पुणे महापालिकेने 1,200 कोटी रुपयांची तरतूद केली. आयुक्त राजेश पाटील म्हणाले, \"काम दोन वर्षांत पूर्ण होईल.\""


def test_stat_motion_needs_a_figure_that_is_in_the_source():
    ok = ee.clean_motion({"type": "stat", "value": "₹1,200 कोटी", "label": "तरतूद"}, MOTION_SOURCE)
    assert ok == {"type": "stat", "value": "₹१,२०० कोटी", "label": "तरतूद"}  # shown in Devanagari digits
    assert ee.clean_motion({"type": "stat", "value": "₹900 कोटी"}, MOTION_SOURCE) == {}
    assert ee.clean_motion({"type": "stat", "value": "मोठा निधी"}, MOTION_SOURCE) == {}


def test_place_and_quote_motion_must_be_verbatim_from_the_source():
    assert ee.clean_motion({"type": "place", "value": "पुणे"}, MOTION_SOURCE) == {}  # location pin removed on request
    quote = {"type": "quote", "value": "काम दोन वर्षांत पूर्ण होईल.", "label": "राजेश पाटील"}
    assert ee.clean_motion(quote, MOTION_SOURCE) == quote
    assert ee.clean_motion({**quote, "value": "काम लवकरच पूर्ण होईल असे सांगितले."}, MOTION_SOURCE) == {}
    assert ee.clean_motion({**quote, "label": "अनोळखी व्यक्ती"}, MOTION_SOURCE) == {}


def test_bad_or_unknown_motion_is_dropped_not_an_error():
    for raw in (None, "stat", {}, {"type": "confetti", "value": "x"}, {"type": "quote", "value": "लहान", "label": "x"}):
        assert ee.clean_motion(raw, MOTION_SOURCE) == {}


def test_validate_story_keeps_only_checked_motion():
    story = valid_story()
    story["scenes"][1]["motion"] = {"type": "stat", "value": "120 कोटी", "label": "तरतूद"}
    story["scenes"][0]["motion"] = {"type": "stat", "value": "999 कोटी"}
    result = ee.validate_story(story, SOURCE_TEXT)
    assert result["scenes"][1]["motion"]["value"] == "१२० कोटी" and result["scenes"][0]["motion"] == {}


def test_a_ten_second_story_is_accepted():
    story = valid_story()
    story["scenes"] = story["scenes"][:2]
    story["scenes"][0]["tts_text"] = "पुणे महापालिकेने, नव्या उड्डाणपुलाला मंजुरी दिली आहे."
    story["scenes"][1]["tts_text"] = "प्रकल्पासाठी, कोट्यवधी रुपयांची तरतूद करण्यात आली आहे. दोन वर्षांत, उड्डाणपूल वाहतुकीसाठी खुला होईल, असे आयुक्तांनी सांगितले. काम पुढील महिन्यात सुरू होणार आहे."
    result = ee.validate_story(story, SOURCE_TEXT)
    assert 2 == len(result["scenes"]) and 25 <= len(result["tts_narration_script"].split()) < 40


def test_visual_place_is_plain_english():
    assert ee.clean_visual_place("Pune, Maharashtra India extra") == "Pune Maharashtra India"
    assert ee.clean_visual_place("पुणे") == ""


# ----- Wikimedia Commons topic photos -------------------------------------------------------------


def test_topic_photo_skips_maps_used_titles_and_non_free_files(monkeypatch):
    monkeypatch.undo()  # use the real search function with a fake HTTP layer
    pages = {
        "1": commons_page("File:Pune map.jpg", "CC BY 4.0", width=2000, index=1),
        "2": commons_page("File:Pune used.jpg", "CC BY 4.0", width=2000, index=2),
        "3": commons_page("File:Pune closed.jpg", "All rights reserved", width=2000, index=3),
        "4": commons_page("File:Pune flyover.jpg", "CC BY-SA 4.0", width=2000, index=4),
    }
    monkeypatch.setattr(mf.requests, "get", lambda *a, **k: FakeResp({"query": {"pages": pages}}))
    found = mf.search_commons_topic("flyover", "Pune", {"File:Pune used.jpg"})
    assert found["title"] == "File:Pune flyover.jpg" and found["credit"].endswith("Wikimedia Commons")


def test_scenes_without_stock_video_get_commons_photos_with_their_size(monkeypatch, tmp_path):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    titles = iter(f"File:p{i}.jpg" for i in range(10))
    monkeypatch.setattr(
        mf,
        "search_commons_topic",
        lambda q, place, used: {"title": next(titles), "url": "u", "credit": "Photo: A, CC BY 4.0, Wikimedia Commons", "width": 1600, "height": 1067},
    )
    monkeypatch.setattr(mf, "download", lambda url, dest: dest.write_bytes(b"x" * 10) or True)
    out = mf.attach_media(make_story(), tmp_path / "story.json", tmp_path / "media")
    media = [s["media"] for s in out["scenes"]]
    assert all(m["type"] == "image" and m["width"] == 1600 and m["file"].endswith(".jpg") for m in media)


def _has_key(node, key):
    if isinstance(node, dict):
        return key in node or any(_has_key(v, key) for v in node.values())
    if isinstance(node, list):
        return any(_has_key(v, key) for v in node)
    return False


def test_story_schema_has_no_additional_properties():
    """Gemini's Developer API rejects 'additionalProperties' (this broke every reel after PR #15)."""
    assert not _has_key(ee.Story.model_json_schema(), "additionalProperties")


def test_empty_typed_motion_is_dropped():
    assert ee.clean_motion(ee.Motion().model_dump(), MOTION_SOURCE) == {}
