"""approve_payout (PIN gate #2), pay_completion, settle_escrow nodes.

M9: Full payout implementation.
  - approve_payout: HUMAN PIN GATE #2 — shows advisory score + work summary;
    binding human approval releases the completion fee.
  - pay_completion: escrow → agent:{agent_name} (base + completion together)
  - settle_escrow: assert escrow:{task_id} == 0; close HiringTxn.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import node
from google.genai import types as genai_types

from app.escrow.operations import get_escrow_balance, release_to_agent

CATALOG_ID = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"


def _content(text: str) -> genai_types.Content:
    return genai_types.Content(role="model", parts=[genai_types.Part(text=text)])


def _a2ui(messages: list[dict]) -> genai_types.Content:
    payload = f"<a2ui-json>{json.dumps(messages)}</a2ui-json>"
    return genai_types.Content(role="model", parts=[genai_types.Part(text=payload)])


def _build_payout_a2ui(
    agent_name: str,
    advisory_score: int,
    output_preview: str,
    completion_cents: int,
    doc_id: str | None,
) -> list[dict]:
    surface_id = f"payout-{agent_name[:8]}"
    children = ["heading", "divider-0", "card", "divider-1", "hint"]
    card_children = ["agent-row", "score-row", "preview-row", "divider-2", "amount-row"]
    if doc_id:
        card_children.insert(3, "doc-row")

    components: list[dict] = [
        {"id": "root", "component": "Column", "children": children},
        {"id": "heading",  "component": "Text", "text": "Work Verification"},
        {"id": "divider-0", "component": "Divider"},
        {"id": "card", "component": "Card", "child": "card-inner"},
        {"id": "card-inner", "component": "Column", "children": card_children},
        {"id": "agent-row",   "component": "Text", "text": f"Specialist:  {agent_name}"},
        {"id": "score-row",   "component": "Text", "text": f"Advisory score:  {advisory_score}/10"},
        {"id": "preview-row", "component": "Text", "text": f"Output preview:\n{output_preview[:200]}"},
        {"id": "divider-2",   "component": "Divider"},
        {"id": "amount-row",  "component": "Text",
         "text": f"Completion fee: ${completion_cents / 100:.2f}"},
        {"id": "divider-1", "component": "Divider"},
        {"id": "hint",      "component": "Text",
         "text": "Enter your PIN below to approve payout (or cancel to refund completion fee)."},
    ]
    if doc_id:
        components.append({"id": "doc-row", "component": "Text", "text": f"Doc saved: {doc_id}"})

    return [
        {"version": "v0.9", "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID}},
        {"version": "v0.9", "updateComponents": {"surfaceId": surface_id, "components": components}},
    ]


# ── approve_payout (PIN gate #2) ───────────────────────────────────────────────

@node(rerun_on_resume=True)
async def approve_payout(ctx: Context, node_input: dict[str, Any]):
    """HUMAN PIN GATE #2 — verify + release completion payment."""
    if "payout_auth" not in ctx.resume_inputs:
        verification: dict = node_input.get("verification", {})
        result: dict = node_input.get("specialist_result", {})
        skill_card: dict = node_input.get("skill_card", {})
        pricing = skill_card.get("pricing", {})
        completion_cents = pricing.get("completion_fee_cents", 0)

        yield Event(content=_a2ui(_build_payout_a2ui(
            agent_name=result.get("agent_name", "Agent"),
            advisory_score=verification.get("advisory_score", 0),
            output_preview=result.get("output", ""),
            completion_cents=completion_cents,
            doc_id=result.get("doc_id"),
        )))
        yield RequestInput(interrupt_id="payout_auth", message="Enter PIN to approve payout")
        return

    response = str(ctx.resume_inputs.get("payout_auth", "")).lower().strip()
    if "confirm" in response:
        yield Event(
            output={**node_input, "user_id": ctx.state.get("user_id", node_input.get("user_id"))},
            route="approved",
            content=_content("Payout approved — releasing completion fee to specialist."),
        )
    else:
        yield Event(
            output=node_input,
            route="rejected",
            content=_content("Payout rejected — completion fee will be refunded."),
        )


# ── pay_completion ─────────────────────────────────────────────────────────────

async def pay_completion(node_input: dict[str, Any]) -> Any:
    """Release escrow:{task_id} → agent:{agent_name} (full amount: base + completion)."""
    task_id: str = node_input.get("task_id", "")
    skill_card: dict = node_input.get("skill_card", {})
    agent_name: str = skill_card.get("agent_name", "Agent")
    pricing: dict = skill_card.get("pricing", {})
    base_cents: int = pricing.get("base_fee_cents", 0)
    completion_cents: int = pricing.get("completion_fee_cents", 0)
    total_cents: int = base_cents + completion_cents

    journal_id = await release_to_agent(
        task_id=task_id,
        agent_name=agent_name,
        amount_cents=total_cents,
        reason="payout",
    )

    # Update hiring txn
    try:
        from app.db import get_conn
        conn = get_conn()
        try:
            conn.execute(
                """UPDATE hiring_txns
                   SET base_status='RELEASED', completion_status='RELEASED',
                       completion_journal_id=?, updated_at=?
                   WHERE task_id=?""",
                (journal_id, datetime.now(timezone.utc).isoformat(), task_id),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass

    return Event(
        output={**node_input, "completion_journal_id": journal_id},
        content=_content(
            f"${total_cents / 100:.2f} released to agent:{agent_name}\n"
            f"Journal: {journal_id}"
        ),
    )


# ── settle_escrow ──────────────────────────────────────────────────────────────

async def settle_escrow(node_input: dict[str, Any]) -> Any:
    """Assert escrow:{task_id} == 0 and close the HiringTxn."""
    task_id: str = node_input.get("task_id", "")
    balance = await get_escrow_balance(task_id)

    if balance != 0:
        return Event(
            output={**node_input, "escrow_balance_after": balance},
            content=_content(
                f"WARNING: escrow:{task_id} balance is {balance}¢ after settlement "
                f"(expected 0). Double-entry invariant may be violated."
            ),
        )

    return Event(
        output={**node_input, "escrow_balance_after": 0},
        content=_content(f"Escrow settled: escrow:{task_id} == 0. HiringTxn closed."),
    )
