import os
import random
import urllib.parse
import requests

FALLBACK_REMOTE_URL = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=1080&auto=format&fit=crop"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def generate_ai_background(
    visual_prompt: str, entity_query: str = None
) -> str:
  """Generates hyper-realistic Indian press photojournalism backgrounds using Flux AI."""
  os.makedirs("assets/images", exist_ok=True)
  output_path = "assets/images/background.jpg"

  # Clean and craft a strict editorial photojournalism prompt
  prompt_clean = " ".join(visual_prompt.split())
  doc_prompt = (
      f"Raw authentic Indian editorial press photography: {prompt_clean}, "
      "main subject positioned naturally on the right side of frame, clean"
      " negative space on the left, "
      "shot on Sony A7 IV 35mm lens, natural daylight, candid photojournalism,"
      " 9:16 vertical ratio, realistic lighting, "
      "unedited realism, no text, no captions, no logos, no watermark, no"
      " graphic design overlays"
  )

  encoded = urllib.parse.quote(doc_prompt)
  rand_seed = random.randint(1000, 999999)
  image_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&model=flux&nologo=true&seed={rand_seed}"

  try:
    print("📸 Generating clean AI photojournalism frame via Flux...")
    response = requests.get(image_url, headers=HEADERS, timeout=60)
    if response.status_code == 200 and len(response.content) > 8000:
      with open(output_path, "wb") as f:
        f.write(response.content)
      print("✅ AI Background visual generated successfully.")
      return output_path
  except Exception as e:
    print(f"⚠️ Image generation error: {e}")

  # Fallback to neutral background if network fails
  try:
    r = requests.get(FALLBACK_REMOTE_URL, headers=HEADERS, timeout=15)
    if r.status_code == 200:
      with open(output_path, "wb") as f:
        f.write(r.content)
  except Exception:
    pass

  return output_path