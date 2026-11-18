import wave

import pytest

import explainer
import longform
import quiz
from llm_providers import ContentRejected

SOURCE = (
    "पुणे महापालिकेने शहरातील पाणीपुरवठा सुधारण्यासाठी १२०० कोटी रुपयांची योजना मंजूर केली. "
    "आयुक्त नवल किशोर राम म्हणाले, \"नव्या जलवाहिन्यांमुळे शहरातील पाणी गळती कमी होईल\". "
    "योजना २०२८ पर्यंत पूर्ण होईल. " * 3
)


def write_wav(path, seconds=2.0, rate=24000):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as h:
        h.setnchannels(1)
        h.setsampwidth(2)
        h.setframerate(rate)
        h.writeframes(b"\x00\x00" * int(rate * seconds))


# ----- timing ------------------------------------------------------------------------------------


def words(*texts):
    return [{"text": t, "start": i * 1.0, "end": i * 1.0 + 0.8} for i, t in enumerate(texts)]


def test_cue_follows_the_spoken_word_and_keeps_order():
    w = words("पुणे", "महापालिकेने", "योजना", "मंजूर", "केली.")
    cues = longform.cue_times([{"cue": "योजना"}, {"cue": "केली"}], w, 5.0)
    assert cues[0] == pytest.approx(0.5 + 2.0 - 0.15)
    assert cues[1] > cues[0]


def test_cue_index_beats_cue_word_and_missing_cue_is_spread():
    w = words("अ", "ब", "क", "ड")
    assert longform.cue_times([{"cue_index": 2, "cue": "x"}], w, 4.0)[0] == pytest.approx(0.5 + 2.0 - 0.1)
    spread = longform.cue_times([{"cue": ""}, {"cue": "नाही"}], w, 4.0)
    assert 0 < spread[0] < spread[1]


def test_build_scene_times_words_cues_and_length(tmp_path):
    def tts(text, path):
        write_wav(path, 2.0)

    scene = {"kind": "points", "headline": "मुद्दे", "tts_text": "पुणे योजना मंजूर केली.", "items": [{"label": "योजना", "cue": "योजना"}]}
    out = longform.build_scene(scene, 3, tts=tts, whisper=lambda p: [], out_dir=tmp_path)
    assert out["audio"] == "long/scene-3.wav" and out["audio_seconds"] == 2.0
    assert out["seconds"] == pytest.approx(0.5 + 2.0 + 0.8)
    assert out["words"][0]["start"] >= longform.LEAD_SECONDS
    assert 0.4 < out["items"][0]["cue"] < 3.0


def test_build_scene_turns_word_indexes_into_seconds(tmp_path):
    def tts(text, path):
        write_wav(path, 3.0)

    scene = {"kind": "answer", "headline": "x", "tts_text": "बरोबर उत्तर ब, पुणे. कारण असे.", "reveal_index": 2, "explain_index": 4, "items": []}
    out = longform.build_scene(scene, 0, tts=tts, whisper=lambda p: [], out_dir=tmp_path, extra_seconds=5)
    assert "reveal_index" not in out and out["reveal_at"] < out["explain_at"]
    assert out["seconds"] == pytest.approx(0.5 + 3.0 + 5 + 0.8)


def test_chapters_are_at_least_ten_seconds_apart():
    props = {"scenes": [{"start": 0}, {"start": 4}, {"start": 12}, {"start": 30}], "outro_start": 50}
    marks = longform.chapters(props, ["a", "b", "c", "d"])
    assert marks[0][0] == 0 and [m[0] for m in marks] == [0, 12, 30, 50]
    assert longform.chapters({"scenes": [{"start": 0}], "outro_start": 5}, ["a"]) == []


def test_assemble_sums_scene_lengths():
    props = longform.assemble("quiz", "t", [{"seconds": 5.0}, {"seconds": 7.5}], 20)
    assert props["scenes"][1]["start"] == 5.0 and props["outro_start"] == 12.5 and props["total_seconds"] == 20.5


# ----- explainer ---------------------------------------------------------------------------------

