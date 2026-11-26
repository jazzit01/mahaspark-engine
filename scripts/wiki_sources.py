"""Reference text for the evergreen explainer and the general-knowledge quiz: Wikipedia (Marathi and English).

The writer may only use facts that are in the source text, so an evergreen topic needs a source too. The English article
is the full one; the Marathi article (found through the language link) gives the correct Marathi names and terms. Both
go to the model labelled; every number and quote on screen must appear in them (same validators as news).
Wikipedia text is CC BY-SA: the YouTube description credits the articles (``credit_line``).
"""

from __future__ import annotations

import re
from urllib.parse import quote

import requests

UA = {"User-Agent": "MahaSparkBot/1.0 (https://www.youtube.com/@MahaSparkOfficial; news and education channel)"}
MAX_EXTRACT_CHARS = 7000
MIN_ARTICLE_CHARS = 600
TIMEOUT = 25


def _api(lang: str) -> str:
    return f"https://{lang}.wikipedia.org/w/api.php"


def _get(lang: str, params: dict) -> dict:
    resp = requests.get(_api(lang), params={"format": "json", "formatversion": "2", **params}, headers=UA, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def page_url(lang: str, title: str) -> str:
    return f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"


def clean_extract(text: str) -> str:
    """Plain article text without section markers, reference leftovers and runs of blank lines."""
    text = re.sub(r"^=+\s*(.*?)\s*=+\s*$", r"\1.", str(text or ""), flags=re.M)
    text = re.sub(r"\[\d+\]|\[[a-z]\]", "", text)
    return re.sub(r"\n{2,}", "\n", text).strip()


def fetch_extract(title: str, lang: str = "en") -> dict | None:
    """{title, url, text, mr_title} of one article (redirects followed), or None when it does not exist or is stub-short."""
    other = "en" if lang == "mr" else "mr"
    try:
        data = _get(lang, {"action": "query", "prop": "extracts|langlinks", "explaintext": 1, "redirects": 1, "titles": title,
                           "lllang": other, "lllimit": 1})
        page = (data.get("query", {}).get("pages") or [{}])[0]
    except Exception as exc:  # noqa: BLE001 - one bad lookup must not stop the video
        print(f"⚠️ Wikipedia lookup failed for '{title}': {str(exc)[:100]}")
        return None
    text = clean_extract(page.get("extract", ""))
    if page.get("missing") or len(text) < MIN_ARTICLE_CHARS:
        return None
    links = page.get("langlinks") or []
    return {"title": page.get("title", title), "url": page_url(lang, page.get("title", title)), "text": text[:MAX_EXTRACT_CHARS],
            f"{other}_title": links[0].get("title", "") if links else ""}


def search_title(query: str, lang: str = "en") -> str | None:
    try:
        hits = _get(lang, {"action": "query", "list": "search", "srsearch": query, "srlimit": 1}).get("query", {}).get("search", [])
        return hits[0]["title"] if hits else None
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ Wikipedia search failed for '{query}': {str(exc)[:100]}")
        return None


def fetch_topic(topic: str, search: bool = True) -> dict | None:
    """The reference text of ``topic`` (an English Wikipedia title or any search words):
    {"title", "url", "urls", "text"} with the Marathi article added when one exists."""
    en = fetch_extract(topic, "en")
    if not en and search:
        found = search_title(topic, "en")
        en = fetch_extract(found, "en") if found else None
    if not en:
        return None
    parts = [f"[English Wikipedia: {en['title']}]\n{en['text']}"]
    urls = [en["url"]]
    if en["mr_title"]:
        mr = fetch_extract(en["mr_title"], "mr")
        if mr:
            parts.insert(0, f"[Marathi Wikipedia: {mr['title']}] (use these Marathi names and terms)\n{mr['text']}")
            urls.append(mr["url"])
    return {"title": en["title"], "url": en["url"], "urls": urls, "text": "\n\n".join(parts)}


def credit_line(urls: list[str]) -> str:
    """Attribution for the YouTube description (Wikipedia is CC BY-SA)."""
    wiki = [u for u in urls if "wikipedia.org" in u]
    return ("📚 संदर्भ: Wikipedia (CC BY-SA) - " + " , ".join(wiki[:4])) if wiki else ""


def discover_topic(topic: str) -> dict | None:
    """Search Marathi first for a Marathi topic, progressively removing descriptive suffixes."""
    if not re.search(r"[\u0900-\u097f]", topic):
        return fetch_topic(topic)
    words = topic.split()
    for query in dict.fromkeys((topic, " ".join(words[:2]))):
        if not query:
            continue
        title = search_title(query, "mr")
        if title:
            page = fetch_extract(title, "mr")
            if page:
                reference = {"title": page["title"], "urls": [page["url"]],
                             "text": f"[Marathi Wikipedia: {page['title']}]\n{page['text']}"}
                if len(page["text"]) < 3500 and page.get("en_title"):
                    english = fetch_extract(page["en_title"], "en")
                    if english:
                        reference["urls"].append(english["url"])
                        reference["text"] += f"\n\n[English Wikipedia: {english['title']}]\n{english['text']}"
                return reference
    return None
