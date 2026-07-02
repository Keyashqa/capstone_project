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

# ── Marketplace commission (Phase 3 foundation — DEFINED, not yet applied) ────
# When a LISTED skill is hired, the broker keeps COMMISSION_RATE_BPS of the
# COMMISSION_BASIS tranche and routes the remainder to the owner. Penny-exact
# rule (Phase 3): commission = (tranche * BPS) // 10000; owner = tranche - commission.
# NOT wired into payout.py yet — pay_completion still pays 100% to the agent.
COMMISSION_RATE_BPS: int = int(_get("COMMISSION_RATE_BPS", "1000"))   # 1000 bps = 10%
COMMISSION_BASIS: str = _get("COMMISSION_BASIS", "completion")        # "completion" only

# ── Phase 3 demo seed (LOCAL demo accounts — NOT real secrets) ────────────────
# Seeds a real seller ("alice") + a funded buyer/operator through the existing
# users/wallets/keys tables so the earnings loop can be demonstrated end-to-end
# without a signup UI (plan3.md §P3-6c). Values are overridable via .env; the
# defaults are demo-only and carry no security meaning.
DEMO_SEED_ENABLED: bool = _get("DEMO_SEED_ENABLED", "true").lower() == "true"
DEMO_SELLER_ID: str = _get("DEMO_SELLER_ID", "alice")                 # == users.id == owner_id
DEMO_SELLER_EMAIL: str = _get("DEMO_SELLER_EMAIL", "alice@marvis.local")
DEMO_BUYER_ID: str = _get("DEMO_BUYER_ID", "operator")               # the funded hirer
DEMO_BUYER_EMAIL: str = _get("DEMO_BUYER_EMAIL", "operator@marvis.local")
DEMO_PASSWORD: str = _get("DEMO_PASSWORD", "marvis-demo")            # demo-only
DEMO_PIN: str = _get("DEMO_PIN", "1234")                             # demo-only
DEMO_BUYER_TOPUP_CENTS: int = int(_get("DEMO_BUYER_TOPUP_CENTS", "5000"))  # $50 float
# The skill "alice" lists to the marketplace. Twitter has NO owned competitor
# (Marvis owns only linkedin from Phase 2), so a listed twitter skill wins the
# hire cleanly and the Phase-1 flagship ("Write a tweet…") now pays alice.
DEMO_LISTING_SLUG: str = _get("DEMO_LISTING_SLUG", "twitter-writer")
