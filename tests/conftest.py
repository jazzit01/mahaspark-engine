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
