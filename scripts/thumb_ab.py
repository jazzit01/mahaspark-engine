"""Swap the thumbnail of an uploaded video between the variants kept in ``out/thumbs/`` (A/B by hand).

    python scripts/thumb_ab.py list                       # the variants on disk
    python scripts/thumb_ab.py swap <video id or URL> [--name long-explainer] [--style bold]

Without ``--style`` the next variant after the one used last time is set (state in ``out/thumbs/ab_state.json``), so
running it once a week rotates question -> bold -> figure. YouTube's own "Test & compare" in Studio measures click
rate for you; this helper is for rotating by hand. Needs the YouTube secrets in the environment (same as the upload).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from thumbnails import THUMB_DIR

STATE = THUMB_DIR / "ab_state.json"


def variants(name: str | None = None, folder: Path = THUMB_DIR) -> list[Path]:
    """Variant files (``<name>-<style>.jpg``), in a stable order. ``name`` filters on the prefix."""
    return sorted(p for p in Path(folder).glob("*.jpg") if not name or p.name.startswith(f"{name}-"))


def next_variant(files: list[Path], last: str | None = None) -> Path | None:
    """The file after ``last`` (by file name) in ``files``, wrapping round; the first when ``last`` is unknown."""
    if not files:
        return None
    names = [p.name for p in files]
    return files[(names.index(last) + 1) % len(files)] if last in names else files[0]


def video_ref(value: str) -> str:
    """A bare video id or any YouTube URL -> the ``…?v=<id>`` form that ``youtube_upload.set_thumbnail`` reads."""
    value = value.strip()
    video_id = value.rsplit("v=", 1)[-1].split("&")[0] if "v=" in value else value.rsplit("/", 1)[-1].split("?")[0]
    return f"https://www.youtube.com/watch?v={video_id}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    swap = sub.add_parser("swap")
    swap.add_argument("video")
    swap.add_argument("--name", default=None, help="variant prefix, for example long-explainer or long-quiz")
    swap.add_argument("--style", default=None, help="a style to set: bold, question, figure or alert")
    args = parser.parse_args(argv)

    if args.cmd == "list":
        for path in variants():
            print(path.name)
        return 0

    files = variants(args.name)
    if args.style:
        files = [p for p in files if p.name.endswith(f"-{args.style}.jpg")]
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    ref = video_ref(args.video)
    chosen = files[0] if args.style and files else next_variant(files, state.get(ref))
    if not chosen:
        print("❌ No variants in out/thumbs/ (they are made by the video runs; download the workflow artifact first).")
        return 1
    import youtube_upload

    if not youtube_upload.set_thumbnail(ref, chosen):
        print(f"❌ YouTube did not accept {chosen.name}.")
        return 1
    state[ref] = chosen.name
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"✅ Thumbnail of {ref} is now {chosen.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
