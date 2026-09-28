from pathlib import Path
import tempfile

import pytest
from fastapi.testclient import TestClient

from backend import auth
import backend.main as main
from backend.schemas import WorkspaceRequest
import backend.workspace as workspace

MODES = [
    "research", "decision_matrix", "tutor",
    "document_intelligence", "idea_incubator", "code_review", "meeting", "memory_lab",
]


def sample_output():
    return {
        "title": "Workspace result",
        "summary": "A grounded result with explicit next steps and limitations.",
        "sections": [{"title": "Findings", "content": "The supplied context supports a bounded conclusion.", "bullets": ["Check the primary source."]}],
        "action_items": ["Review the cited evidence before acting."],
        "caveats": ["This output is not a guarantee and uses only supplied context."],
        "confidence": 0.74,
        "citations": [
            {"source_id": "src_1", "claim": "Supported claim", "support": "supports"},
            {"source_id": "src_fake", "claim": "Unverified claim", "support": "supports"},
        ],
    }


@pytest.mark.parametrize("mode", MODES)
def test_every_workspace_mode_has_a_typed_contract(mode):
    request = WorkspaceRequest(mode=mode, task=f"Use the {mode} workspace mode for this task.")
    assert request.mode == mode
    assert workspace.MODE_GUIDANCE[mode]


@pytest.mark.parametrize("mode", MODES)
def test_every_workspace_mode_runs_through_grounded_pipeline(monkeypatch, mode):
    monkeypatch.setattr(workspace, "retrieve_urls", lambda urls: [])
    monkeypatch.setattr(workspace, "build_evidence_context", lambda sources, text: "No external evidence supplied.")
    monkeypatch.setattr(workspace, "generate_json", lambda *args, **kwargs: sample_output())
    result = workspace.run_workspace(WorkspaceRequest(mode=mode, task=f"Run the {mode} workflow."))
    assert result["mode"] == mode
    assert result["summary"]
    assert result["sections"]
    assert result["confidence"] == 0.74


def test_workspace_filters_citations_to_retrieved_sources(monkeypatch):
    monkeypatch.setattr(workspace, "retrieve_urls", lambda urls: [{"source_id": "src_1", "status": "retrieved", "title": "Source"}])
    monkeypatch.setattr(workspace, "build_evidence_context", lambda sources, text: "Evidence context")
    monkeypatch.setattr(workspace, "generate_json", lambda *args, **kwargs: sample_output())
    result = workspace.run_workspace(WorkspaceRequest(mode="research", task="Research this claim."))
    assert [item["source_id"] for item in result["citations"]] == ["src_1"]
    assert result["evidence"][0]["status"] == "retrieved"


def test_modes_route_to_different_specialists_and_non_source_modes_do_not_fetch(monkeypatch):
    calls = []
    monkeypatch.setattr(workspace, "retrieve_urls", lambda urls: calls.append(urls) or [])
    monkeypatch.setattr(workspace, "build_evidence_context", lambda sources, text: "No external evidence supplied.")
    agents = []
    monkeypatch.setattr(workspace, "generate_json", lambda *args, **kwargs: agents.append(kwargs["agent"]) or sample_output())
    workspace.run_workspace(WorkspaceRequest(mode="research", task="Research a topic.", evidence_urls=["https://example.com"]))
    workspace.run_workspace(WorkspaceRequest(mode="code_review", task="Review this code.", evidence_urls=["https://example.com"]))
    assert agents == ["strategist", "technical"]
    assert calls == [["https://example.com"]]


def test_workspace_endpoint_is_authenticated_and_returns_structured_result(monkeypatch):
    old_db, old_data, old_overrides = auth.DB_PATH, auth.DATA_DIR, main.app.dependency_overrides.copy()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            auth.DB_PATH, auth.DATA_DIR = Path(tmp) / "test.db", Path(tmp)
            auth.init_db()
            monkeypatch.setattr(main, "run_workspace", lambda req: {"mode": req.mode, **sample_output(), "evidence": []})
            main.app.dependency_overrides[main.current_user] = lambda: {"id": 1, "email": "workspace@example.com", "supabase_id": "fake"}
            with TestClient(main.app) as client:
                response = client.post("/api/workspace", json={"mode": "research", "task": "Research this topic."})
                assert response.status_code == 200
                assert response.json()["mode"] == "research"
                assert response.json()["sections"]
    finally:
        auth.DB_PATH, auth.DATA_DIR = old_db, old_data
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(old_overrides)
