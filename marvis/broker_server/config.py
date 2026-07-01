"""Broker server configuration."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env", override=False)


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


BROKER_HOST: str = _get("BROKER_HOST", "0.0.0.0")
BROKER_PORT: int = int(_get("BROKER_PORT", "8002"))

_db_path_raw = _get("BROKER_DB_PATH")
DB_PATH: Path = Path(_db_path_raw) if _db_path_raw else _ROOT / "broker.db"

CART_MANDATE_TTL_MINUTES: int = int(_get("CART_MANDATE_TTL_MINUTES", "15"))
