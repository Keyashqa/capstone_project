from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.tools import AgentTool

from .config import MODEL, retry_options, check_env_variables, configure_logging
from .prompt import ORCHESTRATOR_PROMPT
from .sub_agents.agentsmith_pipeline import agentsmith_pipeline
from .sub_agents.toolsmith_pipeline import toolsmith_pipeline
from .tools.flight_search.tools import register_flight_tools
from .tools.registry.tools import list_registered_tools, call_registered_tool, run_agent_pipeline, \
    list_agent_pipelines, get_agent_pipeline_design
from .tools.weather_lookup.tools import register_weather_tools

# Configure Gemini API key and logging
check_env_variables()
configure_logging()

# Register sandbox domain tools at startup
register_flight_tools()
register_weather_tools()


class DaedalusAgent(LlmAgent):
    pass


# Define the Orchestrator Agent
root_agent = DaedalusAgent(
    model=Gemini(model=MODEL, retry_options=retry_options),
    name="OrchestratorAgent",
    description="""
        High-level orchestrator that first tries to solve the user's request using 
        already registered tools. If no suitable tool exists, it can invoke:
        - ToolsmithPipeline: to design, implement, and register a new tool.
        - AgentSmithPipeline: to design and register a new multi-agent pipeline
          (e.g., a LoopAgent with 3 sub-agents that collaboratively write blogs).

        After new capabilities are created, it calls either the tool directly or
        uses run_agent_pipeline(pipeline_name, user_request) to execute the 
        appropriate agent pipeline, then returns a final answer to the user.
    """,
    instruction=ORCHESTRATOR_PROMPT,
    tools=[
        AgentTool(agent=toolsmith_pipeline),
        AgentTool(agent=agentsmith_pipeline),
        list_registered_tools,
        list_agent_pipelines,
        call_registered_tool,
        run_agent_pipeline,
        get_agent_pipeline_design
    ]
)

# app = App(name=APP_NAME, root_agent=root_agent)
