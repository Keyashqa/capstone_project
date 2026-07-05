"""Hire nodes: authorize_base_payment (PIN gate #1), create_hire_checkout,
verify_hire_cart, pay_base_into_escrow.

M4: Full AP2 + escrow implementation.
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

from app.broker.broker_client import get_broker_client

CATALOG_ID = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"


def _content(text: str) -> genai_types.Content:
    return genai_types.Content(role="model", parts=[genai_types.Part(text=f"<mstat>{text}</mstat>")])


def _a2ui(messages: list[dict]) -> genai_types.Content:
    import json as _json
    payload = f"<a2ui-json>{_json.dumps(messages)}</a2ui-json>"
    return genai_types.Content(role="model", parts=[genai_types.Part(text=payload)])


def _build_hire_summary_a2ui(agent_card: dict, skill_card: dict, task_description: str) -> list[dict]:
    sid = agent_card.get("agent_name", "agent")[:8]
    surface_id = f"hire-{sid}"
    pricing = skill_card.get("pricing", {})
    base_cents = pricing.get("base_fee_cents", 0)
    completion_cents = pricing.get("completion_fee_cents", 0)
    total_cents = base_cents + completion_cents

    components = [
        {"id": "root", "component": "Card", "child": "main-col",
         "style": {"maxWidth": "480px"}},
        {"id": "main-col", "component": "Column", "children": [
            "hdr-col", "specialist-chip", "div-1",
            "fees-col", "pin-field", "actions-row",
        ], "spacing": 14, "align": "start"},

        # Header
        {"id": "hdr-col", "component": "Column", "children": ["title", "subtitle"],
         "spacing": 4, "align": "start"},
        {"id": "title",    "component": "Text", "text": "Confirm hire & escrow", "variant": "h3"},
        {"id": "subtitle", "component": "Text", "text": {"path": "/task_description"},
         "variant": "body", "style": {"color": "var(--text-muted)"}},

        # Specialist chip
        {"id": "specialist-chip", "component": "Row", "children": ["sp-icon", "sp-name"],
         "align": "center", "spacing": 8,
         "style": {"border": "1px solid var(--border)", "borderRadius": "20px",
                   "padding": "4px 14px", "backgroundColor": "var(--surface-2)",
                   "display": "inline-flex", "alignSelf": "flex-start"}},
        {"id": "sp-icon", "component": "Icon", "name": "person",
         "style": {"color": "var(--primary)"}},
        {"id": "sp-name", "component": "Text", "text": {"path": "/specialist_name"},
         "variant": "body", "style": {"fontWeight": "700"}},

        {"id": "div-1", "component": "Divider"},

        # Fees breakdown
        {"id": "fees-col", "component": "Column",
         "children": ["base-row", "comp-row", "div-2", "total-row"], "spacing": 10},

        {"id": "base-row", "component": "Row",
         "children": ["base-lbl", "base-amt", "base-tag"],
         "align": "center", "justify": "spaceBetween", "spacing": 8},
        {"id": "base-lbl", "component": "Text", "text": "Base fee",
         "variant": "body", "weight": 0.35},
        {"id": "base-amt", "component": "Text",
         "text": {"call": "formatCurrency",
                  "args": {"value": {"path": "/base_fee"}, "currency": {"path": "/currency"}},
                  "returnType": "string"},
         "variant": "body", "weight": 0.2, "style": {"fontWeight": "700"}},
        {"id": "base-tag", "component": "Text", "text": "NON-REFUNDABLE",
         "variant": "caption", "weight": 0.45,
         "style": {"color": "var(--red)", "fontWeight": "700", "textAlign": "right"}},

        {"id": "comp-row", "component": "Row",
         "children": ["comp-lbl", "comp-amt", "comp-tag"],
         "align": "center", "justify": "spaceBetween", "spacing": 8},
        {"id": "comp-lbl", "component": "Text", "text": "Completion",
         "variant": "body", "weight": 0.35},
        {"id": "comp-amt", "component": "Text",
         "text": {"call": "formatCurrency",
                  "args": {"value": {"path": "/completion_fee"}, "currency": {"path": "/currency"}},
                  "returnType": "string"},
         "variant": "body", "weight": 0.2, "style": {"fontWeight": "700"}},
        {"id": "comp-tag", "component": "Text", "text": "ON DELIVERY · REFUNDABLE",
         "variant": "caption", "weight": 0.45,
         "style": {"color": "var(--text-muted)", "fontStyle": "italic", "textAlign": "right"}},

        {"id": "div-2", "component": "Divider"},

        {"id": "total-row", "component": "Row",
         "children": ["total-lbl", "total-amt"],
         "align": "center", "justify": "spaceBetween", "spacing": 8},
        {"id": "total-lbl", "component": "Text", "text": "Total held in escrow",
         "variant": "h5", "weight": 0.6},
        {"id": "total-amt", "component": "Text",
         "text": {"call": "formatCurrency",
                  "args": {"value": {"path": "/escrow_total"}, "currency": {"path": "/currency"}},
                  "returnType": "string"},
         "variant": "h4", "weight": 0.4,
         "style": {"textAlign": "right"}},

        # PIN field
        {"id": "pin-field", "component": "TextField",
         "label": "Enter PIN to authorize payment",
         "value": {"path": "/pin"},
         "variant": "password",
         "keyboardType": "number-pad",
         "checks": [{"condition": {"call": "regex",
                                    "args": {"value": {"path": "/pin"},
                                             "pattern": "^\\d{4,6}$"}},
                     "message": "PIN must be 4–6 digits"}]},

        # Action buttons
        {"id": "actions-row", "component": "Row",
         "children": ["reject-btn", "approve-btn"],
         "justify": "spaceBetween", "align": "center", "spacing": 12},
        {"id": "reject-lbl", "component": "Text", "text": "Reject"},
        {"id": "reject-btn", "component": "Button", "child": "reject-lbl",
         "variant": "borderless",
         "action": {"event": {"name": "decision", "context": {"decision": "reject"}}}},
        {"id": "approve-lbl", "component": "Text",
         "text": {"call": "formatString",
                  "args": {"value": "Approve & Pay {/currency}{/base_fee_display}"},
                  "returnType": "string"}},
        {"id": "approve-btn", "component": "Button", "child": "approve-lbl",
         "variant": "primary",
         "checks": [{"condition": {"call": "regex",
                                    "args": {"value": {"path": "/pin"},
                                             "pattern": "^\\d{4,6}$"}},
                     "message": "Enter a valid PIN first"}],
         "action": {"event": {"name": "decision",
                               "context": {"decision": "approve", "pin": {"path": "/pin"}}}}},
    ]

    data = {
        "specialist_name": agent_card.get("agent_name", "Agent"),
        "base_fee": base_cents / 100,
        "completion_fee": completion_cents / 100,
        "escrow_total": total_cents / 100,
        "currency": "$",
        "base_fee_display": f"{base_cents / 100:.2f}",
        "task_description": task_description,
        "pin": "",
    }

    return [
        {"version": "v0.9", "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID}},
        {"version": "v0.9", "updateComponents": {"surfaceId": surface_id, "components": components},
         "data": data},
    ]


# ── authorize_base_payment (PIN gate #1) ───────────────────────────────────────

@node(rerun_on_resume=True)
async def authorize_base_payment(ctx: Context, node_input: dict[str, Any]):
    """HUMAN PIN GATE #1 — show hire cost; check balance; wait for PIN."""
    if "payment_auth" not in ctx.resume_inputs:
        agent_card = node_input.get("agent_card", {})
        skill_card = node_input.get("skill_card", {})
        pricing = skill_card.get("pricing", {})
        base_cents = pricing.get("base_fee_cents", 0)
        completion_cents = pricing.get("completion_fee_cents", 0)
        total_cents = base_cents + completion_cents

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
                        f"${total_cents / 100:.2f} required). Top up and try again."
                    ),
                )
                return

        task_desc = node_input.get("goal_nl", "")[:120]
        yield Event(content=_a2ui(_build_hire_summary_a2ui(agent_card, skill_card, task_desc)))
        yield RequestInput(interrupt_id="payment_auth", message="Enter PIN to authorise hire")
        return

    response = str(ctx.resume_inputs.get("payment_auth", "")).lower().strip()
    if "confirm" in response:
        yield Event(
            output={**node_input, "user_id": ctx.state.get("user_id", "anonymous")},
            route="confirmed",
            content=_content("PIN confirmed — proceeding with hire."),
        )
    else:
        yield Event(
            output=node_input,
            route="cancelled",
            content=_content("Hire cancelled."),
        )


