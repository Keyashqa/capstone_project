"""In-memory skill registry — the marketplace catalog.

Adapted from F1's InMemoryAgentRegistry but stores SkillCards (not ADK agent instances).
Hosts SKILLS, not agents. The single specialist runtime wears whichever skill is selected.
"""
from __future__ import annotations

from app.marketplace.skill_card import SkillCard


DEFAULT_OWNER_ID = "marvis"


class InMemorySkillRegistry:
    """Keyed by the composite ``(owner_id, skill_id)`` so two owners can list the
    same slug without colliding (audit §4). Back-compat: ``get``/``has`` default
    ``owner_id="marvis"``, so every existing caller that passes only a ``skill_id``
    keeps resolving Phase 1/2 skills unchanged.
    """

    def __init__(self) -> None:
        self._skills: dict[tuple[str, str], SkillCard] = {}

    def register(self, card: SkillCard) -> None:
        # The card carries its own owner (defaults to "marvis"); no separate arg needed.
        self._skills[(card.owner_id, card.skill_id)] = card

    def has(self, skill_id: str, owner_id: str = DEFAULT_OWNER_ID) -> bool:
        return (owner_id, skill_id) in self._skills

    def get(self, skill_id: str, owner_id: str = DEFAULT_OWNER_ID) -> SkillCard:
        key = (owner_id, skill_id)
        if key not in self._skills:
            raise KeyError(f"Unknown skill: {skill_id} (owner={owner_id})")
        return self._skills[key]

    def list_cards(self) -> list[SkillCard]:
        return list(self._skills.values())

    def find_by_specialty(self, specialty: str) -> list[SkillCard]:
        """Rule-based specialty match — avoids an LLM call on the hot path (plan §model-routing)."""
        # Normalize both sides: treat hyphens and underscores as equivalent
        s = specialty.lower().replace("_", "-")
        return [
            card for card in self._skills.values()
            if any(s in sp.lower().replace("_", "-") for sp in card.specialties)
            or s in card.description.lower()
        ]

    def find_for_task(self, task_type: str, inputs: dict) -> list[SkillCard]:
        """Select candidates for a task. Returns all cards whose specialties or description match."""
        return self.find_by_specialty(task_type)

    def find_custom_matches(self, goal_nl: str) -> list[SkillCard]:
        """Phase 3: custom (user-uploaded) skills whose match_keywords overlap the
        raw task text. These are matched by free-form keyword rather than the closed
        platform+role router, so a listed 'Email Writer' can be hired for an email
        task. Platform skills (empty match_keywords) are never returned here."""
        g = goal_nl.lower()
        return [
            card for card in self._skills.values()
            if card.match_keywords and any(kw.lower() in g for kw in card.match_keywords)
        ]


# ── Module-level singleton — the MARKETPLACE store (rented/hired skills) ──────
_registry: InMemorySkillRegistry | None = None


def get_registry() -> InMemorySkillRegistry:
    global _registry
    if _registry is None:
        _registry = InMemorySkillRegistry()
    return _registry


# ── Module-level singleton — Marvis's OWNED store (built, permanent, free) ────
# A separate instance of the same class — never conflated with the marketplace
# registry above. Populated by app.marketplace.seed.seed_owned_library() at
# startup and by app.builder.persist.persist_skill() after a successful build.
_owned_registry: InMemorySkillRegistry | None = None


def get_owned_registry() -> InMemorySkillRegistry:
    global _owned_registry
    if _owned_registry is None:
        _owned_registry = InMemorySkillRegistry()
    return _owned_registry
