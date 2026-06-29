from dataclasses import dataclass, field
from typing import Any, List, Dict, TypedDict, Callable
from uuid import uuid4


@dataclass
class ToolSpec:
    id: str
    name: str
    description: str


@dataclass
class ToolMetadata:
    spec: ToolSpec
    func: Callable[..., Any]
    version: int = 1
    tags: List[str] = field(default_factory=list)


class InMemoryToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolMetadata] = {}

    def register(
            self,
            name: str,
            func: Callable[..., Any],
            description: str,
            tags: List[str] | None = None,
    ) -> ToolSpec:
        prev = self._tools.get(name)
        new_version = (prev.version + 1) if prev else 1

        tool_id = str(uuid4())
        spec = ToolSpec(
            id=tool_id,
            name=name,
            description=description,
        )
        meta = ToolMetadata(
            spec=spec,
            func=func,
            version=new_version,
            tags=tags or [],
        )
        self._tools[name] = meta
        return spec

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> ToolMetadata:
        return self._tools[name]

    def list_specs(self) -> List[ToolSpec]:
        return [meta.spec for meta in self._tools.values()]

    def list_names(self) -> List[str]:
        return list(self._tools.keys())


class RegisteredToolInfo(TypedDict):
    name: str
    description: str


@dataclass
class ToolParamSpec:
    name: str
    type: str
    description: str


@dataclass
class ToolDesign:
    """
    High-level spec for a Python function tool, as produced by ToolPlannerAgent.
    """
    name: str
    description: str
    params: List[ToolParamSpec]
    return_type: str
    return_description: str
    success_keys: List[str]
    error_behavior: str


def tool_design_from_dict(d: Dict[str, Any]) -> ToolDesign:
    return ToolDesign(
        name=d["tool_name"],
        description=d["description"],
        params=[
            ToolParamSpec(
                name=p["name"],
                type=p["type"],
                description=p["description"],
            )
            for p in d["params"]
        ],
        return_type=d["return_type"],
        return_description=d["return_description"],
        success_keys=d["success_keys"],
        error_behavior=d["error_behavior"],
    )
