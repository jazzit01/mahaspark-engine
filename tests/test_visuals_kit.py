import longform
import manual_kit
import topic_images


def test_english_titles_only_from_english_wikipedia():
    urls = ["https://en.wikipedia.org/wiki/Shivneri_Fort", "https://mr.wikipedia.org/wiki/x", "https://example.com/a",
            "https://en.wikipedia.org/wiki/Shivneri_Fort"]
    assert topic_images.english_titles(urls) == ["Shivneri Fort"]


def test_candidate_files_lead_first_and_junk_dropped(monkeypatch):
    page = {"pageimage": "Shivneri_main.jpg", "images": [{"title": "File:Commons-logo.svg"}, {"title": "File:Map of Pune.png"},
                                                         {"title": "File:Gate.jpg"}, {"title": "File:Icon.png"}]}
    monkeypatch.setattr(topic_images, "_api", lambda params: {"query": {"pages": [page]}})
    assert topic_images.candidate_files("Shivneri Fort") == ["File:Shivneri main.jpg", "File:Gate.jpg"]


def test_usable_photos_keeps_free_and_large_only(monkeypatch):
    def info(licence, width, mime="image/jpeg"):
        return {"imageinfo": [{"thumburl": "https://u/x.jpg", "width": width, "thumbwidth": 1600, "thumbheight": 900, "mime": mime,
                               "extmetadata": {"LicenseShortName": {"value": licence}, "Artist": {"value": "<b>Ann</b>"}}}]}

    pages = [{"title": "File:A.jpg", **info("CC BY-SA 4.0", 3000)}, {"title": "File:B.jpg", **info("All rights reserved", 3000)},
             {"title": "File:C.jpg", **info("CC BY 2.0", 500)}, {"title": "File:D.jpg", **info("Public domain", 2000)}]
    monkeypatch.setattr(topic_images, "_api", lambda params: {"query": {"pages": pages}})
    got = topic_images.usable_photos(["File:A.jpg", "File:B.jpg", "File:C.jpg", "File:D.jpg"])
    assert [g["credit"] for g in got] == ["Photo: Ann, CC BY-SA 4.0, Wikimedia Commons", "Photo: Ann, Public domain, Wikimedia Commons"]


def test_fetch_images_downloads_and_never_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(topic_images, "candidate_files", lambda t: ["File:A.jpg"])
    monkeypatch.setattr(topic_images, "usable_photos", lambda f: [{"url": "u", "width": 1600, "height": 900, "credit": "c"}])
    monkeypatch.setattr(topic_images, "download", lambda url, dest: dest.write_bytes(b"x" * 3000) or True)
    got = topic_images.fetch_images(["https://en.wikipedia.org/wiki/Pune"], out_dir=tmp_path)
    assert got == [{"file": "long/photos/photo-1.jpg", "width": 1600, "height": 900, "credit": "c"}]
    monkeypatch.setattr(topic_images, "candidate_files", lambda t: (_ for _ in ()).throw(RuntimeError("network")))
    assert topic_images.fetch_images(["https://en.wikipedia.org/wiki/Pune"], out_dir=tmp_path) == []
    assert topic_images.fetch_images(["https://example.com"], out_dir=tmp_path) == []


def test_attach_photos_spreads_over_scenes_and_keeps_credits():
    props = {"scenes": [{"kind": "title"} for _ in range(8)]}
    photos = [{"file": f"long/photos/photo-{i}.jpg", "width": 1600, "height": 900, "credit": f"c{i}"} for i in (1, 2, 3, 4)]
    longform.attach_photos(props, photos)
    files = [s["media"]["file"][-11:] for s in props["scenes"]]
    assert files == ["photo-1.jpg", "photo-1.jpg", "photo-2.jpg", "photo-2.jpg", "photo-3.jpg", "photo-3.jpg", "photo-4.jpg", "photo-4.jpg"]
    assert props["credits"] == ["c1", "c2", "c3", "c4"]
    assert longform.attach_photos({"scenes": [{}]}, []) == {"scenes": [{}]}


