"""
AInimity API + web app entrypoint.

Run from the repository root:
    python -m uvicorn backend.main:app --reload --port 8000

The same FastAPI process serves the frontend at `/`, so login cookies,
voice input, and the council API all live on one local origin.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from queue import Queue
from threading import Thread
import json

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .auth import clear_history, init_db, list_history, save_history
from .supabase_auth import current_user
from .config import (
    CORS_ORIGINS,
    GEMINI_MODEL,
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY,
    SUPABASE_STORAGE_BUCKET,
    SUPABASE_CONFIG_ERROR,
    SUPABASE_MAX_FILE_SIZE_BYTES,
    SUPABASE_ALLOWED_MIME_TYPES,
    SUPABASE_EMAIL_CONFIRMATION_REQUIRED,
    VOICE_RECOGNITION_LANGUAGE,
    APP_PORT,
    _is_server_side_supabase_key,
    validate_supabase_url,
    configured_agents,
    configured_role_agents,
    general_fallback_configured,
    missing_agents,
)
from .gemini_client import GeminiError
from .orchestrator import run_council
from .schemas import (
    ConveneRequest, CouncilResult, WorkspaceRequest, WorkspaceResult,
    EvidenceAssessment, EvidenceAssessmentRequest, ScenarioRequest, ScenarioResult,
)
from .observatory import assess_document, simulate_scenario
from .workspace import run_workspace

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AInimity Council API",
    description="Multi-agent AI decision council with simple accounts, per-user history, and browser voice input.",
    version="2.1.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip() and o.strip() != "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # Never combine a wildcard origin with credentialed access.
    allow_credentials=bool(origins),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "alinimity-council",
        "model": GEMINI_MODEL,
        "configured_agents": configured_agents(),
        "role_specific_agents": configured_role_agents(),
        "general_fallback_configured": general_fallback_configured(),
        "missing_agents": missing_agents(),
        "features": ["five-role-council", "human-mind-interruption", "evidence-retrieval", "citation-aware-validation", "argument-graph-memory", "user-rebuttal-turn", "explicit-image-analysis", "multi-mode-workspace", "research", "decision-matrix", "socratic-tutor", "document-intelligence", "idea-incubator", "code-review", "meeting-assistant", "memory-lab", "evidence-observatory", "chronoforge-play-forward", "supabase-auth", "per-user-history", "private-supabase-storage", "browser-voice-input"],
        "supabase_auth": bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY),
    }

@app.get("/api/config")
def public_config():
    """Return only browser-safe Supabase configuration."""
    configuration_error = SUPABASE_CONFIG_ERROR or validate_supabase_url(SUPABASE_URL)
    if _is_server_side_supabase_key(SUPABASE_PUBLISHABLE_KEY):
        configuration_error = "A server-side Supabase secret/service_role key was detected. Replace it with the browser-safe publishable or anon key."
    configured = bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY and not configuration_error)
    if not configured:
        return {
            "supabase_configured": False,
            "supabase_url": "",
            "supabase_publishable_key": "",
            "supabase_storage_bucket": SUPABASE_STORAGE_BUCKET,
            "max_file_size_bytes": SUPABASE_MAX_FILE_SIZE_BYTES,
            "allowed_mime_types": list(SUPABASE_ALLOWED_MIME_TYPES),
            "voice_recognition_language": VOICE_RECOGNITION_LANGUAGE,
            "email_confirmation_required": SUPABASE_EMAIL_CONFIRMATION_REQUIRED,
            "configuration_error": configuration_error,
        }
    return {
        "supabase_configured": True,
        "supabase_url": SUPABASE_URL,
        "supabase_publishable_key": SUPABASE_PUBLISHABLE_KEY,
        "supabase_storage_bucket": SUPABASE_STORAGE_BUCKET,
        "max_file_size_bytes": SUPABASE_MAX_FILE_SIZE_BYTES,
        "allowed_mime_types": list(SUPABASE_ALLOWED_MIME_TYPES),
        "voice_recognition_language": VOICE_RECOGNITION_LANGUAGE,
        "email_confirmation_required": SUPABASE_EMAIL_CONFIRMATION_REQUIRED,
    }


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return {"user": user}


@app.get("/api/history")
def history(user: dict = Depends(current_user)):
    return {"items": list_history(user["id"])}

@app.delete("/api/history")
def delete_history(user: dict = Depends(current_user)):
    clear_history(user["id"])
    return {"message": "Council memory cleared."}

@app.post("/api/council/stream")
def council_stream(req: ConveneRequest, user: dict = Depends(current_user)):
    """Stream council progress as Server-Sent Events for a live UI."""
    events: Queue = Queue()

    def emit(event: dict):
        events.put(event)

    def worker():
        try:
            result = run_council(req, on_event=emit)
            save_history(user["id"], result)
        except ValidationError as exc:
            events.put({"event": "error", "message": f"Agent response validation failed: {exc}"})
        except GeminiError as exc:
            events.put({"event": "error", "message": str(exc)})
        except Exception:
            events.put({"event": "error", "message": "Council failed unexpectedly. Check the server logs and retry."})
        finally:
            events.put({"event": "__end__"})

    Thread(target=worker, name="ainimity-council-stream", daemon=True).start()

    def event_generator():
        while True:
            event = events.get()
            if event.get("event") == "__end__":
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.post("/api/council/convene", response_model=CouncilResult)
def convene(req: ConveneRequest, user: dict = Depends(current_user)):
    """
    Runs the full council debate and stores the resulting ruling in the
    authenticated user's private council history.
    """
    try:
        result = run_council(req)
        save_history(user["id"], result)
        return result
    except ValidationError as e:
        raise HTTPException(status_code=502, detail=f"An agent returned an invalid response: {e}")
    except GeminiError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Council failed unexpectedly. Check the server logs and retry.")


@app.post("/api/workspace", response_model=WorkspaceResult)
def workspace(req: WorkspaceRequest, user: dict = Depends(current_user)):
    """Run one of the isolated non-debate Workspace modes."""
    try:
        return run_workspace(req)
    except ValidationError as e:
        raise HTTPException(status_code=502, detail=f"Workspace output validation failed: {e}")
    except GeminiError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Workspace failed unexpectedly. Check the server logs and retry.")


@app.post("/api/evidence/assess", response_model=EvidenceAssessment)
def assess_evidence(req: EvidenceAssessmentRequest, user: dict = Depends(current_user)):
    """Assess document reliability signals without making a high-impact decision."""
    try:
        return assess_document(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Evidence assessment failed. Check the document and retry.")


@app.post("/api/chronoforge/simulate", response_model=ScenarioResult)
def chronoforge(req: ScenarioRequest, user: dict = Depends(current_user)):
    """Play selected manual events forward; this is not a forecasting endpoint."""
    return simulate_scenario(req)

# Serve the existing single-file frontend from the same origin.
# API routes above take precedence over this mount.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=APP_PORT, reload=True)
