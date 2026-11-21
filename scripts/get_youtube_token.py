"""Make the YouTube refresh token on your own computer, with the SAME client id and secret that GitHub will use.

    python scripts/get_youtube_token.py <CLIENT_ID> <CLIENT_SECRET>

A browser window opens; sign in with the Google account that owns the MahaSpark channel and press Allow. The refresh token is
printed (and saved in youtube_refresh_token.txt, which is git-ignored). Put it in GitHub as YOUTUBE_REFRESH_TOKEN together with
the same client id and secret. Works with a "Desktop app" OAuth client (no redirect address to register).
"""

from __future__ import annotations

import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

SCOPE = "https://www.googleapis.com/auth/youtube.upload"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
OUT_FILE = Path("youtube_refresh_token.txt")


def auth_url(client_id: str, redirect_uri: str) -> str:
    query = urlencode({"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": SCOPE,
                       "access_type": "offline", "prompt": "consent"})
    return f"{AUTH_URL}?{query}"


def exchange(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    resp = requests.post(TOKEN_URL, data={"code": code, "client_id": client_id, "client_secret": client_secret,
                                          "redirect_uri": redirect_uri, "grant_type": "authorization_code"}, timeout=30)
    data = resp.json()
    if resp.status_code != 200 or not data.get("refresh_token"):
        raise RuntimeError(f"Google said: HTTP {resp.status_code} {str(data)[:300]}")
    return data


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    client_id, client_secret = argv[0].strip(), argv[1].strip()
    box: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            box.update({k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>Done. You can close this tab and go back to the black window.</h2>".encode("utf-8"))

        def log_message(self, *args):  # silence the access log
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}"
    url = auth_url(client_id, redirect_uri)
    print("Opening the Google sign-in page. If nothing opens, copy this link into your browser:\n\n" + url + "\n")
    threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()
    server.timeout = 300
    while "code" not in box and "error" not in box:
        server.handle_request()
        if server.timeout is None:
            break
    if "error" in box or "code" not in box:
        print(f"❌ Sign-in failed: {box.get('error', 'no answer')}")
        return 1
    try:
        data = exchange(box["code"], client_id, client_secret, redirect_uri)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ {exc}")
        return 1
    OUT_FILE.write_text(data["refresh_token"], encoding="utf-8")
    print("\n✅ Your YOUTUBE_REFRESH_TOKEN (also saved in youtube_refresh_token.txt):\n")
    print(data["refresh_token"])
    print("\nNow save it in GitHub: Settings > Secrets > YOUTUBE_REFRESH_TOKEN, and make sure YOUTUBE_CLIENT_ID and "
          "YOUTUBE_CLIENT_SECRET are the SAME client id and secret you typed here.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
