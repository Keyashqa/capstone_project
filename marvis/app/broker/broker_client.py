"""HTTP client for the broker server (marketplace + hiring merchant at :8002).

Adapted from F2's MerchantClient. Covers:
- A2A: fetch SkillCards from the skill catalog
- UCP/MCP: create_checkout (hiring CartMandate)
- AP2: verify_mandate
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import BROKER_BASE_URL


class BrokerClient:
    def __init__(self, base_url: str = BROKER_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    async def fetch_skills(self) -> list[dict]:
        """GET /.well-known/skills — returns list of SkillCard dicts."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.base_url}/.well-known/skills")
            resp.raise_for_status()
            return resp.json()

    async def fetch_agent_card(self) -> dict:
        """GET /.well-known/agent-card — broker's identity."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.base_url}/.well-known/agent-card")
            resp.raise_for_status()
            return resp.json()

    async def mcp_call(
        self,
        method: str,
        params: dict[str, Any],
        rpc_id: int = 1,
    ) -> dict[str, Any]:
        """POST /mcp — JSON-RPC 2.0 (UCP MCP call). Returns full response dict."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.base_url}/mcp",
                json={"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params},
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data and data["error"]:
                raise RuntimeError(f"MCP error ({method}): {data['error']}")
            return data

    async def verify_mandate(
        self,
        session_id: str,
        cart_mandate: dict[str, Any],
        payment_sd_jwt: str,
        user_public_jwk: dict[str, Any],
    ) -> dict[str, Any]:
        """POST /mandates/verify — AP2 double-mandate verification."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.base_url}/mandates/verify",
                json={
                    "session_id": session_id,
                    "cart_mandate": cart_mandate,
                    "payment_sd_jwt": payment_sd_jwt,
                    "user_public_jwk": user_public_jwk,
                },
            )
            resp.raise_for_status()
            return resp.json()


_client: BrokerClient | None = None


def get_broker_client() -> BrokerClient:
    global _client
    if _client is None:
        _client = BrokerClient()
    return _client
