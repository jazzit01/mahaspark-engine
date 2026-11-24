"""Instagram Reels publishing (OFF unless the repository variable ENABLE_INSTAGRAM is exactly 'true').

Credentials come only from the environment: INSTAGRAM_USER_ID (the Instagram Business/Creator account id) and
INSTAGRAM_ACCESS_TOKEN (a long-lived token with the instagram_content_publish permission). The video is sent
straight to Meta with the resumable upload protocol, so no public link is needed.
"""
from __future__ import annotations

import os
import time

import requests

from config import get_env_value

GRAPH_API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
CAPTION_LIMIT = 2200      # Instagram's caption limit
MAX_BYTES = 300 * 1024 * 1024
POLL_ATTEMPTS = 24
POLL_SECONDS = 5


def instagram_enabled() -> bool:
    """Opt-in: anything other than the exact value 'true' keeps Instagram off."""
    return os.getenv("ENABLE_INSTAGRAM", "").strip().lower() == "true"


def build_caption(story: dict) -> str:
    """Caption: the SEO caption, the follow call, then the hashtags (Instagram allows up to 30), cut to the limit."""
    five = story.get("five_w_one_h") or {}
    parts = [str(story.get("social_caption", "")).strip()]
    if not parts[0] and five.get("what"):
        parts = [str(five["what"]).strip()]
    parts.append("🔔 MahaSpark ला फॉलो करा, रोज ताज्या बातम्या मिळवा.")
    tags = " ".join(str(story.get("hashtags", "")).split()[:30])
    if tags:
        parts.append(tags)
    text = "\n\n".join(p for p in parts if p)
    return text if len(text) <= CAPTION_LIMIT else text[: CAPTION_LIMIT - 1].rstrip() + "…"


def _json(response: requests.Response) -> dict:
    try:
        data = response.json()
    except ValueError:
        return {"error": {"message": response.text[:200]}}
    return data if isinstance(data, dict) else {"error": {"message": str(data)[:200]}}


def _error_text(data: dict) -> str:
    err = data.get("error") if isinstance(data.get("error"), dict) else {}
    message = err.get("message") or str(data)[:200]
    if err.get("code") == 190 or "access token" in str(message).lower():
        message += " (the INSTAGRAM_ACCESS_TOKEN has expired or is wrong; make a new long-lived token)"
    return str(message)


def post_reel_to_instagram(local_video_path: str, caption_text: str, sleep=time.sleep) -> str:
    """Upload a local MP4 as a Reel and publish it. Returns the Instagram post id."""
    user_id = get_env_value("INSTAGRAM_USER_ID").strip()
    token = get_env_value("INSTAGRAM_ACCESS_TOKEN").strip()
    if not user_id or not token:
        raise RuntimeError("INSTAGRAM_USER_ID and INSTAGRAM_ACCESS_TOKEN must be set in the environment.")
    if not os.path.exists(local_video_path):
        raise FileNotFoundError(f"Video file not found: {local_video_path}")
    file_size = os.path.getsize(local_video_path)
    if file_size > MAX_BYTES:
        raise RuntimeError(f"The video is {file_size // (1024 * 1024)} MB; Instagram accepts up to 300 MB.")

    print(f"📦 [Instagram] Creating the Reels container ({file_size // 1024} KB)...")
    init = _json(requests.post(
        f"{BASE_URL}/{user_id}/media",
        data={"media_type": "REELS", "upload_type": "resumable", "caption": caption_text,
              "share_to_feed": "true", "access_token": token},
        timeout=30,
    ))
    if "id" not in init:
        raise RuntimeError(f"Instagram container failed: {_error_text(init)}")
    creation_id = init["id"]
    upload_url = init.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{GRAPH_API_VERSION}/{creation_id}"

    with open(local_video_path, "rb") as handle:
        video_bytes = handle.read()
    upload = requests.post(
        upload_url,
        headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(file_size),
                 "Content-Type": "application/octet-stream"},
        data=video_bytes,
        timeout=300,
    )
    if upload.status_code not in (200, 201):
        raise RuntimeError(f"Instagram video upload failed ({upload.status_code}): {upload.text[:200]}")

    for attempt in range(1, POLL_ATTEMPTS + 1):
        sleep(POLL_SECONDS)
        status = _json(requests.get(f"{BASE_URL}/{creation_id}", params={"fields": "status_code,status", "access_token": token}, timeout=30))
        code = status.get("status_code")
        print(f"   [Instagram] processing {attempt}/{POLL_ATTEMPTS}: {code}")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram could not process the video: {status.get('status') or code}")
    else:
        raise RuntimeError("Instagram did not finish processing the video in time.")

    published = _json(requests.post(f"{BASE_URL}/{user_id}/media_publish", data={"creation_id": creation_id, "access_token": token}, timeout=30))
    if "id" not in published:
        raise RuntimeError(f"Instagram publish failed: {_error_text(published)}")
    print(f"🎉 Instagram Reel published. Post ID: {published['id']}")
    return str(published["id"])
