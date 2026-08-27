import json
import os
import re
import time
from google import genai
from google.genai import types

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY", "AQ.Ab8RN6Iyt8Gu6j8gsIKSN8QxYSFl77TuZnDXqvao37fRnj9deQ"
)
client = genai.Client(api_key=GEMINI_API_KEY)

EDITORIAL_SYSTEM_INSTRUCTION = """
You are the Creative Director and Executive Editor of MahaSpark.

VISUAL RULES:
1. Generate ONE realistic scene only.
2. Hero subject must dominate the RIGHT side.
3. LEFT side should remain darker and visually clean for large Marathi headlines.
4. Use authentic Indian locations, uniforms, vehicles and government infrastructure.
5. Documentary photojournalism only (Reuters/AP quality).
6. Never create collage, split screen, infographic or illustration.
7. Never include text, logos, watermarks or readable signboards.

EDITORIAL RULES:
- Headlines must be punchy and high impact (2-3 words per part).
- Each bullet MUST BE ultra-crisp (strictly between 10 to 14 Marathi words, fitting in maximum 2 lines).
- Highlight 1-2 key impactful words or figures in each bullet with <span class="hl">...</span>.
"""


def generate_news_content(
    raw_news_text_or_topic: str, max_retries: int = 5
) -> dict:
  prompt = f"""
    RAW NEWS INPUT:
    \"\"\"{raw_news_text_or_topic}\"\"\"

    Analyze the input and return strictly valid JSON matching this schema:
    {{
      "badge": "Category in Marathi (e.g. पुणे अपडेट, मोठी बातमी, वाहतूक)",
      "headline_part1": "Location/Subject (White text, 2-3 words max)",
      "headline_part2": "Action/Hook (Yellow text, 2-3 words max)",
      "hook_pill": "Short high-curiosity stat or phrase (max 5 words)",
      "bullets": [
        {{"icon": "⚡", "text": "Crisp 10-14 words key point with <span class=\\"hl\\">crucial keyword</span>"}},
        {{"icon": "📍", "text": "Crisp 10-14 words impact detail with <span class=\\"hl\\">data or route</span>"}},
        {{"icon": "✅", "text": "Crisp 10-14 words final outcome with <span class=\\"hl\\">official status</span>"}}
      ],
      "visual_prompt": "Write a 40-60 word English editorial scene describing the primary hero subject on right side, exact Indian location, cinematic natural lighting. Vertical 9:16, dark negative space on left, no text, no watermark.",
      "yt_shorts_title": "Create a viral Marathi YouTube Shorts title (55-70 characters). Use curiosity + keyword + emoji. No clickbait.",
      "yt_shorts_description": "Write a 3-4 line SEO-optimized Marathi description. Start with the key news, include Maharashtra keywords naturally, end with: 📲 ताज्या आणि विश्वासार्ह बातम्यांसाठी Follow & Subscribe @mahasparkofficial",
      "yt_shorts_tags": "Generate 12 high-reach hashtags mixing trending, Marathi, Maharashtra and topic-specific tags (e.g. #MahaSpark #MarathiNews #BreakingNews).",
      "ig_reels_caption": "Write an engaging Marathi caption with a strong 2-line hook, concise story summary, one question encouraging comments, and end with: ❤️ Follow @mahasparkofficial | 🔔 Subscribe for daily breaking news.",
      "ig_hashtags": "Generate 5 high-reach hashtags mixing trending, Marathi, Maharashtra and topic-specific tags (e.g. #MahaSpark #MarathiNews #BreakingNews)."
    }}
    """

  for attempt in range(1, max_retries + 1):
    try:
      print(f"🧠 MahaSpark Brain analyzing story (Attempt {attempt})...")
      response = client.models.generate_content(
          model="gemini-3.6-flash",
          contents=prompt,
          config=types.GenerateContentConfig(
              system_instruction=EDITORIAL_SYSTEM_INSTRUCTION,
              response_mime_type="application/json",
              temperature=0.2,
          ),
      )
      return json.loads(response.text)

    except Exception as e:
      err_str = str(e)

      # Handle 429 Rate Limit (Extract the exact wait time)
      if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
        match = re.search(r"retry in (\d+(?:\.\d+)?)s", err_str)
        wait_sec = float(match.group(1)) + 2.0 if match else (attempt * 15)
        print(
            f"⏳ Gemini Rate Limit reached. Pausing for {wait_sec:.1f}s before"
            " retry..."
        )
        time.sleep(wait_sec)

      # Handle 503 Capacity Spikes
      elif "503" in err_str or "UNAVAILABLE" in err_str:
        wait_sec = attempt * 5
        print(f"⏳ Server busy (503). Waiting {wait_sec}s...")
        time.sleep(wait_sec)

      else:
        raise e

  raise Exception(
      f"Failed to generate news pack after {max_retries} attempts due to rate limits."
  )
