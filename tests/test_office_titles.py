"""Leaders must never be promoted or demoted: Eknath Shinde is उपमुख्यमंत्री, Devendra Fadnavis is मुख्यमंत्री."""

import pytest

import bulletin_editorial
import content_rules
import editorial_engine as ee
import editorial_prompts


@pytest.mark.parametrize("text", [
    "मुख्यमंत्री एकनाथ शिंदे यांनी आज घोषणा केली.",
    "राज्याचे मुख्यमंत्री शिंदे म्हणाले.",
    "मुख्यमंत्री श्री. एकनाथ शिंदे उपस्थित होते.",
    "Chief Minister Eknath Shinde announced it.",
    "CM Shinde said on Sunday.",
    "उपमुख्यमंत्री देवेंद्र फडणवीस यांनी सांगितले.",
    "उप मुख्यमंत्री फडणवीस यांनी सांगितले.",
    "Deputy CM Devendra Fadnavis said.",
])
def test_wrong_office_is_caught(text):
    assert content_rules.office_error(text)


@pytest.mark.parametrize("text", [
    "उपमुख्यमंत्री एकनाथ शिंदे यांनी आज घोषणा केली.",
    "उप मुख्यमंत्री शिंदे म्हणाले.",
    "माजी मुख्यमंत्री एकनाथ शिंदे यांनी हे काम सुरू केले होते.",
    "तत्कालीन मुख्यमंत्री एकनाथ शिंदे उपस्थित होते.",
    "मुख्यमंत्री देवेंद्र फडणवीस आणि उपमुख्यमंत्री एकनाथ शिंदे यांची बैठक झाली.",
    "Deputy CM Eknath Shinde said.",
    "Chief Minister Devendra Fadnavis said.",
    "माजी मुख्यमंत्री सुशीलकुमार शिंदे यांचे भाषण झाले.",
    "एकनाथ शिंदे यांनी मुख्यमंत्री फडणवीस यांची भेट घेतली.",
    "मुख्यमंत्री फडणवीस यांनी उपमुख्यमंत्री शिंदे यांना बोलावले.",
])
def test_right_office_and_former_titles_pass(text):
    assert content_rules.office_error(text) is None


def test_check_offices_gives_the_model_a_repair_message(monkeypatch):
    monkeypatch.setattr(content_rules, "static_is_fresh", lambda today=None: True)
    with pytest.raises(ValueError, match="उपमुख्यमंत्री"):
        ee.check_offices("मुख्यमंत्री एकनाथ शिंदे यांनी आज घोषणा केली.")
    ee.check_offices("उपमुख्यमंत्री एकनाथ शिंदे यांनी आज घोषणा केली.")


def test_the_prompt_has_the_generic_rule_and_no_hard_coded_holders():
    assert "Never state a leader's office from memory" in editorial_prompts.SYSTEM_INSTRUCTION
    assert "एकनाथ शिंदे is" not in editorial_prompts.SYSTEM_INSTRUCTION  # who holds an office changes; the live check decides


def test_bulletin_item_with_the_wrong_title_is_sent_back_for_repair(monkeypatch):
    monkeypatch.setattr(content_rules, "static_is_fresh", lambda today=None: True)
    item = {
        "approved": True, "category": "राजकारण", "headline": "शिंदे यांची घोषणा", "context": "उपमुख्यमंत्र्यांनी योजना जाहीर केली आहे",
        "tts_text": "मुख्यमंत्री एकनाथ शिंदे यांनी आज नवी योजना जाहीर केली, लाखो नागरिकांना याचा लाभ मिळेल. योजना पुढील महिन्यापासून लागू होईल.",
        "audio_mood": "neutral",
    }
    with pytest.raises(ValueError, match="उपमुख्यमंत्री"):
        bulletin_editorial.validate_item(item, "Deputy CM Eknath Shinde announced a new scheme.")
