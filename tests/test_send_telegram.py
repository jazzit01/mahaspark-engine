import send_telegram as tg
from helpers import valid_story


def test_summary_contains_all_5w1h_and_source_url():
    text = tg.build_summary_message(valid_story(), "https://example.com/a?x=1&y=2")
    for label in ("काय घडले", "केव्हा", "कोण", "कुठे", "का", "कसे"):
        assert label in text
    assert "https://example.com/a?x=1&amp;y=2" in text  # HTML-escaped for Telegram


def test_caption_is_within_telegram_limit():
    story = valid_story()
    story["social_caption"] = "क" * 3000
    assert len(tg.build_caption(story)) <= tg.CAPTION_LIMIT


def test_missing_credentials_raise(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    try:
        tg._credentials()
    except RuntimeError as exc:
        assert "TELEGRAM_BOT_TOKEN" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_no_hardcoded_secrets_in_scripts():
    import re
    from pathlib import Path

    pattern = re.compile(r"\d{8,}:[A-Za-z0-9_-]{30,}|EAA[A-Za-z0-9]{20,}")
    for path in Path(tg.__file__).parent.glob("*.py"):
        assert not pattern.search(path.read_text(encoding="utf-8")), path.name
