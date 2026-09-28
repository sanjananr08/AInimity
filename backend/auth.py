"""Local persistence helpers for Council history and Supabase user mapping.

Supabase Auth is the active identity provider. The legacy local password/session
helpers remain for backwards compatibility with old local databases and tests;
the FastAPI app does not expose local password login routes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client

from fastapi import Cookie, HTTPException

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.getenv("AINIMITY_DB_PATH", str(DATA_DIR / "ainimity.db")))

SESSION_COOKIE = "ainimity_session"
SESSION_DAYS = int(os.getenv("AINIMITY_SESSION_DAYS", "7"))
SESSION_SECURE = os.getenv("AINIMITY_COOKIE_SECURE", "false").strip().lower() == "true"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()

@contextmanager
def _db():
    """Open one SQLite connection and always close it on exit.

    The explicit close is important on Windows, where an uncollected SQLite
    connection can keep the database file locked and prevent clean-up.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db() -> None:
    with _db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                supabase_user_id TEXT UNIQUE
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS council_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                dilemma TEXT NOT NULL,
                verdict TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                rounds INTEGER NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
            CREATE INDEX IF NOT EXISTS idx_history_user_time
                ON council_history(user_id, created_at DESC);
            """
        )
        # Upgrade databases created by the original AInimity auth schema.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "supabase_user_id" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN supabase_user_id TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_supabase ON users(supabase_user_id)")
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (_iso(_now()),))

def normalize_email(email: str) -> str:
    return email.strip().lower()

def validate_registration(email: str, password: str) -> tuple[str, str]:
    email = normalize_email(email)
    if not EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if len(password) > 256:
        raise HTTPException(status_code=400, detail="Password is too long.")
    return email, password

def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )

def hash_password(password: str) -> tuple[str, str]:
    salt = os.urandom(16)
    digest = _hash_password(password, salt)
    return (
        base64.urlsafe_b64encode(digest).decode("ascii"),
        base64.urlsafe_b64encode(salt).decode("ascii"),
    )

def verify_password(password: str, encoded_hash: str, encoded_salt: str) -> bool:
    try:
        expected = base64.urlsafe_b64decode(encoded_hash.encode("ascii"))
        salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
        actual = _hash_password(password, salt)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False

def create_user(email: str, password: str) -> dict:
    email, password = validate_registration(email, password)
    password_hash, password_salt = hash_password(password)
    created_at = _iso(_now())
    try:
        with _db() as conn:
            cur = conn.execute(
                """
                INSERT INTO users(email, password_hash, password_salt, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (email, password_hash, password_salt, created_at),
            )
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    return {"id": user_id, "email": email, "created_at": created_at}

def authenticate_user(email: str, password: str) -> Optional[dict]:
    email = normalize_email(email)
    with _db() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash, password_salt, created_at FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    if not row or not verify_password(password, row["password_hash"], row["password_salt"]):
        return None
    return {"id": row["id"], "email": row["email"], "created_at": row["created_at"]}

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_session(user_id: int) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(48)
    created_at = _now()
    expires_at = created_at + timedelta(days=SESSION_DAYS)
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO sessions(user_id, token_hash, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, _token_hash(token), _iso(created_at), _iso(expires_at)),
        )
    return token, expires_at

def get_user_from_session_token(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    now = _iso(_now())
    with _db() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.created_at
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ?
            """,
            (_token_hash(token), now),
        ).fetchone()
    return dict(row) if row else None

def current_user(session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
    user = get_user_from_session_token(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Login required.")
    return user

def delete_session(token: Optional[str]) -> None:
    if not token:
        return
    with _db() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))

def set_session_cookie(response, token: str, expires_at: datetime) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=max(1, int((expires_at - _now()).total_seconds())),
        expires=expires_at,
        httponly=True,
        samesite="lax",
        secure=SESSION_SECURE,
        path="/",
    )

def clear_session_cookie(response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")

def save_history(user_id: int, result: dict) -> None:
    import json
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO council_history
                (user_id, dilemma, verdict, confidence, rounds, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                result.get("dilemma", ""),
                result.get("final_verdict", ""),
                int(result.get("final_confidence", 0)),
                int(result.get("rounds", 1)),
                json.dumps(result, ensure_ascii=False),
                _iso(_now()),
            ),
        )

def list_history(user_id: int, limit: int = 30) -> list[dict]:
    import json
    limit = max(1, min(int(limit), 100))
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT id, dilemma, verdict, confidence, rounds, created_at
            FROM council_history
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]

def clear_history(user_id: int) -> None:
    with _db() as conn:
        conn.execute("DELETE FROM council_history WHERE user_id = ?", (user_id,))


def get_or_create_supabase_user(supabase_user_id: str, email: str) -> dict:
    """Map a verified Supabase Auth user to the local history user row.

    The local database is now only an application-data store. Password
    authentication is handled by Supabase and is never read here.
    """
    email = normalize_email(email)
    created_at = _iso(_now())
    with _db() as conn:
        row = conn.execute(
            "SELECT id, email, created_at FROM users WHERE supabase_user_id = ?",
            (supabase_user_id,),
        ).fetchone()
        if row:
            return dict(row)

        row = conn.execute(
            "SELECT id, email, created_at FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET supabase_user_id = ? WHERE id = ?",
                (supabase_user_id, row["id"]),
            )
            return {"id": row["id"], "email": row["email"], "created_at": row["created_at"]}

        # Existing demo schema keeps password columns NOT NULL for backwards
        # compatibility. These random placeholders are not authentication
        # credentials and are never checked by the Supabase flow.
        placeholder_hash, placeholder_salt = hash_password(secrets.token_urlsafe(32))
        cur = conn.execute(
            """
            INSERT INTO users(email, password_hash, password_salt, created_at, supabase_user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email, placeholder_hash, placeholder_salt, created_at, supabase_user_id),
        )
        return {"id": cur.lastrowid, "email": email, "created_at": created_at}

load_dotenv()
_sb_client = None

def _supabase():
    global _sb_client
    if _sb_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
        _sb_client = create_client(url, key)
    return _sb_client

def save_history(user_id: int, result: dict) -> None:
    _supabase().table("council_history").insert({
        "user_id": user_id,
        "dilemma": result.get("dilemma", ""),
        "verdict": result.get("final_verdict", ""),
        "confidence": int(result.get("final_confidence", 0)),
        "rounds": int(result.get("rounds", 1)),
        "result_json": result,
    }).execute()

def list_history(user_id: int, limit: int = 30) -> list[dict]:
    limit = max(1, min(int(limit), 100))
    return (
        _supabase().table("council_history")
        .select("id, dilemma, verdict, confidence, rounds, created_at")
        .eq("user_id", user_id)
        .order("id", desc=True)
        .limit(limit)
        .execute()
        .data
    )

def clear_history(user_id: int) -> None:
    _supabase().table("council_history").delete().eq("user_id", user_id).execute()

def get_or_create_supabase_user(supabase_user_id: str, email: str) -> dict:
    sb = _supabase()
    email = normalize_email(email)
    cols = "id, email, created_at"
    rows = sb.table("users").select(cols).eq("supabase_user_id", supabase_user_id).limit(1).execute().data
    if rows:
        return rows[0]
    rows = sb.table("users").select(cols).eq("email", email).limit(1).execute().data
    if rows:
        sb.table("users").update({"supabase_user_id": supabase_user_id}).eq("id", rows[0]["id"]).execute()
        return rows[0]
    created = sb.table("users").insert({"email": email, "supabase_user_id": supabase_user_id}).execute().data[0]
    return {"id": created["id"], "email": created["email"], "created_at": created["created_at"]}