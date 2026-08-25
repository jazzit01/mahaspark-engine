import json
import os
from google import genai
from google.genai import types


# Reads GEMINI_API_KEY from environment (Cloud/GitHub Actions), falls back to hardcoded string locally
GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY", "AQ.Ab8RN6Iyt8Gu6j8gsIKSN8QxYSFl77TuZnDXqvao37fRnj9deQ"
)

client = genai.Client(api_key=GEMINI_API_KEY)

EDITORIAL_SYSTEM_INSTRUCTION = """
You are the Creative Director of MahaSpark.

Your job is to create visually accurate, trustworthy editorial scenes for AI image generation.

VISUAL RULES:

1. Generate ONE realistic scene only.
2. Hero subject must dominate the RIGHT side.
3. LEFT side should remain darker and visually clean for Marathi headlines.
4. Use authentic Indian locations, uniforms, vehicles and government infrastructure.
5. Documentary photojournalism only (Reuters/AP quality).
6. Never create collage, split screen, infographic or illustration.
7. Never include text, logos, watermarks or readable signboards.

SCENE STRUCTURE:
- Primary hero subject
- Secondary supporting subject
- Exact location
- Camera angle
- Lighting
- Background context

The output must feel like a real press photograph.
"""

def generate_news_content(raw_news_text_or_topic: str) -> dict:
    prompt = f"""
    RAW NEWS INPUT:
    \"\"\"{raw_news_text_or_topic}\"\"\"

    Analyze the input and return strictly valid JSON matching this schema:
    {{
      "badge": "Category in Marathi (e.g. पुणे अपडेट, मोठी बातमी, वाहतूक)",
      "headline_part1": "Location/Subject (White text, 2-4 words)",
      "headline_part2": "Action/Hook (Yellow text, 2-4 words)",
      "hook_pill": "Short high-curiosity stat or phrase (max 6 words)",
      "bullets": [
        {{"icon": "🚆", "text": "First verified key point in crisp Marathi"}},
        {{"icon": "📍", "text": "Second key route/impact detail"}},
        {{"icon": "✅", "text": "Third decision/timeline outcome"}}
      ],
      "visual_prompt": "Write a 40-60 word English editorial scene describing the primary hero subject, supporting subject, exact Indian location, camera angle and natural lighting. Vertical 9:16, hero on right, clean dark space on left, no text, no watermark."
      "yt_shorts_title": "Shorts Title in Marathi with emoji (under 70 chars)",
      "yt_shorts_description": "Concise Marathi SEO description for YouTube Shorts.",
      "yt_shorts_tags": "#MahaSpark #PuneMetro #MarathiNews #Maharashtra #Shorts",
      "ig_reels_caption": "Engaging high-retention Marathi Instagram caption with call to action.",
      "ig_hashtags": "#MahaSpark #PuneUpdates #PuneMetro #MarathiNews #BreakingNews"
    }}
    """

    print("🧠 MahaSpark Brain crafting high-impact news pack...")
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=EDITORIAL_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.2
        )
    )
    return json.loads(response.text)
