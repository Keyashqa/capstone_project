from google.adk.agents import LlmAgent
from google.adk.models import Gemini

from daedalus_toolsmith.config import retry_options, MODEL
from .prompt import INITIAL_CODE_GENERATOR_PROMPT

initial_code_generator_agent = LlmAgent(
    model=Gemini(model=MODEL, retry_options=retry_options),
    name="InitialCodeGeneratorAgent",
    description="Generates the first implementation of the tool from the tool design spec.",
    instruction=INITIAL_CODE_GENERATOR_PROMPT,
    output_key="tool_code",
)
