"""Single specialist runtime — the one ADK agent shell that wears a skill.

On dispatch:
1. Load the chosen SkillCard (instruction + ONE required_capability).
2. Build a lent-tool wrapper that enforces the CapabilityGrant allowlist
   before forwarding to the real gdocs MCP tool.
3. Create an LlmAgent named skill.agent_name running on local Gemma via Ollama.
4. Run it against task.spec; return the result + attestation.

M5: runtime loads skill and runs on Gemma (no tools yet).
M6: adds the lent gdocs tool (in-proc allowlist enforcement).

Phase 2 (plan2.md §P2-4): ONE new branch — when the worn skill is skill-builder
(zero required_capabilities, no gdocs tool), the runtime instead asks Gemma to
fill in a new SkillCard's `instruction` + `description`. Every safety-critical
field (skill_id, agent_name, tool, specialties, pricing) is DERIVED by Marvis
from the detected {platform, role}, never model-generated — this is the
reliability decision that keeps a 2b model from fabricating a tool or identity.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import ollama

from app.capability.grant import CapabilityGrant, InMemoryGrantRegistry
from app.config import USER_GOOGLE_EMAIL
from app.marketplace.skill_card import CapabilityRef, SkillCard, SkillPricing


class SpecialistResult:
    def __init__(
        self,
        agent_name: str,
        skill_id: str,
        output: str,
        doc_id: str | None = None,
        called_tools: list[dict] | None = None,
        built_skill_card: SkillCard | None = None,
    ) -> None:
        self.agent_name = agent_name
        self.skill_id = skill_id
        self.output = output
        self.doc_id = doc_id
        self.called_tools: list[dict] = called_tools or []
        self.built_skill_card = built_skill_card  # only set by the builder branch


# ── Phase 2: builder branch — derives every safety-critical field itself ──────

_ROLE_TOOL: dict[str, tuple[str, str]] = {
    "writer": ("create_doc", "Save the written {platform} post as a Google Doc"),
    "reviewer": ("get_doc_content", "Read the {platform} post from Google Docs in order to review it"),
}
_PLATFORM_WORD: dict[str, str] = {"twitter": "Twitter", "instagram": "Insta", "linkedin": "Linkedin"}
_PLATFORM_LIMIT: dict[str, int] = {"twitter": 280, "instagram": 2200, "linkedin": 3000}
_WRITER_PRICING = SkillPricing(base_fee_cents=50, completion_fee_cents=100)
_REVIEWER_PRICING = SkillPricing(base_fee_cents=25, completion_fee_cents=50)


def _assemble_skill_card(platform: str, role: str, instruction: str, description: str) -> SkillCard:
    """Build the full SkillCard from Marvis-derived fields + the model's instruction/description.

    The model NEVER chooses skill_id, agent_name, the tool, specialties, or
    pricing — those come only from the closed {platform, role} gap Marvis
    already detected deterministically in select_specialist (plan2.md §P2-4).
    """
    tool_name, why_template = _ROLE_TOOL[role]
    platform_word = _PLATFORM_WORD.get(platform, platform.capitalize())
    role_suffix = "Specialist" if role == "writer" else "Reviewer"
    is_writer = role == "writer"

    specialties = (
        [platform, f"{platform}-post", "post-writing", "content-writing", "doc-writing", "social-media"]
        if is_writer
        else [platform, f"{platform}-post", "post-review", "post-reviewing", "doc-reading", "review"]
    )

    return SkillCard(
        skill_id=f"skill-{platform}-{role}",
        agent_name=f"{platform_word}Post{role_suffix}",
        display_name=f"{platform.capitalize()} Post {role_suffix}",
        version="1.0.0",
        description=description.strip(),
        specialties=specialties,
        instruction=instruction.strip(),
        model="ollama/gemma2:2b",
        required_capabilities=[
            CapabilityRef(mcp_server="gdocs", tool_name=tool_name, why=why_template.format(platform=platform))
        ],
        pricing=_WRITER_PRICING if is_writer else _REVIEWER_PRICING,
        public_key={},  # placeholder — persist_skill mints the real, Marvis-owned key
    )


async def _generate_json_with_ollama(prompt: str, model_str: str) -> str:
    ollama_model = model_str.replace("ollama/", "")
    resp = await asyncio.to_thread(
        ollama.chat,
        model=ollama_model,
        messages=[{"role": "user", "content": prompt}],
        format="json",
        options={"temperature": 0.2},
    )
    return resp["message"]["content"]


async def _run_builder(
    skill_card: SkillCard,
    task_spec: dict[str, Any],
    timeout_seconds: int,
) -> SpecialistResult:
    """Ask Gemma to write ONLY `instruction` + `description`; Marvis derives the rest.

    Hardened the same way as intake_task: format="json" + schema validation +
    ONE retry + graceful fail (empty output — validate_build then rejects it).
    """
    platform = task_spec.get("gap_platform", "") or task_spec.get("inputs", {}).get("channel", "")
    role = task_spec.get("gap_role", "writer")
    goal_nl = task_spec.get("goal_nl", "")
    limit = _PLATFORM_LIMIT.get(platform, 280)

    prompt = (
        f"{skill_card.instruction}\n\n"
        f"Gap to fill: platform={platform}, role={role}, character limit={limit}\n"
        f"Original user goal: {goal_nl}\n"
    )

    built: dict | None = None
    for attempt in range(2):
        try:
            raw = await asyncio.wait_for(
                _generate_json_with_ollama(prompt, skill_card.model),
                timeout=timeout_seconds,
            )
            candidate = json.loads(raw)
            if not isinstance(candidate.get("instruction"), str) or not candidate["instruction"].strip():
                raise ValueError("missing/empty instruction")
            if not isinstance(candidate.get("description"), str) or not candidate["description"].strip():
                raise ValueError("missing/empty description")
            built = candidate
            break
        except Exception:
            if attempt == 0:
                continue

    if built is None or not platform:
        # Graceful fail — empty output makes validate_build reject deterministically.
        return SpecialistResult(agent_name=skill_card.agent_name, skill_id=skill_card.skill_id, output="")

    new_card = _assemble_skill_card(platform, role, built["instruction"], built["description"])
    return SpecialistResult(
        agent_name=skill_card.agent_name,
        skill_id=skill_card.skill_id,
        output=new_card.model_dump_json(),
        built_skill_card=new_card,
    )


async def run_specialist(
    skill_card: SkillCard,
    task_spec: dict[str, Any],
    grant: CapabilityGrant | None,
    grant_registry: InMemoryGrantRegistry,
    timeout_seconds: int = 20,
) -> SpecialistResult:
    """Run the single specialist runtime wearing the given skill.

    M5: Gemma generates the text output (no tool calls yet).
    M6: Also calls the lent gdocs MCP tool via the grant allowlist.
    Phase 2: the builder (zero caps) branches into _run_builder — no tool, no grant.
    """
    if skill_card.skill_id == "skill-builder":
        return await _run_builder(skill_card, task_spec, timeout_seconds)

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
            title=inputs.get("doc_title", "Marvis social post"),
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
    """Check the grant, then create the doc with its content in a single call.

    Passing content up-front (create_doc's optional `content` arg) inserts it once
    at the document start. This avoids the Google Docs API error
    "insertion index cannot be within a grapheme cluster" that
    manage_doc_tab/populate_from_markdown raises on emoji-rich posts.
    """
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

    email_arg = {"user_google_email": USER_GOOGLE_EMAIL} if USER_GOOGLE_EMAIL else {}
    create_args = {"title": title, **email_arg}
    if content:
        create_args["content"] = content

    async with GDocsSession() as session:
        create_result = await session.call_tool("create_doc", create_args)
        create_text = "".join(getattr(b, "text", "") for b in create_result.content)

    doc_id = _extract_doc_id(create_text)
    if not doc_id:
        print(f"[create_doc] WARNING: could not extract doc_id from response. Full response:\n{create_text!r}")
    return doc_id or "created"


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
