"""P3-M0/M1 — prove the Phase 3 payout split in isolation.

Uses a throwaway temp SQLite DB (never touches marvis.db). Tests two levels:
  1. compute_split / base_sweep_leg — pure arithmetic (penny-exactness).
  2. pay_completion / verify_failed — real ledger movement through the actual
     nodes: escrow drains to 0, ledger stays zero-sum, money lands where Q1/Q3 say.
"""
from __future__ import annotations

import os
import tempfile
import uuid

# MUST set the DB path + commission config BEFORE importing any app module,
# because app.config reads them at import time.
os.environ["MARVIS_DB_PATH"] = os.path.join(tempfile.mkdtemp(prefix="marvis_split_"), "test.db")
os.environ.setdefault("COMMISSION_RATE_BPS", "1000")   # 10%
os.environ.setdefault("COMMISSION_BASIS", "completion")

import pytest  # noqa: E402

from app.db import init_db  # noqa: E402
from app import wallet  # noqa: E402
from app.escrow.operations import get_escrow_balance, hold_in_escrow  # noqa: E402
from app.escrow.split import (  # noqa: E402
    BROKER_ACCOUNT,
    REASON_BROKER,
    REASON_COMMISSION,
    REASON_OWNER,
    base_sweep_leg,
    compute_split,
)
from app.workflow.nodes.payout import pay_completion  # noqa: E402
from app.workflow.nodes.terminals import verify_failed  # noqa: E402

init_db()


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _skill_card(owner_account, base, completion, owner_id="marvis"):
    return {
        "agent_name": "LinkedinPostSpecialist",
        "owner_id": owner_id,
        "owner_account": owner_account,
        "pricing": {"base_fee_cents": base, "completion_fee_cents": completion},
    }


async def _fund_escrow(buyer: str, task_id: str, total: int) -> None:
    await wallet.deposit(buyer, total, reason="topup")
    await hold_in_escrow(user_id=buyer, task_id=task_id, amount_cents=total)


# ── 1. PURE ARITHMETIC — penny-exactness (no DB) ────────────────────────────────

@pytest.mark.parametrize(
    "base, completion, expected_commission, expected_owner",
    [
        (100, 150, 15, 235),   # clean 10%
        (100, 155, 15, 240),   # ODD: 155*1000//10000 = 15, owner = 255-15
        (100, 151, 15, 236),   # ODD: 151*1000//10000 = 15
        (50, 95, 9, 136),      # ODD: 95*1000//10000 = 9
    ],
)
def test_compute_split_listed_penny_exact(base, completion, expected_commission, expected_owner):
    legs = compute_split(base, completion, "agent:owner:alice")
    total = base + completion
    # exactly two legs, summing to total — no cent leaked or invented
    assert legs == [
        ("agent:owner:alice", expected_owner, REASON_OWNER),
        (BROKER_ACCOUNT, expected_commission, REASON_COMMISSION),
    ]
    assert sum(a for _, a, _ in legs) == total
    assert expected_owner == base + (completion - expected_commission)


def test_compute_split_drops_zero_commission_leg():
    # completion 5¢: 5*1000//10000 = 0 → broker leg dropped, owner keeps all 55¢
    legs = compute_split(50, 5, "agent:owner:alice")
    assert legs == [("agent:owner:alice", 55, REASON_OWNER)]
    assert sum(a for _, a, _ in legs) == 55


def test_compute_split_unowned_all_to_broker():
    legs = compute_split(100, 150, None)
    assert legs == [(BROKER_ACCOUNT, 250, REASON_BROKER)]
    assert sum(a for _, a, _ in legs) == 250


def test_base_sweep_leg():
    assert base_sweep_leg(100, "agent:owner:alice") == ("agent:owner:alice", 100, REASON_OWNER)
    assert base_sweep_leg(100, None) == (BROKER_ACCOUNT, 100, REASON_BROKER)
    assert base_sweep_leg(0, "agent:owner:alice") is None


# ── 2. LEDGER MOVEMENT through the real nodes ───────────────────────────────────