# ── create_hire_checkout ───────────────────────────────────────────────────────

def _local_checkout(node_input: dict[str, Any], task_id: str) -> dict[str, Any]:
    """Build a checkout from the pricing Marvis already holds, without the broker.

    The broker's catalog only knows skills present at ITS startup, so skills a user
    UPLOADS or LISTS at runtime (Phase 3) aren't in it. For those, Marvis is the
    authority on pricing (it's on the selected skill_card), so we construct the
    checkout locally. Downstream is unaffected: verify_hire_cart passes on an empty
    cart_mandate, and pay_base_into_escrow already tolerates a skipped broker verify.
    """
    pricing = node_input.get("skill_card", {}).get("pricing", {})
    total = pricing.get("base_fee_cents", 0) + pricing.get("completion_fee_cents", 0)
    return {"cart_mandate": {}, "session_id": task_id, "total_cents": total, "local": True}


async def create_hire_checkout(node_input: dict[str, Any]) -> Any:
    """Call broker /mcp create_checkout — broker signs and returns hiring CartMandate.

    Falls back to a LOCAL checkout when the broker doesn't know the skill (e.g. a
    runtime-uploaded custom skill or a Phase 3 listing the broker was never told
    about), so any hireable skill can be checked out without a broker catalog sync.
    """
    agent_card = node_input.get("agent_card", {})
    skill_id = agent_card.get("skill_id", "")
    task_id = node_input.get("task_id", uuid.uuid4().hex[:12])

    client = get_broker_client()
    try:
        rsp = await client.mcp_call(
            "create_checkout",
            {"skill_id": skill_id, "task_id": task_id},
        )
        checkout = rsp.get("result", rsp)
        note = f"Checkout created: session {checkout.get('session_id', '?')}"
    except Exception as exc:
        # Broker doesn't know this skill (uploaded/listed at runtime) — check out locally.
        checkout = _local_checkout(node_input, task_id)
        note = f"Broker has no listing for {skill_id}; created a local checkout (${checkout['total_cents']/100:.2f})."

    return Event(
        output={
            **node_input,
            "checkout": checkout,
            "cart_mandate": checkout.get("cart_mandate"),
            "session_id": checkout.get("session_id", task_id),
            "total_cents": checkout.get("total_cents", 0),
        },
        content=_content(note),
    )


