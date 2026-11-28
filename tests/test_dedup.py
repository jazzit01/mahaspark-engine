import pytest

import dedup
from llm_providers import ContentRejected


class FakeSheet:
    def __init__(self, rows):
        self.rows, self.spreadsheet = rows, self

    def get_all_values(self):
        return self.rows

    def worksheet(self, name):
        raise RuntimeError("no such tab")


class FakeQueue:
    def __init__(self, rows):
        self.sheet = FakeSheet(rows)


def row(status, raw, url="", note=""):
    cells = [""] * 16
    cells[0], cells[1], cells[13] = status, raw, url
    return cells


HEADER = [["Status", "Raw"]]


def test_history_has_only_done_rows_newest_last():
    queue = FakeQueue(HEADER + [row("DONE", "पहिली - सारांश", "https://a.com/1"), row("PENDING", "तिसरी"),
                                row("REJECTED", "दुसरी"), row("DONE", "चौथी - सारांश", "https://a.com/4")])
    assert dedup.recent_history(queue) == [("पहिली", "https://a.com/1"), ("चौथी", "https://a.com/4")]


def test_same_source_url_is_a_duplicate_without_any_model_call(monkeypatch):
    monkeypatch.setattr(dedup, "generate_json", lambda **kw: pytest.fail("no model call expected"))
    with pytest.raises(dedup.DuplicateEvent):
        dedup.check("नवी हेडलाईन", "", "https://www.a.com/1/?utm_source=x", [("जुनी", "https://a.com/1")])


def test_same_event_with_a_different_headline_is_blocked(monkeypatch):
    monkeypatch.setattr(dedup, "generate_json",
                        lambda **kw: {"same_event": True, "match": 1, "new_development": False, "reason": "same attack"})
    with pytest.raises(ContentRejected):
        dedup.check("Different words", "other summary", "https://b.com/9", [("मूळ बातमी", "https://a.com/1")])


def test_new_development_and_different_events_pass(monkeypatch):
    monkeypatch.setattr(dedup, "generate_json",
                        lambda **kw: {"same_event": False, "match": 0, "new_development": True, "reason": "arrest"})
    dedup.check("आरोपीला अटक", "", "https://b.com/9", [("हल्ला", "https://a.com/1")])


def test_empty_history_needs_no_model_call(monkeypatch):
    monkeypatch.setattr(dedup, "generate_json", lambda **kw: pytest.fail("no model call expected"))
    dedup.check("पहिली बातमी", "", "https://b.com/9", [])


def test_a_made_up_match_number_is_rejected_by_the_validator(monkeypatch):
    def fake(**kw):
        with pytest.raises(ValueError):
            kw["validate"]({"same_event": True, "match": 7, "reason": ""})
        return {"same_event": False, "match": 0}

    monkeypatch.setattr(dedup, "generate_json", fake)
    dedup.check("x", "", "https://b.com/9", [("a", "https://a.com/1")])
