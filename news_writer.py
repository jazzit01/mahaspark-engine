import json
import os
import re
import time
from google import genai
from google.genai import types

from config import get_env_value

GEMINI_API_KEY = get_env_value("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("⚠️ GEMINI_API_KEY is not configured. Set it in the environment or .env file.")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

EDITORIAL_SYSTEM_INSTRUCTION = """
You are the Chief Editor of MahaSpark News.
Transform raw news input into grammatically complete, fact-rich, high-impact Marathi news broadcast cards.

NON-NEGOTIABLE QUALITY RULES:
1. REAL, NEUTRAL, FACT-BASED REPORTING:
   - Prioritize verified, concrete, location-specific facts over speculation.
   - Keep the tone neutral and credible. Do not sound like motivation, propaganda, opinion, or a campaign slogan.
   - Do not invent people, numbers, events, quotes, or agencies.
   - If the raw input is vague, do not fabricate details. Return a neutral summary with explicit uncertainty labels if needed.

2. MAHARASHTRA RELEVANCE:
   - Anchor each story to a clear Maharashtra location, district, city, or governance context whenever possible.
   - Explain why the issue matters to Maharashtra or its citizens.
   - Do not write generic national or emotional filler unrelated to the state context.

3. NO VAGUE EUPHEMISMS OR EMPTY FILLER:
   - STRICTLY FORBIDDEN: Do not write vague phrases like "टोकाचे पाऊल उचलले", "अचानक काहीतरी घडले", "पोलीस अधिक तपास करत आहेत", or "हळहळ व्यक्त होत आहे" without concrete context.
   - MANDATORY: State the exact concrete facts: What actually happened? (उदा. गळफास घेऊन आत्महत्या, इमारतीवरून उडी मारून जीवन संपवले, ५ लाखांची लाच स्वीकारताना रंगेहात अटक, कंटेनरने दुचाकीला चिरडले).

4. HEADLINE (Continuous Grammatical Sentence):
   - 'headline_part1' (White text): Primary subject, entity, or specific location (e.g., "पुण्यातील हिंजवडीत,", "मनोज जरांगे पाटलांचा").
   - 'headline_part2' (Yellow text): The direct, specific event or breaking action (e.g., "IT इंजिनिअरची गळफास घेऊन आत्महत्या!", "सरकारला आंदोलनाचा नवा इशारा!").
   - Together they MUST form ONE complete, clear Marathi headline.

5. HOOK PILL (Cause / Trigger / Stat):
   - A punchy 4 to 7 word factual context tag revealing the trigger, reason, or primary impact (e.g., "कामाच्या तणावातून उचलले पाऊल", "३ जणांचा जागीच मृत्यू, १० जखमी").
   - Must NOT merely repeat the headline.

6. BULLET POINTS (Strictly 2 Fact-Packed Points):
   - Exactly 2 bullets. Both must be complete, well-formed Marathi sentences (12 to 18 words).
   - Bullet 1 (घटना, व्यक्ती व अचूक ठिकाण): The concrete incident detail—who was the person/vehicle, exact society/locality/spot, and the exact method or occurrence.
   - Bullet 2 (शोध, कारण, गुन्हा किंवा कारवाई): The investigation detail—suicide note findings, FIR/arrest sections, family/police statements, or hospital status. Never use generic closing filler.
   - Highlight strictly 1 key phrase per bullet in <span class="hl">...</span>.

7. VISUAL / DESIGN INTEGRITY:
   - The visual prompt must describe a real, authentic, editorial photo with no watermark, no visible text, no fake propaganda branding, no copy of another outlet's identity.
   - Keep the scene grounded in India and Maharashtra context whenever possible.

8. AUDIO MOOD RULES:
   - 'serious': STRICTLY fatal casualties, suicides, and deaths only.
   - 'crime': Police arrests, FIRs, raids, court rulings, scams, fraud.
   - 'breaking': Accidents, sudden tragedies, hospitalizations, major political developments, urgent alerts.
   - 'upbeat': Sports victories, achievements, festivals, welfare bonuses.
   - 'neutral': General administrative schemes, agriculture, weather.
"""

CANDIDATE_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]

VALID_AUDIO_MOODS = {"serious", "crime", "breaking", "upbeat", "neutral"}
BLOCKED_NEWS_PATTERNS = [
    "अचानक काहीतरी घडले",
    "टोकाचे पाऊल उचलले",
    "हळहळ व्यक्त होत आहे",
    "हवा आल्यासारखे",
    "बघा काय घडले",
    "महान परिणाम",
    "अशा प्रकारे",
    "जाणून घ्या",
]


def contains_blocked_pattern(text: str) -> bool:
  lower = str(text or "").lower()
  return any(pattern.lower() in lower for pattern in BLOCKED_NEWS_PATTERNS)