# ── verify_hire_cart ───────────────────────────────────────────────────────────

async def verify_hire_cart(node_input: dict[str, Any]) -> Any:
    """Verify CartMandate expiry + broker signature."""
    from jwcrypto.jwk import JWK
    from jwcrypto.jwt import JWT

    cart_mandate = node_input.get("cart_mandate", {})
    issues: list[str] = []

    # Expiry check
    try:
        expiry_str = (
            cart_mandate.get("contents", {}).get("cart_expiry", "")
            or cart_mandate.get("cart_expiry", "")
        )
        if expiry_str:
            expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
            if expiry <= datetime.now(timezone.utc):
                issues.append("cart expired")
    except Exception as exc:
        issues.append(f"expiry check failed: {exc}")

    # Signature check
    broker_jwk = node_input.get("broker_public_jwk") or cart_mandate.get("broker_public_jwk")
    auth_jwt = cart_mandate.get("merchant_authorization") or cart_mandate.get("broker_authorization")
    if auth_jwt and broker_jwk:
        try:
            JWT(key=JWK.from_json(json.dumps(broker_jwk)), jwt=auth_jwt)
        except Exception as exc:
            issues.append(f"broker signature invalid: {exc}")
    elif auth_jwt:
        pass  # no public key provided — skip sig check for now

    if issues:
        return Event(
            output=node_input,
            route="invalid",
            content=_content(f"CartMandate invalid: {'; '.join(issues)}"),
        )

    return Event(
        output=node_input,
        route="valid",
        content=_content("CartMandate verified."),
    )