async def test_listed_pass_split():
    """base+90% → agent:owner:<id>, 10% → broker, escrow==0, ledger zero-sum."""
    buyer, owner_id, task_id = _uid("buyer"), _uid("alice"), _uid("t")
    owner_account = f"agent:owner:{owner_id}"
    await _fund_escrow(buyer, task_id, 250)  # base 100 + completion 150

    broker_before = await wallet.get_balance(BROKER_ACCOUNT)
    await pay_completion({"task_id": task_id, "skill_card": _skill_card(owner_account, 100, 150)})

    assert await wallet.get_balance(owner_account) == 235          # 100 + 90% of 150
    assert await wallet.get_balance(BROKER_ACCOUNT) - broker_before == 15  # 10% of 150
    assert await get_escrow_balance(task_id) == 0
    assert wallet.get_all_account_sum() == 0
    assert wallet.verify_chain(owner_account)["valid"]
    assert wallet.verify_chain(BROKER_ACCOUNT)["valid"]


async def test_unowned_pass_all_to_broker():
    """100% (base+completion) → broker, escrow==0."""
    buyer, task_id = _uid("buyer"), _uid("t")
    await _fund_escrow(buyer, task_id, 250)

    broker_before = await wallet.get_balance(BROKER_ACCOUNT)
    await pay_completion({"task_id": task_id, "skill_card": _skill_card(None, 100, 150)})

    assert await wallet.get_balance(BROKER_ACCOUNT) - broker_before == 250
    assert await get_escrow_balance(task_id) == 0
    assert wallet.get_all_account_sum() == 0


async def test_listed_fail_base_sweep():
    """completion → buyer, base → agent:owner:<id>, broker gets nothing, escrow==0."""
    buyer, owner_id, task_id = _uid("buyer"), _uid("alice"), _uid("t")
    owner_account = f"agent:owner:{owner_id}"
    await _fund_escrow(buyer, task_id, 250)  # buyer wallet now 0, escrow 250

    broker_before = await wallet.get_balance(BROKER_ACCOUNT)
    await verify_failed({
        "task_id": task_id, "user_id": buyer,
        "skill_card": _skill_card(owner_account, 100, 150),
        "verification": {"issues": ["forced fail"]},
    })

    assert await wallet.get_balance(buyer) == 150                  # completion refunded
    assert await wallet.get_balance(owner_account) == 100          # non-refundable base swept
    assert await wallet.get_balance(BROKER_ACCOUNT) - broker_before == 0  # no commission on failed work
    assert await get_escrow_balance(task_id) == 0
    assert wallet.get_all_account_sum() == 0


async def test_odd_completion_155_no_leak():
    """Penny-exactness end-to-end on an odd completion (155¢): legs sum exactly."""
    buyer, owner_id, task_id = _uid("buyer"), _uid("alice"), _uid("t")
    owner_account = f"agent:owner:{owner_id}"
    await _fund_escrow(buyer, task_id, 255)  # base 100 + completion 155

    broker_before = await wallet.get_balance(BROKER_ACCOUNT)
    await pay_completion({"task_id": task_id, "skill_card": _skill_card(owner_account, 100, 155)})

    owner_got = await wallet.get_balance(owner_account)
    broker_got = await wallet.get_balance(BROKER_ACCOUNT) - broker_before
    assert owner_got == 240 and broker_got == 15
    assert owner_got + broker_got == 255                          # nothing leaked or invented
    assert await get_escrow_balance(task_id) == 0
    assert wallet.get_all_account_sum() == 0


def test_owner_account_for_is_the_owners_spendable_wallet():
    """Production listing (app.marketplace.listing.owner_account_for) now routes
    earnings into the owner's OWN <user_id> wallet — the same account top-ups
    and hires use — not a separate non-spendable account."""
    from app.marketplace.listing import owner_account_for

    assert owner_account_for("alice") == "alice"


