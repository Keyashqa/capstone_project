from google.adk.agents import SequentialAgent

from .initial_code_generator import initial_code_generator_agent
from .tool_gym.agent import tool_gym_agent
from .tool_planner import tool_planner_agent
from .tool_test_planner.agent import tool_test_planner_agent
from ..agent import ForgeAgent
from ...tools.registry.tools import register_dynamic_tool

toolsmith_builder_agent = SequentialAgent(
    name="ToolsmithPipeline",
    description="Designs, implements, tests, and registers new Python tools when needed.",
    sub_agents=[
        tool_planner_agent,
        initial_code_generator_agent,
        tool_test_planner_agent,
        tool_gym_agent
    ],
)

toolsmith_pipeline = ForgeAgent(
    name="ToolsmithPipeline",
    description="Designs, implements, tests, and registers new Python tools when needed.",
    builder_agent=toolsmith_builder_agent,
    registration_tool=register_dynamic_tool
)
