"""Capability grant — the in-process allowlist (§7c-C, M6).

A CapabilityGrant declares which ONE MCP tool a specialist may call during a specific task,
subject to TTL, usage caps, and argument constraints.

The InMemoryGrantRegistry is the live authority. The DB table (capability_grants) is the
audit log — written at mint/revoke time.

Phase 1: exactly ONE allowed_tool per grant. The read-vs-write split of the two gdocs tools
is itself the scoping demonstration (DocReader gets get_doc_content ONLY; DocWriter gets
create_doc ONLY).
"""
from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel


class GrantStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    CONSUMED = "CONSUMED"


class AllowedTool(BaseModel):
    mcp_server: str    # "gdocs"
    tool_name: str     # "create_doc" | "get_doc_content"
    arg_constraints: dict[str, Any] = {}


class GrantLimits(BaseModel):
    max_calls_total: int = 5
    max_calls_per_tool: dict[str, int] = {}
    rate_per_min: int = 10


class CapabilityGrant(BaseModel):
    grant_id: str
    task_id: str
    agent_id: str       # skill_id of the grantee
    issued_by: str      # "marvis"
    allowed_tools: list[AllowedTool]    # Phase 1: exactly ONE
    limits: GrantLimits
    task_bound: bool = True
    issued_at: str
    expires_at: str
    status: GrantStatus = GrantStatus.ACTIVE
    usage: dict[str, Any] = {"calls_total": 0, "per_tool": {}}
    grant_token: str    # opaque secret; NOT a credential — just a capability handle


