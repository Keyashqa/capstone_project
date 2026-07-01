"""Scoped MCP Proxy — stub for M0, full implementation at M12.

At M12 this becomes the out-of-process capability broker (:8003) that:
- Holds the gdocs MCP stdio session + Google OAuth tokens
- Enforces the CapabilityGrant allowlist on every tool call
- Returns HTTP 403 on denied calls

For M0-M11, the in-process GDocsSession + InMemoryGrantRegistry serve this role
(§7c-C Option C). The boundary and data model are identical; only the transport changes.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Marvis Scoped MCP Proxy",
    description="Scoped MCP proxy — enforces CapabilityGrant allowlist against real gdocs MCP tools.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "marvis-proxy",
        "note": "Stub — in-process grant enforcement active (M12 upgrades to out-of-process)",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
