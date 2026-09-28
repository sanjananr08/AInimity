from fastapi import HTTPException
from fastapi.testclient import TestClient

import backend.main as main
import backend.config as config
import backend.supabase_auth as supabase_auth


def test_public_config_exposes_only_browser_safe_supabase_settings(monkeypatch):
    monkeypatch.setattr(main, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(main, "SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_key")
    monkeypatch.setattr(main, "SUPABASE_STORAGE_BUCKET", "council-documents")

    with TestClient(main.app) as client:
        response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json() == {
        "supabase_configured": True,
        "supabase_url": "https://example.supabase.co",
        "supabase_publishable_key": "sb_publishable_test_key",
        "supabase_storage_bucket": "council-documents",
        "max_file_size_bytes": 20 * 1024 * 1024,
        "allowed_mime_types": [],
        "voice_recognition_language": "en-IN",
        "email_confirmation_required": True,
    }


def test_public_config_marks_missing_credentials_unconfigured(monkeypatch):
    monkeypatch.setattr(main, "SUPABASE_URL", "")
    monkeypatch.setattr(main, "SUPABASE_PUBLISHABLE_KEY", "")

    with TestClient(main.app) as client:
        response = client.get("/api/config")

    assert response.json() == {
        "supabase_configured": False,
        "supabase_url": "",
        "supabase_publishable_key": "",
        "supabase_storage_bucket": "council-documents",
        "max_file_size_bytes": 20 * 1024 * 1024,
        "allowed_mime_types": [],
        "voice_recognition_language": "en-IN",
        "email_confirmation_required": True,
        "configuration_error": "",
    }


def test_server_side_supabase_keys_are_never_treated_as_browser_safe():
    assert config._is_server_side_supabase_key("sb_secret_test_secret")
    assert config._is_server_side_supabase_key("eyJhbGciOiJub25lIn0.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.")
    assert not config._is_server_side_supabase_key("sb_publishable_test_public")
    assert config._browser_safe_supabase_key("sb_secret_test_secret")[0] == ""
    assert config._browser_safe_supabase_key("sb_publishable_test_public") == ("sb_publishable_test_public", "")


def test_legacy_gemini_defaults_migrate_but_custom_models_are_preserved():
    assert config.resolve_gemini_model("") == "gemini-3.8-flash"
    assert config.resolve_gemini_model("gemini-2.5-flash") == "gemini-3.8-flash"
    assert config.resolve_gemini_model("gemini-3.5-flash-lite") == "gemini-3.8-flash"
    assert config.resolve_gemini_model("my-enabled-custom-model") == "my-enabled-custom-model"


def test_invalid_token_remains_401(monkeypatch):
    monkeypatch.setattr(supabase_auth, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(supabase_auth, "SUPABASE_PUBLISHABLE_KEY", "public-test-key")

    class Response:
        status_code = 401

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(supabase_auth.httpx, "Client", lambda **kwargs: Client())
    try:
        supabase_auth.get_supabase_user("invalid-token")
    except HTTPException as exc:
        assert exc.status_code == 401
        assert "sign in again" in exc.detail
    else:
        raise AssertionError("invalid tokens must be rejected")


def test_supabase_server_error_is_reported_as_retryable(monkeypatch):
    monkeypatch.setattr(supabase_auth, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(supabase_auth, "SUPABASE_PUBLISHABLE_KEY", "public-test-key")

    class Response:
        status_code = 503

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(supabase_auth.httpx, "Client", lambda **kwargs: Client())
    try:
        supabase_auth.get_supabase_user("valid-token")
    except HTTPException as exc:
        assert exc.status_code == 503
        assert "temporarily unavailable" in exc.detail
    else:
        raise AssertionError("upstream outage must be retryable")
