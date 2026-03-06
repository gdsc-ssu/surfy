import logging

from surfy.domain.models import ActionType, ActorOutput, StepResult, Task
from surfy.domain.ports import BrowserPort, LLMPort

logger = logging.getLogger(__name__)


class ActorService:
    def __init__(self, browser: BrowserPort, llm: LLMPort):
        self._browser = browser
        self._llm = llm

    async def execute_task(self, task: Task, max_steps: int = 15) -> StepResult:
        history: list[tuple[ActorOutput, StepResult]] = []

        result = StepResult(success=False, message="No steps executed")

        for step in range(max_steps):
            page_state = await self._browser.get_page_state()
            output = await self._llm.decide_action(task, page_state, history)

            logger.info(
                "Step %d: %s (target=%s, value=%s)",
                step + 1,
                output.action_type.value,
                output.target_id,
                output.value,
            )

            action = output.to_browser_action()
            result = await self._browser.execute_action(action)
            history.append((output, result))

            if output.action_type in (ActionType.DONE, ActionType.STUCK):
                break

        return result
