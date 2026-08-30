import os
import random
import urllib.parse
import requests
from ddgs import DDGS

FALLBACK_REMOTE_URL = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=1080&auto=format&fit=crop"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def fetch_real_editorial_photo(query: str, output_path: str) -> bool:
    """Searches and downloads real press/editorial images from the web."""
    try:
        search_term = f"{query} news photo"
        print(f"🔎 Searching real editorial photo for: '{search_term}'...")
        
        with DDGS() as ddgs:
            results = list(ddgs.images(
                keywords=search_term,
                region="in-en",
                safesearch="moderate",
                max_results=6
            ))
            
        for item in results:
            img_url = item.get("image")
            if not img_url or img_url.endswith(".svg") or "icon" in img_url.lower():
                continue
            
            resp = requests.get(img_url, headers=HEADERS, timeout=12)
            if resp.status_code == 200 and len(resp.content) > 15000:
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                print(f"✅ Found & saved authentic editorial photo: {img_url[:60]}...")
                return True
    except Exception as e:
        print(f"⚠️ Real photo search skipped ({e})")
    
    return False

def generate_ai_background(visual_prompt: str, entity_query: str = None) -> str:
    """Gets real photo if available, otherwise generates hyper-realistic press image."""
    os.makedirs("assets/images", exist_ok=True)
    output_path = "assets/images/background.jpg"

    # 1. Try real web editorial photo first if an entity exists
    if entity_query and len(entity_query.strip()) > 3:
        if fetch_real_editorial_photo(entity_query, output_path):
            return output_path

    # 2. Keyless Flux photojournalism fallback
    prompt_clean = " ".join(visual_prompt.split())
    doc_prompt = (
        f"Raw Reuters press photo, candid journalism, real life Indian documentary scene: {prompt_clean}, "
        f"shot on Sony Alpha 35mm, realistic skin textures, authentic Maharashtra lighting, 9:16 portrait, no CGI, no 3D render, no text"
    )
    encoded = urllib.parse.quote(doc_prompt)
    rand_seed = random.randint(1000, 999999)
    image_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&model=flux&nologo=true&seed={rand_seed}"

    try:
        print(f"📸 Generating realistic photojournalism frame...")
        response = requests.get(image_url, headers=HEADERS, timeout=60)
        if response.status_code == 200 and len(response.content) > 8000:
            with open(output_path, "wb") as f:
                f.write(response.content)
            return output_path
    except Exception as e:
        print(f"⚠️ Image generation error: {e}")

    # 3. Static fallback
    try:
        r = requests.get(FALLBACK_REMOTE_URL, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(r.content)
    except Exception:
        pass

    return output_path