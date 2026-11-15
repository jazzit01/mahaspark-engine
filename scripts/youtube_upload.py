"""Upload a finished video to YouTube with the Data API (resumable upload, plain ``requests``).

Credentials come from the environment only: ``YOUTUBE_CLIENT_ID``, ``YOUTUBE_CLIENT_SECRET`` and
``YOUTUBE_REFRESH_TOKEN`` (an OAuth refresh token with the ``youtube.upload`` scope). ``YOUTUBE_PRIVACY`` is
``private`` (default), ``unlisted`` or ``public``. API projects that Google has not audited can only upload private
videos; the video is still uploaded and can be made public by hand in YouTube Studio.
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from config import get_env_value

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
CHUNK_BYTES = 8 * 1024 * 1024
MAX_TITLE, MAX_DESCRIPTION, MAX_TAGS_CHARS = 100, 5000, 450
PRIVACY_VALUES = ("private", "unlisted", "public")


class YouTubeUnavailable(RuntimeError):
    """The credentials are not configured (upload is skipped, not a failure)."""


def credentials() -> tuple[str, str, str]:
    values = [get_env_value(k) for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")]
    if not all(values):
        raise YouTubeUnavailable("YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN are not all set.")
    return values[0], values[1], values[2]


def privacy_status() -> str:
    value = (get_env_value("YOUTUBE_PRIVACY", "private") or "private").strip().lower()
    return value if value in PRIVACY_VALUES else "private"


def clean_tags(tags: list[str], limit: int = MAX_TAGS_CHARS) -> list[str]:
    """Unique tags whose combined length stays under YouTube's 500 character cap."""
    out, seen, total = [], set(), 0
    for tag in tags:
        tag = " ".join(str(tag).replace("#", "").replace('"', "").split())
        if not tag or tag.lower() in seen:
            continue
        cost = len(tag) + (2 if " " in tag else 0) + 1
        if total + cost > limit:
            break
        seen.add(tag.lower())
        out.append(tag)
        total += cost
    return out


def build_metadata(title: str, description: str, tags: list[str], privacy: str | None = None) -> dict:
    return {
        "snippet": {
            "title": " ".join(title.split())[:MAX_TITLE],
            "description": description[:MAX_DESCRIPTION].replace("<", "‹").replace(">", "›"),
            "tags": clean_tags(tags),
            "categoryId": "25",  # News & Politics
            "defaultLanguage": "mr",
            "defaultAudioLanguage": "mr",
        },
        "status": {
            "privacyStatus": privacy or privacy_status(),
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
        },
    }


def access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if resp.status_code != 200 or "access_token" not in resp.json():
        raise RuntimeError(f"YouTube token refresh failed: HTTP {resp.status_code} {resp.text[:200]}")
    return resp.json()["access_token"]


def upload_video(video_path: Path, title: str, description: str, tags: list[str], max_retries: int = 4) -> str:
    """Upload ``video_path`` and return the watch URL. Raises YouTubeUnavailable without credentials."""
    client_id, client_secret, refresh = credentials()
    video_path = Path(video_path)
    size = video_path.stat().st_size
    token = access_token(client_id, client_secret, refresh)
    headers = {"Authorization": f"Bearer {token}"}

    init = requests.post(
        UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={**headers, "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
        json=build_metadata(title, description, tags),
        timeout=60,
    )
    if init.status_code != 200 or not init.headers.get("Location"):
        raise RuntimeError(f"YouTube upload could not start: HTTP {init.status_code} {init.text[:300]}")
    session_url = init.headers["Location"]

    offset, failures = 0, 0
    with open(video_path, "rb") as handle:
        while True:
            handle.seek(offset)
            chunk = handle.read(CHUNK_BYTES)
            end = offset + len(chunk) - 1
            try:
                resp = requests.put(
                    session_url,
                    data=chunk,
                    headers={**headers, "Content-Length": str(len(chunk)), "Content-Range": f"bytes {offset}-{end}/{size}"},
                    timeout=300,
                )
            except requests.RequestException as exc:
                failures += 1
                if failures > max_retries:
                    raise RuntimeError(f"YouTube upload failed: {exc}") from exc
                time.sleep(2 * failures)
                continue
            if resp.status_code in (200, 201):
                video_id = resp.json().get("id")
                if not video_id:
                    raise RuntimeError("YouTube accepted the upload but returned no video id.")
                return f"https://www.youtube.com/watch?v={video_id}"
            if resp.status_code == 308:  # chunk stored, send the next one
                failures = 0
                sent = resp.headers.get("Range", "")
                offset = int(sent.split("-")[-1]) + 1 if "-" in sent else offset + len(chunk)
                continue
            failures += 1
            if resp.status_code < 500 or failures > max_retries:
                raise RuntimeError(f"YouTube upload failed: HTTP {resp.status_code} {resp.text[:300]}")
            time.sleep(2 * failures)


def set_thumbnail(video_url: str, image_path: Path) -> bool:
    """Best effort: attach a custom thumbnail (needs a verified channel). Returns True when YouTube accepted it."""
    image_path = Path(image_path)
    video_id = video_url.rsplit("v=", 1)[-1]
    if not image_path.exists() or image_path.stat().st_size > 2 * 1024 * 1024 or not video_id:
        return False
    client_id, client_secret, refresh = credentials()
    token = access_token(client_id, client_secret, refresh)
    resp = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/thumbnails/set",
        params={"videoId": video_id, "uploadType": "media"},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"},
        data=image_path.read_bytes(),
        timeout=60,
    )
    if resp.status_code != 200:
        print(f"⚠️ Thumbnail not set: HTTP {resp.status_code} {resp.text[:160]}")
    return resp.status_code == 200
