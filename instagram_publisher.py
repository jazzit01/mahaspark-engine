import os
import time
import requests

IG_USER_ID = os.getenv("INSTAGRAM_USER_ID", "17841405800341984")
IG_ACCESS_TOKEN = os.getenv(
    "INSTAGRAM_ACCESS_TOKEN",
    "EAAWsoO8J6QQBSTZA4IKUwqkwYy9lxYomnL8xzdOuR3Eo3cqMYvN5cVXx6aUVzNYms1VEUnYOk5DmAFzJQquL0uUbHtnTLpLkZCnTw9QrAXenZANusNWit03tVDgZAKaG4LmUY5wMZBOeyPZBAo6rPJeqz8vn84jzTUzRZCifQ6I7WxnJVaR5eNAGmSHnAYfPSvhwTLSMbbnxQ9KZBN8Yz2nq",
)
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "3917b524a07f8c8e8a260d60c57dbf5a")

GRAPH_API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def upload_image_to_public_url(local_image_path: str) -> str:
  """Uploads local card to ImgBB (auto-expires in 1h) so Meta can fetch it."""
  if not os.path.exists(local_image_path):
    raise FileNotFoundError(f"Local graphic missing at: {local_image_path}")

  if not IMGBB_API_KEY:
    raise ValueError(
        "IMGBB_API_KEY is required to generate a public URL for Meta."
    )

  url = "https://api.imgbb.com/1/upload"
  with open(local_image_path, "rb") as file:
    payload = {"key": IMGBB_API_KEY, "expiration": 3600}
    files = {"image": file}
    resp = requests.post(url, data=payload, files=files, timeout=30).json()

    if resp.get("success"):
      return resp["data"]["url"]
    else:
      raise Exception(f"ImgBB upload failed: {resp}")


def post_to_instagram(local_image_path: str, caption_text: str) -> str:
  """Publishes news card to @mahasparkofficial via Meta Graph API."""
  print("📤 Uploading news card to public host for Instagram...")
  public_image_url = upload_image_to_public_url(local_image_path)

  print("📦 Creating Instagram media container...")
  container_resp = requests.post(
      f"{BASE_URL}/{IG_USER_ID}/media",
      data={
          "image_url": public_image_url,
          "caption": caption_text,
          "access_token": IG_ACCESS_TOKEN,
      },
      timeout=30,
  ).json()

  if "id" not in container_resp:
    raise Exception(f"Failed to create IG container: {container_resp}")

  creation_id = container_resp["id"]
  print(f"✅ Container created ({creation_id}). Waiting for Meta ingestion...")

  time.sleep(5)

  print("🚀 Publishing post to @mahasparkofficial...")
  publish_resp = requests.post(
      f"{BASE_URL}/{IG_USER_ID}/media_publish",
      data={"creation_id": creation_id, "access_token": IG_ACCESS_TOKEN},
      timeout=30,
  ).json()

  if "id" not in publish_resp:
    raise Exception(f"Failed to publish IG post: {publish_resp}")

  post_id = publish_resp["id"]
  print(f"🎉 Post live on Instagram! (Post ID: {post_id})")
  return post_id