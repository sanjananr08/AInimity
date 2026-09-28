from types import SimpleNamespace

import pytest

from backend.gemini_client import _generate_content_with_model_fallback


class FakeModels:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append(model)
        if self.error and len(self.calls) == 1:
            raise self.error
        return SimpleNamespace(text='{}')


class FakeClient:
    def __init__(self, models):
        self.models = models


def test_unavailable_legacy_model_retries_with_current_fallback():
    models = FakeModels(RuntimeError("404 NOT_FOUND: model is no longer available"))
    response = _generate_content_with_model_fallback(
        FakeClient(models), "gemini-2.5-flash", "hello", object()
    )
    assert response.text == "{}"
    assert models.calls == ["gemini-2.5-flash", "gemini-3.8-flash"]


def test_non_model_error_is_not_hidden_by_fallback():
    models = FakeModels(RuntimeError("403 PERMISSION_DENIED"))
    with pytest.raises(RuntimeError, match="PERMISSION_DENIED"):
        _generate_content_with_model_fallback(
            FakeClient(models), "gemini-custom", "hello", object()
        )
    assert models.calls == ["gemini-custom"]
