"""A2A skill catalog endpoints.

GET /.well-known/skills      → list of SkillCards (M2 done-test)
GET /.well-known/agent-card  → broker's identity (M0 health check: :8002/.well-known/agent-card)
"""
from __future__ import annotations

from fastapi import APIRouter

from broker_server.keys import broker_public_key_dict

router = APIRouter()

# The skill catalog is seeded from app/marketplace/seed.py; the broker_server
# keeps its own copy for the HTTP endpoint (same data, served independently).
_SKILLS: list[dict] = []


def get_skill_catalog() -> list[dict]:
    return _SKILLS


def set_skill_catalog(skills: list[dict]) -> None:
    global _SKILLS
    _SKILLS = skills


def _default_catalog() -> list[dict]:
    """Default seed catalog (broker_server's own copy, mirrors app/marketplace/seed.py)."""
    return [
        {
            "skill_id": "skill-doc-writer",
            "agent_name": "DocWriter",
            "display_name": "Doc Writer",
            "version": "1.0.0",
            "description": (
                "Writes content (tweets, scripts, articles) and saves the result "
                "as a new Google Doc."
            ),
            "specialties": ["doc-writing", "content-writing", "twitter", "social-media"],
            "instruction": (
                "You are DocWriter, a specialist content creator. "
                "Write the requested content and keep tweets under 280 characters."
            ),
            "model": "ollama/gemma2:2b",
            "required_capabilities": [
                {"mcp_server": "gdocs", "tool_name": "create_doc", "why": "Save content as a Google Doc"}
            ],
            "pricing": {"currency": "USD", "base_fee_cents": 50, "completion_fee_cents": 100},
            "public_key": {},   # populated at startup from keys module
            "io": {},
            "reputation": None,
        },
        {
            "skill_id": "skill-doc-reader",
            "agent_name": "DocReader",
            "display_name": "Doc Reader",
            "version": "1.0.0",
            "description": (
                "Reads and summarises the content of an existing Google Doc."
            ),
            "specialties": ["doc-reading", "research", "summarisation"],
            "instruction": (
                "You are DocReader, a specialist document analyst. "
                "Read the provided document and return a concise summary."
            ),
            "model": "ollama/gemma2:2b",
            "required_capabilities": [
                {"mcp_server": "gdocs", "tool_name": "get_doc_content", "why": "Read the source document"}
            ],
            "pricing": {"currency": "USD", "base_fee_cents": 25, "completion_fee_cents": 50},
            "public_key": {},
            "io": {},
            "reputation": None,
        },
    ]


@router.get("/.well-known/skills")
def list_skills() -> list[dict]:
    catalog = get_skill_catalog() or _default_catalog()
    return catalog


@router.get("/.well-known/agent-card")
def get_agent_card() -> dict:
    return {
        "name": "Marvis Broker",
        "description": "Marketplace + hiring broker for Marvis specialist agents.",
        "version": "1.0.0",
        "url": "http://localhost:8002",
        "public_key": broker_public_key_dict(),
        "capabilities": ["skill-catalog", "hiring", "mandate-verification"],
        "protocols": ["A2A", "UCP", "AP2"],
    }
