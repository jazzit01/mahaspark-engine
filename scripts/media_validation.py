"""Measure production media before it can reach a publishing integration."""
import json
import math
import subprocess
from pathlib import Path

SHORT = (15, 30)
NEWS = (240, 300)


class InvalidMedia(ValueError):
    pass


def probe(path: Path) -> dict:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-count_packets", "-show_streams", "-show_format", "-of", "json", str(path)],
            check=True, capture_output=True, text=True, timeout=90,
        )
        info = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise InvalidMedia(f"FFprobe could not read {path.name}: {type(exc).__name__}") from exc
    if result.stderr.strip():
        raise InvalidMedia(f"FFprobe detected errors in {path.name}.")
    return info


def duration(value) -> float:
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        raise InvalidMedia("Media is missing a valid duration.") from None
    if not math.isfinite(seconds) or seconds <= 0:
        raise InvalidMedia("Media is missing a valid duration.")
    return seconds


def stream(info: dict, kind: str) -> dict:
    for track in info.get("streams", []):
        if (track.get("codec_type") == kind and track.get("codec_name") not in (None, "unknown")
                and str(track.get("nb_read_packets", "")).isdigit()
                and int(track["nb_read_packets"]) > 0 and not track.get("disposition", {}).get("attached_pic")):
            return track
    raise InvalidMedia(f"Media has no playable {kind} stream.")


def audio_seconds(path: Path) -> float:
    info = probe(path)
    audio = stream(info, "audio")
    return duration(audio.get("duration", info.get("format", {}).get("duration")))


def within(seconds: float, bounds: tuple[int, int], label: str) -> None:
    if not bounds[0] <= seconds <= bounds[1]:
        raise InvalidMedia(f"{label} is {seconds:.3f}s; required {bounds[0]}–{bounds[1]}s inclusive.")


def video(path: Path, bounds: tuple[int, int], aspect: tuple[int, int]) -> float:
    info = probe(path)
    audio = stream(info, "audio")
    picture = stream(info, "video")
    seconds = duration(info.get("format", {}).get("duration"))
    within(seconds, bounds, "Container")
    within(duration(picture.get("duration", seconds)), bounds, "Video stream")
    display = picture.get("display_aspect_ratio")
    if display in (None, "N/A", "0:1"):
        display = f"{picture.get('width', 0)}:{picture.get('height', 0)}"
    if display != f"{aspect[0]}:{aspect[1]}" or any(
        item.get("rotation", 0) % 180 for item in picture.get("side_data_list", [])
    ):
        raise InvalidMedia(f"Expected {aspect[0]}:{aspect[1]} video, found {display}.")
    if duration(audio.get("duration", seconds)) < seconds - 1:
        raise InvalidMedia("Audio stream ends more than one second before the video.")
    return seconds


def reel_route(seconds: float) -> str:
    if seconds < SHORT[0]:
        return "skip"
    if seconds <= SHORT[1]:
        return "short"
    if seconds <= 60:
        return "condense"
    return "news"
