# API Reference

Base URL (local dev): `http://127.0.0.1:8000`

## `GET /api/health`

Returns liveness, the configured Gemini model, configured/missing council roles, and feature flags. It does not make live Supabase or Gemini calls.

## `GET /api/config`

Returns only browser-safe runtime settings used by the single-origin frontend:

```json
{
  "supabase_configured": true,
  "supabase_url": "https://YOUR_PROJECT_REF.supabase.co",
  "supabase_publishable_key": "<publishable-or-anon-key>",
  "supabase_storage_bucket": "council-documents",
  "max_file_size_bytes": 20971520,
  "allowed_mime_types": [],
  "voice_recognition_language": "en-IN",
  "email_confirmation_required": true
}
```

Only a publishable/anon key can be returned. If the URL is missing/malformed or a secret/service-role key is detected, `supabase_configured` is false, `supabase_url` and `supabase_publishable_key` are empty, and `configuration_error` explains the correction without echoing secret material.

## Authentication and private data

- The browser uses Supabase Auth for registration, sign-in, session restore/refresh, and sign-out.
- Protected endpoints accept `Authorization: Bearer <access token>`.
- FastAPI validates that token against Supabase Auth; invalid/expired tokens return `401`, and provider outages return `503`.
- `/api/history` and `/api/council/*` are private to the authenticated Supabase user.
- Council files use the browser's current Supabase session directly against the configured private Storage bucket. RLS restricts the first object-path folder to the authenticated user's UUID.

## `POST /api/council/convene`

Runs the five-role debate synchronously and returns the validated result. `GEMINI_API_KEY` may be shared across roles, or role-specific environment keys may be used. `gemini-3.8-flash` is the default model; obsolete Gemini 2.5/3.5 default values are migrated to it. If a legacy/custom model returns a 404/NOT_FOUND response, the client retries once with the current fallback model; quota, permission, key, and invalid-output failures remain visible.

### Request body

| Field | Type | Required | Notes |
|---|---|---|---|
| `dilemma` | string | yes | The question or decision to debate. |
| `clarified_goal` | string | no | Defaults to `dilemma`. |
| `constraints` | string[] | no | e.g. `['24–48 hour build window']`. |
| `priorities` | object | no | `time`, `impact`, and `innovation` weights. |
| `team_skills` | string | no | Technical-agent context. |
| `mode` | `quick` or `deep` | no | One round or two rounds. |

The backend returns actionable `502` details for missing keys, denied projects, quota exhaustion, invalid model output, and invalid agent JSON. It does not silently fabricate a ruling after a real provider failure.

## `POST /api/council/stream`

Authenticated Server-Sent Events stream consumed by the existing live debate UI. Events report status, agent progress, completion, or an error. When a proxy rejects streamed POST transport, the frontend retries the same authenticated request through `/api/council/convene`.

## Memory

- `GET /api/history` — list the signed-in user's rulings.
- `DELETE /api/history` — clear only the signed-in user's rulings.

## Evidence Observatory and ChronoForge

- `POST /api/evidence/assess` — authenticated JSON request containing readable document text or a base64-encoded PDF up to 32 MiB. Text sent to the model is bounded at 120,000 characters while preserving the beginning and end. Returns provenance signals, claim statuses, contradictions, missing information, review questions, and an advisory safety notice. It does not make healthcare, legal, financial, eligibility, or sentencing decisions.
- `POST /api/chronoforge/simulate` — authenticated JSON request containing a manually authored objective, initial state, horizon, and selected events. Returns checkpoints and branch comparisons. This is scenario playback, not forecasting.

## `POST /api/workspace`

Runs a separate non-debate specialist mode. This endpoint does not change the
existing Debate routes or Debate history contract.

Supported `mode` values:

| Mode | Purpose |
|---|---|
| `research` | Source-grounded research briefing |
| `decision_matrix` | Criteria-based option comparison |
| `tutor` | Adaptive Socratic teaching and practice |
| `document_intelligence` | Extract facts, obligations, ambiguity, and risks from supplied text |
| `idea_incubator` | Turn an idea into a testable concept |
| `code_review` | Correctness, security, performance, maintainability, and test review |
| `meeting` | Decisions, owners, deadlines, and follow-up drafting |
| `memory_lab` | User-controlled goals, projects, and decision snapshot; never silently persisted |

### Request body

```json
{
  "mode": "research",
  "task": "Research this topic.",
  "context": "Optional notes, transcript, code, or document text.",
  "evidence_urls": [],
  "evidence_text": "Optional unverified source notes.",
  "audience": "The signed-in user"
}
```

The response contains a title, summary, typed sections, next actions, caveats,
calibrated confidence, and citations restricted to retrieved source IDs. The
endpoint requires the same authenticated Supabase session as Debate.

## Error responses

| Status | Meaning |
|---|---|
| `401` | Missing, invalid, or expired Supabase access token. |
| `422` | Request body validation failed. |
| `502` | Gemini/provider response or agent output could not be used. |
| `503` | Supabase configuration or upstream Auth service is unavailable. |
| `500` | Unexpected server-side failure. |

FastAPI errors use a JSON `detail` field.

## Debate-engine extensions

`POST /api/council/convene` and `POST /api/council/stream` now accept these optional fields:

- `rebuttal`: a user interruption or counterargument carried through every role.
- `evidence_urls`: up to 8 explicit public HTTP(S) URLs. Private/local hosts, embedded credentials, excessive redirects, non-text content, and responses over 1 MB are blocked.
- `evidence_text`: user-supplied source notes, clearly labeled as unverified.
- `reference_image_base64` + `reference_image_mime_type`: explicit PNG/JPEG/WebP/GIF attachment, capped at 4 MB for Gemini multimodal analysis.

Responses now include:

- `evidence`: source provenance, retrieval status, content hash, and bounded snippet.
- `validator.citations`: source IDs connected to claims; the model is instructed never to invent URLs.
- `argument_graph`: deterministic nodes and edges for the question, options, risks, attacks, human interruption, evidence, and final ruling.

The server never treats private Supabase Storage files as analyzed evidence automatically. An image becomes model input only when the user explicitly attaches it to the next debate in the UI.
