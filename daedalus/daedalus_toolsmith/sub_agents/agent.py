import inspect
from typing import AsyncGenerator, Callable
from venv import logger

from google.adk.agents import InvocationContext, BaseAgent
from google.adk.events import Event, EventActions
from typing_extensions import override


class ForgeAgent(BaseAgent):
    builder_agent: BaseAgent
    registration_tool: Callable

    def __init__(
            self,
            name: str,
            description: str,
            builder_agent: BaseAgent,
            registration_tool: Callable
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            builder_agent=builder_agent,
            registration_tool=registration_tool
        )

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        logger.info(f"[{self.name}] Forging started.")

        async for event in self.builder_agent.run_async(ctx):
            logger.info(f"[{self.name}] Event from BuilderAgent: {event.model_dump_json(indent=2, exclude_none=True)}")
            yield event

        result = self.registration_tool(ctx)
        if inspect.isawaitable(result):
            result = await result

        if result and result['status'] == 'success':
            logger.info(f"[{self.name}] Registration successful: {result}")
        else:
            logger.error(f"[{self.name}] Registration failed: {result}")

        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    "registration_tool_result`": result
                }
            )
        )

        logger.info(f"[{self.name}] Forging completed.")
