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
    return genai_types.Content(role="model", parts=[genai_types.Part(text=f"<mstat>{text}</mstat>")])


def _channel_key(raw: str) -> str:
    """Normalise a free-form channel value to a canonical platform key."""
    r = raw.lower()
    if "insta" in r:
        return "instagram"
    if "linkedin" in r or "linked-in" in r:
        return "linkedin"
    if "twitter" in r or "tweet" in r or r.strip() == "x":
        return "twitter"
    return ""


def _is_review(task_type: str, goal_nl: str) -> bool:
    """Heuristic: does this task want an existing post reviewed rather than written?"""
    t = f"{task_type} {goal_nl}".lower()
    return any(w in t for w in ("review", "reading", "reader", "critique", "feedback", "evaluate"))


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

    # Route by platform (channel) + role (write vs review). Each candidate skill_id
    # encodes both, e.g. "skill-twitter-writer" / "skill-linkedin-reviewer".
    channel_key = _channel_key(str(spec.get("inputs", {}).get("channel", "")))
    review = _is_review(task_type, node_input.get("goal_nl", ""))

    def _score(card: SkillCard) -> int:
        sid = card.skill_id
        score = 0
        if channel_key and channel_key in sid:
            score += 2                       # right platform matters most
        if sid.endswith("reviewer" if review else "writer"):
            score += 1                       # right role
        return score

    candidates = [registry.get(cid) for cid in candidate_ids]
    chosen: SkillCard | None = max(candidates, key=_score) if candidates else None

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
