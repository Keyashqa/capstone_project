import pytest
from google.adk.evaluation.agent_evaluator import AgentEvaluator


@pytest.mark.asyncio
async def test_weather_tool():
    await AgentEvaluator.evaluate(
        agent_module="daedalus_toolsmith",
        eval_dataset_file_path_or_dir="daedalus_toolsmith/daedalus.evalset.json"
    )
