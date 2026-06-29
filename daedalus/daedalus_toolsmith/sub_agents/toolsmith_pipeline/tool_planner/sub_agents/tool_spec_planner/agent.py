from google.adk import Agent
from google.adk.models import Gemini

from daedalus_toolsmith.config import retry_options, MODEL
from .prompt import TOOL_SPEC_PLANNER_PROMPT

tool_spec_planner_agent = Agent(
    model=Gemini(model=MODEL, retry_options=retry_options),
    name="ToolSpecPlannerAgent",
    instruction=TOOL_SPEC_PLANNER_PROMPT,
    output_key="tool_design"
)
