import json
from google import genai
from google.genai import types

# 🔑 Your active key:
GEMINI_API_KEY = "AQ.Ab8RN6Iyt8Gu6j8gsIKSN8QxYSFl77TuZnDXqvao37fRnj9deQ"

client = genai.Client(api_key=GEMINI_API_KEY)

EDITORIAL_SYSTEM_INSTRUCTION = """
You are the Creative Director and Executive Editor for 'MahaSpark' (@mahasparkofficial), a high-growth Marathi digital news publisher.

CRITICAL VISUAL PROMPT DIRECTIVE FOR FLUX AI:
1. HERO OBJECT / SUBJECT MUST DOMINATE:
   - Never describe empty rooms, building interiors, walls, windows, or abstract themes.
   - Describe a vivid, recognizable, physical HERO OBJECT clearly visible on the right half of the frame.
   - For Metro/Train news: "A sharp, vibrant modern metro train (Pune Metro style) moving on an elevated concrete viaduct bridge, blue sky with golden sunlight, dynamic low-angle photojournalism shot, crystal clear details, 8k resolution."
   - For Dam/Weather news: "Massive torrent of foaming water rushing out of open dam floodgates, misty spray, daylight press photo."
   - For Tech/Cyber news: "Close-up of modern high-tech enterprise server racks with glowing active LEDs and network fiber optic cables in a data center."
2. PURE HIGH-IMPACT GENERATIVE NEWS PHOTOGRAPHY:
   - Photorealistic, rich saturation, cinematic natural lighting, sharp focus on the right side.
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
      "visual_prompt": "Action-first, vibrant, hyper-realistic English visual prompt with a clear heroic subject on the right side.",
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