def validate_news_pack(data: dict) -> dict:
  """Validate the generated story payload before it reaches render or publish."""
  if not isinstance(data, dict):
    raise ValueError("Generated content is not a JSON object.")

  required_fields = [
      "badge",
      "headline_part1",
      "headline_part2",
      "hook_pill",
      "bullets",
      "audio_mood",
      "visual_prompt",
      "yt_shorts_title",
      "yt_shorts_description",
      "ig_reels_caption",
      "ig_hashtags",
  ]

  for field in required_fields:
    if field not in data or data.get(field) in (None, ""):
      raise ValueError(f"Missing required news field: {field}")

  bullets = data.get("bullets") or []
  if not isinstance(bullets, list) or len(bullets) < 2:
    raise ValueError("News payload must include at least two bullet points.")

  for bullet in bullets[:2]:
    if not isinstance(bullet, dict):
      raise ValueError("Each bullet must be an object with icon and text.")
    text = str(bullet.get("text", "")).strip()
    if len(text) < 20:
      raise ValueError("Bullet text is too short to be useful or credible.")

  headline1 = str(data.get("headline_part1", "")).strip()
  headline2 = str(data.get("headline_part2", "")).strip()
  if len(headline1) < 2 or len(headline2) < 4:
    raise ValueError("Headline is too short or incomplete.")

  mood = str(data.get("audio_mood", "")).strip().lower()
  data["audio_mood"] = mood if mood in VALID_AUDIO_MOODS else "neutral"

  visual_prompt = str(data.get("visual_prompt", "")).strip()
  if len(visual_prompt) < 25:
    raise ValueError("Visual prompt is too weak for a credible news graphic.")

  combined_text = "\n".join(
      [
          headline1,
          headline2,
          str(data.get("hook_pill", "")),
          str(data.get("badge", "")),
          "\n".join(str(b.get("text", "")) for b in bullets if isinstance(b, dict)),
          str(data.get("yt_shorts_title", "")),
          str(data.get("ig_reels_caption", "")),
      ]
  )

  if contains_blocked_pattern(combined_text):
    raise ValueError("Generated content contains vague or promotional wording that is not suitable for neutral news.")

  return data


def generate_news_content(raw_news_text_or_topic: str) -> dict:
  if not raw_news_text_or_topic or not str(raw_news_text_or_topic).strip():
    raise ValueError("Raw news input is empty.")

  if client is None:
    raise RuntimeError("GEMINI_API_KEY is not configured. Please set environment variable GEMINI_API_KEY.")

  prompt = f"""
    RAW NEWS INPUT:
    \"\"\"{raw_news_text_or_topic}\"\"\"

    Analyze and output STRICT valid JSON:
    {{
      "badge": "Short Marathi category (e.g. मोठी बातमी, राजकीय, क्राईम डायरी, पुणे विशेष)",
      "headline_part1": "Subject or specific location (White text, 2-4 words)",
      "headline_part2": "Specific incident/action completing the sentence (Yellow text)",
      "hook_pill": "Factual trigger, reason or impact stat (4-7 words)",
      "bullets": [
        {{"icon": "⚡", "text": "घडलेली नेमकी घटना, व्यक्ती व परिसराचा अचूक तपशील देणारे पूर्ण वाक्य ज्यात <span class=\\"hl\\">नेमकी घटना</span> असेल."}},
        {{"icon": "🚨", "text": "पोलीस तपास, सुसाईड नोट/FIR, प्रत्यक्ष कारण किंवा पुढील कारवाईचे माहितीपूर्ण वाक्य ज्यात <span class=\\"hl\\">कारवाई/तपास</span> असेल."}}
      ],
      "audio_mood": "serious | crime | breaking | upbeat | neutral",
      "is_real_person_or_event": true,
      "person_or_event_query": "Exact English search term for visual context (e.g. 'Manoj Jarange Patil' or 'Pune road accident night police' or 'Maharashtra Assembly Mumbai')",
      "visual_prompt": "Documentary press photo: Real Indian editorial news photograph, authentic Maharashtra scene, natural daylight, candid photojournalism, unedited realism, clean negative space on the left, no watermark, no text, no logo, no third-party watermark, no fake political branding, neutral journalistic composition.",
      "yt_shorts_title": "Viral Marathi YouTube Shorts title (55-70 chars with emoji)",
      "yt_shorts_description": "Clear 3-4 sentence Marathi report summary.\\n\\n📲 ताज्या घडामोडींसाठी आताच Subscribe करा @mahasparkofficial",
      "yt_shorts_tags": "#MahaSpark #MarathiNews #Maharashtra #BreakingNews #LatestNews",
      "ig_reels_caption": "Engaging Marathi post caption with headline context and key facts.\\n\\nतुमचे यावर काय मत आहे? कमेंटमध्ये नक्की सांगा 👇\\n\\n❤️ ताज्या बातम्यांसाठी Follow करा @mahasparkofficial",
      "ig_hashtags": "#MahaSpark #MarathiNews #Maharashtra #BreakingNews #ViralNews"
    }}
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
          clean_json = re.sub(
              r"^```(?:json)?\s*\n?|\n?```\s*$", "", clean_json
          ).strip()

        data = json.loads(clean_json)

        data = validate_news_pack(data)
        return data

      except Exception as e:
        last_error = f"[{model_name}] {type(e).__name__}: {str(e)}"
        err_str = str(e).upper()
        if "429" in err_str or "503" in err_str or "UNAVAILABLE" in err_str:
          wait_time = (attempt + 1) * 3
          print(
              f"⚠️ Model {model_name} busy (503/429). Retrying in {wait_time}s"
              f" (Attempt {attempt + 1}/3)..."
          )
          time.sleep(wait_time)
        else:
          print(f"⚠️ Error on model {model_name}: {last_error[:160]}")
          break

  raise Exception(
      f"Content generation failed across candidate models. Last Error:"
      f" {last_error}"
  )