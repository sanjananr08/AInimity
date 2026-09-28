# AInimity — The Council Chamber

AInimity is a FastAPI application serving its existing single-file HTML council UI from the same origin. Four Gemini-backed roles—Strategist, Technical, Adversarial, and Validator—produce a validated ruling. This repair keeps the supplied pages, layout, CSS, animations, interactions, and embedded media intact; changes are limited to integration wiring and diagnostics.

## What is included

- Supabase Auth email/password registration, sign-in, session restore, refresh, and sign-out.
- FastAPI Bearer-token validation against Supabase Auth for private history and council endpoints.
- Private Supabase Storage bucket support for upload, list, download, and delete under `<supabase-user-id>/<random-id>__<safe-file-name>`.
- 20 MiB default per-file limit, configurable MIME allowlist, path sanitization, unique IDs, and `upsert: false`.
- Streamed `/api/council/stream` transport with JSON `/api/council/convene` fallback.
- Shared `GEMINI_API_KEY` or optional role-specific keys, with `gemini-3.8-flash` as the default model.
- Local SQLite application history only. Passwords are not handled by FastAPI or stored as usable credentials by the Supabase flow.

## Workspace modes

The original **Council Debate** remains available in its own chamber and keeps
the existing five-role streaming and JSON endpoints. The separate Workspace
adds focused tools through `/api/workspace`: Research Expedition, Decision
Matrix, Socratic Tutor, Document Intelligence, Idea Incubator, Code Review,
Meeting Assistant, and Memory Lab. Each mode is routed to a deliberate
specialist role and source policy; Fact Check and Scenario Simulator are not
Workspace modes. They live in their own Evidence Observatory and ChronoForge
universes. Workspace results are structured and not silently persisted; paste
document/code/meeting context into its dedicated Workspace input when needed.

## Quantum multiverse navigation

The interface treats major sections as connected universes rather than flat
tabs. Navigation collapses a visible wavefunction and branches into a new
destination before opening the panel:

| Section | Universe identity | Visual language |
|---|---|---|
| Home | Nexus Prime | Origin point and shared coordinate system |
| Council | Singularity Court | Event horizon, accretion rings, five minds in orbit |
| Workspace | Nebula of Possibilities | Branching futures, quasar/pulsar/orbit/wormhole/aurora metaphors |
| Memory | Archive Moon | Slow orbital archive and warm lunar signal |
| Games | Pulsar Arcade | Rhythmic pulse, solar flare, playful frequency |
| Evidence | Evidence Observatory | Provenance, claims, contradictions, and human review |
| Chrono | ChronoForge | Manual events, checkpoints, and branch comparison |

The transition is implemented locally in the frontend with a reduced-motion
fallback. No external image or tracking request is required for the effects;
the visual language is inspired by NASA/ESA references for black holes,
pulsars, neutron stars, and planetary aurorae.

## Evidence Observatory

Evidence Observatory is a separate universe for manually reviewing important
documents up to 32 MiB. It accepts readable text documents and PDFs, extracts the text,
separates claims, and returns inspectable reliability signals including
provenance gaps, contradictions, missing context, and questions for a human
reviewer. Its score is an evidence-health signal, not a truth guarantee.

Healthcare, legal, financial, eligibility, and other high-impact material is
advisory only. The feature does not diagnose, prescribe, determine eligibility,
make official decisions, or replace a qualified professional. Scanned PDFs
need OCR before analysis. Large documents are bounded at the model-context
boundary while preserving the beginning and end of the document.

## ChronoForge Play Forward

ChronoForge is a manually operated scenario playback tool. Users set an
objective and starting state, place events on a timeline, classify their
impact, and compare three branches: continue, pause and investigate, or change
course. Its output is explicitly labelled as a scenario, not a forecast.

## Optional Node.js and MongoDB integration

The primary application remains Python/FastAPI with SQLite and Supabase. The
`integrations/mongodb/decision-snapshot-repository.mjs` adapter is an optional,
human-readable Node.js integration for storing a later **human decision and
actual outcome** for calibration work. It is opt-in, bounded, and never runs
unless `MONGODB_URI` is configured and `connect()` is called. Run
`npm run verify:contracts` to check the repository contracts without needing a
MongoDB server.

## Configuration

Copy the template and edit only your local copy:

```bash
python -m venv .venv
# Linux/macOS
. .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cp .env.example .env                 # Windows: Copy-Item .env.example .env
```

Set these values in `.env`. The repository now includes a complete [`.env.example`](.env.example) template with safe placeholders; copy it first and edit only `.env`:

| Variable | Purpose | Default |
|---|---|---|
| `SUPABASE_URL` | HTTPS Supabase project URL | required |
| `SUPABASE_PUBLISHABLE_KEY` | Browser-safe publishable key; legacy `SUPABASE_ANON_KEY` is also accepted | required |
| `SUPABASE_STORAGE_BUCKET` | Private Storage bucket name; must match the SQL | `council-documents` |
| `SUPABASE_MAX_FILE_SIZE_BYTES` | Frontend and SQL-aligned file limit | `20971520` |
| `SUPABASE_ALLOWED_MIME_TYPES` | Optional comma-separated MIME allowlist; empty means broad support | empty |
| `SUPABASE_EMAIL_CONFIRMATION_REQUIRED` | UI guidance for the Supabase Email setting | `true` |
| `GEMINI_API_KEY` | One shared Gemini key for all five roles | optional |
| `GEMINI_API_KEY_STRATEGIST`, `_TECHNICAL`, `_ADVERSARIAL`, `_HUMAN_MIND`, `_VALIDATOR` | Optional role-specific keys; override the shared key | optional |
| `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL` | Primary and unavailable-model fallback | `gemini-3.8-flash` |
| `GEMINI_RPM_LIMIT` | Local calls-per-minute guard per role | `4` |
| `CORS_ORIGINS` | Comma-separated allowed origins | local origins |
| `APP_PORT` / `PORT` | Application port; hosting `PORT` wins | `8000` |
| `VOICE_RECOGNITION_LANGUAGE` | Browser SpeechRecognition language | `en-IN` |
| `COUNCIL_DEADLINE` | Optional project deadline passed into the runtime | `2026-12-31T23:59:00Z` |
| `AINIMITY_DB_PATH` | Local SQLite history path | `data/ainimity.db` |
| `AINIMITY_SESSION_DAYS` / `AINIMITY_COOKIE_SECURE` | Local session lifetime and HTTPS cookie flag | `7` / `false` |

