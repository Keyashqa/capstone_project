"""Escrow operations on top of wallet.py's double-entry ledger.

Marvis escrow accounts:
  "escrow:<task_id>"   — funds held during a hire (base + completion)
  "agent:<agent_name>" — specialist earnings (deterministic name from SkillCard)

Base payment = non-refundable hiring fee (held in escrow, released to agent on completion)
Completion payment = fully refundable if verify fails (released from escrow to agent on pass,
                     or back to user on fail)
"""
from __future__ import annotations

from app import wallet


def escrow_account(task_id: str) -> str:
    return f"escrow:{task_id}"


def agent_account(agent_name: str) -> str:
    return f"agent:{agent_name}"


async def hold_in_escrow(
    user_id: str,
    task_id: str,
    amount_cents: int,
    reason: str = "hire_escrow",
) -> str:
    """Move user → escrow:{task_id}. Returns journal_id."""
    return await wallet.transfer(
        from_account=user_id,
        to_account=escrow_account(task_id),
        amount_cents=amount_cents,
        reason=reason,
        reference_id=task_id,
    )


async def release_to_agent(
    task_id: str,
    agent_name: str,
    amount_cents: int,
    reason: str = "payout",
) -> str:
    """Move escrow:{task_id} → agent:{agent_name}. Returns journal_id."""
    return await wallet.transfer(
        from_account=escrow_account(task_id),
        to_account=agent_account(agent_name),
        amount_cents=amount_cents,
        reason=reason,
        reference_id=task_id,
    )


async def refund_from_escrow(
    task_id: str,
    user_id: str,
    amount_cents: int,
    reason: str = "completion_refund",
) -> str:
    """Move escrow:{task_id} → user (completion refund on verify-fail). Returns journal_id."""
    return await wallet.transfer(
        from_account=escrow_account(task_id),
        to_account=user_id,
        amount_cents=amount_cents,
        reason=reason,
        reference_id=task_id,
    )


async def get_escrow_balance(task_id: str) -> int:
    return await wallet.get_balance(escrow_account(task_id))


async def get_agent_balance(agent_name: str) -> int:
    return await wallet.get_balance(agent_account(agent_name))
