"""Centralised configuration — reads .env, then environment, then defaults."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env", override=False)
# Fall back to mcp-test credentials so the working OAuth session is reused
load_dotenv(_ROOT.parent / "mcp-test" / "google_workspace_mcp" / ".env", override=False)


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# ── Marvis agent process (:8000) ───────────────────────────────────────────────
MARVIS_HOST: str = _get("MARVIS_HOST", "0.0.0.0")
MARVIS_PORT: int = int(_get("MARVIS_PORT", "8000"))
AGENT_BASE_URL: str = f"http://localhost:{MARVIS_PORT}"

# ── Broker server (:8002) ──────────────────────────────────────────────────────
BROKER_BASE_URL: str = _get("BROKER_BASE_URL", "http://localhost:8002").rstrip("/")

# ── Scoped MCP proxy (:8003) ───────────────────────────────────────────────────
PROXY_BASE_URL: str = _get("PROXY_BASE_URL", "http://localhost:8003").rstrip("/")

# ── Local Ollama (all LLM) ─────────────────────────────────────────────────────
MODEL_NAME: str = _get("MODEL_NAME", "ollama/gemma2:2b")
OLLAMA_MODEL: str = _get("OLLAMA_MODEL", "gemma2:2b")

# ── SQLite ─────────────────────────────────────────────────────────────────────
_db_path_raw = _get("MARVIS_DB_PATH")
DB_PATH: Path = Path(_db_path_raw) if _db_path_raw else _ROOT / "marvis.db"

# ── Auth ───────────────────────────────────────────────────────────────────────
TOKEN_TTL_HOURS: int = int(_get("TOKEN_TTL_HOURS", "72"))

# ── Capability grants ──────────────────────────────────────────────────────────
GRANT_TTL_SECONDS: int = int(_get("GRANT_TTL_SECONDS", "300"))  # 5-min TTL

# ── gdocs MCP (from mcp-test/google_workspace_mcp) ────────────────────────────
GDOCS_MCP_CWD: str = _get(
    "GDOCS_MCP_CWD",
    str(_ROOT.parent / "mcp-test" / "google_workspace_mcp"),
)
GOOGLE_OAUTH_CLIENT_ID: str = _get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET: str = _get("GOOGLE_OAUTH_CLIENT_SECRET", "")
WORKSPACE_MCP_ENABLED_TOOLS: str = _get("WORKSPACE_MCP_ENABLED_TOOLS", "docs,drive")
MCP_SINGLE_USER_MODE: str = _get("MCP_SINGLE_USER_MODE", "true")
USER_GOOGLE_EMAIL: str = _get("USER_GOOGLE_EMAIL", "")

# ── Specialist dispatch ────────────────────────────────────────────────────────
DISPATCH_TIMEOUT_SECONDS: int = int(_get("DISPATCH_TIMEOUT_SECONDS", "120"))
