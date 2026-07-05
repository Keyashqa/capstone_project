# Marvis — Architecture

Technical companion to [README.md](README.md). This documents the **shipped code**;
where it diverges from the planning docs (`../plan*.md`, `../audit.md`), the code is
authoritative and the divergence is flagged.

---

## 1. Process & data model

| Process | Port | Entry point | State |
|---|---|---|---|
| Agent server | 8000 | `app/fast_api_app.py` (`uvicorn app.fast_api_app:app`) | `marvis.db` (SQLite) |
| Broker server | 8002 | `broker_server/app.py` | `broker.db` (hiring sessions only — **no ledger**) |
| Frontend | 5173 | `frontend/` (Vite dev) | — |
| ~~MCP proxy~~ | ~~8003~~ | stub in `references/proxy_server/` | **not run** — grant enforcement is in-process |

The gdocs MCP server is **not** a long-running process; it's spawned per call as a
stdio subprocess (`uv run workspace-mcp --transport stdio`) by
`app/capability/gdocs_session.py`.

**`marvis.db` tables** (`app/db.py`): `users`, `user_keys`, `auth_sessions`,
`adk_sessions`, `wallets`, `ledger` (the money), `tasks`, `hiring_txns`,
`capability_grants` (audit log; the in-memory registry is the live authority),
`job_receipts`, and `skill_ownership` (who listed what, and where earnings route).

---

## 2. The workflow graph (state machine)

`app/agent.py` defines an ADK `Workflow` — a **deterministic** directed graph. No LLM
chooses an edge; each node returns an `Event` with a named `route`, and the edge map
sends it on. Nodes correspond 1:1 to a task's status.

```
START → intake_task ─┬─ intake_failed → no_specialist_terminal
                     └─ parsed → discover_specialists ─┬─ none → no_specialist_terminal
                                                       └─ found → select_specialist
select_specialist ─┬─ none   → no_specialist_terminal
                   ├─ market → authorize_base_payment      (PIN #1)
                   ├─ owned  → grant_capability            (free, self-issued)
                   └─ gap    → propose_build               (PIN #B — commission the builder)

authorize_base_payment ─┬─ cancelled → cancelled_terminal
                        └─ confirmed → create_hire_checkout → verify_hire_cart
propose_build          ─┬─ cancelled → cancelled_terminal
                        └─ confirmed → create_hire_checkout → verify_hire_cart

verify_hire_cart ─┬─ invalid → hire_invalid_terminal
                  └─ valid   → pay_base_into_escrow → grant_capability

grant_capability ─┬─ grant_failed → verify_failed
                  └─ granted      → dispatch_to_specialist ─┬─ dispatch_failed → revoke_capability
                                                            └─ dispatched     → collect_result → revoke_capability

revoke_capability ─┬─ post_work  → verify_work
                   └─ post_build → validate_build

verify_work ─┬─ hard_fail         → verify_failed → refunded_terminal
             ├─ checks_pass       → approve_payout (PIN #2) ─┬─ rejected → verify_failed → refunded_terminal
             │                                               └─ approved → pay_completion → settle_escrow
             ├─ owned_hard_fail   → output_failed_terminal   (free run — nothing to refund)
             └─ owned_checks_pass → receipt_terminal          (free run — nothing to release)

validate_build ─┬─ invalid → build_failed → refunded_terminal
                └─ valid   → pay_completion → settle_escrow

settle_escrow ─┬─ settled       → receipt_terminal
               └─ build_settled → persist_skill → discover_specialists   ↺ (self-growing loop)
```

**Three routes out of `select_specialist`** (`app/workflow/nodes/discover.py`):

- **market** — a listed/platform marketplace skill. Runs the full paid hire loop.
- **owned** — a skill in Marvis's owned library. Skips payment entirely: routes
  straight to `grant_capability`, and after verify goes to `receipt_terminal` with
  `total_cents = 0`. **Owned runs move no money.**
- **gap** — no skill scores a platform match. Commission the SkillBuilder; on success
  `persist_skill` writes the new skill to the owned store and loops back to
  `discover_specialists`, so the original request now resolves.

**Why deterministic routing matters:** the LLM (Gemma) is confined to `intake_task`
(parse goal → typed spec), `verify_work` (advisory score only — never gates money by
itself), and the specialist runtime. Money, grants, and control flow are pure code.

---

## 3. Gap detection & skill selection

`select_specialist` scores every candidate card and routes on the best score.

**Platform routing** — each platform skill_id encodes platform + role
(`skill-twitter-writer`, `skill-linkedin-reviewer`). Score (`_score`):

```
+2  if the task's platform key (twitter/instagram/linkedin) appears in skill_id
+1  if the role matches (writer vs reviewer, inferred from the goal text)
```

- Tie-break (`_rank_key`): prefer a real **listed** card (`owner_account` set) over the
  platform's unowned stub — so a seller's listing wins the hire and the earnings flow.
- **Gap** iff the best platform score `< 2` (`_GAP_SCORE_THRESHOLD`): no card covers the
  platform, so trigger a build. This is what turned the old silent mis-serve (a LinkedIn
  task answered by a Twitter writer) into an explicit build trigger.

