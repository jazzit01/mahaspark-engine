import fetch_news
import pipeline


class FakeQueue:
    def __init__(self):
        self.added = []

    def known_keys(self):
        return set()

    def append_pending(self, raw, url):
        self.added.append((raw, url))


def candidates(n):
    return [fetch_news.Candidate(f"शीर्षक {i}", "सारांश", f"https://news.google.com/rss/articles/{i}") for i in range(n)]


def test_only_stories_with_a_readable_article_are_queued(monkeypatch):
    monkeypatch.setattr(fetch_news, "iter_candidates", lambda: iter(candidates(4)))
    monkeypatch.setattr(fetch_news, "resolve_article_url", lambda link: link.replace("news.google.com/rss/articles", "pub.com/a"))
    # items 0 and 1 cannot be read, 2 and 3 can
    monkeypatch.setattr(fetch_news, "fetch_article_text", lambda url: "x" * 400 if url.endswith(("/2", "/3")) else "")
    queue = FakeQueue()
    assert pipeline.queue_new_items(queue, max_items=2) == 2
    assert [url for _raw, url in queue.added] == ["https://pub.com/a/2", "https://pub.com/a/3"]


def test_unreadable_items_are_never_queued(monkeypatch):
    monkeypatch.setattr(fetch_news, "iter_candidates", lambda: iter(candidates(3)))
    monkeypatch.setattr(fetch_news, "resolve_article_url", lambda link: link)
    monkeypatch.setattr(fetch_news, "fetch_article_text", lambda url: "")
    queue = FakeQueue()
    assert pipeline.queue_new_items(queue) == 0
    assert queue.added == []


def test_scan_stops_after_candidate_limit(monkeypatch):
    seen = []
    monkeypatch.setattr(fetch_news, "iter_candidates", lambda: iter(candidates(40)))
    monkeypatch.setattr(fetch_news, "resolve_article_url", lambda link: link)
    monkeypatch.setattr(fetch_news, "fetch_article_text", lambda url: seen.append(url) or "")
    pipeline.queue_new_items(FakeQueue())
    assert len(seen) == pipeline.MAX_CANDIDATES_TO_CHECK


def test_instagram_is_fully_removed():
    from pathlib import Path

    root = Path(pipeline.__file__).parent.parent
    assert not (root / "scripts" / "publish_instagram.py").exists()
    for path in list((root / "scripts").glob("*.py")) + [root / ".github" / "workflows" / "runner.yml"]:
        assert "instagram" not in path.read_text(encoding="utf-8").lower(), path.name
