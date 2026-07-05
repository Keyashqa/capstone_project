# Marvis — Phase 2 Implementation Plan

**The self-extending registry: when no skill fits, hire a BUILDER skill that outputs a new, permanent SkillCard.**

Status: PLAN ONLY — no code is written yet. Read [§P2-9 Open Questions](#p2-9-open-questions--assumptions) and confirm before any build starts. This document is a **Phase 2 addendum** to `plan.md`; it assumes Phase 1 is complete and working, and reuses its machinery verbatim wherever possible.

> **Scope of Phase 2 — ONE new idea.** When Marvis gets a task and **no existing skill matches** (a genuine capability gap), it **hires a BUILDER skill from the marketplace via the exact Phase 1 loop**. The builder outputs a **new SkillCard** (specialized instruction + acceptance_criteria + a `required_capability` drawn ONLY from existing tools + a deterministic `agent_name`). The new SkillCard is **persisted permanently into Marvis's OWN owned-skills library** (an asset Marvis buys once and owns — **not** the marketplace, **not** the broker catalog). Marvis re-runs selection, the new skill now matches from the owned library, the single runtime wears it (a **self-issued** temporary grant + AgentCard, **no re-hire, no payment**) and completes the **original** task. The next identical request skips the builder entirely and runs for free (owned).
>
> **Two stores, never conflated.** (1) The **marketplace** (`agent-skills/`, broker :8002) hosts skills Marvis **rents/hires** from third-party sellers, pay-per-use — *unchanged*. (2) Marvis's **owned-skills library** (NEW, `app/marvis/owned-skills/`) holds skills Marvis **owns outright**, produced by the builder and seeded into Marvis's own registry at startup. The builder is itself a legitimate marketplace skill Marvis hires; only the builder's **output** lands in the owned library.
>
> **Explicitly out of scope:** code generation, dynamic tool loading, sandboxing new tools, inventing MCP tools, make-vs-buy economics, a savings dashboard, multi-tool skills.

---

## P2-0. Grounding: what Phase 1 actually is *as built* (read this first)

Phase 1 evolved past `plan.md`. Phase 2 must splice into the **real** code, not the original DocReader/DocWriter sketch. The load-bearing facts:

| Fact (as built) | Where | Why it matters for Phase 2 |
|---|---|---|
| **Skills are files, not code.** Each skill = `app/marketplace/agent-skills/<slug>/{skill.json, instruction.md}`. | `marketplace/seed.py: _load_skill_card`, `seed_catalog` | Write-back **mirrors this file pattern but into a SEPARATE owned-skills folder** (`app/marvis/owned-skills/`, §P2-2) — never this marketplace folder. Permanence across restart is a filesystem write — no new persistence layer needed. |
| **In-memory registry seeded at startup** from that folder. | `skill_registry.py: InMemorySkillRegistry`, `agent.py: seed_catalog()` | Marvis's **owned-skills library reuses this exact pattern** via the same registry (both stores load into it at startup). Write-back **both** writes the owned folder (permanent) **and** `registry.register(card)` (live, so re-selection sees it this run). |
| **Broker keeps its own copy** of the catalog, read from the same folder. | `broker_server/skill_router.py: _default_catalog` | The built skill is **owned, not for-sale** — it must **NOT** touch the broker catalog. Write-back **never refreshes the broker** (which removes the split-brain risk entirely). |
| **Seed catalog is 6 skills:** `{twitter, instagram, linkedin} × {writer, reviewer}`. | `agent-skills/` | ⚠️ **LinkedIn already exists.** The flagship demo needs LinkedIn to be the *hole*. See [§P2-9 Q1](#p2-9-open-questions--assumptions) — we must remove the LinkedIn skills from the seed. |
| **Selection is deterministic/rule-based.** `_channel_key()` maps free-text → `{twitter,instagram,linkedin}`; `select_specialist._score()` gives **+2 for platform-in-skill_id**, +1 for role match. | `workflow/nodes/discover.py` | This is the **gap-detection lever**: a genuine gap = *no candidate scores the platform match*. No LLM needed to detect the gap. |
| **Two MCP tools only:** `create_doc` (write), `get_doc_content` (read). | `runtime/specialist.py`, `capability/gdocs_session.py` | The builder may reference **only these**. Writer→`create_doc`, reviewer→`get_doc_content`. Anything else = fabricated tool = build FAILS. |
| **`agent_name` convention:** `<Platform>Post{Specialist,Reviewer}`. | all `skill.json` | Builder output must follow this deterministically (never LLM-freestyled). |
| **Grant expects exactly ONE tool** and fails on empty `required_capabilities`. | `workflow/nodes/capability.py: grant_capability` (`"grant_failed"` route) | The **builder skill needs no gdocs tool** — this forces a design decision (see [§P2-5b](#p2-5b-builder-hire-does-the-builder-need-a-grant)). |
| **Per-skill keypair auto-mints** for any `skill_id` on first access. | `keys.py: skill_public_key_dict → _load_or_generate` | A newly-built skill gets its signing identity **for free** at persist time. No new key infra. |
| **Escrow holds base+completion at hire** with one PIN + one AP2 mandate; released at payout. | `workflow/nodes/hire.py: pay_base_into_escrow`, `payout.py` | Build fee is a **separate hire** with its own escrow lifecycle. Gap is detected **before** the original task escrows anything — so no nested-escrow problem (see [§P2-5c](#p2-5c-payment-model-honest)). |
| **PIN gate is A2UI + `RequestInput(interrupt_id=…)` + resumable.** | `hire.py: authorize_base_payment`, `_build_hire_summary_a2ui` | The build-approval PIN reuses this card builder verbatim. |

---

## P2-1. REUSE MAP (net-new list kept deliberately short)

Legend: **REUSE** = used verbatim / already generic enough · **ADAPT** = small, localized change to an existing file · **NET-NEW** = genuinely new code.

| Phase 2 component | Verdict | Detail |
|---|---|---|
| Hire loop (authorize → checkout → verify cart → escrow) | **REUSE — builder hire ONLY** | `hire.py` nodes run unchanged for the **builder hire** (a real marketplace seller). The **owned-skill run does NOT hire** — see below. |
| AP2 sign/verify, CartMandate, broker | **REUSE — builder hire ONLY** | `broker_client.py`, `broker_server/*`, `pay_base_into_escrow`. Only the builder is a broker line item; the owned skill never touches the broker. |
| Wallet / ledger / escrow | **REUSE — builder hire ONLY** | `wallet.py`, `escrow/operations.py`. Builder gets an `agent:{builder_name}` account; build escrow is `escrow:{build_task_id}`. The owned-skill run moves **no money**. |
| Payout + settle | **REUSE — build purchase ONLY** | `payout.py` releases the **build** completion after validation (the one-time purchase). The owned-skill run has **no payout** — Marvis owns it. |
| PIN gate + A2UI card builder | **REUSE / light theme** | `authorize_base_payment` + `_build_hire_summary_a2ui`. Build-approval card is the same shape with "Commission LinkedInWriter (one-time)" copy. |
| **Grant → dispatch → verify → revoke for the OWNED-SKILL run** | **REUSE** | The post-build run of the original task reuses `grant_capability` (self-issued) / `dispatch_to_specialist` / `verify_work` / `revoke_capability` verbatim, but **skips** `authorize_base_payment`/`create_hire_checkout`/`pay_base_into_escrow`/`pay_completion`. |
| Single specialist runtime | **ADAPT** | `runtime/specialist.py` gains ONE branch: if the worn skill is the builder, generate a **SkillCard JSON** (Gemma, `format="json"`) instead of calling a gdocs tool. |
| `grant_capability` / `dispatch` | **ADAPT (small)** | Handle the **zero-capability builder**: skip the grant (no MCP tool to lend) and dispatch the builder runtime without a `grant_token`. One `if` per node. |
| `discover_specialists` / `select_specialist` | **ADAPT (the brain)** | Add **gap-detection over BOTH stores** (marketplace + owned) + route the outcome to `market` / `owned` / `gap`. Everything else in these nodes stays. |
| Intake | **REUSE** | `intake_task` already extracts `channel` ∈ {twitter,instagram,linkedin} + type. No change (already knows all three platforms). |
| Verify | **REUSE** | `verify_work` already handles per-channel limits incl. linkedin=3000. Once LinkedInWriter is owned, its output verifies with the **existing** code (owned run routes verify → receipt, no payout). |
| **Gap-detection branch (both stores)** | **NET-NEW (tiny)** | A coverage check across marketplace + owned registry, + graph routes. ~1 function. |
| **BuilderSkillCard** (builder as a marketplace skill) | **NET-NEW (data only)** | One new `agent-skills/skill-builder/{skill.json, instruction.md}` — this one legitimately **stays in the marketplace**. Zero `required_capabilities`. No new code. |
| **Builder-OUTPUT SkillCard: generation + validation + write-back** | **NET-NEW (the real work)** | (1) runtime builder branch, (2) `builder/validate.py` schema+tool+dedup+quality gate, (3) `builder/persist.py` writes the **owned** folder + registers into Marvis's registry (**no broker refresh**). |
| **Seed the owned-skills library at startup** | **NET-NEW (tiny)** | A mirror of `seed_catalog()` pointed at `app/marvis/owned-skills/`, called alongside it in `agent.py`. Makes built skills survive restart. |
| **Re-selection after write-back** | **ADAPT** | A graph edge that loops from `persist_skill` back into `discover_specialists` for the **original** task; it now finds the skill in the **owned** store. |

> **Over-design check.** Net-new reduces to **four small things**: (1) gap-detection (over both stores), (2) a builder SkillCard (pure data), (3) generate→validate→persist→re-select, (4) a one-line startup seed of the owned library (a literal copy of the existing `seed_catalog`). No new subsystem, sandbox, codegen, protocol, or tool. If any milestone below starts adding one, **stop — that's scope creep.** Flagged inline as ⚠️SCOPE.

---

## P2-2. Target Phase 2 architecture

No new processes. No new protocols. The builder branch splices **inside the existing Marvis Workflow graph** (:8000); the **builder hire** reuses the broker (:8002) and (optionally) the proxy (:8003) exactly as Phase 1 does. The only new *artifacts* are: a builder skill folder (in the marketplace), a `builder/` package (validate + persist), Marvis's **owned-skills library** folder + startup seed, and the new graph routes.

```
                         ┌──────────────────────────── MARVIS Workflow (:8000) ───────────────────────────┐
                         │                                                                                 │
   "Write a LinkedIn     │  intake_task ─▶ discover_specialists ─▶ select_specialist                       │
    post ..."            │                  (queries BOTH stores)          │                               │
                         │                                     ┌───────────┼──── coverage check ───────┐   │
                         │                                     │           │                           │   │
                         │                                 [market]     [owned]                      [GAP] │
                         │                                     │           │                           │   │
                         │                                     ▼           ▼                           ▼   │
                         │                       authorize_base_pay   grant_capability        ╔═ BUILDER SUB-FLOW ═╗
                         │                       (PIN #1) → Phase 1   (SELF-issued, no hire)   ║ (nested Phase 1    ║
                         │                       hire→work→verify     → dispatch → verify      ║  hire of a REAL    ║
                         │                       →pay→receipt         → revoke → receipt       ║  seller: skill-    ║
                         │                       (rented skill)       (owned skill, FREE run)  ║  builder)          ║
                         │                                                  ▲                  ║   │               ║
                         │  ┌─── RE-SELECTION (ADAPT: edge back to discover; ┘ now [owned]) ── ║ propose_build     ║
                         │  │                                                                  ║ (PIN #B, one-time)║
                         │  └───────────────◀──────── persist_skill ◀── validate_build ◀───── ║ dispatch(builder) ║
                         │         (owned library now covers the platform)                    ║ emits SkillCard   ║
                         │                                                                     ╚═══════│═════════╝
                         └─────────────────────────────────────────────────────────────────────────  │ ────────┘
                                                                                                       ▼
                       ┌───────── writes a NEW, PERMANENT, OWNED skill (NOT the marketplace) ──────────┐
                       │  app/marvis/owned-skills/linkedin-writer/skill.json                            │
                       │  app/marvis/owned-skills/linkedin-writer/instruction.md                        │
                       │  + registry.register(card)          (Marvis's own registry — NOT the broker)   │
                       │  + keypair auto-minted via skill_public_key_dict(skill_id)                      │
                       │  (seeded back into Marvis's registry at every startup → survives restart)       │
                       └────────────────────────────────────────────────────────────────────────────────┘
```

**Where the builder splices in:** exactly at the `select_specialist` decision, which now checks **both** stores. Covered by the **marketplace** → unchanged Phase 1 hire (rented, pay-per-use). Covered by the **owned library** → a **local self-grant run** (no hire, no payment). **GAP** (neither store) → the builder sub-flow, which is **itself a full Phase 1 hire** of `skill-builder` (a real seller) and whose deliverable is a SkillCard **persisted into the owned library**. After persist, control loops back to `discover_specialists` for the **original** task, which now finds the skill in the owned store and takes the **free owned-skill run**.

---

## P2-3. Data models

### P2-3.1 BuilderSkillCard — the builder *as a marketplace skill* (pure data, no new schema)

The builder is **not** a special subsystem. It is a `SkillCard` (existing schema, `marketplace/skill_card.py`) with two distinguishing properties:

```jsonc
// app/marketplace/agent-skills/skill-builder/skill.json
{
  "skill_id": "skill-builder",
  "agent_name": "SkillBuilder",              // deterministic, like every other skill
  "display_name": "Skill Builder",
  "version": "1.0.0",
  "description": "Designs and commissions a NEW specialist skill when no existing skill covers a task. Outputs a SkillCard; composes only over existing tools.",
  "specialties": ["skill-building", "meta", "commission", "capability-gap"],
  "model": "ollama/gemma2:2b",
  "required_capabilities": [],               // ← ZERO. The builder invents BEHAVIOR, not tools.
                                             //    It calls no gdocs tool → needs no grant.
  "pricing": { "currency": "USD", "base_fee_cents": 100, "completion_fee_cents": 150 }
}
```
- `required_capabilities: []` is the honest encoding of "the builder never touches an MCP tool." It generates text (a SkillCard). This forces the small grant/dispatch adaptation in [§P2-5b](#p2-5b-builder-hire-does-the-builder-need-a-grant).
- `instruction.md` is the builder's system prompt: *"You are the Skill Builder. Given a capability gap {platform, role, original goal}, output a JSON SkillCard for a specialist that composes ONLY over the existing tools create_doc (write) and get_doc_content (read). …"* (full contract in §P2-4).
- Because it's a normal SkillCard, it is **hired through the identical Phase 1 loop** — its own pricing, its own `agent:SkillBuilder` ledger account, its own escrow, its own PIN.

> **Subtlety (keep these two straight):** the **builder card itself lives in the marketplace** and is a real skill Marvis rents (correct — there is a real seller to pay). Its **output** is an *owned* skill that lives in Marvis's owned library. Do not move the builder card out of the marketplace, and do not leave the output in the marketplace.

### P2-3.2 Builder-OUTPUT SkillCard — schema + validation contract

The builder must emit an object that parses cleanly as the **existing** `SkillCard` pydantic model. Beyond schema validity, it must pass the **build-acceptance gate** (§P2-5b/P2-4). Required fields and their validation:

| Field | Constraint (validated BEFORE persist) | Rejects |
|---|---|---|
| `skill_id` | matches `^skill-[a-z]+-(writer\|reviewer)$`; **not already in registry** | duplicate / malformed id |
| `agent_name` | matches convention `<Platform>Post{Specialist,Reviewer}`; **not already in registry** | renamed clone of an existing skill |
| `specialties` | must contain the requested **platform** key and the **role** token (`post-writing`/`post-review`) | mis-targeted skill that won't match on re-selection |
| `instruction` | non-empty, ≥ N chars, **mentions the platform** and its char limit | generic/empty clone |
| `required_capabilities` | **exactly ONE** entry; `mcp_server=="gdocs"`; `tool_name ∈ {create_doc, get_doc_content}`; role↔tool consistent (writer→create_doc, reviewer→get_doc_content) | ⚠️ **fabricated tool** (e.g. `post_to_linkedin`) → hard reject, build FAILS gracefully |
| `pricing` | base+completion ints > 0 | malformed pricing |
| `acceptance_criteria`* | *(carried on the skill or re-derived at task time)*; must be **platform-specific + verifiable** (references the platform char limit) | vague "make it good" criteria |
| `public_key` | **not** from the model — minted by Marvis via `skill_public_key_dict(skill_id)` at persist | model-invented keys |

\* Acceptance criteria for the *original task* already come from `intake_task`; the builder's job is the skill's `instruction` + `required_capability` + identity. Keeping criteria out of the model's required output reduces the small-model failure surface (see §P2-5a reliability note).

**On malformed/invalid output:** re-prompt the builder **once** (mirrors `intake_task`), re-validate; if it still fails → the build FAILS gracefully → `build_failed` terminal → build escrow refunded per policy (§P2-5c). **Nothing is persisted unless it passes validation** — permanence is earned, not assumed.

### P2-3.3 Two lifetimes — stated explicitly (do not conflate)

| | The built **SKILL** | The **GRANT** token |
|---|---|---|
| Lifetime | **PERMANENT** | **TEMPORARY** |
| Created by | `persist_skill` (write owned folder + register) | `grant_capability` (mint, self-issued for owned runs) |
| Lives in | `app/marvis/owned-skills/<slug>/` on disk + Marvis's own registry (**NOT** the marketplace, **NOT** the broker catalog) | in-memory grant registry (+ DB audit) |
| Ends | never (survives restart via the owned-library startup seed; deletion is a manual/admin act) | at task end: TTL expiry **or** `revoke_capability` |
| Scope | any future task on that platform, run for **free** (owned) | this one task_id, this agent_id, ONE tool |
| Demo line | "LinkedInWriter is now in Marvis's **owned** library — Marvis owns it outright" | "the grant that let it call create_doc has already expired" |

The built LinkedInWriter is a **permanent owned asset**; the grant that lets the runtime-wearing-LinkedInWriter call `create_doc` for *this* task is **temporary** and is revoked/expired exactly as in Phase 1. These are different objects in different registries.

---

## P2-4. Builder generation contract (structured output on Gemma-2b)

The builder runtime branch (in `runtime/specialist.py`) uses the **same hardening pattern as `intake_task`**: `ollama.chat(..., format="json", temperature≈0.2)` → JSON parse → schema+gate validation → re-prompt once → fail. The prompt is fully deterministic in its *scaffolding* so the model fills only the creative slots:

- **Marvis supplies** (not the model): `skill_id`, `agent_name`, `specialties` platform/role tokens, `required_capabilities` (derived from role: writer→`create_doc`, reviewer→`get_doc_content`), `pricing` (copied from a default/template), `model`. These are **computed from the gap** `{platform, role}` that gap-detection already extracted — the model does **not** get to invent them. This is the single biggest reliability win: the fields most likely to break the system (tool name, id, identity) are **not model-generated**.
- **The model supplies** only: the `instruction` prose (the genuinely-specialized system prompt) and, optionally, a one-line `description`. Even a shaky 2b model can write a platform-specific instruction; it cannot fabricate a tool because it never chooses the tool.

> **Reliability stance (Gemma-2b, CPU, structured output):** treat the builder exactly like `intake_task` — *constrained decoding + schema validation + one retry + graceful fail.* Minimize what the model must produce (instruction only); **derive** everything safety-critical. This sidesteps the classic small-model failure (hallucinated JSON keys / invented tools) by construction, not by hoping the model behaves.

This makes the "builder invents behavior only, never tools" constraint **structurally enforced**, not merely requested.

---

## P2-5. Control flow (state machine) + the hard design questions

### P2-5.0 The splice, as graph edges (ADAPT to `app/agent.py`)

```
select_specialist ──[market]──▶ authorize_base_payment    # covered by MARKETPLACE → unchanged Phase 1 rented-skill loop
                                                           #   hire→work→verify→pay→receipt
                  ├─[owned]───▶ grant_capability           # covered by OWNED library → local FREE run (see bottom block)
                  └─[gap]─────▶ propose_build              # NET-NEW route: neither store covers it

# ── BUILDER SUB-FLOW = a nested Phase 1 hire of skill-builder (a REAL marketplace seller — this hire is correct) ──
propose_build ──[PIN #B approve]──▶ create_hire_checkout(builder)     # REUSE hire.py, skill_id="skill-builder"
              └─[reject]──────────▶ cancelled_terminal
create_hire_checkout ▶ verify_hire_cart ▶ pay_base_into_escrow(build) # REUSE, escrow:{build_task_id}
    ▶ grant_capability            # ADAPT: builder has 0 caps → route "no_grant_needed" (skip lending)
    ▶ dispatch_to_specialist      # ADAPT: builder branch → runtime emits SkillCard JSON (no gdocs)
    ▶ collect_result ▶ validate_build          # NET-NEW gate (§P2-3.2)
          ├─[invalid]──▶ build_failed ▶ refund build COMPLETION ▶ refunded_terminal   # base non-refundable; nothing persisted
          └─[valid]────▶ pay_completion(build) ▶ settle_escrow(build)   # REUSE payout.py — this fee IS the one-time PURCHASE
                              ▶ persist_skill               # NET-NEW: write OWNED folder + register into Marvis's registry (NO broker)
                                    ▶ discover_specialists(ORIGINAL task)   # ADAPT: loop back, queries BOTH stores
                                          # platform now covered by the OWNED library → [owned] route ↓

# ── OWNED-SKILL RUN (the original task on an owned skill) — NO hire, NO escrow, NO payout, NO broker ──
grant_capability(self-issued) ▶ dispatch_to_specialist ▶ collect_result ▶ revoke_capability ▶ verify_work
     ├─[checks_pass]──▶ receipt_terminal          # done — Marvis owns the skill, so there is nothing to pay/release
     └─[hard_fail]────▶ output_failed_terminal    # no money to refund (run was free); user may retry for free
```

Node name == `Task.status`, same as Phase 1. Note the owned-skill run **reuses `grant/dispatch/collect/revoke/verify` verbatim** but has **no `approve_payout`/`pay_completion`** — verify routes straight to a terminal. `revoke_capability` still runs on every dispatch exit; for the builder dispatch (no grant) it's a no-op (revokes 0 grants) — safe and consistent.

### P2-5a. GAP DETECTION — the brain of Phase 2

**The requirement:** decide "no skill matches" without false gaps (matching too loosely → never builds) or false builds (refusing a skill that would've worked → builds a duplicate).

- **Option A — LLM decides the gap.** Ask Gemma "does any of these skills cover the task?" *Reject as primary:* non-deterministic on a 2b CPU model; exactly the wrong place to trust the small model; can hallucinate both a match and a gap.
- **Option B — Coverage predicate on the deterministic router, over BOTH stores (RECOMMENDED).** Reuse the machinery that already exists: `intake_task` yields `channel ∈ {twitter,instagram,linkedin}` and `type ∈ {doc_writing,doc_reading}` → `(platform, role)`. `select_specialist` already computes `_channel_key` and `_score` where **+2 = platform-in-skill_id**. Define the gap predicate over the **union of candidates from the marketplace registry AND Marvis's owned-skills registry**: **a gap exists iff no candidate in *either* store has a `skill_id` containing the requested `platform` key for the requested `role`.** Concretely: `max(_score(c) for c in market ∪ owned) < 2` ⇒ GAP. The route is then `market`, `owned`, or `gap` depending on **which store** the winning candidate came from. This is deterministic, free, and rides on code already in the repo.
- **Option C — Threshold on a similarity/embedding score.** *Reject:* adds an embedding dependency and a magic threshold — the exact "false gap / false build" tuning nightmare the brief warns about, with no upside over B given platforms are a closed, known set.

**Recommendation: B.** The platform set is small and closed (`twitter/instagram/linkedin`) and `intake_task` already classifies into it, so "is platform P covered by either store?" is an exact set-membership test, not a fuzzy judgment. This is why B has **near-zero false-gap/false-build risk**: the gap is defined on the same deterministic key the selector already scores on. After a build, the owned store covers the platform, so the identical task re-selects to the `owned` route (free) — **the builder never fires twice for the same platform.**

> **Guard against the current false-match bug:** today `discover_specialists` returns *any* writer for `type=doc_writing` (they all carry the `doc-writing` specialty), so a LinkedIn task would silently select a **Twitter** writer (score 1, platform miss). Phase 2's coverage predicate turns that silent false-match into an explicit `gap`. **This is a real behavior change to flag** ([§P2-9 Q2](#p2-9-open-questions--assumptions)): after Phase 2, a platform miss builds instead of mis-serving.
>
> **Gemma reliability note:** the *only* place the model touches gap-detection is upstream, in `intake_task`'s channel extraction — already hardened (format="json" + schema validation + 1 retry). If intake can't resolve a channel, that's an intake failure (existing `intake_failed` path), **not** a gap. So a mis-parse never silently triggers a build.

### P2-5b. Builder hire — does the builder need a grant?

**The requirement:** the builder must emit a valid, genuinely-specialized SkillCard — not a renamed clone, not a card citing a non-existent tool — and must fail gracefully on bad output.

- **Design decision (grant):** the builder has `required_capabilities: []` because it calls **no MCP tool**. Two ways to handle the grant node:
  - **Option A — Skip the grant for zero-cap skills (RECOMMENDED).** `grant_capability` adds: `if not required_caps: return route "no_grant_needed"` → dispatch runs the builder runtime **without** a `grant_token`. Honest ("nothing to lend"), one `if`, keeps the "builder invents behavior, never tools" property literally true. `revoke_capability` later revokes 0 grants — consistent.
  - **Option B — Mint a fake/empty grant.** *Reject:* invents a capability with no tool; muddies the clean "grant == lent tool" story for zero benefit.
- **Validation (the anti-clone / anti-fabrication gate), `builder/validate.py`:** runs the table in §P2-3.2. The three load-bearing checks:
  1. **Existing-tool check** — `tool_name ∈ {create_doc, get_doc_content}`. A fabricated tool (`post_to_linkedin`, `linkedin_api`) → **hard reject → build FAILS gracefully.** *This is where "if a task needs a tool that doesn't exist, the build FAILS — it does not fabricate a tool" is enforced.*
  2. **Anti-clone check** — `skill_id` and `agent_name` must not already exist, and `specialties` must include the *requested* platform. A card that's just "TwitterWriter renamed" fails because either its id collides or its platform token is wrong for the gap.
  3. **Specialization check** — `instruction` must be non-trivial and mention the platform + its limit. (Because Marvis *derives* id/tool/identity and the model writes only the instruction, this is the model's one real responsibility — easy to validate.)
- **On failure:** re-prompt once → re-validate → `build_failed` terminal. **Persist only on pass.**

**Recommendation: A + the validation gate.** The gate is deterministic (no LLM), so "is this a valid, specialized, existing-tool skill?" is decided by code, not by trusting Gemma's self-report.

### P2-5c. Payment model (honest) — pay ONCE

**The user pays ONCE on a first-time gap: the one-time BUILD FEE. That fee IS the purchase of an owned skill.** There is **no** separate "work fee" hire for the built skill — Marvis owns it and runs it on its own runtime for **free**. Every subsequent request on that platform is also **free** (owned). Building a reusable asset costs once; owning it costs nothing thereafter.

- **Only ONE transaction ever occurs for a gap:** the Phase 1 hire of `skill-builder` (a real seller). The original task, once the skill is owned, runs through `grant → dispatch → verify` with **no `authorize_base_payment`, no checkout, no escrow, no payout**. (Contrast a *marketplace* task, which still pays the seller per use — unchanged.)
- **Where does the ORIGINAL task's escrow sit during the build? It never exists.** Gap-detection fires at `select_specialist`, **before** any payment node. The build hire completes its own escrow lifecycle; then the original task runs on the now-owned skill with **zero** money movement. No double-holding, no nested escrow, no AP2 semantics to rethink.
- **The build escrow (`escrow:{build_task_id}`) is the only escrow:** base **non-refundable** (Phase 1 policy); completion **released when `validate_build` passes** — i.e. when a valid SkillCard has been produced and is about to be persisted as an owned asset. The build's "verification" is the **deterministic validation gate** (§P2-3.2), with the build-approval PIN (PIN #B) doubling as its payment authorization. If validation fails → build completion refunded, **base kept**, escrow closes, **nothing persisted**.
- **Key correctness point (asked in the brief):** *if the build succeeds but the later task output fails verification*, the **build fee is NOT refunded.** The skill was genuinely built and is now a permanent owned asset — the deliverable was the skill, not any one task's output. And because the owned-skill run is **free**, there is simply **nothing to refund** on the task side: a failed output just means the user re-runs it for free. This keeps the single build escrow settled strictly by its own deliverable (a valid, persisted skill) — consistent with Phase 1's ledger/escrow invariants.

**Recommendation:** one Phase 1 hire (the builder), then a free local run. Reuse `hire.py`/`payout.py`/`escrow/operations.py` verbatim for the **build purchase only**; the owned-skill run adds **zero** money-path code because it has no money path.

---

## P2-6. Build sequence — small, independently testable milestones

Ordered so the **risky bits (gap-detection §P2-5a, and registry write-back §P2-5b/persist) are validated before the full arc**. Each has a one-line done-test.

| # | Milestone | Done-test (run to confirm) |
|---|---|---|
| **P2-M0** | **Create the hole + add the builder card + owned-library scaffold.** Remove `agent-skills/linkedin-writer` (+ `linkedin-reviewer`, see Q1) from the marketplace seed; add `agent-skills/skill-builder/{skill.json, instruction.md}` (zero caps); create the empty `app/marvis/owned-skills/` folder + a `seed_owned_library()` mirror of `seed_catalog()` called at startup. | `GET :8002/.well-known/skills` lists `skill-builder` and **no** `skill-linkedin-*`; Marvis registry has 5 marketplace skills + 0 owned; `owned-skills/` seed runs clean. |
| **P2-M1** | **Gap detection over both stores (§P2-5a-B).** Add coverage predicate across marketplace + owned registries; route `market` / `owned` / `gap` out of `select_specialist`. | Flagship #2 "Write a LinkedIn post…" → routes to `gap` (NOT to a Twitter writer); "Write a tweet…" still routes to `market`. |
| **P2-M2** | **Builder runtime branch.** `runtime/specialist.py`: when worn skill is `skill-builder`, Gemma emits a SkillCard JSON (Marvis pre-fills id/tool/identity; model writes `instruction`). `format="json"` + 1 retry. | Given gap `{linkedin, writer}`, builder returns a dict that pydantic-parses as `SkillCard` with `agent_name=="LinkedinPostSpecialist"`, `tool_name=="create_doc"`. |
| **P2-M3** | **Validation gate (§P2-3.2 / P2-5b).** `builder/validate.py`: schema + existing-tool + anti-clone + specialization. | Fabricated-tool card → reject; duplicate id → reject; valid linkedin-writer card → accept. (Unit-testable in isolation, no money.) |
| **P2-M4** | **Owned write-back + re-selection (§P2-2).** `builder/persist.py`: write to `owned-skills/<slug>/`, `registry.register`, keypair auto-mints (**NO broker refresh**). Edge loops back to `discover_specialists`. | After persist: `app/marvis/owned-skills/linkedin-writer/` exists on disk; `registry.has("skill-linkedin-writer")`; the broker catalog is **unchanged** (no `linkedin` in `/.well-known/skills`); re-running `select_specialist` on the original task returns `owned` (LinkedInWriter). ***Risky bits proven here, before the full arc.*** |
| **P2-M5** | **Builder hire = nested Phase 1 loop (the ONE purchase).** Wire `propose_build` (PIN #B) → reuse `hire.py`/`payout.py` with `skill_id="skill-builder"`; `grant_capability` `no_grant_needed` branch. | Approving the build PIN moves build fee `user→escrow:{build_task}` then `escrow→agent:SkillBuilder`; `verify_chain(user).valid`; rejecting → `cancelled_terminal`, no money moves. |
| **P2-M6** | **FULL FLAGSHIP ARC.** Gap → build (pay once) → persist to owned → re-select → original LinkedIn task runs FREE on the owned skill (grant→dispatch→create_doc→verify→receipt, **no payment**). | ⭐ **SHIPPABLE PHASE 2.** "Write a LinkedIn post about X" from empty-of-LinkedIn state → new skill appears in the **owned** library → long-form post saved to gdocs → `receipt_terminal`. Ledger shows **only** the build fee charged. Immediately re-run "Write another LinkedIn post" → **skips builder, runs free** on the owned skill. |
| **P2-M7** | **A2UI: build-approval card + live registry surface (§P2-7).** | Build-approval PIN card renders ("Commission LinkedInWriter for $X? Approve/Reject"); after persist, a card shows the new skill now in the catalog. |
| **P2-M8** *(opt)* | **Persistence across restart.** Restart Marvis after a build. | The built LinkedInWriter is still present (re-seeded by `seed_owned_library()` from the owned folder written in P2-M4) and still absent from the broker — proves the owned skill is PERMANENT and local, vs the grant's TEMPORARY lifetime. |

Failure paths to also test: builder emits fabricated tool → `build_failed` + build **completion** refunded (base kept), nothing persisted (P2-M3+M5); build succeeds but the owned LinkedIn run's output later fails verify → build fee **kept**, and since the owned run is **free there is nothing to refund** — the user simply re-runs for free (P2-M6, per §P2-5c).

---

## P2-7. Where A2UI fits (reuse Phase 1's approval-card pattern)

Two surfaces, both reusing `hire.py:_build_hire_summary_a2ui` + `RequestInput(interrupt_id=…)` + `/auth/verify-pin`:

1. **Build-approval PIN gate (`propose_build`)** — the same card shape as the Phase 1 hire summary, copy changed to the one-time commission decision:
   > *"No skill for **LinkedIn** yet. Commission a **LinkedInWriter** specialist you'll **own**? One-time build fee **$1.00** (base, non-refundable) + **$1.50** on delivery. After this, all LinkedIn posts run on your own skill for **free**. [Reject] [Approve & Pay $1.00]"*
   Reuses the base/completion/total rows, the PIN `TextField` with the `^\d{4,6}$` check, and the `decision` event verbatim.
2. **Live "new owned skill appears" surface** — after `persist_skill`, emit an A2UI result card (reuse `dispatch.py:_build_result_card` shape): *"✅ LinkedInWriter added to **your owned skill library** — Marvis owns it and will handle all future LinkedIn posts for free."* Optionally render Marvis's owned-library list so the judge sees it grow live on camera. (This is Marvis's own library view — **not** the broker's `/.well-known/skills`, which stays unchanged.)

No new A2UI infrastructure — same tagged-SSE `<a2ui-json>` transport, same renderer, same PIN modal.

---

## P2-8. What is explicitly NOT changing (guard rails)

- **No new process, port, or protocol.** Broker (:8002) and proxy (:8003) unchanged; the **builder hire** rides A2A/UCP/AP2 as a normal skill.
- **Built skill is OWNED, local, a one-time purchase.** It is written to `app/marvis/owned-skills/` and registered in Marvis's own registry only. It **never** enters the marketplace or the broker catalog, is **never re-hired or re-paid**, and runs for **free** on Marvis's runtime forever after.
- **The owned-skill run reuses `grant/dispatch/verify/revoke` but SKIPS `hire/checkout/escrow/payout/broker`.** There is no seller, so there is no money path for it.
- **Only the builder is a marketplace skill.** The builder card stays in `agent-skills/`; only its *output* is owned. (Two different things — do not swap them.)
- **No code generation, no dynamic tool loading, no sandbox.** The builder emits *data* (a SkillCard). Its `instruction` is prose; its tool is chosen from a closed set of two.
- **No new MCP tool, ever.** Validation hard-rejects any `tool_name ∉ {create_doc, get_doc_content}`. A task needing a truly-new tool → `build_failed`, gracefully.
- **No multi-tool skills.** Built skills keep the Phase 1 one-tool invariant.
- **Verify/intake unchanged.** `intake_task` already knows all three platforms; `verify_work` already enforces linkedin=3000. The owned skill's *output* verifies with existing code (owned run routes verify → receipt, no payout).

---

## P2-9. Open questions & assumptions

**Must-confirm (blocking):**
- **Q1 — The LinkedIn hole conflict.** The seed **currently ships LinkedIn** (`linkedin-writer` + `linkedin-reviewer`). The flagship demo needs LinkedIn to be the missing platform. **Recommendation:** remove **both** `agent-skills/linkedin-writer/` and `agent-skills/linkedin-reviewer/` from the seed so the hole is clean and the live build is unambiguous. *Confirm:* remove both, or only `linkedin-writer` (leaving the reviewer would let a "review my LinkedIn post" task match while "write" builds — a subtler but noisier demo)? **I recommend removing both.**
- **Q2 — Accept the selection behavior change?** Today a platform-miss silently mis-serves (LinkedIn task → Twitter writer). Phase 2 turns that into an explicit `gap`/build. This is intended and correct, but it **changes existing Phase 1 behavior** for uncovered platforms. Confirm that's desired (it is the whole point).

**Assumptions (will proceed on these unless corrected):**
- **A1 — Builder = zero-capability SkillCard**, grant skipped via a `no_grant_needed` branch (§P2-5b-A). The builder never calls an MCP tool.
- **A2 — Marvis derives the safety-critical fields** (`skill_id`, `agent_name`, `required_capabilities`/tool, `specialties` tokens, `pricing`, `model`) from the detected `{platform, role}`; **Gemma writes only the `instruction`** (§P2-4). This is the core reliability decision.
- **A3 — Build fee is a ONE-TIME purchase** via a single Phase 1 hire of `skill-builder`; the user pays **once** on a first-time gap and the owned skill then runs **free** forever; there is **no** separate work-fee hire for the built skill; gap detected before any escrow, so no nested escrow (§P2-5c).
- **A4 — Build escrow settled by the validation gate** (deterministic), with the build-approval PIN doubling as its payment authorization; build base non-refundable; build fee **kept** even if the later owned run's output fails verify (the owned run is free — nothing to refund).
- **A5 — Permanence = writing `app/marvis/owned-skills/<slug>/`** (survives restart via a new `seed_owned_library()`) + live `registry.register`. **No broker catalog refresh** — the owned skill never touches the broker. Keypair auto-mints via `skill_public_key_dict(new_skill_id)`.
- **A6 — Builder handles both roles** (writer→`create_doc`, reviewer→`get_doc_content`) driven by the detected role; the flagship demos the writer.
- **A7 — Pricing on a built/owned skill is vestigial** (kept only for schema completeness — the owned skill is never sold or hired, so its `pricing` is never charged). What matters is the **builder's** own pricing (the one-time build fee). *Confirm the builder's price* (proposal: `base 100 / completion 150` cents as in §P2-3.1).
- **A8 — Re-selection loops back to `discover_specialists`** for the original task after persist (not a fresh user turn), querying **both** stores; the original `spec`/`goal_nl` are carried through the builder sub-flow in `node_input`.
- **A9 — Owned-skills library seeded at startup** by `seed_owned_library()` (a mirror of `seed_catalog()` pointed at `app/marvis/owned-skills/`), called from `agent.py` alongside the marketplace seed.

**Conflicts with Phase 1 patterns → resolution:**
- **`grant_capability` currently treats empty `required_capabilities` as `grant_failed`.** Phase 2 needs empty-caps to be legitimate (the builder). **Phase 2 wins:** add the `no_grant_needed` route; keep `grant_failed` only for a skill that declares caps but mis-declares them. (Localized to one node.)
- Everything else is additive; no other Phase 1 pattern is overridden.

**Open questions still needing input:** Q1, Q2, A7-price. Everything else assumed as above.

---

*End of Phase 2 plan. Awaiting approval before building. Suggested first action on approval: P2-M0 → P2-M1 → P2-M4 (create the hole, prove gap-detection, prove write-back + re-selection) — the three risky pieces — before wiring the full arc at P2-M6.*
