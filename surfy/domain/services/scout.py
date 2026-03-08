import logging

from surfy.domain.models import ActionType, HistoryEntry, RouteMap, RouteStep, Task
from surfy.domain.ports import BrowserPort, LLMPort

logger = logging.getLogger(__name__)


class ScoutService:
    def __init__(self, browser: BrowserPort, llm: LLMPort):
        self._browser = browser
        self._llm = llm

    async def scout(self, command: str, max_steps: int = 20) -> RouteMap:
        steps: list[RouteStep] = []
        history: list[HistoryEntry] = []
        task = Task(description=f"정찰: {command}")

        for step in range(max_steps):
            page_state = await self._browser.get_page_state()
            output = await self._llm.scout(task, page_state, history)

            logger.info("Scout step %d: %s", step + 1, output.action_type.value)

            route_step = RouteStep(
                url=page_state.url,
                title=page_state.title,
                action_taken=f"{output.action_type.value}({output.target_id or output.value or ''})",
                observed_elements=page_state.dom_text[:500].split("\n")[:10],
                notes=output.memory or output.thinking,
            )
            steps.append(route_step)

            if output.action_type == ActionType.DONE:
                return RouteMap(
                    steps=steps,
                    final_url=page_state.url,
                    scout_summary=output.value or "Scout completed",
                )

            if output.action_type == ActionType.STUCK:
                return RouteMap(
                    steps=steps,
                    final_url=page_state.url,
                    scout_summary=f"Scout stuck: {output.value}",
                )

            action = output.to_browser_action()
            result = await self._browser.execute_action(action)
            history.append(HistoryEntry(action=output, result=result, step=step + 1))

        return RouteMap(
            steps=steps,
            final_url=steps[-1].url if steps else "",
            scout_summary="Max steps reached",
        )
