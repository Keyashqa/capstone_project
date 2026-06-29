from google.adk.agents import LlmAgent
from google.adk.models import Gemini

from daedalus_toolsmith.config import retry_options, MODEL
from .prompt import GENERATOR_CRITIC_PLANNER_PROMPT

generator_critic_pipeline_planner_agent = LlmAgent(
    model=Gemini(model=MODEL, retry_options=retry_options),
    name="GeneratorCriticPipelinePlanner",
    description="Designs generator–critic pipelines with a final answer.",
    instruction=GENERATOR_CRITIC_PLANNER_PROMPT,
    output_key="agent_pipeline_design",
)
