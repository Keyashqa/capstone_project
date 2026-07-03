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

from app.db import get_conn, init_db

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
            "owner_id": c.owner_id,
            "is_custom": bool(c.match_keywords),
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


@app.post("/skills/list")
def list_skill_endpoint(body: dict) -> dict:
    """List a marketplace slug under the authenticated caller as its owner (Phase 3).

    The general write-path counterpart to the demo seed (plan3.md §P3-5.1) — a
    single write, no delist/edit CRUD. Promotes the flat template `skill_id`'s
    content under the caller's ownership so future hires earn for them.
    """
    from fastapi import HTTPException

    from app.auth import _get_user_from_token
    from app.marketplace.listing import list_skill
    from app.marketplace.seed import SKILLS_DIR, _load_skill_card

    token = body.get("token", "")
    skill_id = body.get("skill_id", "")
    user = _get_user_from_token(token)  # 401s on a bad/expired token

    slug = skill_id.removeprefix("skill-")
    src_dir = SKILLS_DIR / slug
    if not (src_dir / "skill.json").exists():
        raise HTTPException(status_code=404, detail=f"No template skill '{skill_id}' to list")

    listed = list_skill(_load_skill_card(src_dir), owner_id=user["id"])
    return {
        "skill_id": listed.skill_id,
        "owner_id": listed.owner_id,
        "owner_account": listed.owner_account,
    }


@app.post("/skills/create")
def create_skill_endpoint(body: dict) -> dict:
    """Create + list a CUSTOM skill from user-supplied metadata (Phase 3 upload tab).

    The caller becomes the owner; when someone else hires the skill, the caller
    earns via the payout split. Custom skills are matched to tasks by their
    `match_keywords` (not the closed platform router). The tool is restricted to
    the two real gdocs tools — no fabricated tools (Phase 1/2 invariant).
    """
    import re

    from fastapi import HTTPException

    from app.auth import _get_user_from_token
    from app.marketplace.listing import list_skill
    from app.marketplace.skill_card import CapabilityRef, SkillCard, SkillPricing

    user = _get_user_from_token(body.get("token", ""))  # 401s on bad/expired token

    display_name = str(body.get("display_name", "")).strip()
    description = str(body.get("description", "")).strip()
    instruction = str(body.get("instruction", "")).strip()
    tool_name = str(body.get("tool_name", "")).strip()
    base = int(body.get("base_fee_cents", 0))
    completion = int(body.get("completion_fee_cents", 0))

    raw_kw = body.get("match_keywords", [])
    if isinstance(raw_kw, str):
        raw_kw = raw_kw.split(",")
    keywords = [k.strip() for k in raw_kw if str(k).strip()]

    # ── Validation (fabricated tools + malformed input rejected) ──────────────
    if not display_name or not instruction:
        raise HTTPException(status_code=400, detail="display_name and instruction are required")
    if tool_name not in ("create_doc", "get_doc_content"):
        raise HTTPException(status_code=400, detail="tool_name must be create_doc or get_doc_content")
    if not keywords:
        raise HTTPException(status_code=400, detail="at least one match keyword is required so the skill can be hired")
    if base < 0 or completion < 0 or (base + completion) <= 0:
        raise HTTPException(status_code=400, detail="fees must be non-negative and total more than 0")
    if base > 1_000_000 or completion > 1_000_000:
        raise HTTPException(status_code=400, detail="fee too large")

    slug = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", display_name.lower())).strip("-") or "skill"
    skill_id = f"skill-{slug}"
    agent_name = re.sub(r"[^A-Za-z0-9]+", " ", display_name).title().replace(" ", "") or "CustomSkill"
    why = "save the produced document" if tool_name == "create_doc" else "read the source document"

    card = SkillCard(
        skill_id=skill_id,
        agent_name=agent_name,
        display_name=display_name,
        description=description or display_name,
        specialties=keywords,
        instruction=instruction,
        match_keywords=keywords,
        required_capabilities=[CapabilityRef(mcp_server="gdocs", tool_name=tool_name, why=why)],
        pricing=SkillPricing(base_fee_cents=base, completion_fee_cents=completion),
        public_key={},  # list_skill mints the real per-owner key
    )
    listed = list_skill(card, owner_id=user["id"])
    return {
        "skill_id": listed.skill_id,
        "agent_name": listed.agent_name,
        "owner_id": listed.owner_id,
        "owner_account": listed.owner_account,
        "match_keywords": listed.match_keywords,
    }


@app.get("/skills/contributed")
def contributed_skills(token: str) -> dict:
    """Every skill the authenticated caller has listed to the marketplace —
    whether it's their own custom upload (/skills/create) or a promoted
    owned-skill listing — plus per-skill hire count and lifetime earnings.

    Sourced from the live registry (owner_id == caller), NOT the skill_ownership
    table alone: pre-seeded owner-namespaced fixtures (e.g. the demo listings
    under agent-skills/<owner_id>/) are registered straight from disk at
    startup and never call list_skill(), so they'd have no skill_ownership row.
    listed_at is filled in opportunistically where that row does exist.
    """
    from app.auth import _get_user_from_token
    from app.marketplace.seed import seed_catalog
    from app.marketplace.skill_registry import get_registry
    from app import wallet as wallet_ops

    user = _get_user_from_token(token)  # 401s on a bad/expired token
    seed_catalog()  # idempotent — ensures the registry is populated

    cards = [c for c in get_registry().list_cards() if c.owner_id == user["id"]]
    earnings = wallet_ops.get_skill_earnings(user["id"])

    conn = get_conn()
    try:
        listed_at_by_skill = {
            r["skill_id"]: r["listed_at"]
            for r in conn.execute(
                "SELECT skill_id, listed_at FROM skill_ownership WHERE owner_id=?", (user["id"],)
            ).fetchall()
        }
    finally:
        conn.close()

    skills = [
        {
            "skill_id": c.skill_id,
            "agent_name": c.agent_name,
            "display_name": c.display_name,
            "description": c.description,
            "match_keywords": c.match_keywords,
            "currency": c.pricing.currency,
            "base_fee_cents": c.pricing.base_fee_cents,
            "completion_fee_cents": c.pricing.completion_fee_cents,
            "listed_at": listed_at_by_skill.get(c.skill_id),
            "hires": earnings.get(c.skill_id, {}).get("hires", 0),
            "earned_cents": earnings.get(c.skill_id, {}).get("earned_cents", 0),
        }
        for c in cards
    ]
    skills.sort(key=lambda s: s["earned_cents"], reverse=True)
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
