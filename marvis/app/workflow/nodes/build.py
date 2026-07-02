"""Phase 2 builder sub-flow nodes (plan2.md §P2-5.0 / §P2-6).

propose_build   — HUMAN PIN GATE #B. Same shape as authorize_base_payment, but
                   commissions the builder (a real marketplace seller) instead
                   of hiring the selected skill directly.
validate_build  — NET-NEW deterministic gate (app.builder.validate) wrapped as
                   a graph node: routes "valid" / "invalid".
persist_skill   — NET-NEW: writes the OWNED folder + registers into Marvis's
                   own registry (never the broker), then restores the
                   ORIGINAL task_id so the free owned-skill run's receipt is
                   keyed correctly, and loops back into discover_specialists.
build_failed    — refunds the build's completion fee (base kept, non-refundable);
                   nothing is persisted.

The build hire is a SEPARATE escrow (`escrow:{build_task_id}`) from the
original task, which never escrows anything — gap-detection fires before any
payment node (plan2.md §P2-5c). `original_task_id` is carried through the
sub-flow so persist_skill can restore it before looping back.
"""
from __future__ import annotations

import json
from typing import Any

from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import node
from google.genai import types as genai_types

from app.builder.persist import persist_skill as _persist_skill
from app.builder.validate import validate_build as _validate_build
from app.marketplace.skill_card import AgentCard, SkillCard
from app.marketplace.skill_registry import get_registry

CATALOG_ID = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"


def _content(text: str) -> genai_types.Content:
    return genai_types.Content(role="model", parts=[genai_types.Part(text=f"<mstat>{text}</mstat>")])


def _a2ui(messages: list[dict]) -> genai_types.Content:
    payload = f"<a2ui-json>{json.dumps(messages)}</a2ui-json>"
    return genai_types.Content(role="model", parts=[genai_types.Part(text=payload)])


