"""SkillCard — the marketplace catalog entry for a single skill.

Fuses F1's AgentNodeDesign (instruction + allowed_tool_names) with F2's UcpProfile shape.
One SkillCard per skill (NOT per agent). Phase 1 seed: skill-doc-reader, skill-doc-writer.
"""
from __future__ import annotations

from pydantic import BaseModel


class CapabilityRef(BaseModel):
    """A single MCP tool that this skill requires. Phase 1: exactly ONE per skill."""
    mcp_server: str    # "gdocs"
    tool_name: str     # "create_doc" | "get_doc_content"
    why: str           # human-readable justification


class SkillPricing(BaseModel):
    currency: str = "USD"
    base_fee_cents: int        # paid at hire (non-refundable)
    completion_fee_cents: int  # paid after verify-pass (refundable on fail)


class SkillIo(BaseModel):
    input_schema: dict = {}
    output_schema: dict = {}


class SkillCard(BaseModel):
    skill_id: str           # "skill-doc-writer"
    agent_name: str         # DETERMINISTIC — declared by the skill, never LLM-invented (A10)
                            # e.g. "DocWriter" / "DocReader"
    display_name: str
    version: str = "1.0.0"
    description: str        # used by select_specialist to match the task
    specialties: list[str]  # ["doc-writing","content-writing"]
    instruction: str        # scoped system prompt the runtime loads (F1 AgentNodeDesign.instruction)
    model: str = "ollama/gemma2:2b"
    required_capabilities: list[CapabilityRef]   # Phase 1: EXACTLY ONE entry
    pricing: SkillPricing
    public_key: dict        # JWK — per-skill signing identity (A9)
    io: SkillIo = SkillIo()
    reputation: float | None = None


class AgentCard(BaseModel):
    """Derived by Marvis at hire time from a chosen SkillCard. Never stored in the catalog."""
    agent_id: str           # == skill_id (1:1 in Phase 1)
    agent_name: str         # == SkillCard.agent_name (deterministic; drives ledger agent:{name})
    skill_id: str
    specialties: list[str]
    required_capabilities: list[CapabilityRef]
    pricing: SkillPricing
    endpoint: str           # A2A dispatch URL or in-proc handle id
    public_key: dict        # copied from SkillCard

    @classmethod
    def from_skill_card(cls, card: SkillCard, endpoint: str = "in-process") -> "AgentCard":
        return cls(
            agent_id=card.skill_id,
            agent_name=card.agent_name,
            skill_id=card.skill_id,
            specialties=card.specialties,
            required_capabilities=card.required_capabilities,
            pricing=card.pricing,
            endpoint=endpoint,
            public_key=card.public_key,
        )
