"""Deterministic validation gate for builder-output SkillCards (plan2.md §P2-3.2 / §P2-5b).

Runs BEFORE persist_skill. Nothing is persisted unless every check passes.
No LLM in this gate — "is this a valid, specialized, existing-tool skill?" is
decided by code, never by trusting Gemma's self-report.
"""
from __future__ import annotations

import re

from app.marketplace.skill_card import SkillCard
from app.marketplace.skill_registry import get_owned_registry, get_registry

_ALLOWED_TOOLS = {"create_doc", "get_doc_content"}
_ROLE_TOOL = {"writer": "create_doc", "reviewer": "get_doc_content"}
_PLATFORM_LIMIT = {"twitter": "280", "instagram": "2200", "linkedin": "3000"}
_SKILL_ID_RE = re.compile(r"^skill-[a-z]+-(writer|reviewer)$")
_AGENT_NAME_RE = re.compile(r"^[A-Za-z]+Post(Specialist|Reviewer)$")
_MIN_INSTRUCTION_LEN = 40


class ValidationResult:
    def __init__(self, ok: bool, issues: list[str]) -> None:
        self.ok = ok
        self.issues = issues


def validate_build(card: SkillCard | None, platform: str, role: str) -> ValidationResult:
    """Validate a builder-produced SkillCard against the gap it was built for.

    `card` may be None — the builder produced no parseable output at all
    (graceful fail per plan2.md §P2-3.2's "re-prompt once, then fail" policy).
    """
    if card is None:
        return ValidationResult(False, ["builder produced no output"])

    issues: list[str] = []

    # 1. skill_id — shape, matches the gap, and not a duplicate in EITHER store
    if not _SKILL_ID_RE.match(card.skill_id):
        issues.append(f"malformed skill_id: {card.skill_id!r}")
    elif get_registry().has(card.skill_id) or get_owned_registry().has(card.skill_id):
        issues.append(f"skill_id already exists: {card.skill_id!r}")
    if platform and role and card.skill_id != f"skill-{platform}-{role}":
        issues.append(f"skill_id {card.skill_id!r} does not match the gap {platform}/{role}")

    # 2. agent_name — <Platform>Post{Specialist,Reviewer} convention, not a duplicate
    if not _AGENT_NAME_RE.match(card.agent_name):
        issues.append(f"agent_name doesn't follow <Platform>Post{{Specialist,Reviewer}}: {card.agent_name!r}")
    existing_names = {c.agent_name for c in get_registry().list_cards()} | {
        c.agent_name for c in get_owned_registry().list_cards()
    }
    if card.agent_name in existing_names:
        issues.append(f"agent_name already exists (possible clone): {card.agent_name!r}")

    # 3. specialties — must target the requested platform + role
    role_token = "post-writing" if role == "writer" else "post-review"
    specialties_lower = [s.lower() for s in card.specialties]
    if platform and platform not in specialties_lower:
        issues.append(f"specialties missing platform token {platform!r}: {card.specialties}")
    if role_token not in specialties_lower:
        issues.append(f"specialties missing role token {role_token!r}: {card.specialties}")

    # 4. instruction — non-trivial, mentions the platform + (for writers) its char limit
    instr_lower = card.instruction.lower()
    if len(card.instruction.strip()) < _MIN_INSTRUCTION_LEN:
        issues.append("instruction too short / likely empty clone")
    if platform and platform not in instr_lower:
        issues.append(f"instruction never mentions the platform {platform!r}")
    limit = _PLATFORM_LIMIT.get(platform)
    if role == "writer" and limit and limit not in card.instruction:
        issues.append(f"instruction never mentions the {platform} character limit ({limit})")

    # 5. required_capabilities — exactly ONE, existing tool only, role-consistent.
    #    This is where a fabricated tool (e.g. post_to_linkedin) is hard-rejected.
    caps = card.required_capabilities
    if len(caps) != 1:
        issues.append(f"required_capabilities must have exactly ONE entry, got {len(caps)}")
    else:
        cap = caps[0]
        if cap.mcp_server != "gdocs":
            issues.append(f"unknown mcp_server: {cap.mcp_server!r}")
        if cap.tool_name not in _ALLOWED_TOOLS:
            issues.append(f"fabricated tool: {cap.tool_name!r} not in {_ALLOWED_TOOLS}")
        expected_tool = _ROLE_TOOL.get(role)
        if expected_tool and cap.tool_name != expected_tool:
            issues.append(f"tool {cap.tool_name!r} inconsistent with role {role!r} (expected {expected_tool!r})")

    # 6. pricing — sane positive ints
    if card.pricing.base_fee_cents <= 0 or card.pricing.completion_fee_cents <= 0:
        issues.append("pricing must have positive base_fee_cents and completion_fee_cents")

    return ValidationResult(len(issues) == 0, issues)
