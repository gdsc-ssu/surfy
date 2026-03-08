import logging

from surfy.domain.models import ActionType, HistoryEntry, PageState, StepResult, Task
from surfy.domain.ports import BrowserPort, LLMPort

logger = logging.getLogger(__name__)


def _page_fingerprint(page_state: PageState) -> str:
    """Generate a fingerprint for loop detection."""
    return str(hash(page_state.url + page_state.dom_text[:500]))


class ActorService:
    def __init__(self, browser: BrowserPort, llm: LLMPort):
        self._browser = browser
        self._llm = llm

    async def execute_task(self, task: Task, max_steps: int = 15) -> StepResult:
        history: list[HistoryEntry] = []
        fingerprints: list[str] = []

        for step in range(max_steps):
            page_state = await self._browser.get_page_state()

            fp = _page_fingerprint(page_state)
            fingerprints.append(fp)

            if len(fingerprints) >= 5 and len(set(fingerprints[-5:])) == 1:
                logger.warning("Loop detected: 5 identical page states. Forcing STUCK.")
                return StepResult(success=False, message="Loop detected: stuck on same page")

            if len(fingerprints) >= 3 and len(set(fingerprints[-3:])) == 1:
                task = Task(
                    description=(
                        task.description
                        + "\n\n⚠️ 같은 페이지에서 3번 연속 동일 상태입니다. "
                        + "다른 접근 방식을 시도하세요."
                    ),
                    success_criteria=task.success_criteria,
                )

            remaining = max_steps - step
            if remaining <= 2:
                nudge = f"\n\n⚠️ 남은 스텝이 {remaining}개입니다. 현재 상태에서 DONE 또는 STUCK을 선택하세요."
                if remaining == 1:
                    nudge = "\n\n🚨 이것이 마지막 스텝입니다. 반드시 DONE 또는 STUCK으로 종료하세요."
                task = Task(
                    description=task.description + nudge,
                    success_criteria=task.success_criteria,
                )

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
