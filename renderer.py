import json
import os
import random
from pathlib import Path
from playwright.sync_api import sync_playwright

TEMPLATE_PATH = Path("template.html").resolve()
LOGO_PATH = Path("assets/images/logo.png").resolve()


def render_news_tile(pack: dict, output_path: str = "output/post.png") -> dict:
  os.makedirs(os.path.dirname(output_path), exist_ok=True)
  base_stem = os.path.splitext(output_path)[0]

  layer_paths = {
      "full": output_path,
      "raw_bg": f"{base_stem}_raw_bg.png",
      "frame": f"{base_stem}_frame.png",
      "hl": f"{base_stem}_hl.png",
      "pill": f"{base_stem}_pill.png",
      "b1": f"{base_stem}_b1.png",
      "b2": f"{base_stem}_b2.png",
  }

  bullets = pack.get("bullets", [])[:2]
  theme = random.choice(["yellow", "red"])

  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1080, "height": 1920})
    page.goto(f"file://{TEMPLATE_PATH}")

    # Inject Background Image
    bg_path = pack.get("background_path", "")
    if bg_path and os.path.exists(bg_path):
      bg_url = Path(bg_path).resolve().as_uri()
      page.evaluate(f"document.getElementById('bg-img').src = '{bg_url}';")

    # Inject Logo
    if LOGO_PATH.exists():
      page.evaluate(
          f"document.getElementById('logo-img').src = '{LOGO_PATH.as_uri()}';"
      )
    elif os.path.exists("assets/logo.png"):
      page.evaluate(
          "document.getElementById('logo-img').src ="
          f" '{Path('assets/logo.png').resolve().as_uri()}';"
      )

    # Inject Content
    page.evaluate(
        "document.getElementById('badge-tag').innerText ="
        f" {json.dumps(pack.get('badge', ''))};"
    )
    page.evaluate(
        "document.getElementById('hl-part1').innerText ="
        f" {json.dumps(pack.get('headline_part1', ''))};"
    )
    page.evaluate(
        "document.getElementById('hl-part2').innerText ="
        f" {json.dumps(pack.get('headline_part2', ''))};"
    )
    page.evaluate(
        "document.getElementById('hook-pill').innerText ="
        f" {json.dumps(pack.get('hook_pill', ''))};"
    )

    bullet_html = ""
    for idx, b in enumerate(bullets):
      icon = b.get("icon", "⚡")
      text = b.get("text", "")
      bullet_html += f"""
            <div class="bullet-row" id="bullet-{idx}">
              <div class="bullet-icon">{icon}</div>
              <div class="bullet-text">{text}</div>
            </div>
            """
    page.evaluate(
        f"document.getElementById('bullet-list').innerHTML = `{bullet_html}`;"
    )

    # 1. Full Preview Image (For Sheet thumbnail & Instagram feed preview)
    page.evaluate(f"document.body.className = 'mode-all theme-{theme}';")
    page.screenshot(path=layer_paths["full"])

    # 2. Raw Photo Only (This plate is the only one sent to zoompan)
    page.evaluate(f"document.body.className = 'mode-raw-bg theme-{theme}';")
    page.screenshot(path=layer_paths["raw_bg"])

    # 3. Fixed Frame Only (Logo + Badge + Scrim, 100% transparent and static)
    page.evaluate(f"document.body.className = 'mode-frame theme-{theme}';")
    page.screenshot(path=layer_paths["frame"], omit_background=True)

    # 4. Transparent Headline Plate
    page.evaluate(f"document.body.className = 'mode-hl theme-{theme}';")
    page.screenshot(path=layer_paths["hl"], omit_background=True)

    # 5. Transparent Hook Pill Plate
    page.evaluate(f"document.body.className = 'mode-pill theme-{theme}';")
    page.screenshot(path=layer_paths["pill"], omit_background=True)

    # 6. Transparent Bullet 1 Plate
    page.evaluate(f"document.body.className = 'mode-b1 theme-{theme}';")
    page.screenshot(path=layer_paths["b1"], omit_background=True)

    # 7. Transparent Bullet 2 Plate
    page.evaluate(f"document.body.className = 'mode-b2 theme-{theme}';")
    page.screenshot(path=layer_paths["b2"], omit_background=True)

    browser.close()

  print(
      f"📸 Rendered broadcast plates ({theme}): Raw BG, Fixed Frame, HL, Pill,"
      " B1, B2"
  )
  return layer_paths