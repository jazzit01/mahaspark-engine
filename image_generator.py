import os
import random
import urllib.parse
import requests

def generate_ai_background(prompt: str, output_path: str = "assets/images/background.jpg") -> str:
    """
    Generates a copyright-free, ultra-sharp news visual using FLUX.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
     # Enhanced photorealistic styling with high subject focus
    # Premium Editorial FLUX Prompt
    cinematic_prompt = f"""
    {prompt}

    Create a PREMIUM EDITORIAL NEWS PHOTOGRAPH.

    STYLE:
    Reuters, AP News, BBC documentary photojournalism.
    Ultra realistic, authentic Indian environment, natural lighting, 8K, highly detailed.

    COMPOSITION:
    - Vertical 9:16
    - Hero subject on the RIGHT 55%
    - LEFT 45% kept darker and clean for headline
    - One clear scene only
    - Strong depth and realistic perspective

    QUALITY:
    Professional DSLR photography, sharp focus, realistic skin tones.
    Accurate Indian architecture, believable government offices, hospitals,
    metro stations, police, courts and public infrastructure.

    STRICTLY AVOID:
    text, watermark, logo, caption, collage, split screen,
    infographic, CGI, cartoon, illustration, fantasy lighting,
    duplicate people, deformed hands, cropped faces, blurry image.
    """
    
    encoded_prompt = urllib.parse.quote(cinematic_prompt)
    seed = random.randint(100000, 999999)
    
    flux_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model=flux&nologo=true&seed={seed}"
    
    print(f"📸 Generating Hero Visual with FLUX (Seed: {seed})...")
    response = requests.get(flux_url, timeout=60)
    
    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"✅ Background saved at: {output_path}")
        return output_path
    else:
        raise Exception(f"Image generation failed with status {response.status_code}")
