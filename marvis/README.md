# Marvis — a self-growing marketplace of niche AI content agents

> Tell Marvis what you want written. It finds the right niche skill in a
> marketplace, hires it, lends it a single scoped tool for a few minutes, checks
> the work, and pays the creator — asking for your PIN before any money moves.
> If no skill fits your niche, it commissions one and adds it to the market for good.

**What this is.** Marvis is a personal orchestrator agent plus a three-sided
marketplace. A user makes a natural-language content request; a deterministic
[ADK](https://google.github.io/adk-docs/) workflow parses it, discovers a matching
**niche writing skill** (platform × task, extensible by domain keywords), hires it
over a commerce protocol, grants it a **time-limited single-tool** capability to a
real Google Docs MCP server, runs it on a local model, verifies the output, and
settles payment through a **double-entry, hash-chained ledger** — with a **human PIN
gate** at hire and at payout. Everything runs locally: the LLM is **Gemma 2 (2B) via
Ollama**, storage is **SQLite**, and there are **no paid API keys**.

---

## The problem

Generic AI writing is easy; *good* niche content is hard. A tweet in a founder's
voice, a LinkedIn post for a B2B security audience, a Medium dev-tools article —
each needs its own tone, length rules, and structure. One giant prompt can't hold
all of them, and hand-tuning a prompt per niche doesn't scale.

Agents are a natural fit because niche skill is **composable and tradeable**: a
person who has nailed one niche can package it as a skill, and everyone else can
*hire* that skill on demand instead of re-deriving it. That only works if you can
also **discover, trust, scope, verify, and pay** for a stranger's skill safely —
which is exactly the loop Marvis implements.

---

## What Marvis does — three sides

| Side | Who | What happens |
|---|---|---|
| **Rent** | anyone with a task | Describe a goal → Marvis hires the best-matching marketplace skill, runs it, and you pay per job (base + completion fee). |
| **Build & own** | Marvis, on your behalf | If no skill covers your niche, Marvis commissions the **SkillBuilder** to author one. It's added to an **owned** library and runs **free** for its owner forever after. |
| **List & earn** | creators | List a skill (or upload a custom one). When **someone else** hires it, the base fee + 90% of the completion fee land in **your wallet**; the platform keeps a **10% commission**. |

"Self-growing" is literal: a capability **gap** triggers a build, and after the
build purchase settles, the workflow **loops back** to discovery — the task that
found nothing a moment ago now finds the freshly-created skill.

---

## Architecture

![Marvis architecture](docs/architecture.png)
<!-- Diagram image to be added at marvis/docs/architecture.png -->

Three processes run in the demo (a fourth, a standalone MCP proxy, was designed
but left as a stub — enforcement is in-process; see [ARCHITECTURE.md](ARCHITECTURE.md)):

```
Browser — React + Vite (:5173)
   │  REST (/auth, /wallet, /marketplace, /platform, /skills) + SSE (/run_sse)
   ▼
Marvis Agent Server (:8000)  — FastAPI + ADK Workflow (deterministic graph)
   ├─ intake_task            Gemma parses goal → typed spec
   ├─ discover/select        rule-based match over marketplace ∪ owned registries
   ├─ authorize_base_payment *** PIN GATE #1 (hire) ***
   ├─ create/verify checkout UCP CartMandate from the Broker (AP2-signed)
   ├─ pay_base_into_escrow   AP2 SD-JWT PaymentMandate → double-entry ledger → escrow
   ├─ grant_capability       mint 1-tool, TTL-bound CapabilityGrant
   ├─ dispatch/collect       one specialist runtime "wears" the chosen skill (Gemma)
   │     └─ calls the REAL gdocs MCP tool under the grant allowlist
   ├─ revoke_capability      ALWAYS runs (success or failure)
   ├─ verify_work            deterministic checks + advisory LLM score
   ├─ approve_payout         *** PIN GATE #2 (payout) ***
   └─ pay_completion         3-way split: owner + broker; settle escrow → receipt
        │
        ▼
Broker Server (:8002)        — skill catalog + CartMandate signer
   └─ GET /skills · POST /mcp (create_checkout) · POST /mandate (verify)   [SQLite: sessions only]

Google Workspace MCP         — real stdio subprocess (../mcp-test/google_workspace_mcp)
   └─ create_doc · get_doc_content   (one-time OAuth; agent never sees the token)

SQLite (marvis.db)           — users, wallets, hash-chained ledger, escrow, grants, receipts, ownership
Ollama (gemma2:2b)           — all LLM calls, local, no API key
```

**Key components:**

- **Orchestrator** — an ADK `Workflow` (`app/agent.py`) with **deterministic
  routing** (no LLM decides control flow). Gemma is used only *inside* nodes:
  `intake_task` (parse goal), `verify_work` (advisory score), and the specialist
  runtime. State machine detail is in [ARCHITECTURE.md](ARCHITECTURE.md).
- **Marketplace + registries** — two in-memory registries keyed by
  `(owner_id, skill_id)` (`app/marketplace/skill_registry.py`): a **marketplace**
  store (rented/listed, pay-per-use) and an **owned** store (built, free). Skill
  content lives on disk as `skill.json` + `instruction.md`.
- **One runtime, many skills** — there is **not** one agent per skill.
  `app/runtime/specialist.py` is a single runtime shell that loads whichever
  SkillCard was selected and runs Gemma against its instruction.
- **The builder** — when a niche has no skill, `propose_build` commissions the
  `skill-builder`. The model writes only the `instruction`/`description`; every
  safety-critical field (id, tool, pricing, agent name) is **derived by Marvis**,
  so a 2B model can't fabricate a tool or identity.
- **Money** — `app/wallet.py` is a **double-entry, hash-chained** ledger; balances
  are never stored, always derived as `SUM(delta_cents)`. Escrow
  (`app/escrow/operations.py`) holds funds per task. `app/escrow/split.py` is the
  pure **3-way split**: base 100% + 90% completion → owner's wallet, 10% completion
  → `broker` (unowned skills → 100% broker). Penny-exact by flooring one leg and
  deriving the other by subtraction.
- **Scoped MCP grants** — `app/capability/grant.py` mints a `CapabilityGrant`:
  **one** allowed tool, a **5-minute TTL**, a **call cap**, and optional arg
  constraints. It's the *only* path from the specialist to the gdocs tool; the
  grant is revoked on **every** exit from dispatch, plus TTL expiry.
- **Human PIN gates** — money moves only after a PIN at hire (`authorize_base_payment`)
  and at payout (`approve_payout`).

---

## Course concepts demonstrated

| Concept (rubric) | Where it lives in the code | What it does |
|---|---|---|
| **Multi-agent / ADK** | `app/agent.py` (ADK `Workflow`, ~20 named edges); `app/runtime/specialist.py`; `app/workflow/nodes/build.py` (builder) | Orchestrator agent routes a deterministic graph; a marketplace of specialist skills + a builder agent + a broker are distinct principals with their own keys and ledger accounts. |
| **MCP server** | **Client:** `app/capability/gdocs_session.py` spawns the real `workspace-mcp` server over stdio and calls `create_doc`/`get_doc_content`. **Server:** `broker_server/mcp_router.py` exposes a JSON-RPC 2.0 `/mcp` commerce endpoint (`create_checkout`). | Marvis consumes a real external MCP server for Google Docs and exposes its own MCP-style commerce endpoint. |
| **Security features** | `app/capability/grant.py` (scoped grant: 1 tool, TTL, caps, dual-revoke); `app/wallet.py` (hash-chained double-entry); `app/auth.py` (bcrypt password + PIN, token sessions); `app/keys.py` (per-user & per-skill ES256 JWKs); PIN gates in `hire.py`/`payout.py` | Least-privilege tool access, tamper-evident ledger, human-in-the-loop money gates, and no OAuth token ever reaching the agent. |
| **Agent skills** | `app/marketplace/skill_card.py`, `skill_registry.py`, `seed.py`; on-disk `app/marketplace/agent-skills/<owner>/<slug>/`; `app/builder/` (author + persist) | Skills are first-class, tradeable, on-disk artifacts (`skill.json` + `instruction.md`); new ones can be built by the builder or uploaded via `POST /skills/create`. |
| **Deployability** | `app/fast_api_app.py` (FastAPI + uvicorn, serves the built SPA); SQLite (`app/db.py`); `pyproject.toml` (`uv`); `run_*.sh`; all-local Ollama | Single-machine, keyless deployment; env-configured; frontend build served by the backend. |

> Honesty note: the specialist runtime calls Gemma via `ollama.chat` directly (not
> an ADK `LlmAgent`); ADK provides the **workflow graph, SSE transport, and session
> resumability**. "A2A" appears as a labeling/discovery convention (agent cards,
> broker catalog) — hire **dispatch is in-process**, not an A2A wire call.

---

## The protocols (what each does *here*)

- **A2A** — the discovery/identity convention: skills are advertised as agent cards
  via the broker's catalog (`GET /skills`). *In this build, dispatch is in-process,
  not a networked A2A call.*
- **AP2** — real SD-JWT signed payment mandates. `pay_base_into_escrow` builds a
  `PaymentMandateContents`, signs it with the user's key (`ap2.sdk.mandate.MandateClient`),
  and the broker verifies it.
- **UCP** — commerce checkout: the broker signs a `CartMandate` (`broker_server/checkout.py`)
  and returns it over its JSON-RPC 2.0 `/mcp` endpoint (`create_checkout`).
- **MCP** — real Google Workspace tools (`create_doc`, `get_doc_content`) via a stdio
  subprocess; Marvis is the MCP client and mediates every call through a capability grant.
- **A2UI** — the agent streams `<a2ui-json>` UI surfaces (hire card, payout card,
  receipt) over SSE; `frontend/src/components/A2uiRenderer.tsx` renders them, and PIN
  input flows back through the same channel.

---

## Setup & run

### Prerequisites

| Tool | Version | Install / note |
|---|---|---|
| Python | 3.11–3.13 | `python --version` |
| [uv](https://docs.astral.sh/uv/) | latest | `pip install uv` |
| Node.js | 18+ | for the React frontend |
| [Ollama](https://ollama.com) | latest | then `ollama pull gemma2:2b` |
| Google Cloud OAuth client | — | Desktop-app client, Docs + Drive APIs enabled |

> **Required sibling folder.** The Google Docs tools run from
> `../mcp-test/google_workspace_mcp` (a vendored copy of
> [google-workspace-mcp](https://github.com/taylorai/google-workspace-mcp)).
> Keep it next to `marvis/`, or set `GDOCS_MCP_CWD` in `.env` to its path. Marvis
> will not create documents without it.

### 1. Install

```bash
ollama pull gemma2:2b

cd marvis
uv sync                       # backend deps

cd frontend && npm install    # frontend deps
cd ..
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your Google OAuth credentials (see `.env.example` for every
variable and its meaning):

```ini
GOOGLE_OAUTH_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-your_secret
USER_GOOGLE_EMAIL=you@gmail.com
```

Get them at [console.cloud.google.com](https://console.cloud.google.com): enable
**Google Docs API** + **Google Drive API**, create an **OAuth 2.0 Client ID →
Desktop app**, and copy the id/secret. The OAuth **token cache is gitignored** and
never committed.

### 3. One-time Google consent

The first `create_doc` call prints a Google OAuth URL to the **Marvis server
console**. Open it, grant Docs + Drive access, and the token is cached to
`~/.google_workspace_mcp/credentials/`. You won't be prompted again.

### 4. Run — two terminals (from `marvis/`)

```bash
# Terminal 1 — agent server (:8000)
./run_marvis.sh

# Terminal 2 — broker server (:8002)
./run_broker.sh
```

Then the frontend:

```bash
# Terminal 3 — dev frontend (:5173)
./run_frontend.sh          # open http://localhost:5173
```

> Windows / no bash: run the commands inside the `.sh` files directly, e.g.
> `uv run uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8000 --reload` and
> `uv run uvicorn broker_server.app:app --host 0.0.0.0 --port 8002 --reload`, and
> `cd frontend && npm run dev`.

On startup the agent server auto-seeds a demo (configurable/disable-able via
`DEMO_*` vars in `.env`): a real seller **alice**, a funded buyer **operator**
($50), and alice's **listed twitter-writer** skill — so the earnings loop works
out of the box.

---

## Demo walkthrough — the three moments to show

1. **Register / log in.** Any username + password; PIN is any 4–6 digit number.
   Top up your wallet (Wallet tab) so you can afford a hire.

2. **Rent (a hire that pays a creator).** In Chat:
   > *Write a tweet about my Marvis launch and save it as a Twitter script in Google Docs.*

   Marvis shows a **Hire card** (base non-refundable + completion refundable). Enter
   PIN #1. Watch: checkout → escrow → grant minted → Gemma writes the tweet → a real
   Google Doc is created → grant revoked. A **Payout card** shows the advisory score;
   enter PIN #2. A **receipt** appears with a live Google Docs link. Because alice
   listed the twitter skill, **alice's wallet grows and `broker` takes 10%** — visible
   on the Platform Volume tab.

3. **Build a missing niche (self-growing).** Ask for a platform Marvis doesn't yet
   cover, e.g.:
   > *Write a LinkedIn post announcing our seed round.*

   With no LinkedIn writer in the market, Marvis proposes a **build** (PIN gate),
   commissions the SkillBuilder, persists a new skill into the **owned** library, and
   **loops back** — the same request now runs the newly-built skill. Refresh the
   Owned Skills tab to see it appear.

4. **List & earn.** The Platform Volume tab shows **broker revenue** and
   **per-owner earnings** ticking up as listed skills get hired; a seller's
   Contributed Skills view (`GET /skills/contributed`) shows hire count + lifetime
   earnings per skill.

**Also try:** enter the *wrong* PIN at payout — the completion fee is refunded to
your wallet and the non-refundable base sweeps to the skill's owner; escrow still
settles to exactly 0.

---

## Security notes

- **Least-privilege, scoped grants.** A `CapabilityGrant` allows **exactly one**
  MCP tool, for **one task**, with a **5-minute TTL**, a **call cap** (default 5),
  and optional argument constraints. The read/write split (`get_doc_content` vs
  `create_doc`) means a reviewer skill can never write and a writer can never read.
- **Dual revocation.** Grants are revoked **explicitly** on every dispatch exit
  (success *or* failure, `revoke_capability`) **and** by **TTL** expiry inside
  `check_and_use`. There's no path where a grant outlives its task.
- **Agent never sees credentials.** OAuth tokens live only in the orchestrator's
  MCP session. The specialist holds only an opaque grant token — a capability
  handle, not a secret.
- **Two human PIN gates.** No money moves without a PIN at hire and at payout
  (bcrypt-hashed, verified server-side).
- **Base non-refundable / completion refundable.** On verify-fail the completion
  fee refunds to the buyer; the base sweeps to the skill's owner (or broker if
  unowned). The broker never commissions failed work.
- **Zero-sum, penny-exact ledger.** Every movement is a balanced double entry, so
  all accounts sum to 0; escrow always drains to exactly 0. The 3-way split floors
  one leg and derives the other by subtraction — no float ever touches money. Each
  ledger row is **hash-chained** (`prev_hash`/`entry_hash`), so tampering is
  detectable via `verify_chain`.
- **No secrets in the repo.** `.env`, `*.db`, `_keys/*.json`, and the OAuth token
  cache are all gitignored; `.env.example` carries placeholders only.

---

## Known limitations / what's next

- **CPU-model latency.** `gemma2:2b` on CPU makes a full hire take tens of seconds;
  the `DISPATCH_TIMEOUT_SECONDS` default is 120s. Quality is "2B-model good," not
  frontier.
- **In-process dispatch, not real A2A.** Specialists run in the orchestrator
  process; "A2A" is a discovery/identity convention here. A real networked A2A
  dispatch is future work.
- **The scoped MCP proxy is a stub.** Grant enforcement is in-process; the planned
  out-of-process proxy (`:8003`) is parked in `references/`. The trust boundary and
  data model are identical — only the transport would change.
- **No withdrawal / cash-out.** Seller earnings land in the seller's spendable
  wallet directly (so they *are* usable in-app), but there's no external payout
  rail — it's a closed-loop demo economy.
- **Demo-seeded owners.** The seller (`alice`) and buyer (`operator`) are seeded at
  startup for a repeatable demo; there's no live multi-user marketplace UX.
- **Broker signature verify is best-effort.** In demo mode a failed CartMandate/
  mandate verification is tolerated so a runtime-listed skill (unknown to the
  broker's startup catalog) can still be hired via a local checkout.
- **Single-process SQLite.** WAL + `BEGIN IMMEDIATE` serialize writes; fine for the
  demo, not tuned for concurrency.

---

## Tests

```bash
cd marvis
uv run pytest tests/ -v      # includes the money-split arithmetic (tests/test_split.py)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the workflow state machine, money-path
invariants, the two-store model, and gap-detection logic.
