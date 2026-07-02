"""Phase 3 demo seed — real owner accounts + one marketplace listing.

Creates, idempotently and without a signup UI (plan3.md §P3-6c):
  • a real SELLER  "alice"    (users + user_keys + wallet)
  • a real funded  "operator" (the buyer/hirer, topped up)
  • alice's LISTING of a marketplace skill (via app.marketplace.listing.list_skill)

Everything routes through the EXISTING users/wallets/keys tables and the same
ledger — no new auth, no new store. Runs at startup (app.agent import), after
init_db + seed_catalog. A "seller" is simply a users row that appears as an
owner_id in a skill_ownership row.
"""
from __future__ import annotations

from app import wallet
from app.config import (
    DEMO_BUYER_EMAIL,
    DEMO_BUYER_ID,
    DEMO_BUYER_TOPUP_CENTS,
    DEMO_LISTING_SLUG,
    DEMO_PASSWORD,
    DEMO_PIN,
    DEMO_SEED_ENABLED,
    DEMO_SELLER_EMAIL,
    DEMO_SELLER_ID,
)
from app.db import get_conn


def _ensure_user(user_id: str, email: str, password: str, pin: str) -> bool:
    """Create a real user (mirrors auth.register's inserts) with a FIXED id.

    Returns True iff the user was newly created. Idempotent: an existing id or
    email is left untouched. Reuses auth.py's hashing + keypair helpers so a
    seeded account is indistinguishable from a signed-up one (PINs work at both
    gates).
    """
    import uuid

    from app.auth import _generate_user_keypair, _hash_secret

    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE id=? OR email=?", (user_id, email)
        ).fetchone()
        if existing:
            return False

        private_jwk, public_jwk = _generate_user_keypair(user_id)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO users (id, email, password_hash, pin_hash) VALUES (?,?,?,?)",
            (user_id, email, _hash_secret(password), _hash_secret(pin)),
        )
        conn.execute(
            "INSERT INTO user_keys (user_id, private_jwk, public_jwk) VALUES (?,?,?)",
            (user_id, private_jwk, public_jwk),
        )
        conn.execute(
            "INSERT INTO wallets (id, user_id) VALUES (?,?)",
            (uuid.uuid4().hex[:16], user_id),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _topup_sync(user_id: str, amount_cents: int) -> None:
    """Synchronous system → user top-up (double-entry) — safe to call at import
    time where no event loop is running yet."""
    if amount_cents <= 0:
        return
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        wallet._double_entry(conn, wallet.SYSTEM, user_id, amount_cents, "topup", None)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _list_alice_skill() -> None:
    """List the demo slug to the marketplace as alice (promote the flat platform
    card's content under alice's ownership). Idempotent."""
    from app.marketplace.listing import list_skill
    from app.marketplace.seed import SKILLS_DIR, _load_skill_card
    from app.marketplace.skill_registry import get_registry

    src_dir = SKILLS_DIR / DEMO_LISTING_SLUG
    if not (src_dir / "skill.json").exists():
        return  # nothing to promote (fresh checkout without the template)

    skill_id = _load_skill_card(src_dir).skill_id
    if get_registry().has(skill_id, DEMO_SELLER_ID):
        return  # already listed this run / prior run

    # Re-load the template content each time; list_skill re-owns it to alice.
    list_skill(_load_skill_card(src_dir), owner_id=DEMO_SELLER_ID)


def seed_demo() -> None:
    """Idempotent Phase 3 demo bootstrap. No-op if DEMO_SEED_ENABLED is false."""
    if not DEMO_SEED_ENABLED:
        return
    _ensure_user(DEMO_SELLER_ID, DEMO_SELLER_EMAIL, DEMO_PASSWORD, DEMO_PIN)
    buyer_created = _ensure_user(DEMO_BUYER_ID, DEMO_BUYER_EMAIL, DEMO_PASSWORD, DEMO_PIN)
    if buyer_created:
        _topup_sync(DEMO_BUYER_ID, DEMO_BUYER_TOPUP_CENTS)
    _list_alice_skill()
