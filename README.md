# Capstone Project — Marvis

This repository contains the capstone implementation of **Marvis**, a personal AI orchestrator for agentic commerce, and the supporting reference prototypes used during development.

## Repository layout

```
capstone_project/
├── marvis/                        ← MAIN PROJECT (start here)
│   └── README.md                  Full setup, architecture, and demo guide
├── adk_ucp_ap2_working_prototype/ ← Reference: ADK + UCP + AP2 integration spike
│   ├── ucp-commerce-agent/        Validated AP2 payment + CartMandate patterns
│   └── ucp-merchant-server/       Reference UCP merchant endpoint
├── mcp-test/                      ← Reference: Google Workspace MCP integration test
│   ├── google_workspace_mcp/      Workspace MCP server (submodule/install)
│   └── create_doc.py              Working create_doc + populate flow (OAuth reference)
└── plan-audit/                    Original implementation plan (M0–M11) + audit notes
    ├── plan.md / plan2.md / plan3.md
    ├── audit.md
    └── dump.txt                    Tutorial / demo walkthrough transcript
```

## Quick start

See **[marvis/README.md](marvis/README.md)** for the full setup guide (architecture, protocols, project structure, demo walkthrough). The short version:

### 1. Clone

```bash
git clone https://github.com/Keyashqa/capstone_project.git
cd capstone_project/marvis
```

### 2. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11 – 3.13 | `python3 --version` |
| [uv](https://docs.astral.sh/uv/) | latest | `pip install uv` |
| Node.js | 18+ | for the React frontend |
| [Ollama](https://ollama.com) | latest | local LLM, zero API keys |
| Google Cloud project | — | OAuth client for Docs + Drive APIs |

```bash
ollama pull gemma2:2b
```

### 3. Install dependencies

```bash
uv sync                                # Python deps (from marvis/)
cd frontend && npm install && cd ..    # frontend deps
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in Google OAuth credentials (create an OAuth 2.0 **Desktop app** client at [console.cloud.google.com](https://console.cloud.google.com) with the Docs + Drive APIs enabled):

```ini
GOOGLE_OAUTH_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-your_secret
USER_GOOGLE_EMAIL=your@gmail.com
```

### 5. One-time Google OAuth consent

`mcp-test/create_doc.py` needs the `mcp` package, which requires Python ≥3.10 —
your system `python3` may be older, so run it through `uv` with an explicit
interpreter instead of the bare `python`/`python3` command:

```bash
cd ../mcp-test
uv run --python 3.11 --with mcp --with python-dotenv --with requests create_doc.py
cd ../marvis
```

A browser tab opens → sign in → grant Docs + Drive access → the token is cached to `~/.google_workspace_mcp/credentials/`. You won't be prompted again.

### 6. Launch (3 terminals, all from `marvis/`)

```bash
./run_marvis.sh            # terminal 1: agent server :8000
./run_broker.sh             # terminal 2: broker :8002
./run_frontend.sh           # terminal 3: frontend :5173
```

> A fourth process — a standalone MCP proxy (:8003) for scoped tool grant
> enforcement — was designed but never built (`marvis/proxy_server/` is an
> unused stub). Enforcement happens in-process instead, so only the three
> processes above need to run. See [ARCHITECTURE.md](marvis/ARCHITECTURE.md) for details.

Then open `http://localhost:5173`, register/log in (any username + password + 4-digit PIN), top up your wallet, and type:
> Write a tweet about my Marvis launch and save it as a Twitter script in Google Docs.

## What Marvis demonstrates

- **Agentic commerce loop** — hire → pay → provision → work → verify → settle, end-to-end
- **AP2 payment protocol** — SD-JWT signed payment mandates
- **UCP CartMandate** — standardised commerce checkout flow
- **Scoped capability grants** — the agent gets one tool for one task; revoked on exit
- **Real MCP integration** — live Google Docs creation via Google Workspace MCP
- **Local LLM** — Gemma 2B via Ollama, zero API keys, zero cost
- **Double-entry ledger** — every cent is tracked and hash-chained
