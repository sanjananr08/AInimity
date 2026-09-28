# Accounts and Voice

## Account flow

```text
Create account
     ↓
email + password
     ↓
scrypt password hash → SQLite
     ↓
random session token → HttpOnly cookie
     ↓
Council Chamber
     ↓
council result → private user history
```

The browser never receives the Gemini API keys.

## Voice flow

```text
Microphone
   ↓
Browser SpeechRecognition
   ↓
Transcript
   ↓
#dilemma textarea
   ↓
POST /api/council/convene
   ↓
four Gemini agents
   ↓
validated verdict
```

Voice recognition is intentionally client-side so the project does not need another paid speech-to-text API.


## Supabase Auth

The current authentication flow is Supabase-first:

1. The frontend loads `@supabase/supabase-js`.
2. `GET /api/config` provides only the Supabase project URL and browser-safe publishable/anon key.
3. Registration uses `supabase.auth.signUp({ email, password })`.
4. Login uses `supabase.auth.signInWithPassword({ email, password })`.
5. The Supabase session persists in the browser.
6. AInimity sends the Supabase access token as `Authorization: Bearer <token>` to FastAPI.
7. FastAPI calls Supabase Auth's `/auth/v1/user` endpoint to validate the token.
8. Private history and council APIs use the resulting Supabase user mapping.

Supabase, not AInimity's SQLite database, is responsible for password authentication. The backend never needs a service-role key.
