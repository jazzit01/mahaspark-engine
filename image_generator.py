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
    cinematic_prompt = (
        f"{prompt}, professional photojournalism, 8k resolution, ultra-detailed, "
        f"vivid cinematic lighting, highly focused main subject positioned clearly on the right half, "
        f"clean dark contrast on left half, award winning press shot, masterpiece, sharp depth of field"
    )
    
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
