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
You are the Chief Editor of MahaSpark News.
Transform raw news input into grammatically complete, fact-rich, high-impact Marathi news broadcast cards.

STRICT EDITORIAL & FACT-DELIVERY RULES:
1. NO VAGUE EUPHEMISMS OR EMPTY FILLER:
   - STRICTLY FORBIDDEN: Do not write vague phrases like "टोकाचे पाऊल उचलले", "अचानक काहीतरी घडले", "पोलीस अधिक तपास करत आहेत", or "हळहळ व्यक्त होत आहे" without concrete context.
   - MANDATORY: State the exact concrete facts: What actually happened? (उदा. गळफास घेऊन आत्महत्या, इमारतीवरून उडी मारून जीवन संपवले, ५ लाखांची लाच स्वीकारताना रंगेहात अटक, कंटेनरने दुचाकीला चिरडले).

2. HEADLINE (Continuous Grammatical Sentence):
   - 'headline_part1' (White text): Primary subject, entity, or specific location (e.g., "पुण्यातील हिंजवडीत,", "मनोज जरांगे पाटलांचा").
   - 'headline_part2' (Yellow text): The direct, specific event or breaking action (e.g., "IT इंजिनिअरची गळफास घेऊन आत्महत्या!", "सरकारला आंदोलनाचा नवा इशारा!").
   - Together they MUST form ONE complete, clear Marathi headline.

3. HOOK PILL (Cause / Trigger / Stat):
   - A punchy 4 to 7 word factual context tag revealing the trigger, reason, or primary impact (e.g., "कामाच्या तणावातून उचलले पाऊल", "३ जणांचा जागीच मृत्यू, १० जखमी").
   - Must NOT merely repeat the headline.

4. BULLET POINTS (Strictly 2 Fact-Packed Points):
   - Exactly 2 bullets. Both must be complete, well-formed Marathi sentences (12 to 18 words).
   - Bullet 1 (घटना, व्यक्ती व अचूक ठिकाण): The concrete incident detail—who was the person/vehicle, exact society/locality/spot, and the exact method or occurrence.
   - Bullet 2 (शोध, कारण, गुन्हा किंवा कारवाई): The investigation detail—suicide note findings, FIR/arrest sections, family/police statements, or hospital status. Never use generic closing filler.
   - Highlight strictly 1 key phrase per bullet in <span class="hl">...</span>.

5. AUDIO MOOD RULES:
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


def generate_news_content(raw_news_text_or_topic: str) -> dict:
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
      "visual_prompt": "Documentary press photo: Real Indian editorial news photograph, authentic scene, natural daylight, candid photojournalism, unedited realism, clean negative space on the left, no watermark, no text.",
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

        mood = str(data.get("audio_mood", "")).strip().lower()
        data["audio_mood"] = mood if mood in VALID_AUDIO_MOODS else "neutral"

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