"""Regression for a Marathi custom topic with missing URL and malformed model drafts."""
import json
from types import SimpleNamespace

import pytest

import drafts
import explainer
import llm_providers as llm
import wiki_sources

TOPIC = "शरद पवार राजकीय प्रवास"
URL = "https://mr.wikipedia.org/wiki/Sharad_Pawar"
REFERENCE = (
    "शरद पवार यांनी महाराष्ट्राच्या राजकारणात विविध भूमिका पार पाडल्या. "
    "त्यांच्या सार्वजनिक कारकिर्दीत राज्याचे नेतृत्व आणि केंद्रीय राजकारणाचा समावेश आहे. "
    "त्यांनी राजकीय पक्षाच्या स्थापनेतही भूमिका बजावली. "
) * 18


def pawar_draft():
    narrative = (
        "शरद पवार यांच्या सार्वजनिक जीवनात महाराष्ट्र आणि देशाच्या राजकारणाचा समावेश आहे. "
        "त्यांनी राज्यातील नेतृत्व सांभाळले आणि केंद्रीय राजकारणात काम केले. "
        "पक्षाच्या स्थापनेतही त्यांची भूमिका होती. "
        "या विविध जबाबदाऱ्यांतून त्यांचा राजकीय प्रवास समजतो. "
        "राज्य आणि देश पातळीवरील कामाचा तो भाग आहे. त्यातून त्यांच्या सार्वजनिक कारकिर्दीतील वेगवेगळ्या जबाबदाऱ्या स्पष्ट होतात."
    )
    headings = ["शरद पवारांचा राजकीय प्रवास", "महाराष्ट्रातील नेतृत्व", "केंद्रीय राजकारण",
                "पक्ष स्थापनेतील भूमिका", "राजकीय प्रवासातील टप्पे"]
    items = [{"label": "राज्यातील नेतृत्व"}, {"label": "केंद्रीय राजकारणातील काम"}]
    scenes = [{"kind": kind, "headline": headline, "tts_text": narrative, "items": [] if kind == "title" else items}
              for kind, headline in zip(["title", "points", "points", "points", "summary"], headings)]
    return {"approved": True, "title": TOPIC, "scenes": scenes}


@pytest.mark.parametrize("explicit", [False, True])
def test_sharad_pawar_custom_topic_discovery_validation_and_repair(monkeypatch, tmp_path, explicit):
    searches = []
    if explicit:
        monkeypatch.setattr(drafts.fetch_news, "fetch_article_text", lambda url: REFERENCE if url == URL else "")
        monkeypatch.setattr(wiki_sources, "discover_topic", lambda topic: pytest.fail("Used unrelated discovery"))
    else:
        def search(query, language):
            searches.append((query, language))
            return "शरद पवार" if query == "शरद पवार" else None

        monkeypatch.setattr(wiki_sources, "search_title", search)
        monkeypatch.setattr(wiki_sources, "fetch_extract", lambda title, lang:
                            {"title": title, "url": URL, "text": REFERENCE})
    monkeypatch.setattr(explainer.topic_bank, "pick", lambda *a: pytest.fail("Custom topic went to the bank"))
    monkeypatch.setattr(drafts, "new_draft_path", lambda kind: tmp_path / "approval.txt")
    monkeypatch.setattr(drafts, "announce", lambda *a: None)
    prompts = []
    valid = pawar_draft()
    invalid = pawar_draft()
    invalid["scenes"].pop(3)
    invalid["scenes"][0]["headline"] = "क" * 57
    invalid["scenes"][1]["tts_text"] = " ".join(["राजकीय"] * 16) + "."

    def generate(**kwargs):
        model = kwargs["response_model"]
        if model is explainer.TopicReview:
            assert TOPIC in kwargs["prompt"]
            assert REFERENCE[:100] in kwargs["prompt"]
            return kwargs["validate"]({"relevant": True, "reason": "Exact subject"})
        assert model is explainer.Explainer

        def provider(prompt):
            prompts.append(prompt)
            return json.dumps(invalid if len(prompts) == 1 else valid, ensure_ascii=False)

        return llm.generate_json(**kwargs, attempts=[("gemini", "test", provider)])

    monkeypatch.setattr(explainer, "generate_json", generate)
    monkeypatch.setattr(explainer.factcheck, "unsupported_statements", lambda *args: [])
    args = ["--topic", TOPIC] + (["--url", URL] if explicit else [])
    assert explainer.draft_main(args) == 0
    text = (tmp_path / "approval.txt").read_text(encoding="utf-8")
    assert TOPIC in text and URL in text
    assert len(prompts) == 2
    repair = prompts[1]
    assert all(piece in repair for piece in (
        TOPIC, "Expected 5 to 10 scenes, got 4", "57 characters", "16 words", "PREVIOUS ANSWER",
        invalid["scenes"][0]["headline"], "Preserve valid fields",
    ))
    if not explicit:
        assert searches == [(TOPIC, "mr"), ("शरद पवार", "mr")]


