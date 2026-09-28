from backend import gemini_client


def test_general_key_is_the_only_emergency_fallback(monkeypatch):
    monkeypatch.setattr(gemini_client, "GENERAL_GEMINI_API_KEY", "general-key")
    monkeypatch.setattr(
        gemini_client,
        "AGENT_API_KEYS",
        {
            "strategist": "strategist-key",
            "technical": "technical-key",
            "adversarial": "adversarial-key",
            "human_mind": "human-key",
            "validator": "validator-key",
        },
    )
    assert gemini_client._configured_fallbacks("strategist") == [("general", "general-key")]


def test_general_key_is_not_reused_when_it_is_the_active_key(monkeypatch):
    monkeypatch.setattr(gemini_client, "GENERAL_GEMINI_API_KEY", "shared-key")
    monkeypatch.setattr(gemini_client, "AGENT_API_KEYS", {"strategist": "shared-key"})
    assert gemini_client._configured_fallbacks("strategist") == []


def test_quota_error_switches_to_general_key(monkeypatch):
    monkeypatch.setattr(gemini_client, "GENERAL_GEMINI_API_KEY", "general-key")
    monkeypatch.setattr(gemini_client, "AGENT_API_KEYS", {"strategist": "role-key"})
    monkeypatch.setattr(gemini_client, "AGENT_MODELS", {"strategist": "test-model"})
    monkeypatch.setattr(gemini_client, "get_client", lambda agent: "role-client")
    monkeypatch.setattr(gemini_client, "_client_for_api_key", lambda name, key: "general-client")
    monkeypatch.setattr(gemini_client._rate_limiters["strategist"], "wait", lambda: None)
    monkeypatch.setattr(gemini_client._general_rate_limiter, "wait", lambda: None)

    calls = []

    class Response:
        text = '{"answer": "fallback worked"}'

    def fake_generate(client, model, contents, config):
        calls.append(client)
        if len(calls) == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED quota")
        return Response()

    monkeypatch.setattr(gemini_client, "_generate_content_with_model_fallback", fake_generate)

    result = gemini_client.generate_json(
        "system", "user", response_schema={"type": "object"}, retries=0, agent="strategist"
    )
    assert result == {"answer": "fallback worked"}
    assert calls == ["role-client", "general-client"]
