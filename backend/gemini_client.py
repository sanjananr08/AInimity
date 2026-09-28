"""Small Gemini wrapper with strict one-key-per-agent routing."""

from __future__ import annotations

import json
import base64
import threading
import time
from collections import deque
from typing import Optional

from google import genai
from google.genai import types

from .config import (
    AGENT_API_KEYS,
    AGENT_MODELS,
    GENERAL_GEMINI_API_KEY,
    GEMINI_FALLBACK_MODEL,
    GEMINI_MODEL,
    GEMINI_RPM_LIMIT,
)


class GeminiError(RuntimeError):
    """Raised when an agent cannot produce a usable response."""


_clients: dict[str, genai.Client] = {}
_clients_lock = threading.Lock()


def get_client(agent: str) -> genai.Client:
    """Return only the client created from the requested agent's key."""
    if agent not in AGENT_API_KEYS:
        raise GeminiError(f"Unknown council agent: {agent}")

    api_key = AGENT_API_KEYS[agent]
    if not api_key:
        raise GeminiError(
            f"No API key configured for {agent}. "
            f"Set GEMINI_API_KEY_{agent.upper()} in .env."
        )

    with _clients_lock:
        client = _clients.get(agent)
        if client is None:
            client = genai.Client(api_key=api_key)
            _clients[agent] = client
        return client


def _configured_fallbacks(agent: str) -> list[tuple[str, str]]:
    """Return only the dedicated general key as an emergency fallback."""
    current_key = AGENT_API_KEYS.get(agent, "")
    if GENERAL_GEMINI_API_KEY and GENERAL_GEMINI_API_KEY != current_key:
        return [("general", GENERAL_GEMINI_API_KEY)]
    return []


def _client_for_api_key(cache_name: str, api_key: str) -> genai.Client:
    with _clients_lock:
        client = _clients.get(cache_name)
        if client is None:
            client = genai.Client(api_key=api_key)
            _clients[cache_name] = client
        return client


def _is_permission_denied_error(err: Exception) -> bool:
    message = str(err).upper()
    return ("403" in message and "PERMISSION_DENIED" in message) or "PROJECT HAS BEEN DENIED ACCESS" in message


class _RateLimiter:
    """Small local guard against accidentally hammering one agent."""

    def __init__(self, max_calls: int, period: float = 60.0):
        self.max_calls = max_calls
        self.period = period
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def wait(self) -> None:
        if self.max_calls <= 0:
            return
        while True:
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self.period:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return
                sleep_for = self.period - (now - self._calls[0])
            time.sleep(max(sleep_for, 0.05))


# A separate limiter per agent keeps one busy role from consuming another
# role's local allowance. Google still enforces the real project quota.
_rate_limiters = {
    agent: _RateLimiter(GEMINI_RPM_LIMIT) for agent in AGENT_API_KEYS
}
_general_rate_limiter = _RateLimiter(GEMINI_RPM_LIMIT)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1].strip()
            if text.lower().startswith("json"):
                text = text[4:].lstrip()
    return text.strip()


def _is_transient_error(err: Exception) -> bool:
    message = str(err).upper()
    return any(marker in message for marker in ("503", "UNAVAILABLE", "DEADLINE_EXCEEDED", "TIMEOUT"))


def _is_quota_error(err: Exception) -> bool:
    message = str(err).upper()
    return "429" in message or "RESOURCE_EXHAUSTED" in message or "QUOTA" in message


def _is_model_unavailable_error(err: Exception) -> bool:
    message = str(err).upper()
    return (
        ("404" in message and ("NOT_FOUND" in message or "MODEL" in message))
        or "NO LONGER AVAILABLE" in message
        or "MODEL_NOT_FOUND" in message
    )


def _content_with_optional_image(contents: str, image_base64: str | None, image_mime_type: str | None):
    if not image_base64:
        return contents
    try:
        raw = base64.b64decode(image_base64, validate=True)
    except Exception as exc:
        raise GeminiError("The reference image encoding is invalid.") from exc
    if len(raw) > 4 * 1024 * 1024:
        raise GeminiError("Reference images must be 4 MB or smaller for analysis.")
    return [contents, types.Part.from_bytes(data=raw, mime_type=image_mime_type or "image/png")]


def _generate_content_with_model_fallback(client, model: str, contents, config):
    """Retry an unavailable legacy model once with the current stable model."""
    try:
        return client.models.generate_content(model=model, contents=contents, config=config)
    except Exception as exc:
        if model == GEMINI_FALLBACK_MODEL or not _is_model_unavailable_error(exc):
            raise
        return client.models.generate_content(
            model=GEMINI_FALLBACK_MODEL,
            contents=contents,
            config=config,
        )


