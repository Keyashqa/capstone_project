# Marvis — Phase 1 Implementation Plan

**Personal orchestrator that hires, pays, provisions, verifies, and settles with marketplace specialist agents.**

Status: PLAN ONLY — no code is written yet. Read [§9 Open Questions](#9-open-questions--assumptions) and confirm before any build starts.

Scope of this document: **Phase 1 only** — the hire → pay-base → provision-access → work → verify → pay-remainder loop, with 2–3 stub specialists. Explicitly **out of scope**: the builder agent, gap-detection, make-vs-buy economics, savings dashboard. Where the winner's codebase contains primitives a future builder phase will need, they are flagged **[PRESERVE]**.

---

## 1. Codebase summaries & what's reusable

### Folder 1 — `daedalus/` (last year's winner)

**What it actually is:** a *single-process* Google ADK + Gemini "self-expanding agent" system. It is **not** a networked A2A marketplace — there is no agent-to-agent network protocol. "Discovery" and "hiring" happen in-process through registries and the ADK `AgentTool` wrapper, with an LLM orchestrator deciding routing. This is the single most important thing to understand before reusing it: **its A2A story is in-process, LLM-mediated, not wire-level.**

Key patterns and where they live:

| Pattern | Where | What it does | Reusable for Marvis? |
|---|---|---|---|
| **Agent registry** | `models/agentsmith/models.py: InMemoryAgentRegline)`), `tools/registry/tools.py: call_registered_tool`, `run_agent_pipeline` | Orchestrator calls a sub-agent as a tool, or runs a named pipeline in an **isolated `InMemoryRunner`**. | Concept yes; mechanism replaced by HTTP A2A + scoped dispatch. |
| **Tool→agent wiring** | `agent.py`, `tools/.../tools.py: register_flight_tools()`, `build_agent_from_node()` | Tools are plain Python fns registered at startup; an agent gets only the tools whose names appear in `allowed_tool_names`, looked up from a curated `available_tools` dict. | **Yes** — `build_agent_from_node` filtering by allowlist is the in-process analog of the MCP grant proxy. **[PRESERVE]** |
| **Orchestration loop** | `prompt.py: ORCHESTRATOR_PROMPT` | "Never answer directly → inventory → classify → use existing OR create (Toolsmith/AgentSmith) → execute → summarize." | Concept reused for Marvis's intake/select; **but routing is LLM-driven and non-deterministic** — see conflict §"Standardization" below. |

**Future-phase flags [PRESERVE]:** the Toolsmith/AgentSmith *dynamic-creation* pipelines (`sub_agents/toolsmith_pipeline`, `agentsmith_pipeline`) are exactly the seed of a future **builder agent** (design → generate → test in ToolGym → register → golden set). Do not delete or architect them out. Keep: (a) the registry abstraction, (b) the `*Design` dataclasses with `allowed_tool_names`, (c) the "create-when-missing" branch in the orchestrator prompt as a stubbed/disabled route.

### Folder 2 — `adk_ucp_ap2_working_prototype/` (your proven money rail)

Two services that together implement a complete UCP/AP2 commerce loop:

**`ucp-commerce-agent/`** — an **ADK `Workflow` graph** (deterministic, no-LLM state machine) for cinema booking, plus FastAPI auth/wallet and a React A2UI frontend.

- **UCP wrapper** — `app/merchant_client.py: MerchantClient`:
  - `fetch_ucp_profile()` → `GET /.well-known/ucp` → returns `merchant_public_jwk` (used to verify CartMandates).
  - `mcp_call(method, params)` → `POST /mcp` JSON-RPC 2.0 (`search_movies`, `get_showtimes`, `create_checkout`).
  - `verify_mandate(...)` → `POST /mandates/verify`.
- **AP2 payment path** — `app/agent.py` nodes:
  - `create_checkout` → merchant signs a **CartMandate** (ES256 JWT over `CartContents`).
  - `verify_booking` → agent checks expiry + merchant signature.
  - `authorize_payment` → **HITL PIN gate** + wallet balance check.
  - `sign_ap2_mandates` → builds `PaymentMandateContents`, signs an **SD-JWT** with the **user's private key** (`keys.py: user_private_key_for(user_id)`).
  - `verify_mandates` → local double-verify, then `POST /mandates/verify`; merchant re-verifies both, cross-checks the session, records the booking, returns `booking_id`.
  - `booking_complete_terminal` → **only now** debits the wallet. **Critical AP2 rule: never debit before merchant confirms.**