TTS = "पुणे महापालिकेने पाणीपुरवठा योजना मंजूर केली, आयुक्तांनी याची माहिती दिली. ही योजना शहरातील नागरिकांसाठी महत्त्वाची आहे. पाणी गळती कमी होईल. " + "आयुक्तांनी पुढील कामाचा तपशील सांगितला, नागरिकांना लवकरच फायदा मिळेल. योजना वेळेत पूर्ण होईल. " + "पुणेकरांना पाणी मिळावे यासाठी महापालिकेने वेळापत्रक ठरवले, कामाची पाहणी नियमित होईल. आयुक्तांनी हे स्पष्ट केले."


def good_scene(kind, items, n=1):
    return {"kind": kind, "headline": "पुणे पाणी योजना मंजूर", "subtitle": "", "items": items, "tts_text": TTS}


def good_explainer():
    pts = [{"label": "योजना मंजूर", "cue": "योजना"}, {"label": "गळती कमी", "cue": "गळती"}]
    scenes = [
        good_scene("title", []),
        good_scene("points", pts),
        good_scene("stat", [{"label": "मंजूर निधी", "value": "₹१,२०० कोटी", "cue": "योजना"}]),
        good_scene("timeline", [{"label": "२०२८", "value": "योजना पूर्ण", "cue": "पुणे"}, {"label": "आज", "value": "मंजुरी", "cue": "महापालिकेने"}, {"label": "पुढे", "value": "काम", "cue": "गळती"}]),
        good_scene("summary", pts),
    ]
    return {"title": "पुणे पाणीपुरवठा योजना: १२०० कोटींची मंजुरी समजून घ्या", "social_caption": "x", "seo_keywords": ["पुणे", "Pune water"], "audio_mood": "neutral", "scenes": scenes}


def test_a_good_explainer_passes_and_digits_stay_devanagari():
    out = explainer.validate_explainer(good_explainer(), SOURCE)
    assert out["scenes"][0]["kind"] == "title" and out["scenes"][2]["items"][0]["value"].startswith("₹")
    assert out["scenes"][2]["items"][0]["cue"] == "योजना"


def test_explainer_rejects_numbers_not_in_the_source():
    data = good_explainer()
    data["scenes"][2]["items"][0]["value"] = "₹९९९ कोटी"
    with pytest.raises(ValueError, match="not in the source"):
        explainer.validate_explainer(data, SOURCE)


def test_explainer_quote_must_be_verbatim():
    data = good_explainer()
    data["scenes"][1] = good_scene("quote", [{"label": "आयुक्त", "value": "आम्ही सर्व काही मोफत करू असे सांगितले", "cue": "योजना"}])
    with pytest.raises(ValueError, match="word for word"):
        explainer.validate_explainer(data, SOURCE)


def test_explainer_structure_rules():
    data = good_explainer()
    data["scenes"][-1]["kind"] = "points"
    with pytest.raises(ValueError, match="summary"):
        explainer.validate_explainer(data, SOURCE)
    data = good_explainer()
    data["scenes"][1]["items"] = [{"label": "एक", "cue": ""}]
    with pytest.raises(ValueError, match="items"):
        explainer.validate_explainer(data, SOURCE)
    data = good_explainer()
    data["scenes"][1]["tts_text"] = "पुणे 5 योजना."
    with pytest.raises(ValueError):
        explainer.validate_explainer(data, SOURCE)


def test_a_cue_that_is_not_spoken_is_dropped_not_fatal():
    data = good_explainer()
    data["scenes"][1]["items"][0]["cue"] = "नसलेला"
    out = explainer.validate_explainer(data, SOURCE)
    assert out["scenes"][1]["items"][0]["cue"] == ""


def test_explainer_rejected_when_not_approved_or_source_thin():
    with pytest.raises(ContentRejected):
        explainer.validate_explainer({"approved": False, "rejection_reason": "अफवा"}, SOURCE)
    with pytest.raises(ContentRejected):
        explainer.write_explainer("शीर्षक", "थोडे", "थोडा मजकूर", "https://x")


def test_explainer_prompt_carries_the_shared_rules():
    assert "FACT DISCIPLINE" in explainer.EXPLAINER_INSTRUCTION and "PHONETIC RULES" in explainer.EXPLAINER_INSTRUCTION


# ----- quiz --------------------------------------------------------------------------------------

