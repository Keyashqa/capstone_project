"""Single specialist runtime — the one ADK agent shell that wears a skill.

On dispatch:
1. Load the chosen SkillCard (instruction + ONE required_capability).
2. Build a lent-tool wrapper that enforces the CapabilityGrant allowlist
   before forwarding to the real gdocs MCP tool.
3. Create an LlmAgent named skill.agent_name running on local Gemma via Ollama.
4. Run it against task.spec; return the result + attestation.

M5: runtime loads skill and runs on Gemma (no tools yet).
M6: adds the lent gdocs tool (in-proc allowlist enforcement).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import ollama

from app.capability.grant import CapabilityGrant, InMemoryGrantRegistry
from app.config import USER_GOOGLE_EMAIL
from app.marketplace.skill_card import SkillCard


class SpecialistResult:
    def __init__(
        self,
        agent_name: str,
        skill_id: str,
        output: str,
        doc_id: str | None = None,
        called_tools: list[dict] | None = None,
    ) -> None:
        self.agent_name = agent_name
        self.skill_id = skill_id
        self.output = output
        self.doc_id = doc_id
        self.called_tools: list[dict] = called_tools or []


async def run_specialist(
    skill_card: SkillCard,
    task_spec: dict[str, Any],
    grant: CapabilityGrant,
    grant_registry: InMemoryGrantRegistry,
    timeout_seconds: int = 20,
) -> SpecialistResult:
    """Run the single specialist runtime wearing the given skill.

    M5: Gemma generates the text output (no tool calls yet).
    M6: Also calls the lent gdocs MCP tool via the grant allowlist.
    """
    inputs = task_spec.get("inputs", {})
    goal = task_spec.get("goal_nl", "")

    # Build prompt from skill instruction + task inputs
    prompt = _build_prompt(skill_card, inputs, goal)

    # M5: Generate text output with local Gemma
    text_output = await asyncio.wait_for(
        _generate_with_ollama(prompt, skill_card.model),
        timeout=timeout_seconds,
    )

    result = SpecialistResult(
        agent_name=skill_card.agent_name,
        skill_id=skill_card.skill_id,
        output=text_output,
    )

    # M6: Call the lent gdocs tool (in-proc allowlist check)
    required_cap = skill_card.required_capabilities[0]  # exactly ONE in Phase 1
    if required_cap.tool_name == "create_doc":
        doc_id = await _call_create_doc(
            grant=grant,
            grant_registry=grant_registry,
            title=inputs.get("doc_title", "Twitter Scripts — Marvis launch"),
            content=text_output,
        )
        result.doc_id = doc_id
        result.called_tools.append({"tool": "create_doc", "doc_id": doc_id})

    elif required_cap.tool_name == "get_doc_content":
        doc_id = inputs.get("doc_id", "")
        if doc_id:
            content = await _call_get_doc_content(
                grant=grant,
                grant_registry=grant_registry,
                document_id=doc_id,
            )
            result.output = content
            result.doc_id = doc_id
            result.called_tools.append({"tool": "get_doc_content", "doc_id": doc_id})

    return result


def _build_prompt(skill_card: SkillCard, inputs: dict, goal: str) -> str:
    lines = [skill_card.instruction, ""]
    if goal:
        lines.append(f"Task: {goal}")
    for k, v in inputs.items():
        if k not in ("doc_id", "doc_title"):
            lines.append(f"{k}: {v}")
    return "\n".join(lines)


async def _generate_with_ollama(prompt: str, model_str: str) -> str:
    ollama_model = model_str.replace("ollama/", "")
    resp = await asyncio.to_thread(
        ollama.chat,
        model=ollama_model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.7},
    )
    return resp["message"]["content"].strip()


async def _call_create_doc(
    grant: CapabilityGrant,
    grant_registry: InMemoryGrantRegistry,
    title: str,
    content: str,
) -> str | None:
    """Check grant, create doc, then populate a content tab — mirrors create_doc.py exactly."""
    allowed, reason = grant_registry.check_and_use(
        grant.grant_token, "create_doc", {"title": title, "content": content}
    )
    if not allowed:
        raise PermissionError(f"create_doc denied by grant: {reason}")

    from app.capability.gdocs_session import GDocsSession
    import re

    def _extract_doc_id(text: str) -> str | None:
        for pat in [
            r'["\'](?:documentId|document_id)["\']\s*[:=]\s*["\']([a-zA-Z0-9_-]+)["\']',
            r'\(ID:\s*([a-zA-Z0-9_-]+)\)',
            r'/document/d/([a-zA-Z0-9_-]+)',
        ]:
            m = re.search(pat, text)
            if m:
                return m.group(1)
        return None

    def _extract_tab_id(text: str) -> str | None:
        for pat in [
            r'["\']tab_id["\']\s*:\s*["\']([a-zA-Z0-9_.\-]+)["\']',
            r'Tab ID:\s*([a-zA-Z0-9_.\-]+)',
        ]:
            m = re.search(pat, text)
            if m:
                return m.group(1).rstrip(".")
        return None

    email_arg = {"user_google_email": USER_GOOGLE_EMAIL} if USER_GOOGLE_EMAIL else {}

    async with GDocsSession() as session:
        # Step 1: create the empty doc
        create_result = await session.call_tool("create_doc", {"title": title, **email_arg})
        create_text = "".join(getattr(b, "text", "") for b in create_result.content)
        doc_id = _extract_doc_id(create_text)

        if not doc_id:
            return "created"

        if not content:
            return doc_id

        # Step 2: create a "Content" tab
        tab_result = await session.call_tool(
            "manage_doc_tab",
            {"document_id": doc_id, "action": "create", "title": "Content", "index": 1, **email_arg},
        )
        tab_text = "".join(getattr(b, "text", "") for b in tab_result.content)
        tab_id = _extract_tab_id(tab_text)

        if tab_id:
            # Step 3: populate the tab with the specialist's output
            await session.call_tool(
                "manage_doc_tab",
                {
                    "document_id": doc_id,
                    "action": "populate_from_markdown",
                    "tab_id": tab_id,
                    "markdown_text": content,
                    **email_arg,
                },
            )

    return doc_id


async def _call_get_doc_content(
    grant: CapabilityGrant,
    grant_registry: InMemoryGrantRegistry,
    document_id: str,
) -> str:
    """Check grant allowlist then call get_doc_content via a fresh gdocs session."""
    allowed, reason = grant_registry.check_and_use(
        grant.grant_token, "get_doc_content", {"document_id": document_id}
    )
    if not allowed:
        raise PermissionError(f"get_doc_content denied by grant: {reason}")

    from app.capability.gdocs_session import GDocsSession

    gdoc_args: dict[str, Any] = {"document_id": document_id}
    if USER_GOOGLE_EMAIL:
        gdoc_args["user_google_email"] = USER_GOOGLE_EMAIL

    async with GDocsSession() as session:
        result = await session.call_tool("get_doc_content", gdoc_args)
    return "".join(getattr(b, "text", "") for b in result.content)