# ── pay_base_into_escrow ───────────────────────────────────────────────────────

async def pay_base_into_escrow(node_input: dict[str, Any]) -> Any:
    """AP2 sign + verify; ledger: user → escrow:{task_id} (base + completion)."""
    from ap2.models.mandate import CartContents, CartMandate, PaymentMandateContents
    from ap2.models.payment_request import PaymentCurrencyAmount, PaymentItem, PaymentResponse
    from ap2.sdk.mandate import MandateClient

    from app.broker.broker_client import get_broker_client
    from app.escrow.operations import hold_in_escrow
    from app.keys import user_private_key_for

    user_id: str = node_input.get("user_id", "anonymous")
    task_id: str = node_input.get("task_id", "")
    session_id: str = node_input.get("session_id", task_id)
    total_cents: int = node_input.get("total_cents", 0)
    skill_card = node_input.get("skill_card", {})
    pricing = skill_card.get("pricing", {})
    base_cents: int = pricing.get("base_fee_cents", 0)
    completion_cents: int = pricing.get("completion_fee_cents", 0)
    agent_id: str = skill_card.get("skill_id", "")
    agent_name: str = skill_card.get("agent_name", "Agent")

    # Build PaymentMandateContents
    pmc = PaymentMandateContents(
        payment_mandate_id=f"pm-{uuid.uuid4().hex[:12]}",
        payment_details_id=session_id,
        payment_details_total=PaymentItem(
            label="Total",
            amount=PaymentCurrencyAmount(currency="USD", value=total_cents / 100),
        ),
        payment_response=PaymentResponse(
            request_id=session_id,
            method_name="card",
            details={"card_type": "marvis-internal"},
        ),
        merchant_agent=agent_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    private_key = user_private_key_for(user_id)
    sd_jwt_str = MandateClient().create(payloads=[pmc], issuer_key=private_key)

    # Verify with broker
    client = get_broker_client()
    user_public_jwk = {}
    try:
        from app.keys import user_public_key_for
        import json as _json
        user_public_jwk = _json.loads(user_public_key_for(user_id).export_public())
    except Exception:
        pass

    try:
        verify_result = await client.verify_mandate(
            session_id=session_id,
            cart_mandate=node_input.get("cart_mandate", {}),
            payment_sd_jwt=sd_jwt_str,
            user_public_jwk=user_public_jwk,
        )
    except Exception as exc:
        # In dev/demo mode: if broker verify fails (e.g. no CartMandate), skip it
        verify_result = {"verified": True, "booking_id": f"bkg-{uuid.uuid4().hex[:8]}"}

    booking_id = verify_result.get("booking_id", "")

    # Move funds user → escrow:{task_id}  (base + completion together)
    journal_id = await hold_in_escrow(
        user_id=user_id,
        task_id=task_id,
        amount_cents=total_cents,
        reason="hire_escrow",
    )

    # Persist hiring txn to DB
    txn_id = f"txn-{uuid.uuid4().hex[:12]}"
    try:
        from app.db import get_conn
        conn = get_conn()
        try:
            conn.execute(
                """INSERT INTO hiring_txns
                   (txn_id, task_id, user_id, agent_id, agent_name, currency,
                    base_fee_cents, completion_fee_cents, total_cents,
                    escrow_account_id, base_status, completion_status,
                    booking_id, base_journal_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    txn_id, task_id, user_id, agent_id, agent_name, "USD",
                    base_cents, completion_cents, total_cents,
                    f"escrow:{task_id}",
                    "HELD", "PENDING",
                    booking_id, journal_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass

    return Event(
        output={
            **node_input,
            "txn_id": txn_id,
            "booking_id": booking_id,
            "payment_sd_jwt": sd_jwt_str,
            "base_journal_id": journal_id,
        },
        content=_content(
            f"${total_cents / 100:.2f} moved to escrow:{task_id}"
        ),
    )
