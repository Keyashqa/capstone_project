from google.adk.agents import LoopAgent

from .sub_agents.tool_spec_planner.agent import tool_spec_planner_agent
from .sub_agents.tool_spec_reviewer import tool_spec_reviewer_agent

tool_planner_agent = LoopAgent(
    name="ToolPlannerAgent",
    sub_agents=[tool_spec_planner_agent, tool_spec_reviewer_agent],
    max_iterations=2
)
