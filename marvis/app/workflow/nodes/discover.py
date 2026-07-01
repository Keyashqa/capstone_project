"""discover_specialists + select_specialist nodes.

M3:
- discover_specialists: fetches SkillCards from the registry (HTTP or in-proc).
  Routes "none" → no_specialist_terminal, "found" → select_specialist.
- select_specialist: rule-based specialty match (avoids LLM on hot path).
  Builds AgentCard from the chosen SkillCard (deterministic agent_name).
"""
from __future__ import annotations

from typing import Any

from google.adk.events.event import Event
from google.genai import types as genai_types

from app.marketplace.skill_card import AgentCard, SkillCard
from app.marketplace.skill_registry import get_registry


def _content(text: str) -> genai_types.Content:
    return genai_types.Content(role="model", parts=[genai_types.Part(text=text)])


async def discover_specialists(node_input: dict[str, Any]) -> Any:
    """Query the in-process SkillRegistry for skills matching this task."""
    spec: dict = node_input.get("spec", {})
    task_type: str = spec.get("type", "")

    registry = get_registry()
    candidates = registry.find_for_task(task_type, spec.get("inputs", {}))

    if not candidates:
        return Event(
            output=node_input,
            route="none",
            content=_content(f"No specialist found for task type '{task_type}'."),
        )

    cards_summary = "\n".join(
        f"  • {c.display_name} ({c.skill_id}) — {c.description}" for c in candidates
    )
    return Event(
        output={**node_input, "candidate_skill_ids": [c.skill_id for c in candidates]},
        route="found",
        content=_content(f"Found {len(candidates)} specialist(s):\n{cards_summary}"),
    )


async def select_specialist(node_input: dict[str, Any]) -> Any:
    """Pick the best SkillCard and build the AgentCard (deterministic agent_name)."""
    spec: dict = node_input.get("spec", {})
    task_type: str = spec.get("type", "")
    candidate_ids: list[str] = node_input.get("candidate_skill_ids", [])

    registry = get_registry()

    # Prefer the most specific match; for Phase 1 this is straightforward:
    # doc_writing → skill-doc-writer, doc_reading → skill-doc-reader
    chosen: SkillCard | None = None
    for skill_id in candidate_ids:
        card = registry.get(skill_id)
        if task_type in ("doc_writing", "content_writing") and "write" in skill_id:
            chosen = card
            break
        if task_type in ("doc_reading", "research") and "read" in skill_id:
            chosen = card
            break

    # Fallback: pick first candidate
    if chosen is None and candidate_ids:
        chosen = registry.get(candidate_ids[0])

    if chosen is None:
        return Event(
            output=node_input,
            route="none",
            content=_content("Could not select a specialist."),
        )

    agent_card = AgentCard.from_skill_card(chosen)

    return Event(
        route="selected",
        output={
            **node_input,
            "selected_skill_id": chosen.skill_id,
            "agent_card": agent_card.model_dump(),
            "skill_card": chosen.model_dump(),
        },
        content=_content(
            f"Selected: {chosen.display_name} ({chosen.agent_name})\n"
            f"  Base fee: ${chosen.pricing.base_fee_cents / 100:.2f}  "
            f"Completion fee: ${chosen.pricing.completion_fee_cents / 100:.2f}"
        ),
    )
