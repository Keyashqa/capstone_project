"""Marvis FastAPI application — wraps the ADK Workflow agent.

Boots:
1. init_db()  — create/migrate SQLite schema (must happen before ADK imports agent)
2. get_fast_api_app() — ADK framework app (SSE run, session management, /health)
3. Auth + wallet routes
4. /health endpoint

Model: local Gemma via Ollama (no Gemini, no API keys).
"""
from __future__ import annotations

import os
from pathlib import Path

from app.db import init_db

init_db()

# ADK framework checks for GOOGLE_GENAI_USE_VERTEXAI and GOOGLE_API_KEY at import.
# We're not using Gemini — set a dummy value so ADK doesn't crash at startup.
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "False")
os.environ.setdefault("GOOGLE_API_KEY", "not-used-ollama-only")

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from google.adk.cli.fast_api import get_fast_api_app  # noqa: E402

from app.auth import router as auth_router  # noqa: E402
from app.config import MODEL_NAME  # noqa: E402

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    allow_origins=["*"],
    default_llm_model=MODEL_NAME,
)

app.title = "Marvis"
app.description = "Personal orchestrator — hire, pay, provision, verify, settle with specialist agents."

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/marvis/health")
def health() -> dict:
    return {"status": "ok", "service": "marvis", "model": MODEL_NAME}


# Serve React UI build if it exists
_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/ui", include_in_schema=False)
    @app.get("/login", include_in_schema=False)
    @app.get("/register", include_in_schema=False)
    @app.get("/wallet", include_in_schema=False)
    @app.get("/chat", include_in_schema=False)
    def serve_spa(_path: str = "") -> FileResponse:
        return FileResponse(_DIST / "index.html")

    @app.get("/", include_in_schema=False)
    def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/login")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
