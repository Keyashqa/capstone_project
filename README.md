# Capstone Project — Marvis

This repository contains the capstone implementation of **Marvis**, a personal AI orchestrator for agentic commerce, and the supporting reference prototypes used during development.

## Repository layout

```
capstone_project/
├── marvis/                        ← MAIN PROJECT (start here)
│   └── README.md                  Full setup, architecture, and demo guide
├── adk_ucp_ap2_working_prototype/ ← Reference: ADK + UCP + AP2 integration spike
│   └── ucp-commerce-agent/        Validated AP2 payment + CartMandate patterns
├── mcp-test/                      ← Reference: Google Workspace MCP integration test
│   ├── google_workspace_mcp/      Workspace MCP server (submodule/install)
│   └── create_doc.py              Working create_doc + populate flow (OAuth reference)
├── plan.md                        Original implementation plan (M0–M11)
└── dump.txt                       Tutorial / demo walkthrough transcript
```

## Quick start

See **[marvis/README.md](marvis/README.md)** for the full setup guide.

The short version:
```bash
cd marvis
uv sync                    # install Python deps
cp .env.example .env       # fill in Google OAuth credentials
./run_marvis.sh            # terminal 1: agent server :8000
./run_broker.sh            # terminal 2: broker :8002
./run_frontend.sh          # terminal 3: frontend :5173
```

Then open `http://localhost:5173` and type:
> Write a tweet about my Marvis launch and save it as a Twitter script in Google Docs.

## What Marvis demonstrates

- **Agentic commerce loop** — hire → pay → provision → work → verify → settle, end-to-end
- **AP2 payment protocol** — SD-JWT signed payment mandates
- **UCP CartMandate** — standardised commerce checkout flow
- **Scoped capability grants** — the agent gets one tool for one task; revoked on exit
- **Real MCP integration** — live Google Docs creation via Google Workspace MCP
- **Local LLM** — Gemma 2B via Ollama, zero API keys, zero cost
- **Double-entry ledger** — every cent is tracked and hash-chained
