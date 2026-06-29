import json
import re
from typing import Any, Dict, Type

from pydantic import BaseModel, ValidationError

from daedalus_toolsmith.models.agentsmith.schemas import AgentPipelineModel

SCHEMA_REGISTRY: Dict[str, Type[BaseModel]] = {
    "agent_pipeline": AgentPipelineModel
}


def clean_json_string(json_string):
    """Remove markdown JSON code block markers from a string and parse it."""
    if not json_string:
        return ""
    pattern = r'^```json\s*(.*?)\s*```$'
    cleaned_string = re.sub(pattern, r'\1', json_string, flags=re.DOTALL)
    cleaned_string = cleaned_string.strip()
    return json.loads(cleaned_string)


def clean_python_string(python_string):
    """Remove markdown Python code block markers from a string."""
    if not python_string:
        return ""
    pattern = r'^```python\s*(.*?)\s*```$'
    cleaned_string = re.sub(pattern, r'\1', python_string, flags=re.DOTALL)
    return cleaned_string.strip()


def validate_json_against_schema(raw_text: str, schema_name: str) -> Dict[str, Any]:
    """Validate raw JSON string against a named Pydantic schema."""
    if schema_name not in SCHEMA_REGISTRY:
        raise ValueError(f"Unknown schema: {schema_name}")

    schema: Type[BaseModel] = SCHEMA_REGISTRY[schema_name]

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        return {
            "status": "error",
            "error_type": "json_decode",
            "message": str(e),
            "errors": [],
        }

    try:
        model = schema.model_validate(data)
    except ValidationError as e:
        return {
            "status": "error",
            "error_type": "schema",
            "message": "Schema validation failed.",
            "errors": e.errors(),
            "pretty": str(e),
        }

    return {
        "status": "ok",
        "data": model.model_dump(),
    }
