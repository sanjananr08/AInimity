from pathlib import Path

from backend import auth


def test_password_hash_roundtrip():
    hashed, salt = auth.hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert auth.verify_password("correct horse battery staple", hashed, salt)
    assert not auth.verify_password("wrong password", hashed, salt)


def test_user_and_session_and_history(tmp_path):
    original_db = auth.DB_PATH
    original_data = auth.DATA_DIR
    auth.DB_PATH = tmp_path / "ainimity.db"
    auth.DATA_DIR = tmp_path
    try:
        auth.init_db()
        user = auth.create_user("Person@Example.com", "password123")
        assert user["email"] == "person@example.com"

        logged = auth.authenticate_user("person@example.com", "password123")
        assert logged and logged["id"] == user["id"]

        token, _ = auth.create_session(user["id"])
        session_user = auth.get_user_from_session_token(token)
        assert session_user["email"] == "person@example.com"

        auth.delete_session(token)
        assert auth.get_user_from_session_token(token) is None
    finally:
        auth.DB_PATH = original_db
        auth.DATA_DIR = original_data
