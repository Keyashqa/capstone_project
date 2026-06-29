from google.adk.agents import LlmAgent
from google.adk.models import Gemini

from daedalus_toolsmith.config import retry_options, MODEL
from .prompt import ITERATIVE_REFINEMENT_PLANNER_PROMPT

iterative_refinement_pipeline_planner_agent = LlmAgent(
    model=Gemini(model=MODEL, retry_options=retry_options),
    name="IterativeRefinementPipelinePlanner",
    description="Designs loop-based iterative refinement pipelines with a loop controller and final writer.",
    instruction=ITERATIVE_REFINEMENT_PLANNER_PROMPT,
    output_key="agent_pipeline_design",
)
