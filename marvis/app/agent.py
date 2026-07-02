"""Marvis — ADK Workflow graph (deterministic control flow).

Graph topology (§5 of plan.md; Phase 2 splice per plan2.md §P2-5.0):
  START
    └─▶ intake_task            Gemma parses goal_nl → spec
          └─▶ discover_specialists   fetches SkillCards from BOTH stores
                ├─[none]─▶ no_specialist_terminal
                └─[found]─▶ select_specialist   rule-match over market ∪ owned
                      ├─[market]─▶ authorize_base_payment   *** PIN GATE #1 *** (rented skill)
                      │                 ├─[cancelled]─▶ cancelled_terminal
                      │                 └─[confirmed]─▶ create_hire_checkout ─▶ verify_hire_cart
                      │                                       ├─[invalid]─▶ hire_invalid_terminal
                      │                                       └─[valid]──▶ pay_base_into_escrow ─┐
                      ├─[owned]───▶ grant_capability (self-issued, FREE) ◀──────────────────────┘
                      │                 ├─[grant_failed]───▶ verify_failed ─▶ refunded_terminal
                      │                 └─[granted]───▶ dispatch_to_specialist  (0-cap skills dispatch w/o a token)
                      │                       ├─[dispatch_failed]─▶ revoke_capability
                      │                       └─[dispatched]───────▶ collect_result ─▶ revoke_capability
                      │                             ├─[post_work]──▶ verify_work
                      │                             │     ├─[hard_fail|owned_hard_fail]───▶ verify_failed / output_failed_terminal
                      │                             │     └─[checks_pass]──▶ approve_payout *** PIN GATE #2 ***
                      │                             │           ├─[rejected]─▶ verify_failed ─▶ refunded_terminal
                      │                             │           └─[approved]─▶ pay_completion ─▶ settle_escrow ─▶ receipt_terminal
                      │                             │     [owned_checks_pass]──▶ receipt_terminal (nothing to release)
                      │                             └─[post_build]─▶ validate_build   (builder dispatch only)
                      │                                   ├─[invalid]─▶ build_failed ─▶ refunded_terminal
                      │                                   └─[valid]───▶ pay_completion ─▶ settle_escrow ─▶ persist_skill
                      │                                                       (writes OWNED library, loops back ↺ to discover_specialists)
                      └─[gap]─────▶ propose_build   *** PIN GATE #B *** (commission SkillBuilder — real seller)
                                          ├─[cancelled]─▶ cancelled_terminal
                                          └─[confirmed]─▶ create_hire_checkout ─▶ ... ─▶ grant_capability (builder, 0 caps)

The Workflow is deterministic — no LLM at the routing level.
LLM (local Gemma/Ollama) is used inside: intake_task, verify_work (advisory), specialist runtime
(incl. the Phase 2 builder branch, which only writes the `instruction` field — plan2.md §P2-4).
"""
from __future__ import annotations

from google.adk.apps import App, ResumabilityConfig
from google.adk.workflow import Workflow

from app.workflow.nodes.build import build_failed, persist_skill, propose_build, validate_build
from app.workflow.nodes.capability import grant_capability, revoke_capability
from app.workflow.nodes.dispatch import collect_result, dispatch_to_specialist
from app.workflow.nodes.discover import discover_specialists, select_specialist
from app.workflow.nodes.hire import (
    authorize_base_payment,
    create_hire_checkout,
    pay_base_into_escrow,
    verify_hire_cart,
)
from app.workflow.nodes.intake import intake_task
from app.workflow.nodes.payout import approve_payout, pay_completion, settle_escrow
from app.workflow.nodes.terminals import (
    cancelled_terminal,
    hire_invalid_terminal,
    no_specialist_terminal,
    output_failed_terminal,
    receipt_terminal,
    refunded_terminal,
    verify_failed,
)
from app.workflow.nodes.verify import verify_work

# ── Seed the skill catalog on startup ─────────────────────────────────────────
# (imported here so the registries are populated before any request arrives)
from app.marketplace.seed import seed_catalog, seed_owned_library  # noqa: F401, E402
from app.seed_demo import seed_demo  # noqa: E402

seed_catalog()
seed_owned_library()  # Phase 2: Marvis's owned-skills library (survives restart)
seed_demo()           # Phase 3: real seller "alice" + funded buyer + alice's listing

# ── Marvis Workflow graph ──────────────────────────────────────────────────────

root_agent = Workflow(
    name="marvis",
    description=(
        "Personal orchestrator that hires, pays, provisions, verifies, and settles "
        "with marketplace specialist agents. "
        "Flagship: 'Write a tweet about my Marvis launch and save it as a Twitter "
        "script in Google Docs.'"
    ),
    edges=[
        ("START", intake_task),

        (intake_task, {
            "intake_failed": no_specialist_terminal,
            "parsed":        discover_specialists,
        }),

        (discover_specialists, {
            "none":  no_specialist_terminal,
            "found": select_specialist,
        }),

        (select_specialist, {
            "none":   no_specialist_terminal,
            "market": authorize_base_payment,             # rented skill — Phase 1 hire loop
            "owned":  grant_capability,                    # owned skill — self-issued, FREE run
            "gap":    propose_build,                       # capability gap — commission the builder
        }),

        (authorize_base_payment, {
            "cancelled": cancelled_terminal,
            "confirmed": create_hire_checkout,
        }),

        (propose_build, {                                  # *** PIN GATE #B ***
            "cancelled": cancelled_terminal,
            "confirmed": create_hire_checkout,             # nested Phase 1 hire of skill-builder
        }),

        (create_hire_checkout, verify_hire_cart),

        (verify_hire_cart, {
            "invalid": hire_invalid_terminal,
            "valid":   pay_base_into_escrow,
        }),

        (pay_base_into_escrow, grant_capability),

        (grant_capability, {
            "grant_failed": verify_failed,
            "granted":      dispatch_to_specialist,  # incl. zero-cap skills (builder) — no token minted
        }),

        (dispatch_to_specialist, {
            "dispatch_failed": revoke_capability,
            "dispatched":      collect_result,
        }),

        (collect_result, revoke_capability),

        (revoke_capability, {
            "post_work":  verify_work,                   # normal task output (market or owned)
            "post_build": validate_build,                # builder's SkillCard deliverable
        }),

        (verify_work, {
            "hard_fail":         verify_failed,
            "checks_pass":       approve_payout,
            "owned_hard_fail":   output_failed_terminal,  # owned run failed — free, nothing to refund
            "owned_checks_pass": receipt_terminal,        # owned run passed — free, nothing to release
        }),

        (approve_payout, {
            "rejected": verify_failed,
            "approved": pay_completion,
        }),

        (validate_build, {
            "invalid": build_failed,
            "valid":   pay_completion,                    # releases the ONE-TIME build purchase
        }),

        (pay_completion, settle_escrow),

        (settle_escrow, {
            "settled":       receipt_terminal,            # market hire complete
            "build_settled": persist_skill,                # build purchase complete → write owned skill
        }),

        (persist_skill, discover_specialists),            # ↺ loop back — original task now finds it "owned"

        (verify_failed, refunded_terminal),

        (build_failed, refunded_terminal),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(is_resumable=True),
)
