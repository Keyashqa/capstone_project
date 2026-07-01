"""dispatch_to_specialist + collect_result nodes.

M5: runtime loads skill + runs Gemma (no tools) — returns tweet draft.
M6: runtime uses the lent gdocs tool via the grant_token.
"""
from __future__ import annotations

import asyncio
from typing import Any

from google.adk.events.event import Event
from google.genai import types as genai_types

import json

from app.capability.grant import get_grant_registry
from app.config import DISPATCH_TIMEOUT_SECONDS
from app.marketplace.skill_registry import get_registry
from app.runtime.specialist import run_specialist

CATALOG_ID = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"


def _a2ui(messages: list[dict]) -> genai_types.Content:
    payload = f"<a2ui-json>{json.dumps(messages)}</a2ui-json>"
    return genai_types.Content(role="model", parts=[genai_types.Part(text=payload)])


def _build_result_card(
    agent_name: str, output: str, doc_id: str | None, task_id: str
) -> list[dict]:
    surface_id = f"result-{task_id[:8]}"
    doc_components: list[dict] = []
    if doc_id:
        doc_components = [
            {"id": "doc-div", "component": "Divider"},
            {"id": "doc-row", "component": "Row", "children": ["doc-icon", "doc-col"],
             "align": "center", "spacing": 8},
            {"id": "doc-icon", "component": "Icon", "name": "doc",
             "style": {"color": "var(--green)"}},
            {"id": "doc-col", "component": "Column", "children": ["doc-lbl", "doc-val"], "spacing": 2},
            {"id": "doc-lbl", "component": "Text", "text": "Saved to Google Docs", "variant": "label"},
            {"id": "doc-val", "component": "Text", "text": "Open it any time from MPay → your payment",
             "variant": "caption", "style": {"color": "var(--green)"}},
        ]
    col_children = ["header-row", "div-1", "output-lbl", "output-text"] + [c["id"] for c in doc_components]
    components: list[dict] = [
        {"id": "root", "component": "Card", "child": "col", "style": {"maxWidth": "480px"}},
        {"id": "col", "component": "Column", "children": col_children, "spacing": 10, "align": "start"},
        {"id": "header-row", "component": "Row", "children": ["agent-icon", "agent-lbl"],
         "align": "center", "spacing": 8},
        {"id": "agent-icon", "component": "Icon", "name": "person",
         "style": {"color": "var(--primary)"}},
        {"id": "agent-lbl", "component": "Text",
         "text": f"{agent_name} completed the task", "variant": "h5"},
        {"id": "div-1", "component": "Divider"},
        {"id": "output-lbl", "component": "Text", "text": "Generated output", "variant": "label"},
        {"id": "output-text", "component": "Text", "text": output[:400],
         "variant": "body",
         "style": {"backgroundColor": "var(--surface)", "borderRadius": "8px",
                   "padding": "10px 12px", "border": "1px solid var(--border-light)"}},
        *doc_components,
    ]
    return [
        {"version": "v0.9", "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID}},
        {"version": "v0.9", "updateComponents": {"surfaceId": surface_id, "components": components}},
    ]


def _content(text: str) -> genai_types.Content:
    return genai_types.Content(role="model", parts=[genai_types.Part(text=f"<mstat>{text}</mstat>")])


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
            f"{result.agent_name} completed the task."
            + ("\n  Saved to Google Docs — details in MPay" if result.doc_id else "")
        ),
    )


async def collect_result(node_input: dict[str, Any]) -> Any:
    """Receive and store the specialist result before revoke."""
    result = node_input.get("specialist_result", {})
    task_id = node_input.get("task_id", "task")
    output_text = result.get("output", "")
    agent_name = result.get("agent_name", "Specialist")
    doc_id = result.get("doc_id")

    return Event(
        output=node_input,
        content=_a2ui(_build_result_card(agent_name, output_text, doc_id, task_id)),
    )
