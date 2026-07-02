"""list_skill — the Phase 3 "list a skill to the marketplace" write-path.

Listing is a catalog-state write, OUT of the hire graph (plan3.md §P3-5.1). It
promotes a SkillCard into the MARKETPLACE registry under a real owner so that
when someone ELSE hires it, the payout split routes the earnings to that owner
(base 100% + completion 90%) and the broker takes its commission.

Three things happen atomically (plan3.md §P3-6a):
  1. skill_ownership row  — the durable "who listed this + where money goes".
  2. owner_account set + registered into the marketplace registry, keyed by the
     composite (owner_id, skill_id) so two owners can list the same slug.
  3. files written to agent-skills/<owner_id>/<slug>/ so seed_catalog re-loads
     the listing (with owner_id + owner_account) after a restart.

Skill CONTENT stays on disk (skill.json + instruction.md) — the ownership TABLE
only records routing. No second DB, no content-in-DB (audit §A).
"""
from __future__ import annotations

import json

from app.db import get_conn
from app.keys import skill_public_key_dict
from app.marketplace.seed import SKILLS_DIR
from app.marketplace.skill_card import SkillCard
from app.marketplace.skill_registry import get_registry


def owner_account_for(owner_id: str) -> str:
    """The dedicated, non-spendable earnings account a listed skill pays into
    (decision #1). Distinct from the owner's spendable <user_id> wallet."""
    return f"agent:owner:{owner_id}"


def _record_ownership(owner_id: str, skill_id: str, owner_account: str) -> None:
    """Idempotent skill_ownership INSERT (PK (owner_id, skill_id))."""
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """INSERT OR IGNORE INTO skill_ownership (owner_id, skill_id, owner_account)
               VALUES (?, ?, ?)""",
            (owner_id, skill_id, owner_account),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_skill(card: SkillCard, owner_id: str, owner_account: str | None = None) -> SkillCard:
    """List `card` to the marketplace under `owner_id`; return the listed card.

    The listed card is a re-owned copy: owner_id + owner_account set, a per-owner
    signing key minted, registered into the marketplace registry, its files
    written owner-namespaced. Idempotent — re-listing overwrites the same files
    and re-registers (registry.register is an upsert; the ownership row is
    INSERT OR IGNORE).
    """
    owner_account = owner_account or owner_account_for(owner_id)
    slug = card.skill_id.removeprefix("skill-")

    listed = card.model_copy(
        update={
            "owner_id": owner_id,
            "owner_account": owner_account,
            "public_key": skill_public_key_dict(card.skill_id, owner_id),
        }
    )

    skill_dir = SKILLS_DIR / owner_id / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "skill_id": listed.skill_id,
        "owner_id": listed.owner_id,
        "owner_account": listed.owner_account,
        "agent_name": listed.agent_name,
        "display_name": listed.display_name,
        "version": listed.version,
        "description": listed.description,
        "specialties": listed.specialties,
        "model": listed.model,
        "match_keywords": listed.match_keywords,
        "required_capabilities": [c.model_dump() for c in listed.required_capabilities],
        "pricing": listed.pricing.model_dump(),
    }
    (skill_dir / "skill.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (skill_dir / "instruction.md").write_text(listed.instruction.strip() + "\n", encoding="utf-8")

    get_registry().register(listed)
    _record_ownership(owner_id, listed.skill_id, owner_account)
    return listed
