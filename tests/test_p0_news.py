"""Cross-workflow acceptance tests. The external transport and AI providers are mocked."""
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Lock
from types import SimpleNamespace

import pytest
import requests
from gspread import WorksheetNotFound

import event_memory as memory
import fetch_news
import media_validation as media
import news
import pipeline
import youtube_upload as youtube
from llm_providers import ContentRejected, LLMUnavailableError
from sheet_queue import IST


class Sheet:
    def __init__(self, book, header=None):
        self.spreadsheet = book
        self.id = 1
        self.rows = [header or []]

    def get_all_values(self):
        return [row[:] for row in self.rows]

    def append_rows(self, rows, **kwargs):
        self.rows.extend(rows)


class Book:
    def __init__(self):
        self.names = set()
        self.lock = Lock()
        self.tabs = {memory.TAB: Sheet(self, ["record_id", "record_json"])}
        self.queue = SimpleNamespace(sheet=Sheet(self))

    def worksheet(self, title):
        if title not in self.tabs:
            raise WorksheetNotFound(title)
        return self.tabs[title]

    def batch_update(self, payload):
        with self.lock:
            command = payload["requests"][0]
            if "addNamedRange" in command:
                if self.names:
                    raise ValueError("Named range already exists.")
                self.names.add(command["addNamedRange"]["namedRange"]["namedRangeId"])
            else:
                self.names.remove(command["deleteNamedRange"]["namedRangeId"])


def event(action="passes water plan", *, date="2026-11-26", summary="Pune council passes a new water plan.",
          facts=None, urls=None):
    return memory.Event(summary=summary, entities=["Pune Municipal Corporation"], location="Pune",
                        date=date, action=action, category="government",
                        facts=facts or ["Council passed the water plan."],
                        urls=urls or ["https://alpha.example/pune", "https://beta.example/pune"])


def fixed_ledger(book):
    return memory.Ledger(book.worksheet(memory.TAB), [], now=lambda: datetime(2026, 11, 26, 8, tzinfo=IST))


def assessment(ev=None, *, long=True, words=50):
    return memory.Assessment(eligible=True, reason="", event=ev or event(),
                             long_form_value=long, corroborated=True, brief_words=words)


def reply(status="different", match="", reason="", new_fact="", evidence_urls=None):
    return memory.Comparison(status=status, match=match, reason=reason, new_fact=new_fact,
                             evidence_urls=evidence_urls or []).model_dump()


@pytest.mark.parametrize("new_title", [
    "पुणे महापालिकेकडून पाणी प्रकल्पाला मंजुरी",
    "City approves additional municipal water infrastructure",
])
def test_same_event_across_languages_publishers_and_urls(monkeypatch, new_title):
    book = Book()
    with memory.Ledger.locked(book.queue) as ledger:
        key = ledger.reserve(event(), "bulletin")
        ledger.begin_publish([key], "bulletin")
        ledger.change([key], "published", published_ids={"youtube": "video-id"})
    with memory.Ledger.locked(book.queue) as ledger:
        assert ledger.records[key]["published_ids"]["youtube"] == "video-id"
        other = event(summary=new_title, urls=["https://different.example/new-headline"])
        monkeypatch.setattr(memory, "generate_json", lambda **kwargs: pytest.fail("Deterministic identity matched"))
        with pytest.raises(memory.DuplicateEvent):
            ledger.reserve(other, "short")


def test_semantic_comparison_and_legitimate_development(monkeypatch):
    ledger = fixed_ledger(Book())
    key = ledger.reserve(event(), "news", "08")
    ledger.begin_publish([key], "news", "08")
    ledger.change([key], "published")
    seen = []

    def judge(**kwargs):
        data = json.loads(kwargs["prompt"])
        assert data["records"][0]["id"] == key
        seen.append(data["candidate"]["action"])
        case = data["candidate"]["action"]
        if case == "greenlights water project":
            response = reply("same", key, "Same act and day in translation")
        elif case == "court stays implementation":
            response = reply("development", key, "Court granted an injunction", "Court granted a stay.",
                             data["candidate"]["urls"])
        else:
            response = reply()
        return kwargs["validate"](response)

    monkeypatch.setattr(memory, "generate_json", judge)
    with pytest.raises(memory.DuplicateEvent):
        ledger.reserve(event("greenlights water project", facts=["The authority approved the scheme."]), "short")
    different = ledger.reserve(event("awards school contract", facts=["New school contract awarded."]), "short")
    assert ledger.records[different]["event_id"] != ledger.records[key]["event_id"]
    ledger.abandon([different])
    follow = ledger.reserve(event("court stays implementation", facts=["Court granted a stay."]), "news", "12")
    assert ledger.records[follow]["event_id"] == ledger.records[key]["event_id"]
    assert ledger.records[follow]["new_fact"] == "Court granted a stay."
    ledger.begin_publish([follow], "news", "12")
    assert seen == ["greenlights water project", "awards school contract", "court stays implementation"]


