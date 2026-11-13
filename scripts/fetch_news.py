"""RSS ingestion and source-article extraction.

RSS items only carry a title and a short snippet, which cannot answer What/When/Who/Where/Why/How
from verified facts. ``fetch_article_text`` therefore downloads the publisher page and extracts its
paragraphs so the editorial engine can write from the real article.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import get_env_value

DEFAULT_RSS_FEEDS = [
    # Lokmat Maharashtra (direct publisher links, best source text) first.
    "https://www.lokmat.com/rss/maharashtra.xml",
    # Google News Marathi top stories and Maharashtra focus (links are redirects, resolved best-effort).
    "https://news.google.com/rss/headlines/section/topic/NATION?hl=mr&gl=IN&ceid=IN:mr",
    "https://news.google.com/rss/search?q=Maharashtra+OR+Pune+when:12h&hl=mr&gl=IN&ceid=IN:mr",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20
MAX_ARTICLE_CHARS = 6000
MIN_ARTICLE_CHARS = 300


@dataclass
class Candidate:
    title: str
    summary: str
    link: str

    @property
    def raw_input(self) -> str:
        """The compact text stored in the Sheet's Raw_News_Input column (also the dedup key)."""
        full = f"{self.title} - {self.summary}" if self.summary else self.title
        return " ".join(full.split())[:300]


def rss_feeds() -> list[str]:
    raw = get_env_value("RSS_FEEDS")
    feeds = [f.strip() for f in raw.split(",") if f.strip()]
    return feeds or DEFAULT_RSS_FEEDS


def strip_html(text: str) -> str:
    if not text:
        return ""
    return " ".join(BeautifulSoup(text, "html.parser").get_text(" ").split())


def iter_candidates(feeds: list[str] | None = None, per_feed: int = 5):
    """Yield candidates feed by feed, newest first. Feed errors are reported and skipped."""
    import feedparser  # imported lazily so the other helpers are testable without it

    for feed_url in feeds or rss_feeds():
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ Failed reading feed {feed_url}: {exc}")
            continue
        for entry in parsed.entries[:per_feed]:
            title = strip_html(entry.get("title", ""))
            if not title:
                continue
            yield Candidate(
                title=title,
                summary=strip_html(entry.get("summary", "")),
                link=(entry.get("link") or "").strip(),
            )


# ----- article text ---------------------------------------------------------------------------


def _decode_google_news_id(link: str) -> str | None:
    """Older Google News article ids embed the publisher URL in a base64 protobuf."""
    match = re.search(r"/articles/([A-Za-z0-9_-]+)", link)
    if not match:
        return None
    token = match.group(1)
    try:
        data = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except Exception:  # noqa: BLE001
        return None
    found = re.search(rb"https?://[^\x00-\x20\x7f-\xff\"<>]+", data)
    return found.group(0).decode("ascii", errors="ignore") if found else None


def resolve_article_url(link: str) -> str:
    """Return the publisher URL for a feed link; the original link if it cannot be resolved."""
    if not link:
        return ""
    host = urlparse(link).netloc.lower()
    if "news.google.com" not in host:
        return link

    decoded = _decode_google_news_id(link)
    if decoded and "news.google.com" not in urlparse(decoded).netloc.lower():
        return decoded

    try:
        resp = requests.get(link, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if "news.google.com" not in urlparse(resp.url).netloc.lower():
            return resp.url
        canonical = BeautifulSoup(resp.text, "html.parser").find("link", rel="canonical")
        href = canonical.get("href") if canonical else ""
        if href and "news.google.com" not in urlparse(href).netloc.lower():
            return href
    except requests.RequestException as exc:
        print(f"⚠️ Could not resolve Google News link: {exc}")
    return link


def extract_article_text(html: str) -> str:
    """Pull the readable paragraphs out of an article page."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "aside", "header", "form", "figure"]):
        tag.decompose()

    container = soup.find("article") or soup.find(attrs={"itemprop": "articleBody"}) or soup
    paragraphs = []
    for p in container.find_all("p"):
        text = " ".join(p.get_text(" ").split())
        if len(text) >= 40:
            paragraphs.append(text)
    return "\n".join(paragraphs)[:MAX_ARTICLE_CHARS]


def fetch_article_text(url: str) -> str:
    """Download ``url`` and return its article text, or "" when it cannot be read or is too short."""
    if not url or "news.google.com" in urlparse(url).netloc.lower():
        return ""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            print(f"⚠️ Article fetch returned HTTP {resp.status_code}: {url}")
            return ""
        resp.encoding = resp.apparent_encoding or "utf-8"
        text = extract_article_text(resp.text)
    except requests.RequestException as exc:
        print(f"⚠️ Article fetch failed: {exc}")
        return ""
    return text if len(text) >= MIN_ARTICLE_CHARS else ""
