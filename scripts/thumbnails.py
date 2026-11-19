"""YouTube thumbnails: several variants per video from the ``MahaSparkThumbnail`` composition (1280x720 JPEG).

A thumbnail is judged at the size of a postage stamp, so every variant is built the same way: ONE short punchy line
(about five words, a question or the hook, the last word in gold), ONE focal element (key figure, giant "?", photo or
alert plates) and a red tag. The first variant is uploaded automatically; the others are kept in ``out/thumbs/`` so you
can swap one in by hand or use YouTube Studio's "Test & compare" (the API cannot start that test).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from config import OUT_DIR, PUBLIC_DIR, REMOTION_DIR

THUMB_DIR = OUT_DIR / "thumbs"
STYLES = {  # first style is the one uploaded
    "explainer": ["question", "bold", "figure"],
    "quiz": ["question", "alert", "bold"],
    "bulletin": ["bold", "alert", "figure"],
    "reel": ["bold", "figure", "alert"],
}
HUE_STEPS = [0, 35, -40]
MAX_WORDS, MAX_CHARS = 5, 34


def short_text(text: str, max_words: int = MAX_WORDS, max_chars: int = MAX_CHARS) -> str:
    """The punchy line from a longer headline: the first words up to the limits, never a dangling comma or full stop."""
    words = re.sub(r"\s+", " ", str(text or "")).strip().split(" ")
    out: list[str] = []
    for word in words:
        if len(out) >= max_words or len(" ".join(out + [word])) > max_chars:
            break
        out.append(word)
    return " ".join(out).strip(" ,.;:-–—") or str(text or "")[:max_chars]


def variant_props(style: str, text: str, tag: str = "", figure: str = "", photo: str | None = None, hue: int = 0) -> dict:
    return {
        "text": short_text(text),
        "tag": tag or None,
        "figure": figure or None,
        "photo": {"src": photo} if photo else None,
        "style": style,
        "hue": hue,
    }


def render_variants(kind: str, text: str, tag: str = "", figure: str = "", photo: str | None = None, base_hue: int = 0,
                    name: str | None = None, count: int = 3) -> list[Path]:
    """Render up to ``count`` variants; returns the paths that were made (first = the one to upload). Never raises."""
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    made: list[Path] = []
    for style, step in list(zip(STYLES.get(kind, STYLES["reel"]), HUE_STEPS))[:count]:
        props = variant_props(style, text, tag, figure, photo, base_hue + step)
        props_file = PUBLIC_DIR / f"thumb_{style}.json"
        out = THUMB_DIR / f"{name or kind}-{style}.jpg"
        try:
            props_file.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
            cmd = ["npx", "remotion", "still", "src/index.ts", "MahaSparkThumbnail", str(out),
                   f"--props=public/{props_file.name}", "--image-format=jpeg", "--jpeg-quality=88"]
            if subprocess.run(cmd, cwd=REMOTION_DIR).returncode == 0 and out.exists():
                made.append(out)
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ Thumbnail '{style}' failed: {exc}")
    if made:
        print(f"🖼️ Thumbnails: {', '.join(p.name for p in made)} in {THUMB_DIR} (the first one is uploaded)")
    return made
