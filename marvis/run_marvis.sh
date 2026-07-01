#!/usr/bin/env bash
# Start the Marvis agent process (:8000)
set -e
cd "$(dirname "$0")"
exec uv run uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8000 --reload
