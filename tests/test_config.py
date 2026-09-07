import os
from pathlib import Path

from config import get_env_value, load_env_file


def test_load_env_file_sets_values(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("GEMINI_API_KEY=test-key\nAPP_MODE=preview\n", encoding="utf-8")

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("APP_MODE", raising=False)

    load_env_file(env_path)

    assert os.getenv("GEMINI_API_KEY") == "test-key"
    assert os.getenv("APP_MODE") == "preview"


def test_get_env_value_uses_default_when_missing(monkeypatch):
    monkeypatch.delenv("NOT_SET_VALUE", raising=False)

    assert get_env_value("NOT_SET_VALUE", "fallback") == "fallback"
    assert get_env_value("NOT_SET_VALUE", "") == ""