def test_no_reference_and_off_topic_output_cannot_fall_back(monkeypatch, tmp_path):
    monkeypatch.setattr(drafts, "topic_sources", lambda *a: ("", []))
    monkeypatch.setattr(explainer.topic_bank, "pick", lambda *a: pytest.fail("Random selection for custom topic"))
    assert explainer.draft_main(["--topic", TOPIC]) == 1

    def generate(**kwargs):
        if kwargs["response_model"] is explainer.TopicReview:
            return {"relevant": "SCRIPT:" not in kwargs["prompt"], "reason": "Different topic"}
        return kwargs["validate"](pawar_draft())

    monkeypatch.setattr(explainer, "generate_json", generate)
    monkeypatch.setattr(explainer, "LONG_PATH", tmp_path / "video.mp4")
    with pytest.raises(llm.ContentRejected, match="Different topic"):
        explainer.write_explainer(TOPIC, "", REFERENCE, URL, custom=True)
    debug = next((tmp_path / "explainer-debug").glob("*.json"))
    assert json.loads(debug.read_text())["topic"] == TOPIC


def test_malformed_groq_response_is_repairable_and_falls_back(monkeypatch):
    llm.reset_state()
    requests = []
    provider = {"url": "https://groq.example", "json_mode": True}

    def post(*_args, **kwargs):
        requests.append(kwargs["json"])
        return SimpleNamespace(status_code=400, text='{"error":{"code":"json_validate_failed"}}')

    monkeypatch.setattr(llm.requests, "post", post)
    fallback = []

    def groq(prompt):
        return llm._call_openai_compatible(provider, "test", "model", "system", prompt)

    result = llm.generate_json(
        system_instruction="system", prompt=f"topic={TOPIC} | refs={URL}",
        attempts=[("groq", "model", groq), ("openrouter", "model", lambda prompt: fallback.append(prompt) or '{"ok": true}')],
    )
    assert result == {"ok": True}
    assert len(requests) == 2 and "json_validate_failed" in requests[1]["messages"][1]["content"]
    assert TOPIC in fallback[0] and URL in fallback[0]


def test_rate_limit_backoff_quota_and_permanent_errors_have_bounded_attempts(monkeypatch):
    llm.reset_state()
    hit, sleeps = [], []

    def failure(label, code, retry_after=None):
        def call(_prompt):
            hit.append(label)
            exc = RuntimeError(f"HTTP {code}")
            exc.status_code = code
            exc.retry_after = retry_after
            raise exc
        return call

    with pytest.raises(llm.LLMUnavailableError):
        llm.generate_json(system_instruction="system", prompt="prompt", max_calls=5, sleep=sleeps.append,
                          attempts=[("gemini", "bad-request", failure("bad", 400)),
                                    ("groq", "limited", failure("limit", 429, "2")),
                                    ("cerebras", "quota", failure("quota", 429)),
                                    ("openrouter", "outage", failure("outage", 503)),
                                    ("openrouter", "would-exceed", lambda _: pytest.fail("Call budget exceeded"))])
    assert hit == ["bad", "limit", "limit", "quota", "outage"]
    assert sleeps == [2]
    llm.reset_state()


def test_field_repair_preserves_unaffected_scenes():
    first = pawar_draft()
    first["scenes"][0]["headline"] = "क" * 57
    repair = pawar_draft()
    repair["title"] = "Different"
    repair["scenes"][1]["headline"] = "Different"
    merged = explainer.merge_scene_repair(first, repair, "Scene 1 headline has 57 characters.")
    assert merged["title"] == first["title"]
    assert merged["scenes"][1:] == first["scenes"][1:]
    assert merged["scenes"][0]["headline"] == repair["scenes"][0]["headline"]
