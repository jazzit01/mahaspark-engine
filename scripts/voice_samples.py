"""Listen before you choose: one short Marathi line in several Gemini voices and every role style.

    python scripts/voice_samples.py                      # the default voices of each role -> out/voices/
    python scripts/voice_samples.py --voices Kore,Puck,Charon,Leda,Orus,Fenrir,Aoede,Zephyr
    python scripts/voice_samples.py --role quiz_cheer --voices Puck,Zephyr,Aoede

Play the .wav files, then set EXPLAINER_TTS_VOICE / QUIZ_TTS_VOICE / QUOTE_TTS_VOICE in .env (and as GitHub variables).
"""

from __future__ import annotations

import argparse
import sys

import editorial_engine as ee
import voices
from config import OUT_DIR

SAMPLE = {
    "explainer": "पुणे महापालिकेने बाराशे कोटी रुपयांची पाणी योजना मंजूर केली आहे. हे काम कसे होणार, ते समजून घेऊया.",
    "quote": "आयुक्त म्हणाले, नव्या जलवाहिन्यांमुळे शहरातील पाणी गळती कमी होईल.",
    "quiz_read": "प्रश्न क्रमांक तीन. पुणे महापालिकेने कोणती योजना मंजूर केली. अ, पाणीपुरवठा योजना. ब, मेट्रो योजना. क, रस्ते योजना. ड, शाळा योजना.",
    "quiz_cheer": "बरोबर उत्तर, अ, पाणीपुरवठा योजना. महापालिकेने बाराशे कोटींची योजना मंजूर केली आहे.",
}
DEFAULT_TRY = ["Kore", "Puck", "Charon", "Leda", "Orus", "Fenrir", "Aoede", "Zephyr"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Make voice samples to choose from.")
    parser.add_argument("--voices", help="comma list of Gemini voice names; default: the voice of each role")
    parser.add_argument("--role", choices=list(voices.STYLES), help="only this role (default: all)")
    args = parser.parse_args(argv)
    roles = [args.role] if args.role else list(voices.STYLES)
    names = [v.strip() for v in args.voices.split(",") if v.strip()] if args.voices else None
    out_dir = OUT_DIR / "voices"
    out_dir.mkdir(parents=True, exist_ok=True)
    failed = 0
    for role in roles:
        kw = voices.role_kwargs(role)
        for voice in names or [kw["voice"] or ee.TTS_VOICE_DEFAULT]:
            path = out_dir / f"{role}-{voice}.wav"
            try:
                ee.reset_tts_state()
                ee.synthesize_voiceover(ee.clean_tts_text(SAMPLE[role]), path, voice=voice, style=kw["style"])
                print(f"✅ {path}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"⚠️ {role}/{voice}: {str(exc)[:140]}")
    print(f"Done. Play the files in {out_dir}.")
    return 1 if failed and failed >= len(roles) else 0


if __name__ == "__main__":
    sys.exit(main())
