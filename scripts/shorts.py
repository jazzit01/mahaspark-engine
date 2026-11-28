"""Auto-cut a 9:16 Short (30-58 s) from a finished explainer or quiz, sent to Telegram.

``pick_clip`` chooses a run of whole scenes from ``long.json`` props (no model call, deterministic). ``make_short`` writes
``long_short.json`` (the same props plus a ``clip`` window) and renders composition ``MahaSparkLongShort``: the title on
top, the 16:9 video scaled to the full width, big karaoke captions below. Best effort: a failure never fails the video.
Shorts are not uploaded to YouTube (the daily upload quota is used by the long videos); they go to Telegram only.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from config import (
    LONG_SHORT_COMPOSITION_ID,
    LONG_SHORT_JSON,
    LONG_SHORT_PATH,
    OUT_DIR,
    REMOTION_DIR,
)

MIN_SECONDS, MAX_SECONDS, TARGET_SECONDS = 28.0, 58.0, 40.0

# how interesting a scene is as a Short (the hook and the punchy graphics first)
KIND_WEIGHT = {
    "title": 3.0, "stat": 3.0, "quote": 2.5, "compare": 2.0, "timeline": 1.5, "steps": 1.2, "points": 1.0,
    "summary": 0.4, "quiz_intro": 0.5, "question": 2.0, "answer": 2.0, "quiz_end": 0.0,
}


def pick_clip(props: dict) -> dict | None:
    """``{"start", "end", "first", "last"}`` (seconds, scene indexes) of the best run of scenes, or None if none fits.

    Explainer: any run that ends before the closing summary is worth less; the hook (scene 0) is preferred.
    Quiz: starts on a question and ends on its answer, so a Short is whole questions with their reveal.
    """
    scenes = props.get("scenes") or []
    quiz = props.get("kind") == "quiz"
    best: tuple[float, dict] | None = None
    for i in range(len(scenes)):
        if quiz and scenes[i]["kind"] != "question":
            continue
        total = 0.0
        for j in range(i, len(scenes)):
            total += float(scenes[j]["seconds"])
            if total > MAX_SECONDS:
                break
            if total < MIN_SECONDS:
                continue
            if quiz and scenes[j]["kind"] != "answer":
                continue
            score = sum(KIND_WEIGHT.get(s["kind"], 1.0) for s in scenes[i : j + 1])
            score -= abs(total - TARGET_SECONDS) * 0.15
            if i == 0:
                score += 2.0  # opens with the hook
            if best is None or score > best[0]:
                start = float(scenes[i]["start"])
                best = (score, {"start": round(start, 2), "end": round(start + total, 2), "first": i, "last": j})
    return best[1] if best else None


def make_short(props: dict, output: Path = LONG_SHORT_PATH, crf: int = 24) -> Path | None:
    """Render the Short; returns its path, or None when no clip fits or the render fails."""
    clip = pick_clip(props)
    if not clip:
        print("ℹ️ No 30-58 s run of scenes for a Short; skipped.")
        return None
    short_props = {**props, "clip": {"start": clip["start"], "end": clip["end"]}}
    LONG_SHORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    LONG_SHORT_JSON.write_text(json.dumps(short_props, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    from pipeline import render_concurrency

    cmd = [
        "npx", "remotion", "render", "src/index.ts", LONG_SHORT_COMPOSITION_ID, str(output),
        "--props=public/long_short.json", "--codec=h264", f"--crf={crf}", f"--concurrency={render_concurrency()}",
    ]
    print(f"🎞️ Rendering a {clip['end'] - clip['start']:.0f} s Short (scenes {clip['first'] + 1}-{clip['last'] + 1})...")
    result = subprocess.run(cmd, cwd=REMOTION_DIR)
    if result.returncode != 0 or not os.path.exists(output):
        print(f"⚠️ Short render failed (exit {result.returncode}); the long video is unaffected.")
        return None
    return Path(output)


def send_short(path: Path, title: str, label: str) -> None:
    """Telegram only (video without a long caption). Best effort."""
    import send_telegram

    try:
        send_telegram.send_video_file(path, f"📱 {label} Short: {title}")
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ Short not sent to Telegram: {exc}")


def run(props: dict, title: str, label: str, send: bool) -> Path | None:
    """Make (and optionally send) the Short. Never raises; ``LONG_SHORTS=0`` turns it off."""
    if os.getenv("LONG_SHORTS", "1") == "0":
        return None
    try:
        path = make_short(props)
        if path and send:
            send_short(path, title, label)
        return path
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ Short skipped: {exc}")
        return None