Never put a `service_role`, `sb_secret_`, or other server-side Supabase key in either browser configuration variable. The backend rejects such a key and `/api/config` returns empty credentials. Do not commit `.env`.

## Supabase setup

1. In **Authentication → Providers → Email**, enable Email.
2. Decide whether **Confirm email** is enabled. If enabled, users must confirm before signing in. For a disposable demo, it may be disabled temporarily.
3. In **Project Settings → API**, copy the Project URL and publishable key (or legacy anon key) into `.env`.
4. In the correct project's **SQL Editor**, run [`supabase/council_files_storage.sql`](supabase/council_files_storage.sql). It creates/updates a private `council-documents` bucket with a 20 MiB limit and owner-only insert/select/delete policies. If you change the bucket name, replace it consistently in the SQL and `.env` before running it.
5. Keep the bucket private. Do not add an UPDATE policy: the frontend uses unique paths and `upsert: false`.

Uploaded files are **private reference storage only**. Uploading a file does not automatically send it to Gemini or change a council answer. A future file-aware feature would need explicit file selection, server-side authorization, format extraction, text/context limits, malware scanning, and transparent status reporting.

## Run locally

From the project root, always serve the frontend through FastAPI:

```bash
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Opening `frontend/index.html` via `file://` is unsupported for the authenticated version. On Windows, `start_backend.bat` prefers `.venv\Scripts\python.exe` and invokes `python -m uvicorn`, avoiding blocked `uvicorn.exe` launchers.

Useful endpoints:

- `GET /api/health` — liveness and configured model/agent summary.
- `GET /api/config` — browser-safe Supabase URL/key, bucket, file limit, MIME list, voice language, and email-confirmation guidance.
- `GET /docs` — FastAPI Swagger UI.

## Troubleshooting

- **Missing bucket / unknown bucket:** run `supabase/council_files_storage.sql` in the same Supabase project and make `SUPABASE_STORAGE_BUCKET` match exactly.
- **RLS/policy denial:** sign in again and rerun the SQL. The first folder of every object path must equal the authenticated user's Supabase UUID.
- **Expired login / invalid JWT:** sign out and sign in again. The browser refreshes sessions asynchronously and protected FastAPI routes validate the current Bearer token.
- **20 MiB failure:** the frontend rejects files before upload; check `SUPABASE_MAX_FILE_SIZE_BYTES` and the bucket's `file_size_limit`. Run the SQL again if the bucket was created with a smaller limit.
- **Invalid publishable key:** use the Project Settings → API publishable or anon key, not `service_role` or `sb_secret_`. Restart FastAPI after changing `.env` and inspect `/api/config`.
- **Email not confirmed:** confirm the Supabase email or disable Confirm email in Supabase Auth for a demo.
- **Gemini key/model failure:** set `GEMINI_API_KEY` or all role-specific keys, verify project access/quota, and choose a model available to that project. The old Gemini 2.5/3.5 default setting is automatically migrated to `gemini-3.8-flash`; other custom values are preserved. No fake council output is substituted when real generation fails.
- **Stream rejected by a proxy:** the frontend retries through the authenticated JSON `/api/council/convene` endpoint when streamed POST transport is unavailable.

## Tests

```bash
python -m compileall -q backend tests
python -m pytest -q
node --check /tmp/ainimity-inline.js
```

The automated suite mocks model/provider calls and does not require live credentials. Real Supabase registration, private Storage operations, and Gemini generation require your own configured project, signed-in user, Storage SQL, and API key.

## Important attachment behavior

The current Council Files panel is private Supabase Storage only. Uploading a file does **not** send it to Gemini or make the council image-aware; the UI states this explicitly so it never implies that a screenshot was analyzed when it was not.

## Debate-engine upgrade

The council now supports explicit user rebuttals, bounded public-source retrieval with provenance, citation-aware validation, explicit image attachments for Gemini multimodal analysis, and a deterministic argument graph returned with each ruling. The image path is opt-in and capped at 4 MB; private Supabase files remain storage-only until explicitly attached.

Before public deployment, add request rate limiting, rotate any keys that have appeared in old archives, and use a separate Gemini project per role only if you need operational isolation—not as proof of independent intelligence.

## Gemini quota routing

Configure five dedicated role keys—`GEMINI_API_KEY_STRATEGIST`, `GEMINI_API_KEY_TECHNICAL`, `GEMINI_API_KEY_ADVERSARIAL`, `GEMINI_API_KEY_HUMAN_MIND`, and `GEMINI_API_KEY_VALIDATOR`—plus `GEMINI_API_KEY` as the general fallback. A quota, permission, or transient provider failure on a role first switches to the general key; role keys are not silently borrowed by other roles. The `/api/health` response reports only non-sensitive routing status.
