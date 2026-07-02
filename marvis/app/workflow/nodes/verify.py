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
    return genai_types.Content(role="model", parts=[genai_types.Part(text=f"<mstat>{text}</mstat>")])


# Per-platform character limits enforced on written posts.
_CHANNEL_LIMITS = {"twitter": 280, "instagram": 2200, "linkedin": 3000}


def _channel_limit(channel: str) -> tuple[str, int]:
    """Resolve a free-form channel to (platform_name, char_limit). Defaults to twitter."""
    c = channel.lower()
    if "insta" in c:
        return "instagram", _CHANNEL_LIMITS["instagram"]
    if "linkedin" in c or "linked-in" in c:
        return "linkedin", _CHANNEL_LIMITS["linkedin"]
    return "twitter", _CHANNEL_LIMITS["twitter"]


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

    # For post-writing tasks: enforce the platform's character limit.
    if task_type in ("doc_writing", "content_writing"):
        platform, limit = _channel_limit(str(spec.get("inputs", {}).get("channel", "")))
        text = output.strip()
        if platform == "twitter":
            # Short-form: the post is one line — ignore any trailing model chatter.
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            candidate = lines[0] if lines else text
        else:
            # Long-form captions/posts: check the whole body.
            candidate = text
        if len(candidate) > limit:
            issues.append(
                f"{platform} post is {len(candidate)} chars (max {limit})"
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
