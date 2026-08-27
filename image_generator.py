import os
import urllib.parse
import requests

FALLBACK_REMOTE_URL = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=1080&auto=format&fit=crop"


def generate_ai_background(visual_prompt: str) -> str:
  """Generates high-res 9:16 vertical editorial images using free FLUX via Pollinations."""
  os.makedirs("assets/images", exist_ok=True)
  output_path = "assets/images/background.jpg"

  # Enhance prompt for clean photojournalistic vertical output
  enhanced_prompt = f"{visual_prompt}, hyper-realistic documentary photojournalism, authentic Indian editorial scene, cinematic lighting, 8k, no text, no watermark, 9:16 vertical aspect ratio"
  encoded_prompt = urllib.parse.quote(enhanced_prompt)

  # Free, keyless Flux endpoint (1080x1920 portrait format)
  image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model=flux&nologo=true&seed=42"

  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/122.0.0.0 Safari/537.36"
      )
  }

  try:
    print(f"📸 Generating free Flux visual: {visual_prompt[:60]}...")
    response = requests.get(image_url, headers=headers, timeout=60)

    if response.status_code == 200 and len(response.content) > 5000:
      with open(output_path, "wb") as f:
        f.write(response.content)
      print(f"✅ Background generated & saved: {output_path}")
      return output_path
    else:
      raise Exception(
          f"Pollinations returned status {response.status_code} or empty image"
      )

  except Exception as e:
    print(f"⚠️ Primary image generation failed ({e}). Downloading fallback...")
    try:
      resp = requests.get(FALLBACK_REMOTE_URL, headers=headers, timeout=20)
      if resp.status_code == 200:
        with open(output_path, "wb") as f:
          f.write(resp.content)
        return output_path
    except Exception as err:
      print(f"❌ Fallback download error: {err}")

  return output_path
