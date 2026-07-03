# Marvis — Phase 3 Pre-Build Audit (read-only ground truth)

**Scope:** Answer where money lives, how skills + ownership are stored/keyed, and exactly where a hire pays out — so the 90/10 commission split can be spliced in for Phase 3. Everything below is the **actual state on disk**, not what plan.md / plan2.md describe. Divergences from the plans are flagged **⚠︎ DIVERGENCE**.

**Money DB:** `marvis/marvis.db` (SQLite). Broker service has a separate `marvis/broker.db` (sessions/bookings only — **no ledger**).

---

## 1. Money layer

**Where it lives:** file-based **SQLite** at `marvis/marvis.db` (path from `app/config.py:DB_PATH`). One append-only, hash-chained, double-entry `ledger` table. **Balance is never stored — always derived** as `SUM(delta_cents)`. Modules:

- `app/wallet.py` — the ledger primitive (deposit/deduct/transfer, balance, chain verify, platform stats).
- `app/escrow/operations.py` — thin escrow helpers over `wallet.transfer`.
- `app/db.py` — schema (`ledger`, `hiring_txns`, `capability_grants`, `job_receipts`, users/auth).

**Core transfer/ledger-write primitive** — `app/wallet.py:_double_entry` (writes the two balanced rows) and the public `transfer()` that wraps it with a balance check + lock:

```python
# app/wallet.py:66
def _double_entry(conn, debit_account, credit_account, amount_cents, reason, reference_id) -> str:
    journal_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    _insert_entry(conn, journal_id, debit_account,  -amount_cents, credit_account, reason, reference_id, now)
    _insert_entry(conn, journal_id, credit_account, +amount_cents, debit_account,  reason, reference_id, now)
    return journal_id

# app/wallet.py:145
async def transfer(from_account, to_account, amount_cents, reason, reference_id=None) -> str:
    if amount_cents <= 0:
        raise ValueError("transfer amount must be positive")
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        balance = _balance_sync(conn, from_account)
        if balance < amount_cents:
            raise ValueError(f"Insufficient funds in {from_account}: {balance}¢, need {amount_cents}¢")
        journal_id = _double_entry(conn, from_account, to_account, amount_cents, reason, reference_id)
        conn.commit()
        return journal_id
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()
```

**Account-id conventions in use** (accounts are arbitrary strings; nothing needs "creating" — an account exists the moment a row references it):

| Account string | Meaning | Minted where |
|---|---|---|
| `"system"` | top-up source / sink | `wallet.py:22 SYSTEM` |
| `"<user_id>"` | the single owner's wallet | `auth.py` register |
| `"escrow:<task_id>"` | funds held during a hire | `escrow/operations.py:escrow_account` |
| `"agent:<agent_name>"` | specialist earnings | `escrow/operations.py:agent_account` |

**Does a BROKER account exist? — NO.** `grep "broker:" app` → **NONE**. The broker server signs CartMandates but never appears in the ledger. Today, escrow releases the **full** base+completion to `agent:<agent_name>`; the broker takes **0¢**. This is exactly the gap Phase 3 fills.

**Penny-exact?** Yes — everything is integer cents. `delta_cents INTEGER` with a `CHECK(delta_cents != 0)` (`db.py:79`). The **only** float arithmetic anywhere is *presentation* (`/100` for UI/AP2 display, e.g. `hire.py:319 value=total_cents/100`); no money is ever stored or split from a float. **No rounding exists today** because nothing is ever divided — money only moves in whole pre-set amounts.

**Concurrency:** single SQLite file, `PRAGMA journal_mode=WAL` (`db.py:15`), and every mutation opens `BEGIN IMMEDIATE` (write-lock) then commit/rollback (`deposit`/`deduct`/`transfer`). Effectively serialized writes; single-process demo. `get_conn` uses `check_same_thread=False`.

---

## 2. The payout path (where Phase 3's 90/10 split will go)

**The single release function is `pay_completion` in `app/workflow/nodes/payout.py:196`.** It moves escrow → agent for the **whole** amount in one transfer:

```python
# app/workflow/nodes/payout.py:196
async def pay_completion(node_input):
    task_id     = node_input.get("task_id", "")
    skill_card  = node_input.get("skill_card", {})
    agent_name  = skill_card.get("agent_name", "Agent")
    pricing     = skill_card.get("pricing", {})
    base_cents        = pricing.get("base_fee_cents", 0)
    completion_cents  = pricing.get("completion_fee_cents", 0)
    total_cents       = base_cents + completion_cents          # ← full amount

    journal_id = await release_to_agent(                        # escrow:{task} → agent:{name}
        task_id=task_id, agent_name=agent_name,
        amount_cents=total_cents, reason="payout",
    )
    # ... UPDATE hiring_txns SET base_status='RELEASED', completion_status='RELEASED' ...
```

