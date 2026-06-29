from google.adk.agents import LlmAgent
from google.adk.models import Gemini

from daedalus_toolsmith.config import MODEL, retry_options
from .prompt import TOOL_CODE_FIXER_PROMPT

tool_code_fixer_agent = LlmAgent(
    model=Gemini(model=MODEL, retry_options=retry_options),
    name="ToolCodeFixerAgent",
    description="Rewrites tool_code based on failing ToolGym tests. If tests are passing, returns the tool_code unchanged.",
    instruction=TOOL_CODE_FIXER_PROMPT,
    output_key="tool_code",
)
