import logging
from types import FunctionType
from typing import List, Dict, Any

from google.adk.agents import LoopAgent, LlmAgent, SequentialAgent, ParallelAgent, InvocationContext
from google.adk.models import Gemini
from google.adk.runners import InMemoryRunner
from google.adk.tools import exit_loop, ToolContext, google_search

from daedalus_toolsmith.config import MODEL, retry_options
from daedalus_toolsmith.models.agentsmith.models import AgentPipelineDesign, agent_pipeline_from_dict, \
    InMemoryAgentRegistry, AgentNodeDesign
from daedalus_toolsmith.models.toolsmith.models import RegisteredToolInfo, tool_design_from_dict, InMemoryToolRegistry
from daedalus_toolsmith.tools.common.tools import clean_json_string, clean_python_string

logger = logging.getLogger(__name__)
tool_registry = InMemoryToolRegistry()
agent_pipeline_registry = InMemoryAgentRegistry()


def list_registered_tools() -> List[Dict[str, Any]]:
    """
    Returns basic info for all registered tools.

    ADK/Gemini-friendly return type: list of dicts with 'name' and 'description'.
    """
    specs: List[RegisteredToolInfo] = [
        {
            "name": spec.name,
            "description": spec.description,
        }
        for spec in tool_registry.list_specs()
    ]
    logger.debug("Listing %d registered tools: %s", len(specs), [s["name"] for s in specs])

    # Returning as plain list[dict] so automatic function calling is happy
    return specs


