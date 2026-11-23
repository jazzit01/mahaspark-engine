"""Shared engine of the long 16:9 videos (explainer and daily quiz).

Both are a list of SCENES. Every scene has its own voice clip, so the graphics can be tied to the exact spoken words:

    scene text -> Gemini TTS clip -> faster-whisper word times (aligned to the script) -> on-screen items appear on
    the word that names them (``cue_times``) -> remotion/public/long.json -> ONE Remotion render (MahaSparkLong).

All times in ``long.json`` are in seconds from the START OF THE SCENE (the voice starts ``lead_seconds`` in).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import align_timings
import editorial_engine
import voices
from config import (
    LONG_COMPOSITION_ID,
    LONG_DIR,
    LONG_JSON,
    LONG_PATH,
    OUT_DIR,
    REMOTION_DIR,
)
from content_rules import plain_names
from llm_providers import LLMUnavailableError
from marathi_numbers import caption_words

LEAD_SECONDS, TAIL_SECONDS, MIN_SCENE_SECONDS = 0.5, 0.8, 3.0
OUTRO_SECONDS = 8.0
MIN_CHAPTER_SECONDS = 10


def norm(word: str) -> str:
    return align_timings.normalize_token(word)


def time_words(script: str, wav: Path | None, duration: float, whisper=align_timings.transcribe_words) -> list[dict]:
    """Start/end (seconds from the start of the clip) of every script word, using Whisper's times where they match.
    ``caption_words`` merges spoken numbers back into digits (१२, ₹१,२०० कोटी) for the screen."""
    heard = []
    if wav is not None:
        try:
            heard = whisper(wav)
        except Exception as exc:  # noqa: BLE001 - captions still work with proportional timing
            print(f"⚠️ faster-whisper failed ({exc}); using proportional word timing.")
    timed, _matched = align_timings.align_script_to_audio(script.split(), heard, duration)
    return caption_words([{"text": w.text, "start": w.start, "end": w.end, "scene": 0} for w in timed])


def cue_times(items: list[dict], words: list[dict], duration: float, lead: float = LEAD_SECONDS) -> list[float]:
    """Moment (seconds from scene start) each on-screen item should appear: the first time its ``cue`` word is spoken,
    searching forward so the items come in the order they are spoken. An item whose cue is not found is spread
    evenly over the speech instead, so a bad cue costs precision, never the video."""
    n = len(items)
    cues: list[float | None] = []
    cursor = 0
    for item in items:
        target = norm(item.get("cue", ""))
        found = None
        index = item.get("cue_index")
        if isinstance(index, int) and 0 <= index < len(words):  # an exact word position beats a cue word
            cursor = index + 1
            cues.append(lead + words[index]["start"] - 0.1)
            continue
        if target:
            for i in range(cursor, len(words)):
                if target and (norm(words[i]["text"]) == target or (len(target) >= 4 and target in norm(words[i]["text"]))):
                    found = i
                    break
        if found is None:
            cues.append(None)
        else:
            cursor = found + 1
            cues.append(lead + words[found]["start"] - 0.15)
    out: list[float] = []
    for i, cue in enumerate(cues):
        if cue is None:
            cue = lead + (i / max(n, 1)) * duration * 0.85  # spread evenly
        out.append(round(max(lead * 0.5, cue if not out else max(cue, out[-1] + 0.25)), 2))
    return out


# Scene keys holding a word position that build_scene turns into seconds. NOT every key ending in "_index":
# "q_index" is the question number and was being stripped, so every question showed "प्रश्न १ / १०".
WORD_INDEX_KEYS = ("reveal_index", "explain_index")


def voice_scene(text: str, index: int, tts=editorial_engine.synthesize_voiceover, out_dir: Path = LONG_DIR,
                kind: str = "") -> tuple[str, float]:
    """Voice one scene in the voice role of its kind (voices.py). Returns (path under public/, seconds)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"scene-{index}.wav"
    kwargs = voices.role_kwargs(voices.role_for_scene(kind))
    # a clip already voiced (same text, voice and style) is reused, so a run that died on a spent quota resumes
    cached = out_dir / "cache" / (hashlib.sha1(json.dumps([text, kwargs], sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:20] + ".wav")
    if cached.exists() and cached.stat().st_size > 4000:
        shutil.copyfile(cached, path)
        print(f"♻️ Scene {index + 1}: reusing the voice made earlier.")
    else:
        tts(text, path, **kwargs)
        try:
            cached.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, cached)
        except OSError:
            pass
    return f"long/{path.name}", align_timings.audio_duration(path)


