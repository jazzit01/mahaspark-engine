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


def candidate_gemini_models() -> list:
    raw = get_env_value("GEMINI_MODELS") or DEFAULT_GEMINI_MODELS
    return list(dict.fromkeys(normalize_gemini_model(m) for m in split_models(raw)))


def parse_json(text: str) -> dict:
    """Turn a model reply into a dict, tolerating code fences and stray text around the JSON."""
    clean = (text or "").strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*\n?|\n?```\s*$", "", clean).strip()
    if not clean.startswith("{"):
        start, end = clean.find("{"), clean.rfind("}")
        if start != -1 and end > start:
            clean = clean[start : end + 1]
    return json.loads(clean)


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


def _gemini_client():
    api_key = get_env_value("GEMINI_API_KEY")
    if not (api_key and genai):
        return None
    return genai.Client(api_key=api_key)


def _call_gemini(model_name: str, system_instruction: str, prompt: str, response_model) -> str:
    client = _gemini_client()
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
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
    return response.json()["choices"][0]["message"]["content"]


def build_attempts(system_instruction: str, response_model) -> list:
    """Ordered (provider, model, callable(prompt)) for every provider that has a key configured."""
    attempts = []

    if get_env_value("GEMINI_API_KEY") and genai is not None:
        for model_name in candidate_gemini_models():
            attempts.append(
                (
                    "gemini",
                    model_name,
                    lambda prompt, m=model_name: _call_gemini(m, system_instruction, prompt, response_model),
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
) -> dict:
    """Generate and validate one JSON object, falling back across models and providers.

    ``validate`` raises ValueError for unusable content (the same model then gets ONE repair
    attempt with the error appended to the prompt) and ``ContentRejected`` to stop everything.
    """
    attempts = attempts if attempts is not None else build_attempts(system_instruction, response_model)
    if not attempts:
        raise LLMUnavailableError(
            "No LLM API key configured. Set GEMINI_API_KEY and/or one of GROQ_API_KEY,"
            " CEREBRAS_API_KEY, OPENROUTER_API_KEY."
        )

    last_error = ""
    bad_content = False

    for provider, model_name, call in attempts:
        slot = f"{provider}:{model_name}"
        if slot in _EXHAUSTED or provider in _EXHAUSTED:
            continue

        current_prompt = prompt
        repaired = False
        retried_transient = False

        while True:
            try:
                data = validate(parse_json(call(current_prompt)))
                print(f"✅ Content written by {provider}/{model_name}")
                return data

            except ContentRejected:
                raise

            except ValueError as e:
                # Bad JSON or failed quality rules: the quota is fine, this model just wrote
                # something unusable. Give it one repair attempt, then move on.
                bad_content = True
                last_error = f"[{slot}] {type(e).__name__}: {e}"
                print(f"⚠️ {slot} returned unusable content: {last_error[:200]}")
                if repaired:
                    break
                repaired = True
                current_prompt = (
                    f"{prompt}\n\nYOUR PREVIOUS ANSWER WAS REJECTED BY THE AUTOMATIC CHECKER: {e}\n"
                    "Fix exactly this problem and return the complete corrected JSON object."
                )
                continue

            except Exception as e:  # noqa: BLE001 - classification below decides what to do
                last_error = f"[{slot}] {type(e).__name__}: {e}"

                if is_quota_error(e):
                    _EXHAUSTED.add(slot if provider == "gemini" else provider)
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

                if is_transient_error(e) and not retried_transient:
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
        raise Exception(message)
    raise LLMUnavailableError(message)
