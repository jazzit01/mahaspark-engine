import json
import os
import re
import time

import requests

from config import get_env_value

try:  # google-genai is optional: the engine can also run on the other free providers alone.
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None
    types = None

GEMINI_API_KEY = get_env_value("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if (GEMINI_API_KEY and genai) else None

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

# Free-tier friendly order: the Flash-Lite models have a far larger free daily quota than the
# full Flash models. Override without editing code: GEMINI_MODELS="model-a,model-b".
# Check the exact model names and your real limits at https://aistudio.google.com (Rate limits).
CANDIDATE_MODELS = [
    m.strip()
    # "or" matters: GitHub Actions passes an unset variable as an empty string, not as "missing".
    for m in (get_env_value("GEMINI_MODELS") or "gemini-3.5-flash-lite,gemini-3.1-flash-lite").split(",")
    if m.strip()
]

# Extra free providers, tried in this order after Gemini. Each one is used only if its key is set.
# All three speak the OpenAI chat-completions format, so one small function handles them.
OPENAI_COMPATIBLE_PROVIDERS = [
    {
        "name": "groq",
        "key_env": "GROQ_API_KEY",
        "model_env": "GROQ_MODEL",
        "default_model": "llama-3.3-70b-versatile",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "json_mode": True,
    },
    {
        "name": "cerebras",
        "key_env": "CEREBRAS_API_KEY",
        "model_env": "CEREBRAS_MODEL",
        "default_model": "llama-3.3-70b",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "json_mode": True,
    },
    {
        "name": "openrouter",
        "key_env": "OPENROUTER_API_KEY",
        "model_env": "OPENROUTER_MODEL",
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "json_mode": False,  # not every free OpenRouter model supports response_format
    },
]

# Providers/models whose quota ran out during this run. Skipped for the rest of the run so the
# remaining rows do not waste calls (and time) on a quota that cannot recover in seconds.
_EXHAUSTED: set = set()

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


def _parse_json(text: str) -> dict:
  """Turn a model reply into a dict, tolerating code fences and stray text around the JSON."""
  clean = (text or "").strip()
  if clean.startswith("```"):
    clean = re.sub(r"^```(?:json)?\s*\n?|\n?```\s*$", "", clean).strip()
  if not clean.startswith("{"):
    start, end = clean.find("{"), clean.rfind("}")
    if start != -1 and end > start:
      clean = clean[start : end + 1]
  return json.loads(clean)


def _error_code(exc: Exception):
  code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
  return code if isinstance(code, int) else None


def _is_quota_error(exc: Exception) -> bool:
  """True when the provider says we are out of quota / being rate limited."""
  if _error_code(exc) == 429:
    return True
  text = str(exc).upper()
  return bool(re.search(r"HTTP 429|RESOURCE_EXHAUSTED|QUOTA|RATE.?LIMIT", text))


def _is_transient_error(exc: Exception) -> bool:
  """True for short-lived failures worth one quick retry (overload, timeouts)."""
  if _error_code(exc) in (500, 502, 503, 504):
    return True
  if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
    return True
  text = str(exc).upper()
  return any(token in text for token in ("UNAVAILABLE", "OVERLOADED", "TIMED OUT", "HTTP 503", "HTTP 502"))


def _call_gemini(model_name: str, prompt: str) -> str:
  response = client.models.generate_content(
      model=model_name,
      contents=prompt,
      config=types.GenerateContentConfig(
          system_instruction=EDITORIAL_SYSTEM_INSTRUCTION,
          response_mime_type="application/json",
          temperature=0.2,
      ),
  )
  return response.text


def _call_openai_compatible(provider: dict, api_key: str, model: str, prompt: str) -> str:
  payload = {
      "model": model,
      "messages": [
          {"role": "system", "content": EDITORIAL_SYSTEM_INSTRUCTION},
          {"role": "user", "content": prompt},
      ],
      "temperature": 0.2,
  }
  if provider.get("json_mode"):
    payload["response_format"] = {"type": "json_object"}

  response = requests.post(
      provider["url"],
      headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
      json=payload,
      timeout=90,
  )
  if response.status_code != 200:
    raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
  return response.json()["choices"][0]["message"]["content"]


def _build_attempts() -> list:
  """Ordered list of (provider, model, callable) for every provider that has a key configured."""
  attempts = []

  if client is not None:
    for model_name in CANDIDATE_MODELS:
      attempts.append(("gemini", model_name, lambda prompt, m=model_name: _call_gemini(m, prompt)))

  for provider in OPENAI_COMPATIBLE_PROVIDERS:
    api_key = get_env_value(provider["key_env"])
    if not api_key:
      continue
    model = get_env_value(provider["model_env"]) or provider["default_model"]
    attempts.append(
        (
            provider["name"],
            model,
            lambda prompt, p=provider, k=api_key, m=model: _call_openai_compatible(p, k, m, prompt),
        )
    )

  return attempts


def generate_news_content(raw_news_text_or_topic: str) -> dict:
  if not raw_news_text_or_topic or not str(raw_news_text_or_topic).strip():
    raise ValueError("Raw news input is empty.")

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

  attempts = _build_attempts()
  if not attempts:
    raise RuntimeError(
        "No LLM API key configured. Set GEMINI_API_KEY and/or one of GROQ_API_KEY,"
        " CEREBRAS_API_KEY, OPENROUTER_API_KEY (all have free tiers)."
    )

  last_error = ""

  for provider, model_name, call in attempts:
    slot = f"{provider}:{model_name}"
    # A provider-wide quota (Groq, Cerebras, OpenRouter) is tracked per provider, not per model.
    if slot in _EXHAUSTED or provider in _EXHAUSTED:
      continue

    for attempt in range(2):
      try:
        data = validate_news_pack(_parse_json(call(prompt)))
        print(f"✅ Content written by {provider}/{model_name}")
        return data

      except ValueError as e:
        # Bad JSON or failed quality rules: the quota is fine, this model just wrote something
        # unusable. Move on to the next model/provider instead of burning more calls on it.
        last_error = f"[{slot}] {type(e).__name__}: {str(e)}"
        print(f"⚠️ {slot} returned unusable content: {last_error[:160]}")
        break

      except Exception as e:
        last_error = f"[{slot}] {type(e).__name__}: {str(e)}"

        if _is_quota_error(e):
          # Out of free quota. Retrying in a few seconds cannot fix a daily limit, so skip it
          # for the rest of this run and fall through to the next free provider right away.
          _EXHAUSTED.add(slot if provider == "gemini" else provider)
          print(f"⛔ {slot} is out of free quota. Switching provider.")
          break

        if _is_transient_error(e) and attempt == 0:
          print(f"⚠️ {slot} temporarily unavailable. Retrying once in 3s...")
          time.sleep(3)
          continue

        print(f"⚠️ Error on {slot}: {last_error[:160]}")
        break

  raise Exception(
      f"Content generation failed on every configured free provider. Last Error: {last_error}"
  )