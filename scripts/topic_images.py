"""Real pictures for the explainer: freely licensed photos from the topic's own English Wikipedia article (lead image first).

Only jpg/png photos with a free licence (CC / public domain), at least 900 px wide, never maps, flags, logos or icons.
Each picture keeps its credit line (author, licence, Wikimedia Commons) for the YouTube description. Anything that cannot be
fetched is skipped; with no pictures the video simply keeps its animated studio background. Never raises.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

import requests

from config import LONG_DIR
from media_fetch import FREE_LICENCE, NOT_A_PHOTO, USER_AGENT, _plain, download

API = "https://en.wikipedia.org/w/api.php"
MIN_WIDTH = 900
MAX_PHOTOS = 6
SKIP_WORDS = NOT_A_PHOTO + ("commons-logo", "question book", "ambox", "wikiquote", "wikisource", "wiktionary", "padlock", "edit-clear", "disambig", "stub")


def english_titles(urls: list[str]) -> list[str]:
    """Article titles of the English Wikipedia links in ``urls`` (other links are ignored)."""
    titles = []
    for url in urls:
        m = re.match(r"https?://en\.wikipedia\.org/wiki/([^?#]+)", str(url).strip())
        if m:
            titles.append(unquote(m.group(1)).replace("_", " "))
    return list(dict.fromkeys(titles))


def _api(params: dict) -> dict:
    resp = requests.get(API, headers={"User-Agent": USER_AGENT}, params={"format": "json", "formatversion": 2, **params}, timeout=25)
    resp.raise_for_status()
    return resp.json()


def candidate_files(title: str) -> list[str]:
    """File names used on the article: the lead image first, then the others in page order."""
    data = _api({"action": "query", "titles": title, "redirects": 1, "prop": "images|pageimages", "imlimit": 60, "piprop": "name"})
    page = (data.get("query", {}).get("pages") or [{}])[0]
    files = [i.get("title", "") for i in page.get("images", [])]
    lead = page.get("pageimage")
    if lead:
        files.insert(0, f"File:{lead.replace('_', ' ')}")
    keep = []
    for name in dict.fromkeys(files):
        low = name.lower()
        if not low.endswith((".jpg", ".jpeg", ".png")) or any(w in low for w in SKIP_WORDS):
            continue
        keep.append(name)
    return keep


def usable_photos(files: list[str]) -> list[dict]:
    """Licence, size and download url of each file, in the order given; only the free, large enough ones."""
    found = []
    for start in range(0, len(files), 20):
        chunk = files[start:start + 20]
        data = _api({"action": "query", "titles": "|".join(chunk), "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1600})
        by_title = {p.get("title"): p for p in data.get("query", {}).get("pages", [])}
        for name in chunk:
            info = ((by_title.get(name) or {}).get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            licence = _plain((meta.get("LicenseShortName") or {}).get("value", ""))
            url = info.get("thumburl") or info.get("url")
            if not url or not str(info.get("mime", "")).startswith("image/") or not FREE_LICENCE.match(licence):
                continue
            if int(info.get("width") or 0) < MIN_WIDTH:
                continue
            artist = _plain((meta.get("Artist") or {}).get("value", "")) or "Unknown author"
            found.append({
                "url": url,
                "width": int(info.get("thumbwidth") or info.get("width") or 0),
                "height": int(info.get("thumbheight") or info.get("height") or 0),
                "credit": f"Photo: {artist[:60]}, {licence}, Wikimedia Commons",
            })
    return found


def fetch_images(urls: list[str], limit: int = MAX_PHOTOS, out_dir: Path = LONG_DIR / "photos") -> list[dict]:
    """Download up to ``limit`` photos of the topic into ``out_dir``; returns [{file, width, height, credit}] ([] if none)."""
    titles = english_titles(urls)
    if not titles:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("photo-*.jpg"):
        old.unlink(missing_ok=True)
    photos: list[dict] = []
    try:
        for title in titles[:2]:
            for cand in usable_photos(candidate_files(title)):
                if len(photos) >= limit:
                    break
                dest = out_dir / f"photo-{len(photos) + 1}.jpg"
                if download(cand["url"], dest):
                    photos.append({"file": f"long/photos/{dest.name}", "width": cand["width"], "height": cand["height"], "credit": cand["credit"]})
    except Exception as exc:  # noqa: BLE001
        print(f"ℹ️ Topic photos unavailable ({str(exc)[:100]}); the animated studio background is used.")
    print(f"🖼️ {len(photos)} topic photo(s) found.")
    return photos
