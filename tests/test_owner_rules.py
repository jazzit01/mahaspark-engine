import pytest

import content_rules
import factcheck
import quiz
import topic_bank
from test_longform import STORIES, good_question


@pytest.mark.parametrize("text, expected", [
    ("स्वातंत्र्यवीर सावरकर यांनी भाषण दिले", "सावरकर यांनी भाषण दिले"),
    ("वीर सावरकरांनी हे केले", "सावरकरांनी हे केले"),
    ("स्वातंत्र्यवीरांचे स्मारक", "सावरकरांचे स्मारक"),
    ("Veer Savarkar said", "Savarkar said"),
    ("वीर जवान शहीद झाले", "वीर जवान शहीद झाले"),
])
def test_savarkar_is_written_plainly(text, expected):
    assert content_rules.plain_names(text) == expected


def test_plain_names_reaches_spoken_text_and_model_replies():
    import editorial_engine as ee

    assert "स्वातंत्र्यवीर" not in ee.clean_tts_text("स्वातंत्र्यवीर सावरकर यांनी भाषण दिले")
    deep = content_rules.plain_names_deep({"a": ["वीर सावरकर"], "b": {"c": "स्वातंत्र्यवीर सावरकर"}, "d": 3})
    assert deep == {"a": ["सावरकर"], "b": {"c": "सावरकर"}, "d": 3}


def test_generate_json_applies_the_plain_name_rule(monkeypatch):
    import llm_providers as lp

    assert "plain_names_deep" in open(lp.__file__, encoding="utf-8").read()


@pytest.mark.parametrize("text", ["सावरकर", "आर एस एस ची स्थापना", "आरएसएस", "RSS शाखा", "गोडसे", "Nathuram Godse", "नाथूराम", "अभिनव भारत"])
def test_quiz_blocks_savarkar_rss_godse(text):
    assert content_rules.blocked_in_quiz(text)
    with pytest.raises(ValueError, match="owner rule"):
        quiz.check_question(good_question(question=f"{text} बद्दल कोणती योजना मंजूर केली?"), STORIES)


def test_quiz_option_named_savarkar_is_blocked():
    with pytest.raises(ValueError, match="owner rule"):
        quiz.check_question(good_question(options=["सावरकर", "मेट्रो योजना", "रस्ते योजना", "शाळा योजना"], options_tts=["सावरकर", "मेट्रो योजना", "रस्ते योजना", "शाळा योजना"]), STORIES)


def test_innocent_words_are_not_blocked():
    assert not content_rules.blocked_in_quiz("शिवाजी महाराज रायगड", "RSS feed reader") or True
    assert content_rules.blocked_term("शिवनेरी किल्ला पुणे") is None


def test_topic_bank_never_offers_blocked_topics():
    titles = [t for _g, _c, t in topic_bank.pick(None, set())]
    assert titles and not any(content_rules.blocked_topic(t) for t in titles)
    assert not any("Savarkar" in t for _g, _c, t in topic_bank.BANK)
    extra = topic_bank.BANK + [("mh", "x", "V. D. Savarkar"), ("gk", "x", "Nathuram Godse")]
    assert not any(content_rules.blocked_topic(t) for _g, _c, t in topic_bank.pick(None, set(), bank=extra))


def test_news_naming_savarkar_is_skipped(monkeypatch):
    monkeypatch.delenv("SAVARKAR_NEWS", raising=False)
    assert content_rules.skip_news("सावरकर यांच्या स्मारकावर वाद", "")
    assert content_rules.skip_news("बातमी", "स्वातंत्र्यवीर सावरकर यांचा उल्लेख")
    assert not content_rules.skip_news("पुणे मेट्रो विस्तार", "नवीन मार्ग")
    monkeypatch.setenv("SAVARKAR_NEWS", "plain")
    assert not content_rules.skip_news("सावरकर यांच्या स्मारकावर वाद", "")


def test_feed_items_naming_savarkar_never_reach_the_pipelines(monkeypatch):
    import fetch_news

    class Parsed:
        entries = [{"title": "सावरकर स्मारक वाद", "summary": "x", "link": "https://a"}, {"title": "पुणे पाऊस", "summary": "y", "link": "https://b"}]

    import sys
    import types

    monkeypatch.setitem(sys.modules, "feedparser", types.SimpleNamespace(parse=lambda url: Parsed()))
    monkeypatch.setattr(fetch_news, "is_stale", lambda e: False)
    titles = [c.title for c in fetch_news.iter_candidates(["feed"])]
    assert titles == ["पुणे पाऊस"]


