from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.tools import exit_loop

from daedalus_toolsmith.config import retry_options, MODEL
from .prompt import TOOL_SPEC_REVIEWER_PROMPT

tool_spec_reviewer_agent = LlmAgent(
    model=Gemini(model=MODEL, retry_options=retry_options),
    name="ToolSpecReviewerAgent",
    description=(
        "Reviews the current tool design, either approves it by calling exit_loop "
        "or provides a critique in 'tool_design_critique'."
    ),
    instruction=TOOL_SPEC_REVIEWER_PROMPT,
    output_key="tool_design_critique",
    tools=[exit_loop]
)
