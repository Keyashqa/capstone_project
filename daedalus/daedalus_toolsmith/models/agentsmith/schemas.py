from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class AgentNodeModel(BaseModel):
    """
    Pydantic schema for ONE node in the pipeline tree.
    Used only for validation of LLM output.
    """
    name: str = Field(..., description="Agent or group name, snake_case.")
    node_type: Literal["llm", "parallel_group"]
    description: str

    # Only for node_type == "llm"
    instruction: Optional[str] = None
    allowed_tool_names: List[str] = Field(default_factory=list)

    # Only for node_type == "parallel_group"
    sub_agents: List["AgentNodeModel"] = Field(default_factory=list)

    @field_validator("instruction")
    @classmethod
    def instruction_required_for_llm(cls, v: Optional[str], info):
        if info.data.get("node_type") == "llm" and not v:
            raise ValueError("instruction is required for node_type='llm'")
        return v

    @field_validator("sub_agents")
    @classmethod
    def sub_agents_only_for_parallel_group(cls, v: List["AgentNodeModel"], info):
        node_type = info.data.get("node_type")
        if node_type == "parallel_group" and not v:
            raise ValueError("parallel_group nodes must define at least one child in sub_agents")
        if node_type == "llm" and v:
            raise ValueError("llm nodes must not define sub_agents")
        return v


class AgentPipelineModel(BaseModel):
    """
    Pydantic schema for the WHOLE pipeline.
    """
    pipeline_name: str
    pipeline_type: Literal["sequential", "loop"]
    max_iterations: Optional[int] = None
    sub_agents: List[AgentNodeModel]

    @field_validator("max_iterations")
    @classmethod
    def max_iterations_required_for_loop(cls, v: Optional[int], info):
        if info.data.get("pipeline_type") == "loop" and v is None:
            raise ValueError("max_iterations is required for pipeline_type='loop'")
        return v

    @field_validator("sub_agents")
    @classmethod
    def at_least_one_sub_agent(cls, v: List[AgentNodeModel]):
        if not v:
            raise ValueError("sub_agents must contain at least one node")
        return v