STORIES = [{"title": "पुणे महापालिका योजना", "url": "https://x/1", "text": SOURCE}]


def good_question(**over):
    q = {
        "story": 1, "question": "पुणे महापालिकेने कोणती योजना मंजूर केली?", "question_tts": "पुणे महापालिकेने कोणती योजना मंजूर केली.",
        "options": ["पाणीपुरवठा योजना", "मेट्रो योजना", "रस्ते योजना", "शाळा योजना"], "options_tts": ["पाणीपुरवठा योजना", "मेट्रो योजना", "रस्ते योजना", "शाळा योजना"],
        "correct": 0, "explanation": "महापालिकेने १२०० कोटींची पाणीपुरवठा योजना मंजूर केली.", "explanation_tts": "महापालिकेने बाराशे कोटींची पाणीपुरवठा योजना मंजूर केली.",
    }
    q.update(over)
    return q


def test_good_question_passes():
    out = quiz.check_question(good_question(), STORIES)
    assert out["correct"] == 0 and len(out["options"]) == 4


@pytest.mark.parametrize(
    "over, message",
    [
        ({"options": ["अ", "अ", "ब", "क"]}, "4 different"),
        ({"correct": 5}, "index"),
        ({"explanation": "योजना ९९९ कोटींची आहे."}, "not in story"),
        ({"question_tts": "प्रश्न 5 आहे?"}, "question_tts"),
        ({"story": 4}, "story"),
        ({"options_tts": ["अ", "ब"]}, "4 entries"),
    ],
)
def test_bad_questions_are_caught(over, message):
    with pytest.raises(ValueError, match=message):
        quiz.check_question(good_question(**over), STORIES)


def test_quiz_drops_bad_questions_but_needs_enough_good_ones():
    data = {"title": "आजची न्यूज क्विझ: पुणे पाणी योजना", "social_caption": "x", "seo_keywords": ["a"], "questions": [good_question() for _ in range(7)] + [good_question(correct=9)]}
    assert len(quiz.validate_quiz(data, STORIES)["questions"]) == 7
    data["questions"] = [good_question() for _ in range(3)]
    with pytest.raises(ValueError, match="valid questions"):
        quiz.validate_quiz(data, STORIES)


def test_quiz_scenes_have_intro_question_answer_pairs_and_an_end():
    qz = quiz.validate_quiz({"title": "आजची न्यूज क्विझ: पुणे पाणी योजना", "questions": [good_question() for _ in range(6)]}, STORIES)
    scenes, extras = quiz.build_scenes(qz)
    kinds = [s["kind"] for s in scenes]
    assert kinds[0] == "quiz_intro" and kinds[-1] == "quiz_end" and kinds.count("question") == 6 and kinds.count("answer") == 6
    assert extras[kinds.index("question")] == quiz.COUNTDOWN_SECONDS and extras[kinds.index("answer")] == 0
    q = scenes[1]
    spoken = q["tts_text"].split()
    # every option card is cued on the word position of its own letter in the spoken text
    for k, item in enumerate(q["items"]):
        assert spoken[item["cue_index"]].strip(",.") == quiz.LETTERS[k]
    assert not any(c.isdigit() for s in scenes for c in s["tts_text"])  # numbers are spelled out for the voice
    a = scenes[2]
    assert a["tts_text"].split()[a["explain_index"]] == good_question()["explanation_tts"].split()[0]


# ----- approval drafts ---------------------------------------------------------------------------

import drafts  # noqa: E402


def test_explainer_draft_round_trips_through_the_txt_format():
    ex = explainer.validate_explainer(good_explainer(), SOURCE)
    text = drafts.explainer_to_text(ex, ["https://x/1", "https://x/2"])
    back = drafts.parse_explainer(text)
    assert [s["kind"] for s in back["scenes"]] == [s["kind"] for s in ex["scenes"]]
    assert back["scenes"][1]["tts_text"] == ex["scenes"][1]["tts_text"]
    assert back["scenes"][2]["items"][0]["value"] == ex["scenes"][2]["items"][0]["value"]
    assert back["source"]["url"] == "https://x/1\nhttps://x/2" and back["title"]