def test_material_development_needs_independent_evidence(monkeypatch):
    ledger = fixed_ledger(Book())
    key = ledger.reserve(event(), "short")
    ledger.begin_publish([key], "short")
    ledger.change([key], "published")
    monkeypatch.setattr(memory, "generate_json", lambda **kwargs: reply("development", key, "new quote", "quote"))
    with pytest.raises(memory.DuplicateEvent, match="independently"):
        ledger.reserve(event("new quotes on water plan", facts=["A new quotation."]), "news")


def test_lock_and_reservation_are_exclusive_across_workers():
    book = Book()

    def second():
        with memory.Ledger.locked(book.queue):
            pytest.fail("A concurrent worker acquired the transaction lock")

    with memory.Ledger.locked(book.queue) as ledger:
        ledger.reserve(event(), "news")
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(memory.HistoryUnavailable):
                pool.submit(second).result()
    with memory.Ledger.locked(book.queue) as ledger:
        with pytest.raises(memory.DuplicateEvent):
            ledger.reserve(event(), "short")


def test_unavailable_history_prevents_production(monkeypatch):
    book = Book()
    monkeypatch.setattr(book.tabs[memory.TAB], "get_all_values",
                        lambda: (_ for _ in ()).throw(OSError("unavailable")))
    monkeypatch.setattr(news.youtube_upload, "credentials", lambda: None)
    monkeypatch.setattr(news.SheetQueue, "connect", lambda: book.queue)
    monkeypatch.setattr(news.fetch_news, "iter_candidates", lambda: pytest.fail("discovery must not run"))
    with pytest.raises(memory.HistoryUnavailable):
        news.run("08")
    assert not book.names


def test_daily_cap_and_slot_are_checked_before_publication(monkeypatch):
    monkeypatch.setattr(memory, "generate_json", lambda **kw: reply())
    ledger = fixed_ledger(Book())
    for index, slot in enumerate(("08", "12", "16", "20")):
        candidate = event(f"distinct action {index}", facts=[str(index)])
        key = ledger.reserve(candidate, "news", slot)
        ledger.begin_publish([key], "news", slot)
        ledger.change([key], "published")
        with pytest.raises(ContentRejected, match="cap or"):
            ledger.reserve(candidate, "news", slot)
    with pytest.raises(ContentRejected, match="cap or"):
        ledger.reserve(event("fifth story"), "news", "22")


def test_preflight_rechecks_changed_history(monkeypatch):
    monkeypatch.setattr(memory, "generate_json", lambda **kw: reply())
    book = Book()
    ledger = fixed_ledger(book)
    first = ledger.reserve(event(), "short")
    second = ledger.reserve(event("other action", facts=["Different facts."], urls=["https://other.example/new"]), "short")
    other = ledger.records[second]
    ledger.write([{**other, "event": event().model_dump(), "state": "published"}])
    with pytest.raises(memory.DuplicateEvent):
        ledger.begin_publish([first], "short")


def test_publish_failure_retries_only_when_safe(monkeypatch):
    ledger = fixed_ledger(Book())
    story = {"social_title": "title", "social_caption": "text", "seo_keywords": [], "source": {"urls": ["u"]}}
    monkeypatch.setattr(news.youtube_upload, "credentials", lambda: None)
    monkeypatch.setattr(news.media, "video", lambda *args: 245)
    first = ledger.reserve(event(), "news", "08")
    monkeypatch.setattr(news.youtube_upload, "upload_video", lambda *args: (_ for _ in ()).throw(youtube.UploadNotStarted("init")))
    with pytest.raises(youtube.UploadNotStarted):
        news.publish_long(ledger, first, story, "08")
    assert ledger.records[first]["state"] == "failed"
    second = ledger.reserve(event(), "news", "08")
    monkeypatch.setattr(news.youtube_upload, "upload_video", lambda *args: (_ for _ in ()).throw(RuntimeError("unknown")))
    with pytest.raises(RuntimeError, match="unknown"):
        news.publish_long(ledger, second, story, "08")
    ledger.abandon([second])
    assert ledger.records[second]["state"] == "publishing"
    with pytest.raises(memory.DuplicateEvent):
        ledger.reserve(event(), "short")