def build_scene(scene: dict, index: int, tts=editorial_engine.synthesize_voiceover, whisper=align_timings.transcribe_words,
                out_dir: Path = LONG_DIR, extra_seconds: float = 0.0) -> dict:
    """Voice and time one scene dict (it needs ``tts_text``; ``items`` may carry ``cue`` words). ``extra_seconds`` is
    silent time after the voice (the quiz countdown)."""
    rel, seconds = voice_scene(scene["tts_text"], index, tts, out_dir, scene.get("kind", ""))
    wav = out_dir / Path(rel).name
    words = time_words(scene["tts_text"], wav, seconds, whisper)
    for w in words:
        w["start"] = round(w["start"] + LEAD_SECONDS, 3)
        w["end"] = round(w["end"] + LEAD_SECONDS, 3)
    items = [dict(it) for it in scene.get("items", [])]
    for item, cue in zip(items, cue_times(items, words, seconds)):
        item["cue"] = cue
    # "reveal_index" / "explain_index" (word positions) become "reveal_at" / "explain_at" (seconds from scene start)
    marks = {
        k[: -len("_index")] + "_at": round(LEAD_SECONDS + words[v]["start"] - 0.1, 2)
        for k, v in scene.items()
        if k in WORD_INDEX_KEYS and isinstance(v, int) and 0 <= v < len(words)
    }
    scene = {k: v for k, v in scene.items() if k != "items" and k not in WORD_INDEX_KEYS}
    return {
        **marks,
        **scene,
        "items": items,
        "audio": rel,
        "audio_seconds": round(seconds, 2),
        "lead_seconds": LEAD_SECONDS,
        "extra_seconds": round(extra_seconds, 2),
        "words": words,
        "seconds": round(max(MIN_SCENE_SECONDS, LEAD_SECONDS + seconds + extra_seconds + TAIL_SECONDS), 2),
    }


def voice_all(scenes: list[dict], extras: list[float] | None = None, **kw) -> list[dict]:
    """Build every scene. A voice failure on one scene is fatal for the video (a silent scene would be wrong), but a
    spent quota raises LLMUnavailableError so the caller can stop cleanly."""
    built = []
    editorial_engine.allow_tts_wait(float(os.getenv("TTS_WAIT_SECONDS", "1200")))  # wait out per-minute 429s (20 min in all)
    try:
        for i, scene in enumerate(scenes):
            extra = extras[i] if extras else 0.0
            built.append(build_scene(scene, i, extra_seconds=extra, **kw))
            print(f"🎙️ Scene {i + 1}/{len(scenes)} voiced ({built[-1]['audio_seconds']:.1f}s)")
    finally:
        editorial_engine.allow_tts_wait(0)
    return built


STUDIOS = ("PrimeGridStudio", "DataTelemetryStudio", "GlassNewsroomDepth", "BreakingNewsStudio")
# line-art studios (original code in the look families "Sketch & Board", "Line Diagrams", "Data & Maps")
LINE_STUDIOS = {
    "explainer": ("ChalkboardStudio", "BlueprintStudio", "DataMapStudio", "AuroraStudio", "OrbitStudio"),
    "quiz": ("ChalkboardStudio", "BlueprintStudio", "DataMapStudio"),
}


def pick_studio(seed: str) -> str:
    """One of the animated studios, chosen from the title so every video does not look the same."""
    import zlib

    pool = STUDIOS[:3] + LINE_STUDIOS["explainer"]  # the crimson Breaking studio is for grave news only
    return pool[zlib.crc32(("studio" + seed).encode("utf-8")) % len(pool)]


