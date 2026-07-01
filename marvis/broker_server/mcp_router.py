"""UCP MCP endpoint — JSON-RPC 2.0 interface for the broker.

Methods:
  create_checkout(skill_id, task_id) → hiring session + signed CartMandate
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from broker_server.checkout import create_hiring_session
from broker_server.models import McpRequest
from broker_server.skill_router import get_skill_catalog, _default_catalog

router = APIRouter()


@router.post("/mcp")
def mcp_endpoint(req: McpRequest) -> dict:
    method = req.method
    params = req.params

    if method == "create_checkout":
        skill_id = params.get("skill_id", "")
        task_id = params.get("task_id", "")
        if not skill_id or not task_id:
            raise HTTPException(status_code=400, detail="skill_id and task_id are required")
        catalog = get_skill_catalog() or _default_catalog()
        try:
            result = create_hiring_session(skill_id, task_id, catalog)
        except ValueError as exc:
            return {"jsonrpc": "2.0", "id": req.id, "error": str(exc), "result": None}
        return {"jsonrpc": "2.0", "id": req.id, "result": result, "error": None}

    return {
        "jsonrpc": "2.0",
        "id": req.id,
        "error": f"Unknown method: {method}",
        "result": None,
    }
