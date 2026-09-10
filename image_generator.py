import os
import random
import requests
import urllib.parse
from pathlib import Path

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
PRIMARY_DIR = Path("assets/images/backgrounds")
FALLBACK_DIR = Path("assets/images")
TEMP_AI_DIR = Path("output/ai_backgrounds")

def generate_ai_background(visual_prompt: str = "", entity_query: str = None) -> str:
    """
    Generates a unique AI background for FREE using Pollinations.ai.
    Falls back to local assets if generation fails.
    """
    os.makedirs(TEMP_AI_DIR, exist_ok=True)

    # 1. Try Free AI Generation first
    if visual_prompt:
        try:
            print(f"🤖 Generating FREE AI Background for: {visual_prompt[:50]}...")
            
            # Clean and encode the prompt for the URL
            encoded_prompt = urllib.parse.quote(visual_prompt)
            # Use Flux model via Pollinations (Free)
            # Seed is randomized for uniqueness
            seed = random.randint(0, 999999)
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model=flux&seed={seed}&nologo=true"
            
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                file_path = TEMP_AI_DIR / f"bg_{seed}.jpg"
                with open(file_path, "wb") as f:
                    f.write(response.content)
                
                print(f"✅ Unique AI Background Generated: {file_path}")
                return str(file_path.resolve())
            else:
                print(f"⚠️ AI Generation failed (Status {response.status_code}). Falling back to local assets.")
        except Exception as e:
            print(f"⚠️ AI Generation Error: {e}. Falling back to local assets.")

    # 2. Local Assets Fallback (Original Logic)
    candidates = []
    if PRIMARY_DIR.exists():
        candidates = [
            str(f.resolve()) for f in PRIMARY_DIR.iterdir()
            if f.is_file() and f.suffix.lower() in VALID_EXTENSIONS
        ]

    if not candidates and FALLBACK_DIR.exists():
        candidates = [
            str(f.resolve()) for f in FALLBACK_DIR.iterdir()
            if f.is_file() and f.suffix.lower() in VALID_EXTENSIONS and "logo" not in f.stem.lower()
        ]

    if candidates:
        chosen = random.choice(candidates)
        print(f"🎨 Selected local asset background: {chosen}")
        return chosen

    print("⚠️ No backgrounds found. Returning empty string.")
    return ""