PACKS = {"explainer": "knowledge", "quiz": "quiz"}  # brand style packs: colours per series (remotion/src/long/kit.tsx)
LOOP_DIR = LONG_DIR.parent / "loops"  # optional looping background clips (for example made with lemo-opuscar)


def pick_pack(kind: str) -> str:
    return PACKS.get(kind, "news")


def pick_loop(seed: str, folder: Path | None = None) -> str | None:
    """A looping background clip from ``remotion/public/loops/*.mp4`` (chosen by the title), or None when there are none."""
    import zlib

    clips = sorted(Path(folder or LOOP_DIR).glob("*.mp4"))
    if os.getenv("LONG_LOOPS", "1") == "0" or not clips:
        return None
    return f"loops/{clips[zlib.crc32(('loop' + seed).encode('utf-8')) % len(clips)].name}"


def attach_photos(props: dict, photos: list[dict]) -> dict:
    """Spread the topic photos over the scenes in order (scene i gets photo floor(i * n / scenes)), never the quiz scenes."""
    if not photos:
        return props
    scenes = props["scenes"]
    for i, scene in enumerate(scenes):
        photo = photos[min(len(photos) - 1, i * len(photos) // len(scenes))]
        scene["media"] = {"file": photo["file"], "width": photo["width"], "height": photo["height"]}
    props["credits"] = list(dict.fromkeys(p["credit"] for p in photos))
    return props


def assemble(kind: str, title: str, scenes: list[dict], bg_hue: int, mood: str = "neutral") -> dict:
    cursor, out = 0.0, []
    for scene in scenes:
        out.append({**scene, "start": round(cursor, 2)})
        cursor += scene["seconds"]
    return {
        "kind": kind,
        "title": title,
        "audio_mood": mood,
        "bg_hue": bg_hue,
        "studio": pick_studio(title),
        "pack": pick_pack(kind),
        "loop": pick_loop(title),
        "scenes": out,
        "outro_seconds": OUTRO_SECONDS,
        "outro_start": round(cursor, 2),
        "total_seconds": round(cursor + OUTRO_SECONDS, 2),
    }


def timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"


def chapters(props: dict, labels: list[str]) -> list[tuple[float, str]]:
    """YouTube chapters: the first is 0:00 and every one lasts at least 10 s (shorter scenes merge into the previous)."""
    marks: list[tuple[float, str]] = []
    for scene, label in zip(props["scenes"], labels):
        if not marks:
            marks.append((0.0, label))
        elif scene["start"] - marks[-1][0] >= MIN_CHAPTER_SECONDS and props["outro_start"] - scene["start"] >= MIN_CHAPTER_SECONDS:
            marks.append((scene["start"], label))
    marks.append((props["outro_start"], "MahaSpark फॉलो करा"))
    return marks if len(marks) >= 3 else []


def write_props(props: dict, path: Path = LONG_JSON) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")


def render(output: Path = LONG_PATH, crf: int = 24) -> None:
    from pipeline import render_concurrency

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        "npx", "remotion", "render", "src/index.ts", LONG_COMPOSITION_ID, str(output),
        "--props=public/long.json", "--codec=h264", f"--crf={crf}", f"--concurrency={render_concurrency()}",
    ]
    print("🎬 Rendering the video with Remotion (one job)...")
    result = subprocess.run(cmd, cwd=REMOTION_DIR)
    if result.returncode != 0 or not os.path.exists(output):
        raise RuntimeError(f"Remotion render failed with exit code {result.returncode}")


def render_thumbnail(kind: str, text: str, tag: str, figure: str = "", hue: int = 0) -> Path | None:
    """Thumbnail variants (see thumbnails.py). Returns the one to upload (the first), or None. Best effort."""
    import thumbnails

    made = thumbnails.render_variants(kind, text, tag, figure, base_hue=hue, name=f"long-{kind}")
    return made[0] if made else None


def speakable(text: str) -> str:
    """Boilerplate or composed speech: digits to Marathi words, then the usual cleanup."""
    from marathi_numbers import numbers_to_words

    return editorial_engine.clean_tts_text(numbers_to_words(text))


def squash(text: str) -> str:
    return re.sub(r"[\s\"'“”‘’]+", "", plain_names(str(text or "")))
