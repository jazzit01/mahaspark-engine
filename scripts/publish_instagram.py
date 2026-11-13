"""Optional Instagram Reels publishing (OFF unless the repository variable ENABLE_INSTAGRAM is 'true').

Credentials come only from the environment (INSTAGRAM_USER_ID, INSTAGRAM_ACCESS_TOKEN).
"""

from __future__ import annotations

import os
import time

import requests

from config import get_env_value

GRAPH_API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def instagram_enabled() -> bool:
    """Opt-in: anything other than the exact value 'true' keeps Instagram off."""
    return os.getenv("ENABLE_INSTAGRAM", "").strip().lower() == "true"


def post_reel_to_instagram(local_video_path: str, caption_text: str) -> str:
    """Upload a local MP4 through Meta's resumable upload protocol and publish it as a Reel."""
    user_id = get_env_value("INSTAGRAM_USER_ID")
    token = get_env_value("INSTAGRAM_ACCESS_TOKEN")
    if not user_id or not token:
        raise RuntimeError("INSTAGRAM_USER_ID and INSTAGRAM_ACCESS_TOKEN must be set in the environment.")
    if not os.path.exists(local_video_path):
        raise FileNotFoundError(f"Video file not found: {local_video_path}")

    file_size = os.path.getsize(local_video_path)
    print(f"📦 [Instagram] Creating Reels container ({file_size} bytes)...")

    init = requests.post(
        f"{BASE_URL}/{user_id}/media",
        data={
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": caption_text,
            "share_to_feed": "true",
            "thumb_offset": 3000,
            "access_token": token,
        },
        timeout=30,
    ).json()
    if "id" not in init:
        raise RuntimeError(f"Instagram container initialisation failed: {init}")

    creation_id = init["id"]
    upload_url = init.get("uri", f"https://rupload.facebook.com/ig-api-upload/{GRAPH_API_VERSION}/{creation_id}")

    with open(local_video_path, "rb") as handle:
        video_bytes = handle.read()
    upload = requests.post(
        upload_url,
        headers={
            "Authorization": f"OAuth {token}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream",
        },
        data=video_bytes,
        timeout=180,
    )
    if upload.status_code not in (200, 201):
        raise RuntimeError(f"Instagram video upload failed ({upload.status_code}): {upload.text}")

    for attempt in range(20):
        time.sleep(5)
        status = requests.get(
            f"{BASE_URL}/{creation_id}", params={"fields": "status_code", "access_token": token}, timeout=30
        ).json()
        code = status.get("status_code")
        print(f"   Status check ({attempt + 1}/20): {code}")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"Meta failed processing the video: {status}")
    else:
        raise RuntimeError("Instagram did not finish processing the video in time.")

    published = requests.post(
        f"{BASE_URL}/{user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=30,
    ).json()
    if "id" not in published:
        raise RuntimeError(f"Failed to publish the Instagram Reel: {published}")

    print(f"🎉 Instagram Reel published. Post ID: {published['id']}")
    return published["id"]
