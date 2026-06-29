from google.adk.agents import LlmAgent
from google.adk.models import Gemini

from daedalus_toolsmith.config import MODEL, retry_options
from .prompt import SEQUENTIAL_PIPELINE_PLANNER_PROMPT

sequential_pipeline_planner_agent = LlmAgent(
    model=Gemini(model=MODEL, retry_options=retry_options),
    name="SequentialPipelinePlanner",
    description="Designs sequential multi-agent pipelines with a final writer agent.",
    instruction=SEQUENTIAL_PIPELINE_PLANNER_PROMPT,
    output_key="agent_pipeline_design",
)
