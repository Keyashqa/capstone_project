"""CartMandate signing for hire transactions (adapted from F2 checkout.py)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from ap2.models.mandate import CartContents, CartMandate
from ap2.models.payment_request import (
    PaymentCurrencyAmount,
    PaymentDetailsInit,
    PaymentItem,
    PaymentMethodData,
    PaymentRequest,
)
from jwcrypto.jwt import JWT

from broker_server.config import CART_MANDATE_TTL_MINUTES
from broker_server.db import get_conn
from broker_server.keys import broker_private_key


def create_hiring_session(skill_id: str, task_id: str, skill_catalog: list[dict]) -> dict:
    """Create a hiring session and return it with a signed CartMandate."""
    # Find the skill in the catalog
    skill = next((s for s in skill_catalog if s["skill_id"] == skill_id), None)
    if not skill:
        raise ValueError(f"Unknown skill: {skill_id}")

    pricing = skill.get("pricing", {})
    base_cents = pricing.get("base_fee_cents", 0)
    completion_cents = pricing.get("completion_fee_cents", 0)
    total_cents = base_cents + completion_cents

    session_id = f"hire-{uuid.uuid4().hex[:10]}"
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=CART_MANDATE_TTL_MINUTES)).isoformat()

    cart_mandate = _sign_cart_mandate(
        session_id=session_id,
        skill_name=skill.get("display_name", skill_id),
        agent_name=skill.get("agent_name", skill_id),
        task_id=task_id,
        total_cents=total_cents,
        expires_at=expires_at,
    )

    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO hiring_sessions
               (session_id, skill_id, task_id, base_fee_cents, completion_fee_cents,
                total_cents, expires_at, status, cart_mandate_jwt)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (session_id, skill_id, task_id, base_cents, completion_cents,
             total_cents, expires_at, "pending", cart_mandate.merchant_authorization),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "session_id": session_id,
        "skill_id": skill_id,
        "task_id": task_id,
        "base_fee_cents": base_cents,
        "completion_fee_cents": completion_cents,
        "total_cents": total_cents,
        "expires_at": expires_at,
        "cart_mandate": cart_mandate.model_dump(),
        "broker_public_jwk": json.loads(broker_private_key().export_public()),
    }


def _sign_cart_mandate(
    session_id: str,
    skill_name: str,
    agent_name: str,
    task_id: str,
    total_cents: int,
    expires_at: str,
) -> CartMandate:
    display_label = f"Hire {skill_name} for task {task_id}"
    payment_request = PaymentRequest(
        method_data=[PaymentMethodData(supported_methods="card")],
        details=PaymentDetailsInit(
            id=session_id,
            display_items=[
                PaymentItem(
                    label=display_label,
                    amount=PaymentCurrencyAmount(currency="USD", value=total_cents / 100),
                )
            ],
            total=PaymentItem(
                label="Total",
                amount=PaymentCurrencyAmount(currency="USD", value=total_cents / 100),
            ),
        ),
    )

    contents = CartContents(
        id=session_id,
        user_cart_confirmation_required=True,
        payment_request=payment_request,
        cart_expiry=expires_at,
        merchant_name=f"Marvis Broker ({agent_name})",
    )

    jwk = broker_private_key()
    tok = JWT(
        header=json.dumps({"alg": "ES256", "typ": "JWT", "kid": "broker"}),
        claims=json.dumps(contents.model_dump(), default=str),
    )
    tok.make_signed_token(jwk)

    return CartMandate(contents=contents, merchant_authorization=tok.serialize())


def confirm_booking(
    session_id: str,
    payment_mandate_jwt: str,
    payment_mandate_id: str,
    user_public_jwk: dict,
) -> str:
    booking_id = f"bkg-{uuid.uuid4().hex[:12]}"
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT total_cents FROM hiring_sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Session not found: {session_id}")
        charged_cents = row["total_cents"]

        conn.execute(
            "UPDATE hiring_sessions SET status='confirmed' WHERE session_id=?",
            (session_id,),
        )
        conn.execute(
            """INSERT INTO hire_bookings
               (id, session_id, payment_mandate_jwt, payment_mandate_id,
                user_public_jwk, charged_cents)
               VALUES (?,?,?,?,?,?)""",
            (booking_id, session_id, payment_mandate_jwt, payment_mandate_id,
             json.dumps(user_public_jwk), charged_cents),
        )
        conn.commit()
    finally:
        conn.close()
    return booking_id
