"""Provider-agnostic structured-JSON generation with free-tier fallbacks.

Order of attempts: every configured Gemini model first, then Groq, Cerebras and OpenRouter
(each only if its API key is set). Quota, auth and missing-model failures are remembered for the
rest of the run so the pipeline does not waste calls on something that cannot recover in seconds.
"""

from __future__ import annotations

import json
import re
import time
from typing import Callable

import requests

from config import get_env_value
from content_rules import plain_names_deep

try:  # google-genai is optional so the engine can also run on the fallback providers alone.
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None
    types = None

GEMINI_TEMPERATURE = 0.15

DEFAULT_GEMINI_MODELS = "gemini-2.5-pro,gemini-2.5-flash"

OPENAI_COMPATIBLE_PROVIDERS = [
    {
        "name": "groq",
        "key_env": "GROQ_API_KEY",
        "model_env": "GROQ_MODEL",
        "default_models": ["openai/gpt-oss-120b", "openai/gpt-oss-20b"],
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "json_mode": True,
    },
    {
        "name": "cerebras",
        "key_env": "CEREBRAS_API_KEY",
        "model_env": "CEREBRAS_MODEL",
        "default_models": ["gpt-oss-120b", "llama-3.3-70b"],
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "json_mode": True,
    },
    {
        "name": "openrouter",
        "key_env": "OPENROUTER_API_KEY",
        "model_env": "OPENROUTER_MODEL",
        "default_models": ["openai/gpt-oss-120b:free", "meta-llama/llama-3.3-70b-instruct:free"],
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "json_mode": False,  # not every free OpenRouter model supports response_format
    },
]

# Providers/models that cannot be used for the rest of this run.
_EXHAUSTED: set = set()


class LLMUnavailableError(RuntimeError):
    """No AI provider could be used (quota, bad key, missing model, outage).

    The story itself is fine, so the caller should keep it queued and retry later instead of
    marking it as an error."""


class ContentFailed(Exception):
    """Every provider answered, but none produced content that passed the quality checks."""

    def __init__(self, message: str, errors: list[str] | None = None, draft=None):
        super().__init__(message)
        self.errors = errors or []
        self.draft = draft


class InvalidProviderJSON(ValueError):
    def __init__(self, draft: str):
        super().__init__("Provider rejected malformed generated JSON (json_validate_failed).")
        self.draft = draft


class ContentRejected(Exception):
    """The model (or a validator) decided the story must not be published.

    Deliberately NOT a ValueError: it must stop the provider loop instead of triggering a retry
    on another model."""


def reset_state() -> None:
    _EXHAUSTED.clear()


def split_models(value: str) -> list:
    return [m.strip() for m in (value or "").split(",") if m.strip()]


def normalize_gemini_model(name: str) -> str:
    """Accept the API id ("gemini-2.5-flash") or the AI Studio display name ("Gemini 2.5 Flash")."""
    name = name.strip()
    if name.lower().startswith("models/"):
        name = name[len("models/"):]
    return re.sub(r"\s+", "-", name).lower()


_SKIP_MODEL_WORDS = ("tts", "image", "embed", "live", "audio", "veo", "imagen", "aqa", "robotics", "computer", "vision",
                     "native", "learnlm", "gemma", "exp", "customtools")
_DISCOVERED: list | None = None


def rank_text_models(models: list) -> list:
    """Usable text models, newest version first; within a version pro, then flash, then flash-lite."""
    def key(name: str):
        match = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
        version = float(match.group(1)) if match else 0.0
        tier = 0 if "pro" in name else 2 if "lite" in name else 1
        return (-version, tier, name)

    good = [m for m in models if m.startswith("gemini-") and not any(w in m for w in _SKIP_MODEL_WORDS)]
    return sorted(dict.fromkeys(good), key=key)


def discover_gemini_models(limit: int = 6) -> list:
    """Ask Google which text models the first API key can use (generateContent), best first. [] on any problem."""
    global _DISCOVERED
    if _DISCOVERED is not None:
        return _DISCOVERED
    _DISCOVERED = []
    key = (split_models(get_env_value("GEMINI_API_KEYS")) or [get_env_value("GEMINI_API_KEY")])[0]
    if not key or get_env_value("GEMINI_AUTO_MODELS") == "0":
        return _DISCOVERED
    try:
        import requests

        resp = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"pageSize": 1000},
                            headers={"x-goog-api-key": key}, timeout=15)
        if resp.status_code != 200:
            print(f"⚠️ Could not list Gemini models (HTTP {resp.status_code}); using the built-in list.")
            return _DISCOVERED
        names = [str(m.get("name", "")).removeprefix("models/") for m in resp.json().get("models", [])
                 if "generateContent" in (m.get("supportedGenerationMethods") or [])]
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ Could not list Gemini models ({exc}); using the built-in list.")
        return _DISCOVERED
    _DISCOVERED = rank_text_models(names)[:limit]
    print(f"🔎 Gemini text models this key can use: {', '.join(_DISCOVERED) or '(none)'}")
    return _DISCOVERED