async def test_listed_pass_deposits_into_owner_real_wallet():
    """End-to-end with the PRODUCTION owner_account shape: earnings must show up
    in the same account get_balance()/get_transactions() use for a normal
    wallet — i.e. immediately spendable, immediately visible in MPay."""
    from app.marketplace.listing import owner_account_for

    buyer, owner_id, task_id = _uid("buyer"), _uid("alice"), _uid("t")
    owner_account = owner_account_for(owner_id)
    assert owner_account == owner_id  # sanity: no separate account minted

    owner_before = await wallet.get_balance(owner_id)
    await _fund_escrow(buyer, task_id, 250)  # base 100 + completion 150
    await pay_completion({"task_id": task_id, "skill_card": _skill_card(owner_account, 100, 150, owner_id=owner_id)})

    # The owner's ordinary spendable wallet grew — no cash-out step needed.
    assert await wallet.get_balance(owner_id) - owner_before == 235
    assert await get_escrow_balance(task_id) == 0
    assert wallet.get_all_account_sum() == 0

    txns = wallet.get_transactions(owner_id, limit=5)
    assert any(t["reason"] == REASON_OWNER and t["delta_cents"] == 235 for t in txns)

    # get_platform_stats still finds this owner's earnings (grouped by `reason`
    # now, not by an 'agent:owner:%' account prefix that no longer exists).
    stats = wallet.get_platform_stats()
    owners = {o["owner_id"]: o["earned_cents"] for o in stats["per_owner"]}
    assert owners[owner_id] == 235


async def test_platform_stats_separates_owner_broker_specialist():
    """get_platform_stats groups owner earnings, broker revenue, and legacy
    specialist earnings into DISTINCT buckets (plan3.md §P3-8)."""
    owner_id, task_l, task_u = _uid("alice"), _uid("t"), _uid("t")
    owner_account = f"agent:owner:{owner_id}"

    before = wallet.get_platform_stats()  # temp DB is shared → assert on DELTAS

    # one LISTED hire (owner + commission) and one UNOWNED hire (broker keeps all)
    await _fund_escrow(_uid("b"), task_l, 250)
    await pay_completion({"task_id": task_l, "skill_card": _skill_card(owner_account, 100, 150)})
    await _fund_escrow(_uid("b"), task_u, 250)
    await pay_completion({"task_id": task_u, "skill_card": _skill_card(None, 100, 150)})

    stats = wallet.get_platform_stats()
    # broker delta: 15 (commission on listed) + 250 (full unowned) = 265
    assert stats["broker_revenue_cents"] - before["broker_revenue_cents"] == 265
    assert stats["commission_cents"] - before["commission_cents"] == 15
    # this owner's earnings appear under per_owner (unique id → isolated), NOT per_agent
    owners = {o["owner_id"]: o["earned_cents"] for o in stats["per_owner"]}
    assert owners[owner_id] == 235
    agent_names = {a["agent_name"] for a in stats["per_agent"]}
    assert not any(n.startswith("owner:") for n in agent_names)  # no agent:owner:* leaked in
    assert "broker" not in agent_names  # broker isn't a specialist


async def test_self_hire_nets_minus_commission():
    """buyer == owner, using an owner_account DISTINCT from the principal's own
    wallet id (exercises compute_split's generality — it never assumes
    owner_account == owner_id): spendable wallet pays in, earnings land in the
    distinct account, broker skims 10% — a real -10% move, not a wash. In
    PRODUCTION owner_account == owner_id (see test_owner_account_for_is_the_owners_spendable_wallet),
    so a real self-hire nets the same -10% but through the SAME wallet."""
    principal, task_id = _uid("self"), _uid("t")
    owner_account = f"agent:owner:{principal}"
    await _fund_escrow(principal, task_id, 250)  # principal's spendable wallet → escrow

    broker_before = await wallet.get_balance(BROKER_ACCOUNT)
    await pay_completion({
        "task_id": task_id,
        "skill_card": _skill_card(owner_account, 100, 150, owner_id=principal),
    })

    spendable = await wallet.get_balance(principal)          # 0 — it was fully escrowed
    earnings = await wallet.get_balance(owner_account)       # 235 — separate, non-spendable account
    broker_delta = await wallet.get_balance(BROKER_ACCOUNT) - broker_before
    assert spendable == 0
    assert earnings == 235
    assert broker_delta == 15
    # Net worth across the principal's TWO accounts fell by exactly the 15¢ commission.
    assert spendable + earnings == 250 - 15
    assert wallet.get_all_account_sum() == 0
