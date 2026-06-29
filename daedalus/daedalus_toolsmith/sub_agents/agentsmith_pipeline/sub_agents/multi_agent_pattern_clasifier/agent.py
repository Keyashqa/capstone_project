from google.adk.agents import LlmAgent
from google.adk.models import Gemini

from daedalus_toolsmith.config import MODEL, retry_options
from .prompt import MULTI_AGENT_PATTERN_CLASSIFIER_PROMPT

multi_agent_pattern_classifier = LlmAgent(
    model=Gemini(model=MODEL, retry_options=retry_options),
    name="MultiAgentPatternClassifier",
    description="Classifies the best multi-agent workflow pattern for the given request.",
    instruction=MULTI_AGENT_PATTERN_CLASSIFIER_PROMPT,
    output_key="agent_pipeline_pattern",
)