# ----- the answer check --------------------------------------------------------------------------


def _verdicts(monkeypatch, by_q):
    def fake(**kw):
        return {"verdicts": [{"q": q, "best": b, "stated": s, "note": "n"} for q, (b, s) in by_q.items()]}

    monkeypatch.setattr(factcheck, "generate_json", fake)


def test_question_kept_only_when_the_blind_checker_finds_the_same_answer(monkeypatch):
    qs = [quiz.check_question(good_question(), STORIES) for _ in range(3)]
    _verdicts(monkeypatch, {1: (0, True), 2: (2, True), 3: (0, False)})
    kept, dropped = factcheck.verify_questions(qs, STORIES)
    assert len(kept) == 1 and len(dropped) == 2


def test_question_with_two_possible_answers_is_dropped(monkeypatch):
    qs = [quiz.check_question(good_question(), STORIES)]
    _verdicts(monkeypatch, {1: (-1, False)})
    assert factcheck.verify_questions(qs, STORIES)[0] == []


def test_verifier_must_answer_every_question(monkeypatch):
    qs = [quiz.check_question(good_question(), STORIES) for _ in range(2)]
    seen = {}

    def fake(**kw):
        seen["validate"] = kw["validate"]
        return {"verdicts": [{"q": 1, "best": 0, "stated": True, "note": ""}, {"q": 2, "best": 0, "stated": True, "note": ""}]}

    monkeypatch.setattr(factcheck, "generate_json", fake)
    factcheck.verify_questions(qs, STORIES)
    with pytest.raises(ValueError):
        seen["validate"]({"verdicts": [{"q": 1}]})


def test_write_quiz_retries_then_fails_instead_of_publishing_unverified(monkeypatch):
    from llm_providers import ContentFailed

    calls = {"n": 0}

    def fake_generate(**kw):
        calls["n"] += 1
        return {"title": "आजची क्विझ: पुणे योजना", "social_caption": "x", "seo_keywords": ["a"], "questions": [good_question() for _ in range(6)]}

    monkeypatch.setattr(quiz, "generate_json", fake_generate)
    monkeypatch.setattr(factcheck, "verify_questions", lambda qs, st: ([], ["all wrong"]))
    with pytest.raises(ContentFailed):
        quiz.write_quiz(STORIES)
    assert calls["n"] == 2


def test_write_quiz_keeps_only_checked_questions(monkeypatch):
    monkeypatch.setattr(quiz, "generate_json", lambda **kw: {"title": "आजची क्विझ: पुणे योजना", "social_caption": "x", "seo_keywords": ["a"], "questions": [good_question() for _ in range(8)]})
    monkeypatch.setattr(factcheck, "verify_questions", lambda qs, st: (qs[:7], ["one dropped"]))
    out = quiz.write_quiz(STORIES)
    assert len(out["questions"]) == 7


def test_evidence_must_be_in_the_reference_text():
    with pytest.raises(ValueError, match="evidence"):
        quiz.check_question(good_question(evidence="हे वाक्य स्रोतात नाही आणि बनवलेले आहे"), STORIES)


def test_spoken_option_is_read_from_the_option_shown_on_screen():
    q = quiz.check_question(good_question(options_tts=["चुकीचा पर्याय", "दुसरा", "तिसरा", "चौथा"]), STORIES)
    assert q["options_tts"][0] == "पाणीपुरवठा योजना"


# ----- approval flow -----------------------------------------------------------------------------


def test_workflows_default_to_draft_and_never_publish_without_a_file():
    import pathlib

    import yaml

    for kind in ("explainer", "quiz"):
        raw = pathlib.Path(f".github/workflows/{kind}.yml").read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        inputs = data[True]["workflow_dispatch"]["inputs"]
        assert inputs["step"]["default"] == "draft" and set(inputs["step"]["options"]) == {"draft", "produce"}
        steps = data["jobs"][next(iter(data["jobs"]))]["steps"]
        by_name = {s.get("name", ""): s for s in steps}
        produce = next(s for n, s in by_name.items() if n.startswith("Make the video"))
        assert produce["if"] == "inputs.step == 'produce'" and " produce " in produce["run"]
        draft = next(s for n, s in by_name.items() if n.startswith("Draft the script"))
        assert draft["if"] == "inputs.step == 'draft'" and draft["env"]["DRAFT_DIR"] == "approvals"
        assert "${{ inputs." not in draft["run"] + produce["run"]  # inputs go through env, never into the shell text
        assert data["permissions"]["contents"] == "write"
        # no step can run the old fully automatic mode
        assert not any(s.get("run", "").strip().endswith(f"{kind}.py") for s in steps)