- **Wallet / balance / receipt** — `app/wallet.py`: append-only **double-entry ledger**, hash-chained per account. Balance is *derived* (`SUM(delta_cents)`), never stored. `deposit` (system→user), `deduct` (user→system), `verify_chain` (tamper detection). **Accounts are arbitrary strings** (`"system"`, `user_id`) → trivially extensible to `escrow:*` and `agent:*` accounts. The merchant's `bookings` row (`payment_mandate_jwt`, `charged_cents`, `booking_id`) is the **receipt**.
- **Keys** — EC P-256 JWK per merchant and **per user** (`user_keys` table; generated on register in `auth.py`).
- **A2UI + HITL** — agent emits component trees tagged `<a2ui-json>…</a2ui-json>` over SSE; React renderer; pauses via `RequestInput(interrupt_id=…)` and resumes via `ctx.resume_inputs`; PIN confirmed through `/auth/verify-pin`. Workflow is **resumable** (`ResumabilityConfig`).

**`ucp-merchant-server/`** — standalone FastAPI merchant: `mcp_router.py` (catalog/checkout tools), `checkout.py` (signs CartMandate, stores sessions), `mandate_router.py` (`/mandates/verify` → verifies both mandates, records booking), `keys.py` (merchant JWK).

**Reusable verbatim or near-verbatim:** `wallet.py` (the ledger), the AP2 mandate sign/verify sequence, `MerchantClient`, the merchant-server skeleton, the JWK/auth machinery, the A2UI builders + RequestInput HITL pattern, and the **deterministic Workflow-graph control style** (this is the right backbone for Marvis).

---

## 2. Reuse map (every component Marvis needs)

