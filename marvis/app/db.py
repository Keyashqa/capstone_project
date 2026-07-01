"""SQLite database setup for Marvis.

Schema: users + auth + wallet/ledger (from F2) + tasks + hiring_txns + capability_grants.
"""
from __future__ import annotations

import sqlite3

from app.config import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    # ── Identity & auth (verbatim from F2) ───────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            pin_hash      TEXT NOT NULL,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_keys (
            user_id     TEXT PRIMARY KEY REFERENCES users(id),
            private_jwk TEXT NOT NULL,
            public_jwk  TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token      TEXT PRIMARY KEY,
            user_id    TEXT NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS adk_sessions (
            adk_session_id TEXT PRIMARY KEY,
            user_id        TEXT NOT NULL REFERENCES users(id),
            created_at     TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── Wallet (v2 — no balance_cents; balance derived from ledger) ───────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            id         TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
            user_id    TEXT UNIQUE NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── Double-entry ledger (verbatim from F2) ────────────────────────────────
    # Accounts used in Marvis:
    #   "system"              top-ups source
    #   "<user_id>"           owner wallet
    #   "escrow:<task_id>"    funds held during a hire (M1)
    #   "agent:<agent_name>"  specialist earnings; deterministic name (M1)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            id           TEXT PRIMARY KEY,
            journal_id   TEXT NOT NULL,
            account_id   TEXT NOT NULL,
            delta_cents  INTEGER NOT NULL CHECK(delta_cents != 0),
            counterpart  TEXT NOT NULL,
            reason       TEXT NOT NULL,
            reference_id TEXT,
            prev_hash    TEXT NOT NULL,
            entry_hash   TEXT NOT NULL,
            created_at   TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_account ON ledger(account_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_journal ON ledger(journal_id)")

    # ── Tasks (M1) ─────────────────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id           TEXT PRIMARY KEY,
            user_id           TEXT NOT NULL REFERENCES users(id),
            goal_nl           TEXT NOT NULL,
            spec              TEXT,           -- JSON blob (parsed by intake_task)
            selected_skill_id TEXT,
            agent_name        TEXT,
            status            TEXT NOT NULL DEFAULT 'created',
            grant_id          TEXT,
            txn_id            TEXT,
            result            TEXT,           -- JSON blob
            verification      TEXT,           -- JSON blob
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── Hiring transactions / escrow (M1) ──────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hiring_txns (
            txn_id                     TEXT PRIMARY KEY,
            task_id                    TEXT NOT NULL REFERENCES tasks(task_id),
            user_id                    TEXT NOT NULL REFERENCES users(id),
            agent_id                   TEXT NOT NULL,
            agent_name                 TEXT NOT NULL,
            currency                   TEXT NOT NULL DEFAULT 'USD',
            base_fee_cents             INTEGER NOT NULL,
            completion_fee_cents       INTEGER NOT NULL,
            total_cents                INTEGER NOT NULL,
            escrow_account_id          TEXT NOT NULL,      -- "escrow:<task_id>"
            base_status                TEXT NOT NULL DEFAULT 'PENDING',
            completion_status          TEXT NOT NULL DEFAULT 'PENDING',
            cart_mandate               TEXT,               -- JSON
            base_payment_mandate_id    TEXT,
            completion_payment_mandate_id TEXT,
            booking_id                 TEXT,
            base_journal_id            TEXT,
            completion_journal_id      TEXT,
            created_at                 TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at                 TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── Capability grants (M6 — in-memory is live source; DB is audit log) ────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS capability_grants (
            grant_id      TEXT PRIMARY KEY,
            task_id       TEXT NOT NULL REFERENCES tasks(task_id),
            agent_id      TEXT NOT NULL,
            issued_by     TEXT NOT NULL,
            allowed_tools TEXT NOT NULL,   -- JSON array
            limits        TEXT NOT NULL,   -- JSON object
            task_bound    INTEGER NOT NULL DEFAULT 1,
            issued_at     TEXT NOT NULL,
            expires_at    TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'ACTIVE',
            usage         TEXT NOT NULL DEFAULT '{"calls_total":0,"per_tool":{}}',
            grant_token   TEXT NOT NULL UNIQUE,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_grants_token ON capability_grants(grant_token)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_grants_task ON capability_grants(task_id)")

    # ── Job receipts (what was actually delivered for a given payment) ─────────
    # Linked to a wallet ledger row via task_id (== ledger.reference_id for the
    # escrow hold / refund). Powers the "what did I pay for" view in MPay.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_receipts (
            task_id              TEXT PRIMARY KEY,
            user_id              TEXT NOT NULL,
            goal_nl              TEXT,
            agent_name           TEXT,
            skill_id             TEXT,
            booking_id           TEXT,
            txn_id               TEXT,
            grant_id             TEXT,
            doc_id               TEXT,
            output               TEXT,
            tools_json           TEXT NOT NULL DEFAULT '[]',
            verification_json    TEXT NOT NULL DEFAULT '{}',
            base_fee_cents       INTEGER NOT NULL DEFAULT 0,
            completion_fee_cents INTEGER NOT NULL DEFAULT 0,
            total_cents          INTEGER NOT NULL DEFAULT 0,
            status               TEXT NOT NULL DEFAULT 'completed',
            created_at           TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_user ON job_receipts(user_id)")

    conn.commit()
    conn.close()
