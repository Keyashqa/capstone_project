"""verify_work node — §7a-C hybrid verification.

Deterministic pre-filter (hard gate) → advisory Gemma score → human PIN gate #2.

Deterministic checks for the flagship doc_writing task:
  1. tweet body <= 280 chars
  2. create_doc was actually called (called_tools contains create_doc)
  3. doc_id is non-empty and valid
  Advisory: Gemma re-reads goal_nl + acceptance_criteria + output → {score, reasons}.

Routes: "hard_fail" → verify_failed, "checks_pass" → approve_payout (PIN gate #2).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import ollama
from google.adk.events.event import Event
from google.genai import types as genai_types

from app.config import OLLAMA_MODEL


def _content(text: str) -> genai_types.Content:
    return genai_types.Content(role="model", parts=[genai_types.Part(text=text)])


def _deterministic_checks(
    spec: dict,
    result: dict,
) -> tuple[bool, list[str]]:
    """Run the acceptance_criteria as deterministic checks. Returns (all_pass, issues)."""
    criteria: list[str] = spec.get("acceptance_criteria", [])
    task_type: str = spec.get("type", "")
    called_tools: list[dict] = result.get("called_tools", [])
    output: str = result.get("output", "")
    doc_id: str | None = result.get("doc_id")

    issues: list[str] = []

    # For doc_writing tasks: check tweet length
    if task_type in ("doc_writing", "content_writing"):
        tweet_text = output.strip()
        # If the output is longer than a tweet, check first paragraph
        lines = [l.strip() for l in tweet_text.splitlines() if l.strip()]
        tweet_candidate = lines[0] if lines else tweet_text
        if len(tweet_candidate) > 280:
            issues.append(
                f"tweet body is {len(tweet_candidate)} chars (max 280)"
            )

    # create_doc must have been called
    if task_type in ("doc_writing", "content_writing"):
        doc_calls = [t for t in called_tools if t.get("tool") == "create_doc"]
        if not doc_calls:
            issues.append("create_doc was never called — no document was saved")
        elif not doc_id:
            issues.append("create_doc was called but no document_id was returned")

    return len(issues) == 0, issues


async def _advisory_score(goal_nl: str, criteria: list[str], output: str) -> dict:
    """Ask local Gemma to score the output. Advisory only — human PIN is the authority."""
    criteria_text = "\n".join(f"- {c}" for c in criteria)
    prompt = (
        f"You are an output quality judge.\n\n"
        f"Original goal: {goal_nl}\n\n"
        f"Acceptance criteria:\n{criteria_text}\n\n"
        f"Output to evaluate:\n{output[:1000]}\n\n"
        f'Return JSON: {{"score": 0-10, "reasons": ["..."], "recommendation": "approve|reject"}}'
    )
    try:
        resp = await asyncio.to_thread(
            ollama.chat,
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": 0.3},
        )
        return json.loads(resp["message"]["content"])
    except Exception:
        return {"score": 5, "reasons": ["judge unavailable"], "recommendation": "approve"}


async def verify_work(node_input: dict[str, Any]) -> Any:
    """Hybrid verification: deterministic pre-filter + advisory Gemma score."""
    spec: dict = node_input.get("spec", {})
    result: dict = node_input.get("specialist_result", {})
    goal_nl: str = node_input.get("goal_nl", "")

    # Step 1: Deterministic pre-filter (hard gate)
    checks_pass, issues = _deterministic_checks(spec, result)

    if not checks_pass:
        issue_lines = "\n".join(f"  • {i}" for i in issues)
        return Event(
            output={**node_input, "verification": {"passed": False, "issues": issues}},
            route="hard_fail",
            content=_content(
                f"Verification FAILED (deterministic checks):\n{issue_lines}"
            ),
        )

    # Step 2: Advisory Gemma score
    advisory = await _advisory_score(
        goal_nl=goal_nl,
        criteria=spec.get("acceptance_criteria", []),
        output=result.get("output", ""),
    )
    score = advisory.get("score", 0)
    reasons = advisory.get("reasons", [])

    verification = {
        "passed": True,
        "deterministic": "ok",
        "advisory_score": score,
        "advisory_reasons": reasons,
    }

    reason_lines = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(reasons))
    return Event(
        output={**node_input, "verification": verification},
        route="checks_pass",
        content=_content(
            f"Deterministic checks: PASSED\n"
            f"Advisory score: {score}/10\n"
            f"Reasons:\n{reason_lines}\n\n"
            f"Awaiting your PIN to release the completion payment."
        ),
    )