`release_to_agent` (`escrow/operations.py:40`) is just `wallet.transfer(escrow:{task} → agent:{name})`.

**Accounts moved between, end-to-end for a paid market hire:**
1. **Hire** — `hire.py:pay_base_into_escrow` → `hold_in_escrow(user_id, task_id, total_cents)` = `transfer(<user_id> → escrow:{task}, base+completion)` (reason `"hire_escrow"`). ⚠︎ Note: despite the node name "pay_base", it escrows **base + completion together** in one move.
2. **Payout (pass)** — `payout.py:pay_completion` → `release_to_agent(escrow:{task} → agent:{name}, total)`.
3. **Settle** — `payout.py:settle_escrow` asserts `escrow:{task} == 0`.
4. **Fail/reject** — `terminals.py:verify_failed` → `refund_from_escrow(escrow:{task} → <user_id>, completion_cents)`; base stays in escrow and is later swept to the agent (base non-refundable, per §7b-B).

**Total-preservation invariant — guaranteed by construction, not by an assertion:**
- Everything is derived from `pricing.base_fee_cents + completion_fee_cents`; the same `total_cents` is escrowed and released.
- `wallet._double_entry` writes `-amount` and `+amount` in the same journal, so `get_all_account_sum()` is always 0 (`wallet.py:223`).
- Enforced sum-check: `settle_escrow` (`payout.py:242`) reads `get_escrow_balance(task_id)` and warns if `!= 0`. On the pass path `escrow` drains to exactly 0 because `release_to_agent(total)` removes exactly what `hold_in_escrow(total)` added. On the fail path, `completion` refunds to user and `base` remains held (escrow ≠ 0 by design until swept).

**⚠︎ This `release_to_agent(total)` call at `payout.py:206` is the exact line the 90/10 split replaces.**

---

## 3. Skill storage — marketplace vs owned (actual, on disk)

**Marketplace skills** — `marvis/app/marketplace/agent-skills/<slug>/` with `skill.json` + `instruction.md` per slug. **Actual contents (⚠︎ DIVERGENCE from plan.md, which says the seed is `skill-doc-reader` / `skill-doc-writer`):**

```
app/marketplace/agent-skills/
  twitter-writer/     twitter-reviewer/
  instagram-writer/   instagram-reviewer/
  skill-builder/                                 # the Phase-2 builder, listed as a market skill
```
No `doc-reader`/`doc-writer` folders exist anymore (they survive only as stale key files — see §5).

**Owned skills — FLAT, NOT per-owner (confirmed):**

```
app/owned-skills/
  .gitkeep
  linkedin-writer/
    skill.json
    instruction.md
```

Path constants: `SKILLS_DIR = seed.py:23` (`marketplace/agent-skills`), `OWNED_SKILLS_DIR = seed.py:28` (`app/owned-skills`). The owned tree is `owned-skills/<slug>/` — **there is no `<owner_id>` level**. `persist.py:31` derives the folder purely from the slug: `slug = card.skill_id.removeprefix("skill-")`.

**SkillCard schema (`app/marketplace/skill_card.py:29`) — every field:**

`skill_id`, `agent_name`, `display_name`, `version`, `description`, `specialties[]`, `instruction`, `model`, `required_capabilities[]` (`{mcp_server, tool_name, why}`), `pricing` (`{currency, base_fee_cents, completion_fee_cents}`), `public_key` (JWK dict), `io`, `reputation`.

**Owner/seller field today? — NONE.** There is no `owner_id`, `owner_account`, `seller`, or `listed_by` field on `SkillCard`, `SkillPricing`, or the derived `AgentCard`. Confirmed.

**Loader + both seeds (`app/marketplace/seed.py`)** — read from disk and register:

```python
# seed.py:31
def _load_skill_card(skill_dir):
    meta = json.loads((skill_dir / "skill.json").read_text(...))
    instruction = (skill_dir / "instruction.md").read_text(...).strip()
    return SkillCard(
        skill_id=meta["skill_id"], agent_name=meta["agent_name"], ...,
        required_capabilities=[CapabilityRef(**c) for c in meta["required_capabilities"]],
        pricing=SkillPricing(**meta["pricing"]),
        public_key=skill_public_key_dict(meta["skill_id"]),   # key minted from skill_id ALONE
    )

# seed.py:52  — marketplace store
def seed_catalog():
    registry = get_registry()
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir/"skill.json").exists(): continue
        card = _load_skill_card(skill_dir)
        if not registry.has(card.skill_id): registry.register(card)   # keyed by skill_id

# seed.py:68  — owned store (mirror)
def seed_owned_library():
    registry = get_owned_registry()
    if not OWNED_SKILLS_DIR.exists(): return
    for skill_dir in sorted(OWNED_SKILLS_DIR.iterdir()):
        ...
        if not registry.has(card.skill_id): registry.register(card)
```

