import pytest

import llm_providers as llm


@pytest.fixture(autouse=True)
def fresh_state():
    llm.reset_state()
    yield
    llm.reset_state()


def run(attempts, validate=lambda d: d):
    return llm.generate_json(
        system_instruction="s", prompt="p", attempts=attempts, validate=validate, sleep=lambda _s: None
    )


def test_parse_json_handles_fences_and_noise():
    assert llm.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.parse_json('here you go {"a": 2} thanks') == {"a": 2}


def test_quota_error_falls_back_to_next_provider():
    calls = []

    def gemini(_p):
        calls.append("gemini")
        raise RuntimeError("429 RESOURCE_EXHAUSTED quota")

    def groq(_p):
        calls.append("groq")
        return '{"ok": true}'

    assert run([("gemini", "m1", gemini), ("groq", "m2", groq)]) == {"ok": True}
    assert calls == ["gemini", "groq"]


def test_bad_content_gets_one_repair_attempt_with_the_error():
    prompts = []

    def model(prompt):
        prompts.append(prompt)
        return '{"n": %d}' % len(prompts)

    def validate(data):
        if data["n"] < 2:
            raise ValueError("too short")
        return data

    assert run([("gemini", "m", model)], validate) == {"n": 2}
    assert "too short" in prompts[1]


def test_content_rejected_stops_everything():
    second = []

    def validate(_d):
        raise llm.ContentRejected("rumour")

    with pytest.raises(llm.ContentRejected):
        run([("gemini", "a", lambda _p: "{}"), ("groq", "b", lambda _p: second.append(1) or "{}")], validate)
    assert second == []


def test_all_providers_out_of_quota_raises_unavailable():
    def boom(_p):
        raise RuntimeError("429 quota")

    with pytest.raises(llm.LLMUnavailableError):
        run([("gemini", "a", boom), ("groq", "b", boom)])


def test_no_attempts_raises_unavailable():
    with pytest.raises(llm.LLMUnavailableError):
        run([])


def test_missing_model_is_skipped_not_fatal():
    def missing(_p):
        raise RuntimeError("404 model not found")

    assert run([("gemini", "bad", missing), ("gemini", "good", lambda _p: '{"x": 1}')]) == {"x": 1}


def test_normalize_gemini_model_names():
    assert llm.normalize_gemini_model("Gemini 2.5 Flash") == "gemini-2.5-flash"
    assert llm.normalize_gemini_model("models/gemini-2.5-pro") == "gemini-2.5-pro"


def test_gemini_keys_are_merged_and_deduplicated(monkeypatch):
    import llm_providers as lp

    monkeypatch.setenv("GEMINI_API_KEY", "a")
    monkeypatch.setenv("GEMINI_API_KEYS", "b, c\nb a")
    assert lp.gemini_keys() == ["a", "b", "c"]


def test_each_key_gets_its_own_attempt(monkeypatch):
    import llm_providers as lp

    monkeypatch.setenv("GEMINI_API_KEY", "a")
    monkeypatch.setenv("GEMINI_API_KEYS", "b")
    monkeypatch.setenv("GEMINI_MODELS", "m1")
    monkeypatch.setattr(lp, "genai", object())
    gem = [(p, m) for p, m, _ in lp.build_attempts("s", None) if p.startswith("gemini")]
    assert gem == [("gemini", "m1"), ("gemini-key2", "m1")]
