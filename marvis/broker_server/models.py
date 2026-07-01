"""Pydantic models for the broker server."""
from __future__ import annotations

from pydantic import BaseModel


class MandateVerifyRequest(BaseModel):
    session_id: str
    cart_mandate: dict
    payment_sd_jwt: str
    user_public_jwk: dict


class MandateVerifyResponse(BaseModel):
    verified: bool
    booking_id: str | None = None
    error: str | None = None


class McpRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int = 1
    method: str
    params: dict = {}
