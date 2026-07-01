"""grant_capability + revoke_capability nodes (§7c-C in-process allowlist).

M6: Mint a CapabilityGrant with exactly ONE allowed tool (from the chosen SkillCard's
    required_capabilities). Register it in InMemoryGrantRegistry.
M7: revoke_capability runs on EVERY exit path from dispatch (success + failure).
    Grant additionally self-expires by TTL — dual safety mechanism.
"""
from __future__ import annotations

from typing import Any

from google.adk.events.event import Event
from google.genai import types as genai_types

from app.capability.grant import AllowedTool, GrantLimits, get_grant_registry
from app.config import GRANT_TTL_SECONDS


def _content(text: str) -> genai_types.Content:
    return genai_types.Content(role="model", parts=[genai_types.Part(text=f"<mstat>{text}</mstat>")])


async def grant_capability(node_input: dict[str, Any]) -> Any:
    """Mint a CapabilityGrant for the chosen skill's ONE required tool."""
    task_id: str = node_input.get("task_id", "")
    skill_card: dict = node_input.get("skill_card", {})
    skill_id: str = skill_card.get("skill_id", "")
    agent_name: str = skill_card.get("agent_name", "Agent")

    required_caps: list[dict] = skill_card.get("required_capabilities", [])
    if not required_caps:
        return Event(
            output=node_input,
            route="grant_failed",
            content=_content("No required_capabilities declared in SkillCard."),
        )

    # Phase 1: exactly ONE capability entry
    cap = required_caps[0]
    tool_name: str = cap.get("tool_name", "")

    # Arg constraints per tool (plan §4.5 / §7c)
    arg_constraints: dict = {}
    if tool_name == "create_doc":
        arg_constraints = {
            "title": 'prefix:"Twitter Scripts — "',
            "content": {"max_len": 4000},
        }
    elif tool_name == "get_doc_content":
        doc_id = node_input.get("spec", {}).get("inputs", {}).get("doc_id", "")
        if doc_id:
            arg_constraints = {"document_id": f"fixed:{doc_id}"}

    allowed_tool = AllowedTool(
        mcp_server=cap.get("mcp_server", "gdocs"),
        tool_name=tool_name,
        arg_constraints=arg_constraints,
    )

    limits = GrantLimits(
        max_calls_total=5,
        max_calls_per_tool={tool_name: 3},
        rate_per_min=10,
    )

    registry = get_grant_registry()
    grant = registry.mint(
        task_id=task_id,
        agent_id=skill_id,
        allowed_tools=[allowed_tool],
        ttl_seconds=GRANT_TTL_SECONDS,
        limits=limits,
    )

    return Event(
        route="granted",
        output={
            **node_input,
            "grant_id": grant.grant_id,
            "grant_token": grant.grant_token,
            "granted_tool": tool_name,
        },
        content=_content(
            f"Capability grant minted: {grant.grant_id}\n"
            f"  Tool: {tool_name} (agent: {agent_name})\n"
            f"  TTL: {GRANT_TTL_SECONDS}s  max_calls: {limits.max_calls_total}"
        ),
    )


async def revoke_capability(node_input: dict[str, Any]) -> Any:
    """Revoke all active grants for this task. Runs on EVERY exit from dispatch."""
    task_id: str = node_input.get("task_id", "")
    count = get_grant_registry().revoke_by_task(task_id)

    return Event(
        output=node_input,
        content=_content(
            f"Capability revoked for task {task_id} ({count} grant(s) revoked). "
            f"Access to specialist closed."
        ),
    )
