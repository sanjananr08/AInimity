"""Supabase Auth integration for AInimity.

The browser authenticates with Supabase Auth. The FastAPI backend validates the
Supabase access token against the Supabase Auth server before authorizing
private endpoints.

Only the Supabase project URL and publishable/anon key are needed. Never put a
Supabase service-role key in the browser or in this project.
"""

from __future__ import annotations

import httpx
from fastapi import Header, HTTPException

from .config import SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY
from .auth import get_or_create_supabase_user


def _require_configured() -> None:
    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured. Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in .env.",
        )


def get_supabase_user(access_token: str) -> dict:
    """Validate an access token with Supabase Auth and return the user."""
    _require_configured()
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{SUPABASE_URL.rstrip('/')}/auth/v1/user",
                headers={
                    "apikey": SUPABASE_PUBLISHABLE_KEY,
                    "Authorization": f"Bearer {access_token}",
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Supabase Auth unavailable: {exc}") from exc

    if response.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="Supabase session is invalid or expired. Please sign in again.")
    if response.status_code == 429 or response.status_code >= 500:
        raise HTTPException(status_code=503, detail="Supabase Auth is temporarily unavailable. Please retry shortly.")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Supabase Auth could not validate this session (HTTP {response.status_code}).")

    data = response.json()
    if not data.get("id") or not data.get("email"):
        raise HTTPException(status_code=401, detail="Supabase returned an incomplete user.")

    return {
        "id": data["id"],
        "email": data["email"].strip().lower(),
        "created_at": data.get("created_at"),
    }


def current_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency: authenticate the caller with a Supabase Bearer token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Login required.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Login required.")
    supabase_user = get_supabase_user(token)
    local_user = get_or_create_supabase_user(supabase_user["id"], supabase_user["email"])
    return {
        **local_user,
        "supabase_id": supabase_user["id"],
    }
