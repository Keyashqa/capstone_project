#!/usr/bin/env bash
# Start the Scoped MCP Proxy stub (:8003)
set -e
cd "$(dirname "$0")"
exec uv run uvicorn proxy_server.app:app --host 0.0.0.0 --port 8003 --reload
