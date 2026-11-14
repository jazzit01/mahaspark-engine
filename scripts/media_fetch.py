"""Per-scene visuals for the reel.

Two sources, both with licences that allow reuse:

* **Pexels videos** (needs ``PEXELS_API_KEY``): portrait stock footage matched to each scene's
  ``visual_query`` (a few English keywords the editorial model wrote for what the scene is about).
* **Wikimedia Commons photos**: a freely licensed (CC / public domain) portrait of the public figure the
  story is about (``story["public_figure"]``). Only used for non-grave stories, see ``editorial_engine``.

Stock footage is *representative*, not footage of the actual event, so the Telegram summary says so. Anything
that cannot be found or downloaded is simply skipped: a scene without media keeps the animated studio
background, and the story is never dropped because of a missing visual.

``attach_media`` writes ``scenes[i].media`` and ``media_credits`` into ``story.json``; the Remotion project
reads them (``remotion/src/Backdrop.tsx``).
"""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

import requests

from config import MEDIA_DIR, PUBLIC_DIR, STORY_PATH, get_env_value

PEXELS_SEARCH = "https://api.pexels.com/videos/search"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "MahaSparkEngine/1.0 (Marathi news reel pipeline; contact via the project repository)"
MAX_DOWNLOAD_BYTES = 30 * 1024 * 1024
MAX_CLIP_SECONDS = 45
MIN_PHOTO_WIDTH = 600
FREE_LICENCE = re.compile(r"^(cc[ -]|cc0|public domain|pd[ -]|attribution)", re.IGNORECASE)


# ----- Pexels stock footage --------------------------------------------------------------------


def pick_video_file(video: dict) -> dict | None:
    """The mp4 rendition that fits a 1080x1920 frame best: the smallest file that is at least 1280 px high."""
    files = [f for f in video.get("video_files", []) if str(f.get("file_type", "")).endswith("mp4") and f.get("link")]
    if not files:
        return None
    tall_enough = [f for f in files if int(f.get("height") or 0) >= 1280]
    if tall_enough:
        return min(tall_enough, key=lambda f: int(f.get("width") or 0) * int(f.get("height") or 0))
    return max(files, key=lambda f: int(f.get("width") or 0) * int(f.get("height") or 0))


