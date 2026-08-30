import json
import os
import re
import time
from google import genai
from google.genai import types

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6Iyt8Gu6j8gsIKSN8QxYSFl77TuZnDXqvao37fRnj9deQ")
client = genai.Client(api_key=GEMINI_API_KEY)

EDITORIAL_SYSTEM_INSTRUCTION = """
You are the Executive Managing Editor of MahaSpark News.

CORE RULES:
1. IDENTIFY ENTITIES: If the news mentions a specific politician, leader, celebrity, or organization (e.g., 'Rohit Pawar', 'Eknath Shinde', 'Narendra Modi', 'MPSC Pune'), extract the exact English search query in 'person_or_event_query'.
2. VISUAL AUTHENTICITY: Describe RAW, realistic Indian press photography. No digital art, no cartoonish render, no studio gloss.
3. BULLETS: Strictly 10 to 14 Marathi words per point. Use <span class="hl">...</span> for key phrases.
"""

CANDIDATE_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]

def generate_news_content(raw_news_text_or_topic: str) -> dict:
    prompt = f"""
    RAW NEWS INPUT:
    \"\"\"{raw_news_text_or_topic}\"\"\"

    Analyze and output STRICT valid JSON:
    {{
      "badge": "Short Marathi category tag (e.g. मोठी बातमी, राजकीय, पुणे क्राइम)",
      "headline_part1": "Location or Person (White text, 2-3 words max)",
      "headline_part2": "Action or Impact (Yellow text, 2-3 words max)",
      "hook_pill": "High-curiosity stat or phrase (max 5 words)",
      "bullets": [
        {{"icon": "⚡", "text": "Crisp 10-14 words key point with <span class=\\"hl\\">crucial keyword</span>"}},
        {{"icon": "📍", "text": "Crisp 10-14 words impact detail with <span class=\\"hl\\">data or route</span>"}},
        {{"icon": "✅", "text": "Crisp 10-14 words final outcome with <span class=\\"hl\\">official status</span>"}}
      ],
      "is_real_person_or_event": true,
      "person_or_event_query": "Exact English name of the politician/celebrity or exact event (e.g. 'Rohit Pawar NCP leader' or 'MPSC students protest Pune' or 'Amravati hospital fire')",
      "visual_prompt": "Documentary press photo: Real Indian editorial news photograph, authentic scene, 35mm lens, natural daylight, candid photojournalism, 9:16 vertical ratio, unedited realism, no watermark, no text.",
      "yt_shorts_title": "Marathi viral Shorts title (55-70 chars with emoji)",
      "yt_shorts_description": "3-4 lines Marathi description ending with: 📲 ताज्या बातम्यांसाठी Follow @mahasparkofficial",
      "yt_shorts_tags": "#MahaSpark #MarathiNews #MaharashtraNews #BreakingNews",
      "ig_reels_caption": "Engaging Marathi post caption with hook, brief details and: ❤️ Follow @mahasparkofficial",
      "ig_hashtags": "#MahaSpark #MarathiNews #Maharashtra #BreakingNews"
    }}
    """

    for model_name in CANDIDATE_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=EDITORIAL_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    temperature=0.2,
                )
            )
            clean_json = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            return json.loads(clean_json)
        except Exception as e:
            err = str(e)
            if "429" in err or "503" in err:
                time.sleep(3)
            continue

    raise Exception("Content generation failed across all models.")