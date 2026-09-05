import os
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

TEMPLATE_PATH = Path("template.html").resolve()
LOGO_PATH = Path("assets/images/logo.png").resolve()

def render_news_tile(pack: dict, output_path: str = "output/post.png") -> dict:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    base_stem = os.path.splitext(output_path)[0]

    layer_paths = {
        "full": output_path,
        "bg": f"{base_stem}_bg.png",
        "hl": f"{base_stem}_hl.png",
        "pill": f"{base_stem}_pill.png",
        "b1": f"{base_stem}_b1.png",
        "b2": f"{base_stem}_b2.png",
    }

    bullets = pack.get("bullets", [])[:2]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{TEMPLATE_PATH}")

        # Inject Background Image
        bg_path = pack.get("background_path", "")
        if bg_path and os.path.exists(bg_path):
            bg_url = Path(bg_path).resolve().as_uri()
            page.evaluate(f"document.getElementById('bg-img').src = '{bg_url}';")

        # Inject Brand Logo
        if LOGO_PATH.exists():
            page.evaluate(f"document.getElementById('logo-img').src = '{LOGO_PATH.as_uri()}';")
        elif os.path.exists("assets/logo.png"):
            page.evaluate(f"document.getElementById('logo-img').src = '{Path('assets/logo.png').resolve().as_uri()}';")

        page.evaluate(f"document.getElementById('badge-tag').innerText = {json.dumps(pack.get('badge', ''))};")
        page.evaluate(f"document.getElementById('hl-part1').innerText = {json.dumps(pack.get('headline_part1', ''))};")
        page.evaluate(f"document.getElementById('hl-part2').innerText = {json.dumps(pack.get('headline_part2', ''))};")
        page.evaluate(f"document.getElementById('hook-pill').innerText = {json.dumps(pack.get('hook_pill', ''))};")

        bullet_html = ""
        for idx, b in enumerate(bullets):
            icon = b.get("icon", "⚡")
            text = b.get("text", "")
            bullet_html += f"""
            <div class="bullet-item" id="bullet-{idx}">
              <div class="bullet-icon">{icon}</div>
              <div class="bullet-text">{text}</div>
            </div>
            """
        page.evaluate(f"document.getElementById('bullet-list').innerHTML = `{bullet_html}`;")

        # 1. Full image
        page.evaluate("document.body.className = 'mode-all';")
        page.screenshot(path=layer_paths["full"])

        # 2. Base plate (Background + Scrim + Logo + Badge)
        page.evaluate("document.body.className = 'mode-bg';")
        page.screenshot(path=layer_paths["bg"])

        # 3. Transparent Headline plate
        page.evaluate("document.body.className = 'mode-hl';")
        page.screenshot(path=layer_paths["hl"], omit_background=True)

        # 4. Transparent Hook Pill plate
        page.evaluate("document.body.className = 'mode-pill';")
        page.screenshot(path=layer_paths["pill"], omit_background=True)

        # 5. Transparent Bullet 1 plate
        page.evaluate("document.body.className = 'mode-b1';")
        page.screenshot(path=layer_paths["b1"], omit_background=True)

        # 6. Transparent Bullet 2 plate
        page.evaluate("document.body.className = 'mode-b2';")
        page.screenshot(path=layer_paths["b2"], omit_background=True)

        browser.close()

    print("📸 Rendered layers with dynamic logo: Full, BG, Headline, Hook Pill, B1, B2")
    return layer_paths