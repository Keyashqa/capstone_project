"""Load the marketplace catalog from the agent-skills/ folder.

Each skill lives in its own directory so definitions stay decoupled from code
and the catalog scales without editing one monolithic file:

  agent-skills/<slug>/skill.json     — structured metadata (id, pricing, capabilities…)
  agent-skills/<slug>/instruction.md — the scoped system prompt the runtime loads

The read-vs-write split between skill-doc-reader (get_doc_content only) and
skill-doc-writer (create_doc only) IS the least-privilege scoping demonstration.

Skills are loaded once at startup by seed_catalog() (called from app.agent).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.keys import skill_public_key_dict
from app.marketplace.skill_card import CapabilityRef, SkillCard, SkillPricing
from app.marketplace.skill_registry import get_registry

SKILLS_DIR = Path(__file__).parent / "agent-skills"


def _load_skill_card(skill_dir: Path) -> SkillCard:
    """Build a SkillCard from a skill directory's skill.json + instruction.md."""
    meta = json.loads((skill_dir / "skill.json").read_text(encoding="utf-8"))
    instruction = (skill_dir / "instruction.md").read_text(encoding="utf-8").strip()
    skill_id = meta["skill_id"]

    return SkillCard(
        skill_id=skill_id,
        agent_name=meta["agent_name"],            # deterministic (A10) — drives ledger account
        display_name=meta["display_name"],
        version=meta.get("version", "1.0.0"),
        description=meta["description"],          # used by select_specialist to match the task
        specialties=meta["specialties"],
        instruction=instruction,
        model=meta.get("model", "ollama/gemma2:2b"),
        required_capabilities=[CapabilityRef(**c) for c in meta["required_capabilities"]],
        pricing=SkillPricing(**meta["pricing"]),
        public_key=skill_public_key_dict(skill_id),  # per-skill signing identity (A9)
    )


def seed_catalog() -> None:
    """Register every skill found under agent-skills/ into the in-memory registry.

    Idempotent: skills already present are left untouched, so repeated calls
    (e.g. on module re-import) are safe.
    """
    registry = get_registry()

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir / "skill.json").exists():
            continue
        card = _load_skill_card(skill_dir)
        if not registry.has(card.skill_id):
            registry.register(card)
