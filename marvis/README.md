# Marvis — Personal AI Orchestrator

Marvis is a personal AI orchestrator that **hires, pays, provisions, verifies, and settles** with marketplace specialist agents. It demonstrates a complete agent-commerce loop using Google ADK, AP2 payment protocol, UCP commerce protocol, and real Google Workspace MCP tools — all running locally with no paid API keys.

---

## What it does

You type a goal in natural language (e.g. *"Write a tweet about my Marvis launch and save it as a Twitter script in Google Docs"*). Marvis:

1. **Parses** your goal into a typed task spec (Gemma via Ollama)
2. **Discovers** matching specialist skills from the marketplace
3. **Shows you a hire quote** and waits for your PIN
4. **Creates a UCP CartMandate**, verifies it with the broker, and moves funds to escrow
5. **Mints a scoped CapabilityGrant** — a time-limited, single-tool access token
6. **Dispatches** the specialist runtime (Gemma wearing the chosen skill) to do the work
7. **Calls the real Google Docs MCP** tool under the grant allowlist (no raw credentials exposed to the agent)
8. **Revokes** the grant immediately after dispatch (success or failure)
9. **Verifies** the output with deterministic checks + an advisory LLM score
10. **Shows you the result** and waits for your payout PIN
11. **Releases** completion fee to the specialist, settles escrow, and issues a receipt

Everything is double-entry ledger-tracked with hash-chained journal entries.

---

## Architecture

```
Browser (React + Vite :5173)
        │  SSE + REST (proxied)
        ▼
Marvis Agent Server (:8000)   — ADK Workflow (12-node deterministic graph)
  ├─ intake_task              Gemma parses goal_nl → typed spec
  ├─ discover_specialists     SkillRegistry lookup
  ├─ select_specialist        Rule-based match → AgentCard
  ├─ authorize_base_payment   *** PIN GATE #1 (hire) ***
  ├─ create_hire_checkout     UCP CartMandate via Broker
  ├─ verify_hire_cart         Expiry + broker signature check
  ├─ pay_base_into_escrow     AP2 SD-JWT + double-entry ledger
  ├─ grant_capability         Mint CapabilityGrant (1 tool, TTL, call limit)
  ├─ dispatch_to_specialist   Run Gemma + lent MCP tool
  ├─ collect_result           Buffer output
  ├─ revoke_capability        ALWAYS runs (success or failure)
  ├─ verify_work              Deterministic checks + advisory LLM score
  ├─ approve_payout           *** PIN GATE #2 (payout) ***
  ├─ pay_completion           Release escrow → specialist
  └─ settle_escrow / receipt  Close HiringTxn, issue receipt

Broker Server (:8002)         — Marketplace + CartMandate signer
  └─ /skills, /mcp, /mandate

Google Workspace MCP          — stdio subprocess (gdocs tools)
  └─ create_doc, get_doc_content, manage_doc_tab
```

