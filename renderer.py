import base64
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright


def image_to_base64(image_path: str) -> str:
  """Converts a local file to Base64 data URI to guarantee instant rendering in Chromium."""
  if not os.path.exists(image_path):
    return ""
  ext = Path(image_path).suffix.lower().replace(".", "")
  mime = "image/png" if ext == "png" else "image/jpeg"
  with open(image_path, "rb") as f:
    encoded = base64.b64encode(f.read()).decode("utf-8")
  return f"data:{mime};base64,{encoded}"


def render_news_tile(data: dict, output_path: str = "output/post.png") -> str:
  template_path = Path("template.html").resolve()
  os.makedirs(os.path.dirname(output_path), exist_ok=True)

  # Convert local logo to Base64 so it never fails to load
  logo_b64 = image_to_base64("assets/images/logo.png")

  # Handle background image: local file to Base64 or external URL
  bg_src = data.get("background_path", "")
  if os.path.exists(bg_src):
    bg_src = image_to_base64(bg_src)

  with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1080, "height": 1920})
    page.goto(f"file://{template_path}", wait_until="networkidle")

    script = f"""
        () => {{
            const bgImg = document.getElementById('bg-img');
            bgImg.src = '{bg_src}';

            const logoImg = document.getElementById('logo-img');
            if ('{logo_b64}') {{
                logoImg.src = '{logo_b64}';
            }} else {{
                logoImg.style.display = 'none';
            }}

            document.getElementById('badge-tag').innerText = '{data.get("badge", "ब्रेकिंग न्यूज")}';
            document.getElementById('hl-part1').innerText = '{data.get("headline_part1", "")}';
            document.getElementById('hl-part2').innerText = '{data.get("headline_part2", "")}';

            const hookPill = document.getElementById('hook-pill');
            const hookText = '{data.get("hook_pill", "")}';
            if (hookText.trim()) {{
                hookPill.innerText = hookText;
                hookPill.style.display = 'inline-block';
            }} else {{
                hookPill.style.display = 'none';
            }}

            const bulletContainer = document.getElementById('bullet-list');
            bulletContainer.innerHTML = '';
            
            const bullets = {json.dumps(data.get("bullets", []))};
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
    page.wait_for_timeout(400)

    abs_output = os.path.abspath(output_path)
    page.screenshot(path=abs_output, type="png")
    browser.close()

  return abs_output


if __name__ == "__main__":
  sample_hacker_bg = "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?q=80&w=1080&auto=format&fit=crop"

  test_data = {
      "background_path": sample_hacker_bg,
      "badge": "सायबर सुरक्षा",
      "headline_part1": "बँक ऑफ बडोदाचा",
      "headline_part2": "मोठा डेटा लीक!",
      "hook_pill": "1TB संवेदनशील डेटा डार्क वेबवर?",
      "bullets": [
          {
              "icon": "🛡️",
              "text": (
                  "बँकेचा दावा: मुख्य <span class='hl'>Core Banking</span>"
                  " सर्व्हर पूर्णपणे सुरक्षित."
              ),
          },
          {
              "icon": "⚠️",
              "text": (
                  "डार्क वेबवर <span class='hl'>1TB पेक्षा जास्त</span>"
                  " संवेदनशील डेटा उपलब्ध असल्याचा संशय."
              ),
          },
          {
              "icon": "🔍",
              "text": (
                  "सायबर फॉरेन्सिक्स पथकाकडून <span class='hl'>सखोल तांत्रिक"
                  " तपास</span> युद्धपातळीवर सुरू."
              ),
          },
      ],
  }

  out = render_news_tile(test_data, "output/test_post.png")
  print(f"✅ Rendered updated post at: {out}")
