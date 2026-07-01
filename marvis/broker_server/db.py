"""SQLite DB for the broker server (hiring sessions and bookings)."""
from __future__ import annotations

import sqlite3

from broker_server.config import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS hiring_sessions (
        session_id       TEXT PRIMARY KEY,
        skill_id         TEXT NOT NULL,
        task_id          TEXT NOT NULL,
        base_fee_cents   INTEGER NOT NULL,
        completion_fee_cents INTEGER NOT NULL,
        total_cents      INTEGER NOT NULL,
        expires_at       TEXT NOT NULL,
        status           TEXT NOT NULL DEFAULT 'pending',
        cart_mandate_jwt TEXT,
        created_at       TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS hire_bookings (
        id                  TEXT PRIMARY KEY,
        session_id          TEXT NOT NULL REFERENCES hiring_sessions(session_id),
        payment_mandate_jwt TEXT NOT NULL,
        payment_mandate_id  TEXT NOT NULL,
        user_public_jwk     TEXT NOT NULL,
        charged_cents       INTEGER NOT NULL,
        confirmed_at        TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """)
    conn.commit()
    conn.close()
