from datetime import date

import drafts
import explainer
import quiz
import topic_bank
import wiki_sources

REF = {
    "title": "Shivneri Fort",
    "url": "https://en.wikipedia.org/wiki/Shivneri_Fort",
    "urls": ["https://en.wikipedia.org/wiki/Shivneri_Fort", "https://mr.wikipedia.org/wiki/x"],
    "text": "[English Wikipedia: Shivneri Fort]\n" + "Shivneri is a fort near Junnar. " * 120,
}


def test_bank_is_unique_and_has_both_groups():
    keys = [t for _g, _c, t in topic_bank.BANK]
    assert len(keys) == len(set(keys)) >= 150
    assert {g for g, _c, _t in topic_bank.BANK} == {"mh", "gk"}


def test_pick_skips_known_and_rotates_categories():
    day = date(2026, 11, 19)
    first = [e for _, e in zip(range(4), topic_bank.pick("mh", set(), day))]
    assert len({c for _g, c, _t in first}) == 4
    known = {topic_bank.wiki_key(first[0][2])}
    assert first[0] not in list(topic_bank.pick("mh", known, day))


def test_credit_line_only_wikipedia():
    assert "CC BY-SA" in wiki_sources.credit_line(["https://en.wikipedia.org/wiki/A", "https://x.com"])
    assert "x.com" not in wiki_sources.credit_line(["https://en.wikipedia.org/wiki/A", "https://x.com"])
    assert wiki_sources.credit_line(["https://x.com"]) == ""


def test_explainer_pick_story_uses_bank_and_records_bank_key(monkeypatch):
    monkeypatch.setattr(wiki_sources, "fetch_topic", lambda t, search=True: dict(REF))
    seen = {}

    def fake_write(title, summary, text, url):
        seen["args"] = (title, summary, url)
        return {"title": "x", "source": {"title": title, "url": url}}

    monkeypatch.setattr(explainer, "write_explainer", fake_write)
    ex = explainer.pick_story(set(), 10**12)
    assert ex["source"]["url"].startswith("https://en.wikipedia.org/wiki/")
    assert ex["source"]["urls"] == REF["urls"]
    assert "आजची" not in explainer.EXPLAINER_INSTRUCTION and "evergreen" in explainer.EXPLAINER_INSTRUCTION


def test_explainer_description_credits_wikipedia():
    ex = {"title": "t", "social_caption": "c", "scenes": [{"kind": "summary", "headline": "h", "items": [{"label": "a"}]}],
          "source": {"urls": REF["urls"]}}
    props = {"scenes": [{"start": 0, "end": 12}], "total_seconds": 12, "outro_start": 12}
    assert "Wikipedia" in explainer.build_description(ex, props)


def test_quiz_gather_mixes_mh_and_gk(monkeypatch):
    monkeypatch.setattr(wiki_sources, "fetch_topic", lambda t, search=True: {**REF, "title": t})
    stories = quiz.gather_stories(set(), 10**12)
    assert len(stories) == quiz.MH_TOPICS + quiz.GK_TOPICS
    assert len({s["url"] for s in stories}) == len(stories)
    assert "not about today's news" in quiz.QUIZ_INSTRUCTION


def test_draft_topic_sources_wikipedia_first(monkeypatch):
    monkeypatch.setattr(wiki_sources, "fetch_topic", lambda t, search=True: dict(REF))
    monkeypatch.setattr(drafts, "topic_reports", lambda *a, **k: (_ for _ in ()).throw(AssertionError("news used")))
    text, urls = drafts.topic_sources("Shivneri")
    assert urls == REF["urls"] and "Shivneri" in text
