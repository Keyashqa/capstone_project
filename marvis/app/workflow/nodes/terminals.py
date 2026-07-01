"""Terminal nodes — all dead-end states in the Marvis workflow.

Includes:
  receipt_terminal        — success: happy path complete
  no_specialist_terminal  — no skill found
  cancelled_terminal      — user cancelled (PIN gate #1)
  hire_invalid_terminal   — CartMandate invalid
  verify_failed           — deterministic checks failed OR payout rejected
  refunded_terminal       — completion fee refunded (after verify_failed)
"""
from __future__ import annotations

import json
from typing import Any

from google.adk.events.event import Event
from google.genai import types as genai_types

CATALOG_ID = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"

_SEP = "=" * 56


def _content(text: str) -> genai_types.Content:
    return genai_types.Content(role="model", parts=[genai_types.Part(text=text)])


def _a2ui(messages: list[dict]) -> genai_types.Content:
    payload = f"<a2ui-json>{json.dumps(messages)}</a2ui-json>"
    return genai_types.Content(role="model", parts=[genai_types.Part(text=payload)])


def _build_receipt_a2ui(
    agent_name: str,
    booking_id: str,
    total_cents: int,
    doc_id: str | None,
    output_preview: str,
    task_id: str,
) -> list[dict]:
    surface_id = f"receipt-{task_id[:8]}"
    card_children = [
        "agent-row", "taskid-row", "booking-row", "divider-2", "amount-row"
    ]
    if doc_id:
        card_children.append("doc-row")

    components: list[dict] = [
        {"id": "root", "component": "Column",
         "children": ["heading", "divider-0", "card", "divider-1", "preview"]},
        {"id": "heading",   "component": "Text", "text": "Task Complete!"},
        {"id": "divider-0", "component": "Divider"},
        {"id": "card",      "component": "Card", "child": "card-inner"},
        {"id": "card-inner","component": "Column", "children": card_children},
        {"id": "agent-row",   "component": "Text", "text": f"Specialist:   {agent_name}"},
        {"id": "taskid-row",  "component": "Text", "text": f"Task ID:      {task_id}"},
        {"id": "booking-row", "component": "Text", "text": f"Booking ID:   {booking_id}"},
        {"id": "divider-2",   "component": "Divider"},
        {"id": "amount-row",  "component": "Text",
         "text": f"Total paid:   ${total_cents / 100:.2f} USD"},
        {"id": "divider-1",   "component": "Divider"},
        {"id": "preview",     "component": "Text",
         "text": f"Output:\n{output_preview[:300]}"},
    ]
    if doc_id:
        components.append(
            {"id": "doc-row", "component": "Text", "text": f"Google Doc:   {doc_id}"}
        )

    return [
        {"version": "v0.9", "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID}},
        {"version": "v0.9", "updateComponents": {"surfaceId": surface_id, "components": components}},
    ]


# ── receipt_terminal ───────────────────────────────────────────────────────────

async def receipt_terminal(node_input: dict[str, Any]) -> Any:
    task_id: str = node_input.get("task_id", "")
    booking_id: str = node_input.get("booking_id", "")
    skill_card: dict = node_input.get("skill_card", {})
    pricing: dict = skill_card.get("pricing", {})
    total_cents: int = (
        pricing.get("base_fee_cents", 0) + pricing.get("completion_fee_cents", 0)
    )
    result: dict = node_input.get("specialist_result", {})
    agent_name: str = result.get("agent_name", skill_card.get("agent_name", "Agent"))
    output: str = result.get("output", "")
    doc_id: str | None = result.get("doc_id")

    return Event(
        output={
            "status": "complete",
            "task_id": task_id,
            "booking_id": booking_id,
            "agent_name": agent_name,
            "total_cents": total_cents,
            "doc_id": doc_id,
            "output": output,
        },
        content=_a2ui(_build_receipt_a2ui(
            agent_name=agent_name,
            booking_id=booking_id,
            total_cents=total_cents,
            doc_id=doc_id,
            output_preview=output,
            task_id=task_id,
        )),
    )


# ── no_specialist_terminal ─────────────────────────────────────────────────────

def no_specialist_terminal(node_input: dict[str, Any]) -> Any:
    spec = node_input.get("spec", {})
    return Event(
        output={"status": "no_specialist"},
        content=_content(
            f"\n{_SEP}\n  NO SPECIALIST AVAILABLE\n{_SEP}\n"
            f"  No skill found for task type '{spec.get('type', '?')}'.\n"
            f"  Try rephrasing your request.\n{_SEP}\n"
        ),
    )


# ── cancelled_terminal ─────────────────────────────────────────────────────────

def cancelled_terminal(node_input: dict[str, Any]) -> Any:
    return Event(
        output={"status": "cancelled"},
        content=_content(
            f"\n{_SEP}\n  HIRE CANCELLED\n{_SEP}\n"
            f"  No payment was made. Start a new chat to try again.\n{_SEP}\n"
        ),
    )


# ── hire_invalid_terminal ──────────────────────────────────────────────────────

def hire_invalid_terminal(node_input: dict[str, Any]) -> Any:
    return Event(
        output={"status": "hire_invalid"},
        content=_content(
            f"\n{_SEP}\n  HIRE FAILED — Invalid CartMandate\n{_SEP}\n"
            f"  The broker's CartMandate failed validation. Please try again.\n{_SEP}\n"
        ),
    )


# ── verify_failed (+ refund path) ─────────────────────────────────────────────

async def verify_failed(node_input: dict[str, Any]) -> Any:
    """Refund the completion fee to user; base is non-refundable."""
    task_id: str = node_input.get("task_id", "")
    user_id: str = node_input.get("user_id", "")
    skill_card: dict = node_input.get("skill_card", {})
    pricing: dict = skill_card.get("pricing", {})
    completion_cents: int = pricing.get("completion_fee_cents", 0)
    verification: dict = node_input.get("verification", {})
    issues = verification.get("issues", [])

    refund_journal = None
    if task_id and user_id and completion_cents > 0:
        try:
            from app.escrow.operations import refund_from_escrow
            refund_journal = await refund_from_escrow(
                task_id=task_id,
                user_id=user_id,
                amount_cents=completion_cents,
                reason="completion_refund",
            )
        except Exception as exc:
            issues.append(f"refund failed: {exc}")

    issue_lines = "\n".join(f"  • {i}" for i in issues) if issues else "  (no details)"

    return Event(
        output={
            **node_input,
            "status": "verify_failed",
            "refund_journal": refund_journal,
        },
        content=_content(
            f"\n{_SEP}\n  VERIFICATION FAILED\n{_SEP}\n"
            f"{issue_lines}\n"
            f"{_SEP}\n"
            + (f"  Completion fee ${completion_cents/100:.2f} refunded.\n" if refund_journal else "")
            + f"{_SEP}\n"
        ),
    )


def refunded_terminal(node_input: dict[str, Any]) -> Any:
    skill_card: dict = node_input.get("skill_card", {})
    pricing: dict = skill_card.get("pricing", {})
    base_cents: int = pricing.get("base_fee_cents", 0)
    completion_cents: int = pricing.get("completion_fee_cents", 0)

    return Event(
        output={"status": "refunded"},
        content=_content(
            f"\n{_SEP}\n  TASK ENDED — PARTIAL REFUND\n{_SEP}\n"
            f"  Base fee (${base_cents/100:.2f}) kept by specialist.\n"
            f"  Completion fee (${completion_cents/100:.2f}) refunded to your wallet.\n"
            f"{_SEP}\n"
        ),
    )