`persist.py:persist_skill` (the builder's write path) writes `owned-skills/<slug>/skill.json` (+ `instruction.md`) and does `get_owned_registry().register(card)`. `skill.json` written by the builder carries **no owner field** (`persist.py:37` meta dict).

---

## 4. Registry keying (the ownership-collision question)

**Keyed by `skill_id` alone — a plain dict.** `app/marketplace/skill_registry.py:11`:

```python
class InMemorySkillRegistry:
    def __init__(self): self._skills: dict[str, SkillCard] = {}
    def register(self, card): self._skills[card.skill_id] = card     # upsert by skill_id
    def get(self, skill_id): ...return self._skills[skill_id]
```

There are two **separate instances** of this same class — `get_registry()` (marketplace) and `get_owned_registry()` (owned) — but each is internally keyed by `skill_id` only. No composite key, no owner dimension.

**DIAGNOSIS — if user "alice" and user "bob" both list/own slug `linkedin-writer` (`skill_id = "skill-linkedin-writer"`) TODAY:**

1. **File-path collision.** Both resolve to the same directory. `persist.py:31` `skill_dir = OWNED_SKILLS_DIR / "linkedin-writer"` and `mkdir(exist_ok=True)` + `write_text` → bob's `skill.json`/`instruction.md` **silently overwrite** alice's. Only one skill survives on disk.
2. **Registry key collision.** `register()` is an upsert on `skill_id`; the second `register` **evicts** the first from the in-memory dict. `get("skill-linkedin-writer")` returns whichever was registered last (load order is `sorted(iterdir())` — non-deterministic w.r.t. owner).
3. **Signing-identity collision.** `keys.py:skill_private_key(skill_id)` mints/loads `_keys/skill-<skill_id>.json` from `skill_id` alone → alice and bob **share one keypair**. Attestations are indistinguishable between owners.
4. **Earnings mis-routing (the money bug).** Payout targets `agent:<agent_name>` (`payout.py:201`), and `agent_name` comes from the card. Both cards declare `agent_name = "LinkedinPostSpecialist"` → both owners' earnings land in the **same** `agent:LinkedinPostSpecialist` account. Even if the collision above were fixed, **there is no owner field to route 90% to**, so alice's and bob's revenue are inseparable.

Net: today the system is single-owner by construction. Multi-owner breaks at the filesystem, the registry, the keystore, **and** the ledger simultaneously.

---

## 5. Identity / keys

**Per-skill keypairs** — `app/keys.py`. `_load_or_generate(name)` (`keys.py:13`) loads `app/_keys/<name>.json` or generates an EC P-256 JWK and writes it. Skill keys use `name = f"skill-{skill_id}"` (`keys.py:67`), so the file is `_keys/skill-skill-<slug>.json`. `skill_public_key_dict` (used by the loader and `persist_skill`) is derived **from `skill_id` only** — no owner input.

Actual `_keys/` on disk (⚠︎ stale keys from the old doc-reader/doc-writer seed persist even though those skills are gone):
```
skill-skill-builder.json          skill-skill-doc-reader.json     skill-skill-doc-writer.json
skill-skill-instagram-reviewer.json  skill-skill-instagram-writer.json
skill-skill-linkedin-reviewer.json   skill-skill-linkedin-writer.json
skill-skill-twitter-reviewer.json    skill-skill-twitter-writer.json
```

**Any "owner"/"user" identity beyond the single human + skill identities? — NO.** `db.py` has `users`/`user_keys`/`auth_sessions`, but the whole app assumes **one** owner: `authorize_base_payment` reads `ctx.state["user_id"]`, wallet routes to `<user_id>`, and there is no concept of a *seller/owner distinct from the operator*. Skill identities are `agent:<agent_name>` ledger accounts + per-skill keypairs. No owner principal exists. Confirmed.

---

## 6. Frontend / read APIs

**Surfaces** (`marvis/frontend/src/pages/`): `Auth`, `Chat`, `Landing`, `Marketplace`, `OwnedSkills`, `PlatformVolume`, `Wallet` (+ `components/A2uiRenderer`, `Sidebar`, `Modal`).

**Data fetch mechanisms (`frontend/src/api.ts`):**
- **REST (fetch)** for auth, wallet, catalogs, stats: `/auth/*`, `/wallet/balance`, `/wallet/topup`, `/marketplace/agents`, `/owned-skills`, `/platform/stats`.
- **SSE** for the agent loop: `streamAdkRun` POSTs to `/run_sse` and parses tagged `<a2ui-json>`/`<mstat>` parts (A2UI + status).

**Read endpoints exposing balance/ledger TODAY — YES, two already exist:**
- `GET /wallet/balance?token=…` (`auth.py:228`) → `{balance_cents, transactions[]}` for the **logged-in owner** (`get_transactions(user_id)`).
- `GET /platform/stats` (`fast_api_app.py:126` → `wallet.py:get_platform_stats`) → cross-account aggregate: `total_volume_cents`, `total_paid_to_agents_cents`, `total_refunded_cents`, `total_topped_up_cents`, `hire_count`, **`per_agent[]` earnings** (`agent:%` grouped), and a **`feed[]`** of recent ledger credit rows. Rendered by `PlatformVolume.tsx`.

So a broker-revenue tab has a natural home: extend `get_platform_stats` to also `SUM` a future `broker` account and `agent:owner:*` rows. No new plumbing needed — it's another read over the same ledger.

---

## 7. Phase 1 & 2 invariants Phase 3 must not break

| Invariant | Enforced in | What it guarantees |
|---|---|---|
| **Zero-sum ledger** | `wallet.py:_double_entry`, `get_all_account_sum()` | Every journal writes ±amount; all accounts sum to 0. A split into >2 accounts must still net to zero. |
| **Balance never stored, always derived** | `wallet.py:_balance_sync` | No cached balances to desync. |
| **Never debit before confirm** | `hire.py:pay_base_into_escrow` (escrow only after checkout/verify), `payout.py:pay_completion` (after PIN #2) | Money moves to the agent only after human approval. |
| **Base non-refundable / completion refundable** | `hire.py` escrows both; `terminals.py:verify_failed` refunds **completion only**; base swept to agent | The classic deposit + on-delivery structure. |
| **Escrow settles to 0** | `payout.py:settle_escrow` (`get_escrow_balance == 0`) | Escrow fully drained per task. Splitting the payout across owner+broker must still zero the escrow. |
| **Two PIN gates** | `hire.py:authorize_base_payment` (#1), `payout.py:approve_payout` (#2) | Human authority at hire and payout. |
| **Grant least-privilege + dual revoke (explicit + TTL)** | `capability.py:grant_capability`/`revoke_capability`, `capability/grant.py:check_and_use` | ONE tool per grant; `revoke_by_task` on every dispatch exit + TTL expiry. |
| **Two-lifetime stores never conflated** | `skill_registry.py` (two instances), `seed.py`/`persist.py` (owned never touches marketplace folder or broker) | Marketplace = rented/pay-per-use; owned = permanent/free. Owned runs move **no money** (`terminals.py:receipt_terminal` sets `total_cents=0` when `skill_store=="owned"`). |
| **Idempotent seeding** | `seed_catalog`/`seed_owned_library` (`if not registry.has(...)`) | Restart-safe registry population. |

**Phase 3 must preserve:** the zero-sum property (a 3-way split still nets 0), escrow-settles-to-0, and the owned-run-is-free rule (a listed marketplace skill earns; an owned skill does not).

---

## A. The ownership-namespacing fix (DIAGNOSE + PROPOSE — not implemented)

**Root cause:** `skill_id` is the sole key at three layers (filesystem, registry dict, keystore) and there is no owner principal or owner account. Minimal, content-stays-as-files fix:

1. **Add an owner principal.** Introduce an `owner_id` (reuse `users.id`). A "broker" account is just the string `"broker"` — no schema change needed (ledger accounts are arbitrary strings).
2. **`SkillCard` gains `owner_account: str | None`** (`skill_card.py`). `None` ⇒ unowned ⇒ broker keeps 100%. For listed skills, `owner_account = "agent:owner:<owner_id>"` (or reuse the seller's user wallet). Copy it through into `AgentCard.from_skill_card`.
3. **Owner-namespaced folders** for listed/owned skills: `owned-skills/<owner_id>/<slug>/` (and, when Phase 3 lets sellers list, `agent-skills/<owner_id>/<slug>/`). Touches `seed.py` (`_load_skill_card` to read `owner_id` + the two seed loops to descend one level) and `persist.py:31` (`skill_dir = OWNED_SKILLS_DIR / owner_id / slug`).
4. **Composite registry key `(owner_id, skill_id)`** in `InMemorySkillRegistry` (`skill_registry.py`): `register`, `get`, `has` become `(owner_id, skill_id)`-keyed. ⚠︎ **This is the one change that ripples**: every `registry.get(skill_id)` caller must pass owner too — `dispatch.py:89`, `discover.py:54/121`, `select.py`, `build.py:162/194`. Keep a single-owner default (Phase-1/2 skills registered under a synthetic `owner_id="marvis"`) so existing tests pass unchanged.
5. **Per-owner keys:** `keys.py` key name → `f"skill-{owner_id}-{skill_id}"` so two owners don't share a keypair.

**Does this break Phase 1/2 tests?** Only if the composite key is made mandatory. Mitigation: default `owner_id="marvis"` for all currently-seeded skills and keep `get(skill_id)` resolving within that default namespace → Phase 1/2 loop, grant, verify, payout tests are untouched. The folder move for the lone owned `linkedin-writer` is a one-time relocation to `owned-skills/marvis/linkedin-writer/`.

**Storage recommendation:** money is already SQLite (`marvis.db`) — **no new store needed**. Ledger already supports the split (arbitrary accounts, zero-sum). Ownership is small and relational; add a tiny **`skill_ownership(owner_id, skill_id, owner_account, listed_at)`** table in the existing `marvis.db` rather than a second DB. **Keep skill CONTENT as files** (`skill.json` + `instruction.md`), namespaced by owner. Do not move skill text into the DB.

---

## B. Phase 3 splice points + risks

**The one function for the 90/10 split:** `app/workflow/nodes/payout.py:pay_completion` — specifically the single `release_to_agent(..., amount_cents=total_cents)` call at **`payout.py:206`**. Replace it with two zero-sum transfers from the same escrow:

- `owner_cut = (total_cents * 90) // 100` → `escrow:{task} → agent:owner:<owner_id>` (or the skill's `owner_account`)
- `broker_cut = total_cents - owner_cut` → `escrow:{task} → broker`

**Exact rounding rule (penny-exact on odd cents):** compute **one** side by integer floor and **derive the other by subtraction** — never round both independently:

```
owner_cut  = (total_cents * 90) // 100     # floor
broker_cut = total_cents - owner_cut       # exact remainder
assert owner_cut + broker_cut == total_cents
```

This guarantees the two legs sum to `total_cents` for any odd amount (e.g. 151¢ → owner 135, broker 16; 155¢ → owner 139, broker 16), so `settle_escrow`'s `escrow == 0` assertion still holds. For an **unowned** skill (`owner_account is None`): send 100% to `broker`. Add a `hiring_txns` cross-ref column or a new `reason` (`"payout_owner"` / `"payout_broker_fee"`) so `get_platform_stats` can report commission — those SUM filters (`wallet.py:257`) key off `reason`/account prefix, so pick names it can group.

**Top 3 risks / landmines:**
1. **`agent_name` is the current earnings key, and it's not owner-unique.** Two owners' skills can share `agent_name` (§4). If Phase 3 keeps routing to `agent:<agent_name>`, revenue merges silently. The split must route to an **owner-derived** account, not `agent_name`.
2. **`skill_id`/slug collision at filesystem + registry + keystore (§4).** Listing multiple owners before the namespacing fix (§A) causes silent overwrite and last-writer-wins lookup. Do §A *before* enabling multi-owner listing.
3. **Owned-vs-market money rule.** `receipt_terminal` zeroes `total_cents` for `skill_store=="owned"` and owned runs never hit `pay_completion`. Phase 3 must keep "owned skill = free to its owner" while "listed marketplace skill = earns for its owner" — i.e. the split fires only on the **market** payout path, not the owned/free path. Don't accidentally start charging owned runs.

**Open questions to answer before Phase 3 design:**
- **Owner account model:** does an owner's 90% land in a dedicated `agent:owner:<owner_id>` ledger account, or directly in that owner's **user wallet** (`<user_id>`)? (Affects whether owner earnings are spendable immediately.)
- **Who is "broker"?** A single `"broker"` account for the platform, or does the current human owner *act as* broker (i.e. broker == the operator's wallet)?
- **Where is 90/10 configurable?** Global constant (`config.py`), or per-`SkillCard.pricing.commission_bps`? (Latter needs a schema field now.)
- **Listing surface:** can a seller list a skill *without* being the running operator (true multi-user), or is Phase 3 still one operator listing skills "as" different owners? This decides whether `users`/auth must grow a seller role now or later.
- **Base vs completion in the split:** does the broker take 10% of **both** tranches (current `total_cents`), or only the completion? (Plan says "10% commission, 90% to owner" on the hire — audit assumes total; confirm.)

---

*End of audit — read-only, no code modified.*





