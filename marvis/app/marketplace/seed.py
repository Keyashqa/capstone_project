"""Seed the in-process SkillRegistry with the Phase 1 catalog.

Two skills (M2):
  skill-doc-reader  → DocReader  (get_doc_content only — read-only)
  skill-doc-writer  → DocWriter  (create_doc only   — write)

The read-vs-write split IS the least-privilege scoping demonstration.
"""
from __future__ import annotations

from app.keys import skill_public_key_dict
from app.marketplace.skill_card import CapabilityRef, SkillCard, SkillPricing
from app.marketplace.skill_registry import get_registry


def seed_catalog() -> None:
    registry = get_registry()
    if registry.has("skill-doc-writer") and registry.has("skill-doc-reader"):
        return  # already seeded

    # ── DocWriter — creates a Google Doc (create_doc only) ────────────────────
    if not registry.has("skill-doc-writer"):
        registry.register(SkillCard(
            skill_id="skill-doc-writer",
            agent_name="DocWriter",           # deterministic (A10) — drives ledger account
            display_name="Doc Writer",
            version="1.0.0",
            description=(
                "Writes content (tweets, scripts, articles) and saves the result "
                "as a new Google Doc. Suitable for content creation and doc writing tasks."
            ),
            specialties=["doc-writing", "content-writing", "twitter", "social-media"],
            instruction=(
                "You are DocWriter, a specialist content creator.\n\n"
                "Your job:\n"
                "1. Write the requested content (e.g. a tweet, blog post, script).\n"
                "2. Keep tweets under 280 characters — this is a hard requirement.\n"
                "3. Be casual and engaging.\n"
                "4. Return ONLY the content text — no preamble, no explanation.\n\n"
                "For Twitter content: write exactly one tweet, no hashtag spam."
            ),
            model="ollama/gemma2:2b",
            required_capabilities=[
                CapabilityRef(
                    mcp_server="gdocs",
                    tool_name="create_doc",
                    why="Save the written content as a Google Doc",
                )
            ],
            pricing=SkillPricing(
                base_fee_cents=50,        # $0.50 base (non-refundable)
                completion_fee_cents=100, # $1.00 on delivery
            ),
            public_key=skill_public_key_dict("skill-doc-writer"),
        ))

    # ── DocReader — reads an existing Google Doc (get_doc_content only) ───────
    if not registry.has("skill-doc-reader"):
        registry.register(SkillCard(
            skill_id="skill-doc-reader",
            agent_name="DocReader",
            display_name="Doc Reader",
            version="1.0.0",
            description=(
                "Reads and summarises the content of an existing Google Doc. "
                "Suitable for research, extraction, and doc-reading tasks."
            ),
            specialties=["doc-reading", "research", "summarisation"],
            instruction=(
                "You are DocReader, a specialist document analyst.\n\n"
                "Your job:\n"
                "1. Read the provided document content.\n"
                "2. Return a clear, concise summary or extract as requested.\n"
                "3. Return ONLY the analysis — no preamble.\n\n"
                "You have read-only access. You cannot create or modify documents."
            ),
            model="ollama/gemma2:2b",
            required_capabilities=[
                CapabilityRef(
                    mcp_server="gdocs",
                    tool_name="get_doc_content",
                    why="Read the source document",
                )
            ],
            pricing=SkillPricing(
                base_fee_cents=25,       # $0.25 base
                completion_fee_cents=50, # $0.50 on delivery
            ),
            public_key=skill_public_key_dict("skill-doc-reader"),
        ))
