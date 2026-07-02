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


@app.get("/marketplace/agents")
def marketplace_agents() -> dict:
    """Public catalog of hireable specialist agents (SkillCards)."""
    from app.marketplace.seed import seed_catalog
    from app.marketplace.skill_registry import get_registry

    seed_catalog()  # idempotent — ensures catalog is populated
    cards = get_registry().list_cards()

    agents = [
        {
            "skill_id": c.skill_id,
            "agent_name": c.agent_name,
            "display_name": c.display_name,
            "version": c.version,
            "description": c.description,
            "specialties": c.specialties,
            "model": c.model,
            "currency": c.pricing.currency,
            "base_fee_cents": c.pricing.base_fee_cents,
            "completion_fee_cents": c.pricing.completion_fee_cents,
            "capabilities": [
                {"mcp_server": cap.mcp_server, "tool_name": cap.tool_name, "why": cap.why}
                for cap in c.required_capabilities
            ],
            "reputation": c.reputation,
        }
        for c in cards
    ]
    return {"agents": agents, "count": len(agents)}


@app.get("/owned-skills")
def owned_skills() -> dict:
    """Marvis's OWNED skill library — built once via SkillBuilder, run free forever after.

    Separate from /marketplace/agents: these are never for sale, never re-hired,
    and never appear in the broker's catalog (plan2.md §P2-2).
    """
    from app.marketplace.seed import seed_owned_library
    from app.marketplace.skill_registry import get_owned_registry

    seed_owned_library()  # idempotent — picks up anything built before a restart
    cards = get_owned_registry().list_cards()

    skills = [
        {
            "skill_id": c.skill_id,
            "agent_name": c.agent_name,
            "display_name": c.display_name,
            "version": c.version,
            "description": c.description,
            "specialties": c.specialties,
            "model": c.model,
            "instruction": c.instruction,
            "capabilities": [
                {"mcp_server": cap.mcp_server, "tool_name": cap.tool_name, "why": cap.why}
                for cap in c.required_capabilities
            ],
        }
        for c in cards
    ]
    return {"skills": skills, "count": len(skills)}


@app.get("/platform/stats")
def platform_stats() -> dict:
    """Read-only, cross-user view of total money moved through the ledger so far.

    Purely observational — reads the existing double-entry ledger (app/wallet.py:
    get_platform_stats). Never writes, never touches payment/escrow/payout logic.
    """
    from app import wallet as wallet_ops

    return wallet_ops.get_platform_stats()


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
