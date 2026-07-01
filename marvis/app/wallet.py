"""Ledger-based wallet operations (verbatim from F2 ucp-commerce-agent).

Balance is NEVER stored — always derived: SELECT SUM(delta_cents) FROM ledger WHERE account_id=?

Accounts in Marvis extend F2's user/system accounts:
  "system"              top-ups source
  "<user_id>"           owner wallet
  "escrow:<task_id>"    funds held during a hire
  "agent:<agent_name>"  specialist earnings (deterministic name from SkillCard)

Hash chain: every row includes prev_hash + entry_hash (sha256) so tampering is detectable.
Sum of all delta_cents across ALL accounts always equals zero.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from app.db import get_conn

SYSTEM = "system"
GENESIS_HASH = "0" * 64


def _sha256(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _prev_hash(conn, account_id: str) -> str:
    row = conn.execute(
        "SELECT entry_hash FROM ledger WHERE account_id=? ORDER BY rowid DESC LIMIT 1",
        (account_id,),
    ).fetchone()
    return row["entry_hash"] if row else GENESIS_HASH


def _insert_entry(
    conn,
    journal_id: str,
    account_id: str,
    delta_cents: int,
    counterpart: str,
    reason: str,
    reference_id: str | None,
    now: str,
) -> str:
    entry_id = uuid.uuid4().hex
    ph = _prev_hash(conn, account_id)
    entry_hash = _sha256(
        entry_id, journal_id, account_id,
        str(delta_cents), counterpart, reason,
        reference_id or "", now, ph,
    )
    conn.execute(
        """INSERT INTO ledger
               (id, journal_id, account_id, delta_cents, counterpart,
                reason, reference_id, prev_hash, entry_hash, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (entry_id, journal_id, account_id, delta_cents, counterpart,
         reason, reference_id, ph, entry_hash, now),
    )
    return entry_hash


def _double_entry(
    conn,
    debit_account: str,
    credit_account: str,
    amount_cents: int,
    reason: str,
    reference_id: str | None,
) -> str:
    journal_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    _insert_entry(conn, journal_id, debit_account,  -amount_cents, credit_account, reason, reference_id, now)
    _insert_entry(conn, journal_id, credit_account, +amount_cents, debit_account,  reason, reference_id, now)
    return journal_id


def _balance_sync(conn, account_id: str) -> int:
    return conn.execute(
        "SELECT COALESCE(SUM(delta_cents), 0) AS bal FROM ledger WHERE account_id=?",
        (account_id,),
    ).fetchone()["bal"]


# ── Public API ─────────────────────────────────────────────────────────────────

async def get_balance(account_id: str) -> int:
    conn = get_conn()
    try:
        return _balance_sync(conn, account_id)
    finally:
        conn.close()


async def deposit(
    user_id: str,
    amount_cents: int,
    reason: str = "topup",
    reference_id: str | None = None,
) -> int:
    if amount_cents <= 0:
        raise ValueError("deposit amount must be positive")
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _double_entry(conn, SYSTEM, user_id, amount_cents, reason, reference_id)
        conn.commit()
        return _balance_sync(conn, user_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


async def deduct(
    user_id: str,
    amount_cents: int,
    reason: str = "payment",
    reference_id: str | None = None,
) -> int:
    if amount_cents <= 0:
        raise ValueError("deduct amount must be positive")
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        balance = _balance_sync(conn, user_id)
        if balance < amount_cents:
            raise ValueError(
                f"Insufficient funds: balance {balance}¢, need {amount_cents}¢"
            )
        _double_entry(conn, user_id, SYSTEM, amount_cents, reason, reference_id)
        conn.commit()
        return _balance_sync(conn, user_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


async def transfer(
    from_account: str,
    to_account: str,
    amount_cents: int,
    reason: str,
    reference_id: str | None = None,
) -> str:
    """Generic double-entry transfer between any two accounts. Returns journal_id."""
    if amount_cents <= 0:
        raise ValueError("transfer amount must be positive")
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        balance = _balance_sync(conn, from_account)
        if balance < amount_cents:
            raise ValueError(
                f"Insufficient funds in {from_account}: {balance}¢, need {amount_cents}¢"
            )
        journal_id = _double_entry(conn, from_account, to_account, amount_cents, reason, reference_id)
        conn.commit()
        return journal_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_transactions(account_id: str, limit: int = 20) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT id, journal_id, delta_cents, counterpart, reason,
                      reference_id, created_at
               FROM ledger WHERE account_id=? ORDER BY rowid DESC LIMIT ?""",
            (account_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def verify_chain(account_id: str) -> dict:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT id, journal_id, account_id, delta_cents, counterpart, reason,
                      reference_id, prev_hash, entry_hash, created_at
               FROM ledger WHERE account_id=? ORDER BY rowid ASC""",
            (account_id,),
        ).fetchall()

        expected_prev = GENESIS_HASH
        for row in rows:
            if row["prev_hash"] != expected_prev:
                return {
                    "valid": False,
                    "error": f"Chain broken at entry {row['id']}: "
                             f"prev_hash mismatch (expected {expected_prev[:16]}…, "
                             f"got {row['prev_hash'][:16]}…)",
                }
            recomputed = _sha256(
                row["id"], row["journal_id"], row["account_id"],
                str(row["delta_cents"]), row["counterpart"], row["reason"],
                row["reference_id"] or "", row["created_at"], row["prev_hash"],
            )
            if row["entry_hash"] != recomputed:
                return {
                    "valid": False,
                    "error": f"Hash corrupted at entry {row['id']}",
                }
            expected_prev = row["entry_hash"]

        return {"valid": True, "entries": len(rows)}
    finally:
        conn.close()


def get_all_account_sum() -> int:
    """Sum of all delta_cents across all accounts — must always be 0."""
    conn = get_conn()
    try:
        return conn.execute(
            "SELECT COALESCE(SUM(delta_cents), 0) AS total FROM ledger"
        ).fetchone()["total"]
    finally:
        conn.close()
