from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.tools import exit_loop

from daedalus_toolsmith.config import MODEL, retry_options
from daedalus_toolsmith.tools.tool_gym.tools import run_tool_tests
from .prompt import TOOL_TEST_RUNNER_PROMPT

tool_test_runner_agent = LlmAgent(
    model=Gemini(model=MODEL, retry_options=retry_options),
    name="ToolTestRunnerAgent",
    description="Runs tests on the current tool_code and sets validation status. Exits if all tests pass.",
    instruction=TOOL_TEST_RUNNER_PROMPT,
    tools=[run_tool_tests, exit_loop],
    output_key="tool_test_runner_output",
)
