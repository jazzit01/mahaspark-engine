import json
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

import bulletin
import bulletin_editorial as be
import youtube_upload as yt
from llm_providers import ContentRejected, LLMUnavailableError

SOURCE = "पुणे महापालिकेने शहरातील पाणीपुरवठा बुधवारी बंद ठेवण्याचा निर्णय घेतला. देखभालीचे काम सकाळी दहा वाजता सुरू होईल. 85% भागात परिणाम."

GOOD = {
    "approved": True,
    "category": "पुणे",
    "headline": "पुण्यात बुधवारी पाणीपुरवठा बंद",
    "context": "महापालिकेच्या देखभाल कामामुळे 85% भागात परिणाम होईल",
    "tts_text": "पुणे महापालिकेने बुधवारी शहरातील पाणीपुरवठा बंद ठेवण्याचा निर्णय घेतला आहे. देखभालीचे काम सकाळी दहा वाजता सुरू होईल, पंच्याऐंशी टक्के भागात परिणाम होईल.",
    "audio_mood": "neutral",
    "visual_query": "water pipeline maintenance",
    "visual_place": "Pune",
    "public_figure": "",
    "seo_keywords": ["पुणे पाणीपुरवठा", "Pune water supply"],
}


def test_valid_item_passes():
    out = be.validate_item(dict(GOOD), SOURCE)
    assert out["headline"] == GOOD["headline"] and out["visual_query"]


def test_rejected_item_raises():
    with pytest.raises(ContentRejected):
        be.validate_item({"approved": False, "rejection_reason": "rumour"}, SOURCE)


@pytest.mark.parametrize(
    "change",
    [
        {"headline": "अ" * 80},
        {"context": "क" * 140},
        {"tts_text": "पुणे पाणी बंद."},
        {"tts_text": GOOD["tts_text"] + " 85 टक्के."},
        {"context": "महापालिकेच्या कामामुळे 97% भागात परिणाम होईल"},
        {"context": "अधिकृत माहितीनुसार पाणीपुरवठा बंद राहणार आहे"},
    ],
)
def test_invalid_items_are_refused(change):
    with pytest.raises(ValueError):
        be.validate_item({**GOOD, **change}, SOURCE)


def test_no_face_for_crime_mood():
    out = be.validate_item({**GOOD, "audio_mood": "crime", "public_figure": "Some Minister"}, SOURCE)
    assert out["public_figure"] == ""


def test_prompt_reuses_reel_rules():
    assert "FACT DISCIPLINE" in be.BULLETIN_INSTRUCTION and "PHONETIC RULES" in be.BULLETIN_INSTRUCTION


# ----- candidate selection -------------------------------------------------------------------


def cand(title, link="https://x/a"):
    return SimpleNamespace(title=title, summary="सारांश " * 20, link=link)


def test_interleave_round_robin():
    assert bulletin.interleave([[1, 2, 3], [4], [5, 6]]) == [1, 4, 5, 2, 6, 3]


def test_duplicate_detection():
    assert bulletin.is_duplicate("पुण्यात पाणीपुरवठा बंद", ["पुण्यात पाणीपुरवठा बंद!"], set())
    assert bulletin.is_duplicate("abc", [], {"abc"})
    assert not bulletin.is_duplicate("मुंबईत पाऊस", ["पुण्यात पाणीपुरवठा बंद"], set())


def patch_news(monkeypatch, writer):
    monkeypatch.setattr(bulletin.fetch_news, "resolve_article_url", lambda link: link)
    monkeypatch.setattr(bulletin.fetch_news, "fetch_article_text", lambda url: "")
    monkeypatch.setattr(bulletin.bulletin_editorial, "write_item", writer)


