import time
import requests

IG_USER_ID = "17841405800341984"
PAGE_TOKEN = "EAAWsoO8J6QQBSTZA4IKUwqkwYy9lxYomnL8xzdOuR3Eo3cqMYvN5cVXx6aUVzNYms1VEUnYOk5DmAFzJQquL0uUbHtnTLpLkZCnTw9QrAXenZANusNWit03tVDgZAKaG4LmUY5wMZBOeyPZBAo6rPJeqz8vn84jzTUzRZCifQ6I7WxnJVaR5eNAGmSHnAYfPSvhwTLSMbbnxQ9KZBN8Yz2nq"

# 1. Provide any sample public image URL to verify container & publish flow
test_img_url = (
    "https://images.unsplash.com/photo-1504711434969-e33886168f5c?q=80&w=1080"
)
caption = "🚩 महास्पार्क चाचणी पोस्ट | @mahasparkofficial"

# Step 1: Create Container
c_res = requests.post(
    f"https://graph.facebook.com/v20.0/{IG_USER_ID}/media",
    data={
        "image_url": test_img_url,
        "caption": caption,
        "access_token": PAGE_TOKEN,
    },
).json()
print("Container Result:", c_res)

# Step 2: Publish Container
time.sleep(5)
p_res = requests.post(
    f"https://graph.facebook.com/v20.0/{IG_USER_ID}/media_publish",
    data={"creation_id": c_res["id"], "access_token": PAGE_TOKEN},
).json()
print("Publish Result:", p_res)