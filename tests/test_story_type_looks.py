import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import editorial_engine as ee  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NEW = tuple(ee.STORY_TYPE_THEMES.values())


def test_story_type_from_category_and_text():
    assert ee.story_type("क्रीडा", "भारताचा विजय", "upbeat") == "sports"
    assert ee.story_type("हवामान", "राज्यात पावसाचा इशारा", "neutral") == "weather"
    assert ee.story_type("अर्थकारण", "सेन्सेक्स वाढला", "neutral") == "business"
    assert ee.story_type("आरोग्य", "रुग्णालयात नवी सुविधा", "neutral") == "health"
    assert ee.story_type("राजकारण", "आमदारांची बैठक", "neutral") == "politics"
    assert ee.story_type("मोठी बातमी", "पोलिसांनी आरोपीला अटक केली", "neutral") == "crime"
    assert ee.story_type("मोठी बातमी", "काहीही नाही", "crime") == "crime"
    assert ee.story_type("पुणे", "नवीन उद्यान सुरू", "neutral") == "general"


def test_category_outweighs_a_stray_word_in_the_text():
    assert ee.story_type("क्रीडा", "मंत्री उपस्थित होते", "neutral") == "sports"


def test_pick_theme_uses_the_story_type_studio(monkeypatch):
    monkeypatch.setattr(ee, "AVOID_THEME", None)
    for kind, theme in ee.STORY_TYPE_THEMES.items():
        assert ee.pick_theme("PrimeGridStudio", "neutral", "seed", kind) == theme
    assert ee.pick_theme(None, "neutral", "seed", "general") in ee.CALM_THEMES
    assert ee.pick_theme(None, "serious", "seed", "weather") == "BreakingNewsStudio"  # grave news keeps the breaking studio
    assert ee.pick_theme("BreakingNewsStudio", "neutral", "seed", "sports") == "BreakingNewsStudio"


def test_same_look_twice_in_a_row_falls_back_to_rotation(monkeypatch):
    monkeypatch.setattr(ee, "AVOID_THEME", "SkyWeatherStudio")
    picked = {ee.pick_theme(None, "neutral", f"s{i}", "weather") for i in range(40)}
    assert "SkyWeatherStudio" not in picked and picked <= set(ee.CALM_THEMES)
    ee.set_avoid_theme("SkyWeatherStudio")
    assert ee.AVOID_THEME == "SkyWeatherStudio"
    ee.set_avoid_theme(None)


def test_remotion_side_is_registered_and_deterministic():
    types = (ROOT / "remotion/src/types.ts").read_text(encoding="utf-8")
    index = (ROOT / "remotion/src/studios/index.ts").read_text(encoding="utf-8")
    theme = (ROOT / "remotion/src/theme.ts").read_text(encoding="utf-8")
    for name in NEW:
        assert name in types and name in index and name in theme
        source = (ROOT / f"remotion/src/studios/{name}.tsx").read_text(encoding="utf-8")
        assert "Math.random" not in source and "Date.now" not in source  # a render must be repeatable frame by frame
        assert f"export const {name}" in source
