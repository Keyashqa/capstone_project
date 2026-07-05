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
from app.marketplace.skill_registry import DEFAULT_OWNER_ID, get_owned_registry, get_registry


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
    goal_nl: str = node_input.get("goal_nl", "")

    market_registry = get_registry()
    # Platform candidates (specialty match) ∪ Phase 3 CUSTOM candidates (keyword match
    # on the raw goal). Dedupe by (owner_id, skill_id) so a card matched both ways
    # appears once.
    market_candidates = _dedupe(
        market_registry.find_for_task(task_type, inputs)
        + market_registry.find_custom_matches(goal_nl)
    )
    owned_candidates = _dedupe(get_owned_registry().find_for_task(task_type, inputs))

    if not market_candidates and not owned_candidates:
        return Event(
            output=node_input,
            route="none",
            content=_content(f"No specialist found for task type '{task_type}'."),
        )

    all_candidates = market_candidates + owned_candidates
    # Phase 3: carry (owner_id, skill_id) — the registry is composite-keyed, so a
    # non-"marvis" seller's listing (e.g. alice's) must be resolved WITH its owner
    # in select_specialist, else registry.get defaults to "marvis" and KeyErrors
    # (audit §A-4).
    return Event(
        output={
            **node_input,
            "candidate_skill_ids": [[c.owner_id, c.skill_id] for c in market_candidates],
            "owned_candidate_skill_ids": [[c.owner_id, c.skill_id] for c in owned_candidates],
        },
        route="found",
        content=_content(f"Found {len(all_candidates)} matching specialist(s)"),
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


def _rank_key(card: SkillCard, channel_key: str, review: bool) -> tuple[int, int]:
    """Ranking key: score first, then prefer a real seller LISTING (owner_account
    set) over the platform's unowned stub on a tie (plan3.md §P3-6a). This lets
    alice's listed twitter-writer win the hire over Marvis's unowned twitter-writer
    so the earnings actually flow to the seller. Owned skills (no market
    competitor for their platform in the demo) are unaffected."""
    return (_score(card, channel_key, review), 1 if card.owner_account else 0)


def _ref(entry) -> tuple[str, str]:
    """Unpack a candidate ref [owner_id, skill_id] (Phase 3) or a bare skill_id
    (back-compat / pre-Phase-3 session state) → (skill_id, owner_id)."""
    if isinstance(entry, (list, tuple)):
        owner_id, skill_id = entry
        return skill_id, owner_id
    return entry, DEFAULT_OWNER_ID


def _dedupe(cards: list[SkillCard]) -> list[SkillCard]:
    """Dedupe cards by (owner_id, skill_id), preserving order."""
    seen: set[tuple[str, str]] = set()
    out: list[SkillCard] = []
    for c in cards:
        key = (c.owner_id, c.skill_id)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def _custom_score(card: SkillCard, goal_nl: str) -> int:
    """# of the card's match_keywords that appear (substring) in the task text."""
    g = goal_nl.lower()
    return sum(1 for kw in card.match_keywords if kw.lower() in g)


def _select_output(node_input: dict, chosen: SkillCard, store: str) -> Event:
    """Build the select_specialist success Event for a chosen card."""
    agent_card = AgentCard.from_skill_card(chosen)
    return Event(
        route=store,  # "market" (rent / listed-earns) or "owned" (free, self-issued)
        output={
            **node_input,
            "selected_skill_id": chosen.skill_id,
            "selected_owner_id": chosen.owner_id,
            "skill_store": store,
            "agent_card": agent_card.model_dump(),
            "skill_card": chosen.model_dump(),
        },
        content=_content(
            f"Selected: {chosen.display_name} · base ${chosen.pricing.base_fee_cents / 100:.2f} "
            f"+ completion ${chosen.pricing.completion_fee_cents / 100:.2f}"
        ),
    )


async def select_specialist(node_input: dict[str, Any]) -> Any:
    """Pick the best SkillCard across BOTH stores; route market / owned / gap."""
    spec: dict = node_input.get("spec", {})
    task_type: str = spec.get("type", "")
    market_refs = node_input.get("candidate_skill_ids", [])
    owned_refs = node_input.get("owned_candidate_skill_ids", [])

    market_registry = get_registry()
    owned_registry = get_owned_registry()
    goal_nl: str = node_input.get("goal_nl", "")

    candidates: list[tuple[SkillCard, str]] = (
        [(market_registry.get(sid, oid), "market") for sid, oid in map(_ref, market_refs)]
        + [(owned_registry.get(sid, oid), "owned") for sid, oid in map(_ref, owned_refs)]
    )
    if not candidates:
        return Event(
            output=node_input,
            route="none",
            content=_content("Could not select a specialist."),
        )

    # ── Phase 3: CUSTOM (user-uploaded) skills, matched by free-form keyword ──────
    # A custom skill wins when it matches the task text AND its match is at least as
    # strong as the platform router's (custom_score*2 > platform_score). Platform
    # skills carry no match_keywords, so they never accidentally win a keyword
    # contest — the flagship "write a tweet" (custom_score 0) still routes to the
    # twitter skill, while "draft a cold outreach email" routes to a listed Email
    # Writer that the platform router (score ~0) can't serve.
    custom = [(c, s) for c, s in candidates if c.match_keywords]
    platform = [(c, s) for c, s in candidates if not c.match_keywords]

    # Route by platform (channel) + role (write vs review). Each platform skill_id
    # encodes both, e.g. "skill-twitter-writer" / "skill-linkedin-reviewer".
    channel_key = _channel_key(str(spec.get("inputs", {}).get("channel", "")))
    review = _is_review(task_type, goal_nl)

    platform_best, platform_score = None, -1
    if platform:
        platform_best, platform_store = max(platform, key=lambda p: _rank_key(p[0], channel_key, review))
        platform_score = _score(platform_best, channel_key, review)

    if custom:
        custom_best, custom_store = max(custom, key=lambda p: _custom_score(p[0], goal_nl))
        custom_score = _custom_score(custom_best, goal_nl)
        if custom_score >= 1 and custom_score * 2 > platform_score:
            return _select_output(node_input, custom_best, custom_store)

    # ── Platform routing (twitter/instagram/linkedin × writer/reviewer) ──────────
    if not channel_key:
        return Event(
            output=node_input,
            route="none",
            content=_content("Could not resolve a target platform for this task."),
        )
    if platform_best is None:
        return Event(
            output=node_input,
            route="none",
            content=_content("Could not select a specialist."),
        )

    chosen, store = platform_best, platform_store

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

    return _select_output(node_input, chosen, store)