**Custom skills** — user-uploaded skills (`POST /skills/create`) carry `match_keywords`
and are matched by free-form keyword overlap on the raw goal, not the closed
platform×role router. A custom skill wins only when `custom_score >= 1` **and**
`custom_score * 2 > platform_score`, so the flagship "write a tweet" still routes to the
Twitter skill while "draft a cold outreach email" can route to a listed Email Writer the
platform router can't serve. This is the **domain** extensibility axis on top of
platform × task.

---

## 4. Two-lifetime store model

Two invariants the whole system rests on:

| Store | Instance | Lifetime | Payment |
|---|---|---|---|
| **Marketplace** | `get_registry()` | permanent listing, **rented per hire** | base + completion, split at payout |
| **Owned** | `get_owned_registry()` | permanent, **free for its owner** | none (`total_cents = 0`) |

Both are `InMemorySkillRegistry` (`app/marketplace/skill_registry.py`), keyed by the
**composite `(owner_id, skill_id)`** so two owners can list the same slug without
colliding. `get`/`has` default `owner_id="marvis"` for back-compat, so Phase 1/2 callers
that pass only a `skill_id` still resolve.

Skill **content stays on disk** (`skill.json` + `instruction.md`), owner-namespaced:
- marketplace: `app/marketplace/agent-skills/<owner_id>/<slug>/` (flat `<slug>/` = owner `marvis`)
- owned: `app/owned-skills/<owner_id>/<slug>/`

Seeds are idempotent (`seed_catalog`, `seed_owned_library`, `seed_demo`), so registries
survive restarts.

**Grant lifetime is the opposite of skill lifetime** — deliberately ephemeral:

