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


def test_tts_failure_falls_back_to_a_voiceless_story(monkeypatch, tmp_path):
    import json

    import editorial_engine
    from helpers import valid_story
    from llm_providers import LLMUnavailableError

    story = valid_story()
    story["tts_narration_script"] = " ".join(s["tts_text"] for s in story["scenes"])
    story_path = tmp_path / "story.json"
    story_path.write_text(json.dumps(story, ensure_ascii=False), encoding="utf-8")
    voice_path = tmp_path / "voiceover.wav"
    voice_path.write_bytes(b"stale")

    monkeypatch.setattr(pipeline, "STORY_PATH", story_path)
    monkeypatch.setattr(pipeline, "VOICEOVER_PATH", voice_path)
    monkeypatch.setattr(editorial_engine, "synthesize_voiceover", lambda *a, **k: (_ for _ in ()).throw(LLMUnavailableError("no tts")))

    result = pipeline.add_voice_and_timings(story)
    assert result["audio"] is False and not voice_path.exists()
    assert json.loads(story_path.read_text(encoding="utf-8"))["words"]


def test_deliver_marks_voiceless_posts(monkeypatch):
    monkeypatch.setattr(pipeline.send_telegram, "send_reel", lambda *a, **k: True)
    assert pipeline.deliver({"audio": False}, "u") == "SUCCESS (voiceless) - Telegram: OK"
    assert pipeline.deliver({"audio": True}, "u") == "SUCCESS - Telegram: OK"


def test_render_concurrency_never_exceeds_cpu_cores(monkeypatch):
    monkeypatch.setattr(pipeline.os, "cpu_count", lambda: 2)
    monkeypatch.delenv("REMOTION_CONCURRENCY", raising=False)
    assert pipeline.render_concurrency() == 2  # default: all cores
    monkeypatch.setenv("REMOTION_CONCURRENCY", "3")
    assert pipeline.render_concurrency() == 2  # the value that crashed the CI run is capped
    monkeypatch.setenv("REMOTION_CONCURRENCY", "1")
    assert pipeline.render_concurrency() == 1
    monkeypatch.setenv("REMOTION_CONCURRENCY", "abc")
    assert pipeline.render_concurrency() == 2
    monkeypatch.setattr(pipeline.os, "cpu_count", lambda: None)
    assert pipeline.render_concurrency() == 1


class RunQueue(FakeQueue):
    def __init__(self, rows):
        super().__init__()
        self.rows = rows
        self.statuses = {}

    def pending_rows(self):
        return self.rows

    def set_status(self, row, status, note=None):
        self.statuses[row] = status


def _run_with_rows(monkeypatch, produce):
    from sheet_queue import PendingRow

    queue = RunQueue([PendingRow(i, f"शीर्षक {i} - सारांश", "https://pub.com/x") for i in (1, 2, 3)])
    monkeypatch.setattr(pipeline.SheetQueue, "connect", classmethod(lambda cls: queue))
    monkeypatch.setattr(pipeline, "queue_new_items", lambda q: 0)
    monkeypatch.setattr(pipeline.time, "sleep", lambda _s: None)
    monkeypatch.setattr(pipeline, "MAX_STORIES_PER_RUN", 1)
    monkeypatch.setattr(pipeline.fetch_news, "resolve_article_url", lambda u: u)
    monkeypatch.setattr(pipeline.fetch_news, "fetch_article_text", lambda u: "x" * 400)
    monkeypatch.setattr(pipeline, "produce_reel", produce)
    monkeypatch.setattr(pipeline, "deliver", lambda story, url: "SUCCESS - Telegram: OK")
    monkeypatch.setattr(queue, "write_story", lambda *a, **k: None, raising=False)
    return pipeline.run_scheduled(), queue


def test_a_failing_story_counts_toward_the_run_limit(monkeypatch):
    def boom(*a):
        raise RuntimeError("Remotion render failed")

    code, queue = _run_with_rows(monkeypatch, boom)
    assert queue.statuses.get(1) == "ERROR"
    assert 2 not in queue.statuses and 3 not in queue.statuses  # the other rows were not touched or spent
    assert code == 1  # the workflow run shows as failed


def test_successful_story_exits_cleanly(monkeypatch):
    code, queue = _run_with_rows(monkeypatch, lambda *a: {"audio": True})
    assert queue.statuses.get(1) == "DONE" and 2 not in queue.statuses
    assert code == 0
