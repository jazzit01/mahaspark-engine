import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import editorial_engine as ee  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_icon_is_chosen_from_the_figure_and_label():
    assert ee.figure_icon("८५%", "उपस्थिती") == "percent"
    assert ee.figure_icon("₹१,२०० कोटी", "तरतूद") == "rupee"
    assert ee.figure_icon("५० हजार", "शेतकरी") == "people"
    assert ee.figure_icon("३२ किमी", "मार्ग") == "road"
    assert ee.figure_icon("४० टीएमसी", "पाणीसाठा") == "drop"
    assert ee.figure_icon("२०० मेगावॅट", "वीज") == "bolt"
    assert ee.figure_icon("१०० खाटा", "रुग्णालय") == "cross"
    assert ee.figure_icon("५ हेक्टर", "ऊस") == "wheat"
    assert ee.figure_icon("१२ शाळा", "") == "building"
    assert ee.figure_icon("१२", "क्रमांक") == "burst"


def test_percent_beats_money_and_every_icon_has_a_drawing():
    assert ee.figure_icon("१० टक्के", "कर्ज") == "percent"
    drawing = (ROOT / "remotion/src/FigureIcon.tsx").read_text(encoding="utf-8")
    for name, _ in ee.FIGURE_ICONS:
        assert f"case '{name}'" in drawing, name
    assert "default:" in drawing  # 'burst'


def test_only_stat_graphics_carry_an_icon():
    source = "पुणे महापालिकेने 1,200 कोटी रुपयांची तरतूद केली. आयुक्त राजेश पाटील म्हणाले, \"काम दोन वर्षांत पूर्ण होईल.\""
    stat = ee.clean_motion({"type": "stat", "value": "₹1,200 कोटी", "label": "तरतूद"}, source)
    quote = ee.clean_motion({"type": "quote", "value": "काम दोन वर्षांत पूर्ण होईल.", "label": "राजेश पाटील"}, source)
    assert stat["icon"] == "rupee" and "icon" not in quote
    assert 'icon?: string' in (ROOT / "remotion/src/types.ts").read_text(encoding="utf-8")
    assert "FigureIcon" in (ROOT / "remotion/src/MotionGraphic.tsx").read_text(encoding="utf-8")
