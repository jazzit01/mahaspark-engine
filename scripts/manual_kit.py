"""When the YouTube upload does not happen (token problem, quota, no credentials) the finished video must still be usable:
the title, the full description and the tags go to Telegram (and into ``out/youtube_metadata.txt``, which every workflow keeps
as an artifact), and the video itself follows when it fits Telegram's bot limit. Best effort; never raises.
"""

from __future__ import annotations

import html
from pathlib import Path

import send_telegram
from config import OUT_DIR

KIT_PATH = OUT_DIR / "youtube_metadata.txt"


def kit_text(title: str, description: str, tags: list[str]) -> str:
    return f"TITLE\n{title}\n\nDESCRIPTION\n{description}\n\nTAGS\n{', '.join(tags)}\n"


def write_kit(title: str, description: str, tags: list[str], path: Path = KIT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(kit_text(title, description, tags), encoding="utf-8")
    return path


def deliver(label: str, video_path: Path, title: str, description: str, tags: list[str], reason: str, send: bool = True) -> Path:
    """Write the metadata file and (``send``) tell the owner on Telegram how to post the video by hand."""
    path = write_kit(title, description, tags)
    print(f"📝 YouTube details saved to {path} ({reason[:120]})")
    if not send:
        return path
    try:
        short_reason = html.escape(reason.strip()[:200])
        send_telegram.send_message(
            f"⚠️ <b>{html.escape(label)}: YouTube वर आपोआप पोस्ट झाले नाही</b>\n{short_reason}\n\n"
            f"<b>Title:</b>\n{html.escape(title)}\n\n<b>Tags:</b>\n{html.escape(', '.join(tags))}\n\n"
            "पूर्ण description खालच्या फाईलमध्ये आहे. व्हिडिओ आणि ही माहिती वापरून YouTube Studio मध्ये स्वतः अपलोड करा."
        )
        send_telegram.send_document(path, f"{label}: title, description, tags")
        video = Path(video_path)
        if video.exists() and video.stat().st_size <= send_telegram.MAX_VIDEO_BYTES:
            send_telegram.send_video_file(video, label)
        else:
            send_telegram.send_message("🎞️ व्हिडिओ Telegram साठी खूप मोठा आहे; तो GitHub Actions run च्या Artifacts मध्ये आहे (२ दिवस).")
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ Could not send the YouTube details to Telegram: {exc}")
    return path
