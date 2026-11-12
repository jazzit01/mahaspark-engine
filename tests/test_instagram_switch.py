import importlib
import sys
import types

import pytest

# sheet_processor pulls in Google Sheets, video and browser libraries at import time. The switch
# under test does not need any of them, so stand-in modules keep this test fast and dependency free.
HEAVY_MODULES = [
    "gspread",
    "image_generator",
    "news_fetcher",
    "renderer",
    "video_renderer",
    "telegram_notifier",
]


@pytest.fixture()
def sheet_processor(monkeypatch):
    for name in HEAVY_MODULES:
        if name not in sys.modules:
            monkeypatch.setitem(sys.modules, name, types.SimpleNamespace(
                generate_ai_background=None, fetch_and_queue_news=None,
                render_news_tile=None, create_news_reel=None, send_news_video=None,
            ))
    monkeypatch.delitem(sys.modules, "sheet_processor", raising=False)
    monkeypatch.delitem(sys.modules, "instagram_publisher", raising=False)
    module = importlib.import_module("sheet_processor")
    yield module
    sys.modules.pop("sheet_processor", None)


def test_instagram_is_off_by_default(sheet_processor, monkeypatch):
    monkeypatch.delenv("ENABLE_INSTAGRAM", raising=False)
    assert sheet_processor.instagram_enabled() is False


def test_empty_value_from_github_actions_stays_off(sheet_processor, monkeypatch):
    monkeypatch.setenv("ENABLE_INSTAGRAM", "")
    assert sheet_processor.instagram_enabled() is False


def test_only_true_turns_it_on(sheet_processor, monkeypatch):
    cases = [("true", True), ("TRUE", True), (" true ", True), ("1", False), ("yes", False), ("false", False)]
    for value, expected in cases:
        monkeypatch.setenv("ENABLE_INSTAGRAM", value)
        assert sheet_processor.instagram_enabled() is expected, value


def test_importing_sheet_processor_does_not_load_instagram_module(sheet_processor):
    assert "instagram_publisher" not in sys.modules
