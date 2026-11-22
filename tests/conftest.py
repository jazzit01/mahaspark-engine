import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


import pytest


@pytest.fixture(autouse=True)
def _gemini_test_keys(monkeypatch):
    """A key is configured for every test (TTS refuses to run without one) and the per-run TTS state is clean."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
    import editorial_engine

    editorial_engine.reset_tts_state()
    yield
    editorial_engine.reset_tts_state()


@pytest.fixture(autouse=True)
def _no_related_source_search(monkeypatch):
    """Tests never search the web for extra reports of a story."""
    import fetch_news

    monkeypatch.setattr(fetch_news, "related_sources", lambda *a, **k: [])


@pytest.fixture(autouse=True)
def _no_live_office_check(monkeypatch, tmp_path):
    """Tests never call Google Search for office holders; the cache is empty and lives in tmp."""
    import officecheck

    monkeypatch.setenv("OFFICE_LIVE_CHECK", "0")
    monkeypatch.setattr(officecheck, "CACHE_FILE", tmp_path / "office_cache.json")
    officecheck.reset_cache()
    yield
    officecheck.reset_cache()
