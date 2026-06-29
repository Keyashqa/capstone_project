from dataclasses import dataclass, field
from typing import Any, List, Dict, TypedDict


class InMemoryAgentRegistry:
    """
    A simple in-memory registry for dynamically created agents and pipelines.
    Mirrors the behavior of InMemoryToolRegistry, but stores ADK agents
    (LlmAgent, LoopAgent, SequentialAgent, etc.) along with their design specs.

    Use cases:
    - Store dynamically created AgentSmith pipelines
    - Let Orchestrator inspect available pipelines
    - Retrieve pipelines by name to run them via run_agent_pipeline
    """

    def __init__(self):
        # name -> instantiated ADK agent (LlmAgent, LoopAgent, SequentialAgent)
        self._agents: Dict[str, Any] = {}

        # name -> design (AgentNodeDesign or AgentPipelineDesign)
        self._designs: Dict[str, Any] = {}

    # ---------------------------------------------------
    # Registration
    # ---------------------------------------------------

    def register(self, name: str, agent: Any, design: Any) -> None:
        """
        Register an agent under the given name with its design spec.
        """
        if name in self._agents:
            raise ValueError(f"Agent '{name}' already exists in registry.")

        self._agents[name] = agent
        self._designs[name] = design

    # ---------------------------------------------------
    # Query / Lookup
    # ---------------------------------------------------

    def has(self, name: str) -> bool:
        return name in self._agents

    def get(self, name: str) -> Any:
        if name not in self._agents:
            raise ValueError(f"Unknown agent: {name}")
        return self._agents[name]

    def get_design(self, name: str) -> Any:
        if name not in self._designs:
            raise ValueError(f"No design stored for agent: {name}")
        return self._designs[name]

    # ---------------------------------------------------
    # Listing
    # ---------------------------------------------------

    def list(self) -> List[Dict[str, Any]]:
        """
        Returns a list of simple dicts describing each registered agent/pipeline.
        Useful for the Orchestrator or debugging.
        """
        infos = []
        for name, agent in self._agents.items():
            # Infer type from class
            if agent.__class__.__name__.lower().startswith("loopagent"):
                agent_type = "loop"
            elif agent.__class__.__name__.lower().startswith("sequentialagent"):
                agent_type = "sequential"
            else:
                agent_type = agent.__class__.__name__

            # Count sub agents if pipeline
            sub_agents = getattr(agent, "sub_agents", [])
            num_sub_agents = len(sub_agents) if sub_agents else 0

            infos.append(
                {
                    "name": name,
                    "type": agent_type,
                    "num_sub_agents": num_sub_agents,
                }
            )
        return infos

    # ---------------------------------------------------
    # Raw views
    # ---------------------------------------------------

    def all_agents(self) -> Dict[str, Any]:
        """Return the raw registry for debugging / admin tools."""
        return dict(self._agents)

    def all_designs(self) -> Dict[str, Any]:
        """Return all stored designs (AgentNodeDesign / AgentPipelineDesign)."""
        return dict(self._designs)


class RegisteredAgentInfo(TypedDict):
    name: str
    description: str
    code: str


@dataclass
class AgentNodeDesign:
    """
    Node in an agent pipeline tree.

    node_type:
      - "llm":         a single LLM agent
      - "parallel_group": a ParallelAgent containing child LLM agents
    """
    name: str
    node_type: str  # "llm" or "parallel_group"
    description: str
    instruction: str | None = None
    allowed_tool_names: List[str] = field(default_factory=list)
    sub_agents: List["AgentNodeDesign"] = field(default_factory=list)


@dataclass
class AgentPipelineDesign:
    """
    Root description of an agent pipeline.
    """
    pipeline_name: str
    pipeline_type: str  # "sequential" or "loop"
    max_iterations: int | None
    sub_agents: List[AgentNodeDesign]


def agent_node_from_dict(d: Dict[str, Any]) -> AgentNodeDesign:
    node_type = d["node_type"]
    sub_agents_data = d.get("sub_agents", [])

    sub_nodes = [agent_node_from_dict(child) for child in sub_agents_data]

    return AgentNodeDesign(
        name=d["name"],
        node_type=node_type,
        description=d["description"],
        instruction=d.get("instruction"),
        allowed_tool_names=d.get("allowed_tool_names", []),
        sub_agents=sub_nodes,
    )


def agent_pipeline_from_dict(d: Dict[str, Any]) -> AgentPipelineDesign:
    sub_agents = [agent_node_from_dict(node) for node in d["sub_agents"]]

    return AgentPipelineDesign(
        pipeline_name=d["pipeline_name"],
        pipeline_type=d["pipeline_type"],
        max_iterations=d.get("max_iterations"),
        sub_agents=sub_agents,
    )
