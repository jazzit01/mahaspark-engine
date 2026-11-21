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
