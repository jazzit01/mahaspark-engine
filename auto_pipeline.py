from image_generator import generate_ai_background
from news_writer import generate_news_content
from notifier import send_to_whatsapp  # Importing our notifier
from renderer import render_news_tile


def run_full_pipeline(
    news_story: str,
    output_filename: str = "latest_post.png",
    send_whatsapp: bool = True,
    target_phone: str = "91XXXXXXXXXX",
):
  print("=" * 60)
  print(f"🚀 INGESTING NEWS: {news_story}")
  print("=" * 60)

  # 1. Gemini writes the Marathi copy & English visual prompt
  news_pack = generate_news_content(news_story)
  print(
      f"📰 HEADLINE: {news_pack['headline_part1']} {news_pack['headline_part2']}"
  )

  # 2. FLUX generates the 9:16 background photo
  bg_path = generate_ai_background(news_pack["visual_prompt"])

  # 3. Render 1080x1920 graphic
  news_pack["background_path"] = bg_path
  output_path = f"output/{output_filename}"
  final_image = render_news_tile(news_pack, output_path)

  # 4. Prepare social caption
  full_caption = (
      f"⚡ *{news_pack['headline_part1']} {news_pack['headline_part2']}*\n\n"
      f"{news_pack['caption']}\n\n"
      f"{news_pack['hashtags']}\n\n"
      f"📲 ताज्या बातम्यांसाठी फॉलो करा: @mahasparkofficial"
  )

  print(f"🎉 FINAL POST RENDERED: {final_image}")

  # 5. Dispatch to WhatsApp
  if send_whatsapp:
    send_to_whatsapp(
        image_path=final_image,
        caption_text=full_caption,
        recipient_phone=target_phone,
    )

  return final_image


if __name__ == "__main__":
  sample_news = "महाराष्ट्रात सर्व सरकारी कार्यालयांमध्ये 5 दिवसांचा आठवडा कायम राहणार, सामान्य प्रशासन विभागाचे स्पष्टीकरण"

  # Replace with your phone number (e.g., 9198XXXXXXXX)
  run_full_pipeline(
      sample_news,
      "govt_office_news.png",
      send_whatsapp=False,  # Set to True after adding credentials in notifier.py
      target_phone="91XXXXXXXXXX",
  )
