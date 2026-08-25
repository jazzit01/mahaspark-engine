from image_generator import generate_ai_background
from renderer import render_news_tile

if __name__ == "__main__":
  # 1. English Visual Prompt (derived from the news story)
  visual_prompt = (
      "Cyber server room with glowing computer screens displaying encrypted"
      " code in dark room, dramatic gold and blue lighting"
  )

  # 2. Call FLUX (creates assets/images/background.jpg)
  bg_file = generate_ai_background(visual_prompt)

  # 3. Marathi News Copy
  news_payload = {
      "background_path": bg_file,
      "badge": "सायबर सुरक्षा",
      "headline_part1": "बँक ऑफ बडोदाचा",
      "headline_part2": "मोठा डेटा लीक!",
      "hook_pill": "1TB संवेदनशील डेटा डार्क वेबवर?",
      "bullets": [
          {
              "icon": "🛡️",
              "text": "बँकेचा दावा: मुख्य Core Banking सर्व्हर पूर्णपणे सुरक्षित.",
          },
          {
              "icon": "⚠️",
              "text": (
                  "डार्क वेबवर 1TB पेक्षा जास्त संवेदनशील डेटा उपलब्ध असल्याचा"
                  " संशय."
              ),
          },
          {
              "icon": "🔍",
              "text": (
                  "सायबर फॉरेन्सिक्स पथकाकडून सखोल तांत्रिक तपास युद्धपातळीवर"
                  " सुरू."
              ),
          },
      ],
  }

  # 4. Assemble final composite graphic
  print("🎨 Step 2/2: Merging background with Marathi text template...")
  final_post = render_news_tile(news_payload, "output/final_mahaspark_post.png")

  print(f"\n🎉 SUCCESS! Full news tile generated at: {final_post}")
