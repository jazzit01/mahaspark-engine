import get_youtube_token as g


def test_auth_url_asks_for_offline_upload_access():
    url = g.auth_url("id123", "http://127.0.0.1:5555")
    assert "client_id=id123" in url and "access_type=offline" in url and "prompt=consent" in url
    assert "youtube.upload" in url and "127.0.0.1%3A5555" in url


def test_exchange_needs_a_refresh_token(monkeypatch):
    class R:
        status_code = 200

        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

    monkeypatch.setattr(g.requests, "post", lambda *a, **k: R({"access_token": "a"}))
    try:
        g.exchange("c", "i", "s", "r")
        raise AssertionError("should fail")
    except RuntimeError:
        pass
    monkeypatch.setattr(g.requests, "post", lambda *a, **k: R({"refresh_token": "rt"}))
    assert g.exchange("c", "i", "s", "r")["refresh_token"] == "rt"
