"""discover_specialists + select_specialist nodes.

M3:
- discover_specialists: fetches SkillCards from the registry (HTTP or in-proc).
  Routes "none" → no_specialist_terminal, "found" → select_specialist.
- select_specialist: rule-based specialty match (avoids LLM on hot path).
  Builds AgentCard from the chosen SkillCard (deterministic agent_name).

Phase 2 (plan2.md §P2-5a): both nodes now query BOTH stores — the marketplace
(rented) registry and Marvis's owned (built, free) registry — and select_specialist
routes the outcome to "market" / "owned" / "gap". A gap exists iff no candidate in
EITHER store scores a platform match (score < 2). This turns yesterday's silent
mis-serve (LinkedIn task → Twitter writer) into an explicit build trigger.
"""
from __future__ import annotations

from typing import Any

from google.adk.events.event import Event
from google.genai import types as genai_types

from app.marketplace.skill_card import AgentCard, SkillCard
from app.marketplace.skill_registry import get_owned_registry, get_registry


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
    """Query BOTH the marketplace and owned SkillRegistries for matching skills."""
    spec: dict = node_input.get("spec", {})
    task_type: str = spec.get("type", "")
    inputs = spec.get("inputs", {})

    market_candidates = get_registry().find_for_task(task_type, inputs)
    owned_candidates = get_owned_registry().find_for_task(task_type, inputs)

    if not market_candidates and not owned_candidates:
        return Event(
            output=node_input,
            route="none",
            content=_content(f"No specialist found for task type '{task_type}'."),
        )

    all_candidates = market_candidates + owned_candidates
    cards_summary = "\n".join(
        f"  • {c.display_name} ({c.skill_id}) — {c.description}" for c in all_candidates
    )
    return Event(
        output={
            **node_input,
            "candidate_skill_ids": [c.skill_id for c in market_candidates],
            "owned_candidate_skill_ids": [c.skill_id for c in owned_candidates],
        },
        route="found",
        content=_content(f"Found {len(all_candidates)} specialist(s):\n{cards_summary}"),
    )


# A gap exists iff no candidate in EITHER store scores a platform match.
# Score components: +2 platform-in-skill_id, +1 role match. See plan2.md §P2-5a.
_GAP_SCORE_THRESHOLD = 2


def _score(card: SkillCard, channel_key: str, review: bool) -> int:
    sid = card.skill_id
    score = 0
    if channel_key and channel_key in sid:
        score += 2                       # right platform matters most
    if sid.endswith("reviewer" if review else "writer"):
        score += 1                       # right role
    return score


async def select_specialist(node_input: dict[str, Any]) -> Any:
    """Pick the best SkillCard across BOTH stores; route market / owned / gap."""
    spec: dict = node_input.get("spec", {})
    task_type: str = spec.get("type", "")
    market_ids: list[str] = node_input.get("candidate_skill_ids", [])
    owned_ids: list[str] = node_input.get("owned_candidate_skill_ids", [])

    market_registry = get_registry()
    owned_registry = get_owned_registry()

    # Route by platform (channel) + role (write vs review). Each candidate skill_id
    # encodes both, e.g. "skill-twitter-writer" / "skill-linkedin-reviewer".
    channel_key = _channel_key(str(spec.get("inputs", {}).get("channel", "")))
    review = _is_review(task_type, node_input.get("goal_nl", ""))

    if not channel_key:
        # Closed platform set (twitter/instagram/linkedin) — intake already
        # resolves it; an unresolved channel here is a routing dead-end, not a
        # gap the builder can fill.
        return Event(
            output=node_input,
            route="none",
            content=_content("Could not resolve a target platform for this task."),
        )

    candidates: list[tuple[SkillCard, str]] = (
        [(market_registry.get(cid), "market") for cid in market_ids]
        + [(owned_registry.get(cid), "owned") for cid in owned_ids]
    )

    if not candidates:
        return Event(
            output=node_input,
            route="none",
            content=_content("Could not select a specialist."),
        )

    chosen, store = max(candidates, key=lambda pair: _score(pair[0], channel_key, review))

    if _score(chosen, channel_key, review) < _GAP_SCORE_THRESHOLD:
        role = "reviewer" if review else "writer"
        return Event(
            route="gap",
            output={**node_input, "gap_platform": channel_key, "gap_role": role},
            content=_content(
                f"Capability gap: no skill in the marketplace or owned library "
                f"covers {channel_key} ({role}). Proposing a build."
            ),
        )

    agent_card = AgentCard.from_skill_card(chosen)

    return Event(
        route=store,  # "market" (rent, pay-per-use) or "owned" (free, self-issued)
        output={
            **node_input,
            "selected_skill_id": chosen.skill_id,
            "skill_store": store,
            "agent_card": agent_card.model_dump(),
            "skill_card": chosen.model_dump(),
        },
        content=_content(
            f"Selected: {chosen.display_name} ({chosen.agent_name}) [{store}]\n"
            f"  Base fee: ${chosen.pricing.base_fee_cents / 100:.2f}  "
            f"Completion fee: ${chosen.pricing.completion_fee_cents / 100:.2f}"
        ),
    )
