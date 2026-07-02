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

from app.receipts import save_job_receipt

CATALOG_ID = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"

_SEP = "=" * 56


def _content(text: str) -> genai_types.Content:
    return genai_types.Content(role="model", parts=[genai_types.Part(text=f"<mstat>{text}</mstat>")])


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
    doc_components: list[dict] = []
    if doc_id:
        doc_components = [
            {"id": "doc-div", "component": "Divider"},
            {"id": "doc-row", "component": "Row", "children": ["doc-icon", "doc-col"],
             "align": "center", "spacing": 10},
            {"id": "doc-icon", "component": "Icon", "name": "doc",
             "style": {"color": "var(--green)", "fontSize": "1.3rem"}},
            {"id": "doc-col", "component": "Column",
             "children": ["doc-lbl", "doc-id"], "spacing": 2},
            {"id": "doc-lbl", "component": "Text", "text": "Google Doc created",
             "variant": "label"},
            {"id": "doc-id",  "component": "Text",
             "text": "Open it from MPay → this payment",
             "variant": "caption", "style": {"color": "var(--green)"}},
        ]

    meta_rows = [
        {"id": "booking-row", "component": "Row",
         "children": ["bkg-lbl", "bkg-val"],
         "align": "center", "justify": "spaceBetween"},
        {"id": "bkg-lbl", "component": "Text", "text": "Booking ID", "variant": "label", "weight": 0.4},
        {"id": "bkg-val", "component": "Text", "text": booking_id,
         "variant": "caption", "weight": 0.6, "style": {"textAlign": "right", "fontFamily": "monospace"}},
        {"id": "agent-row", "component": "Row",
         "children": ["agt-lbl", "agt-val"],
         "align": "center", "justify": "spaceBetween"},
        {"id": "agt-lbl", "component": "Text", "text": "Specialist", "variant": "label", "weight": 0.4},
        {"id": "agt-val", "component": "Text", "text": agent_name,
         "variant": "body", "weight": 0.6,
         "style": {"textAlign": "right", "fontWeight": "700"}},
        {"id": "paid-row", "component": "Row",
         "children": ["paid-lbl", "paid-val"],
         "align": "center", "justify": "spaceBetween"},
        {"id": "paid-lbl", "component": "Text", "text": "Total paid", "variant": "label", "weight": 0.5},
        {"id": "paid-val", "component": "Text", "text": f"${total_cents / 100:.2f} USD",
         "variant": "h4", "weight": 0.5, "style": {"textAlign": "right"}},
    ]

    content_section = [
        {"id": "content-div", "component": "Divider"},
        {"id": "output-lbl", "component": "Text", "text": "Delivered output", "variant": "label"},
        {"id": "output-preview", "component": "Text", "text": output_preview[:300],
         "variant": "body",
         "style": {"backgroundColor": "var(--surface)", "borderRadius": "8px",
                   "padding": "10px 12px", "fontStyle": "italic",
                   "border": "1px solid var(--border-light)", "marginTop": "4px"}},
    ]

    col_children = (
        ["title", "status-row", "div-1"]
        + [c["id"] for c in meta_rows]
        + [c["id"] for c in doc_components]
        + [c["id"] for c in content_section]
    )

    components: list[dict] = [
        {"id": "root", "component": "Card", "child": "main-col",
         "style": {"maxWidth": "480px", "borderColor": "var(--green)"}},
        {"id": "main-col", "component": "Column",
         "children": col_children, "spacing": 10, "align": "start"},
        {"id": "title", "component": "Text", "text": "Task Complete", "variant": "h3",
         "style": {"color": "var(--green)"}},
        {"id": "status-row", "component": "Row", "children": ["check-icon", "status-txt"],
         "align": "center", "spacing": 6},
        {"id": "check-icon", "component": "Icon", "name": "check",
         "style": {"color": "var(--green)"}},
        {"id": "status-txt", "component": "Text",
         "text": "Specialist delivered — payment settled",
         "variant": "body", "style": {"color": "var(--text-muted)"}},
        {"id": "div-1", "component": "Divider"},
        *meta_rows,
        *doc_components,
        *content_section,
    ]

    return [
        {"version": "v0.9", "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID}},
        {"version": "v0.9", "updateComponents": {"surfaceId": surface_id, "components": components}},
    ]


def _build_status_a2ui(surface_id: str, title: str, body: str,
                        color: str = "var(--text-muted)") -> list[dict]:
    """Generic status card for terminals that don't need rich layout."""
    return [
        {"version": "v0.9", "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID}},
        {"version": "v0.9", "updateComponents": {"surfaceId": surface_id, "components": [
            {"id": "root", "component": "Card", "child": "col",
             "style": {"maxWidth": "480px", "borderColor": color}},
            {"id": "col", "component": "Column",
             "children": ["title", "body"], "spacing": 8, "align": "start"},
            {"id": "title", "component": "Text", "text": title, "variant": "h3",
             "style": {"color": color}},
            {"id": "body",  "component": "Text", "text": body,  "variant": "body",
             "style": {"color": "var(--text-muted)"}},
        ]}},
    ]


# ── receipt_terminal ───────────────────────────────────────────────────────────

async def receipt_terminal(node_input: dict[str, Any]) -> Any:
    task_id: str = node_input.get("task_id", "")
    booking_id: str = node_input.get("booking_id", "")
    skill_card: dict = node_input.get("skill_card", {})
    pricing: dict = skill_card.get("pricing", {})
    # Phase 2: an owned-skill run moves no money — nothing was actually paid.
    is_owned: bool = node_input.get("skill_store") == "owned"
    total_cents: int = 0 if is_owned else (
        pricing.get("base_fee_cents", 0) + pricing.get("completion_fee_cents", 0)
    )
    result: dict = node_input.get("specialist_result", {})
    agent_name: str = result.get("agent_name", skill_card.get("agent_name", "Agent"))
    output: str = result.get("output", "")
    doc_id: str | None = result.get("doc_id")

    save_job_receipt(node_input, "completed")

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


# ── output_failed_terminal (Phase 2: owned-skill run, nothing to refund) ───────

def output_failed_terminal(node_input: dict[str, Any]) -> Any:
    """Owned-skill run failed verification. The run was FREE — nothing to refund."""
    verification: dict = node_input.get("verification", {})
    issues = verification.get("issues", [])
    issue_text = "\n".join(f"• {i}" for i in issues) if issues else "No details available."

    save_job_receipt(node_input, "output_failed")

    return Event(
        output={"status": "output_failed"},
        content=_a2ui(_build_status_a2ui(
            "output-failed", "Output Failed Verification",
            issue_text + "\n\nThis was a FREE run on your owned skill — nothing to refund. "
            "You can retry at no cost.",
            color="var(--red)",
        )),
    )


# ── no_specialist_terminal ─────────────────────────────────────────────────────

def no_specialist_terminal(node_input: dict[str, Any]) -> Any:
    spec = node_input.get("spec", {})
    return Event(
        output={"status": "no_specialist"},
        content=_a2ui(_build_status_a2ui(
            "no-specialist", "No Specialist Available",
            f"No skill found for task type '{spec.get('type', '?')}'. "
            f"Try rephrasing your request.",
            color="var(--gold)",
        )),
    )


# ── cancelled_terminal ─────────────────────────────────────────────────────────

def cancelled_terminal(node_input: dict[str, Any]) -> Any:
    return Event(
        output={"status": "cancelled"},
        content=_a2ui(_build_status_a2ui(
            "cancelled", "Hire Cancelled",
            "No payment was made. Start a new chat to try again.",
            color="var(--text-muted)",
        )),
    )


# ── hire_invalid_terminal ──────────────────────────────────────────────────────

def hire_invalid_terminal(node_input: dict[str, Any]) -> Any:
    return Event(
        output={"status": "hire_invalid"},
        content=_a2ui(_build_status_a2ui(
            "hire-invalid", "Hire Failed",
            "The broker's CartMandate failed validation. Please try again.",
            color="var(--red)",
        )),
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

    issue_text = "\n".join(f"• {i}" for i in issues) if issues else "No details available."
    refund_note = (
        f"\n\nCompletion fee ${completion_cents/100:.2f} has been refunded to your wallet."
        if refund_journal else ""
    )

    return Event(
        output={**node_input, "status": "verify_failed", "refund_journal": refund_journal},
        content=_a2ui(_build_status_a2ui(
            f"verify-failed-{task_id[:6]}", "Verification Failed",
            issue_text + refund_note,
            color="var(--red)",
        )),
    )


def refunded_terminal(node_input: dict[str, Any]) -> Any:
    skill_card: dict = node_input.get("skill_card", {})
    pricing: dict = skill_card.get("pricing", {})
    base_cents: int = pricing.get("base_fee_cents", 0)
    completion_cents: int = pricing.get("completion_fee_cents", 0)

    save_job_receipt(node_input, "refunded")

    return Event(
        output={"status": "refunded"},
        content=_a2ui(_build_status_a2ui(
            "refunded", "Task Ended — Partial Refund",
            f"Base fee (${base_cents/100:.2f}) kept by specialist.\n"
            f"Completion fee (${completion_cents/100:.2f}) refunded to your wallet.",
            color="var(--gold)",
        )),
    )
