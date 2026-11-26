from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "remotion/src"


def test_headline_motion_sits_behind_each_scene_card():
    reel = (SRC / "Reel.tsx").read_text(encoding="utf-8")
    assert "<HeadlineMotion" in reel
    assert reel.index("<HeadlineMotion") < reel.index("<SceneCard")  # behind the text, inside the same scene Sequence
    assert "startFrame={starts[i]}" in reel and "words={story.words}" in reel


def test_headline_motion_is_deterministic_and_text_free():
    source = (SRC / "HeadlineMotion.tsx").read_text(encoding="utf-8")
    assert "Math.random" not in source and "Date.now" not in source  # a render must repeat frame by frame
    assert "export const speechEnvelope" in source and "export const HeadlineMotion" in source
    assert "<span" not in source and "fontSize" not in source  # an effect, never text or a badge
    assert "overMedia" in source  # gentler over footage
