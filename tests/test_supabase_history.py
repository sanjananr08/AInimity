import uuid
from backend import auth

def test_supabase_user_and_history():
    fake_id = str(uuid.uuid4())
    email = f"test-{fake_id[:8]}@example.com"
    user = auth.get_or_create_supabase_user(fake_id, email)
    assert auth.get_or_create_supabase_user(fake_id, email)["id"] == user["id"]

    auth.save_history(user["id"], {
        "dilemma": "Test question", "rounds": 1,
        "final_verdict": "Test answer.", "final_confidence": 90,
    })
    rows = auth.list_history(user["id"])
    assert len(rows) == 1 and rows[0]["dilemma"] == "Test question"

    auth.clear_history(user["id"])
    assert auth.list_history(user["id"]) == []
    auth._supabase().table("users").delete().eq("id", user["id"]).execute()