# Supabase Auth and private Council Files

This project uses Supabase Auth in the browser and private Supabase Storage for the existing Council Files panel. FastAPI validates the browser's current Supabase Bearer token before private history and council operations. The project never requires or exposes a Supabase `service_role` or `sb_secret_` key.

## 1. Configure Auth

1. In the target Supabase project, open **Authentication → Providers → Email** and enable Email.
2. Decide whether **Confirm email** is enabled. With it enabled, a new user must confirm the email before sign-in. For a short-lived demo it can be disabled temporarily; set `SUPABASE_EMAIL_CONFIRMATION_REQUIRED` to keep the UI guidance accurate.
3. In **Project Settings → API**, copy the HTTPS **Project URL** to `SUPABASE_URL`.
4. Copy the browser-safe **Publishable key** to `SUPABASE_PUBLISHABLE_KEY`. The legacy `SUPABASE_ANON_KEY` variable is accepted if the publishable variable is absent.
5. Never use a `service_role`, `sb_secret_`, or other server-side key. The backend rejects recognized server-side keys and does not return them from `/api/config`.

Create the local file from the placeholder-only template:

```bash
cp .env.example .env
```

Then set at least `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY`, and restart FastAPI.

## 2. Create the private bucket and policies

Run [`../supabase/council_files_storage.sql`](../supabase/council_files_storage.sql) in the **SQL Editor of the same Supabase project**. The script is idempotent for the configured default bucket:

- bucket: `council-documents`
- public: `false`
- file size limit: `20971520` bytes (20 MiB)
- MIME allowlist: cleared by default so no stale dashboard restriction unexpectedly rejects files
- policies: authenticated insert, select, and delete only when the first path folder equals `(select auth.uid())::text`
- no UPDATE policy, because frontend uploads use unique names and `upsert: false`

If you choose another bucket, replace every `council-documents` occurrence in the SQL with that exact name, run the edited SQL, and set the same value in `SUPABASE_STORAGE_BUCKET`.

The frontend stores objects as:

```text
<supabase-user-id>/<random-id>__<safe-file-name>
```

The first folder is the authorization boundary. A user cannot list, download, or delete another user's folder under the supplied policies.

## 3. File limits and MIME types

The default limit is 20 MiB. `SUPABASE_MAX_FILE_SIZE_BYTES` is sent to the frontend through `/api/config` and checked before any upload begins. The SQL bucket limit must be at least as large. To restrict types, set `SUPABASE_ALLOWED_MIME_TYPES` to a comma-separated list such as `application/pdf,text/plain`; the frontend mirrors the list and the SQL should be edited to enforce the same choice if you want Storage-side enforcement too. Leave it empty for broad support.

The UI does not send uploaded files to Gemini. They are private reference storage only. A file-aware AI feature would be a separate design requiring explicit file selection, server-side authorization, supported-format extraction, text-size/context limits, malware scanning, and transparent status messages.

## 4. Start and verify

From the project root:

```bash
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`, not `file://.../frontend/index.html`.

Check `http://127.0.0.1:8000/api/config`:

- with valid configuration, it returns the HTTPS project URL, browser-safe publishable/anon key, bucket, file limit, MIME list, voice language, and email-confirmation guidance;
- with missing, malformed, or server-side key configuration, it returns `supabase_configured: false` and empty URL/key fields with an actionable error.

## 5. Troubleshooting

| Symptom | Corrective action |
|---|---|
| Missing/unknown bucket | Run the SQL in the correct project and match `SUPABASE_STORAGE_BUCKET` exactly. |
| RLS or policy denial | Re-run the SQL; sign in again; verify object paths begin with the current Supabase Auth UUID. |
| Expired session / invalid JWT | Sign out and sign in again. The frontend refreshes the list after sign-in and token refresh. |
| Network or inactive project | Verify the HTTPS URL, publishable key, browser access to the Supabase project, and that the project is not paused. |
| File too large | Keep the file at or below the configured byte limit and make the bucket `file_size_limit` agree. |
| Email not confirmed | Confirm the email or adjust Authentication → Providers → Email for the demo. |
| Secret key detected | Replace the value with the browser-safe publishable/anon key; never put a service key in the browser. |
