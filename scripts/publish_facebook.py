"""Facebook Page Reels publishing (OFF unless the repository variable ENABLE_FACEBOOK is exactly 'true').

Credentials come only from the environment: FACEBOOK_PAGE_ID and FACEBOOK_PAGE_ACCESS_TOKEN (a Page access token
with pages_show_list, pages_read_engagement and pages_manage_posts). Facebook Reels must be 9:16 and 3-90 seconds, so
only the 9:16 Shorts qualify; the 16:9 videos are skipped. Flow: start session -> upload the file -> finish (PUBLISHED).
"""
from __future__ import annotations

import os
import time

import requests

from config import get_env_value
from publish_instagram import build_caption

GRAPH_API_VERSION = "v21.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
UPLOAD_BASE = f"https://rupload.facebook.com/video-upload/{GRAPH_API_VERSION}"
MIN_SECONDS, MAX_SECONDS = 3, 90
POLL_ATTEMPTS = 24
POLL_SECONDS = 5


def facebook_enabled() -> bool:
    """Opt-in: anything other than the exact value 'true' keeps Facebook off."""
    return os.getenv("ENABLE_FACEBOOK", "").strip().lower() == "true"


def reel_skip_reason(story: dict) -> str | None:
    """Why this video cannot be a Facebook Reel (None when it can): it must be 9:16 and 3-90 seconds long."""
    if story.get("format") != "portrait":
        return "not 9:16"
    seconds = story.get("duration_seconds")
    if isinstance(seconds, (int, float)) and not (MIN_SECONDS <= seconds <= MAX_SECONDS):
        return f"{seconds:.0f} s is outside {MIN_SECONDS}-{MAX_SECONDS} s"
    return None


def _json(response: requests.Response) -> dict:
    try:
        data = response.json()
    except ValueError:
        return {"error": {"message": response.text[:200]}}
    return data if isinstance(data, dict) else {"error": {"message": str(data)[:200]}}


def _error_text(data: dict) -> str:
    err = data.get("error") if isinstance(data.get("error"), dict) else {}
    message = str(err.get("message") or str(data)[:200])
    if err.get("code") == 190 or "access token" in message.lower():
        message += " (the FACEBOOK_PAGE_ACCESS_TOKEN has expired or is wrong; make a new Page access token)"
    return message


def post_reel_to_facebook(local_video_path: str, description: str, sleep=time.sleep) -> str:
    """Upload a local 9:16 MP4 as a Page Reel and publish it. Returns the Facebook video id."""
    page_id = get_env_value("FACEBOOK_PAGE_ID").strip()
    token = get_env_value("FACEBOOK_PAGE_ACCESS_TOKEN").strip()
    if not page_id or not token:
        raise RuntimeError("FACEBOOK_PAGE_ID and FACEBOOK_PAGE_ACCESS_TOKEN must be set in the environment.")
    if not os.path.exists(local_video_path):
        raise FileNotFoundError(f"Video file not found: {local_video_path}")
    file_size = os.path.getsize(local_video_path)

    print(f"📦 [Facebook] Starting the Reel upload session ({file_size // 1024} KB)...")
    start = _json(requests.post(f"{BASE_URL}/{page_id}/video_reels", json={"upload_phase": "start", "access_token": token}, timeout=30))
    video_id = start.get("video_id")
    if not video_id:
        raise RuntimeError(f"Facebook upload session failed: {_error_text(start)}")

    with open(local_video_path, "rb") as handle:
        video_bytes = handle.read()
    upload = requests.post(
        start.get("upload_url") or f"{UPLOAD_BASE}/{video_id}",
        headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(file_size),
                 "Content-Type": "application/octet-stream"},
        data=video_bytes,
        timeout=300,
    )
    result = _json(upload)
    if upload.status_code not in (200, 201) or result.get("success") is False:
        raise RuntimeError(f"Facebook video upload failed ({upload.status_code}): {_error_text(result)}")

    for attempt in range(1, POLL_ATTEMPTS + 1):
        sleep(POLL_SECONDS)
        status = _json(requests.get(f"{BASE_URL}/{video_id}", params={"fields": "status", "access_token": token}, timeout=30))
        info = status.get("status") if isinstance(status.get("status"), dict) else {}
        code = info.get("video_status")
        print(f"   [Facebook] processing {attempt}/{POLL_ATTEMPTS}: {code}")
        if code == "ready":
            break
        if code in ("error", "upload_failed", "expired"):
            raise RuntimeError(f"Facebook could not process the video: {code}")
    else:
        raise RuntimeError("Facebook did not finish processing the video in time.")

    finish = _json(requests.post(
        f"{BASE_URL}/{page_id}/video_reels",
        json={"upload_phase": "finish", "video_id": video_id, "video_state": "PUBLISHED",
              "description": description, "is_ai_generated": True, "access_token": token},
        timeout=30,
    ))
    if finish.get("success") is not True:
        raise RuntimeError(f"Facebook publish failed: {_error_text(finish)}")
    print(f"🎉 Facebook Reel published. Video ID: {video_id}")
    return str(video_id)
