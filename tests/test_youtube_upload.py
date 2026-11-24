

def test_short_description_is_tagged_and_shorts_can_be_switched_off(monkeypatch):
    import youtube_upload as yt

    story = {"social_caption": "बातमी.", "hashtags": "#MahaSpark"}
    assert "#Shorts" not in yt.build_reel_description(story)
    assert yt.build_reel_description(story, short=True).endswith("#Shorts")
    monkeypatch.delenv("YOUTUBE_UPLOAD_SHORTS", raising=False)
    assert yt.shorts_uploads_enabled()
    monkeypatch.setenv("YOUTUBE_UPLOAD_SHORTS", "0")
    assert not yt.shorts_uploads_enabled()


def test_short_uploads_share_the_slots_and_skip_the_thumbnail(monkeypatch, tmp_path):
    import pipeline
    import youtube_upload as yt

    calls = {}
    monkeypatch.setattr(yt, "credentials", lambda: ("a", "b", "c"))
    monkeypatch.setattr(yt, "upload_video", lambda path, title, desc, tags: calls.update(desc=desc, tags=tags) or "https://youtu.be/x")
    monkeypatch.setattr(pipeline, "render_reel_thumbnail", lambda story: (_ for _ in ()).throw(AssertionError("no thumbnail for a Short")))

    class Q:
        def youtube_reel_uploads_today(self, day):
            return 0

    class Hour:
        hour = 13

        def strftime(self, fmt):
            return "2026-11-25"

    class DT:
        @staticmethod
        def now(tz):
            return Hour()

    monkeypatch.setattr(pipeline, "datetime", DT)
    short = {"format": "portrait", "social_title": "शीर्षक", "social_caption": "x", "hashtags": "#MahaSpark", "scenes": [{"headline": "h"}]}
    note = pipeline.upload_reel_to_youtube(Q(), short)
    assert "YouTube: OK 2026-11-25" in note and "#Shorts" in calls["desc"] and "Shorts" in calls["tags"]
    monkeypatch.setenv("YOUTUBE_UPLOAD_SHORTS", "0")
    assert pipeline.upload_reel_to_youtube(Q(), short) == ""
