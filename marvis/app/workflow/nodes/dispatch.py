"""dispatch_to_specialist + collect_result nodes.

M5: runtime loads skill + runs Gemma (no tools) — returns tweet draft.
M6: runtime uses the lent gdocs tool via the grant_token.
"""
from __future__ import annotations

import asyncio
from typing import Any

from google.adk.events.event import Event
from google.genai import types as genai_types

from app.capability.grant import get_grant_registry
from app.config import DISPATCH_TIMEOUT_SECONDS
from app.marketplace.skill_registry import get_registry
from app.runtime.specialist import run_specialist


def _content(text: str) -> genai_types.Content:
    return genai_types.Content(role="model", parts=[genai_types.Part(text=text)])


async def dispatch_to_specialist(node_input: dict[str, Any]) -> Any:
    """Send task to the single specialist runtime wearing the chosen skill."""
    task_id: str = node_input.get("task_id", "")
    skill_id: str = node_input.get("selected_skill_id", "")
    grant_token: str = node_input.get("grant_token", "")
    spec: dict = node_input.get("spec", {})

    registry = get_registry()
    skill_card = registry.get(skill_id)

    grant_registry = get_grant_registry()
    grant = grant_registry.get_by_token(grant_token)
    if grant is None:
        return Event(
            output=node_input,
            route="dispatch_failed",
            content=_content(f"Grant not found for token. Was grant_capability skipped?"),
        )

    try:
        result = await asyncio.wait_for(
            run_specialist(
                skill_card=skill_card,
                task_spec={**spec, "goal_nl": node_input.get("goal_nl", "")},
                grant=grant,
                grant_registry=grant_registry,
                timeout_seconds=DISPATCH_TIMEOUT_SECONDS,
            ),
            timeout=DISPATCH_TIMEOUT_SECONDS + 5,
        )
    except asyncio.TimeoutError:
        return Event(
            output=node_input,
            route="dispatch_failed",
            content=_content(
                f"Specialist timed out after {DISPATCH_TIMEOUT_SECONDS}s. "
                f"(If Ollama is slow, set DISPATCH_TIMEOUT_SECONDS=180 in marvis/.env)"
            ),
        )
    except PermissionError as exc:
        return Event(
            output=node_input,
            route="dispatch_failed",
            content=_content(f"Permission denied by grant: {exc}"),
        )
    except Exception as exc:
        return Event(
            output=node_input,
            route="dispatch_failed",
            content=_content(f"Specialist error: {exc}"),
        )

    return Event(
        route="dispatched",
        output={
            **node_input,
            "specialist_result": {
                "agent_name": result.agent_name,
                "skill_id": result.skill_id,
                "output": result.output,
                "doc_id": result.doc_id,
                "called_tools": result.called_tools,
            },
        },
        content=_content(
            f"{result.agent_name} completed the task.\n"
            + (f"  Doc created: {result.doc_id}" if result.doc_id else "")
        ),
    )


async def collect_result(node_input: dict[str, Any]) -> Any:
    """Receive and store the specialist result before revoke."""
    result = node_input.get("specialist_result", {})
    output_text = result.get("output", "")
    doc_id = result.get("doc_id")

    summary = f"Result collected from {result.get('agent_name', '?')}:\n\n{output_text[:300]}"
    if doc_id:
        summary += f"\n\n[Doc saved: {doc_id}]"

    return Event(
        output=node_input,
        content=_content(summary),
    )