def test_studio_is_rotated_and_never_the_grave_one():
    names = {longform.pick_studio(f"title {i}") for i in range(40)}
    assert "BreakingNewsStudio" not in names and len(names) >= 2
    assert longform.assemble("quiz", "t", [{"seconds": 5}], 0)["studio"] in names | {"PrimeGridStudio"}


def test_manual_kit_writes_file_and_tells_telegram(monkeypatch, tmp_path):
    import send_telegram

    sent = []
    monkeypatch.setattr(manual_kit, "KIT_PATH", tmp_path / "kit.txt")
    monkeypatch.setattr(send_telegram, "send_message", lambda text: sent.append(("msg", text)) or True)
    monkeypatch.setattr(send_telegram, "send_document", lambda p, c="": sent.append(("doc", str(p))) or True)
    monkeypatch.setattr(send_telegram, "send_video_file", lambda p, c="": sent.append(("video", str(p))) or True)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x" * 100)
    path = manual_kit.deliver("क्विझ", video, "Title <b>", "Desc line", ["a", "b"], "invalid_grant", send=True)
    text = path.read_text(encoding="utf-8")
    assert "TITLE\nTitle <b>" in text and "DESCRIPTION\nDesc line" in text and "TAGS\na, b" in text
    kinds = [k for k, _ in sent]
    assert kinds == ["msg", "doc", "video"] and "&lt;b&gt;" in sent[0][1]
    sent.clear()
    big = tmp_path / "big.mp4"
    big.write_bytes(b"x")
    monkeypatch.setattr(send_telegram, "MAX_VIDEO_BYTES", 0)
    manual_kit.deliver("क्विझ", big, "T", "D", [], "no creds", send=True)
    assert [k for k, _ in sent] == ["msg", "doc", "msg"]
    sent.clear()
    manual_kit.deliver("क्विझ", big, "T", "D", [], "x", send=False)
    assert sent == []


def test_remotion_hooks_are_never_called_conditionally():
    """React error #310 (a render stopped at frame 938): a hook inside `cond ? ... : ...` or `cond && ...` changes the hook count between frames."""
    import re

    from config import ROOT

    bad = []
    for path in (ROOT / "remotion/src").rglob("*.tsx"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("//")[0]
            if re.search(r"(\?|&&|\|\|)[^;:]*\buse(Seconds|Reveal|CurrentFrame|VideoConfig|Layout)\(", code):
                bad.append(f"{path.name}:{n}")
    assert not bad, bad

def test_line_art_studios_are_in_the_rotation_and_exist_in_remotion():
    from config import ROOT

    names = {longform.pick_studio(f"title {i}") for i in range(200)}
    assert set(longform.LINE_STUDIOS["explainer"]) <= names
    assert "BreakingNewsStudio" not in names
    registry = (ROOT / "remotion/src/studios/index.ts").read_text(encoding="utf-8")
    for n in longform.LINE_STUDIOS["quiz"]:
        assert n in registry
        assert (ROOT / f"remotion/src/studios/{n}.tsx").exists()


def test_aurora_and_orbit_studios_are_explainer_only_and_registered():
    from config import ROOT

    assert {"AuroraStudio", "OrbitStudio"} <= set(longform.LINE_STUDIOS["explainer"])
    assert not {"AuroraStudio", "OrbitStudio"} & set(longform.LINE_STUDIOS["quiz"])
    registry = (ROOT / "remotion/src/studios/index.ts").read_text(encoding="utf-8")
    types = (ROOT / "remotion/src/types.ts").read_text(encoding="utf-8")
    theme = (ROOT / "remotion/src/theme.ts").read_text(encoding="utf-8")
    for n in ("AuroraStudio", "OrbitStudio"):
        assert n in registry and n in types and n in theme
        assert (ROOT / f"remotion/src/studios/{n}.tsx").exists()
    video = (ROOT / "remotion/src/long/LongVideo.tsx").read_text(encoding="utf-8")
    assert "SceneSweep" in video and "'explainer'" in video