def search_pexels(query: str, api_key: str, exclude_ids: set[int]) -> dict | None:
    resp = requests.get(
        PEXELS_SEARCH,
        headers={"Authorization": api_key},
        params={"query": query, "orientation": "portrait", "size": "medium", "per_page": 12},
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Pexels HTTP {resp.status_code}: {resp.text[:120]}")
    for video in resp.json().get("videos", []):
        if video.get("id") in exclude_ids:
            continue
        duration = float(video.get("duration") or 0)
        file = pick_video_file(video)
        if not file or not (2 <= duration <= MAX_CLIP_SECONDS):
            continue
        author = (video.get("user") or {}).get("name") or "Pexels contributor"
        return {
            "id": video.get("id"),
            "url": file["link"],
            "duration": duration,
            "credit": f"Video: {author} / Pexels",
        }
    return None


# ----- Wikimedia Commons portraits -------------------------------------------------------------


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", value or ""))).strip()


def search_commons_photo(name: str) -> dict | None:
    """A freely licensed photo of ``name`` from Wikimedia Commons, or None. The file name must contain the
    person's surname, so a loosely related picture is never used."""
    surname = re.sub(r"[^a-z]", "", name.split()[-1].lower()) if name.split() else ""
    if len(surname) < 3:
        return None
    resp = requests.get(
        COMMONS_API,
        headers={"User-Agent": USER_AGENT},
        params={
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": f"{name} filetype:bitmap",
            "gsrnamespace": 6,
            "gsrlimit": 12,
            "prop": "imageinfo",
            "iiprop": "url|size|extmetadata",
            "iiurlwidth": 1080,
        },
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Commons HTTP {resp.status_code}")
    pages = sorted((resp.json().get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    for page in pages:
        title = str(page.get("title", ""))
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        licence = _plain((meta.get("LicenseShortName") or {}).get("value", ""))
        thumb = info.get("thumburl") or info.get("url")
        if surname not in re.sub(r"[^a-z]", "", title.lower()) or not thumb:
            continue
        if not title.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        if not FREE_LICENCE.match(licence) or int(info.get("width") or 0) < MIN_PHOTO_WIDTH:
            continue
        artist = _plain((meta.get("Artist") or {}).get("value", "")) or "Unknown author"
        return {"url": thumb, "credit": f"Photo: {artist[:60]}, {licence}, Wikimedia Commons"}
    return None


# ----- download and attach ---------------------------------------------------------------------


def download(url: str, dest: Path) -> bool:
    """Stream ``url`` to ``dest`` (size capped). Returns False on any failure."""
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=45) as resp:
            if resp.status_code != 200:
                return False
            size = 0
            with open(tmp, "wb") as handle:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    size += len(chunk)
                    if size > MAX_DOWNLOAD_BYTES:
                        tmp.unlink(missing_ok=True)
                        return False
                    handle.write(chunk)
        if size < 2048:
            tmp.unlink(missing_ok=True)
            return False
        tmp.replace(dest)
        return True
    except requests.RequestException:
        tmp.unlink(missing_ok=True)
        return False


def figure_scene_indexes(count: int) -> list[int]:
    """Scenes that show the public figure's photo: the hook and, in a longer story, the closing scene."""
    return [0] if count < 4 else [0, count - 1]


def attach_media(story: dict, story_path: Path = STORY_PATH, media_dir: Path = MEDIA_DIR) -> dict:
    """Find and download visuals for every scene, then write them into ``story_path``. Never raises."""
    scenes = story.get("scenes", [])
    shutil.rmtree(media_dir, ignore_errors=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    api_key = get_env_value("PEXELS_API_KEY")
    figure = str(story.get("public_figure", "")).strip()
    used_ids: set[int] = set()
    credits: list[str] = []
    attached = 0

    photo_file = None
    if figure:
        try:
            found = search_commons_photo(figure)
            if found and download(found["url"], media_dir / "figure.jpg"):
                photo_file = {"file": "media/figure.jpg", "credit": found["credit"]}
                print(f"🧑‍💼 Public-figure photo found for {figure}: {found['credit']}")
            else:
                print(f"ℹ️ No freely licensed photo found for {figure}; using footage only.")
        except Exception as exc:  # noqa: BLE001
            print(f"ℹ️ Public-figure photo lookup failed ({str(exc)[:100]}); using footage only.")

    photo_scenes = set(figure_scene_indexes(len(scenes))) if photo_file else set()

    if not api_key and not photo_file:
        print("ℹ️ PEXELS_API_KEY is not set and no photo was found: the reel keeps its studio backgrounds.")

    for idx, scene in enumerate(scenes):
        scene.pop("media", None)
        if idx in photo_scenes:
            scene["media"] = {"type": "image", "file": photo_file["file"], "credit": photo_file["credit"], "source": "commons"}
            credits.append(photo_file["credit"])
            attached += 1
            continue
        query = str(scene.get("visual_query", "")).strip()
        if not (api_key and query):
            continue
        try:
            clip = search_pexels(query, api_key, used_ids)
            if clip and download(clip["url"], media_dir / f"scene-{idx}.mp4"):
                used_ids.add(clip["id"])
                scene["media"] = {
                    "type": "video",
                    "file": f"media/scene-{idx}.mp4",
                    "duration": clip["duration"],
                    "credit": clip["credit"],
                    "source": "pexels",
                }
                credits.append(clip["credit"])
                attached += 1
            else:
                print(f"ℹ️ Scene {idx + 1}: no usable footage for '{query}'.")
        except Exception as exc:  # noqa: BLE001
            print(f"ℹ️ Scene {idx + 1}: footage lookup failed ({str(exc)[:100]}).")

    # Footage needs light text on dark glass, so the one light studio is swapped for a dark one.
    if attached and story.get("visual_theme") == "EditorialDeskLight":
        story["visual_theme"] = "GlassNewsroomDepth"
    story["media_credits"] = list(dict.fromkeys(credits))
    story_path.write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"🎞️ Visuals attached to {attached} of {len(scenes)} scene(s).")
    return story


def has_media(story: dict) -> bool:
    return any(scene.get("media") for scene in story.get("scenes", []))


__all__ = ["attach_media", "has_media", "PUBLIC_DIR"]
