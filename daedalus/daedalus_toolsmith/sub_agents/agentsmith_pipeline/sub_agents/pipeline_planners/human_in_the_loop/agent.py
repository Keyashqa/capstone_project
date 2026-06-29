from google.adk.agents import LlmAgent
from google.adk.models import Gemini

from daedalus_toolsmith.config import MODEL, retry_options
from .prompt import HUMAN_IN_LOOP_PLANNER_PROMPT

human_in_loop_pipeline_planner_agent = LlmAgent(
    model=Gemini(model=MODEL, retry_options=retry_options),
    name="HumanInLoopPipelinePlanner",
    description="Designs human-in-the-loop pipelines with a human approval tool step.",
    instruction=HUMAN_IN_LOOP_PLANNER_PROMPT,
    output_key="agent_pipeline_design",
)
