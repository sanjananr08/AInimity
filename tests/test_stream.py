"""FastAPI streaming endpoint test; council work is mocked and auth is dependency-overridden."""
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient

from backend import auth
import backend.main as main


def test_council_stream_emits_live_events_for_authenticated_user():
    fake = {
        "dilemma": "hello", "mode": "quick", "rounds": 1, "timeline": [],
        "strategist": {}, "technical": {}, "adversarial": {}, "validator": {},
        "cards": {}, "final_verdict": "Test verdict.", "final_confidence": 91,
    }

    def fake_run(req, on_event=None):
        for event in (
            {"event": "status", "message": "Council engaged."},
            {"event": "agent", "agent": "strategist", "round": 1, "headline": "Strategist complete."},
            {"event": "agent", "agent": "technical", "round": 1, "headline": "Technical complete."},
            {"event": "agent", "agent": "adversarial", "round": 1, "headline": "Adversarial complete."},
            {"event": "agent", "agent": "validator", "round": 1, "headline": "Validator complete."},
            {"event": "complete", "result": fake},
        ):
            on_event(event)
        return fake

    old_run = main.run_council
    old_db, old_data = auth.DB_PATH, auth.DATA_DIR
    old_overrides = main.app.dependency_overrides.copy()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            auth.DB_PATH = Path(tmp) / "test.db"
            auth.DATA_DIR = Path(tmp)
            auth.init_db()
            main.run_council = fake_run
            main.app.dependency_overrides[main.current_user] = lambda: {
                "id": 1, "email": "stream@example.com", "supabase_id": "fake-user-id"
            }
            with TestClient(main.app) as client:
                response = client.post(
                    "/api/council/stream",
                    json={"dilemma": "hello", "mode": "quick"},
                )
                assert response.status_code == 200
                assert "Strategist complete." in response.text
                assert "Test verdict." in response.text
                assert client.get("/api/history").status_code == 200
    finally:
        main.run_council = old_run
        auth.DB_PATH, auth.DATA_DIR = old_db, old_data
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(old_overrides)
