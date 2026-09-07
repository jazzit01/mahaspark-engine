import os

from config import get_env_value

try:
    from whatsapp_api_client_python import API
except ImportError:  # pragma: no cover
    API = None


def send_to_whatsapp(
    image_path: str, caption_text: str, recipient_phone: str
):
  """Sends the generated news tile and Marathi caption directly to your WhatsApp.

  :param image_path: Path to the 1080x1920 rendered .png/.jpg file.
  :param caption_text: The Marathi news caption and hashtags.
  :param recipient_phone: WhatsApp number with country code (e.g.,
  "919876543210").
  """
  if not image_path or not os.path.exists(image_path):
    raise FileNotFoundError(f"Image path does not exist: {image_path}")

  if not recipient_phone or recipient_phone.startswith("91XXXXXXXX"):
    raise ValueError("Recipient phone number is not configured for WhatsApp delivery.")

  ID_INSTANCE = get_env_value("WHATSAPP_ID_INSTANCE")
  API_TOKEN_INSTANCE = get_env_value("WHATSAPP_API_TOKEN")

  if not ID_INSTANCE or not API_TOKEN_INSTANCE or API is None:
    raise RuntimeError(
        "WhatsApp credentials are not configured. Set WHATSAPP_ID_INSTANCE and WHATSAPP_API_TOKEN."
    )

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
