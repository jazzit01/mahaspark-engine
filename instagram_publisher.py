import os
import time
import requests

# Instagram Account ID
IG_USER_ID = os.getenv("INSTAGRAM_USER_ID", "17841405800341984")

# Meta Access Token
IG_ACCESS_TOKEN = os.getenv(
    "INSTAGRAM_ACCESS_TOKEN",
    "EAAWsoO8J6QQBSTZA4IKUwqkwYy9lxYomnL8xzdOuR3Eo3cqMYvN5cVXx6aUVzNYms1VEUnYOk5DmAFzJQquL0uUbHtnTLpLkZCnTw9QrAXenZANusNWit03tVDgZAKaG4LmUY5wMZBOeyPZBAo6rPJeqz8vn84jzTUzRZCifQ6I7WxnJVaR5eNAGmSHnAYfPSvhwTLSMbbnxQ9KZBN8Yz2nq"
)

GRAPH_API_VERSION = "v20.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def post_reel_to_instagram(local_video_path: str, caption_text: str) -> str:
    """Uploads local MP4 directly to Meta via Resumable Upload protocol and publishes Instagram Reel."""
    if not os.path.exists(local_video_path):
        raise FileNotFoundError(f"Video file not found: {local_video_path}")

    file_size = os.path.getsize(local_video_path)
    print(f"📦 [Instagram] Initiating Direct Reels container ({file_size} bytes)...")

    # 1. Initialize Resumable Upload Container with thumb_offset (5.0s mark)
    init_url = f"{BASE_URL}/{IG_USER_ID}/media"
    init_payload = {
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption_text,
        "share_to_feed": "true",
        "thumb_offset": 5000,
        "access_token": IG_ACCESS_TOKEN,
    }
    
    init_resp = requests.post(init_url, data=init_payload, timeout=30).json()
    if "id" not in init_resp:
        raise Exception(f"Instagram container initialization failed: {init_resp}")

    creation_id = init_resp["id"]
    upload_url = init_resp.get("uri", f"https://rupload.facebook.com/ig-api-upload/{GRAPH_API_VERSION}/{creation_id}")
    print(f"⏳ [Instagram] Container initialized ({creation_id}). Streaming bytes to Meta servers...")

    # 2. Upload the Binary MP4 Video Directly to Meta
    with open(local_video_path, "rb") as video_file:
        video_bytes = video_file.read()

    upload_headers = {
        "Authorization": f"OAuth {IG_ACCESS_TOKEN}",
        "offset": "0",
        "file_size": str(file_size),
        "Content-Type": "application/octet-stream",
    }

    upload_res = requests.post(upload_url, headers=upload_headers, data=video_bytes, timeout=120)
    if upload_res.status_code not in (200, 201):
        raise Exception(f"Instagram direct video upload failed ({upload_res.status_code}): {upload_res.text}")

    print("✅ [Instagram] Video binary uploaded. Waiting for server encoding...")

    # 3. Poll Container Status Until FINISHED
    status_url = f"{BASE_URL}/{creation_id}?fields=status_code&access_token={IG_ACCESS_TOKEN}"
    for attempt in range(20):
        time.sleep(5)
        status_data = requests.get(status_url, timeout=30).json()
        status = status_data.get("status_code")
        print(f"   Status check ({attempt + 1}/20): {status}")

        if status == "FINISHED":
            print("✅ [Instagram] Video successfully processed by Meta servers.")
            break
        elif status == "ERROR":
            raise Exception(f"Meta server failed processing video: {status_data}")

    # 4. Publish the Processed Reel
    print("🚀 [Instagram] Publishing Reel to @mahasparkofficial...")
    publish_resp = requests.post(
        f"{BASE_URL}/{IG_USER_ID}/media_publish",
        data={"creation_id": creation_id, "access_token": IG_ACCESS_TOKEN},
        timeout=30,
    ).json()

    if "id" not in publish_resp:
        raise Exception(f"Failed to publish Instagram Reel: {publish_resp}")

    post_id = publish_resp["id"]
    print(f"🎉 Live Reel published successfully on Instagram! Post ID: {post_id}")
    return post_id