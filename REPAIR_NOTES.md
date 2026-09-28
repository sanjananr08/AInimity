# Repair handoff

## Audit findings

The supplied archive already contained the five-role council, Supabase browser wiring, private Storage operations, token validation, SSE transport, and a matching owner-scoped SQL policy. The main reliability gaps were configuration validation and portability: a committed project URL in `.env.example`, no HTTPS URL rejection at the public config boundary, hard-coded file/MIME/voice settings, stale manual Gemini defaults, and incomplete documentation for provider faults and storage-only behavior.

## What was corrected

- Kept the supplied single-page frontend's layout, style blocks, animations, interactions, page panels, and embedded media unchanged. Frontend changes are limited to runtime configuration, file-limit/MIME checks, and configurable voice language.
- Made Supabase URL, publishable/anon key, bucket, file size, MIME allowlist, email-confirmation guidance, voice language, CORS, port, and Gemini settings environment-driven.
- Normalized and validated Supabase URLs as HTTPS URLs without credentials/query/fragment values.
- Rejected modern `sb_secret_`/server-side keys and legacy JWTs with the `service_role` claim. Invalid configuration returns empty URL/key fields and never echoes secret material from `/api/config`.
- Retained asynchronous Supabase auth callbacks, current-session checks before upload, token-bearing protected API calls, and refreshes of history/files after sign-in and token refresh.
- Retained private Storage upload/list/download/delete under `<supabase-user-id>/<random-id>__<safe-file-name>`, cryptographic IDs, path sanitization, `upsert: false`, MIME preservation, and a default 20 MiB limit.
- Retained the private, idempotent SQL with insert/select/delete owner policies and no UPDATE policy. The SQL clears stale MIME allowlists by default.
- Retained streamed council output and authenticated JSON fallback for unsupported streamed POST transport.
- Set `gemini-3.8-flash` as the default and automatically migrate obsolete Gemini 2.5/3.5 default values. The reported Convene glitch was a Gemini `404 NOT_FOUND` because `gemini-2.5-flash` is restricted for new API projects. If a configured legacy/custom model still returns a 404/NOT_FOUND response, the client retries once with `gemini-3.8-flash`; the frontend also shows an actionable model message. Shared or role-specific Gemini keys remain supported; failed real calls are not replaced with fake output.
- Updated README, API reference, Supabase setup guide, environment template, manual Gemini check, and this handoff.

## Required before live use

This archive intentionally contains no `.env`, live credentials, virtual environment, caches, or generated database. Live verification requires your own:

1. Supabase project URL and browser-safe publishable/anon key.
2. Email provider setting and, if enabled, a confirmed user.
3. `supabase/council_files_storage.sql` run in that same project.
4. One shared `GEMINI_API_KEY` or four role-specific keys and a model enabled for that Google project.

Copy `.env.example` to `.env`, configure those values, restart FastAPI, and open `http://127.0.0.1:8000`. Do not open the frontend through `file://`.

## Validation performed

- `python -m compileall -q backend tests` — passed.
- `python -m pytest -q`: **24 passed**.
- Extracted inline frontend script and ran `node --check` — passed.
- Started FastAPI with credentials disabled — `/api/health` returned HTTP 200.
- `/api/config` with no credentials returned `supabase_configured: false`, empty credential fields, and non-secret defaults.
- Simulated `sb_secret_` configuration — endpoint returned `supabase_configured: false`, empty credential fields, and no secret value.
- Root route served the full existing frontend (about 21 MB) from the same origin.
- Source archive integrity was checked with `unzip -t`; final archive is checked again after packaging.

Real Supabase registration, Storage upload/list/download/delete, cross-user RLS isolation, and Gemini generation were not claimed as live-tested because no user credentials were available in this sandbox.
