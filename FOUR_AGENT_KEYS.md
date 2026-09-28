# AInimity — five independent role keys

The backend uses four environment variables:

- `GEMINI_API_KEY_STRATEGIST`
- `GEMINI_API_KEY_TECHNICAL`
- `GEMINI_API_KEY_ADVERSARIAL`
- `GEMINI_API_KEY_HUMAN_MIND`
- `GEMINI_API_KEY_VALIDATOR`

The browser never receives these values. Each role gets its own `genai.Client`.

## Quota detail

Gemini rate limits are applied at the Google project level, not multiplied simply by creating multiple keys in one project. For genuinely separate quotas, use separate projects.

## Windows

1. Copy `.env.example` to `.env`.
2. Put one key into each variable.
3. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

4. Start the application:

```powershell
python -m uvicorn backend.main:app --reload --port 8000
```

5. Open `http://127.0.0.1:8000`.

The default model is `gemini-3.5-flash-lite`. Change it with `GEMINI_MODEL`.

## If one Google project is denied

A Google `403 PERMISSION_DENIED` / `Your project has been denied access` is a project/account access problem, not a council logic problem. The backend now detects that specific error and tries another configured Gemini key once, so one restricted role project does not stop the entire demo. You can also set `GEMINI_API_KEY` once for a simple single-project demo.

This fallback does not bypass Google's restriction; it only routes the request through a different project that already has access.

## Human Mind

The Human Mind role is a bounded simulation of a human interlocutor. It interrupts with values, lived context, emotion, social consequences, and a practical question before validation; it does not claim consciousness or replace a real person.
