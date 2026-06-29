from typing import List

from pydantic import BaseModel, Field, field_validator


class ToolParamModel(BaseModel):
    """
    Pydantic schema for a single function parameter.
    """
    name: str = Field(..., description="Parameter name, snake_case")
    type: str = Field(..., description="Parameter type as a Python or JSON type name")
    description: str = Field(..., min_length=1)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError("Parameter 'name' must not be empty")
        return v


class ToolDesignModel(BaseModel):
    """
    Pydantic schema describing the complete ToolDesign output from the LLM.

    NOTE:
    The LLM must output JSON like:
    {
        "tool_name": "...",
        "description": "...",
        "params": [...],
        "return_type": "...",
        "return_description": "...",
        "success_keys": [...],
        "error_behavior": "..."
    }
    """
    tool_name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    params: List[ToolParamModel] = Field(default_factory=list)
    return_type: str = Field(..., min_length=1)
    return_description: str = Field(..., min_length=1)
    success_keys: List[str] = Field(default_factory=list)
    error_behavior: str = Field(..., min_length=1)

    @field_validator("params")
    @classmethod
    def validate_params_not_empty(cls, v):
        if len(v) == 0:
            raise ValueError("Tool must define at least one parameter")
        return v

    @field_validator("success_keys")
    @classmethod
    def validate_success_keys_non_empty(cls, v):
        if len(v) == 0:
            raise ValueError("success_keys must contain at least one entry")
        return v
