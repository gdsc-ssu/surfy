import logging

from surfy.domain.models import ActionType, HistoryEntry, StepResult, Task
from surfy.domain.ports import BrowserPort, LLMPort

logger = logging.getLogger(__name__)


class ActorService:
    def __init__(self, browser: BrowserPort, llm: LLMPort):
        self._browser = browser
        self._llm = llm

    async def execute_task(self, task: Task, max_steps: int = 15) -> StepResult:
        history: list[HistoryEntry] = []

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

            # 종료 조건 먼저 체크
            if output.action_type == ActionType.DONE:
                return StepResult(
                    success=True,
                    message=output.value or "Task completed",
                )
            if output.action_type == ActionType.STUCK:
                return StepResult(
                    success=False,
                    message=output.value or "Agent stuck",
                )

            action = output.to_browser_action()
            result = await self._browser.execute_action(action)
            history.append(HistoryEntry(action=output, result=result, step=step + 1))

        # max_steps 도달
        return StepResult(
            success=False,
            message=f"Max steps ({max_steps}) reached without completing task",
        )
