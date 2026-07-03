"""Phase 3 payout split — the pure, deterministic money-split arithmetic.

The earnings loop's core rule (plan3.md §P3-4, decisions Q1/Q3):

  LISTED skill (owner_account set):
    base       → 100% owner
    completion → (100 - commission%) owner  /  commission% broker
    i.e. owner_cut = total - commission ; commission floored on the COMMISSION_BASIS
    tranche only (default "completion"), the other leg DERIVED by subtraction.

  UNOWNED skill (owner_account is None):
    base + completion → 100% broker   (there is no seller to pay)

Penny-exact invariant: floor ONE leg (the commission), derive the OTHER by
subtraction, so Σ legs == total_cents for every integer input — escrow always
drains to exactly 0 and settle_escrow's assertion holds. No float touches money.

This module is PURE (no DB, no I/O) so the risky arithmetic is unit-testable in
isolation before any ledger, node, listing, or UI exists (plan3.md §P3-7 M0).
"""
from __future__ import annotations

from app.config import COMMISSION_BASIS, COMMISSION_RATE_BPS

# Ledger destination accounts (arbitrary strings; audit §1). The broker pool is a
# DISTINCT account — never the operator's personal <user_id> wallet (decision #2).
BROKER_ACCOUNT = "broker"

# Ledger `reason` strings, chosen so get_platform_stats can group revenue by them
# (plan3.md §P3-4.4). Broker revenue = SUM(account_id='broker'); commission-only =
# ... AND reason='payout_commission'.
REASON_OWNER = "payout_owner"            # base + owner's share of completion → owner's own wallet
REASON_COMMISSION = "payout_commission"  # broker's commission on a LISTED skill's completion
REASON_BROKER = "payout_broker"          # broker keeps the whole payout of an UNOWNED skill

# One split leg: (destination_account, amount_cents, ledger_reason).
Leg = tuple[str, int, str]


def _commission_cents(base_cents: int, completion_cents: int) -> int:
    """Floored commission on the configured basis tranche (default: completion only)."""
    basis = completion_cents if COMMISSION_BASIS == "completion" else base_cents + completion_cents
    return (basis * COMMISSION_RATE_BPS) // 10000  # FLOOR — the one rounded leg


def compute_split(base_cents: int, completion_cents: int, owner_account: str | None) -> list[Leg]:
    """Split a passing payout of base+completion into balanced escrow→X legs.

    Floors the commission and derives the owner cut by subtraction so the legs
    sum EXACTLY to total_cents. Zero-cent legs are dropped (the ledger's
    CHECK(delta_cents != 0) rejects them; dropping a 0 leg can't change the sum).
    """
    total = base_cents + completion_cents

    if owner_account:  # LISTED — owned by a seller
        commission = _commission_cents(base_cents, completion_cents)
        owner_cut = total - commission  # base(100%) + completion(100% - commission%)
        legs: list[Leg] = [(owner_account, owner_cut, REASON_OWNER)]
        if commission > 0:
            legs.append((BROKER_ACCOUNT, commission, REASON_COMMISSION))
    else:              # UNOWNED — broker keeps everything
        legs = [(BROKER_ACCOUNT, total, REASON_BROKER)]

    legs = [(acct, amt, reason) for acct, amt, reason in legs if amt > 0]
    assert sum(amt for _, amt, _ in legs) == total, (
        f"split legs {legs} do not sum to total {total}"  # zero-sum guard (escrow drains to 0)
    )
    return legs


def base_sweep_leg(base_cents: int, owner_account: str | None) -> Leg | None:
    """The verify-FAIL base sweep (decision Q3).

    Base is the owner's NON-REFUNDABLE hiring fee, so on failure it sweeps 100%
    to the owner (LISTED) or to the broker (UNOWNED) — never refunded, broker
    takes no commission on failed work. This is the leg that drains the base out
    of escrow on the fail path so escrow still settles to 0 (the leg was
    previously implicit/missing — audit §2, plan3.md §P3-4.3).
    """
    if base_cents <= 0:
        return None
    if owner_account:
        return (owner_account, base_cents, REASON_OWNER)
    return (BROKER_ACCOUNT, base_cents, REASON_BROKER)
