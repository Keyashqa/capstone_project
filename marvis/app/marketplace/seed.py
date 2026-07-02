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
from app.marketplace.skill_registry import get_owned_registry, get_registry

SKILLS_DIR = Path(__file__).parent / "agent-skills"

# Marvis's OWNED-skills library — skills the builder has produced and Marvis
# owns outright. Sibling to agent-skills/, but a SEPARATE store: never the
# marketplace, never the broker catalog. See plan2.md §P2-2.
OWNED_SKILLS_DIR = Path(__file__).parent.parent / "owned-skills"


DEFAULT_OWNER_ID = "marvis"


def _load_skill_card(skill_dir: Path, owner_id: str = DEFAULT_OWNER_ID) -> SkillCard:
    """Build a SkillCard from a skill directory's skill.json + instruction.md.

    `owner_id` namespaces the card's registry key, folder, and keypair. It comes
    from the folder layout (owner-namespaced stores) or defaults to "marvis" for
    the current flat marketplace. A skill.json MAY carry its own "owner_id"; the
    on-disk value wins if present, else the passed-in owner_id.
    """
    meta = json.loads((skill_dir / "skill.json").read_text(encoding="utf-8"))
    instruction = (skill_dir / "instruction.md").read_text(encoding="utf-8").strip()
    skill_id = meta["skill_id"]
    owner_id = meta.get("owner_id", owner_id)

    return SkillCard(
        skill_id=skill_id,
        owner_id=owner_id,
        owner_account=meta.get("owner_account"),  # None until LISTED (Phase 3)
        agent_name=meta["agent_name"],            # deterministic (A10) — drives ledger account
        display_name=meta["display_name"],
        version=meta.get("version", "1.0.0"),
        description=meta["description"],          # used by select_specialist to match the task
        specialties=meta["specialties"],
        instruction=instruction,
        model=meta.get("model", "ollama/gemma2:2b"),
        required_capabilities=[CapabilityRef(**c) for c in meta["required_capabilities"]],
        pricing=SkillPricing(**meta["pricing"]),
        public_key=skill_public_key_dict(skill_id, owner_id),  # per-owner signing identity (A9)
    )


def _seed_dir_flat(base_dir: Path, registry, owner_id: str = DEFAULT_OWNER_ID) -> None:
    """Register every `<slug>/skill.json` directly under base_dir, under one owner.

    Used for the current flat marketplace (all implicitly owner "marvis"). Phase 3
    can add an owner-namespaced variant (`<owner_id>/<slug>/`) by looping owner
    dirs and calling this per owner — the seam is already here.
    """
    if not base_dir.exists():
        return
    for skill_dir in sorted(base_dir.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir / "skill.json").exists():
            continue
        card = _load_skill_card(skill_dir, owner_id)
        if not registry.has(card.skill_id, card.owner_id):
            registry.register(card)


def seed_catalog() -> None:
    """Register every skill found under agent-skills/ into the marketplace registry.

    Marketplace is still flat (`agent-skills/<slug>/`), all owner_id="marvis".
    Idempotent: skills already present are left untouched, so repeated calls
    (e.g. on module re-import) are safe.
    """
    _seed_dir_flat(SKILLS_DIR, get_registry(), DEFAULT_OWNER_ID)


def seed_owned_library() -> None:
    """Register every skill under app/owned-skills/<owner_id>/<slug>/ into the OWNED registry.

    Owner-namespaced (audit §A): each top-level entry is an owner directory whose
    children are that owner's skills. Mirrors seed_catalog() but targets the owned
    store (built, permanent, free) rather than the marketplace. Makes skills built
    in a prior run survive a restart. Idempotent, same as seed_catalog().
    """
    registry = get_owned_registry()

    if not OWNED_SKILLS_DIR.exists():
        return

    for owner_dir in sorted(OWNED_SKILLS_DIR.iterdir()):
        if not owner_dir.is_dir():
            continue  # skips stray files like .gitkeep
        _seed_dir_flat(owner_dir, registry, owner_dir.name)