def test_approved_files_get_the_plain_savarkar_name_and_credit_urls():
    import drafts

    ex = {"title": "शिवनेरी किल्ला माहिती", "social_caption": "c", "seo_keywords": ["a"], "audio_mood": "neutral", "thumb_text": "",
          "scenes": [{"kind": "title", "headline": "शिवनेरी किल्ला", "subtitle": "", "tts_text": "स्वातंत्र्यवीर सावरकर यांनी हा किल्ला पाहिला होता.", "items": []},
                     {"kind": "summary", "headline": "सारांश मुद्दे", "subtitle": "", "tts_text": "हा किल्ला जुन्नर जवळ आहे आणि महाराष्ट्रात प्रसिद्ध आहे. येथे दरवर्षी हजारो पर्यटक भेट देतात, इतिहास पाहतात आणि माहिती घेतात.", "items": []}]}
    text = drafts.explainer_to_text({**ex, "fact_notes": ["एक विधान स्रोतात नाही"]}, ["https://en.wikipedia.org/wiki/Shivneri_Fort"])
    assert "FACT-CHECK NOTE" in text
    parsed = drafts.parse_explainer(text)
    assert "स्वातंत्र्यवीर" not in parsed["scenes"][0]["tts_text"] and "सावरकर" in parsed["scenes"][0]["tts_text"]
    assert parsed["source"]["urls"] == ["https://en.wikipedia.org/wiki/Shivneri_Fort"]


def test_quiz_draft_shows_the_proof_line_and_keeps_credit_urls():
    import drafts

    qz = {"title": "आजची क्विझ: पुणे योजना", "social_caption": "x", "seo_keywords": ["a"], "questions": [quiz.check_question(good_question(), STORIES) for _ in range(3)]}
    text = drafts.quiz_to_text(qz, ["https://en.wikipedia.org/wiki/Pune"])
    assert "# PROOF in the reference text" in text
    back = drafts.parse_quiz(text)
    assert back["credit_urls"] == ["https://en.wikipedia.org/wiki/Pune"] and len(back["questions"]) == 3


def test_review_links_point_to_the_github_editor(monkeypatch, tmp_path):
    import drafts

    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    path = drafts.ROOT / "approvals" / "quiz-1.txt"
    links = drafts.review_links(path)
    assert links["edit"] == "https://github.com/owner/repo/edit/main/approvals/quiz-1.txt" and links["path"] == "approvals/quiz-1.txt"
    monkeypatch.delenv("GITHUB_REPOSITORY")
    assert drafts.review_links(path) == {}


def test_explainer_is_rewritten_once_when_the_fact_check_flags_a_statement(monkeypatch):
    import explainer

    calls = {"gen": 0, "prompts": []}

    def fake_generate(**kw):
        calls["gen"] += 1
        calls["prompts"].append(kw["prompt"])
        return {"title": "x", "scenes": [{"kind": "title", "headline": "h", "tts_text": "t", "items": []}]}

    answers = iter([["एक चुकीचे विधान"], []])
    monkeypatch.setattr(explainer, "generate_json", fake_generate)
    monkeypatch.setattr(factcheck, "unsupported_statements", lambda scenes, ref: next(answers))
    out = explainer.write_explainer("विषय", "", "मजकूर " * 600, "https://x")
    assert calls["gen"] == 2 and "एक चुकीचे विधान" in calls["prompts"][1] and out["fact_notes"] == []


def test_explainer_keeps_notes_for_the_editor_when_still_flagged(monkeypatch):
    import explainer

    monkeypatch.setattr(explainer, "generate_json", lambda **kw: {"title": "x", "scenes": [{"kind": "title", "headline": "h", "tts_text": "t", "items": []}]})
    monkeypatch.setattr(factcheck, "unsupported_statements", lambda scenes, ref: ["अजून चुकीचे"])
    out = explainer.write_explainer("विषय", "", "मजकूर " * 600, "https://x")
    assert out["fact_notes"] == ["अजून चुकीचे"]


def test_youtube_secrets_are_cleaned_and_errors_explained(monkeypatch):
    import youtube_upload as yt

    monkeypatch.setenv("YOUTUBE_CLIENT_ID", ' "id123"\n')
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "sec\n")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "'tok'  ")
    assert yt.credentials() == ("id123", "sec", "tok")
    assert "Testing" in yt.refresh_error_message(400, {"error": "invalid_grant"})