**Key design properties:**
- Routing is 100% deterministic — no LLM at the graph level
- LLM (Gemma/Ollama) is used inside: `intake_task`, `verify_work` (advisory), specialist runtime
- Fully keyless: Ollama runs locally; Google auth is one-time OAuth consent, cached
- One specialist runtime that "wears" a skill — not N separate agents
- The CapabilityGrant is the **only** path from the agent to the MCP tool; the agent never sees OAuth tokens

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11 – 3.13 | `python3 --version` |
| [uv](https://docs.astral.sh/uv/) | latest | `pip install uv` |
| Node.js | 18+ | for the React frontend |
| [Ollama](https://ollama.com) | latest | pull `gemma2:2b` |
| Google Cloud project | — | for OAuth client (Docs + Drive APIs) |

Pull the model once:
```bash
ollama pull gemma2:2b
```

---

## Setup

### 1. Clone and install Python dependencies

```bash
cd marvis
uv sync
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your Google OAuth credentials:

```ini
GOOGLE_OAUTH_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-your_secret
USER_GOOGLE_EMAIL=your@gmail.com
```

**How to get Google OAuth credentials:**
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Enable **Google Docs API** and **Google Drive API**
3. Create Credentials → OAuth 2.0 Client ID → **Desktop app**
4. Copy the `client_id` and `client_secret` into `.env`

### 3. One-time Google OAuth consent

Run the test script once to complete browser consent and cache the token:

```bash
cd ../mcp-test
python create_doc.py
```

A browser tab opens → sign in → grant Docs + Drive access → token is saved to `~/.google_workspace_mcp/credentials/`. You will not be prompted again.

### 4. Install frontend dependencies

```bash
cd marvis/frontend
npm install
```

---

## Running

Open **three terminals**, all from the `marvis/` directory:

**Terminal 1 — Marvis agent server**
```bash
./run_marvis.sh
# Starts on :8000
```

**Terminal 2 — Broker server**
```bash
./run_broker.sh
# Starts on :8002
```

**Terminal 3 — Frontend**
```bash
./run_frontend.sh
# Starts on :5173 — open http://localhost:5173
```

---

## Demo walkthrough

1. Open `http://localhost:5173`
2. Register or log in (any username + password, PIN = any 4+ digit number)
3. Top up your wallet (Wallet tab → Add funds)
4. Go to Chat and type:
   ```
   Write a tweet about my Marvis launch and save it as a Twitter script in Google Docs.
   ```
5. Marvis shows a **Hire Confirmation** card with fees. Enter your PIN to approve.
6. Watch the workflow run: checkout → escrow → grant → Gemma writes the tweet → Google Doc created
7. A **Work Verification** card shows the advisory score. Enter your PIN to release the payout.
8. A receipt is issued. Check Google Drive — a doc titled "Twitter Scripts — Marvis launch" will be there with the content.

**Other things to try:**
- Ask to read a doc: `"Summarise the contents of this Google Doc: <doc_id>"`
- Cancel mid-hire by entering the wrong PIN — the completion fee is refunded
- Check your wallet balance before and after to see the exact ledger movements

---

## Project structure

```
marvis/
├── app/
│   ├── agent.py                  ADK Workflow graph (12 nodes, all edges named)
│   ├── fast_api_app.py           FastAPI app — mounts ADK + custom routes
│   ├── config.py                 Centralised env/config loader
│   ├── auth.py                   Register / login / PIN verify
│   ├── wallet.py                 Wallet balance + top-up
│   ├── db.py                     SQLite schema init
│   ├── keys.py                   Per-user ES256 JWK generation
│   ├── capability/
│   │   ├── grant.py              CapabilityGrant + InMemoryGrantRegistry
│   │   └── gdocs_session.py      Google Workspace MCP stdio session
│   ├── escrow/
│   │   └── operations.py         Double-entry escrow hold / release
│   ├── marketplace/
│   │   ├── skill_card.py         SkillCard + AgentCard Pydantic models
│   │   ├── skill_registry.py     In-memory registry with specialty search
│   │   └── seed.py               Seeds DocWriter + DocReader skill cards
│   ├── runtime/
│   │   └── specialist.py         Specialist runtime: Gemma + MCP tool dispatch
│   ├── workflow/nodes/
│   │   ├── intake.py             Parse goal_nl → typed spec
│   │   ├── discover.py           Registry lookup + specialist selection
│   │   ├── hire.py               PIN gate, CartMandate, AP2 escrow
│   │   ├── capability.py         Grant mint + revoke
│   │   ├── dispatch.py           Run specialist, collect result
│   │   ├── verify.py             Deterministic checks + advisory score
│   │   ├── payout.py             PIN gate, fee release, escrow settlement
│   │   └── terminals.py          Receipt / refund / cancel terminal nodes
│   └── broker/
│       └── broker_client.py      HTTP client for broker_server
├── broker_server/
│   ├── app.py                    Broker FastAPI app
│   ├── skill_router.py           GET /skills endpoint
│   ├── mandate_router.py         CartMandate create + verify
│   └── mcp_router.py             MCP tool proxy endpoints
├── frontend/
│   └── src/
│       ├── pages/Auth.tsx        Login / register
│       ├── pages/Chat.tsx        Main chat + SSE event stream + PIN modals
│       ├── pages/Wallet.tsx      Balance + top-up
│       └── api.ts                REST + SSE client
├── .env.example                  Environment variable template
├── pyproject.toml                Python dependencies (uv)
├── run_marvis.sh                 Start agent server
├── run_broker.sh                 Start broker server
└── run_frontend.sh               Start React frontend
```

---

## Key protocols and libraries

| Protocol / Library | Role in Marvis |
|---|---|
| [Google ADK](https://google.github.io/adk-docs/) | Workflow graph engine, SSE transport, session resumability |
| [AP2](https://github.com/google-agentic-commerce/AP2) | SD-JWT signed payment mandates |
| [UCP SDK](https://github.com/Universal-Commerce-Protocol/python-sdk) | CartMandate commerce protocol |
| [Google Workspace MCP](https://github.com/taylorai/google-workspace-mcp) | Real Docs + Drive tools via stdio MCP |
| [Ollama](https://ollama.com) + gemma2:2b | Local LLM — zero API keys, zero cost |
| FastAPI + Vite/React | Backend API + frontend SPA |

---

## Security notes

- **No secrets in the repo.** `.env`, `*.db`, `_keys/*.json`, and OAuth token files are all `.gitignored`.
- **The agent never sees OAuth tokens.** The `CapabilityGrant` token is the only credential the specialist runtime holds; the MCP session and Google credentials live exclusively in the orchestrator process.
- **Grants are short-lived and single-tool.** Default TTL: 5 minutes, max 5 calls, 1 allowed tool. Revocation is guaranteed on every exit path from dispatch.
- **Double-entry ledger.** Every money movement is a pair of journal entries that sum to zero. The escrow account is hash-chained per task.

---

## Running tests

```bash
cd marvis
uv run pytest tests/ -v
```