def test_collect_stops_at_target_and_skips_bad(monkeypatch):
    def writer(title, summary, article, url):
        if "वाईट" in title:
            raise ContentRejected("rumour")
        return {"headline": title, "context": "c", "category": "x", "source": {"url": url}}

    patch_news(monkeypatch, writer)
    cands = [cand(f"वेगळी बातमी क्रमांक {chr(65 + i) * 6}", f"https://x/{i}") for i in range(6)]
    cands.insert(1, cand("वाईट अफवा", "https://x/bad"))
    items = bulletin.collect_items(set(), cands, want=3)
    assert [i["headline"] for i in items] == [cands[0].title, cands[2].title, cands[3].title]


def test_collect_skips_known_and_propagates_llm_outage(monkeypatch):
    patch_news(monkeypatch, lambda *a: {"headline": "h", "context": "c", "category": "x", "source": {}})
    assert bulletin.collect_items({"https://x/a"}, [cand("एक बातमी", "https://x/a")], want=2) == []

    def down(*a):
        raise LLMUnavailableError("no key")

    patch_news(monkeypatch, down)
    with pytest.raises(LLMUnavailableError):
        bulletin.collect_items(set(), [cand("दुसरी बातमी")], want=2)


# ----- voice, props, SEO -----------------------------------------------------------------------


def fake_wav(seconds):
    def tts(text, path):
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(1000)
            w.writeframes(b"\0\0" * int(seconds * 1000))

    return tts


def make_items(n=3):
    return [
        {"category": "पुणे", "headline": f"बातमी {i}", "context": f"संदर्भ {i}", "tts_text": "टेक्स्ट", "seo_keywords": [f"kw{i}"], "source": {"url": f"https://s/{i}"}}
        for i in range(n)
    ]


def test_voices_timing_and_assembly(tmp_path):
    items = bulletin.add_voices(make_items(), tts=fake_wav(6), out_dir=tmp_path)
    assert [i["seconds"] for i in items] == [10.0, 10.0, 10.0]  # padded to the 10 s chapter minimum
    items[0]["seconds"] = 14.0
    props = bulletin.assemble(items, ["credit"])
    assert [e["start"] for e in props["items"]] == [0, 14.0, 24.0]
    assert props["outro_start"] == 34.0 and props["total_seconds"] == 34.0 + bulletin.OUTRO_SECONDS


def test_voice_quota_keeps_voiced_items(tmp_path):
    calls = []

    def tts(text, path):
        calls.append(path)
        if len(calls) == 3:
            raise LLMUnavailableError("quota")
        fake_wav(5)(text, path)

    assert len(bulletin.add_voices(make_items(5), tts=tts, out_dir=tmp_path)) == 2


def test_seo_title_description_tags(tmp_path):
    items = bulletin.add_voices(make_items(4), tts=fake_wav(5), out_dir=tmp_path)
    props = bulletin.assemble(items, ["Photo: A, CC BY, Wikimedia Commons"])
    title = bulletin.build_title([{**items[0], "headline": "अ" * 56}], "सकाळच्या")
    assert len(title) <= 100 and title.endswith("MahaSpark")
    desc = bulletin.build_description(items, props, "सकाळच्या")
    assert desc.splitlines()[3].startswith("0:00 ")  # chapters start at 0:00
    assert "0:10" in desc and "0:40 MahaSpark फॉलो करा" in desc
    assert "Wikimedia Commons" in desc and "https://s/0" in desc and len(desc) < 5000
    tags = bulletin.build_tags(items)
    assert "MahaSpark" in tags and sum(len(t) + 1 for t in tags) < 500


def test_slot_and_timestamp():
    from datetime import datetime

    assert bulletin.slot_for(datetime(2026, 1, 1, 7))[1] == "morning"
    assert bulletin.slot_for(datetime(2026, 1, 1, 17))[1] == "evening"
    assert bulletin.timestamp(125) == "2:05"


def test_telegram_text():
    text = bulletin.build_telegram_text(make_items(2), "सकाळच्या", "https://youtu.be/x", True)
    assert "https://youtu.be/x" in text and "1. बातमी 0" in text
    assert "artifact" in bulletin.build_telegram_text(make_items(1), "सकाळच्या", None, False)


