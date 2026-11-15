"""Shared configuration: environment loading and canonical project paths."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REMOTION_DIR = ROOT / "remotion"
PUBLIC_DIR = REMOTION_DIR / "public"
OUT_DIR = ROOT / "out"

MEDIA_DIR = PUBLIC_DIR / "media"
STORY_PATH = PUBLIC_DIR / "story.json"
VOICEOVER_PATH = PUBLIC_DIR / "voiceover.wav"
REEL_PATH = OUT_DIR / "mahaspark_reel.mp4"

BULLETIN_DIR = PUBLIC_DIR / "bulletin"  # per-item voiceovers and photos (git-ignored)
BULLETIN_JSON = PUBLIC_DIR / "bulletin.json"
BULLETIN_PATH = OUT_DIR / "mahaspark_bulletin.mp4"

COMPOSITION_ID = "MahaSparkReel"
BULLETIN_COMPOSITION_ID = "MahaSparkBulletin"


def load_env_file(env_path: str | os.PathLike[str] | None = None) -> None:
    """Load environment variables from a local .env file when present."""
    target = Path(env_path) if env_path else ROOT / ".env"

    if not target.exists():
        return

    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        os.environ.setdefault(key, value)


def get_env_value(name: str, default: str | None = None) -> str:
    """Return environment variable if set and non-empty, else default.

    GitHub Actions passes an unset variable as an empty string, so empty counts as unset.
    """
    value = os.getenv(name)
    if value:
        return value
    return default if default is not None else ""


load_env_file()