def test_promoted_news_keeps_event_id_without_vertical_publication(monkeypatch):
    ledger = fixed_ledger(Book())
    candidate = assessment(words=160)
    monkeypatch.setattr(news, "research", lambda *args: (candidate, "evidence"))
    monkeypatch.setattr(news.fetch_news, "resolve_article_url", lambda url: url)
    monkeypatch.setattr(news.fetch_news, "fetch_article_text", lambda url: "test source")
    monkeypatch.setattr(pipeline, "publish_short", lambda *args: pytest.fail("vertical upload"))
    row = SimpleNamespace(index=2, source_url=candidate.event.urls[0], raw_input="Pune - summary")
    assert pipeline.process_row(object(), ledger, row).startswith("Deferred")
    old = next(iter(ledger.records))
    assert ledger.records[old]["state"] == "deferred"
    with pytest.raises(memory.DuplicateEvent):
        ledger.reserve(candidate.event, "bulletin")
    new = ledger.reserve(candidate.event, "news", "08", deferred=old)
    assert ledger.records[new]["event_id"] == old
    ledger.begin_publish([new], "news", "08")


def test_explicit_companion_has_a_published_parent_and_only_one_slot():
    ledger = fixed_ledger(Book())
    original = ledger.reserve(event(), "news")
    with pytest.raises(memory.DuplicateEvent, match="published"):
        ledger.reserve_companion(event(), original, "Tell residents how to apply")
    ledger.begin_publish([original], "news")
    ledger.change([original], "published")
    short = ledger.reserve_companion(event(), original, "Tell residents how to apply")
    assert ledger.records[short]["event_id"] == original
    ledger.begin_publish([short], "short")
    with pytest.raises(memory.DuplicateEvent, match="already"):
        ledger.reserve_companion(event(), original, "Another angle")


@pytest.mark.parametrize(("seconds", "route"), [(14, "skip"), (15, "short"), (30, "short"),
                                                  (31, "condense"), (60, "condense"), (61, "news")])
def test_duration_routing_boundaries(seconds, route):
    assert media.reel_route(seconds) == route


@pytest.mark.parametrize(("seconds", "valid"), [(239, False), (240, True), (300, True), (301, False)])
def test_news_media_duration_boundaries(monkeypatch, tmp_path, seconds, valid):
    def track(kind, **fields):
        return {"codec_type": kind, "codec_name": "codec", "nb_read_packets": "94",
                "duration": str(seconds), **fields}

    monkeypatch.setattr(media, "probe", lambda _: {
        "streams": [track("video", display_aspect_ratio="16:9"), track("audio")],
        "format": {"duration": str(seconds)},
    })
    if valid:
        assert media.video(tmp_path / "landscape.mp4", media.NEWS, (16, 9)) == seconds
    else:
        with pytest.raises(media.InvalidMedia):
            media.video(tmp_path / "landscape.mp4", media.NEWS, (16, 9))


def test_ffprobe_reads_real_file_and_rejects_aspect_and_missing_audio(tmp_path):
    fixture = tmp_path / "vertical.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=90x160:r=10",
                    "-f", "lavfi", "-i", "sine=frequency=400", "-t", "15",
                    "-c:v", "libx264", "-c:a", "aac", str(fixture)], check=True)
    assert media.video(fixture, media.SHORT, (9, 16)) == 15
    assert media.audio_seconds(fixture) == 15
    with pytest.raises(media.InvalidMedia, match="16:9"):
        media.video(fixture, media.SHORT, (16, 9))
    silent = tmp_path / "silent.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(fixture), "-an", "-c:v", "copy", str(silent)], check=True)
    with pytest.raises(media.InvalidMedia, match="audio"):
        media.video(silent, media.SHORT, (9, 16))


def test_measured_condensation_is_bounded_and_only_final_copy_is_rendered(monkeypatch):
    inputs = iter((31, 29))
    drafts = []
    monkeypatch.setattr(news, "voice", lambda story: next(inputs))
    monkeypatch.setattr(news, "write_script", lambda *args, **kwargs: drafts.append(kwargs) or {"id": len(drafts)})
    monkeypatch.setattr(news, "render", lambda story, format: story)
    assert news.produce_short("title", "url", "ref", assessment(words=100)) == {"id": 2}
    assert drafts[1]["previous"] == {"id": 1}


@pytest.mark.parametrize("seconds", [14, 31, 60, 61])
def test_never_renders_an_invalid_short(monkeypatch, seconds):
    monkeypatch.setattr(news, "voice", lambda story: seconds)
    monkeypatch.setattr(news, "write_script", lambda *args, **kwargs: {})
    monkeypatch.setattr(news, "render", lambda *args: pytest.fail("invalid media rendered"))
    error = news.PromoteToNews if seconds == 61 else media.InvalidMedia
    with pytest.raises(error):
        news.produce_short("title", "url", "ref", assessment())


