"""EC P-256 JWK key management — per-user and per-skill keypairs."""
from __future__ import annotations

import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec
from jwcrypto.jwk import JWK

_KEY_DIR = Path(__file__).parent / "_keys"


def _load_or_generate(name: str) -> JWK:
    priv_path = _KEY_DIR / f"{name}.json"
    if priv_path.exists():
        return JWK.from_json(priv_path.read_text(encoding="utf-8"))
    _KEY_DIR.mkdir(exist_ok=True)
    raw = ec.generate_private_key(ec.SECP256R1())
    jwk = JWK.from_pyca(raw)
    jwk_dict = json.loads(jwk.export())
    jwk_dict["kid"] = name
    jwk_dict["alg"] = "ES256"
    jwk = JWK.from_json(json.dumps(jwk_dict))
    priv_path.write_text(jwk.export(), encoding="utf-8")
    return jwk


# ── Per-user keys (loaded from DB, same pattern as F2) ────────────────────────

def user_private_key_for(user_id: str) -> JWK:
    try:
        from app.db import get_conn
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT private_jwk FROM user_keys WHERE user_id=?", (user_id,)
            ).fetchone()
            if row:
                return JWK.from_json(row["private_jwk"])
        finally:
            conn.close()
    except Exception:
        pass
    return _load_or_generate(f"user-{user_id}")


def user_public_key_for(user_id: str) -> JWK:
    try:
        from app.db import get_conn
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT public_jwk FROM user_keys WHERE user_id=?", (user_id,)
            ).fetchone()
            if row:
                return JWK.from_json(row["public_jwk"])
        finally:
            conn.close()
    except Exception:
        pass
    return JWK.from_json(user_private_key_for(user_id).export_public())


# ── Per-skill keys (A9: each SkillCard has its own keypair) ───────────────────
# Key name: "skill-<skill_id>"  e.g. "skill-doc-writer"

def skill_private_key(skill_id: str) -> JWK:
    return _load_or_generate(f"skill-{skill_id}")


def skill_public_key(skill_id: str) -> JWK:
    return JWK.from_json(skill_private_key(skill_id).export_public())


def skill_public_key_dict(skill_id: str) -> dict:
    return json.loads(skill_public_key(skill_id).export_public())