| Marvis component | Source | Notes |
|---|---|---|istry` | `dict[name → ADK agent instance]` + parallel `dict[name → design]`. `register/has/get/get_design/list`. | **Yes** — this is the marketplace registry shape. |
| **Tool registry** | `models/toolsmith/models.py: InMemoryToolRegistry` | `dict[name → ToolMetadata{spec, func, version, tags}]`, versioned on re-register. | Yes — model the capability/tool catalog on it. |
| **"Agent card" (design)** | `models/agentsmith/models.py: AgentPipelineDesign`, `AgentNodeDesign` | Describes an agent: `name, node_type, description, instruction, **allowed_tool_names**, sub_agents`. | **Yes, critically.** `allowed_tool_names` is a per-node tool **allowlist** — the exact least-privilege primitive Marvis needs for capability grants. **[PRESERVE]** |
| **Discovery / lookup** | `tools/registry/tools.py: list_registered_tools`, `list_agent_pipelines`, `get_agent_pipeline_design` | Returns `[{name, description, type}]` for the LLM to inspect. | Yes — this is "browse the marketplace," adapted to return AgentCards. |
| **Hire / call another agent** | `agent.py` (`AgentTool(agent=pipe
| Marvis control loop (state machine) | **Adapt F2** (`Workflow` graph in `app/agent.py`) | Same node/edge/HITL/resumable style; new nodes. **Standardize on this over F1's LLM orchestrator** for the money path. |
| Marketplace registry | **Adapt F1** (`InMemoryAgentRegistry`) | `dict[agent_id → AgentCard]`; add `find(specialty)` / `list_cards()`. |
| **AgentCard** schema | **Net-new** (fuses F1 `AgentPipelineDesign` + F2 `UcpProfile`) | Pydantic model; served over HTTP like UCP's well-known. Carries `required_capabilities` (from F1 `allowed_tool_names`) + `pricing` split + `public_key` + `endpoint`. |
| A2A discovery + selection | **Adapt F1 concept**, **net-new transport** | F1 `list_*` → marketplace browse; selection ranking by **local Gemma** (or rule-based specialty match to save CPU). HTTP `/.well-known/agent-card` + `/a2a/tasks`. |
| UCP transaction wrapper | **Reuse F2** (`MerchantClient`) | Rename → `BrokerClient`/`HiringClient`; same `fetch_profile / mcp_call / verify_mandate`. |
| Hiring "merchant" / CartMandate signer | **Reuse F2 merchant-server skeleton** | The party that sells the *service* signs the CartMandate (broker or specialist — see §7b). |
| AP2 payment (base + completion split) | **Reuse F2** (`sign_ap2_mandates`, `verify_mandates`) | Ledger escrow (§7b-B): base → escrow at hire, escrow → agent on payout. |
| Wallet / ledger | **Reuse F2** (`wallet.py`) verbatim | Add `escrow:{task_id}` and `agent:{agent_id}` accounts. |
| Escrow record | **Net-new** | New table + ledger accounts; base/completion split state. |
| **Capability-grant record + scoped MCP proxy** | **Net-new** (modeled on F1 `allowed_tool_names` + `build_agent_from_node` filtering) | The hard new bit. §7c. |
| Work verification | **Net-new** | Deterministic checks + advisory Gemma score; **human PIN is the authority** (§7a). |
| Stub specialists (2–3) | **Net-new** | Scoped system prompt + fixed skills + exactly ONE required tool; run on **local Gemma via Ollama**. |
| A2UI human PIN gate (CORE) | **Reuse F2** (A2UI builders + `RequestInput` + `/auth/verify-pin`) | PIN gate at hire (authorize base) and at payout (verify + release completion). §6. |

---

## 3. Target architecture (Phase 1)

Single repo, three runnable processes (keep F2's two-service split; add the marketplace). All local.

```
                                   ┌──────────────────────────────────────────┐
                                   │              USER (browser)               │
                                   │   React A2UI UI  +  PIN modal (optional)  │
                                   └───────────────▲───────────┬──────────────┘
                                          SSE A2UI │           │ clicks / PIN
                                                   │           ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  MARVIS  (ADK Workflow graph · local Gemma/Ollama) process :8000               │
│                                                                                │
│  intake → discover → select → [approve?] → hire-checkout → pay-base →          │
│  grant-capability → dispatch → collect → revoke → verify → [approve?] →        │
│  pay-completion → settle → receipt                                             │
│                                                                                │
│  ├─ MarketplaceRegistry (in-mem, adapted from F1)                              │
│  ├─ BrokerClient (UCP wrapper, reused from F2 MerchantClient)                  │
│  ├─ AP2 sign/verify (reused from F2)                                           │
│  ├─ wallet.py ledger  (reused from F2; accounts: user, escrow:*, agent:*)      │
│  └─ CapabilityBroker  (issues/revokes grants)  ──────────────┐                 │
└───────┬───────────────┬───────────────────────┬─────────────┼─────────────────┘
        │ A2A           │ UCP /mcp + AP2         │ A2A dispatch │ holds REAL creds
        │ get card      │ /mandates/verify       │ task+grant   │ enforces allowlist
        ▼               ▼                        ▼              ▼
┌───────────────┐ ┌───────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
│ MARKETPLACE / │ │ HIRING MERCHANT   │ │ SPECIALIST AGENT │ │  SCOPED MCP PROXY     │
│ BROKER  :8002 │ │ (broker side)     │ │  (Gemma/Ollama)  │ │  :8003                │
│ serves Agent  │ │ signs CartMandate │ │ system prompt +  │ │ allowlist + TTL +     │
│ Cards (A2A)   │ │ verify_mandate    │ │ fixed skills;    │ │ usage caps; proxies   │
│ + registry    │ │ records "booking" │ │ NO live tools    │ │ to real MCP tools     │
└───────────────┘ └───────────────────┘ └────────▲─────────┘ └──────────▲───────────┘
                                                  │ uses lent tools via grant_token │
                                                  └─────────────────────────────────┘
```

**Notes on the topology**
- **Marketplace/Broker (:8002)** combines F1's registry (serving AgentCards over A2A) with F2's merchant-server (signing the hiring CartMandate, verifying mandates). Keeping them in one process is fine for the demo; they are logically distinct (A2A vs UCP/AP2).
- **Scoped MCP Proxy (:8003)** is the heart of "Marvis provisions access." It alone holds the real tool credentials/endpoints. Specialists never receive raw tools — only a `grant_token` they present to the proxy, which enforces the allowlist, TTL, and usage caps. This is the wire-level version of F1's `build_agent_from_node` allowlist filtering. **[PRESERVE]** — a builder agent later mints capabilities the same way.
- **Specialists** are separate logical agents on **Gemma via Ollama (CPU)**. For the demo they can run in-process behind an A2A-style interface (a function call) or as a tiny FastAPI per specialist. Recommendation: **one process, A2A-shaped interface** (see §9 assumption A1) so the loop is demoable without orchestrating many servers, while keeping the call boundary clean enough to split later.

---

## 4. Data models

All money in integer **cents**. All times ISO-8601 UTC. No secrets in any of these — private keys live only in the keystore/DB as in F2.

### 4.1 AgentCard (marketplace listing)
```
AgentCard {
  agent_id: str                  # "spec-twitter-writer-001"
  name: str
  version: str
  description: str
  specialties: [str]             # ["content-writing","social-copy"]  ← matched against task
  skills: [ {name, description} ]# the specialist's FIXED harness (informational)
  model: str                     # "ollama/gemma:2b"  ← Gemma routing marker
  required_capabilities: [       # ← from F1 allowed_tool_names; what Marvis must provision
     { mcp_server: str, tool_name: str, why: str }
  ]
  pricing: { currency: "USD", base_fee_cents: int, completion_fee_cents: int }
  endpoint: str                  # A2A dispatch URL (or in-proc handle id)
  public_key: JWK                # specialist signs result attestation / CartMandate
  io: { input_schema: {...}, output_schema: {...} }
  reputation: float | null       # future; nullable in Phase 1
}
```

### 4.2 Task
```
Task {
  task_id: str
  user_id: str
  created_at: str
  goal_nl: str                   # "make my twitter post"
  spec: {                        # parsed by Marvis (local Gemma)
     type: str                   # "content_writing"
     inputs: {...}               # topic, tone, length…
     acceptance_criteria: [str]  # drives verification (§7a)
  }
  selected_agent_id: str | null
  status: enum                   # see §5 node names
  grant_id: str | null
  txn_id: str | null
  result: {...} | null           # specialist output
  verification: VerificationResult | null
}
```

### 4.3 Transaction / Escrow record (base + completion split)
```
HiringTxn {
  txn_id: str
  task_id: str
  user_id: str
  agent_id: str
  currency: "USD"
  base_fee_cents: int
  completion_fee_cents: int
  total_cents: int               # base + completion
  escrow_account_id: str         # "escrow:{task_id}"
  base_status: enum              # HELD | RELEASED | REFUNDED
  completion_status: enum        # PENDING | RELEASED | REFUNDED
  cart_mandate: {...}            # the hiring CartMandate (signed by broker/specialist)
  base_payment_mandate_id: str | null
  completion_payment_mandate_id: str | null
  booking_id: str | null         # broker "receipt"
  base_journal_id: str | null    # ledger cross-ref
  completion_journal_id: str | null
  created_at, updated_at
}
```

### 4.4 Wallet (reuse F2 ledger — accounts only extended)
```
ledger row (unchanged):
  id, journal_id, account_id, delta_cents, counterpart,
  reason, reference_id, prev_hash, entry_hash, created_at
Accounts used in Marvis:
  "system"            (top-ups source)
  "<user_id>"         (Marvis's owner wallet)
  "escrow:<task_id>"  (funds held during a hire)
  "agent:<agent_id>"  (specialist earnings)
Balance = SUM(delta_cents) per account; sum across ALL accounts == 0 always.
```

### 4.5 Capability-grant record (which MCP tools were lent, to whom, scope, expiry)
```
CapabilityGrant {
  grant_id: str
  task_id: str
  agent_id: str                  # grantee
  issued_by: str                 # "marvis" / user_id
  allowed_tools: [               # the WHITELIST. Phase 1: EXACTLY ONE entry per grant.
     {
       mcp_server: str,          # "twitter-mcp"
       tool_name: str,           # "post_tweet"
       arg_constraints: {...}    # e.g. {"account_id": "fixed:@me", "max_len": 280}
     }
  ]
  limits: {
     max_calls_total: int,
     max_calls_per_tool: { tool_name: int },
     rate_per_min: int,
     data_scope: {...}           # optional row/record scoping
  }
  task_bound: true               # grant only valid for this task_id
  issued_at: str
  expires_at: str                # TTL — hard wall-clock expiry
  status: enum                   # ACTIVE | EXPIRED | REVOKED | CONSUMED
  usage: { calls_total: int, per_tool: {tool_name:int} }
  grant_token: str               # opaque secret presented to the MCP proxy (NOT a tool cred)
}
```
**Least-privilege invariant:** a specialist can reach a tool **iff** there exists an `ACTIVE`, non-expired grant for its `agent_id` + `task_id` whose `allowed_tools` contains that `tool_name`, AND usage caps are not exceeded. The proxy is the only holder of real credentials; the `grant_token` is not a credential, it is a capability handle.

---

## 5. Control flow (state machine / graph)

Built as an ADK `Workflow` (F2 style): deterministic edges, HITL via `RequestInput`, resumable. The LLM (**local Gemma/Ollama**) is used only in `intake_task`, `select_specialist`, and the advisory part of `verify_work`; the **work** happens inside the specialist (also Gemma). Two human **PIN gates** (hire + payout) are ON. Node name == `Task.status`.

```
START
  └─▶ intake_task            Gemma parses goal_nl → spec{type,inputs,acceptance_criteria}
        └─▶ discover_specialists   A2A: fetch AgentCards from marketplace, filter by specialty
              ├─[none]─▶ no_specialist_terminal
              └─[found]─▶ select_specialist   Gemma ranks cards → pick agent_id, read pricing
                    └─▶ authorize_base_payment   *** HUMAN PIN GATE #1 ***  show hire cost; balance >= base?
                          ├─[cancelled/bad-pin]─▶ cancelled_terminal
                          └─[confirmed]─▶ create_hire_checkout   UCP: broker signs CartMandate (base+completion)
                                └─▶ verify_hire_cart   check expiry + broker signature
                                      ├─[invalid]─▶ hire_invalid_terminal
                                      └─[valid]──▶ pay_base_into_escrow
                                                  │   AP2 sign+verify; ledger: user → escrow:{task} (base)
                                                  └─▶ grant_capability   *** PROVISION ACCESS ***
                                                        │  mint CapabilityGrant (the ONE allowed tool,
                                                        │  TTL, caps, task_bound); register grant
                                                        └─▶ dispatch_to_specialist   A2A: send {task.spec, grant_token, proxy_url}
                                                              │  specialist (Gemma) runs its skills, calls the lent MCP tool
                                                              └─▶ collect_result   receive result + specialist attestation
                                                                    └─▶ revoke_capability   *** REVOKE ACCESS ***
                                                                          │  grant.status = REVOKED (also auto-EXPIRES on TTL)
                                                                          └─▶ verify_work   deterministic checks + advisory Gemma score (§7a)
                                                                                ├─[hard-fail]─▶ verify_failed   completion refunded (§7b) ─▶ refunded_terminal
                                                                                └─[checks-pass]─▶ approve_payout   *** HUMAN PIN GATE #2 (the verification) ***
                                                                                      ├─[rejected/bad-pin]─▶ verify_failed
                                                                                      └─[approved]─▶ pay_completion
                                                                                            │  AP2 release; ledger: escrow → agent (base+completion)
                                                                                            └─▶ settle_escrow   close HiringTxn, assert escrow:{task}==0
                                                                                                  └─▶ receipt_terminal   booking_id + ledger refs + result
```

**Guaranteed cleanup:** `revoke_capability` runs on **every** path out of `dispatch` (success, verify-fail, timeout, error). Grants additionally self-expire by TTL, so even a crashed Marvis cannot leave standing access. This dual mechanism (explicit revoke + TTL) is the safety property to test (§8 M7).

**Failure/timeout edges (collapsed above for readability):** `dispatch_to_specialist` has a timeout → `revoke_capability` → `verify_failed` (escrow refunds base per policy). Any AP2 verification failure routes to a terminal without moving money (F2's invariant: never debit before confirm).

---

## 6. Where each protocol lives (+ A2UI human PIN gate)

| Protocol | Role in Marvis | Concretely |
|---|---|---|
| **A2A** | Specialist **discovery, selection, dispatch** | `GET /.well-known/agent-card` on marketplace → AgentCards; `POST /a2a/tasks` to dispatch `{spec, grant_token, proxy_url}`; specialist returns result + attestation. (Adapted from F1's `list_*` + `AgentTool`, now over HTTP.) |
| **UCP** | Wraps the **hire as a commerce transaction** | Broker exposes UCP profile + `create_checkout` (the "product" is the specialist's service) → returns hiring **CartMandate**. Reuses F2 `MerchantClient`. |
| **AP2** | **Payment execution** (base + completion) | F2 `sign_ap2_mandates` / `verify_mandates`; double-mandate; ledger debits **only after** broker confirms. Base → escrow at hire; escrow → agent on payout (§7b-B). |
| **MCP + skills** | Specialist's **fixed skills** (its own harness) + the **lent tools** Marvis provisions | Skills ship with the specialist; live tools are reached **only** through the **Scoped MCP Proxy** under an active `CapabilityGrant`. (Wire-level version of F1 `allowed_tool_names`.) |
| **A2UI** *(CORE — PIN gates ON)* | **Human PIN approval** at hire and at payout | Reuse F2 A2UI builders + `RequestInput(interrupt_id=…)` + `/auth/verify-pin`. Two PIN surfaces: **PIN gate #1 — authorize_base_payment** ("Hire X for $base now, $completion on delivery — enter PIN") and **PIN gate #2 — approve_payout** ("Work checks passed (advisory score N) — enter PIN to verify & release $completion"). Gate #2 is the binding human verification (§7a). |

---

## 7. The hard design questions

### 7a. How does Marvis verify the work? (trust before final payment)

The acceptance criteria parsed in `intake_task` are the contract; verification scores the result against them.

- **Option A — Deterministic checks only.** Schema/shape validation + rule checks (e.g. tweet ≤ 280 chars, non-empty, contains required hashtag, no banned words). *Pros:* fast, free, fully reproducible, no extra model calls (matters on CPU). *Cons:* can't judge quality/relevance; easy for a lazy specialist to pass.
- **Option B — LLM-as-judge (local Gemma).** Marvis re-reads `goal_nl` + `acceptance_criteria` + result and returns `{pass, score, reasons}`. *Pros:* judges relevance/quality; reuses the local Gemma — no extra service/key. *Cons:* judge runs on the *same model family* the specialist used (no independence) and is non-deterministic — so its verdict must be **advisory only**, never the final authority.
- **Option C — Hybrid: deterministic pre-filter + advisory Gemma judge + AUTHORITATIVE human PIN gate.** Deterministic checks are a hard pre-filter; if they pass, the Gemma judge produces an advisory `{score, reasons}` shown to the human; the **human approves the payout with a PIN** (reusing F2's `/auth/verify-pin`), which is the binding verification before final payment.

**Recommendation: C (Hybrid with human PIN as the authority).** Per your decision, **the final verification is a human PIN approval**, not the LLM. The deterministic checks catch cheap failures for free and the Gemma judge gives the human a quality signal to decide on — but the PIN is what releases the completion payment. This sidesteps the "judge has no independence from Gemma" problem entirely (the human is the independent verifier) and mirrors F2's `verify_mandates` "auto-check, then human review" structure exactly — reuse that node shape, with the human-review branch wired to the PIN modal instead of a text prompt.

### 7b. How is the base/completion split held and released? (escrow vs two direct payments)

- **Option A — Two direct AP2 payments.** Pay `base` to `agent:{id}` at hire; pay `completion` to `agent:{id}` after verify. *Pros:* simplest; two clean reuses of F2's existing AP2 cycle; no new escrow concept. *Cons:* base is already in the specialist's hands before any work — refund on failure requires a reverse payment (trust/clawback problem); no single "held" state to show.
- **Option B — Escrow account in the ledger.** At hire, move **base+completion** `user → escrow:{task_id}`. On verify-pass, `escrow → agent`. On fail, `escrow → user` (refund), or split (base non-refundable, completion refunded) per policy. *Pros:* funds provably held, not yet the specialist's; refund is a normal ledger move (no clawback); single source of truth; demos beautifully ("$X held in escrow"). The F2 ledger already supports arbitrary accounts, so this is a small extension. *Cons:* one new account-type + release logic; AP2 mandate semantics need a tiny rethink (you're authorizing into escrow, releasing on a second event).
- **Option C — Hybrid: AP2 mandate at hire authorizes the full amount; ledger escrow holds it; completion is a *release event*, not a second user-signed payment.** One user signature (at hire) covers both tranches; Marvis releases the completion tranche after verify without re-prompting the user.

**Recommendation: B (ledger escrow), with the base treated as a non-refundable hiring fee and the completion fully refundable on verify-fail** (the classic "deposit + on-delivery" structure your prompt implies). It maps onto the existing double-entry ledger with one new account prefix, keeps F2's "never pay before confirm" invariant for the *completion* tranche, and gives the cleanest demo + the cleanest refund path.

**Two human PIN gates (confirmed):** a PIN at hire authorizes the **base** moving `user → escrow`, and a PIN at payout authorizes the **completion** release `escrow → agent`. The payout PIN *is* the human verification gate from §7a — it doubles as both "I verified the work" and "release the money," so there is no extra prompt beyond these two. Both reuse F2's identical `/auth/verify-pin` flow.

### 7c. How does Marvis grant scoped, restricted MCP access — and revoke/expire it?

This is the defining new mechanic. "The specialist does not come with live tools; Marvis lends them, scoped and time-limited, then revokes."

**What "scoped" means concretely** (all enforced by the proxy, per `CapabilityGrant` §4.5):
- **Which tools:** an explicit allowlist. **Phase 1 (confirmed): exactly ONE tool per specialist** — each stub declares a single `required_capabilities` entry, and the grant lends precisely that one tool, nothing else. (The model still holds a *list* so multi-tool grants are a later config change, not a refactor. Direct descendant of F1 `allowed_tool_names`.)
- **What limits:** `max_calls_total`, `max_calls_per_tool`, `rate_per_min`, **argument constraints** (e.g. `post_tweet.account_id` pinned to the owner's handle; `max_len` 280), optional `data_scope`.
- **Time/task limits:** hard `expires_at` (TTL, e.g. 5 min) **and** `task_bound` (valid only for this `task_id`).

**How access is handed over — three options:**
- **Option A — Lend raw MCP endpoints/credentials to the specialist.** *Reject.* Violates least-privilege; once a specialist holds a credential you cannot truly revoke it, and you can't enforce per-call caps.
- **Option B — Capability token + Scoped MCP Proxy (recommended).** Marvis mints a `grant_token` and registers the `CapabilityGrant` with the proxy. The specialist is dispatched `{grant_token, proxy_url}` only. Every tool call goes `specialist → proxy(grant_token, tool, args)`; the proxy checks: grant ACTIVE + not expired + tool in allowlist + caps not exceeded + args satisfy constraints, then calls the **real** tool (whose credentials only the proxy holds) and increments usage. Revoke = flip `status=REVOKED` (or TTL lapse) → all further calls 403. *Pros:* true least-privilege, real revocation, per-call enforcement, full audit trail, **specialist never touches a credential**. Directly generalizes F1's `build_agent_from_node` allowlist filtering to the wire. *Cons:* one new service to build (small — it's an allowlist + counter + dispatcher).
- **Option C — In-process tool injection (F1-exact).** Marvis builds the specialist's tool list at dispatch by filtering a curated `available_tools` dict against the grant's allowlist (literally `build_agent_from_node`). *Pros:* zero new infra; fastest to demo; already proven in F1. *Cons:* "revocation" is just not-passing-the-tool (no live revoke mid-task), no wall-clock TTL enforcement, only works while specialists are in-process.

**Recommendation: B for the headline mechanic, with C as the day-1 fallback.** Build the loop first with **C** (in-process allowlist filtering — proven, fast, lets every other milestone land), then upgrade the `grant_capability`/`dispatch`/`revoke` nodes to the **proxy (B)** to demonstrate *real* scoped+revocable+expiring access. The data model (§4.5) is identical for both, so the upgrade is localized to three nodes + the proxy service. **[PRESERVE]** — a future builder agent mints capabilities through the same proxy.

---

## 8. Build sequence — small, independently testable milestones

Each milestone has a one-line **done-test**. Order is dependency-driven; money/grant correctness gated by tests before the loop is wired end-to-end.

| # | Milestone | Done-test (run to confirm) |
|---|---|---|
| **M0** | Repo skeleton: copy F2 `wallet.py`, `db.py`, `keys.py`, `MerchantClient`, merchant-server; 3 processes boot. | `curl :8000/health && :8002/.well-known/agent-card && :8003/health` all 200. |
| **M1** | Ledger extended with `escrow:*` / `agent:*` accounts; top-up works. | Top-up $50 then `get_balance(user)==5000` and `sum(all accounts)==0`. |
| **M2** | MarketplaceRegistry + AgentCard schema; seed 2–3 stub specialists; A2A `/.well-known/agent-card`. | `GET /.well-known/agent-card` returns ≥2 cards incl. a `content-writing` specialist with `pricing.base/completion`. |
| **M3** | `intake_task` + `discover_specialists` + `select_specialist` (Gemma or rule-based match). | Input "Hire a content writing specialist to make my twitter post" → selects the twitter-writer card (assert `selected_agent_id`). |
| **M4** | **PIN gate #1** (`authorize_base_payment`) + hire CartMandate + `pay_base_into_escrow` (AP2 + ledger escrow, §7b-B). | Correct PIN → `escrow:{task}==base_fee`, `user` reduced by base, `verify_chain(user).valid==true`; wrong/absent PIN → no money moves. |
| **M5** | Stub specialist runs on **local Gemma/Ollama**, returns a tweet (no tools yet). | `dispatch_to_specialist` returns non-empty result from `ollama/<gemma>` within the configured timeout. |
| **M6** | `grant_capability` (Option C: in-proc allowlist, **one tool**) + specialist uses the lent tool. | Specialist can call only its single allow-listed tool; calling any other tool raises `PermissionError`. |
| **M7** | `revoke_capability` + TTL expiry. | After `revoke` (and after TTL), a tool call by the specialist is denied; grant `status` is `REVOKED`/`EXPIRED`. |
| **M8** | `verify_work` = deterministic checks + advisory Gemma score (§7a-C). | A tweet violating a criterion (e.g. >280 chars) hard-`fail`s; a valid one passes checks and yields an advisory score. |
| **M9** | **PIN gate #2** (`approve_payout`) + `pay_completion` + `settle_escrow`. | Correct PIN → `agent:{id}==base+completion`, `escrow:{task}==0`, `completion_status==RELEASED`; reject/wrong PIN → routes to refund. |
| **M10** | Full loop terminal + receipt; refund path on fail. | Happy path → `receipt_terminal` with `booking_id`+result; forced verify-fail (or payout reject) → completion refunded to `user`, escrow==0. |
| **M11** | A2UI surfaces rendered in React for both PIN gates (hire summary, payout/verify summary with advisory score). | Both gates render as A2UI cards in the browser and the PIN modal drives `/auth/verify-pin`. |
| **M12** *(opt)* | Upgrade grant to Scoped MCP Proxy (Option B, :8003). | Same as M6/M7 but tool calls go through the proxy; a revoked grant returns HTTP 403 mid-task. |

A full headless demo is shippable at **M10**; **M11** adds the visible A2UI/PIN UX; **M12** is the "real scoped+revocable access" upgrade.

---

## 9. Open questions & assumptions

Confirm/correct these before any code:

**Assumptions made (will proceed on these unless you say otherwise):**
- **A1 — Specialists run in-process behind an A2A-shaped interface for Phase 1** (one Python process, clean call boundary), not as N separate servers. Keeps the demo runnable; splittable later. *(Affects §3, M5.)*
- **A2 — Standardize Marvis's control flow on F2's deterministic `Workflow` graph**, not F1's LLM orchestrator. The LLM (**local Gemma**) is used only inside `intake_task`/`select_specialist`/advisory `verify_work`. *(Resolves the F1↔F2 control-flow conflict.)*
- **A3 — Standardize the agent descriptor on a single `AgentCard`** that fuses F1's `*Design` (esp. `required_capabilities` ← `allowed_tool_names`) with F2's `UcpProfile`. *(Resolves the F1↔F2 "how to describe/register an agent" conflict.)*
- **A4 — Escrow model (§7b-B):** base = non-refundable hiring fee; completion = refundable on verify-fail.
- **A5 — Grant mechanic starts as in-process allowlist (§7c-C), upgrades to proxy (§7c-B) at M12.**
- **A6 — One owner/user wallet** (Marvis acts for a single owner in Phase 1); specialists are `agent:*` ledger accounts. Reuses F2 auth/keys as-is.
- **A7 — Marketplace and hiring-merchant/broker live in one process (:8002)** even though logically distinct (A2A vs UCP/AP2).
- **A8 — No real external tools in Phase 1**: the "lent MCP tool" is a mock (e.g. a fake `post_tweet` that echoes) so the grant/scope/revoke mechanics are demonstrable without real credentials. *(No API keys anywhere — consistent with the constraint.)*

**Decisions CONFIRMED:**
- ✅ **Hire signer → central broker** (broker-signed CartMandate; §7b/§3). Marketplace + hiring-merchant in one process (:8002).
- ✅ **Payment split → ledger escrow, base non-refundable** (§7b-B / A4). Hire moves base+completion into `escrow:{task}`; pass → escrow pays specialist; fail → completion refunded, base kept.
- ✅ **Verification → human PIN is the authority.** Deterministic pre-filter + advisory Gemma score, then a binding **human PIN approval** at payout (§7a-C, §6).
- ✅ **Two human PIN gates ON** — gate #1 authorizes the base at hire, gate #2 verifies + releases the completion at payout. Both reuse F2 `/auth/verify-pin`. *(Resolves old Q1.)*
- ✅ **All LLM work runs on the user's local Gemma (Ollama)** — Marvis's intake/select/advisory-judge AND the specialists. **No Gemini; no API keys.** *(Overrides the original "Marvis on Gemini" constraint, per your instruction.)*
- ✅ **One tool per specialist** — each stub declares exactly one `required_capabilities` entry; grants lend precisely that one tool. *(Resolves old Q3.)*
- ✅ **Grant mechanic → in-process allowlist first (§7c-C, M6/M7), upgrade to Scoped MCP Proxy later (§7c-B, M12).**

**Open questions still needing your input:**
- **Q1 — Exact Gemma tag** you'll run locally (e.g. `gemma:2b`, `gemma2:9b`) and rough per-task latency on your CPU? I'll only use this to set the `dispatch_to_specialist` timeout (M5) and decide whether the advisory judge call is worth its latency. Everything else is model-agnostic.

---

## Model-routing notes (all local Gemma via Ollama) — where it matters

- **Everything LLM runs on the user's local Gemma** through ADK's `LiteLlm` wrapper (`model="ollama/<your-gemma-tag>"`): Marvis's `intake_task` (NL→spec), `select_specialist` (ranking) **and** the specialists' own work. One model, no Gemini, **no API keys** (Ollama is local/keyless).
- **The verification authority is the human PIN, not the model.** Because Marvis's advisory judge and the specialist share the same Gemma, the judge has no independence — so it is advisory only and the human PIN at payout is binding. *(§7a)* This is actually a feature: it removes any "judge is the same model as the worker" objection.
- **CPU inference is slow → minimize and time-box LLM calls.** `dispatch_to_specialist` **must** be async with a generous, configurable timeout, and the timeout edge **must** route through `revoke_capability` (never leave a grant standing while waiting on a slow Gemma). Consider making `select_specialist` rule-based (specialty string match) to avoid an LLM call on the hot path; reserve Gemma for intake parsing and the actual specialist work. *(§5, M5/M7)*
- Keep specialist prompts/skills small and feed lent-tool results back compactly; Gemma on CPU degrades fast with long contexts.
- Single Ollama instance serves Marvis + all specialists; serialize or queue calls so concurrent requests don't thrash CPU.

---

*End of plan. Awaiting approval before building. Suggested first action on approval: M0–M2 (skeleton + ledger + marketplace), since everything else depends on them.*
