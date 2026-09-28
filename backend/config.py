"""Environment-backed configuration for the AInimity council.

Only browser-safe Supabase values are exposed through the public config route.
Gemini keys remain server-side and may be shared or assigned per council role.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

AGENT_NAMES = ("strategist", "technical", "adversarial", "human_mind", "validator")
DEFAULT_STORAGE_BUCKET = "council-documents"
DEFAULT_MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
DEFAULT_VOICE_RECOGNITION_LANGUAGE = "en-IN"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
LEGACY_GEMINI_MODELS = frozenset({
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
})

SHARED_GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY", "") or os.getenv("GEMINI_SHARED_API_KEY", "")
).strip()
GENERAL_GEMINI_API_KEY = SHARED_GEMINI_API_KEY
ROLE_API_KEYS = {
    name: os.getenv(f"GEMINI_API_KEY_{name.upper()}", "").strip()
    for name in AGENT_NAMES
}
AGENT_API_KEYS = {
    name: ROLE_API_KEYS[name] or GENERAL_GEMINI_API_KEY
    for name in AGENT_NAMES
}

def resolve_gemini_model(value: str | None) -> str:
    """Use the current stable default when the env file has an old default."""
    configured = (value or "").strip()
    return DEFAULT_GEMINI_MODEL if not configured or configured in LEGACY_GEMINI_MODELS else configured


_configured_model = os.getenv("GEMINI_MODEL", "")
GEMINI_MODEL = resolve_gemini_model(_configured_model)
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
AGENT_MODELS = {
    name: resolve_gemini_model(os.getenv(f"GEMINI_MODEL_{name.upper()}", ""))
    for name in AGENT_NAMES
}

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")
COUNCIL_DEADLINE = os.getenv("COUNCIL_DEADLINE", "2026-12-31T23:59:00Z")
try:
    GEMINI_RPM_LIMIT = max(0, int(os.getenv("GEMINI_RPM_LIMIT", "4")))
except ValueError:
    GEMINI_RPM_LIMIT = 4
try:
    APP_PORT = int(os.getenv("PORT", os.getenv("APP_PORT", "8000")))
except ValueError:
    APP_PORT = 8000
VOICE_RECOGNITION_LANGUAGE = os.getenv(
    "VOICE_RECOGNITION_LANGUAGE", DEFAULT_VOICE_RECOGNITION_LANGUAGE
).strip() or DEFAULT_VOICE_RECOGNITION_LANGUAGE
SUPABASE_EMAIL_CONFIRMATION_REQUIRED = os.getenv(
    "SUPABASE_EMAIL_CONFIRMATION_REQUIRED", "true"
).strip().lower() in {"1", "true", "yes", "on"}

try:
    SUPABASE_MAX_FILE_SIZE_BYTES = int(
        os.getenv("SUPABASE_MAX_FILE_SIZE_BYTES", str(DEFAULT_MAX_FILE_SIZE_BYTES))
    )
except ValueError:
    SUPABASE_MAX_FILE_SIZE_BYTES = DEFAULT_MAX_FILE_SIZE_BYTES
SUPABASE_MAX_FILE_SIZE_BYTES = max(1, SUPABASE_MAX_FILE_SIZE_BYTES)

_raw_mime_types = os.getenv("SUPABASE_ALLOWED_MIME_TYPES", "").strip()
SUPABASE_ALLOWED_MIME_TYPES = tuple(
    sorted({item.strip().lower() for item in _raw_mime_types.split(",") if item.strip()})
)

_SUPABASE_URL_RAW = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_URL = "" if "YOUR_PROJECT_REF" in _SUPABASE_URL_RAW.upper() else _SUPABASE_URL_RAW
_SUPABASE_KEY_RAW = (
    os.getenv("SUPABASE_PUBLISHABLE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")
).strip()
SUPABASE_STORAGE_BUCKET = os.getenv(
    "SUPABASE_STORAGE_BUCKET", DEFAULT_STORAGE_BUCKET
).strip() or DEFAULT_STORAGE_BUCKET


def _is_server_side_supabase_key(value: str) -> bool:
    """Recognize modern secret keys and legacy service_role JWTs."""
    if value.lower().startswith(("sb_secret_", "service_role_")):
        return True
    parts = value.split(".")
    if len(parts) != 3:
        return False
    try:
        encoded = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded).decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return str(payload.get("role", "")).lower() == "service_role"


def _browser_safe_supabase_key(value: str) -> tuple[str, str]:
    if _is_server_side_supabase_key(value):
        return "", "A server-side Supabase secret/service_role key was detected. Replace it with the browser-safe publishable or anon key."
    if not value or "YOUR_SUPABASE" in value.upper() or "PASTE_YOUR" in value.upper():
        return "", ""
    return value, ""


def validate_supabase_url(value: str) -> str:
    """Return a safe configuration error without echoing the configured URL."""
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return "SUPABASE_URL must be a complete HTTPS Supabase project URL."
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return "SUPABASE_URL must not contain credentials, query parameters, or a fragment."
    return ""


SUPABASE_PUBLISHABLE_KEY, SUPABASE_CONFIG_ERROR = _browser_safe_supabase_key(_SUPABASE_KEY_RAW)
SUPABASE_CONFIG_ERROR = SUPABASE_CONFIG_ERROR or validate_supabase_url(SUPABASE_URL)


def configured_agents() -> list[str]:
    return [name for name, key in AGENT_API_KEYS.items() if key]


def configured_role_agents() -> list[str]:
    """Return roles with their own key, excluding the general fallback."""
    return [name for name, key in ROLE_API_KEYS.items() if key]


def general_fallback_configured() -> bool:
    return bool(GENERAL_GEMINI_API_KEY)


def missing_agents() -> list[str]:
    return [name for name, key in AGENT_API_KEYS.items() if not key]
