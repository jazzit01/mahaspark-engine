"""Live office check (officecheck): claims, verdicts, cache, fallback to the offline table that expires."""

import pytest

import content_rules
import editorial_engine as ee
import officecheck as oc


def claim_names(text):
    return [c.text for c in oc.extract(text)]


def test_extract_finds_titles_directly_before_names():
    assert claim_names("राज्याचे उपमुख्यमंत्री एकनाथ शिंदे म्हणाले.") == ["उपमुख्यमंत्री एकनाथ शिंदे"]
    assert claim_names("पंतप्रधान नरेंद्र मोदी आणि राष्ट्रपती द्रौपदी मुर्मू उपस्थित होते.") == ["पंतप्रधान नरेंद्र मोदी", "राष्ट्रपती द्रौपदी मुर्मू"]
    assert claim_names("Chief Minister Devendra Fadnavis said; Deputy CM Eknath Shinde agreed.") == ["Chief Minister Devendra Fadnavis", "Deputy CM Eknath Shinde"]


def test_extract_skips_former_titles_and_non_names():
    assert claim_names("माजी मुख्यमंत्री उद्धव ठाकरे यांनी टीका केली.") == []
    assert claim_names("तत्कालीन मुख्यमंत्री शिंदे उपस्थित होते.") == []
    assert claim_names("मुख्यमंत्री कार्यालयाने निवेदन दिले.") == []
    assert claim_names("former CM Uddhav Thackeray replied.") == []


def fake_answer(rows, sources=("Wikipedia: Chief Minister of Maharashtra",)):
    import json

    return lambda prompt: (json.dumps(rows, ensure_ascii=False), list(sources))


def live(monkeypatch, answer):
    monkeypatch.setenv("OFFICE_LIVE_CHECK", "1")
    monkeypatch.setattr(oc, "_ask_grounded", answer)


def test_a_verdict_against_the_script_becomes_a_repair_message(monkeypatch):
    live(monkeypatch, fake_answer([{"office": "मुख्यमंत्री", "name": "एकनाथ शिंदे", "status": "former", "current_holder": "Devendra Fadnavis", "note": ""}]))
    with pytest.raises(ValueError, match="Devendra Fadnavis"):
        ee.check_offices("मुख्यमंत्री एकनाथ शिंदे यांनी घोषणा केली.")


def test_the_live_answer_wins_over_the_offline_table_after_a_change_of_government(monkeypatch):
    monkeypatch.setattr(content_rules, "static_is_fresh", lambda today=None: True)
    # the table says Shinde is only उपमुख्यमंत्री; the web says he is मुख्यमंत्री today -> the script must pass
    live(monkeypatch, fake_answer([{"office": "मुख्यमंत्री", "name": "एकनाथ शिंदे", "status": "current", "current_holder": "Eknath Shinde", "note": ""}]))
    ee.check_offices("मुख्यमंत्री एकनाथ शिंदे यांनी घोषणा केली.")


def test_a_bad_verdict_without_web_sources_is_ignored(monkeypatch):
    live(monkeypatch, fake_answer([{"office": "मुख्यमंत्री", "name": "एकनाथ शिंदे", "status": "former", "current_holder": "X", "note": ""}], sources=()))
    assert oc.check("मुख्यमंत्री एकनाथ शिंदे", "")[1] == []


def test_results_are_cached(monkeypatch):
    calls = []

    def answer(prompt):
        calls.append(1)
        return fake_answer([{"office": "उपमुख्यमंत्री", "name": "एकनाथ शिंदे", "status": "current", "current_holder": "", "note": ""}])(prompt)

    live(monkeypatch, answer)
    for _ in range(3):
        ee.check_offices("उपमुख्यमंत्री एकनाथ शिंदे म्हणाले.")
    assert len(calls) == 1


def test_unavailable_live_check_falls_back_to_the_table_only_while_it_is_fresh(monkeypatch):
    live(monkeypatch, lambda prompt: None)  # no key / quota / network
    monkeypatch.setattr(content_rules, "static_is_fresh", lambda today=None: True)
    with pytest.raises(ValueError):
        ee.check_offices("मुख्यमंत्री एकनाथ शिंदे यांनी घोषणा केली.")
    monkeypatch.setattr(content_rules, "static_is_fresh", lambda today=None: False)
    ee.check_offices("मुख्यमंत्री एकनाथ शिंदे यांनी घोषणा केली.")  # stale table: never blocks


def test_static_table_expires():
    assert content_rules.static_is_fresh(content_rules.OFFICES_AS_OF)
    assert content_rules.static_is_fresh("2026-12-31")
    assert not content_rules.static_is_fresh("2027-03-01")


def test_not_json_answer_is_skipped(monkeypatch):
    live(monkeypatch, lambda prompt: ("I could not find it", ["x"]))
    assert oc.verify(oc.extract("उपमुख्यमंत्री एकनाथ शिंदे"), "") is None
