#!/usr/bin/env bash
# Start the Broker server (:8002) — marketplace + hiring merchant
set -e
cd "$(dirname "$0")"
exec uv run uvicorn broker_server.app:app --host 0.0.0.0 --port 8002 --reload
