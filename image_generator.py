import os
import random
from pathlib import Path

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PRIMARY_DIR = Path("assets/images/backgrounds")
FALLBACK_DIR = Path("assets/images")

def generate_ai_background(visual_prompt: str = "", entity_query: str = None) -> str:
    """
    Selects a random 9:16 background image stored in the assets directories.
    Prioritizes 'assets/images/backgrounds/', then falls back to 'assets/images/'.
    """
    candidates = []

    # 1. Check assets/images/backgrounds
    if PRIMARY_DIR.exists():
        candidates = [
            str(f.resolve()) for f in PRIMARY_DIR.iterdir()
            if f.is_file() and f.suffix.lower() in VALID_EXTENSIONS
        ]

    # 2. Fallback to assets/images (ignoring logo files)
    if not candidates and FALLBACK_DIR.exists():
        candidates = [
            str(f.resolve()) for f in FALLBACK_DIR.iterdir()
            if f.is_file() and f.suffix.lower() in VALID_EXTENSIONS and "logo" not in f.stem.lower()
        ]

    if candidates:
        chosen = random.choice(candidates)
        print(f"🎨 Selected asset background: {chosen}")
        return chosen

    print("⚠️ No background images found in assets directory. Continuing with default template background.")
    return ""