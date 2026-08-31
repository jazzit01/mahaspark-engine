import base64
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
import requests


def image_to_base64(image_path: str) -> str:
  """Converts a local file to Base64 data URI to guarantee instant rendering in Chromium."""
  if not image_path or not os.path.exists(image_path):
    return ""
  ext = Path(image_path).suffix.lower().replace(".", "")
  mime = "image/png" if ext == "png" else "image/jpeg"
  with open(image_path, "rb") as f:
    encoded = base64.b64encode(f.read()).decode("utf-8")
  return f"data:{mime};base64,{encoded}"


def url_to_base64(url: str) -> str:
  """Downloads a remote image and converts it to Base64 to ensure it renders without load delays."""
  try:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code == 200:
      content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[
          0
      ]
      encoded = base64.b64encode(resp.content).decode("utf-8")
      return f"data:{content_type};base64,{encoded}"
  except Exception as e:
    print(f"⚠️ Failed to fetch remote background image: {e}")
  return ""


def render_news_tile(data: dict, output_path: str = "output/post.png") -> str:
  template_path = Path("template.html").resolve()
  os.makedirs(os.path.dirname(output_path), exist_ok=True)

  # Convert local logo to Base64
  logo_b64 = image_to_base64("assets/images/logo.png")

  # Handle background image conversion
  bg_src = data.get("background_path", "")
  if bg_src.startswith("http://") or bg_src.startswith("https://"):
    bg_b64 = url_to_base64(bg_src)
  elif os.path.exists(bg_src):
    bg_b64 = image_to_base64(bg_src)
  else:
    bg_b64 = ""

  badge_text = data.get("badge", "ब्रेकिंग न्यूज").replace("'", "\\'")
  hl1_text = data.get("headline_part1", "").replace("'", "\\'")
  hl2_text = data.get("headline_part2", "").replace("'", "\\'")
  hook_text = data.get("hook_pill", "").replace("'", "\\'")
  bullets_json = json.dumps(data.get("bullets", []))

  with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1080, "height": 1920})
    page.goto(f"file://{template_path}", wait_until="load")

    script = f"""
        () => {{
            const bgImg = document.getElementById('bg-img');
            if ('{bg_b64}') {{
                bgImg.src = '{bg_b64}';
            }}

            const logoImg = document.getElementById('logo-img');
            if ('{logo_b64}') {{
                logoImg.src = '{logo_b64}';
            }} else {{
                logoImg.style.display = 'none';
            }}

            document.getElementById('badge-tag').innerText = '{badge_text}';
            document.getElementById('hl-part1').innerText = '{hl1_text}';
            document.getElementById('hl-part2').innerText = '{hl2_text}';

            const hookPill = document.getElementById('hook-pill');
            const hookText = '{hook_text}'.trim();
            if (hookText) {{
                hookPill.innerText = hookText;
                hookPill.style.display = 'inline-block';
            }} else {{
                hookPill.style.display = 'none';
            }}

            const bulletContainer = document.getElementById('bullet-list');
            bulletContainer.innerHTML = '';
            
            const bullets = {bullets_json};
            bullets.forEach(item => {{
                const div = document.createElement('div');
                div.className = 'bullet-item';
                div.innerHTML = `
                    <div class="bullet-icon">${{item.icon || '⚡'}}</div>
                    <div class="bullet-text">${{item.text}}</div>
                `;
                bulletContainer.appendChild(div);
            }});
        }}
        """
    page.evaluate(script)

    # Wait for image rendering & layout stabilization
    page.wait_for_timeout(350)

    abs_output = os.path.abspath(output_path)
    page.screenshot(path=abs_output, type="png")
    browser.close()

  return abs_output


if __name__ == "__main__":
  sample_bg = "https://images.unsplash.com/photo-1541872703-74c5e44368f9?q=80&w=1080&auto=format&fit=crop"

  test_data = {
      "background_path": sample_bg,
      "badge": "मंत्रिमंडळ निर्णय",
      "headline_part1": "रिक्षा-टॅक्सी",
      "headline_part2": "चालकांना मोठी मुदतवाढ",
      "hook_pill": "चालकांना मोठा दिलासा",
      "bullets": [
          {
              "icon": "⚡",
              "text": (
                  "राज्य मंत्रिमंडळ बैठकीत <span class='hl'>रिक्षा आणि"
                  " टॅक्सी</span> चालकांसाठी मोठा निर्णय."
              ),
          },
          {
              "icon": "📍",
              "text": (
                  "मराठी भाषेच्या नियमांची पूर्तता करण्यासाठी चालकांना <span"
                  " class='hl'>मुदतवाढ देण्याचा</span> निर्णय."
              ),
          },
          {
              "icon": "✅",
              "text": (
                  "मुख्यमंत्र्यांच्या या निर्णयामुळे राज्यातील हजारो <span"
                  " class='hl'>वाहन चालकांना मोठा दिलासा</span>."
              ),
          },
      ],
  }

  out = render_news_tile(test_data, "output/test_reels_safe.png")
  print(f"✅ Rendered Reels safe-zone card at: {out}")