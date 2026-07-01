"""Marvis — ADK Workflow graph (deterministic control flow).

Graph topology (§5 of plan.md):
  START
    └─▶ intake_task            Gemma parses goal_nl → spec
          └─▶ discover_specialists   fetches SkillCards, filters by specialty
                ├─[none]─▶ no_specialist_terminal
                └─[found]─▶ select_specialist   rule-match → AgentCard (deterministic agent_name)
                      └─▶ authorize_base_payment   *** PIN GATE #1 ***
                            ├─[cancelled]─▶ cancelled_terminal
                            └─[confirmed]─▶ create_hire_checkout   UCP CartMandate
                                  └─▶ verify_hire_cart
                                        ├─[invalid]─▶ hire_invalid_terminal
                                        └─[valid]──▶ pay_base_into_escrow   AP2 + ledger escrow
                                                    └─▶ grant_capability   mint CapabilityGrant
                                                          └─▶ dispatch_to_specialist   run Gemma+tool
                                                                └─▶ collect_result
                                                                      └─▶ revoke_capability   ALWAYS
                                                                            └─▶ verify_work   det+advisory
                                                                                  ├─[hard_fail]─▶ verify_failed ─▶ refunded_terminal
                                                                                  └─[checks_pass]─▶ approve_payout  *** PIN GATE #2 ***
                                                                                        ├─[rejected]─▶ verify_failed ─▶ refunded_terminal
                                                                                        └─[approved]─▶ pay_completion
                                                                                              └─▶ settle_escrow
                                                                                                    └─▶ receipt_terminal

The Workflow is deterministic — no LLM at the routing level.
LLM (local Gemma/Ollama) is used inside: intake_task, verify_work (advisory), specialist runtime.
"""
from __future__ import annotations

from google.adk.apps import App, ResumabilityConfig
from google.adk.workflow import Workflow

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
    receipt_terminal,
    refunded_terminal,
    verify_failed,
)
from app.workflow.nodes.verify import verify_work

# ── Seed the skill catalog on startup ─────────────────────────────────────────
# (imported here so the registry is populated before any request arrives)
from app.marketplace.seed import seed_catalog  # noqa: F401, E402

seed_catalog()

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
            "none":     no_specialist_terminal,
            "selected": authorize_base_payment,
        }),

        (authorize_base_payment, {
            "cancelled": cancelled_terminal,
            "confirmed": create_hire_checkout,
        }),

        (create_hire_checkout, verify_hire_cart),

        (verify_hire_cart, {
            "invalid": hire_invalid_terminal,
            "valid":   pay_base_into_escrow,
        }),

        (pay_base_into_escrow, grant_capability),

        (grant_capability, {
            "grant_failed": verify_failed,
            "granted":      dispatch_to_specialist,
        }),

        (dispatch_to_specialist, {
            "dispatch_failed": revoke_capability,
            "dispatched":      collect_result,
        }),

        (collect_result, revoke_capability),

        (revoke_capability, verify_work),

        (verify_work, {
            "hard_fail":   verify_failed,
            "checks_pass": approve_payout,
        }),

        (approve_payout, {
            "rejected": verify_failed,
            "approved": pay_completion,
        }),

        (pay_completion, settle_escrow),

        (settle_escrow, receipt_terminal),

        (verify_failed, refunded_terminal),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(is_resumable=True),
)