def test_youtube_recovers_ambiguous_final_chunk_without_resending(monkeypatch, tmp_path):
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"12345")
    monkeypatch.setattr(youtube, "credentials", lambda: ("a", "b", "c"))
    monkeypatch.setattr(youtube, "access_token", lambda *args: "test")
    monkeypatch.setattr(youtube.requests, "post", lambda *args, **kwargs:
                        SimpleNamespace(status_code=200, headers={"Location": "https://mock.example"}))
    monkeypatch.setattr(youtube.time, "sleep", lambda delay: None)
    sent = []

    def put(*args, **kwargs):
        sent.append(kwargs["headers"]["Content-Range"])
        if len(sent) == 1:
            raise requests.Timeout
        return SimpleNamespace(status_code=200, json=lambda: {"id": "confirmed"})

    monkeypatch.setattr(youtube.requests, "put", put)
    assert youtube.upload_video(video, "title", "description", []).endswith("confirmed")
    assert sent == ["bytes 0-4/5", "bytes */5"]


def test_default_and_overridden_ist_slots(monkeypatch):
    date = datetime(2026, 11, 26, 12, tzinfo=IST)
    monkeypatch.delenv("NEWS_PUBLISH_HOURS_IST", raising=False)
    assert news.publishing_slot(date) == "12"
    monkeypatch.setenv("NEWS_PUBLISH_HOURS_IST", "6,14,22")
    assert news.publishing_slot(date) is None
    monkeypatch.setenv("NEWS_PUBLISH_HOURS_IST", "12,12")
    with pytest.raises(ValueError, match="distinct"):
        news.publishing_slot(date)


def test_reconcile_reserves_or_releases_the_entire_bulletin_transaction(monkeypatch):
    monkeypatch.setattr(memory, "generate_json", lambda **kwargs: reply())
    ledger = fixed_ledger(Book())
    first = ledger.reserve(event(), "bulletin")
    distinct = event("opens school", facts=["New school opened."], urls=["https://other.example/school"])
    second = ledger.reserve(distinct, "bulletin")
    ledger.begin_publish([first, second], "bulletin")
    memory.resolve(ledger, first, "Confirmed no video in publisher account", {})
    assert ledger.records[second]["state"] == "failed"
    again = ledger.reserve(event(), "bulletin")
    ledger.begin_publish([again], "bulletin")
    memory.resolve(ledger, again, "Confirmed in YouTube Studio", {"youtube": "confirmed-id"})
    with pytest.raises(memory.DuplicateEvent):
        ledger.reserve(event(), "short")


def test_news_prioritizes_quality_and_publishes_at_most_one(monkeypatch):
    book = Book()
    choices = [
        ("public", "public_interest", True),
        ("weak", "politics", False),
        ("political", "politics", True),
    ]
    by_title = {title: assessment(event(action=f"action by {title}", urls=[f"https://a.example/{title}"])
                                  .model_copy(update={"category": category}), long=long)
                for title, category, long in choices}
    monkeypatch.setattr(news.SheetQueue, "connect", lambda: book.queue)
    monkeypatch.setattr(news.youtube_upload, "credentials", lambda: None)
    monkeypatch.setattr(news.fetch_news, "iter_candidates", lambda: iter(
        [fetch_news.Candidate(title, "", f"https://a.example/{title}") for title, _, _ in choices]))
    monkeypatch.setattr(news.fetch_news, "resolve_article_url", lambda url: url)
    monkeypatch.setattr(news.fetch_news, "fetch_article_text", lambda _url: "report")
    monkeypatch.setattr(news, "research", lambda title, *_: (by_title[title], "reports"))
    monkeypatch.setattr(news, "produce_long", lambda title, *_: {"social_title": title})
    monkeypatch.setattr(news.media, "video", lambda *args: 280)
    monkeypatch.setattr(news.pipeline, "render_reel_thumbnail", lambda story: None)
    monkeypatch.setattr(news.send_telegram, "send_message", lambda message: True)
    published = []
    monkeypatch.setattr(news, "publish_long",
                        lambda ledger, key, story, slot: published.append(story["social_title"]) or "watch-url")
    assert news.run("08") == 0
    assert published == ["political"]


def test_assessment_checks_named_source_evidence(monkeypatch):
    reports = [("https://alpha.example/a", "First coverage"),
               ("https://beta.example/b", "Independent coverage")]
    result = assessment(event(urls=["https://alpha.example/a", "https://not-a-source.example/a"]))
    monkeypatch.setattr(memory, "generate_json", lambda **kwargs: result.model_dump())
    assert memory.assess("headline", reports).event.urls == [reports[0][0]]
    assert memory.assess("headline", reports[:1]).event.urls == [reports[0][0]]
    result.event.urls = ["https://not-a-source.example/a"]
    with pytest.raises(ContentRejected, match="supplied supporting source"):
        memory.assess("headline", reports)
    with pytest.raises(ContentRejected, match="At least one readable source"):
        memory.assess("headline", [])
    result.event.urls = [url for url, _ in reports]
    assert memory.assess("headline", reports).event.urls == result.event.urls
