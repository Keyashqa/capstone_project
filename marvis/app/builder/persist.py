"""persist_skill — write a validated builder-output SkillCard into Marvis's
OWNED-skills library (permanent) and register it into the owned in-memory
registry (live, so re-selection sees it this run).

Two stores, never conflated (plan2.md §P2-2): this NEVER touches the
marketplace folder (app/marketplace/agent-skills/) or the broker catalog.
Permanence = a filesystem write to app/owned-skills/<slug>/ that
seed_owned_library() re-loads on every future startup.
"""
from __future__ import annotations

import json

from app.keys import skill_public_key_dict
from app.marketplace.seed import OWNED_SKILLS_DIR
from app.marketplace.skill_card import SkillCard
from app.marketplace.skill_registry import get_owned_registry


def persist_skill(card: SkillCard) -> SkillCard:
    """Write `card` to app/owned-skills/<slug>/ and register it into the owned registry.

    Mints the skill's signing keypair here — the public_key on the returned
    card is ALWAYS Marvis-minted, never whatever the model produced (plan2.md
    A9): a model-supplied public_key would be an unverifiable, self-asserted
    identity, so persist_skill overwrites it unconditionally before writing.

    Idempotent: re-persisting the same skill_id overwrites its files and
    re-registers it (registry.register() is an upsert).
    """
    owner_id = card.owner_id  # defaults to "marvis" for builder-produced skills
    slug = card.skill_id.removeprefix("skill-")
    skill_dir = OWNED_SKILLS_DIR / owner_id / slug
    skill_dir.mkdir(parents=True, exist_ok=True)

    card = card.model_copy(update={"public_key": skill_public_key_dict(card.skill_id, owner_id)})

    meta = {
        "skill_id": card.skill_id,
        "owner_id": card.owner_id,
        "owner_account": card.owner_account,
        "agent_name": card.agent_name,
        "display_name": card.display_name,
        "version": card.version,
        "description": card.description,
        "specialties": card.specialties,
        "model": card.model,
        "required_capabilities": [c.model_dump() for c in card.required_capabilities],
        "pricing": card.pricing.model_dump(),
    }
    (skill_dir / "skill.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (skill_dir / "instruction.md").write_text(card.instruction.strip() + "\n", encoding="utf-8")

    get_owned_registry().register(card)
    return card
