"""Job receipts — a durable record of what was delivered for each paid task.

A receipt is written at a terminal node (success or refund) and later joined to a
wallet ledger row via task_id (== ledger.reference_id for the escrow hold / refund).
This is what powers the "what did I pay for" detail view in MPay.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.db import get_conn

GDOCS_URL = "https://docs.google.com/document/d/{doc_id}/edit"


def save_job_receipt(node_input: dict[str, Any], status: str) -> None:
    """Upsert a job receipt from the workflow node_input. Never raises."""
    try:
        task_id = node_input.get("task_id")
        if not task_id:
            return

        result: dict = node_input.get("specialist_result", {}) or {}
        skill_card: dict = node_input.get("skill_card", {}) or {}
        agent_card: dict = node_input.get("agent_card", {}) or {}
        pricing: dict = skill_card.get("pricing", {}) or {}
        verification: dict = node_input.get("verification", {}) or {}

        agent_name = (
            result.get("agent_name")
            or skill_card.get("agent_name")
            or agent_card.get("agent_name")
            or "Agent"
        )
        skill_id = skill_card.get("skill_id") or agent_card.get("skill_id") or ""
        base = int(pricing.get("base_fee_cents", 0) or 0)
        comp = int(pricing.get("completion_fee_cents", 0) or 0)
        tools = result.get("called_tools", []) or []
        now = datetime.now(timezone.utc).isoformat()

        conn = get_conn()
        try:
            conn.execute(
                """INSERT INTO job_receipts
                     (task_id, user_id, goal_nl, agent_name, skill_id, booking_id, txn_id,
                      grant_id, doc_id, output, tools_json, verification_json,
                      base_fee_cents, completion_fee_cents, total_cents, status, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(task_id) DO UPDATE SET
                      goal_nl=excluded.goal_nl,
                      agent_name=excluded.agent_name,
                      skill_id=excluded.skill_id,
                      booking_id=excluded.booking_id,
                      txn_id=excluded.txn_id,
                      grant_id=excluded.grant_id,
                      doc_id=excluded.doc_id,
                      output=excluded.output,
                      tools_json=excluded.tools_json,
                      verification_json=excluded.verification_json,
                      base_fee_cents=excluded.base_fee_cents,
                      completion_fee_cents=excluded.completion_fee_cents,
                      total_cents=excluded.total_cents,
                      status=excluded.status,
                      updated_at=excluded.updated_at""",
                (
                    task_id,
                    node_input.get("user_id", ""),
                    (node_input.get("goal_nl", "") or "")[:500],
                    agent_name,
                    skill_id,
                    node_input.get("booking_id", ""),
                    node_input.get("txn_id", ""),
                    node_input.get("grant_id", ""),
                    result.get("doc_id") or "",
                    (result.get("output", "") or "")[:2000],
                    json.dumps(tools),
                    json.dumps(verification),
                    base,
                    comp,
                    base + comp,
                    status,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def _receipt_to_dict(row) -> dict:
    doc_id = row["doc_id"] or None
    try:
        tools = json.loads(row["tools_json"])
    except Exception:
        tools = []
    try:
        verification = json.loads(row["verification_json"])
    except Exception:
        verification = {}
    return {
        "task_id": row["task_id"],
        "goal": row["goal_nl"],
        "agent_name": row["agent_name"],
        "skill_id": row["skill_id"],
        "booking_id": row["booking_id"] or None,
        "txn_id": row["txn_id"] or None,
        "grant_id": row["grant_id"] or None,
        "doc_id": doc_id,
        "doc_url": GDOCS_URL.format(doc_id=doc_id) if doc_id else None,
        "output": row["output"] or "",
        "tools": tools,
        "verification": verification,
        "base_fee_cents": row["base_fee_cents"],
        "completion_fee_cents": row["completion_fee_cents"],
        "total_cents": row["total_cents"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def get_job_receipts_by_task(user_id: str) -> dict[str, dict]:
    """Return {task_id: receipt_dict} for all of a user's job receipts."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM job_receipts WHERE user_id=?", (user_id,)
        ).fetchall()
        return {r["task_id"]: _receipt_to_dict(r) for r in rows}
    finally:
        conn.close()
