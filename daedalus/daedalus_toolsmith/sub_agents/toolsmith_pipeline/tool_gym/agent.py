from google.adk.agents import LoopAgent

from .sub_agents.tool_code_fixer.agent import tool_code_fixer_agent
from .sub_agents.tool_test_runner.agent import tool_test_runner_agent

tool_gym_agent = LoopAgent(
    name="ToolGymAgent",
    sub_agents=[
        tool_test_runner_agent,
        tool_code_fixer_agent,
    ],
    max_iterations=3,
)
