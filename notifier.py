import os
from whatsapp_api_client_python import API


def send_to_whatsapp(
    image_path: str, caption_text: str, recipient_phone: str
):
  """Sends the generated news tile and Marathi caption directly to your WhatsApp.

  :param image_path: Path to the 1080x1920 rendered .png/.jpg file.
  :param caption_text: The Marathi news caption and hashtags.
  :param recipient_phone: WhatsApp number with country code (e.g.,
  "919876543210").
  """
  # 🔑 Replace with your Green-API Credentials
  ID_INSTANCE = "YOUR_ID_INSTANCE"
  API_TOKEN_INSTANCE = "YOUR_API_TOKEN_INSTANCE"

  greenAPI = API.GreenApi(ID_INSTANCE, API_TOKEN_INSTANCE)

  chat_id = f"{recipient_phone}@c.us"

  print(f"📲 Sending News Tile to WhatsApp ({recipient_phone})...")

  response = greenAPI.sending.sendFileByUpload(
      chatId=chat_id,
      path=os.path.abspath(image_path),
      fileName=os.path.basename(image_path),
      caption=caption_text,
  )

  print(f"✅ WhatsApp Message Sent! Response: {response.data}")
  return response.data
