import send_telegram as tg
from helpers import valid_story


def test_summary_contains_all_5w1h_and_source_url():
    text = tg.build_summary_message(valid_story(), "https://example.com/a?x=1&y=2")
    for label in ("काय घडले", "केव्हा", "कोण", "कुठे", "का", "कसे"):
        assert label in text
    assert "https://example.com/a?x=1&amp;y=2" in text  # HTML-escaped for Telegram


def test_video_is_sent_without_a_caption_and_with_its_real_size(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    sent = []

    class Resp:
        status_code = 200
        text = ""

    monkeypatch.setattr(tg.requests, "post", lambda url, data=None, **kw: sent.append((url, dict(data))) or Resp())
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    story = valid_story()
    assert tg.send_reel(video, {**story, "format": "portrait"}, "https://src")
    assert tg.send_reel(video, {**story, "format": "landscape"}, "https://src")
    videos = [d for u, d in sent if u.endswith("/sendVideo")]
    assert all("caption" not in d for d in videos)
    assert (videos[0]["width"], videos[0]["height"]) == (1080, 1920) and (videos[1]["width"], videos[1]["height"]) == (1920, 1080)
    messages = [d for u, d in sent if u.endswith("/sendMessage")]
    assert len(messages) == 2 and all("Title (SEO)" in m["text"] and "Tags" in m["text"] for m in messages)


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


def test_chat_id_defaults_to_previous_working_chat(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert tg._credentials() == ("token", "935514943")


def test_chat_id_can_be_overridden(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    assert tg._credentials() == ("token", "42")


def test_summary_mentions_when_the_reel_is_voiceless():
    story = valid_story()
    assert "व्हॉइसओव्हर उपलब्ध नव्हता" not in tg.build_summary_message(story, "u")
    story["audio"] = False
    assert "व्हॉइसओव्हर उपलब्ध नव्हता" in tg.build_summary_message(story, "u")


def test_reel_caption_and_description_carry_the_follow_cta():
    import send_telegram as st

    story = {"social_title": "शीर्षक", "social_caption": "वर्णन", "category": "पुणे", "hashtags": "#MahaSpark", "five_w_one_h": {}, "scenes": []}
    message = st.build_summary_message(story, "https://src")
    assert "@MahaSparkOfficial" in message and "सबस्क्राईब" in message