def generate_json(
    system_prompt: str,
    user_content: str,
    *,
    response_schema: Optional[dict] = None,
    model: str | None = None,
    retries: int = 1,
    temperature: float = 0.4,
    agent: str,
    image_base64: str | None = None,
    image_mime_type: str | None = None,
) -> dict:
    """Generate JSON using exactly the API key assigned to `agent`."""
    client = get_client(agent)
    model = model or AGENT_MODELS.get(agent, GEMINI_MODEL)
    config_kwargs = {
        "system_instruction": system_prompt,
        "temperature": temperature,
        "response_mime_type": "application/json",
    }
    if response_schema:
        config_kwargs["response_schema"] = response_schema
    config = types.GenerateContentConfig(**config_kwargs)

    contents = _content_with_optional_image(user_content, image_base64, image_mime_type)
    last_error = "unknown error"
    for attempt in range(retries + 1):
        try:
            _rate_limiters[agent].wait()
            try:
                response = _generate_content_with_model_fallback(
                    client, model, contents, config
                )
            except Exception as exc:
                # A Google project can be individually restricted even when
                # the rest of the council works.  Do not retry the same
                # denied project; try another configured council key once.
                if not (
                    _is_permission_denied_error(exc)
                    or _is_quota_error(exc)
                    or _is_transient_error(exc)
                ):
                    raise
                response = None
                fallback_errors = []
                for fallback_agent, fallback_key in _configured_fallbacks(agent):
                    try:
                        fallback_client = _client_for_api_key(
                            f"fallback:{fallback_agent}", fallback_key
                        )
                        _general_rate_limiter.wait()
                        response = _generate_content_with_model_fallback(
                            fallback_client, model, contents, config
                        )
                        last_error = (
                            f"{agent} key was denied; council continued using "
                            f"the {fallback_agent} Gemini project."
                        )
                        break
                    except Exception as fallback_exc:
                        fallback_errors.append(
                            f"{fallback_agent}: {fallback_exc}"
                        )
                if response is None:
                    if fallback_errors:
                        raise GeminiError(
                            f"Gemini project for {agent} is denied access, and "
                            "configured fallback projects also failed. Check project access and quota."
                        ) from exc
                    raise
            raw_text = _strip_fences(response.text or "")
            if not raw_text:
                raise ValueError("Gemini returned an empty response")
            return json.loads(raw_text)
        except json.JSONDecodeError as exc:
            last_error = f"Invalid JSON: {exc}"
            if attempt < retries:
                time.sleep(0.5)
        except Exception as exc:
            last_error = str(exc)
            # Do not burn quota by retrying daily/project quota exhaustion.
            if _is_quota_error(exc):
                break
            if attempt < retries and _is_transient_error(exc):
                time.sleep(1.5 * (attempt + 1))
            elif attempt < retries:
                time.sleep(0.5)

    if _is_transient_error(Exception(last_error)):
        raise GeminiError(
            f"Gemini is temporarily unavailable for the {agent} role (provider 503). "
            "Retry in a few seconds."
        )
    raise GeminiError(f"Gemini failed for {agent}: {last_error}")


def generate_text(
    system_prompt: str,
    user_content: str,
    *,
    model: str | None = None,
    temperature: float = 0.4,
    agent: str,
) -> str:
    """Generate plain text using the requested agent's dedicated key."""
    client = get_client(agent)
    model = model or AGENT_MODELS.get(agent, GEMINI_MODEL)
    _rate_limiters[agent].wait()
    try:
        response = _generate_content_with_model_fallback(
            client,
            model,
            user_content,
            types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
            ),
        )
    except Exception as exc:
        if not (
            _is_permission_denied_error(exc)
            or _is_quota_error(exc)
            or _is_transient_error(exc)
        ):
            raise
        response = None
        for fallback_agent, fallback_key in _configured_fallbacks(agent):
            try:
                fallback_client = _client_for_api_key(
                    f"fallback:{fallback_agent}", fallback_key
                )
                _general_rate_limiter.wait()
                response = _generate_content_with_model_fallback(
                    fallback_client,
                    model,
                    user_content,
                    types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=temperature,
                    ),
                )
                break
            except Exception:
                continue
        if response is None:
            raise
    return (response.text or "").strip()
