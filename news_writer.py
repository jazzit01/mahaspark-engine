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
1. IDENTIFY ENTITIES: If the news mentions a specific politician, leader, celebrity, or organization (e.g., 'Rohit Pawar', 'Eknath Shinde', 'Narendra Modi', 'Manoj Jarange Patil', 'MPSC Pune'), extract the exact English search query in 'person_or_event_query'.
2. VISUAL AUTHENTICITY: Describe RAW, realistic Indian press photography. No digital art, no cartoonish render, no studio gloss.
3. BULLETS: Strictly 10 to 14 Marathi words per point. Use <span class="hl">...</span> for key phrases.
4. AUDIO MOOD: Accurately classify the story's emotional tone into one of: 'serious', 'crime', 'breaking', 'upbeat', or 'neutral'.
"""

# Active production models
CANDIDATE_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]

VALID_AUDIO_MOODS = {"serious", "crime", "breaking", "upbeat", "neutral"}


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
      "audio_mood": "serious | crime | breaking | upbeat | neutral",
      "is_real_person_or_event": true,
      "person_or_event_query": "Exact English name of the politician/celebrity or exact event (e.g. 'Manoj Jarange Patil' or 'MPSC students protest Pune' or 'Nepal Flood')",
      "visual_prompt": "Documentary press photo: Real Indian editorial news photograph, authentic scene, 35mm lens, natural daylight, candid photojournalism, 9:16 vertical ratio, unedited realism, no watermark, no text.",
      "yt_shorts_title": "Marathi viral Shorts title (55-70 chars with emoji)",
      "yt_shorts_description": "3-4 lines Marathi description ending with: 📲 ताज्या बातम्यांसाठी Follow @mahasparkofficial",
      "yt_shorts_tags": "#MahaSpark #MarathiNews #MaharashtraNews #BreakingNews",
      "ig_reels_caption": "Engaging Marathi post caption with hook, brief details and: ❤️ Follow @mahasparkofficial",
      "ig_hashtags": "#MahaSpark #MarathiNews #Maharashtra #BreakingNews"
    }}

    AUDIO MOOD RULES:
    - 'serious': Accidents, deaths, tragedies, hospitalizations, funeral, flood, disaster.
    - 'crime': Police arrests, FIRs, raids, court rulings, scams, fraud.
    - 'breaking': Urgent alerts, major political developments, sudden government decisions.
    - 'upbeat': Sports victories, achievements, festivals, positive milestones.
    - 'neutral': General government schemes, administrative notices, agriculture, weather.
    """

    last_error = ""

    for model_name in CANDIDATE_MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=EDITORIAL_SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )

                clean_json = response.text.strip()
                if clean_json.startswith("```"):
                    clean_json = re.sub(r"^```(?:json)?\s*\n?|\n?```\s*$", "", clean_json).strip()

                data = json.loads(clean_json)

                # Ensure safe fallback for audio_mood
                mood = str(data.get("audio_mood", "")).strip().lower()
                data["audio_mood"] = mood if mood in VALID_AUDIO_MOODS else "neutral"

                return data

            except Exception as e:
                last_error = f"[{model_name}] {type(e).__name__}: {str(e)}"
                err_str = str(e).upper()
                if "429" in err_str or "503" in err_str or "UNAVAILABLE" in err_str:
                    wait_time = (attempt + 1) * 3
                    print(f"⚠️ Model {model_name} busy (503/429). Retrying in {wait_time}s (Attempt {attempt + 1}/3)...")
                    time.sleep(wait_time)
                else:
                    print(f"⚠️ Error on model {model_name}: {last_error[:160]}")
                    break  # Failover to the next candidate model

    raise Exception(f"Content generation failed across all models. Last Error: {last_error}")