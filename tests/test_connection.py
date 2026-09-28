"""Manual Gemini connection check for the configured council keys.

Run from the project root:
    python tests/test_connection.py

This makes one tiny request per configured agent. It is intentionally not run by pytest.
"""

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
AGENTS = ("strategist", "technical", "adversarial", "validator")

def main():
    missing = []
    shared = os.environ.get("GEMINI_API_KEY", "").strip()
    for agent in AGENTS:
        env_name = f"GEMINI_API_KEY_{agent.upper()}"
        key = os.environ.get(env_name, "").strip() or shared
        if not key:
            missing.append(env_name)
            continue
        print(f"{agent:12} key loaded")
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"),
            contents="Reply with exactly: OK",
        )
        print(f"{agent:12} response: {(response.text or '').strip()}")
    if missing:
        raise SystemExit("Missing: " + ", ".join(missing))

if __name__ == "__main__":
    main()
