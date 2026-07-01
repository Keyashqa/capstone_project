"""In-memory skill registry — the marketplace catalog.

Adapted from F1's InMemoryAgentRegistry but stores SkillCards (not ADK agent instances).
Hosts SKILLS, not agents. The single specialist runtime wears whichever skill is selected.
"""
from __future__ import annotations

from app.marketplace.skill_card import SkillCard


class InMemorySkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillCard] = {}

    def register(self, card: SkillCard) -> None:
        self._skills[card.skill_id] = card

    def has(self, skill_id: str) -> bool:
        return skill_id in self._skills

    def get(self, skill_id: str) -> SkillCard:
        if skill_id not in self._skills:
            raise KeyError(f"Unknown skill: {skill_id}")
        return self._skills[skill_id]

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


# ── Module-level singleton ─────────────────────────────────────────────────────
_registry: InMemorySkillRegistry | None = None


def get_registry() -> InMemorySkillRegistry:
    global _registry
    if _registry is None:
        _registry = InMemorySkillRegistry()
    return _registry
