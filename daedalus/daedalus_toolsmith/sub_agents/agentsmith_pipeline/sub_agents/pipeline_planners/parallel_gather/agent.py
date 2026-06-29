from google.adk.agents import LlmAgent
from google.adk.models import Gemini

from daedalus_toolsmith.config import retry_options, MODEL
from .prompt import PARALLEL_GATHER_PLANNER_PROMPT

parallel_gather_pipeline_planner_agent = LlmAgent(
    model=Gemini(model=MODEL, retry_options=retry_options),
    name="ParallelGatherPipelinePlanner",
    description="Designs parallel fan-out/gather pipelines with a final synthesizer.",
    instruction=PARALLEL_GATHER_PLANNER_PROMPT,
    output_key="agent_pipeline_design",
)
