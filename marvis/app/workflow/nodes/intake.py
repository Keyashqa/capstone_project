"""intake_task — parse goal_nl into a structured Task spec using local Gemma.

M3: Calls ollama.chat with format="json" to parse the natural-language goal into
    {type, inputs, acceptance_criteria}. Validates parsed keys. Re-prompts once on
    parse/validation failure, then fails the node (schema-validated, never trusted blind).
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import ollama
from google.adk.events.event import Event
from google.adk.utils.content_utils import extract_text_from_content
from google.genai import types as genai_types

from app.config import OLLAMA_MODEL

_INTAKE_PROMPT = """You are a task parser for Marvis, a personal AI orchestrator.

Parse the user's request into a JSON object with EXACTLY these keys:
- "type": string — task type, e.g. "doc_writing", "doc_reading", "content_writing"
- "inputs": object — key/value pairs extracted from the request
  For doc_writing tasks include: topic, tone, channel, doc_title
- "acceptance_criteria": array of strings — objective, verifiable criteria

For the flagship task "Write a tweet about my Marvis launch and save it as a Twitter script in Google Docs":
{
  "type": "doc_writing",
  "inputs": {
    "topic": "Marvis launch",
    "tone": "casual",
    "channel": "twitter",
    "doc_title": "Twitter Scripts — Marvis launch"
  },
  "acceptance_criteria": [
    "tweet body is <= 280 chars",
    "create_doc returned a valid document_id (the doc was actually created)",
    "the saved doc body contains the tweet text"
  ]
}

Return ONLY valid JSON. No explanation.

Request: """

_REQUIRED_KEYS = {"type", "inputs", "acceptance_criteria"}


def _content(text: str) -> genai_types.Content:
    return genai_types.Content(role="model", parts=[genai_types.Part(text=f"<mstat>{text}</mstat>")])


async def _parse_with_ollama(goal_nl: str) -> dict:
    resp = await asyncio.to_thread(
        ollama.chat,
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": _INTAKE_PROMPT + goal_nl}],
        format="json",
        options={"temperature": 0.2},
    )
    return json.loads(resp["message"]["content"])


async def intake_task(node_input: Any) -> Any:
    """Parse goal_nl → Task spec. Validates schema; re-prompts once on failure.

    node_input may be a dict (programmatic/test) or a genai_types.Content
    (from ADK when the first user turn arrives via SSE).
    """
    if isinstance(node_input, genai_types.Content):
        # Initial user message from SSE — extract text
        goal_nl = extract_text_from_content(node_input).strip()
        node_input = {"goal_nl": goal_nl}
    elif isinstance(node_input, dict):
        goal_nl = node_input.get("goal_nl", "")
    else:
        goal_nl = str(node_input) if node_input else ""
        node_input = {"goal_nl": goal_nl}

    task_id: str = (node_input or {}).get("task_id", uuid.uuid4().hex[:12])

    parsed: dict | None = None
    error: str = ""

    for attempt in range(2):
        try:
            candidate = await _parse_with_ollama(goal_nl)
            missing = _REQUIRED_KEYS - set(candidate.keys())
            if missing:
                raise ValueError(f"Missing keys: {missing}")
            if not isinstance(candidate.get("acceptance_criteria"), list):
                raise ValueError("acceptance_criteria must be a list")
            parsed = candidate
            break
        except Exception as exc:
            error = str(exc)
            if attempt == 0:
                continue  # retry once

    if parsed is None:
        return Event(
            output={**node_input, "task_id": task_id},
            route="intake_failed",
            content=_content(f"Failed to parse task after 2 attempts: {error}"),
        )

    return Event(
        output={
            **node_input,
            "task_id": task_id,
            "goal_nl": goal_nl,
            "spec": parsed,
        },
        route="parsed",
        content=_content(
            f"Task parsed:\n  type: {parsed['type']}\n"
            f"  inputs: {json.dumps(parsed['inputs'], indent=2)}\n"
            f"  criteria: {len(parsed['acceptance_criteria'])} checks"
        ),
    )
