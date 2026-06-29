from google.adk.agents import LlmAgent
from google.adk.models import Gemini

from daedalus_toolsmith.config import retry_options, MODEL
from daedalus_toolsmith.tools.tool_gym.tools import load_golden_test_cases
from .prompt import TOOL_TEST_PLANNER_PROMPT

tool_test_planner_agent = LlmAgent(
    model=Gemini(model=MODEL, retry_options=retry_options),
    name="ToolTestPlannerAgent",
    description=(
        "Designs a small JSON test suite for the tool, to be used by ToolGym. "
        "Can query previously saved golden tests to avoid duplicates."
    ),
    instruction=TOOL_TEST_PLANNER_PROMPT,
    tools=[load_golden_test_cases],
    output_key="tool_test_suite",
)
