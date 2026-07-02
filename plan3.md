# Marvis — Phase 3 Implementation Plan

**The earnings loop: a user LISTS a skill; when someone else HIRES it, the owner EARNS and the broker takes a commission. This closes the marketplace — Phase 1 rent → Phase 2 build/own → Phase 3 sell/earn.**

Status: PLAN ONLY — no code is written yet. Read [§P3-9 Open Questions](#p3-9-open-questions--assumptions) and confirm before any build starts. This document is a **Phase 3 addendum** to `plan.md` + `plan2.md`; it assumes Phase 1 + Phase 2 + the **Pre-Phase-3 ownership-namespacing fix** are complete and working (all confirmed by `audit.md`), and reuses their machinery verbatim wherever possible.

> **Scope of Phase 3 — ONE new idea.** The marketplace gains its **third side**. Today Marvis can **rent** a skill (Phase 1) or **build & own** a skill (Phase 2, runs free for its owner). Phase 3 lets an owner **LIST** a skill so that **someone else** can hire it; when they do, the escrow payout **splits three ways instead of one**: the **base fee goes 100 % to the skill's owner**, the **completion fee splits 90 % owner / 10 % broker**, and the money lands in a dedicated **`agent:owner:<owner_id>`** earnings account plus a distinct **`broker`** account. An **unowned** skill (`owner_account is None`) routes its **entire** payout to `broker`. That asymmetry is the whole of Phase 3's money logic.
>
> **The net-new surface is deliberately tiny.** Most of Phase 3 is: **(a) split ONE payout function** (`payout.py:pay_completion`, the single `release_to_agent(total)` call at line 206 — audit §2/§B), **(b) read `owner_account` off the already-threaded SkillCard** at payout, **(c) seed 2–3 real owner accounts** through the existing `/auth/register`, and **(d) a small "list a skill" write-path** (one `skill_ownership` row + register the card owner-namespaced + set `owner_account`). The broker-revenue read/tab is planned but **marked separable** (its own follow-up prompt). If the net-new list grows past that, we've over-designed — flagged inline as ⚠️SCOPE.
>
> **Explicitly out of scope (forbidden — flag as ⚠️SCOPE if tempted):** a full concurrent live-login marketplace UX; real-time seller dashboards; a listing-management CRUD UI; delisting / price-editing flows; reputation / reviews; payout **withdrawals** (owner earnings accumulate, they are not cashed out); any **second database**; moving skill **content** into the DB; a **new auth system**; a new process / port / protocol.

---

## P3-0. Grounding: what the money + ownership layer actually is *as built* (read this first)

Phase 3 must splice into the **real** code the audit documented, not the plan.md sketch. The load-bearing facts (all verified on disk):

| Fact (as built) | Where | Why it matters for Phase 3 |
|---|---|---|
| **The single payout line moves the whole amount to one account.** `release_to_agent(escrow:{task} → agent:{agent_name}, base+completion)`. | `payout.py:206`, `escrow/operations.py:40` | ⭐ **This is the one line Phase 3 replaces** with a 2- or 3-way split. Everything else in `pay_completion` (the `hiring_txns` UPDATE, the event) stays. |
| **`skill_card` (full `model_dump()`) is threaded through `node_input`** from `select_specialist` → hire → payout. It already carries `owner_id` and `owner_account`. | `discover.py:153`, `payout.py:199` | The split needs **no new plumbing** to know the skill's owner — `node_input["skill_card"]["owner_account"]` is present at `pay_completion`. |
| **`SkillCard` already has `owner_id: str = "marvis"` and `owner_account: str | None = None`.** `AgentCard.from_skill_card` copies `owner_account` through. | `skill_card.py:31-33,55,68` | The data model change is **already done** (pre-Phase-3 fix). Phase 3 only *populates* `owner_account` at listing time and *reads* it at payout. |
| **Commission constants exist but are unwired.** `COMMISSION_RATE_BPS=1000` (10 %), `COMMISSION_BASIS="completion"`. | `config.py:63-64` | Phase 3 wires exactly these. No new config knob. The penny-exact rule is even spelled out in the comment: `commission=(tranche*BPS)//10000; owner=tranche-commission`. |
| **Ledger accounts are arbitrary strings; an account "exists" the moment a row references it.** Zero-sum by construction (`_double_entry` writes ∓amount). | `wallet.py:66-78`, audit §1 | `agent:owner:<id>` and `broker` need **no schema change and no "account creation"** — just transfer into them. A 3-way split = three balanced `transfer()` calls (or two, escrow drains either way). |
| **`skill_ownership(owner_id, skill_id, owner_account, listed_at)` table already exists** (schema only, unpopulated). | `db.py:188-196` | The listing write-path has its table already. Phase 3 populates it; no migration. |
| **Registry is `(owner_id, skill_id)`-keyed**, with `owner_id="marvis"` back-compat default on `get`/`has`. | `skill_registry.py:14-35` | Two owners can list the same slug without colliding. ⚠️ But `select_specialist` currently calls `registry.get(cid)` **without** an owner → resolves the `"marvis"` default only. Threading a non-marvis owner through selection is the **one ADAPT ripple** (§P3-1, audit §A-4). |
| **Per-owner folders + keys already wired.** `persist.py:33` writes `owned-skills/<owner_id>/<slug>/`; `seed_owned_library()` descends owner dirs; `skill_public_key_dict(skill_id, owner_id)` mints per-owner keys. | `persist.py`, `seed.py:104-107`, `keys.py` | The **owned** store is already owner-namespaced. The **marketplace** store (`agent-skills/`) is still flat/`marvis` — listing a non-marvis seller needs the same owner-descent `seed_catalog` already has the seam for (`_seed_dir_flat` takes an `owner_id`). |
| **Owned runs move NO money.** `receipt_terminal` sets `total_cents=0` when `skill_store=="owned"`; owned skills route `verify → receipt`, never touching `approve_payout`/`pay_completion`. | `terminals.py:152-155`, `agent.py:142-143` | ⭐ **Invariant to preserve:** the split fires **only** on the market payout path. An owned skill run stays free **for its owner**. "Listed-and-hired-by-someone-else" is the *market* path; "owned, run by its owner" is the *free* path. |
| **`get_platform_stats` already aggregates `agent:%` + reason filters + a live feed.** | `wallet.py:234-298`, audit §6 | The broker-revenue tab is "one more SUM over the same ledger." ⚠️ But `agent:owner:<id>` matches the existing `agent:%` filter → would pollute the specialist `per_agent` list unless excluded (§P3-8). |
| **Two PIN gates, base-nonrefundable/completion-refundable, escrow-settles-to-0** are all enforced today. | audit §7 | Phase 3's split must keep **all** of these. A 3-way split still nets 0; escrow still drains to 0; PIN #2 still authorizes the *release* (now a split release). |

---

## P3-1. REUSE MAP (net-new list kept deliberately short)

Legend: **REUSE** = used verbatim / already generic enough · **ADAPT** = small, localized change to an existing file · **NET-NEW** = genuinely new code.

| Phase 3 component | Verdict | File + function | Detail |
|---|---|---|---|
| Ledger / double-entry / zero-sum / hash-chain | **REUSE** | `wallet.py:transfer/_double_entry` | A 3-way split is just N balanced `transfer()` calls. No ledger change. |
| Escrow hold + settle-to-0 assertion | **REUSE** | `hire.py:pay_base_into_escrow`, `payout.py:settle_escrow` | Hire still escrows `base+completion`; settle still asserts `escrow==0`. The split drains escrow to 0 by subtraction (§P3-4). |
| Hire loop (authorize→checkout→verify→escrow) | **REUSE** | `hire.py:*` | Completely unchanged. Hiring a listed seller skill is the **same** hire as hiring any market skill. |
| Two PIN gates | **REUSE** | `hire.py:authorize_base_payment`, `payout.py:approve_payout` | Unchanged. PIN #2 still authorizes the release; the release is now a split. |
| `SkillCard.owner_id` / `owner_account`, `AgentCard.from_skill_card` copy-through | **REUSE** | `skill_card.py:31-33,55,68` | Fields + copy-through already exist. Phase 3 only populates/reads them. |
| `skill_ownership` table | **REUSE** (schema) | `db.py:188-196` | Exists. Phase 3 INSERTs into it at listing time. |
| Commission constants | **REUSE** | `config.py:63-64` | `COMMISSION_RATE_BPS`, `COMMISSION_BASIS`. Wire them; don't add new ones. |
| Real users / wallets / keys / `/auth/*` | **REUSE** | `auth.py:register`, `db.py:users/user_keys/wallets` | Seed alice + operator through the **existing** register flow. **No new auth.** |
| `get_platform_stats` read shape (SUM/GROUP/feed) | **REUSE** | `wallet.py:234` | The revenue tab extends this read; no new plumbing. |
| Owned-FREE run path | **REUSE (untouched)** | `terminals.py:receipt_terminal`, `agent.py:142` | Must **not** start charging owned runs. Guard: split only on the market payout node. |
| **`pay_completion` → 3-way split** | **ADAPT (the core change)** | `payout.py:196-211` | Replace the single `release_to_agent(total)` at :206 with the split logic (§P3-4). ~15 lines. |
| **Escrow release helpers** | **ADAPT (small)** | `escrow/operations.py` | Add a generic `release_from_escrow(task_id, to_account, amount, reason)`; keep `release_to_agent` as a thin wrapper (back-compat). ~10 lines. |
| **`select_specialist` owner threading** | **ADAPT (the one ripple, audit §A-4)** | `discover.py:71/98-122` | Carry `(owner_id, skill_id)` in candidate lists so a non-`marvis` seller card can be `registry.get(cid, owner_id)`-resolved and selected. Today it defaults `owner_id="marvis"` and would `KeyError` on alice's card. |
| **`seed_catalog` owner-namespaced marketplace loop** | **ADAPT (small)** | `seed.py:81-88` | Descend `agent-skills/<owner_id>/<slug>/` like `seed_owned_library()` already descends the owned store. The `_seed_dir_flat(dir, reg, owner_id)` seam already exists. |
| **`skill_ownership` write + `owner_account` set = "list a skill"** | **NET-NEW (small)** | new `app/marketplace/listing.py` (`list_skill(...)`) | One function: write the `skill_ownership` row, set `owner_account="agent:owner:<owner_id>"` on the card, register it into the marketplace registry, write its files owner-namespaced. |
| **"List as alice" trigger** | **NET-NEW (tiny)** | seed helper (demo) **and/or** a `/skills/list` REST endpoint | For the demo, an **idempotent seed** that lists alice's skill at startup (mirrors `seed_owned_library`). A REST endpoint is the general path — mark **separable**. ⚠️SCOPE: no CRUD/delist UI. |
| **Seed real owner accounts** | **NET-NEW (tiny)** | seed script calling `/auth/register` (or direct DB insert mirroring `auth.register`) | Create `alice` (seller) + `operator/buyer` (me). Idempotent (skip if email exists). |
| **Broker-revenue + owner-earnings read** | **NET-NEW (separable)** | `wallet.py:get_platform_stats` (+ frontend) | `SUM(account_id='broker')`, `GROUP BY agent:owner:%`, exclude owner rows from specialist `per_agent`. **Deferrable to its own prompt.** |

> **Over-design check.** Net-new reduces to **four small things**: (1) split `pay_completion`, (2) a `list_skill` write-path, (3) seed real owners, (4) a stats read (separable). Everything else is REUSE or a localized ADAPT. The **only** ripple is threading `owner_id` through `select_specialist` — and the audit already predicted it (§A-4) and the registry already supports it. If any milestone starts adding a second DB, a withdrawal flow, a delist UI, or a new auth role table, **stop — that's scope creep.**

---

## P3-2. Target Phase 3 architecture

No new processes, ports, protocols, or databases. Two splices into the existing system: **(1)** the payout node gains a split; **(2)** a small out-of-graph write-path ("list a skill") populates ownership. The hire graph itself is **unchanged**.

```
              ┌───────────────────────── LISTING (out of the hire graph) ──────────────────────────┐
              │   list_skill(owner_id=alice, skill_id, ...)   [seed at startup OR POST /skills/list] │
              │        ├─ INSERT skill_ownership(alice, skill_id, "agent:owner:alice")               │
              │        ├─ card.owner_account = "agent:owner:alice"; card.owner_id = alice            │
              │        ├─ marketplace_registry.register(card)      # keyed (alice, skill_id)          │
              │        └─ write agent-skills/alice/<slug>/{skill.json,instruction.md}  (survives restart)
              └───────────────────────────────────────────────────────────────────────────────────┘
                                                     │  (card now discoverable + carries owner_account)
                                                     ▼
   buyer/operator ── "Write a LinkedIn post…" ─▶  ┌──────────── MARVIS Workflow (:8000) — UNCHANGED ────────────┐
                                                  │ intake → discover(BOTH stores) → select_specialist          │
                                                  │        [market] (alice's listed skill selected)             │
                                                  │            → authorize_base_payment (PIN #1)                 │
                                                  │            → create_hire_checkout → verify_hire_cart         │
                                                  │            → pay_base_into_escrow   user → escrow:{task}     │
                                                  │            → grant → dispatch → collect → revoke → verify    │
                                                  │            → approve_payout (PIN #2)                         │
                                                  │            → pay_completion   ★ SPLIT SPLICES HERE ★         │
                                                  │            → settle_escrow (assert escrow==0) → receipt      │
                                                  └────────────────────────────┬────────────────────────────────┘
                                                                               ▼
                    ┌──────────────────── THE SPLIT (payout.py:pay_completion) ────────────────────┐
                    │  owner_account = skill_card["owner_account"]   (the SKILL's owner, not buyer)  │
                    │                                                                                │
                    │  IF owner_account is not None  (LISTED, owned-by-a-seller):                    │
                    │     commission = (completion * COMMISSION_RATE_BPS)//10000     # floor         │
                    │     owner_cut  = base + (completion - commission)              # by subtraction│
                    │     escrow:{task} ── owner_cut  ──▶ agent:owner:<owner_id>     reason=payout_owner
                    │     escrow:{task} ── commission ──▶ broker                     reason=payout_commission
                    │  ELSE  (owner_account is None, UNOWNED / marvis-seeded):                       │
                    │     escrow:{task} ── total ──▶ broker                          reason=payout_broker
                    │                                                                                │
                    │  Σ legs == total  ⇒  escrow drains to 0  ⇒  settle_escrow still passes         │
                    └────────────────────────────────────────────────────────────────────────────────┘
                                    │                                   │
                                    ▼                                   ▼
                       agent:owner:alice (earnings,             broker (platform commission,
                       NOT alice's spendable wallet;            SUM-able; NEVER the operator's
                       decision #1)                             personal user wallet; decision #2)
```

**Where the split splices in:** exactly at `payout.py:pay_completion`, replacing the one `release_to_agent(total)` call. **Where listing writes:** entirely **outside** the graph — a write-path invoked by a startup seed (demo) or a REST endpoint (general). The hire graph never learns about "listing"; it just finds a card that happens to carry `owner_account` and pays it out split.

---

## P3-3. Data models

### P3-3.1 What a LISTED marketplace skill carries (vs unowned vs owned-free)

No schema change — the fields already exist on `SkillCard` (`skill_card.py:31-33`). Phase 3 is about **which values they hold** in each of the three cases:

| Case | Store | `owner_id` | `owner_account` | Runs… | Payout |
|---|---|---|---|---|---|
| **Listed seller skill** (alice) | **marketplace** | `<alice_user_id>` | `"agent:owner:<alice_id>"` | for **hire** by others | base 100 %→owner, completion 90 %→owner / 10 %→broker |
| **Unowned / platform skill** (the current seeded twitter/instagram/builder) | **marketplace** | `"marvis"` | `None` | for **hire** | **100 %→broker** (base+completion) |
| **Owned skill** (Phase 2 build, alice's own use) | **owned** | `<owner_id>` | (irrelevant — free path) | **free for its owner** | **no payout** (`total_cents=0`) |

**The owned-vs-unowned asymmetry, stated explicitly (decision #4):** `owner_account is None` ⇒ the skill has no seller to pay ⇒ the **broker keeps the entire base+completion**. `owner_account` set ⇒ base is 100 % the owner's and only the **completion** is commissioned at 10 %. There is no case where the broker takes a cut of the **base** of an *owned* skill; the broker only ever gets base money from **unowned** skills (where it gets all of it).

### P3-3.2 The `skill_ownership` row lifecycle

```
CREATE (at list time)         →  INSERT (owner_id, skill_id, owner_account="agent:owner:<owner_id>", listed_at=now)
READ   (at seed / discovery)  →  loaded into the SkillCard.owner_account when the marketplace card is registered
READ   (at payout)            →  actually read off the threaded skill_card dict, NOT re-queried (already in node_input)
(no UPDATE / DELETE in Phase 3 — delisting / re-pricing is ⚠️SCOPE / out)
```

The row is the **durable record of "who listed this and where their money goes."** The card's `owner_account` is the **hot-path copy** the payout reads. They are set together by `list_skill(...)` and never diverge in Phase 3 (no edit flow). `PRIMARY KEY (owner_id, skill_id)` makes listing **idempotent** — re-listing the same skill by the same owner is a no-op `INSERT OR IGNORE`.

### P3-3.3 The ledger accounts involved (no schema, arbitrary strings)

| Account string | Meaning | New in Phase 3? | Notes |
|---|---|---|---|
| `escrow:<task_id>` | funds held during a hire | no | source of every split leg |
| `agent:owner:<owner_id>` | **an owner's accumulated earnings** | **yes (by use)** | decision #1 — **NOT** the owner's spendable `<user_id>` wallet. No withdrawal path (out of scope). Matches `agent:%` → must be excluded from the specialist `per_agent` stat (§P3-8). |
| `broker` | **platform commission pool** | **yes (by use)** | decision #2 — a distinct string, separately SUM-able. **Never** the operator's personal `<user_id>` wallet. |
| `agent:<agent_name>` | Phase 1 specialist earnings | (now vestigial for listed/unowned) | ⚠️ **Behavior change:** after Phase 3 a *listed* skill pays `agent:owner:<id>` and an *unowned* skill pays `broker` — neither pays `agent:<agent_name>` anymore. See [§P3-9 Q1](#p3-9-open-questions--assumptions). |

---

## P3-4. The split-payout design — THE core change

**File:** `app/workflow/nodes/payout.py:pay_completion` (lines 196–211). **Everything except the single `release_to_agent(...)` call stays** (the `hiring_txns` UPDATE, the `Event` return).

### P3-4.1 The transform

```python
# app/workflow/nodes/payout.py — pay_completion (replacing lines 202–211)
from app.config import COMMISSION_RATE_BPS, COMMISSION_BASIS
from app.escrow.operations import release_from_escrow   # new generic helper (§P3-4.3)

base_cents       = pricing.get("base_fee_cents", 0)
completion_cents = pricing.get("completion_fee_cents", 0)
total_cents      = base_cents + completion_cents
owner_account    = skill_card.get("owner_account")       # the SKILL's owner, threaded from select
owner_id         = skill_card.get("owner_id", "marvis")

legs = []  # list[(to_account, amount_cents, reason)] — each leg is one escrow→X transfer

if owner_account:                                        # (a) LISTED, owned-by-a-seller
    # commission applies ONLY to the completion tranche (COMMISSION_BASIS=="completion")
    commission = (completion_cents * COMMISSION_RATE_BPS) // 10000   # FLOOR one leg
    owner_cut  = total_cents - commission                            # DERIVE the other by subtraction
    legs.append((owner_account, owner_cut,  "payout_owner"))
    if commission > 0:
        legs.append(("broker",   commission, "payout_commission"))
else:                                                     # (b) UNOWNED / platform skill
    legs.append(("broker", total_cents, "payout_broker"))

assert sum(a for _, a, _ in legs) == total_cents         # zero-sum guard (escrow drains to 0)

journal_ids = []
for to_account, amount, reason in legs:
    journal_ids.append(await release_from_escrow(task_id, to_account, amount, reason))
```

- `owner_cut = total_cents - commission` = `base + (completion - commission)` — i.e. **base 100 % + completion 90 %** to the owner, in **one** transfer, exactly as decision #4 requires. Computing it as `total − commission` (rather than `base + completion − commission`) is the same number and makes the "legs sum to total" proof trivially obvious.
- **Floor one leg, derive the other by subtraction — never round both independently.** `commission` is floored; `owner_cut` is the exact remainder. This is the audit §B rule and the `config.py:61` comment, verbatim.
- `if commission > 0` skips a zero-cent broker leg (the ledger's `CHECK(delta_cents != 0)` at `db.py:79` would otherwise reject a 0¢ transfer). On tiny completion fees the broker simply gets nothing that round — still penny-exact, still zero-sum.

### P3-4.2 Penny-exact arithmetic on odd completion cents (worked)

`COMMISSION_BASIS="completion"`, `COMMISSION_RATE_BPS=1000` (10 %). Commission is 10 % of **completion only**; base is always fully the owner's.

| base | completion | total | `commission = (completion*1000)//10000` | `owner_cut = total − commission` | Σ legs | escrow after |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 150 | 250 | 15 | 235 | 250 | **0** ✓ |
| 100 | **155** | 255 | (155000//10000)=**15** | 240 | 255 | **0** ✓ |
| 100 | **151** | 251 | (151000//10000)=**15** | 236 | 251 | **0** ✓ |
| 50 | **95** | 145 | (95000//10000)=**9** | 136 | 145 | **0** ✓ |
| 50 | **5** | 55 | (5000//10000)=**0** | 55 | 55 | **0** ✓ (no broker leg) |
| — | — | **unowned** | n/a | broker gets `total` | total | **0** ✓ |

The floor-plus-subtraction guarantees `owner_cut + commission == total_cents` for **every** integer input, so `settle_escrow`'s `get_escrow_balance(task_id) == 0` assertion (`payout.py:252`) holds unchanged.

### P3-4.3 Proof the ledger stays zero-sum & escrow settles to 0

- Every `release_from_escrow` = one `wallet.transfer(escrow:{task} → X)` = one `_double_entry` writing `−amount` on escrow and `+amount` on X → **each leg nets 0 across accounts** (`wallet.py:76-77`). N legs → still 0. The global `get_all_account_sum()` invariant (audit §7) is preserved by construction.
- `hold_in_escrow(total)` at hire put exactly `total_cents` into `escrow:{task}`. The split removes `Σ legs == total_cents`. So `escrow:{task}` drains from `+total` to exactly `0`. `settle_escrow` passes. **The 3-way split still nets 0 and still zeroes the escrow** — the two invariants the audit §7 explicitly calls out for Phase 3.
- **Fail/refund path unchanged:** `terminals.py:verify_failed` still refunds `completion_cents` to the buyer and leaves `base` in escrow to be swept — but note that sweep now goes to `owner`/`broker` per the split, not to `agent:<name>`. (Confirm base-sweep-on-fail target in [§P3-9 Q3](#p3-9-open-questions--assumptions).)

### P3-4.4 Reason strings chosen for the revenue read

The `reason` column is what `get_platform_stats` groups on (`wallet.py:256-261`). Phase 3 introduces exactly three, chosen so the revenue tab can `SUM`/filter cleanly:

| Leg | `reason` | Grouped for |
|---|---|---|
| owner earnings (base + 90 % completion) | `payout_owner` | owner-earnings view; `SUM WHERE account_id LIKE 'agent:owner:%'` |
| broker commission (10 % completion, listed skill) | `payout_commission` | broker-revenue = `SUM WHERE account_id='broker'` |
| broker full payout (unowned skill) | `payout_broker` | broker-revenue (same account, distinct reason so "commission" vs "kept-unowned" is separable) |

Broker total revenue = `SUM(delta_cents) WHERE account_id='broker' AND delta_cents>0`. Commission-only = `... AND reason='payout_commission'`. Both are pure reads over rows the split already writes.

---

## P3-5. Control flow — where "list" happens, and the unchanged hire loop

### P3-5.1 Listing is a SEPARATE action, OUTSIDE the hire graph (it should be — confirmed)

Listing is **not** a Workflow node. It's a **write-path** invoked one of two ways, both out-of-band from the `root_agent` graph:

1. **Demo seed (primary for Phase 3):** an idempotent `seed_listings()` called at startup in `agent.py` — right beside `seed_catalog()` / `seed_owned_library()` (`agent.py:69-70`). It lists alice's skill so the marketplace is pre-populated for the recording. Idempotent via `skill_ownership`'s PK + `registry.has(skill_id, owner_id)`.
2. **General write-path (separable):** `POST /skills/list` on the same FastAPI app (`fast_api_app.py`), auth'd by the seller's existing token (`_get_user_from_token`), calling the same `list_skill(...)`. ⚠️SCOPE: **no** delist/edit/CRUD UI — a single write endpoint only, and even this can be deferred to the follow-up prompt.

**Why out of the graph:** the graph is the deterministic *hire/pay* loop. Listing changes *catalog state*, not *task state* — it has no PIN gate, no escrow, no money. Bolting it into the graph would conflate "manage my listings" with "run a task," breaking the clean node==Task.status model (plan.md §5). The graph stays exactly the 20 edges in `agent.py` today.

### P3-5.2 The hire loop is byte-for-byte unchanged; only `pay_completion`'s body differs

The graph edges in `app/agent.py` do **not** change. A hire of alice's listed skill traverses the identical `market` route (`agent.py:97`): `authorize_base_payment → create_hire_checkout → verify_hire_cart → pay_base_into_escrow → grant → dispatch → collect → revoke → verify_work → approve_payout → pay_completion → settle_escrow → receipt_terminal`. The **only** difference is inside `pay_completion`, which now reads `owner_account` and splits. Both PIN gates, escrow, grant/revoke, and verify are untouched.

### P3-5.3 The owned-FREE-run path is confirmed untouched

An **owned** skill run (skill_store=="owned") routes `verify_work → [owned_checks_pass] → receipt_terminal` (`agent.py:142`) and **never reaches `pay_completion`**. `receipt_terminal` already zeroes `total_cents` for owned runs (`terminals.py:152-155`). **Only LISTED-and-hired skills earn; owned skills run by their owner still move no money.** The split code lives only in `pay_completion`, which the owned path does not visit — so there is zero risk of accidentally charging an owned run. This preserves the audit §7 "owned-run-is-free" invariant exactly.

---

## P3-6. The hard design questions (2–3 options each, tradeoff, recommendation)

### P3-6a. LISTING — how does a user list a skill, and what gets written? Can you list a Phase-2 owned skill?

**What gets written (all three, atomically in `list_skill`):** (1) `skill_ownership` row `(owner_id, skill_id, "agent:owner:<owner_id>")`; (2) the card's `owner_account` set + registered into the **marketplace** registry under `(owner_id, skill_id)`; (3) the card's files under `agent-skills/<owner_id>/<slug>/` so `seed_catalog` re-loads it after restart.

- **Option A — List only NET-NEW cards (a fresh seller skill authored directly into the marketplace).** *Pros:* simplest mental model; the marketplace and owned stores never overlap. *Cons:* throws away the Phase 2 narrative — a user who *built & owns* a skill can't sell it; "build → own → **list → earn**" is broken.
- **Option B — List a Phase-2 OWNED skill by PROMOTING a copy into the marketplace (RECOMMENDED).** `list_skill` reads the owner's existing `owned-skills/<owner_id>/<slug>/` card, sets `owner_account`, and writes a marketplace copy at `agent-skills/<owner_id>/<slug>/` + the ownership row. The **owned copy stays** (owner keeps running it free); the **marketplace copy earns** when *others* hire it. *Pros:* completes the full loop (build→own→list→earn); reuses the exact card the builder already produced; two clean copies with two clean behaviors (free-for-me, paid-for-others). *Cons:* two on-disk copies of one card (acceptable — content is small files; the audit explicitly keeps content as files). Must dedupe at selection so the owner hiring *their own* task still takes the **owned/free** route, not the market/paid one (see §P3-6b).
- **Option C — Single card, a `listed: bool` flag, no copy.** *Pros:* one copy. *Cons:* collapses the two-store separation the whole system is built on (audit §7 "two-lifetime stores never conflated"); a listed owned skill would have to be *both* free (for owner) and paid (for others) from one registry entry — exactly the conflation Phase 1/2 forbid. **Reject.**

**Recommendation: B.** It's the only option that delivers the Phase 3 thesis ("build → own → **list → earn**") and it respects the two-store invariant: owned store = free-for-owner, marketplace store = paid-for-hirers, and listing is a *promotion that copies owned→marketplace* with `owner_account` attached. For the demo we can pre-seed alice's skill straight into the marketplace (skipping a live build) — B degrades gracefully to "seed a listed card" without needing a prior Phase-2 build on camera.

### P3-6b. BUYER vs OWNER identity at hire — routing to the SKILL's owner, and the wash-trade question

- **Where `owner_account` comes from at payout:** the **selected `skill_card`**, threaded through `node_input` from `select_specialist` (`discover.py:153`) to `pay_completion` (`payout.py:199`). It is the **skill's** owner, *never* the hirer's `ctx.state["user_id"]`. So the money **structurally** routes to alice (the lister) no matter who hires — the payout code never even reads the buyer's identity when deciding the destination. This is the correct-by-construction answer to "the split must route to the skill's owner, not the hirer."
- **The wash-trade question — a user hiring their OWN listed skill:**
  - **Option A — Allow it; it's economically self-limiting (RECOMMENDED).** If buyer == owner, escrow (funded from the buyer's **spendable** `<user_id>` wallet) releases `base + 90%completion` into their **`agent:owner:<id>` earnings** account (non-spendable, decision #1) and `10%completion` to `broker`. Net effect: they **lose the 10 % commission** and **move the rest into a non-withdrawable earnings bucket**. It is strictly value-destroying — not a free wash — so no exploit exists, and no special-case code is needed. *Pros:* zero new logic; the non-spendable earnings account + broker commission already make self-hire irrational. *Cons:* a confused user could burn commission on themselves.
  - **Option B — Block self-hire with a guard** (`if owner_id == ctx.state["user_id"] and skill_store=="market": route to the owned/free path or refuse`). *Pros:* prevents the confused-user footgun. *Cons:* net-new branch; and for an owner who genuinely wants to *test their listing's* paid path, it's an obstacle. ⚠️SCOPE-adjacent.
  - **Option C — Silently reroute buyer==owner to the free owned path.** *Cons:* surprising (they clicked "hire", got a free run); muddies the demo's money story. **Reject.**

**Recommendation: A (allow, rely on economics), with the demo using DISTINCT identities** — seller **alice**, buyer/operator **me** — so the earnings visibly flow *between* two principals and the wash question never arises on camera. If a guard is wanted later, Option B is a one-line addition. **Because Option B (dedupe/self-hire) matters for §P3-6a Option B's "owner hiring their own task,"** note: an owner whose task matches *both* their owned copy and their listed marketplace copy should take the **owned/free** route (selection prefers the owned store for the owner's own runs) — that dedupe is the same `buyer==owner` check and is worth confirming ([§P3-9 Q2](#p3-9-open-questions--assumptions)).

### P3-6c. SEEDING real owners without a signup UI

The goal: 2–3 **real** `users` rows (+ wallet + keypair) so the ledger and PIN gates work unmodified, created without building a signup screen.

- **Option A — Idempotent seed script that calls the EXISTING `/auth/register` over HTTP (RECOMMENDED).** A `seed_accounts()` (run once at startup or as a `scripts/seed_demo.py`) POSTs to `/auth/register` for `alice@marvis.local` and `operator@marvis.local` with demo passwords + PINs, skipping any email that already exists (register returns 409). This exercises the **real** register path (`auth.py:93`) → creates `users` + `user_keys` (EC P-256 JWK) + `wallets` + an `auth_sessions` token, identically to a human signup. Then `POST /wallet/topup` funds the **buyer** so they can afford a hire. *Pros:* zero new auth code; produces genuine accounts indistinguishable from real signups; PINs work at both gates. *Cons:* needs the server up when the seed runs (fine for a startup hook or a one-shot script). **No secrets in code** — demo passwords/PINs come from `.env` (e.g. `DEMO_ALICE_PIN`), never hardcoded.
- **Option B — Direct DB inserts mirroring `auth.register`'s statements.** *Pros:* no running server needed. *Cons:* duplicates the register logic (bcrypt hash, keypair gen, wallet row) — a second place to drift from `auth.py`. Use only if a no-server seed is required.
- **Option C — A single "operator acts as everyone" pseudo-multi-user.** *Reject:* that's exactly the single-owner-by-construction state the audit says Phase 3 must escape; it can't route earnings *between* principals.

**Recommendation: A.** "**List as alice**" is then expressed as: `list_skill(owner_id=<alice's user_id>, skill_id="skill-linkedin-writer", owner_account="agent:owner:<alice_id>")` — the seed resolves alice's real `user_id` from her registered account and passes it in. The buyer (operator/me) logs in normally and hires; the split routes to `agent:owner:<alice_id>`. **No new auth, no seller role column** — a "seller" is just a `users` row that appears as `owner_id` in a `skill_ownership` row.

---

## P3-7. Build sequence — small, independently testable milestones (risky money-split FIRST)

Ordered so the **split math is proven in isolation before any listing UX and before the revenue tab.** Each has a one-line done-test.

| # | Milestone | Done-test (run to confirm) |
|---|---|---|
| **P3-M0** | **Pure split function, no graph, no DB.** Extract the split arithmetic into a testable pure fn `compute_split(base, completion, owner_account) -> list[(account, amount, reason)]` and add `release_from_escrow(task_id, to_account, amount, reason)` to `escrow/operations.py`. | Unit test: `compute_split(100,155,"agent:owner:alice")` → `[(owner,240,'payout_owner'),('broker',15,'payout_commission')]`, Σ==255; `compute_split(100,150,None)` → `[('broker',250,'payout_broker')]`, Σ==250. **The risky money math is proven here, before anything else.** |
| **P3-M1** | **Wire the split into `pay_completion`.** Replace `release_to_agent(total)` at `payout.py:206` with the `compute_split` legs. No listing yet — drive it with a hand-set `owner_account` on a card. | Hire a card with `owner_account="agent:owner:alice"` → `agent:owner:alice` += `base+90%comp`, `broker` += `10%comp`, `escrow:{task}==0`, `settle_escrow` passes, `verify_chain` valid. Same hire with `owner_account=None` → `broker` += `total`, escrow 0. |
| **P3-M2** | **Seed real owner accounts (§P3-6c-A).** `seed_accounts()` registers alice + operator (idempotent); topup buyer. | `GET /wallet/balance` for both returns 200 with a real token; alice + operator have `user_keys` rows; re-running the seed is a no-op (409-skip). |
| **P3-M3** | **Listing write-path (§P3-6a-B).** `list_skill(...)` writes the `skill_ownership` row + sets `owner_account` + registers the card `(alice, skill_id)` + writes `agent-skills/alice/<slug>/`. Extend `seed_catalog` to descend owner dirs. Thread `owner_id` through `select_specialist` (the audit §A-4 ripple). | After `list_skill` + restart: `GET /marketplace/agents` shows alice's linkedin-writer with `owner_account` set; `skill_ownership` has the row; `select_specialist` on a LinkedIn task resolves **alice's** card (owner threaded, no `KeyError`). |
| **P3-M4** ⭐ | **SHIPPABLE PHASE 3 — full earnings loop.** operator (buyer) hires alice's listed skill end-to-end through the unchanged graph → split fires → alice earns, broker earns, escrow settles. | ⭐ **From a funded operator wallet, "Write a LinkedIn post…" → hire alice's skill → PIN #1 → work → PIN #2 → payout splits: `agent:owner:<alice>` grew by `base+90%comp`, `broker` grew by `10%comp`, buyer wallet down by `total`, `escrow==0`, `get_all_account_sum()==0`. Re-run: alice's earnings keep growing.** |
| **P3-M5** *(separable — own prompt)* | **Broker-revenue + owner-earnings read (§P3-8).** Extend `get_platform_stats`: add `broker` SUM, `per_owner` group over `agent:owner:%`, and **exclude** `agent:owner:%` from the specialist `per_agent` list. | `GET /platform/stats` returns `broker_revenue_cents`, `commission_cents`, `per_owner[]`; the existing `per_agent[]` no longer double-counts owner earnings. |
| **P3-M6** *(separable — frontend)* | **Broker-revenue tab + Alice-earnings view.** New card in `PlatformVolume.tsx` (broker revenue, commission-to-date) + optional owner-earnings panel showing `agent:owner:alice` grow live. | Both render in the browser from the M5 read; recording shows alice's balance tick up as she's hired. Marked **separable from the core money logic.** |

**Shippable Phase 3 = P3-M4.** M5/M6 are the read/visual surface and can be a follow-up prompt. The risky money-split (M0/M1) is proven **before** listing (M3) and **before** the tab (M5/M6), per the ordering discipline.

Failure paths to also test: verify-fail on a listed hire → completion refunded to **buyer**, base swept per §P3-9 Q3, escrow reconciles; unowned hire → 100 % broker, no owner row touched; buyer==owner self-hire → economically self-limiting per §P3-6b-A (or blocked if Q2 chooses the guard).

---

## P3-8. A2UI / frontend — the broker-revenue surface (SEPARABLE)

Both surfaces below are **reads over the ledger the split already writes** — no new money logic, deferrable to their own prompt (audit §6 confirms the home is `get_platform_stats`).

1. **Extend `get_platform_stats` (`wallet.py:234`):**
   - `broker_revenue_cents = SUM(delta_cents) WHERE account_id='broker' AND delta_cents>0`
   - `commission_cents     = SUM(...) WHERE account_id='broker' AND reason='payout_commission'`
   - `per_owner = GROUP BY account_id WHERE account_id LIKE 'agent:owner:%' AND delta_cents>0` → `[{owner_id, earned_cents}]`
   - ⚠️ **Fix the existing `per_agent` / `total_paid_to_agents_cents` filters** (`wallet.py:257,267-273`): they use `account_id LIKE 'agent:%'`, which now also matches `agent:owner:<id>`. Add `AND account_id NOT LIKE 'agent:owner:%'` so specialist earnings and owner earnings don't merge. **This is the one stats-correctness change the split forces.**
2. **Frontend (`PlatformVolume.tsx` + `api.ts`):** a "Platform / Broker revenue" card (total commission, unowned-payout, hire count) and an optional **owner-earnings** panel rendering `per_owner` so Alice's `agent:owner:alice` balance visibly grows on camera. Same fetch mechanism as today (`GET /platform/stats`).

**Marked separable:** the core money logic (P3-M0–M4) is complete and correct without any of §P3-8; the tab only *visualizes* what's already in the ledger.

---

## P3-9. Open questions & assumptions

**Must-confirm (blocking):**
- **Q1 — Accept that listed/unowned skills stop paying `agent:<agent_name>`?** After Phase 3, a *listed* skill pays `agent:owner:<id>` and an *unowned* (marvis-seeded) skill pays `broker` — the Phase 1 `agent:<agent_name>` earnings account goes **vestigial** (audit §B risk #1). This is the direct consequence of decision #4. **Recommendation:** accept it — it's the point; `agent:owner:<id>` + `broker` replace the flat `agent:<name>` payout. *(Conflict with Phase 1's "escrow→agent:name" pattern → **Phase 3 wins**, localized to `pay_completion`.)* Confirm.
- **Q2 — Owner hiring their OWN skill: allow (economics self-limit) or guard?** §P3-6b recommends **allow + distinct demo identities**. If you want the footgun closed, add the one-line `buyer==owner` guard (also used to prefer the owned/free route for an owner's own task under §P3-6a-B). **Recommendation:** allow for Phase 3; add the guard only if the demo hires as alice herself. Confirm.
- **Q3 — On verify-FAIL of a listed hire, where does the non-refundable BASE sweep?** Today base stays in escrow and is "later swept to the agent" (audit §2). Under the split, the natural targets are: **(a)** sweep base 100 % → `agent:owner:<id>` (owner keeps their non-refundable base even on failure — consistent with "base = owner's hiring fee"); or **(b)** split the base too. **Recommendation: (a)** — base is the owner's non-refundable hiring fee, so on failure it sweeps entirely to the owner (broker only ever commissions *completed* work). Confirm the sweep target + which node performs it (currently base-sweep-on-fail is implicit; may need an explicit leg).

**Assumptions (will proceed on these unless corrected):**
- **A1 — Owner earnings → `agent:owner:<owner_id>`** (decision #1), a **non-spendable** account distinct from the owner's `<user_id>` wallet. No withdrawal path in Phase 3 (out of scope).
- **A2 — Broker → the string `"broker"`** (decision #2), separately SUM-able, **never** the operator's personal `<user_id>` wallet.
- **A3 — Commission = 10 % of COMPLETION only** (decision #4), base 100 % to owner; **unowned ⇒ broker keeps base+completion**. Rate from `config.COMMISSION_RATE_BPS`/`COMMISSION_BASIS` (decision #5), **not** a per-card field.
- **A4 — Penny-exact:** floor `commission=(completion*BPS)//10000`; derive `owner_cut=total−commission`; skip zero-cent legs. Escrow settles to 0 for all inputs (§P3-4.2).
- **A5 — Listing is out-of-graph** (§P3-5.1): a demo seed `seed_listings()` (primary) and an optional separable `POST /skills/list` (general). No delist/edit/CRUD UI.
- **A6 — Listing a Phase-2 owned skill = PROMOTE a copy owned→marketplace with `owner_account`** (§P3-6a-B); owned copy stays free-for-owner, marketplace copy earns-from-others.
- **A7 — Real owners via existing `/auth/register`** (§P3-6c-A), idempotent seed, buyer topped-up; "list as alice" resolves alice's real `user_id`. **No new auth, no seller role.**
- **A8 — `owner_id` threaded through `select_specialist`** (the audit §A-4 ripple) so non-`marvis` seller cards resolve; registry already `(owner_id, skill_id)`-keyed.
- **A9 — Reason strings** `payout_owner` / `payout_commission` / `payout_broker` chosen so `get_platform_stats` groups revenue without new plumbing.
- **A10 — The broker-revenue read/tab (§P3-8) is separable** and may land in a follow-up prompt; core money logic (P3-M0–M4) is complete without it.

**Conflicts with Phase 1/2 patterns → resolution:**
- **`pay_completion` pays `agent:<agent_name>` (Phase 1).** Phase 3 needs owner/broker routing. **Phase 3 wins** — localized to `pay_completion`; `agent:<agent_name>` becomes vestigial for listed/unowned skills (Q1).
- **`get_platform_stats` groups all `agent:%` as specialist earnings.** `agent:owner:<id>` collides with that prefix. **Phase 3 wins** — exclude `agent:owner:%` from `per_agent` (§P3-8); additive, one filter clause.
- **Marketplace store is flat/`marvis`-only in `seed_catalog`.** Listing a non-marvis seller needs owner-descent. **Additive** — reuse the `_seed_dir_flat(dir, reg, owner_id)` seam `seed_owned_library` already uses; no override.
- Everything else is additive; no other Phase 1/2 pattern is overridden. All audit §7 invariants (zero-sum, balance-derived, never-debit-before-confirm, base-nonrefundable/completion-refundable, escrow-settles-to-0, two PIN gates, grant least-privilege + dual-revoke, two-lifetime stores, owned-run-is-free, idempotent seeding) are preserved — the 3-way split nets 0, escrow still drains to 0, and only the market payout path is touched.

**Open questions still needing input:** Q1 (vestigial `agent:<name>`), Q2 (self-hire allow/guard), Q3 (base-sweep-on-fail target). Everything else assumed as above.

---

*End of Phase 3 plan. Awaiting approval before building. Suggested first action on approval: P3-M0 → P3-M1 (prove and wire the split math in isolation) — the risky money piece — before seeding owners (P3-M2), the listing write-path (P3-M3), the shippable end-to-end loop (P3-M4), and only then the separable revenue tab (P3-M5/M6).*