| | Skill | Capability grant |
|---|---|---|
| Lifetime | permanent (on disk + registry) | one task, ≤ 5 min TTL |
| Authority | catalog entry | live allowlist (`InMemoryGrantRegistry`) |
| Revocation | never (it's a listing) | on every dispatch exit **and** TTL expiry |

---

## 5. Capability grants (least privilege)

`app/capability/grant.py` + `app/workflow/nodes/capability.py`.

A `CapabilityGrant` minted at `grant_capability` carries:

- **exactly one** allowed tool (`AllowedTool`), taken from the skill's single
  `required_capabilities[0]`;
- a **TTL** (`GRANT_TTL_SECONDS`, default 300s);
- **call caps** — `max_calls_total = 5`, `max_calls_per_tool = {tool: 3}`;
- **arg constraints**, e.g. `create_doc` is bound with `title` = `prefix:"<approved title>"`
  and `content` = `{max_len: 4000}`; `get_doc_content` is bound to a `fixed:<doc_id>`.

`check_and_use(token, tool, args)` enforces, in order: token exists → not past TTL →
`ACTIVE` status → tool in allowlist → caps not exceeded → arg constraints satisfied,
then records usage. It returns `(allowed, reason)`; the specialist runtime (in
`app/runtime/specialist.py`) calls it **before** touching the gdocs session, so a denied
call never reaches Google.

**Dual revoke:** `revoke_capability` runs on the `dispatched` *and* `dispatch_failed`
edges (so success or failure both revoke), and the grant also self-expires by TTL. The
builder skill declares **zero** capabilities — legitimate; no grant is minted and it
dispatches without a token.

**The agent never holds a credential.** OAuth tokens live only in the orchestrator's
`GDocsSession`. The specialist holds only the opaque `grant_token` — a capability
handle, not a secret.

---

## 6. Money path & invariants

`app/wallet.py` (ledger) · `app/escrow/operations.py` (escrow) · `app/escrow/split.py`
(split math) · `app/workflow/nodes/hire.py` + `payout.py` (the nodes).

### Accounts (arbitrary strings; an account exists once a row references it)

| Account | Meaning |
|---|---|
| `system` | top-up source/sink |
| `<user_id>` | a user's spendable wallet (buyers **and** sellers — earnings land here) |
| `escrow:<task_id>` | funds held during one hire |
| `broker` | platform commission + full payout of unowned skills |
| `agent:<agent_name>` | Phase-1 specialist earnings — **vestigial** for listed/unowned skills now |

### Invariants (all enforced in code)

1. **Balance is never stored** — always `SUM(delta_cents)` (`_balance_sync`).
2. **Zero-sum** — every movement is a `_double_entry` writing `−amount` and `+amount`
   in one journal, so `get_all_account_sum() == 0` always.
3. **Hash-chained** — each ledger row carries `prev_hash`/`entry_hash` (sha256 over the
   row + previous hash); `verify_chain(account)` detects tampering.
4. **Never debit before confirm** — escrow only after PIN #1; release only after PIN #2.
5. **Base non-refundable / completion refundable** — see the split and the fail path.
6. **Escrow settles to 0** — `settle_escrow` asserts `get_escrow_balance(task_id) == 0`.

### The hire (funds in)

`pay_base_into_escrow` builds an **AP2** `PaymentMandateContents`, signs it as an SD-JWT
with the user's key, best-effort verifies with the broker, then moves
`base + completion` from `<user_id>` → `escrow:<task_id>` in one transfer
(reason `hire_escrow`). *(Despite the node name, base and completion are escrowed
together.)*

### The 3-way split (funds out — `app/escrow/split.py::compute_split`)

Commission is floored on the completion tranche; the owner leg is derived by
subtraction so legs sum **exactly** to the total (no float touches money):

```
LISTED (owner_account set):
  commission = (completion * COMMISSION_RATE_BPS) // 10000      # floor, one leg
  owner_cut  = (base + completion) - commission                 # derived remainder
    escrow → owner_account   owner_cut    (reason payout_owner)      # base 100% + completion 90%
    escrow → broker          commission   (reason payout_commission) # dropped if 0¢

UNOWNED (owner_account is None):
    escrow → broker          base+completion (reason payout_broker)  # no seller to pay
```

In production, `owner_account` is the seller's **own spendable `<user_id>` wallet**
(`app/marketplace/listing.py::owner_account_for` returns `owner_id`) — so earnings are
immediately spendable and appear in the seller's transaction history, no cash-out step.
*(Divergence from plan3, which proposed a separate non-spendable `agent:owner:<id>`
account. The code, and `tests/test_split.py`, use the plain wallet.)*

**Penny-exact, worked** (`COMMISSION_RATE_BPS=1000`, basis `completion`):

| base | completion | total | commission `= comp*1000//10000` | owner_cut `= total − commission` | Σ legs | escrow after |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 150 | 250 | 15 | 235 | 250 | 0 |
| 100 | 155 | 255 | 15 | 240 | 255 | 0 |
| 100 | 151 | 251 | 15 | 236 | 251 | 0 |
| 50 | 95 | 145 | 9 | 136 | 145 | 0 |
| 50 | 5 | 55 | 0 → *leg dropped* | 55 | 55 | 0 |
| — | — | unowned 250 | n/a | broker 250 | 250 | 0 |

### The fail path (`terminals.py::verify_failed`)

Completion refunds to the buyer; the non-refundable **base sweeps** via
`split.base_sweep_leg` → owner (listed) or broker (unowned). This explicit sweep drains
the base out of escrow so **escrow still settles to 0 even on failure**, and the broker
takes **no commission on failed work**.

### Revenue reads (`wallet.py::get_platform_stats`, `get_skill_earnings`)

Pure reads over the same ledger — never write. They report `broker_revenue_cents`,
`commission_cents` (reason `payout_commission`), `per_owner` earnings (grouped by reason
`payout_owner`), legacy `per_agent`, plus a live `feed`. The `per_agent` filter excludes
`agent:owner:%` so owner earnings and specialist earnings never merge. `get_skill_earnings`
joins `ledger` to `job_receipts` on `task_id` to give a seller per-skill hire counts +
lifetime earnings (surfaced at `GET /skills/contributed`).

---

## 7. The specialist runtime (one runtime, many skills)

`app/runtime/specialist.py` is a single shell. On dispatch it loads the selected
SkillCard, builds a prompt from `instruction` + task inputs, and runs Gemma via
`ollama.chat`. If the skill's one capability is `create_doc`, it checks the grant then
creates the Google Doc (passing content up-front to avoid the "insertion index within a
grapheme cluster" error on emoji-rich posts); if `get_doc_content`, it checks the grant
then reads the doc. The **builder** branch (`skill-builder`, zero capabilities) instead
asks Gemma to fill only `instruction` + `description`; Marvis derives every
safety-critical field (`_assemble_skill_card`) — id, agent name, tool, specialties,
pricing — so a 2B model can never fabricate a tool or identity.

---

## 8. Listing & the earnings loop

`app/marketplace/listing.py::list_skill` is the out-of-graph write-path (invoked by the
demo seed, `POST /skills/list`, and `POST /skills/create`). Atomically it: writes a
`skill_ownership` row (idempotent, `INSERT OR IGNORE`), sets `owner_id` + `owner_account`
on a re-owned copy of the card, mints a per-owner ES256 signing key, registers it into
the marketplace registry under `(owner_id, skill_id)`, and writes the card's files to
`agent-skills/<owner_id>/<slug>/` so it survives a restart. The hire graph itself is
unchanged — it simply finds a card that happens to carry `owner_account` and pays it out
split.

---

## 9. Divergences from the planning docs (code is authoritative)

- Owner earnings route to the seller's **spendable wallet**, not a separate
  `agent:owner:<id>` account (§6).
- Stale "not wired yet" comments remain in `config.py`, `db.py`, and `skill_card.py`; the
  split **is** live in `payout.py`.
- **A2A** is a discovery/identity convention (agent cards, broker catalog labeled "A2A");
  hire **dispatch is in-process** — no A2A wire call.
- The **scoped MCP proxy (:8003)** was never built; enforcement is in-process. The stub is
  parked in `references/`.
- Broker CartMandate/mandate verification is **best-effort** in demo mode — a failure is
  tolerated so a runtime-listed skill (unknown to the broker's startup catalog) can be
  hired via a local checkout (`hire.py::_local_checkout`).
