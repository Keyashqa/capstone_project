import os

import uvicorn
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

# Directory containing agent packages (daedalus_toolsmith)
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Simple SQLite session store inside the container
SESSION_SERVICE_URI = "sqlite:///./sessions.db"

# CORS settings
ALLOWED_ORIGINS = ["http://localhost", "http://localhost:8080", "*"]

# Serve ADK’s built-in web UI
SERVE_WEB_INTERFACE = True

# Let ADK auto-discover your agents in daedalus_toolsmith/
app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=SESSION_SERVICE_URI,
    allow_origins=ALLOWED_ORIGINS,
    web=SERVE_WEB_INTERFACE,
)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="localhost",
        port=int(os.environ.get("PORT", 8080)),
    )
