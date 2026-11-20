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

import content_rules
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


MAX_NEWS_AGE_HOURS = 36  # older RSS items are never queued (a stale story must not air as today's news)


def max_news_age_hours() -> float:
    try:
        return float(get_env_value("MAX_NEWS_AGE_HOURS") or MAX_NEWS_AGE_HOURS)
    except ValueError:
        return float(MAX_NEWS_AGE_HOURS)


def is_stale(entry, now=None, max_hours: float | None = None) -> bool:
    """True when the feed entry carries a publish/update time older than the age limit. Undated entries pass."""
    import calendar
    import time as _time

    stamp = entry.get("published_parsed") or entry.get("updated_parsed")
    if not stamp:
        return False
    try:
        published = calendar.timegm(stamp)
    except (TypeError, ValueError, OverflowError):
        return False
    now = _time.time() if now is None else now
    limit = (max_news_age_hours() if max_hours is None else max_hours) * 3600
    return now - published > limit


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
            if is_stale(entry):
                print(f"ℹ️ Skipped old story: {title[:70]}")
                continue
            summary = strip_html(entry.get("summary", ""))
            if content_rules.skip_news(title, summary):
                print(f"ℹ️ Skipped (owner rule, names Savarkar): {title[:70]}")
                continue
            yield Candidate(
                title=title,
                summary=summary,
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


def _decode_with_library(link: str) -> str | None:
    """Current Google News links are opaque tokens; ``googlenewsdecoder`` asks Google for the real URL."""
    try:
        from googlenewsdecoder import gnewsdecoder
    except ImportError:
        return None
    try:
        result = gnewsdecoder(link, interval=1)
    except Exception as exc:  # noqa: BLE001 - network/format errors must never stop the run
        print(f"⚠️ googlenewsdecoder failed: {exc}")
        return None
    ok = result.get("success", result.get("status"))  # older releases used "status"
    url = result.get("decoded_url") if ok else None
    if url and "news.google.com" not in urlparse(url).netloc.lower():
        return url
    return None


def resolve_article_url(link: str) -> str:
    """Return the publisher URL for a feed link; the original link if it cannot be resolved."""
    if not link:
        return ""
    host = urlparse(link).netloc.lower()
    if "news.google.com" not in host:
        return link

    resolved = _decode_with_library(link)
    if resolved:
        return resolved

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


_ARTICLE_CACHE: dict[str, str] = {}


def fetch_article_text(url: str) -> str:
    """Download ``url`` and return its article text, or "" when it cannot be read or is too short.

    Results are cached for the run, so the ingestion check and the later script step fetch a page once."""
    if not url or "news.google.com" in urlparse(url).netloc.lower():
        return ""
    if url not in _ARTICLE_CACHE:
        _ARTICLE_CACHE[url] = _download_article_text(url)
    return _ARTICLE_CACHE[url]


def _download_article_text(url: str) -> str:
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


# ----- extra sources for thin stories -----------------------------------------------------------

THIN_SOURCE_CHARS = 2200  # title + summary + article shorter than this is too thin for a one-minute video
MAX_EXTRA_SOURCES = 2
MAX_COMBINED_CHARS = 12000
_TITLE_TAIL = re.compile(r"\s+[-|–]\s+[^-|–]{2,40}$")


def _headline_query(title: str) -> str:
    return _TITLE_TAIL.sub("", title or "").strip()[:120]


def related_sources(title: str, source_url: str, limit: int = MAX_EXTRA_SOURCES) -> list[tuple[str, str, str]]:
    """Other publishers' reports of the same event as ``(title, url, article_text)``, found with a Google News
    search on the headline. Pages that cannot be read are skipped; any failure returns what was found so far."""
    import difflib
    from urllib.parse import quote

    import feedparser

    query = _headline_query(title)
    if len(query) < 12:
        return []
    feed = f"https://news.google.com/rss/search?q={quote(query)}&hl=mr&gl=IN&ceid=IN:mr"
    found: list[tuple[str, str, str]] = []
    seen_hosts = {urlparse(source_url).netloc.lower()}
    try:
        entries = feedparser.parse(feed).entries[:8]
    except Exception as exc:  # noqa: BLE001
        print(f"ℹ️ Related-source search failed: {exc}")
        return []
    for entry in entries:
        if len(found) >= limit:
            break
        other = strip_html(entry.get("title", ""))
        if not other or is_stale(entry) or difflib.SequenceMatcher(None, _headline_query(other), query).ratio() < 0.3:
            continue  # a different story that merely shares a word
        url = resolve_article_url((entry.get("link") or "").strip())
        host = urlparse(url).netloc.lower()
        if not url or host in seen_hosts or "news.google.com" in host:
            continue
        text = fetch_article_text(url)
        if text:
            seen_hosts.add(host)
            found.append((other, url, text))
    return found


def enrich_thin_source(title: str, summary: str, article: str, source_url: str) -> str:
    """Return ``article`` unchanged when it is rich enough; otherwise append other reports of the same event, each
    labelled, so the writer has enough verified facts for a one-minute video."""
    if len(title) + len(summary) + len(article) >= THIN_SOURCE_CHARS:
        return article
    try:
        extra = related_sources(title, source_url)
    except Exception as exc:  # noqa: BLE001 - extra sources are a bonus, never a reason to fail the story
        print(f"ℹ️ Could not add related sources: {type(exc).__name__}: {exc}")
        return article
    if not extra:
        return article
    print(f"🔎 Thin source: added {len(extra)} more report(s) of the same event.")
    parts = [article] if article else []
    for other_title, url, text in extra:
        parts.append(f"Another report of the same event ({urlparse(url).netloc}): {other_title}\n{text}")
    return "\n\n".join(parts)[:MAX_COMBINED_CHARS]
