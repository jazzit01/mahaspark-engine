import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish_facebook as fb  # noqa: E402


class Resp:
    def __init__(self, data=None, status=200, text=""):
        self._data, self.status_code, self.text = data, status, text

    def json(self):
        if self._data is None:
            raise ValueError("no json")
        return self._data


def _env(monkeypatch):
    monkeypatch.setenv("FACEBOOK_PAGE_ID", "55")
    monkeypatch.setenv("FACEBOOK_PAGE_ACCESS_TOKEN", "tok")


def test_off_unless_exactly_true(monkeypatch):
    for value in ("", "1", "yes", "TRUEE"):
        monkeypatch.setenv("ENABLE_FACEBOOK", value)
        assert not fb.facebook_enabled()
    monkeypatch.setenv("ENABLE_FACEBOOK", "true")
    assert fb.facebook_enabled()


def test_only_vertical_videos_of_3_to_90_seconds_qualify():
    assert fb.reel_skip_reason({"format": "portrait", "duration_seconds": 40}) is None
    assert fb.reel_skip_reason({"format": "portrait"}) is None
    assert "9:16" in fb.reel_skip_reason({"duration_seconds": 60})
    assert "outside" in fb.reel_skip_reason({"format": "portrait", "duration_seconds": 120})
    assert "outside" in fb.reel_skip_reason({"format": "portrait", "duration_seconds": 2})


def test_missing_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("FACEBOOK_PAGE_ID", raising=False)
    monkeypatch.delenv("FACEBOOK_PAGE_ACCESS_TOKEN", raising=False)
    video = tmp_path / "v.mp4"; video.write_bytes(b"x")
    with pytest.raises(RuntimeError, match="must be set"):
        fb.post_reel_to_facebook(str(video), "d", sleep=lambda s: None)


def test_full_flow(monkeypatch, tmp_path):
    _env(monkeypatch)
    video = tmp_path / "v.mp4"; video.write_bytes(b"video-bytes")
    seen = []

    def post(url, **kw):
        seen.append(url)
        if url.endswith("/55/video_reels") and kw["json"]["upload_phase"] == "start":
            return Resp({"video_id": "v1", "upload_url": "https://up.example/v1"})
        if url == "https://up.example/v1":
            assert kw["headers"]["file_size"] == "11" and kw["headers"]["Authorization"] == "OAuth tok"
            return Resp({"success": True})
        if url.endswith("/55/video_reels"):
            body = kw["json"]
            assert body["upload_phase"] == "finish" and body["video_state"] == "PUBLISHED"
            assert body["video_id"] == "v1" and body["description"] == "desc" and body["is_ai_generated"] is True
            return Resp({"success": True})
        raise AssertionError(url)

    states = iter([{"status": {"video_status": "processing"}}, {"status": {"video_status": "ready"}}])
    monkeypatch.setattr(fb.requests, "post", post)
    monkeypatch.setattr(fb.requests, "get", lambda url, **kw: Resp(next(states)))
    assert fb.post_reel_to_facebook(str(video), "desc", sleep=lambda s: None) == "v1"
    assert len(seen) == 3


def test_errors_are_explained(monkeypatch, tmp_path):
    _env(monkeypatch)
    video = tmp_path / "v.mp4"; video.write_bytes(b"x")
    monkeypatch.setattr(fb.requests, "post", lambda url, **kw: Resp({"error": {"code": 190, "message": "Invalid OAuth access token"}}))
    with pytest.raises(RuntimeError, match="expired or is wrong"):
        fb.post_reel_to_facebook(str(video), "d", sleep=lambda s: None)

    def post(url, **kw):
        return Resp({"video_id": "v1"}) if "upload_phase" in kw.get("json", {}) else Resp({"success": True})

    monkeypatch.setattr(fb.requests, "post", post)
    monkeypatch.setattr(fb.requests, "get", lambda url, **kw: Resp({"status": {"video_status": "error"}}))
    with pytest.raises(RuntimeError, match="could not process"):
        fb.post_reel_to_facebook(str(video), "d", sleep=lambda s: None)


def test_pipeline_note_skips_wide_videos_and_never_raises(monkeypatch):
    import pipeline

    monkeypatch.setenv("ENABLE_FACEBOOK", "")
    assert pipeline.post_reel_to_facebook({"format": "portrait"}) == ""
    monkeypatch.setenv("ENABLE_FACEBOOK", "true")
    assert pipeline.post_reel_to_facebook({"duration_seconds": 60}) == ""  # 16:9 is not a Facebook Reel
    monkeypatch.setattr(pipeline.publish_facebook, "post_reel_to_facebook", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert pipeline.post_reel_to_facebook({"format": "portrait", "social_caption": "x"}).startswith(" - Facebook: FAIL boom")