def _build_propose_build_a2ui(platform: str, role: str, builder_card: SkillCard) -> list[dict]:
    """Commission-approval PIN card — plan2.md §P2-7 item 1."""
    surface_id = "propose-build"
    pricing = builder_card.pricing
    base_cents = pricing.base_fee_cents
    completion_cents = pricing.completion_fee_cents
    total_cents = base_cents + completion_cents
    platform_title = platform.capitalize()
    role_word = "Writer" if role == "writer" else "Reviewer"

    components = [
        {"id": "root", "component": "Card", "child": "main-col", "style": {"maxWidth": "480px"}},
        {"id": "main-col", "component": "Column", "children": [
            "hdr-col", "gap-chip", "div-1", "fees-col", "pin-field", "actions-row",
        ], "spacing": 14, "align": "start"},

        {"id": "hdr-col", "component": "Column", "children": ["title", "subtitle"], "spacing": 4, "align": "start"},
        {"id": "title", "component": "Text", "text": "No Skill Yet — Commission One?", "variant": "h3"},
        {"id": "subtitle", "component": "Text",
         "text": f"No skill covers {platform_title} yet. Commission a {platform_title}{role_word} "
                 f"you'll OWN? After this, all {platform_title} {role} tasks run FREE forever.",
         "variant": "body", "style": {"color": "var(--text-muted)"}},

        {"id": "gap-chip", "component": "Row", "children": ["gap-icon", "gap-lbl"],
         "align": "center", "spacing": 8,
         "style": {"border": "1px solid var(--border)", "borderRadius": "20px",
                   "padding": "4px 14px", "backgroundColor": "var(--surface-2)",
                   "display": "inline-flex", "alignSelf": "flex-start"}},
        {"id": "gap-icon", "component": "Icon", "name": "build", "style": {"color": "var(--primary)"}},
        {"id": "gap-lbl", "component": "Text", "text": f"Commissioning: {platform_title}{role_word} (via SkillBuilder)",
         "variant": "body", "style": {"fontWeight": "700"}},

        {"id": "div-1", "component": "Divider"},

        {"id": "fees-col", "component": "Column", "children": ["base-row", "comp-row", "div-2", "total-row"], "spacing": 10},
        {"id": "base-row", "component": "Row", "children": ["base-lbl", "base-amt", "base-tag"],
         "align": "center", "justify": "spaceBetween", "spacing": 8},
        {"id": "base-lbl", "component": "Text", "text": "Build base fee", "variant": "body", "weight": 0.35},
        {"id": "base-amt", "component": "Text", "text": f"${base_cents / 100:.2f}",
         "variant": "body", "weight": 0.2, "style": {"fontWeight": "700"}},
        {"id": "base-tag", "component": "Text", "text": "NON-REFUNDABLE", "variant": "caption", "weight": 0.45,
         "style": {"color": "var(--red)", "fontWeight": "700", "textAlign": "right"}},

        {"id": "comp-row", "component": "Row", "children": ["comp-lbl", "comp-amt", "comp-tag"],
         "align": "center", "justify": "spaceBetween", "spacing": 8},
        {"id": "comp-lbl", "component": "Text", "text": "On delivery (valid skill built)", "variant": "body", "weight": 0.35},
        {"id": "comp-amt", "component": "Text", "text": f"${completion_cents / 100:.2f}",
         "variant": "body", "weight": 0.2, "style": {"fontWeight": "700"}},
        {"id": "comp-tag", "component": "Text", "text": "ONE-TIME PURCHASE", "variant": "caption", "weight": 0.45,
         "style": {"color": "var(--text-muted)", "fontStyle": "italic", "textAlign": "right"}},

        {"id": "div-2", "component": "Divider"},
        {"id": "total-row", "component": "Row", "children": ["total-lbl", "total-amt"],
         "align": "center", "justify": "spaceBetween", "spacing": 8},
        {"id": "total-lbl", "component": "Text", "text": "Total held in escrow", "variant": "h5", "weight": 0.6},
        {"id": "total-amt", "component": "Text", "text": f"${total_cents / 100:.2f}",
         "variant": "h4", "weight": 0.4, "style": {"textAlign": "right"}},

        {"id": "pin-field", "component": "TextField", "label": "Enter PIN to authorize the build",
         "value": {"path": "/pin"}, "variant": "password", "keyboardType": "number-pad",
         "checks": [{"condition": {"call": "regex", "args": {"value": {"path": "/pin"}, "pattern": "^\\d{4,6}$"}},
                     "message": "PIN must be 4–6 digits"}]},

        {"id": "actions-row", "component": "Row", "children": ["reject-btn", "approve-btn"],
         "justify": "spaceBetween", "align": "center", "spacing": 12},
        {"id": "reject-lbl", "component": "Text", "text": "Reject"},
        {"id": "reject-btn", "component": "Button", "child": "reject-lbl", "variant": "borderless",
         "action": {"event": {"name": "decision", "context": {"decision": "reject"}}}},
        {"id": "approve-lbl", "component": "Text", "text": f"Approve & Pay ${base_cents / 100:.2f}"},
        {"id": "approve-btn", "component": "Button", "child": "approve-lbl", "variant": "primary",
         "checks": [{"condition": {"call": "regex", "args": {"value": {"path": "/pin"}, "pattern": "^\\d{4,6}$"}},
                     "message": "Enter a valid PIN first"}],
         "action": {"event": {"name": "decision", "context": {"decision": "approve", "pin": {"path": "/pin"}}}}},
    ]

    return [
        {"version": "v0.9", "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID}},
        {"version": "v0.9", "updateComponents": {"surfaceId": surface_id, "components": components}, "data": {"pin": ""}},
    ]


def _build_new_skill_a2ui(card: SkillCard) -> list[dict]:
    """Live "new owned skill appears" surface — plan2.md §P2-7 item 2."""
    surface_id = f"owned-added-{card.skill_id[:12]}"
    components = [
        {"id": "root", "component": "Card", "child": "col", "style": {"maxWidth": "480px", "borderColor": "var(--green)"}},
        {"id": "col", "component": "Column", "children": ["title", "body", "chip"], "spacing": 8, "align": "start"},
        {"id": "title", "component": "Text", "text": "New Owned Skill", "variant": "h3", "style": {"color": "var(--green)"}},
        {"id": "body", "component": "Text",
         "text": f"{card.agent_name} added to your OWNED skill library — Marvis owns it "
                 f"and will handle all future {card.specialties[0]} tasks for free.",
         "variant": "body", "style": {"color": "var(--text-muted)"}},
        {"id": "chip", "component": "Row", "children": ["chip-icon", "chip-lbl"], "align": "center", "spacing": 8,
         "style": {"border": "1px solid var(--green)", "borderRadius": "20px", "padding": "4px 14px",
                   "backgroundColor": "var(--surface-2)", "display": "inline-flex", "alignSelf": "flex-start"}},
        {"id": "chip-icon", "component": "Icon", "name": "check", "style": {"color": "var(--green)"}},
        {"id": "chip-lbl", "component": "Text", "text": card.skill_id, "variant": "caption",
         "style": {"fontFamily": "monospace"}},
    ]
    return [
        {"version": "v0.9", "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID}},
        {"version": "v0.9", "updateComponents": {"surfaceId": surface_id, "components": components}},
    ]


# ── propose_build (PIN gate #B) ────────────────────────────────────────────────

@node(rerun_on_resume=True)
async def propose_build(ctx: Context, node_input: dict[str, Any]):
    """HUMAN PIN GATE #B — commission the builder to fill a genuine capability gap."""
    if "build_auth" not in ctx.resume_inputs:
        platform = node_input.get("gap_platform", "")
        role = node_input.get("gap_role", "writer")
        builder_card = get_registry().get("skill-builder")
        total_cents = builder_card.pricing.base_fee_cents + builder_card.pricing.completion_fee_cents

        user_id = ctx.state.get("user_id")
        if user_id:
            from app import wallet as wallet_ops
            balance = await wallet_ops.get_balance(user_id)
            if balance < total_cents:
                yield Event(
                    output=node_input,
                    route="cancelled",
                    content=_content(
                        f"Insufficient balance (${balance / 100:.2f} available, "
                        f"${total_cents / 100:.2f} required to commission the build). Top up and try again."
                    ),
                )
                return

        yield Event(content=_a2ui(_build_propose_build_a2ui(platform, role, builder_card)))
        yield RequestInput(interrupt_id="build_auth", message="Enter PIN to authorize the build")
        return

    response = str(ctx.resume_inputs.get("build_auth", "")).lower().strip()
    if "confirm" not in response:
        yield Event(
            output=node_input,
            route="cancelled",
            content=_content("Build cancelled — no skill was created, no payment was made."),
        )
        return

    original_task_id: str = node_input.get("task_id", "")
    build_task_id = f"build-{original_task_id}"
    builder_card = get_registry().get("skill-builder")
    agent_card = AgentCard.from_skill_card(builder_card)

    yield Event(
        output={
            **node_input,
            "user_id": ctx.state.get("user_id", "anonymous"),
            "original_task_id": original_task_id,
            "task_id": build_task_id,
            "skill_card": builder_card.model_dump(),
            "agent_card": agent_card.model_dump(),
            "selected_skill_id": builder_card.skill_id,
            "skill_store": "market",
        },
        route="confirmed",
        content=_content("Build PIN confirmed — commissioning SkillBuilder."),
    )


# ── validate_build ──────────────────────────────────────────────────────────────

async def validate_build(node_input: dict[str, Any]) -> Any:
    """Deterministic gate (app.builder.validate) — nothing persists unless this passes."""
    built = node_input.get("built_skill_card")
    card = SkillCard(**built) if built else None
    platform = node_input.get("gap_platform", "")
    role = node_input.get("gap_role", "writer")

    result = _validate_build(card, platform, role)

    if not result.ok:
        return Event(
            output={**node_input, "build_validation_issues": result.issues},
            route="invalid",
            content=_content("Build validation FAILED:\n" + "\n".join(f"  • {i}" for i in result.issues)),
        )

    return Event(
        output=node_input,
        route="valid",
        content=_content("Build validation PASSED — releasing the build completion fee."),
    )


# ── persist_skill ────────────────────────────────────────────────────────────────

async def persist_skill(node_input: dict[str, Any]) -> Any:
    """Write the OWNED folder + register (NO broker refresh); loop back to the original task."""
    built = node_input["built_skill_card"]
    card = SkillCard(**built)
    persisted = _persist_skill(card)

    original_task_id = node_input.get("original_task_id", node_input.get("task_id", ""))

    return Event(
        output={
            **node_input,
            "task_id": original_task_id,  # restore the ORIGINAL task for the free owned-skill run
            "persisted_skill_id": persisted.skill_id,
        },
        content=_a2ui(_build_new_skill_a2ui(persisted)),
    )


# ── build_failed ─────────────────────────────────────────────────────────────────

async def build_failed(node_input: dict[str, Any]) -> Any:
    """Validation failed — refund the build's completion fee (base kept); nothing persisted."""
    task_id: str = node_input.get("task_id", "")  # build_task_id at this point
    user_id: str = node_input.get("user_id", "")
    skill_card: dict = node_input.get("skill_card", {})
    completion_cents: int = skill_card.get("pricing", {}).get("completion_fee_cents", 0)
    issues: list[str] = node_input.get("build_validation_issues", [])

    refund_journal = None
    if task_id and user_id and completion_cents > 0:
        try:
            from app.escrow.operations import refund_from_escrow
            refund_journal = await refund_from_escrow(
                task_id=task_id, user_id=user_id, amount_cents=completion_cents, reason="build_completion_refund",
            )
        except Exception as exc:
            issues = [*issues, f"refund failed: {exc}"]

    issue_text = "; ".join(issues) if issues else "builder output failed validation"
    return Event(
        output={
            **node_input,
            "verification": {"issues": [issue_text]},
            "refund_journal": refund_journal,
        },
        content=_content(f"Build FAILED: {issue_text}\nBuild base fee kept; completion fee refunded."),
    )
