import json

import pytest

import news_writer
from test_news_quality_rules import VALID_PACK


class QuotaError(Exception):
    """Looks like the google-genai 429 error."""

    code = 429


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    news_writer._EXHAUSTED.clear()
    for name in ("GROQ_API_KEY", "CEREBRAS_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(news_writer, "client", None)
    monkeypatch.setattr(news_writer.time, "sleep", lambda *_: None)
    yield
    news_writer._EXHAUSTED.clear()


def enable_gemini(monkeypatch):
    monkeypatch.setattr(news_writer, "client", object())


def good_reply():
    return json.dumps(VALID_PACK, ensure_ascii=False)


def test_no_keys_gives_clear_error():
    with pytest.raises(RuntimeError, match="No LLM API key configured"):
        news_writer.generate_news_content("some news")


def test_gemini_quota_falls_back_to_groq_and_is_not_retried(monkeypatch):
    enable_gemini(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    gemini_calls, groq_calls = [], []

    def fake_gemini(model, prompt):
        gemini_calls.append(model)
        raise QuotaError("429 RESOURCE_EXHAUSTED. You exceeded your current quota")

    def fake_openai(provider, key, model, prompt):
        groq_calls.append(provider["name"])
        return good_reply()

    monkeypatch.setattr(news_writer, "_call_gemini", fake_gemini)
    monkeypatch.setattr(news_writer, "_call_openai_compatible", fake_openai)

    first = news_writer.generate_news_content("row one")
    second = news_writer.generate_news_content("row two")

    assert first["headline_part1"] == VALID_PACK["headline_part1"]
    assert second["audio_mood"] == "breaking"
    # Each Gemini model is tried once, on the first row only. No retry loop, nothing on row two.
    assert gemini_calls == list(news_writer.CANDIDATE_MODELS)
    assert groq_calls == ["groq", "groq"]


def test_unusable_content_moves_on_without_marking_quota_exhausted(monkeypatch):
    enable_gemini(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setattr(news_writer, "CANDIDATE_MODELS", ["only-model"])
    monkeypatch.setattr(news_writer, "_call_gemini", lambda model, prompt: "not json at all, sorry")
    monkeypatch.setattr(news_writer, "_call_openai_compatible", lambda *a: good_reply())

    result = news_writer.generate_news_content("some news")

    assert result["badge"] == VALID_PACK["badge"]
    assert news_writer._EXHAUSTED == set()


def test_transient_error_is_retried_once(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    calls = []

    def flaky(provider, key, model, prompt):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("HTTP 503: service unavailable")
        return good_reply()

    monkeypatch.setattr(news_writer, "_call_openai_compatible", flaky)

    assert news_writer.generate_news_content("some news")["badge"] == VALID_PACK["badge"]
    assert len(calls) == 2


def test_everything_failing_raises_with_last_error(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("CEREBRAS_API_KEY", "test-cerebras")

    def always_quota(provider, key, model, prompt):
        raise RuntimeError("HTTP 429: rate limit reached")

    monkeypatch.setattr(news_writer, "_call_openai_compatible", always_quota)

    with pytest.raises(Exception, match="every configured free provider"):
        news_writer.generate_news_content("some news")
    assert {"groq", "cerebras"} <= news_writer._EXHAUSTED


def test_parse_json_handles_fences_and_surrounding_text():
    assert news_writer._parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert news_writer._parse_json('Here you go:\n{"a": 2}\nHope that helps') == {"a": 2}
    with pytest.raises(ValueError):
        news_writer._parse_json("no braces here")


def test_json_error_position_429_is_not_mistaken_for_quota():
    err = json.JSONDecodeError("Expecting ',' delimiter", "x" * 500, 429)
    assert str(err).count("429") >= 1
    assert not news_writer._is_quota_error(Exception("Expecting ',' delimiter: line 1 column 430 (char 429)"))


def test_empty_env_values_fall_back_to_defaults(monkeypatch):
    """GitHub Actions passes unset variables as empty strings."""
    import importlib

    monkeypatch.setenv("GEMINI_MODELS", "")
    monkeypatch.setenv("GROQ_MODEL", "")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    reloaded = importlib.reload(news_writer)
    try:
        assert reloaded.CANDIDATE_MODELS == ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
        attempts = reloaded._build_attempts()
        assert [(p, m) for p, m, _ in attempts] == [
            ("groq", "openai/gpt-oss-120b"),
            ("groq", "openai/gpt-oss-20b"),
        ]
    finally:
        monkeypatch.delenv("GEMINI_MODELS", raising=False)
        monkeypatch.delenv("GROQ_MODEL", raising=False)
        importlib.reload(news_writer)


def test_gemini_models_override_is_respected(monkeypatch):
    import importlib

    monkeypatch.setenv("GEMINI_MODELS", "model-a, model-b")
    reloaded = importlib.reload(news_writer)
    try:
        assert reloaded.CANDIDATE_MODELS == ["model-a", "model-b"]
    finally:
        monkeypatch.delenv("GEMINI_MODELS", raising=False)
        importlib.reload(news_writer)


def test_display_names_are_converted_to_api_ids():
    assert news_writer._normalize_gemini_model("Gemini 3.1 Flash Lite") == "gemini-3.1-flash-lite"
    assert news_writer._normalize_gemini_model("models/gemini-2.5-flash") == "gemini-2.5-flash"


def test_rejected_key_skips_provider_once_and_missing_model_skips_only_that_model(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("CEREBRAS_API_KEY", "test-cerebras")
    calls = []

    def fake(provider, key, model, prompt):
        calls.append((provider["name"], model))
        if provider["name"] == "groq":
            raise RuntimeError("HTTP 401: invalid api key")
        if model == "gpt-oss-120b":
            raise RuntimeError("HTTP 404: model does not exist")
        return good_reply()

    monkeypatch.setattr(news_writer, "_call_openai_compatible", fake)
    news_writer.generate_news_content("row one")
    news_writer.generate_news_content("row two")

    assert [c for c in calls if c[0] == "groq"] == [("groq", "openai/gpt-oss-120b")]
    assert calls.count(("cerebras", "gpt-oss-120b")) == 1
    assert calls.count(("cerebras", "llama-3.3-70b")) == 2


def test_provider_outage_raises_llm_unavailable_but_bad_content_does_not(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setattr(
        news_writer, "_call_openai_compatible",
        lambda *a: (_ for _ in ()).throw(RuntimeError("HTTP 401: invalid api key")),
    )
    with pytest.raises(news_writer.LLMUnavailableError):
        news_writer.generate_news_content("some news")

    news_writer._EXHAUSTED.clear()
    monkeypatch.setattr(news_writer, "_call_openai_compatible", lambda *a: "not json")
    with pytest.raises(Exception) as info:
        news_writer.generate_news_content("some news")
    assert not isinstance(info.value, news_writer.LLMUnavailableError)