# ----- photos ----------------------------------------------------------------------------------


def test_photos_figure_then_topic(monkeypatch, tmp_path):
    mf = bulletin.media_fetch
    monkeypatch.setattr(mf, "search_commons_photo", lambda n: {"url": "u1", "credit": "c1", "width": 1, "height": 1} if n == "Fig" else None)
    monkeypatch.setattr(mf, "search_commons_topic", lambda q, p, used: {"title": q, "url": "u2", "credit": "c2", "width": 2, "height": 2} if q != "none" else None)
    monkeypatch.setattr(mf, "download", lambda url, dest: True)
    items = make_items(3)
    items[0].update(public_figure="Fig", visual_query="x")
    items[1].update(visual_query="road")
    items[2].update(visual_query="none")
    credits = bulletin.add_photos(items, tmp_path)
    assert credits == ["c1", "c2"] and items[0]["photo"]["is_figure"] and "photo" not in items[2]


def test_photo_errors_are_silent(monkeypatch, tmp_path):
    def boom(*a):
        raise RuntimeError("net")

    monkeypatch.setattr(bulletin.media_fetch, "search_commons_topic", boom)
    items = make_items(1)
    items[0]["visual_query"] = "x"
    assert bulletin.add_photos(items, tmp_path) == [] and "photo" not in items[0]


# ----- YouTube ---------------------------------------------------------------------------------


def test_youtube_metadata_limits(monkeypatch):
    monkeypatch.setenv("YOUTUBE_PRIVACY", "weird")
    meta = yt.build_metadata("t" * 200, "d" * 6000 + "<b>", ["a", "a", "b c"] + ["x" * 50] * 30)
    assert len(meta["snippet"]["title"]) == 100 and len(meta["snippet"]["description"]) <= 5000
    assert meta["status"]["privacyStatus"] == "private" and meta["snippet"]["categoryId"] == "25"
    assert sum(len(t) + 1 for t in meta["snippet"]["tags"]) <= 500


def test_youtube_needs_credentials(monkeypatch, tmp_path):
    for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"):
        monkeypatch.setenv(k, "")
    with pytest.raises(yt.YouTubeUnavailable):
        yt.upload_video(tmp_path / "v.mp4", "t", "d", [])


def test_youtube_upload_flow(monkeypatch, tmp_path):
    for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"):
        monkeypatch.setenv(k, "x")
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0" * 100)
    calls = []

    def resp(code, data=None, headers=None):
        return SimpleNamespace(status_code=code, json=lambda: data or {}, headers=headers or {}, text="")

    def post(url, **kw):
        calls.append(("post", url))
        if url == yt.TOKEN_URL:
            return resp(200, {"access_token": "tok"})
        assert kw["headers"]["Authorization"] == "Bearer tok" and kw["json"]["status"]["selfDeclaredMadeForKids"] is False
        return resp(200, headers={"Location": "https://upload/session"})

    def put(url, **kw):
        calls.append(("put", kw["headers"]["Content-Range"]))
        return resp(200, {"id": "abc123"})

    monkeypatch.setattr(yt.requests, "post", post)
    monkeypatch.setattr(yt.requests, "put", put)
    assert yt.upload_video(video, "t", "d", ["k"]) == "https://www.youtube.com/watch?v=abc123"
    assert ("put", "bytes 0-99/100") in calls


def test_no_secrets_in_new_files():
    for name in ("bulletin.py", "bulletin_editorial.py", "youtube_upload.py"):
        text = (Path(__file__).resolve().parent.parent / "scripts" / name).read_text()
        assert "AIza" not in text and "ya29." not in text and "1//" not in text


def test_main_aborts_when_too_few(monkeypatch):
    monkeypatch.setattr(bulletin.SheetQueue, "connect", classmethod(lambda cls: (_ for _ in ()).throw(RuntimeError("no sheet"))))
    monkeypatch.setattr(bulletin, "gather_candidates", lambda: [])
    assert bulletin.main(["--skip-render"]) == 1
