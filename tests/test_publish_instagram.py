import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish_instagram as ig  # noqa: E402


class Resp:
    def __init__(self, data=None, status=200, text=""):
        self._data, self.status_code, self.text = data, status, text

    def json(self):
        if self._data is None:
            raise ValueError("no json")
        return self._data


def _env(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_USER_ID", "123")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "tok")


def test_off_unless_exactly_true(monkeypatch):
    for value in ("", "1", "yes", "TRUEE"):
        monkeypatch.setenv("ENABLE_INSTAGRAM", value)
        assert not ig.instagram_enabled()
    monkeypatch.setenv("ENABLE_INSTAGRAM", "true")
    assert ig.instagram_enabled()


def test_caption_has_cta_tags_and_limit():
    story = {"social_caption": "बातमी " * 500, "hashtags": " ".join(f"#t{i}" for i in range(40))}
    text = ig.build_caption(story)
    assert len(text) <= ig.CAPTION_LIMIT
    short = ig.build_caption({"social_caption": "छोटी बातमी.", "hashtags": " ".join(f"#t{i}" for i in range(40))})
    assert "MahaSpark" in short and short.count("#") == 30


def test_missing_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("INSTAGRAM_USER_ID", raising=False)
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    video = tmp_path / "v.mp4"; video.write_bytes(b"x")
    with pytest.raises(RuntimeError, match="must be set"):
        ig.post_reel_to_instagram(str(video), "c", sleep=lambda s: None)


def test_full_flow(monkeypatch, tmp_path):
    _env(monkeypatch)
    video = tmp_path / "v.mp4"; video.write_bytes(b"video-bytes")
    calls = []

    def post(url, **kw):
        calls.append(url)
        if url.endswith("/123/media"):
            assert kw["data"]["media_type"] == "REELS" and kw["data"]["caption"] == "cap"
            return Resp({"id": "c1", "uri": "https://up.example/c1"})
        if url == "https://up.example/c1":
            assert kw["headers"]["file_size"] == "11"
            return Resp({}, 200)
        if url.endswith("/123/media_publish"):
            return Resp({"id": "post9"})
        raise AssertionError(url)

    states = iter([{"status_code": "IN_PROGRESS"}, {"status_code": "FINISHED"}])
    monkeypatch.setattr(ig.requests, "post", post)
    monkeypatch.setattr(ig.requests, "get", lambda url, **kw: Resp(next(states)))
    assert ig.post_reel_to_instagram(str(video), "cap", sleep=lambda s: None) == "post9"
    assert len(calls) == 3


def test_processing_error_and_expired_token(monkeypatch, tmp_path):
    _env(monkeypatch)
    video = tmp_path / "v.mp4"; video.write_bytes(b"x")
    monkeypatch.setattr(ig.requests, "post", lambda url, **kw: Resp({"error": {"code": 190, "message": "Invalid OAuth access token"}}))
    with pytest.raises(RuntimeError, match="expired or is wrong"):
        ig.post_reel_to_instagram(str(video), "c", sleep=lambda s: None)

    def post(url, **kw):
        return Resp({"id": "c1", "uri": "https://up.example/c1"}) if url.endswith("/media") else Resp({}, 200)

    monkeypatch.setattr(ig.requests, "post", post)
    monkeypatch.setattr(ig.requests, "get", lambda url, **kw: Resp({"status_code": "ERROR", "status": "bad codec"}))
    with pytest.raises(RuntimeError, match="bad codec"):
        ig.post_reel_to_instagram(str(video), "c", sleep=lambda s: None)


def test_pipeline_note_never_raises(monkeypatch):
    import pipeline

    monkeypatch.setenv("ENABLE_INSTAGRAM", "")
    assert pipeline.post_reel_to_instagram({}) == ""
    monkeypatch.setenv("ENABLE_INSTAGRAM", "true")
    monkeypatch.setattr(pipeline.publish_instagram, "post_reel_to_instagram", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert pipeline.post_reel_to_instagram({"social_caption": "x"}).startswith(" - Instagram: FAIL boom")
