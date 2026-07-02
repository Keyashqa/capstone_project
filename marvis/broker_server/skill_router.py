"""A2A skill catalog endpoints.

GET /.well-known/skills      → list of SkillCards (M2 done-test)
GET /.well-known/agent-card  → broker's identity (M0 health check: :8002/.well-known/agent-card)
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from broker_server.keys import broker_public_key_dict

router = APIRouter()

# Single source of truth: the same agent-skills/ folder the Marvis app loads from.
# The broker reads it directly (no key material needed — public keys stay empty here).
_SKILLS_DIR = Path(__file__).resolve().parent.parent / "app" / "marketplace" / "agent-skills"

# The skill catalog is seeded from the agent-skills/ folder; the broker_server
# keeps its own copy for the HTTP endpoint (same data, served independently).
_SKILLS: list[dict] = []


def get_skill_catalog() -> list[dict]:
    return _SKILLS


def set_skill_catalog(skills: list[dict]) -> None:
    global _SKILLS
    _SKILLS = skills


def _default_catalog() -> list[dict]:
    """Load the broker's catalog from the shared agent-skills/ folder.

    Mirrors app/marketplace/seed.py so the broker and the orchestrator agree on
    the exact same skill set, pricing, and capabilities.
    """
    if not _SKILLS_DIR.is_dir():
        return []

    catalog: list[dict] = []
    for skill_dir in sorted(_SKILLS_DIR.iterdir()):
        meta_path = skill_dir / "skill.json"
        if not skill_dir.is_dir() or not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        instr_path = skill_dir / "instruction.md"
        instruction = instr_path.read_text(encoding="utf-8").strip() if instr_path.exists() else ""
        catalog.append({
            "skill_id": meta["skill_id"],
            "agent_name": meta["agent_name"],
            "display_name": meta["display_name"],
            "version": meta.get("version", "1.0.0"),
            "description": meta["description"],
            "specialties": meta["specialties"],
            "instruction": instruction,
            "model": meta.get("model", "ollama/gemma2:2b"),
            "required_capabilities": meta["required_capabilities"],
            "pricing": meta["pricing"],
            "public_key": {},   # broker doesn't hold per-skill signing keys
            "io": {},
            "reputation": None,
        })
    return catalog


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