def call_registered_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    Generic dispatcher that calls a registered tool by name.

    The LLM must construct 'arguments' to match the function signature.
    We deliberately keep this simple and trust the LLM here.
    """
    if not tool_registry.has_tool(tool_name):
        logger.error("Unknown tool requested: %s", tool_name)
        raise ValueError(f"Unknown tool: {tool_name}")

    meta = tool_registry.get(tool_name)
    try:
        result = meta.func(**arguments)
        logger.debug("Tool %s returned: %r", tool_name, result)
    except Exception as exc:
        logger.exception("Failed to call the tool %s", tool_name)
        return {
            "status": "error",
            "error_message": f"Failed to call the tool: {exc}",
        }

    return result


def register_dynamic_tool(ctx: InvocationContext) -> Dict[str, Any]:
    """
    Take a ToolDesign (as dict) and generated Python function code,
    exec the code, extract the function, and register it into the
    InMemoryToolRegistry.

    Returns a dict with status, tool_name, and description.
    """
    tool_design = clean_json_string(ctx.session.state.get("tool_design"))
    if not tool_design:
        return {
            "status": "error",
            "error_message": "No tool_design found in session state.",
        }

    tool_code = clean_python_string(ctx.session.state.get("tool_code"))
    if not tool_code:
        return {
            "status": "error",
            "error_message": "No tool_code found in session state.",
        }

    logger.debug("register_dynamic_tool called with design=%r", tool_design.get("tool_name"))

    try:
        design = tool_design_from_dict(tool_design)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to parse tool design")
        return {
            "status": "error",
            "error_message": f"Failed to parse tool design: {exc}",
        }

    namespace: Dict[str, Any] = {}
    try:
        exec(tool_code, namespace)  # noqa: S102
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error executing generated code for tool %s", design.name)
        return {
            "status": "error",
            "error_message": f"Error executing generated code: {exc}",
        }

    func = namespace.get(design.name)
    if not isinstance(func, FunctionType):
        candidates = [k for k, v in namespace.items() if isinstance(v, FunctionType)]
        return {
            "status": "error",
            "error_message": (
                f"Function '{design.name}' not found in generated code. "
                f"Available functions: {candidates}"
            ),
        }

    try:
        tool_registry.register(
            name=design.name,
            func=func,
            description=design.description,
            tags=["dynamic", "generated"],
        )
    except Exception as exc:
        logger.exception("Failed to register tool %s", design.name)
        return {
            "status": "error",
            "error_message": f"Failed to register tool '{design.name}': {exc}",
        }

    logger.info("Successfully registered dynamic tool: %s", design.name)

    return {
        "status": "success",
        "tool_name": design.name,
        "description": design.description,
    }


def build_agent_from_node(node: AgentNodeDesign, available_tools: Dict[str, Any]):
    if node.node_type == "parallel_group":
        # Build child LLM agents and wrap in ParallelAgent
        children = [build_agent_from_node(child, available_tools) for child in node.sub_agents]
        return ParallelAgent(
            name=node.name,
            sub_agents=children,
        )

    # Default: plain LLM agent
    tools = [
        available_tools[name]
        for name in node.allowed_tool_names
        if name in available_tools
    ]

    return LlmAgent(
        model=Gemini(model=MODEL, retry_options=retry_options),
        name=node.name,
        description=node.description,
        instruction=node.instruction or "",
        tools=tools,
    )


def register_agent_pipeline(ctx: InvocationContext) -> Dict[str, Any]:
    agent_pipeline_design = ctx.session.state.get("agent_pipeline_design")
    if not agent_pipeline_design:
        return {
            "status": "error",
            "error_message": "No agent_pipeline_design found in session state.",
        }
    agent_pipeline_design = clean_json_string(agent_pipeline_design)
    logger.debug("agent_pipeline_design: %r", agent_pipeline_design)

    try:
        design: AgentPipelineDesign = agent_pipeline_from_dict(agent_pipeline_design)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "error_message": f"Failed to parse agent pipeline design: {exc}",
        }

    available_tools: Dict[str, Any] = {
        "list_registered_tools": list_registered_tools,
        "call_registered_tool": call_registered_tool,
        "google_search": google_search,
        "exit_loop": exit_loop
    }

    root_children = [build_agent_from_node(node, available_tools) for node in design.sub_agents]

    if design.pipeline_type == "loop":
        max_iter = design.max_iterations or 3
        pipeline_agent = LoopAgent(
            name=design.pipeline_name,
            sub_agents=root_children,
            max_iterations=max_iter,
        )
    else:
        pipeline_agent = SequentialAgent(
            name=design.pipeline_name,
            sub_agents=root_children,
        )

    # Register in InMemoryAgentRegistry
    try:
        agent_pipeline_registry.register(
            name=design.pipeline_name,
            agent=pipeline_agent,
            design=design,
        )
    except Exception as exc:
        logger.exception("Failed to register agent pipeline %s", design.pipeline_name)
        return {
            "status": "error",
            "error_message": f"Failed to register agent pipeline '{design.pipeline_name}': {exc}",
        }

    return {
        "status": "success",
        "pipeline_name": design.pipeline_name,
        "pipeline_type": design.pipeline_type,
        "num_sub_agents": len(design.sub_agents),
    }


async def run_agent_pipeline(pipeline_name: str, user_request: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Run a dynamically-registered agent pipeline (LoopAgent or SequentialAgent)
    against a user_request string, and return the final response text.

    Skips summarization as normally the agent pipeline should provide the final answer itself.
    """
    if not agent_pipeline_registry.has(pipeline_name):
        return {
            "status": "error",
            "error_message": f"Unknown agent pipeline: {pipeline_name}",
        }

    pipeline_agent = agent_pipeline_registry.get(pipeline_name)

    # Create an isolated runner for this invocation.
    runner = InMemoryRunner(
        agent=pipeline_agent,
        app_name=tool_context.session.app_name
    )

    # Skips summarization as normally the agent pipeline should provide the final answer itself.
    tool_context.actions.skip_summarization = False

    final_text: str | None = None

    events = await runner.run_debug(
        user_messages=user_request,
        session_id=tool_context.session.id
    )

    for ev in events:
        if ev.is_final_response() and ev.content and ev.content.parts:
            final_text = ev.content.parts[0].text

    if final_text is None:
        return {
            "status": "error",
            "error_message": f"Pipeline '{pipeline_name}' produced no final response.",
        }

    return {
        "status": "success",
        "pipeline_name": pipeline_name,
        "response": final_text,
    }


def list_agent_pipelines() -> List[Dict[str, Any]]:
    return agent_pipeline_registry.list()


def get_agent_pipeline_design(pipeline_name: str) -> Dict[str, Any]:
    """
    Retrieve the design spec of a registered agent pipeline by name.
    """
    if not agent_pipeline_registry.has(pipeline_name):
        raise ValueError(f"Unknown agent pipeline: {pipeline_name}")

    design = agent_pipeline_registry.get_design(pipeline_name)
    return design