class InMemoryGrantRegistry:
    """Live authority for capability grants.

    The specialist presents grant_token to check_and_use; the registry enforces:
    - grant ACTIVE
    - not past expires_at (TTL)
    - tool_name in allowed_tools
    - caps not exceeded
    - arg constraints satisfied
    """

    def __init__(self) -> None:
        self._by_id: dict[str, CapabilityGrant] = {}
        self._by_token: dict[str, str] = {}  # token → grant_id

    def mint(
        self,
        task_id: str,
        agent_id: str,
        allowed_tools: list[AllowedTool],
        ttl_seconds: int,
        limits: GrantLimits | None = None,
        issued_by: str = "marvis",
    ) -> CapabilityGrant:
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        expires = (now + timedelta(seconds=ttl_seconds)).isoformat()

        grant = CapabilityGrant(
            grant_id=f"grant-{uuid.uuid4().hex[:12]}",
            task_id=task_id,
            agent_id=agent_id,
            issued_by=issued_by,
            allowed_tools=allowed_tools,
            limits=limits or GrantLimits(),
            issued_at=now.isoformat(),
            expires_at=expires,
            grant_token=secrets.token_hex(32),
        )
        self._by_id[grant.grant_id] = grant
        self._by_token[grant.grant_token] = grant.grant_id
        self._persist(grant)
        return grant

    def get_by_token(self, grant_token: str) -> CapabilityGrant | None:
        gid = self._by_token.get(grant_token)
        if gid is None:
            return None
        return self._by_id.get(gid)

    def get(self, grant_id: str) -> CapabilityGrant | None:
        return self._by_id.get(grant_id)

    def revoke(self, grant_id: str) -> None:
        grant = self._by_id.get(grant_id)
        if grant:
            grant.status = GrantStatus.REVOKED
            self._update_db_status(grant_id, GrantStatus.REVOKED)

    def revoke_by_task(self, task_id: str) -> int:
        """Revoke ALL active grants for a task. Returns count revoked."""
        count = 0
        for grant in self._by_id.values():
            if grant.task_id == task_id and grant.status == GrantStatus.ACTIVE:
                grant.status = GrantStatus.REVOKED
                self._update_db_status(grant.grant_id, GrantStatus.REVOKED)
                count += 1
        return count

    def check_and_use(
        self,
        grant_token: str,
        tool_name: str,
        args: dict[str, Any],
    ) -> tuple[bool, str]:
        """Check the grant and record usage. Returns (allowed, reason).

        Enforces: ACTIVE status, TTL, tool in allowlist, caps, arg constraints.
        """
        grant = self.get_by_token(grant_token)
        if grant is None:
            return False, "grant_token not found"

        # TTL check
        now = datetime.now(timezone.utc)
        expires = datetime.fromisoformat(grant.expires_at)
        if now > expires:
            grant.status = GrantStatus.EXPIRED
            self._update_db_status(grant.grant_id, GrantStatus.EXPIRED)
            return False, "grant expired"

        if grant.status != GrantStatus.ACTIVE:
            return False, f"grant status is {grant.status}"

        # Allowlist check (Phase 1: exactly ONE tool)
        allowed = next((t for t in grant.allowed_tools if t.tool_name == tool_name), None)
        if allowed is None:
            allowed_names = [t.tool_name for t in grant.allowed_tools]
            return False, f"tool '{tool_name}' not in allowlist {allowed_names}"

        # Caps check
        total_calls = grant.usage.get("calls_total", 0)
        if total_calls >= grant.limits.max_calls_total:
            return False, f"usage cap exceeded ({total_calls} / {grant.limits.max_calls_total})"

        per_tool = grant.usage.get("per_tool", {})
        tool_calls = per_tool.get(tool_name, 0)
        per_tool_cap = grant.limits.max_calls_per_tool.get(tool_name, grant.limits.max_calls_total)
        if tool_calls >= per_tool_cap:
            return False, f"per-tool cap exceeded for '{tool_name}'"

        # Arg constraints check
        for key, constraint in allowed.arg_constraints.items():
            if key in args:
                val = str(args[key])
                if isinstance(constraint, str) and constraint.startswith("prefix:"):
                    prefix = constraint[7:].strip('"')
                    if not val.startswith(prefix):
                        return False, f"arg '{key}' must start with '{prefix}'"
                elif isinstance(constraint, dict) and "max_len" in constraint:
                    if len(val) > constraint["max_len"]:
                        return False, f"arg '{key}' exceeds max_len {constraint['max_len']}"

        # Record usage
        grant.usage["calls_total"] = total_calls + 1
        if "per_tool" not in grant.usage:
            grant.usage["per_tool"] = {}
        grant.usage["per_tool"][tool_name] = tool_calls + 1
        self._update_db_usage(grant.grant_id, grant.usage)

        return True, "ok"

    # ── DB persistence (audit log) ─────────────────────────────────────────────

    def _persist(self, grant: CapabilityGrant) -> None:
        try:
            from app.db import get_conn
            conn = get_conn()
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO capability_grants
                       (grant_id, task_id, agent_id, issued_by, allowed_tools, limits,
                        task_bound, issued_at, expires_at, status, usage, grant_token)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        grant.grant_id, grant.task_id, grant.agent_id, grant.issued_by,
                        json.dumps([t.model_dump() for t in grant.allowed_tools]),
                        json.dumps(grant.limits.model_dump()),
                        1 if grant.task_bound else 0,
                        grant.issued_at, grant.expires_at,
                        grant.status.value,
                        json.dumps(grant.usage),
                        grant.grant_token,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass  # DB audit failures don't block the live grant

    def _update_db_status(self, grant_id: str, status: GrantStatus) -> None:
        try:
            from app.db import get_conn
            conn = get_conn()
            try:
                conn.execute(
                    "UPDATE capability_grants SET status=? WHERE grant_id=?",
                    (status.value, grant_id),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass

    def _update_db_usage(self, grant_id: str, usage: dict) -> None:
        try:
            from app.db import get_conn
            conn = get_conn()
            try:
                conn.execute(
                    "UPDATE capability_grants SET usage=? WHERE grant_id=?",
                    (json.dumps(usage), grant_id),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass


# ── Module-level singleton ─────────────────────────────────────────────────────
_grant_registry: InMemoryGrantRegistry | None = None


def get_grant_registry() -> InMemoryGrantRegistry:
    global _grant_registry
    if _grant_registry is None:
        _grant_registry = InMemoryGrantRegistry()
    return _grant_registry
