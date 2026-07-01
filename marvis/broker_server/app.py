"""Broker server FastAPI app — Marketplace + Hiring Merchant (:8002)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from broker_server.db import init_db
from broker_server.mandate_router import router as mandate_router
from broker_server.mcp_router import router as mcp_router
from broker_server.skill_router import router as skill_router

app = FastAPI(
    title="Marvis Broker Server",
    description="Marketplace skill catalog + hiring merchant (CartMandate signing + mandate verification).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(skill_router)
app.include_router(mcp_router)
app.include_router(mandate_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "marvis-broker"}


@app.on_event("startup")
def startup() -> None:
    init_db()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
