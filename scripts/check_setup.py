"""Check every secret the pipelines need and say in plain words what is wrong. ``python scripts/check_setup.py``.

Nothing is published or changed. Each line is OK / PROBLEM; the exit code is 1 if anything failed.
"""

from __future__ import annotations

import sys

import requests

from config import get_env_value


def line(ok: bool, name: str, detail: str = "") -> bool:
    print(f"{'✅ OK     ' if ok else '❌ PROBLEM'}  {name}{': ' + detail if detail else ''}")
    return ok


def check_sheet() -> bool:
    try:
        from sheet_queue import SheetQueue

        queue = SheetQueue.connect()
        queue.longform_known_keys()
        return line(True, "Google Sheet (GCP_CREDENTIALS)", "connected and readable")
    except Exception as exc:  # noqa: BLE001
        text = str(exc)
        hint = ""
        if "invalid_grant" in text or "JWT" in text:
            hint = " -> the service account key is old/deleted. Create a new JSON key and save the WHOLE file as the GCP_CREDENTIALS secret."
        elif "403" in text or "PERMISSION" in text.upper():
            hint = " -> share the Google Sheet with the service account's client_email (Editor)."
        elif "No such file" in text or "credentials" in text.lower():
            hint = " -> credentials.json / GCP_CREDENTIALS is missing."
        return line(False, "Google Sheet (GCP_CREDENTIALS)", text[:200] + hint)


def check_youtube() -> bool:
    import youtube_upload as yt

    try:
        client_id, secret, refresh = yt.credentials()
    except yt.YouTubeUnavailable as exc:
        return line(False, "YouTube secrets", str(exc))
    try:
        token = yt.access_token(client_id, secret, refresh)
    except RuntimeError as exc:
        return line(False, "YouTube refresh token", str(exc))
    info = requests.get("https://oauth2.googleapis.com/tokeninfo", params={"access_token": token}, timeout=20).json()
    scopes = str(info.get("scope", ""))
    if "youtube" not in scopes:
        return line(False, "YouTube scope", f"the token has scopes '{scopes}', it needs https://www.googleapis.com/auth/youtube.upload")
    line(True, "YouTube refresh token", f"valid, scope: {scopes.replace('https://www.googleapis.com/auth/', '')}")
    chan = requests.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "snippet", "mine": "true"},
                        headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if chan.status_code == 200 and chan.json().get("items"):
        line(True, "YouTube channel", chan.json()["items"][0]["snippet"]["title"])
    else:
        print("ℹ️  The channel name cannot be read with an upload-only token; that is normal.")
    return True


def check_gemini() -> bool:
    key = (get_env_value("GEMINI_API_KEYS").split(",")[0] or get_env_value("GEMINI_API_KEY")).strip()
    if not key:
        return line(False, "Gemini API key", "GEMINI_API_KEY is not set")
    resp = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"pageSize": 1000},
                        headers={"x-goog-api-key": key}, timeout=20)
    if resp.status_code != 200:
        return line(False, "Gemini API key", f"HTTP {resp.status_code}: {resp.text[:120]}")
    import llm_providers

    names = [m["name"].removeprefix("models/") for m in resp.json().get("models", []) if "generateContent" in (m.get("supportedGenerationMethods") or [])]
    return line(True, "Gemini API key", "text models: " + ", ".join(llm_providers.rank_text_models(names)[:5]))


def check_telegram() -> bool:
    token = get_env_value("TELEGRAM_BOT_TOKEN").strip()
    if not token:
        return line(False, "Telegram bot", "TELEGRAM_BOT_TOKEN is not set")
    resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=20)
    if resp.status_code != 200:
        return line(False, "Telegram bot", f"HTTP {resp.status_code}: the token is wrong or was revoked (create a new one in BotFather)")
    return line(True, "Telegram bot", "@" + resp.json()["result"].get("username", "?"))


def main() -> int:
    results = [check_gemini(), check_telegram(), check_sheet(), check_youtube()]
    print("\nAll good." if all(results) else "\nFix the PROBLEM lines above, then run this check again.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
