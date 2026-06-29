import logging
from typing import AsyncGenerator, ClassVar, Dict

from google.adk.agents import BaseAgent, InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part
from typing_extensions import override

from .sub_agents.multi_agent_pattern_clasifier import multi_agent_pattern_classifier
from .sub_agents.pipeline_planners.generator_critic import generator_critic_pipeline_planner_agent
from .sub_agents.pipeline_planners.iterative_refiner import iterative_refinement_pipeline_planner_agent
from .sub_agents.pipeline_planners.parallel_gather import parallel_gather_pipeline_planner_agent
from .sub_agents.pipeline_planners.sequential.agent import (
    sequential_pipeline_planner_agent,
)
from ..agent import ForgeAgent
from ...tools.common.tools import clean_json_string
from ...tools.registry.tools import register_agent_pipeline

logger = logging.getLogger(__name__)


class AgentSmithBuilderAgent(BaseAgent):
    """
    Runs pattern classifier -> uses correct planner -> produces agent_pipeline_design.
    It does NOT register pipelines. That is ForgeAgent's job.
    """

    # Mark as ClassVar so Pydantic does NOT treat them as model fields.
    classifier_agent: ClassVar[BaseAgent] = multi_agent_pattern_classifier
    planners: ClassVar[Dict[str, BaseAgent]] = {
        "sequential": sequential_pipeline_planner_agent,
        "iterative_refinement": iterative_refinement_pipeline_planner_agent,
        "parallel_gather": parallel_gather_pipeline_planner_agent,
        "generator_critic": generator_critic_pipeline_planner_agent,
        # Not implemented properly yet:
        # "human_in_loop": human_in_loop_pipeline_planner_agent,
    }

    # Allow arbitrary nested agent types in the Pydantic model
    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, name: str, description: str) -> None:
        # Expose sub_agents to the BaseAgent for introspection / observability
        sub_agents = [self.classifier_agent] + list(self.planners.values())

        super().__init__(
            name=name,
            description=description,
            sub_agents=sub_agents,
        )

    @override
    async def _run_async_impl(self, ctx: InvocationContext, ) -> AsyncGenerator[Event, None]:
        logger.info(f"[{self.name}] Builder started.")

        # Run classifier to pick pipeline pattern
        async for event in self.classifier_agent.run_async(ctx):
            yield event

        pattern = ctx.session.state.get("agent_pipeline_pattern")
        pattern = clean_json_string(pattern)
        pattern = pattern["agent_pipeline_pattern"]
        logger.info(f"[{self.name}] Using pattern: {pattern}")

        if not pattern:
            msg = "Pattern classifier failed to set agent_pipeline_pattern."
            logger.error(msg)
            yield Event(
                author=self.name,
                actions=EventActions(),
                content=Content(role="system", parts=[Part(text=msg)]),
            )
            return

        # Pick correct planner based on pattern
        planner = self.planners.get(pattern)

        if planner is None:
            msg = (
                f"No planner found for pattern '{pattern}'. "
                f"Available: {list(self.planners.keys())}"
            )
            logger.error(msg)

            yield Event(
                author=self.name,
                actions=EventActions(),
                content=Content(role="system", parts=[Part(text=msg)]),
            )
            return

        logger.info(f"[{self.name}] Using planner: {planner.name}")

        # Run chosen planner -> writes agent_pipeline_design into ctx.state
        async for event in planner.run_async(ctx):
            yield event

        # Done -> ForgeAgent will handle registration
        logger.info(f"[{self.name}] Builder completed.")


agentsmith_pipeline = ForgeAgent(
    name="AgentSmithPipeline",
    description="Designs and registers new multi-agent pipelines (sequential, loop, or parallel).",
    builder_agent=AgentSmithBuilderAgent(
        name="AgentSmithBuilderAgent",
        description=(
            """
            Classifies the requested pipeline pattern and uses the appropriate 
            planner to design the multi-agent pipeline.
            """
        ),
    ),
    registration_tool=register_agent_pipeline,
)