def candidate_gemini_models() -> list:
    """GEMINI_MODELS when set; otherwise the models Google says this key can use, then the built-in names."""
    raw = get_env_value("GEMINI_MODELS")
    if raw:
        return list(dict.fromkeys(normalize_gemini_model(m) for m in split_models(raw)))
    return list(dict.fromkeys(discover_gemini_models() + split_models(DEFAULT_GEMINI_MODELS)))


def parse_json(text: str) -> dict:
    """Turn a model reply into a dict, tolerating code fences and stray text around the JSON."""
    if not isinstance(text, str):
        raise ValueError("Provider returned missing or non-text content.")
    clean = text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*\n?|\n?```\s*$", "", clean).strip()
    if not clean.startswith("{"):
        start, end = clean.find("{"), clean.rfind("}")
        if start != -1 and end > start:
            clean = clean[start : end + 1]
    data = json.loads(clean)
    if not isinstance(data, dict):
        raise ValueError("JSON must contain one object.")
    return data


# ----- error classification -------------------------------------------------------------------


def _error_code(exc: Exception):
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    return code if isinstance(code, int) else None


def is_quota_error(exc: Exception) -> bool:
    if _error_code(exc) == 429:
        return True
    return bool(re.search(r"HTTP 429|RESOURCE_EXHAUSTED|QUOTA|RATE.?LIMIT", str(exc).upper()))


def is_auth_error(exc: Exception) -> bool:
    if _error_code(exc) in (401, 403):
        return True
    text = str(exc).upper()
    return any(
        token in text
        for token in (
            "API KEY NOT VALID",
            "INVALID API KEY",
            "INVALID_API_KEY",
            "UNAUTHENTICATED",
            "PERMISSION_DENIED",
            "HTTP 401",
            "HTTP 403",
        )
    )


def is_model_missing(exc: Exception) -> bool:
    if _error_code(exc) == 404:
        return True
    text = str(exc).upper()
    return any(t in text for t in ("HTTP 404", "DOES NOT EXIST", "MODEL_NOT_FOUND", "NOT_FOUND", "IS NOT FOUND"))


def is_transient_error(exc: Exception) -> bool:
    if _error_code(exc) in (500, 502, 503, 504):
        return True
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    text = str(exc).upper()
    return any(t in text for t in ("UNAVAILABLE", "OVERLOADED", "TIMED OUT", "HTTP 503", "HTTP 502"))


# ----- provider calls -------------------------------------------------------------------------


def gemini_keys() -> list[str]:
    """Every configured Gemini key, in order: ``GEMINI_API_KEY`` first, then ``GEMINI_API_KEYS`` (comma, space or
    newline separated). Quota is per Google Cloud project, so keys from different projects add up."""
    raw = [get_env_value("GEMINI_API_KEY")] + re.split(r"[,\s]+", get_env_value("GEMINI_API_KEYS") or "")
    return list(dict.fromkeys(k.strip() for k in raw if k and k.strip()))


def _call_gemini(model_name: str, system_instruction: str, prompt: str, response_model, api_key: str) -> str:
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=response_model,
        temperature=GEMINI_TEMPERATURE,
    )
    response = client.models.generate_content(model=model_name, contents=prompt, config=config)
    return response.text


def _call_openai_compatible(provider: dict, api_key: str, model: str, system_instruction: str, prompt: str) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ],
        "temperature": GEMINI_TEMPERATURE,
    }
    if provider.get("json_mode"):
        payload["response_format"] = {"type": "json_object"}

    response = requests.post(
        provider["url"],
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    if response.status_code != 200:
        if response.status_code == 400 and "json_validate_failed" in response.text:
            try:
                draft = response.json().get("error", {}).get("failed_generation", "")
            except (ValueError, AttributeError):
                draft = ""
            raise InvalidProviderJSON(draft if isinstance(draft, str) else "")
        error = RuntimeError(f"HTTP {response.status_code}")
        error.status_code = response.status_code
        error.retry_after = response.headers.get("Retry-After")
        raise error
    try:
        return response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Provider response has no message content.") from exc


def build_attempts(system_instruction: str, response_model) -> list:
    """Ordered (provider, model, callable(prompt)) for every provider that has a key configured."""
    attempts = []

    keys = gemini_keys() if genai is not None else []
    for model_name in candidate_gemini_models():
        for number, key in enumerate(keys, start=1):
            # One provider name per key, so a rejected or spent key is skipped without touching the others.
            provider = "gemini" if number == 1 else f"gemini-key{number}"
            attempts.append(
                (
                    provider,
                    model_name,
                    lambda prompt, m=model_name, k=key: _call_gemini(m, system_instruction, prompt, response_model, k),
                )
            )

    # Fallback providers have no schema enforcement, so the schema is appended to the prompt.
    schema_hint = ""
    if response_model is not None and hasattr(response_model, "model_json_schema"):
        schema_hint = "\n\nReturn ONLY one JSON object matching this JSON schema:\n" + json.dumps(
            response_model.model_json_schema(), ensure_ascii=False
        )

    for provider in OPENAI_COMPATIBLE_PROVIDERS:
        api_key = get_env_value(provider["key_env"])
        if not api_key:
            continue
        models = split_models(get_env_value(provider["model_env"])) or provider["default_models"]
        for model in dict.fromkeys(models):
            attempts.append(
                (
                    provider["name"],
                    model,
                    lambda prompt, p=provider, k=api_key, m=model: _call_openai_compatible(
                        p, k, m, system_instruction, prompt + schema_hint
                    ),
                )
            )

    return attempts


def generate_json(
    *,
    system_instruction: str,
    prompt: str,
    response_model=None,
    validate: Callable[[dict], dict] = lambda d: d,
    attempts: list | None = None,
    sleep: Callable[[float], None] = time.sleep,
    max_calls: int = 12,
    merge_repair: Callable[[dict, dict, str], dict] | None = None,
) -> dict:
    """Generate and validate one JSON object, falling back across models and providers.

    ``validate`` raises ValueError for unusable content (the same model then gets ONE repair
    attempt with the error appended to the prompt) and ``ContentRejected`` to stop everything.
    """
    attempts = attempts if attempts is not None else build_attempts(system_instruction, response_model)
    if not attempts:
        raise LLMUnavailableError(
            "No LLM API key configured. Set GEMINI_API_KEY (and optionally GEMINI_API_KEYS) and/or one of GROQ_API_KEY,"
            " CEREBRAS_API_KEY, OPENROUTER_API_KEY."
        )

    last_error = ""
    bad_content = False
    content_errors: list[str] = []
    previous = None
    calls = 0

    for index, (provider, model_name, call) in enumerate(attempts):
        slot = f"{provider}:{model_name}"
        if slot in _EXHAUSTED or provider in _EXHAUSTED:
            continue

        current_prompt = prompt
        original_draft = None
        repair_error = ""
        repaired = False
        retried_transient = False

        # Leave at least one call for a later provider when a model has already used its first call.
        alternatives = {name for name, _, _ in attempts[index + 1:]
                        if name != provider and not name.startswith("gemini") and name not in _EXHAUSTED}
        while calls < max_calls:
            if calls and alternatives and max_calls - calls <= len(alternatives):
                break
            draft = None
            raw = ""
            calls += 1
            try:
                raw = call(current_prompt)
                draft = plain_names_deep(parse_json(raw))
                if original_draft is not None and merge_repair is not None:
                    draft = merge_repair(original_draft, draft, repair_error)
                data = validate(draft)
                print(f"✅ Content written by {provider}/{model_name}")
                return data

            except ContentRejected:
                raise

            except ValueError as e:
                # Bad JSON or failed quality rules: the quota is fine, this model just wrote
                # something unusable. Give it one repair attempt, then move on.
                bad_content = True
                if isinstance(e, InvalidProviderJSON):
                    raw = e.draft
                if draft is not None:
                    previous = draft
                last_error = f"[{slot}] {type(e).__name__}: {e}"
                content_errors.append(str(e))
                print(f"⚠️ {slot} returned unusable content: {last_error[:200]}")
                if repaired:
                    break
                repaired = True
                original_draft, repair_error = draft, str(e)
                current_prompt = (
                    f"{prompt}\n\nYOUR PREVIOUS ANSWER WAS REJECTED BY THE AUTOMATIC CHECKER: {e}\n"
                    "Preserve valid fields and scenes verbatim. Change only the invalid values and return the complete corrected JSON object.\n"
                    f"PREVIOUS ANSWER:\n{json.dumps(draft, ensure_ascii=False) if draft is not None else str(raw)[:16000]}"
                )
                continue

            except Exception as e:  # noqa: BLE001 - classification below decides what to do
                last_error = f"[{slot}] {type(e).__name__}: {e}"

                retry_after = str(getattr(e, "retry_after", "") or "")
                if _error_code(e) == 429 and retry_after.isdigit() and 0 < int(retry_after) <= 10 and not retried_transient:
                    retried_transient = True
                    sleep(int(retry_after))
                    continue

                if is_quota_error(e):
                    _EXHAUSTED.add(slot if provider.startswith("gemini") else provider)
                    print(f"⛔ {slot} is out of free quota. Switching provider.")
                    break

                if is_auth_error(e):
                    _EXHAUSTED.add(provider)
                    print(f"🔑 {provider} rejected the API key. Skipping {provider} for this run.")
                    break

                if is_model_missing(e):
                    _EXHAUSTED.add(slot)
                    print(f"🚫 {slot} does not exist or is not available to this key. Skipping it.")
                    break

                if is_transient_error(e) and not retried_transient and calls < max_calls:
                    retried_transient = True
                    print(f"⚠️ {slot} temporarily unavailable. Retrying once in 3s...")
                    sleep(3)
                    continue

                print(f"⚠️ Error on {slot}: {last_error[:200]}")
                break

    message = (
        "Content generation failed on every configured provider."
        f" Last error: {last_error or 'all providers were already unavailable earlier in this run'}"
    )
    if bad_content:
        raise ContentFailed(message, content_errors, previous)
    raise LLMUnavailableError(message)