HAND_WRITTEN = """
TITLE: माझी स्वतःची पुणे पाणी योजना माहिती
CAPTION: थोडक्यात
KEYWORDS: पुणे, Pune water
=== SCENE 1 | title ===
HEADLINE: पुण्याची नवी पाणी योजना
SPEECH: पुणे महापालिकेने 1200 कोटी रुपयांची
  पाणी योजना मंजूर केली आहे.
=== SCENE 2 | points ===
HEADLINE: मुख्य मुद्दे
SPEECH: योजनेमुळे नागरिकांना नियमित पाणी मिळेल, गळती कमी होईल, काम वेळेत पूर्ण होईल.
ITEMS:
- नियमित पाणी
- गळती कमी | | गळती
=== SCENE 3 | stat ===
HEADLINE: निधी
SPEECH: एकूण खर्च 1200 कोटी रुपये आहे.
ITEMS:
- मंजूर निधी | ₹1200 कोटी | खर्च
"""


def test_a_hand_written_script_is_accepted_and_numbers_are_spelled_for_the_voice():
    ex = drafts.parse_explainer(HAND_WRITTEN)
    assert [s["kind"] for s in ex["scenes"]] == ["title", "points", "stat"]
    assert "1200" not in ex["scenes"][0]["tts_text"] and not any(c.isdigit() for s in ex["scenes"] for c in s["tts_text"])
    assert ex["scenes"][1]["items"][0]["cue"] == "नियमित"  # no cue given: found from the item text
    assert ex["scenes"][1]["items"][1]["cue"] == "गळती"
    assert ex["scenes"][2]["items"][0]["value"].startswith("₹")


def test_script_problems_name_the_scene_and_what_to_fix():
    bad = HAND_WRITTEN.replace("पाणी योजना मंजूर केली आहे.", "water plan approved.").replace("SCENE 3 | stat", "SCENE 3 | stat\nHEADLINE: x")
    with pytest.raises(drafts.DraftError) as err:
        drafts.parse_explainer(bad)
    assert any("Scene 1" in p and "Devanagari" in p for p in err.value.problems)
    with pytest.raises(drafts.DraftError) as err:
        drafts.parse_explainer(HAND_WRITTEN.replace("| title ===", "| banana ==="))
    assert "unknown kind" in err.value.problems[0]
    with pytest.raises(drafts.DraftError):
        drafts.parse_explainer("TITLE: काहीही नाही इथे\n")


def test_quiz_draft_round_trips_and_accepts_hand_edits():
    qz = quiz.validate_quiz({"title": "आजची न्यूज क्विझ: पुणे पाणी योजना", "questions": [good_question() for _ in range(6)]}, STORIES)
    text = drafts.quiz_to_text(qz, ["https://x/1"])
    back = drafts.parse_quiz(text)
    assert len(back["questions"]) == 6 and back["questions"][0]["correct"] == 0
    assert back["questions"][0]["options"] == qz["questions"][0]["options"]
    edited = text.replace("ANSWER: A\n", "ANSWER: C\n", 1)
    assert drafts.parse_quiz(edited)["questions"][0]["correct"] == 2
    scenes, _extras = quiz.build_scenes(back)  # the approved file feeds the same scene builder
    assert [s["kind"] for s in scenes].count("question") == 6


def test_quiz_file_errors_are_listed():
    text = "TITLE: आजची न्यूज क्विझ चाचणी\n=== Q1 ===\nQ: पुणे महापालिकेने कोणती योजना मंजूर केली?\nA) एक\nB) एक\nC) तीन\nD) चार\nANSWER: E\nWHY: कारण असे आहे.\n"
    with pytest.raises(drafts.DraftError) as err:
        drafts.parse_quiz(text)
    joined = " ".join(err.value.problems)
    assert "four different options" in joined and "ANSWER" in joined and "at least 3" in joined


def test_cli_dispatch_keeps_the_automatic_mode(monkeypatch):
    called = {}
    monkeypatch.setattr(explainer, "draft_main", lambda a: called.setdefault("draft", a) and 0)
    monkeypatch.setattr(explainer, "produce_main", lambda a: called.setdefault("produce", a) and 0)
    explainer.main(["draft", "--topic", "x"])
    explainer.main(["produce", "f.txt"])
    assert called == {"draft": ["--topic", "x"], "produce": ["f.txt"]}
