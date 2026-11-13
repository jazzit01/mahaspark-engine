import base64

import fetch_news as fn

HTML = """
<html><body><nav><p>menu menu menu menu menu menu menu menu menu menu menu</p></nav>
<article>
<p>पुणे महापालिकेने शहरातील नव्या उड्डाणपुलाच्या कामाला मंगळवारी अंतिम मंजुरी दिली आहे.</p>
<p>लहान.</p>
<p>प्रकल्पासाठी एकशे वीस कोटी रुपयांची तरतूद करण्यात आली असून काम पुढील महिन्यात सुरू होईल.</p>
</article><footer><p>footer footer footer footer footer footer footer footer footer</p></footer>
<script>var x = 1;</script></body></html>
"""


def test_extract_article_text_keeps_article_paragraphs_only():
    text = fn.extract_article_text(HTML)
    assert "उड्डाणपुलाच्या" in text and "तरतूद" in text
    assert "menu" not in text and "footer" not in text and "लहान." not in text


def test_candidate_raw_input_is_compact_and_capped():
    c = fn.Candidate("शीर्षक", "सारांश " * 200, "https://x")
    assert len(c.raw_input) <= 300 and c.raw_input.startswith("शीर्षक - ")


def test_google_news_id_decoding_finds_embedded_url():
    payload = b"\x08\x13\x22" + b"https://www.lokmat.com/pune/story-1/" + b"\xd2\x01"
    token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    assert fn._decode_google_news_id(f"https://news.google.com/rss/articles/{token}?oc=5") == "https://www.lokmat.com/pune/story-1/"


def test_google_news_links_are_never_fetched_as_articles():
    assert fn.fetch_article_text("https://news.google.com/rss/articles/abc") == ""
